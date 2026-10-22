# RecallCircuit — live StudioNet proofs

Recorded 2026-10-20/21 against **StudioNet (chain ID 61999, RPC `https://studio.genlayer.com/api`)** using the `genlayer` CLI v0.39.2, signer account `0xaffE15eEc45b68835cc9E5B4Ab85dD5deaE8e70b`. StudioNet is gasless — no GEN was spent or needed for any transaction below (confirmed: account balance unchanged across the whole run).

No step below used a mock, simulator, or fabricated value. Every status, reason string, and vote tally is copied verbatim from a `genlayer write`/`genlayer call`/`genlayer receipt` response. Where a transaction hash was not captured in the terminal output before truncation, that is stated explicitly rather than invented — the corresponding on-chain state read is cited instead as the evidence.

**How to independently verify any transaction hash below:** `genlayer receipt <hash> --stdout --stderr` against StudioNet (`https://studio.genlayer.com/api`, chain 61999) with the `genlayer` CLI, or any RPC client pointed at that endpoint. The GenLayer explorer at `genlayer-explorer.vercel.app` was returning `503 DEPLOYMENT_PAUSED` at multiple points during this project (noted where relevant below) and should not be assumed to be the only way to check these receipts — the RPC endpoint itself is the source of truth and was used directly for every claim in this document.

This document covers seven deployments: an initial deployment (section A) demonstrating the core adjudication lifecycle with claimant-supplied notice text, a second deployment (section B) after adding real authoritative-source verification, demonstrated against a genuine, currently-live CPSC recall fetched over `gl.nondet.web.render`, a third deployment (section C) after adding an admin-gated authorized-filer allowlist to bound notice-filing DoS/griefing, a standalone `ReleaseGuard` consumer contract (section D) proving the gate is enforceable cross-contract, a fifth deployment (section E) after a security audit identified and fixed several real fail-open gaps in the logic above, a sixth deployment (section F) after a further audit closed the evidence-authenticity gap (a claimant could obtain NOT_AFFECTED/REMEDIATED clearance purely from their own convincing text plus a made-up hash), and a seventh deployment (section G) after a follow-up review found that revocation did not stay effective once a clearance had already happened.

## G. Revocation stays effective after clearance, not just before it (current contract)

A follow-up review of section F's attestation mechanism found that revoking an issuer or a specific attestation **after** a clearance had already set NOT_AFFECTED/REMEDIATED had no effect — `can_release` only checked the assessment's status, never re-checking whether the attestation that produced it was still valid. Fixed by:

- `_current_valid_attestation` now also requires the issuer to be **currently** authorized (not just at submission time) — closing the gap where an issuer revoked between submitting an attestation and someone calling `resolve_appeal`/`resolve_remedy` could still clear a case.
- `Assessment` gained `clearing_attestation_id` (0 = this clearance never depended on any attestation — an ordinary initial `resolve_assessment` NOT_AFFECTED is unaffected by any of this). `resolve_appeal`/`resolve_remedy` record which attestation produced a clearing outcome.
- `can_release` now re-checks, on every call, that any recorded `clearing_attestation_id` is still `ATT_ACTIVE` **and** its issuer is still authorized (`_clearing_attestation_still_valid`) — a later `revoke_attestation` or `revoke_issuer` fails the gate closed again immediately, with no re-resolution needed.

```
Contract Address:  0xBB94AeC77B2de782F0cceB98da157b63A9C7F4b1 (RecallCircuit)
Deploy Tx Hash:     0x80960f8607b3788ea0b4f59b3a3f3e6dfdb23745479ce98f45c052494963a9c8
Status:            FINALIZED, 6/6 execution SUCCESS
ReleaseGuard:      0xF981970C5991CAf6a0BC4d11FdbC693bbE06E757, registry = the address above
ReleaseGuard Tx:    0x9e2f2e52378c195fa1b304e6f4009040a71039feaa12f27215f4ad48dcd7453d
Source hash:        sha256(contracts/recall_circuit.py) = c80c2c21deac396431adb01e9bb5457069045e8d2f2f3b9b59d5aac1816b3b57
```

### G1. Attestation revocation after clearance

Registered a product matching the real CPSC recall (serial `SERIAL-AUDIT4`), filed/verified notice 1 against the real CPSC URL, resolved its assessment to AFFECTED. Owner called `request_remedy(1, ...)`; admin called `authorize_issuer(0xc95df8a18ccae83b6bc5f6e234b8c7859591bfee)` — the same test wallet used in section F, with the same honesty caveat applying. The issuer submitted a remedy attestation (tx `0xa7d63a7fddc89f28e3ff718c0c59d5811043b4779593b79570250abcdc86326c`); `resolve_remedy(1)` (tx `0x2cfaa5839c82b32d3e91c531a2b4b17a44608b07e82448e08c4dbc736033789e`) cleared it:
```json
{"status":5,"clearing_attestation_id":1,"reason":"Remedy verified: ... confirming that this specific unit (SERIAL-AUDIT4) has received the required replacement battery pack remedy."}
```
`can_release(1)` read `true`. The issuer then called `revoke_attestation(1)` (tx `0x96fb238fb82ac860e7570e008851b7ed7881e49ab1a6581da82ffe8674d2f1ba`). **Without any further write to the assessment itself**, `can_release(1)` immediately read back `false`.

### G2. Issuer revocation after clearance

On a second product (serial `SERIAL-AUDIT5`, assessment 2), the same issuer submitted a remedy attestation (tx `0x8fe87571f3ea6fb6679d460817ff7cb2300ba2a5f85dfaebdd474f8693678dc1`) and `resolve_remedy(2)` (tx `0x0cc7a98649437af43e0b285bc4c5beade7f6c3ea694123cc02735f031b778d2d`) cleared it (`clearing_attestation_id: 2`, `can_release(2)` → `true`). The admin then called `revoke_issuer(0xc95df8a18ccae83b6bc5f6e234b8c7859591bfee)` (tx `0xf8f45612fc9ad836d216f8aa53165debff1ab039894f07ae67210d0c5dfc9cfd`) — revoking the issuer's entire registry entry, not any specific attestation. `can_release(2)` immediately read back `false`. Cross-contract `ReleaseGuard.can_release(2)` on the new deployment independently confirmed `false`, as did `ReleaseGuard.can_release(1)` (G1's product, still revoked from the attestation-level revoke).

### G3. Issuer revocation before resolution, and ordinary clearances unaffected

Covered in Direct Mode (`test_issuer_revocation_before_resolution_blocks_clearance`, `test_ordinary_not_affected_assessment_is_unaffected_by_issuer_revocation`) rather than live, to avoid spending further live transactions demonstrating what the live G1/G2 runs already establish structurally: `_current_valid_attestation`'s issuer-authorization check is identical whether it runs before or after the first resolution attempt, and `clearing_attestation_id` staying `0` for a never-attested clearance means `can_release` never calls `_clearing_attestation_still_valid` for it at all.

## F. Independent evidence attestors — mandatory, case-bound, non-self-attested clearance (current contract)

```
Contract Address:  0x3b8E072EF980725C30c974438C8a1928080baaf8 (RecallCircuit)
Deploy Tx Hash:     0xb0edf6dc4dde432cbdc2b9ad03797f57b69022742da475278f2d74ee7c626f0f
Status:            FINALIZED
ReleaseGuard:      0xd53470c49c25BCB545b2df4acbC6F25C0Ef027dC, registry = the address above
ReleaseGuard Tx:    0x8e48dd939e3c5450ca8077456c2fa7e7fc4529a7f8f755d5e63a39781f4baa51
```

**Important honesty note before anything else:** this section uses a locally-created GenLayer test wallet (`recall-outsider`, `0xc95df8a18ccae83b6bc5f6e234b8c7859591bfee`) as the "independent evidence issuer." Authorizing it with `authorize_issuer` only grants it the on-chain *privilege* to submit attestations — **it is not, and must never be represented as, proof that this address is a real manufacturer or authorized repair provider.** No genuine independent attestor (a real manufacturer's or repair network's own key) was available for this session. Everything below demonstrates that the *authorization and binding mechanism* works correctly; it does **not** demonstrate real-world evidence authenticity, which remains unproven and must be treated as a live-deployment prerequisite, not something this project can self-certify.

### F1. Claimant's own text, alone, cannot clear a hold — even with a hash

Registered a product matching the real CPSC recall (`The Blue Cactus Company RWX-RBP02`, serial `SERIAL-AUDIT2`), filed and verified notice 1 against the real CPSC URL (tx `0x9441cee1...`, `0xd560c70b...`, `0x1adda43f...`), opened and resolved its assessment to AFFECTED (tx `0xeea981af...`, `0x21edfa4c...`).

The owner called `request_remedy(1, "Unit SERIAL-AUDIT2 was repaired, replacement part installed.", "sha256:claimant-only-evidence")` (tx `0xc5d3259a972bb556439e90dae69acf7f331f45c338c860c62be53bcd7104e633`) — a convincing claim, naming the exact serial, with a hash attached. `resolve_remedy(1)` (tx `0xafe53e08cbaca7202c412299465f33e40cbd0d471810ecdf97ea040da4cffd2f`) did **not** clear it:
```json
{"status":3,"reason":"No valid independent remedy-completion attestation; quarantine preserved"}
```
No LLM call was even made — the missing-attestation check runs before any classification. This is the exact bypass the brief named, and it is now closed: claimant text plus a made-up hash is insufficient by construction, not by LLM judgment.

### F2. Self-attestation and unauthorized issuers rejected

The deployer/admin account (also the product owner) attempted `submit_attestation(1, EVIDENCE_REMEDY_COMPLETED, ...)` directly — never having been authorized as an issuer. Reverted on-chain with the decoded payload **`"sender not an authorized evidence issuer"`** (tx `0x5b5e05ca18dfd3a5c0133dc320a5d53e562d223097ec969ec6a1474ab46c31a9`). The admin itself is never auto-granted issuer status (unlike `authorize_filer`, where the deployer is auto-trusted) — this is enforced in Direct Mode tests for both "admin never implicit issuer" and "owner cannot self-attest even if separately authorized as an issuer."

### F3. A properly authorized, non-owner issuer's attestation — mandatory and sufficient together with validator agreement

Admin called `authorize_issuer(0xc95df8a18ccae83b6bc5f6e234b8c7859591bfee)` (tx `0x8b633a9922438aa49c4b49c6a0faf71702cfa7b20e6f2332497c35142f8795c3`); `is_authorized_issuer` read back `true`.

On a second product (`SERIAL-AUDIT3`, assessment 2, independently resolved AFFECTED against the same real recall), the owner called `request_remedy(2, ...)`. The **test-wallet issuer** then called:
```
submit_attestation(2, EVIDENCE_REMEDY_COMPLETED,
  "sha256:cdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcd",
  "Authorized repair provider test-wallet attestation: unit SERIAL-AUDIT3 received the CPSC-specified replacement battery pack per remedy instructions.",
  "")
```
(tx `0xe7e9f45adf82d6ef398a34cbc24d07d0c58acad377724a4b433008ed80f6be31`). `get_attestation(2)` read back every bound field captured by the contract itself from live chain state — `assessment_id:2, product_id:2, serial:"SERIAL-AUDIT3", notice_id:1, notice_digest:"90a387ec...", product_revision:1, issuer:"0xc95df8...", status:1 (ACTIVE), consumed:false` — not supplied by the issuer, structurally impossible to mismatch.

`can_release(2)` read `false` immediately before resolution — an attestation existing is not by itself clearance. `resolve_remedy(2)` (tx `0x6c06afd701168f0a95aca871c1808edc01775c51a6473503da24f93ba567fe22`) then independently re-ran the leader+validator classification using the **issuer's** attested description (never the owner's text) and produced:
```json
{"status":5,"reason":"Remedy verified: Attested repair record confirms SERIAL-AUDIT3 received CPSC-specified replacement battery pack per remedy instructions from authorized repair provider."}
```
`get_attestation(2)['consumed']` read back `true`. `can_release(2)` read `true`. Cross-contract `ReleaseGuard.can_release(2)` on the new deployment independently confirmed `true`, while `ReleaseGuard.can_release(1)` (the first product, still stuck UNCERTAIN from F1) independently confirmed `false` — both read from a separate contract address.

### What F does not demonstrate

- **Real-world attestor authenticity is unproven.** The "issuer" here is a GenLayer test wallet with no real-world identity binding. The mechanism (registry, case-binding, mandatory gating, consumption) is proven; whether any given on-chain address is really a manufacturer or repair provider is **not**, and cannot be, proven by this contract alone — see the honesty note above.
- **Adversarial scenarios not reproduced live** (wrong-case attestation, tampered/mismatched public source, duplicate/replay rejection, revoked/stale-by-generation attestation, leader tampering caught by the validator, issuer revocation before resolution) are Direct Mode evidence (`tests/direct/test_recallcircuit_direct.py`), not live-chain evidence — StudioNet's current real recall data doesn't let these specific adversarial conditions be constructed safely without risking real state corruption across sessions. All are covered in the test suite; run `python -m pytest tests --collect-only -q` for the exact, current, verifiable count rather than trusting any specific number written in prose here.
- **No source-fetch verification was exercised live** in this section (`source_url=''` throughout) — the optional public-source independent-fetch path (for when an issuer cites a public record) is Direct Mode evidence only (`test_tampered_evidence_source_fails_independent_check`, `test_source_fetch_failure_invalidates_attestation`).

## E. Security audit remediation — fail-closed invariants, consensus binding, evidence binding (current contract)

An audit of the section C/D contract identified concrete fail-open bugs, not just missing features. Each was fixed and is demonstrated live below against the **real CPSC recall** used throughout this document.

```
Contract Address:  0x6946f6912A3cbE14d0C1A8b793bbF1F6C7342b84 (RecallCircuit)
Deploy Tx Hash:     0xb8f5db59c740b09eb23f745212c2c90317d31558c4410cbcb58ada399d40bb7c
Status:            FINALIZED, 6/6 execution SUCCESS
ReleaseGuard:      0x251367Ba0388dE3bD9e2783C6d18B6354eE349Cc, registry = the address above
ReleaseGuard Tx:    0x81a4fb12aeff157d8971cf5a45e4908909e4c9c1ed8fbbc44c65fd6942b9b069
```

### E1. Fail-open bug: re-verification could silently lift an established hold

**The bug:** `verify_source_notice` previously set `n.verified = bool(result['match'])` unconditionally on every call. `can_release` skips any notice that is not `verified`. So calling `verify_source_notice` a second time on an *already-verified, currently-gating* notice -- say, because the live page was temporarily unreachable, or had been edited -- would flip `verified` back to `False` and silently stop that notice from blocking an affected product, with no owner action and no new assessment. **Fix:** verification is now monotonic — `verify_source_notice` refuses outright if the notice is already verified.

Live: registered product 1 (`The Blue Cactus Company RWX-RBP02`, serial `SERIAL-AUDIT1`), filed and verified notice 1 against the real CPSC URL (tx `0xbad4ef0f...`, `0xbcbe94fb...`), resolved assessment 1 to AFFECTED (tx `0xc207cb31f7a703fe651aa8c439ed78b25650d14d031c0636257feeb2b9cb6677`). Calling `verify_source_notice(1)` again reverted on-chain with the decoded payload **`"notice already verified"`** (tx_id `0x5efa0f5ad575f8a681258c98f14341c5275f7aaba9c360b8fe578dfa856e7a1a`).

### E2. Fail-open bug: supersession dropped the hold during the replacement window

**The bug:** `supersede_notice` immediately set the predecessor's `active = False`, while the successor notice starts `verified = False`. `can_release` requires a notice to be both `active` and `verified` to count at all — so for any window between calling `supersede_notice` and the successor being independently verified, **neither** notice gated the product, even though it had never been cleared. **Fix:** `supersede_notice` no longer deactivates the predecessor. The predecessor is only retired, as a side effect of `verify_source_notice` succeeding on its successor ("safe replacement activation"). If the successor is never verified, the predecessor gates forever — the safe failure mode.

Live, demonstrated both ways against the real recall:
- Called `supersede_notice(1, ...)` with text that fabricated a non-existent "batch N2" (tx `0x1fea5ba79ad82fbb9320ea6190a44f69f38a55b6dab1e601d63253567b3980ad`) → notice 2. `get_notice(1)['active']` read back `true` immediately after — the predecessor's hold was never dropped.
- `verify_source_notice(2)` (tx `0x7f63e42cc4867fe3ee30220a86e07538452d90e41e03bf581cf80439acc1e94e`) independently re-fetched the real page and correctly judged the fabricated "batch N2" claim a **non-match** — `get_notice(2)['verified']` read back `false`, and `get_notice(1)['active']` stayed `true`. This was not staged: the fabricated detail genuinely isn't on the live page, so the real LLM comparison genuinely rejected it.
- `supersede_notice(1, ...)` again, this time with text faithfully matching the real page (tx `0x188a391b5b9d2fff733a92a0e4c71207e742c5cb678a021289be4d7e38ee37b3`) → notice 3. `verify_source_notice(3)` (tx `0xabc4675f22d1bdcd3be6e66fd4a5bbadc0889f5aa98371f8ee14a371bb10db43`) succeeded — and **only at that point**, `get_notice(1)['active']` flipped to `false` while `get_notice(3)['active']` read `true`.

### E3. Consensus binding: validator must recompute the digest, not just the match verdict

**The bug:** the validator closure only compared `observed['match'] == proposed['match']`, never the digest. A dishonest leader could report a correct `match` boolean while binding an arbitrary `digest` string on-chain — nothing checked it against what validators actually fetched. **Fix:** the validator now requires the full expected shape (`{'match','reason','digest'}`, with `match` strictly `bool` and `digest` strictly `str` — no partial-match or permissive coercion) and requires its own independently-fetched `digest` to equal the leader's. Demonstrated in Direct Mode (`test_validator_rejects_fabricated_digest_even_if_match_agrees`): changing the live page's content between the leader's fetch and the validator's re-fetch causes `run_validator()` to return `False` even when both fetches still agree on `match=True`. This specific adversarial timing isn't reproducible against a real, currently-static StudioNet page, so it is Direct Mode evidence, not live-chain evidence — the live chain evidence above (E1/E2) already shows the real digest (`90a387ec...`) being bound to the real page content.

### E4. Authoritative evidence binding: assessments no longer cite unverified claimant text

**The bug:** `open_assessment` set `a.evidence_hash = str(n.source_hash)` — the claimant's own, never-independently-checked string from `file_notice` — instead of the notice's actual verified `source_digest`. **Fix:** `a.evidence_hash` is now always `n.source_digest`, which by construction only exists after an independent leader+validator fetch succeeded.

Live: `get_assessment(1)['evidence_hash']` read back `90a387ec19452d3a7d5340736a686294cf81fba298fce01000ce9fbaecb58f21` — the real digest of the live CPSC page — not `"sha256:claimant-unverified"`, the string that was actually passed to `file_notice`.

### E5. Unit-bound, independently-committed appeal/remedy evidence

**The bug:** `appeal_assessment`/`request_remedy` accepted any free-text evidence with no binding to the specific unit and no commitment artifact. **Fix:** both now require (a) the evidence text to literally reference the product's serial number, rejected outright before any LLM judgment runs, and (b) a mandatory, non-empty `evidence_hash` commitment, recorded on-chain (`get_appeal`/`get_remedy`).

Live: `appeal_assessment(1, "This unit was never affected, please clear it.", "evidence-hash-1")` reverted with the decoded payload **`"evidence must reference the unit serial number"`** (tx `0xeebbc767ef8bdc677b0de73d962f65b959b65bb4f941e8c9c873918bd97f5e3e`). Filing again with `"Unit SERIAL-AUDIT1 was manufactured in a pre-production test lot..."` succeeded (tx `0xee263001d84af1d5de6e113ad5618d47dbbce95b36c695486e5e2c59aff64914`); `resolve_appeal(1)` (tx `0xcfa3f36c1d8f8acd81c6ee2982ecd8b723fdf87478281f97181bb5a8ccfd4eb4`) independently re-ran the scope classification with that evidence and cleared the unit to NOT_AFFECTED; `get_appeal(1)` reads back `evidence_hash: "sha256:appeal-evidence-doc-1"`, the real commitment supplied. Cross-contract `ReleaseGuard.can_release(1)` on the new deployment read back `true` immediately after, confirming the clearance propagates.

### E6. Assessment uniqueness: no retry-spam, defined challenge lifecycle

**The bug:** `open_assessment` had no uniqueness check and no capacity bound, so the same (product, notice, revision) triple could be assessed arbitrarily many times, and `can_release`'s nested scan over all assessments had no bound on their count. **Fix:** `open_assessment` now rejects a duplicate for the same (product, notice, revision); `MAX_ASSESSMENTS`/`MAX_APPEALS`/`MAX_REMEDIES` bound the respective counters. The only sanctioned way to re-challenge an assessment is `appeal_assessment`, a bounded, single-shot, auditable lifecycle (`a.appealed` already prevented a second appeal on the same assessment).

Live: `open_assessment(1, 1)` a second time, after the first already existed, reverted with the decoded payload **`"assessment already exists for this product/notice/revision"`** (tx `0x44f5b9115b40833f35d72923658e3c4ad611b858c4d9d3fca3427340c8de8f8e`); `get_assessment(2)` confirmed no second assessment was created.

### Not addressed by this remediation (explicit scope limits)

- Appeal/remedy evidence commitments (`evidence_hash`) are auditable on-chain commitments, not independently fetched or cryptographically verified artifacts — the contract does not know whether the hash corresponds to anything real, only that the submitter committed to a specific value alongside unit-bound text.
- The authorized-filer allowlist (section C) and the regulator domain allowlist remain single-admin/hardcoded, as documented there; this remediation did not add staking or governance.
- Stress, replay, and race tests beyond the specific hostile transitions above were not performed.

## D. ReleaseGuard — cross-contract gate enforcement (live)

`contracts/recall_gate.py` was stale against the abandoned contract API (`is_release_allowed`/`get_asset`) and has been fixed to call the real `can_release`/`get_product` methods on the section C `RecallCircuit` deployment.

```
Contract:          ReleaseGuard (contracts/recall_gate.py), registry = 0xFeBd68B38e06245c7F319C7e9684510D89923880
Contract Address:  0xE703DAd1c30Bb469A3C0B3d32028D8Ab500AD647
Deploy Tx Hash:     0x13133f3eed124d165d272d88fbce146b87f724232bce1b04e36e990dc2b6eaae
Status:            FINALIZED
```

1. Registered product 1 on the section C `RecallCircuit` (`Gate Co GATE-1`, no notices against it) — `can_release(1)` on RecallCircuit itself returned `true`. A cross-contract read, `ReleaseGuard.can_release(1)`, independently returned `true` from a different contract address, confirmed on-chain.
2. `ReleaseGuard.record_release(1, <recipient>)` succeeded, tx `0x57cff3c2cfb1a16898e5d56b97ee93e22255eaee5b7b7a511b72cdc5d3434926`; its decoded return value was `1` (its internal `shipment_count` incremented from 0), proving the write path, not just the view path, performs a real cross-contract call and only proceeds when the registry allows it.
3. Filed and verified the same real CPSC recall (26-791) against the current `RecallCircuit`, registered a second product matching it (`The Blue Cactus Company RWX-RBP02`, product 2), and resolved its assessment to AFFECTED — `RecallCircuit.can_release(2)` → `false`.
4. `ReleaseGuard.can_release(2)` — a fresh cross-contract read from the `ReleaseGuard` address — also returned `false`.
5. `ReleaseGuard.record_release(2, <recipient>)` was attempted, tx `0x0e3dbba89fa6ca3c3a0beaf7eaa7b666a640a37874466f85e6166ef966c3d7cf`. Execution reverted; the receipt's decoded revert payload reads **`"RecallCircuit blocked release"`** — the exact `gl.vm.UserError` message from `ReleaseGuard.record_release`, proving the cross-contract call chain genuinely ran `IRecallCircuit(registry).view().can_release(...)` and enforced its result, rather than any local/cached assumption.

This demonstrates that `can_release` is not merely an advisory read for whoever calls `RecallCircuit` directly — a separate, independently deployed contract can gate its own write path on it in real time over a live cross-contract call.

## C. Authorized-filer allowlist (current contract)

```
Contract Address:  0xFeBd68B38e06245c7F319C7e9684510D89923880
Deploy Tx Hash:     0x91b3e1d9ace50a44acb2061dd3e46bb654b561d2ab0b561c8e96c0eb935edd39
Status:            FINALIZED
```

`file_notice` now additionally requires `gl.message.sender_address` to be the contract admin (set to the deployer at construction) or an address the admin explicitly authorized via `authorize_filer`. This is on top of, not instead of, the domain allowlist and `verify_source_notice` from section B.

1. `is_authorized_filer(0xaffE...e70b)` (the deployer) → `true` immediately after deploy, with no explicit call.
2. Created a second local account, `recall-outsider` (`0xc95df8a18ccae83b6bc5f6e234b8c7859591bfee`), unrelated to the admin.
3. **Rejected:** `recall-outsider` called `file_notice(...)` before being authorized. Transaction `0x92092d663c86904056aff59c6d069742951306c853cd44bdd0f632593acac5eb` was `ACCEPTED`/`FINALIZED` at the chain-lifecycle level (deterministic revert is itself a valid consensus outcome), but execution reverted with `sender not an authorized filer`: confirmed by `get_notice(1)` erroring as unknown immediately after — no notice was created.
4. Admin called `authorize_filer(0xc95df8...91bfee)`, tx `0x5f0c39b131179391faeb56ad65a3b20e78898930a549a19e1bb62a62397076e0`. `is_authorized_filer` then read back `true`.
5. **Allowed:** `recall-outsider`, now authorized, called `file_notice(...)` for the same real CPSC URL from section B, tx `0x894d235910667ab48dd61b95a9e7df06be28ec2040ec0e30d6b99dcbbc5759c9` → notice 1 created successfully, confirmed by `get_notice(1)`.
6. Ran `verify_source_notice(1)` on that notice (tx `0x78adc556c42f8e8ca93748636e6c79e59190ebe94731516bf02f71b990b08699`): the live fetch succeeded (`source_digest` matched the same real page digest from section B1), but the independent LLM comparison correctly judged the claimant's actual text — a meta-comment about being authorized, not an actual recall description — as **not** a faithful summary of the live page, so `verified` stayed `false`. This was not a staged failure; it is the real match check correctly catching a notice whose text doesn't substantively describe the recall.
7. Admin called `revoke_filer(0xc95df8...91bfee)`, tx `0xd7c06e225d3159920b549dd76c923cd39e0088e49b6e8e8fcc883868a0953652`. `is_authorized_filer` then read back `false` again, so the previously-authorized address is locked out.

This demonstrates a real admin-controlled allowlist gating who may file notices at all, independent of the domain/source checks in section B, closing out the remaining part of `CLAUDE_FINISH_PROMPT.md` item 3 that was feasible without a staking/token economy.

## B. Authoritative source verification (current contract)

```
Contract:          RecallCircuit (contracts/recall_circuit.py, with verify_source_notice)
Contract Address:  0xE8F4522CA39001F2e073788623f0297f6d883963
Deploy Tx Hash:     0xa9795ea75c725d3b3824cc725b3ee2339303837f6fa897d893380ba1ea6fa38d
Status:            FINALIZED, 6/6 execution SUCCESS
```

### B1. Real regulator source, fetched live and independently verified

Used the actual CPSC Recalls REST API (`https://www.saferproducts.gov/RestWebServices/Recall?ProductName=battery&format=json`, documented at `https://www.cpsc.gov/Recalls/CPSC-Recalls-Application-Program-Interface-API-Information`) to find a genuine, currently-published recall: **RecallID 10997, Recall Number 26-791**, "The Blue Cactus Company Reclining Chair Battery Packs Recalled Due to Fire and Burn Hazards; Sold on Amazon," dated 2026-09-24, model `RWX-RBP02`, published at `https://www.cpsc.gov/Recalls/2026/The-Blue-Cactus-Company-Reclining-Chair-Battery-Packs-Recalled-Due-to-Fire-and-Burn-Hazards-Sold-on-Amazon` — confirmed live in-browser before use.

1. `register_product("The Blue Cactus Company","RWX-RBP02","N/A","SERIAL-BC-001","2026-03","sha256:bluecactus001")` → product 1, tx `0x0425c34c8e884cf11e03f38668b1ee1bc2528f036deea0f6b95a24c5008224c8`, 6/6 SUCCESS.
2. `file_notice("CPSC", <the real cpsc.gov URL above>, "26-791", <claimant text closely paraphrasing the real recall>, "sha256:pending-until-verified")` → notice 1, tx `0x806f5376eb9ca8198b81df95ed44771dd796a6e3c417d2e791918a09d5990c2a`.
3. `verify_source_notice(1)` — **leader and validators each independently called `gl.nondet.web.render` against the live cpsc.gov URL**, hashed the fetched page, and ran an independent LLM comparison of the live text against the claimed text. Tx `0x6c44777aaaeef539c3606682415f6e9200ff2eb3c145e31eef6db68574f885ce`, `MAJORITY_AGREE`, votes `[AGREE, IDLE, DISAGREE, AGREE, AGREE]` — a genuine validator disagreement, with the majority still holding.
   `get_notice(1)` afterward:
   ```json
   {"id":1,"verified":true,"source_digest":"90a387ec19452d3a7d5340736a686294cf81fba298fce01000ce9fbaecb58f21",
    "url":"https://www.cpsc.gov/Recalls/2026/The-Blue-Cactus-Company-Reclining-Chair-Battery-Packs-Recalled-Due-to-Fire-and-Burn-Hazards-Sold-on-Amazon"}
   ```
   `source_digest` is the real `sha256` hex digest of the live page text as fetched inside GenVM at verification time — not a precomputed or claimant-supplied value.
4. `open_assessment(1,1)` → assessment 1, tx `0x18378250819b20565ee0af442f6bc53671b3fff91d945264839acb3b843a0828`, 6/6 SUCCESS. `resolve_assessment(1)` → tx `0x49f332ce97bcdf676372f03fdae8bbf2791d999f7cf1f9ea91e29f5f175fe1ed`.
   ```json
   {"id":1,"status":1,"reason":"Product matches recalled model RWX-RBP02 from The Blue Cactus Company. Manufacturing date 2026-03 falls within recall period. No evidence of repair/replacement provided."}
   ```
   `can_release(1)` → `false`. A genuine, currently-live government recall was fetched over the network from inside the contract, hashed, confirmed to match the on-chain claim by independent consensus, and correctly blocked a matching product — with no mocked web or LLM response anywhere in this sequence.

### B2. Fabricated claim against a real page — rejected

`file_notice("CPSC", <same real cpsc.gov URL>, "FAKE-999", "URGENT FABRICATED CLAIM: this notice falsely states CPSC recalled all toasters nationwide effective immediately, unrelated to the real battery pack recall on this page.", "sha256:forged")` → notice 2, ACCEPTED.
`verify_source_notice(2)` → ACCEPTED (independent fetch+compare again ran for real).
`get_notice(2)`:
```json
{"id":2,"verified":false,"source_digest":"90a387ec19452d3a7d5340736a686294cf81fba298fce01000ce9fbaecb58f21",
 "text":"URGENT FABRICATED CLAIM: ..."}
```
Note the `source_digest` matches the real page's digest from B1 (same URL, same live content) — the live fetch succeeded, but the independent LLM comparison correctly judged the claimed text to be an unfaithful, fabricated summary of that real content, so `verified` stayed `false`.
`open_assessment(1, 2)` was then attempted against this unverified notice and reverted (`notice not source-verified`): confirmed by `get_assessment(2)` erroring as unknown — no assessment was ever created from a fabricated claim, even one filed against a real, reachable regulator URL.

## A. Core adjudication lifecycle (initial deployment, claimant-supplied notice text)

```
Contract:          RecallCircuit (contracts/recall_circuit.py, pre-verify_source_notice)
Contract Address:  0x8485533fAB15D14F5231B97C51e7EDcE3fF12377
Deploy Tx Hash:     0x29a431c94f2b67ffc536d700d289d6f26370417c29aa3cc3801a413637743ca0
Status:            FINALIZED
Consensus:         MAJORITY_AGREE, round 0, 5/5 validators committed+revealed, votes [AGREE, AGREE, AGREE, AGREE, AGREE]
Validators:        0x0B50B270Eba5D9B780272C4Cf4720260177e761D, 0xf1C7551292319EE334e2D8A24eAC108Bd4C63b21,
                    0x6a4179A851B3747A458baD2f089AB2EeFE0eBbAb, 0x5Bbbd7cdD63c0ba7f088038Cb049bDDAbE4F6fd1,
                    0x8a876C3F3a4783Bd123982bcBF3c672dc0239004
```
Confirmed with `genlayer schema 0x8485...2377` — the live on-chain ABI matched the source method set at that time. **This deployment predates `verify_source_notice`** — every notice below was claimant-supplied text, not independently fetched, which is exactly the gap closed in section B. It remains below as evidence of the core adjudication/appeal/remedy/propagation/supersession lifecycle, which did not change when source verification was added (the new contract only adds a precondition before `open_assessment`).

## Lifecycle flows executed on-chain

All calls below target `0x8485533fAB15D14F5231B97C51e7EDcE3fF12377`. Transaction hashes are given where captured; all other steps are evidenced by the post-call on-chain reads shown.

### 1. Register affected product (product_id = 1)
`register_product("Example Co","BAT-1","B1","SERIAL-001","2026-01","sha256:1a2b3c")` — ACCEPTED, 5/5 AGREE.
Read-back `get_product(1)` returned the exact stored fields, `owner = 0xaffE15eEc45b68835cc9E5B4Ab85dD5deaE8e70b`, `revision = 1`.

### 2. File recall notice (notice_id = 1)
`file_notice("CPSC","https://www.cpsc.gov/Recalls/2026/example-battery-recall","26-500", <notice text>, "sha256:notice-aaa111")` — ACCEPTED (4/5 AGREE, 1 IDLE round-robin; majority held).
**This notice's authenticity is claimant-asserted, not independently fetched from cpsc.gov by the contract** — consistent with the documented limitation in `docs/STATE_MACHINE.md`. It is used here as synthetic demonstration text styled on a real CPSC notice format, not as a live scrape of the regulator's site.

### 3. Affected classification, real validator consensus
`open_assessment(1,1)` → assessment_id 1, ACCEPTED 5/5 AGREE.
`resolve_assessment(1)` → ACCEPTED 3/5 AGREE (2 IDLE).
`get_assessment(1)`:
```json
{"id":1,"product_id":1,"notice_id":1,"status":1,"pending":false,"appealed":false,
 "reason":"Matches recall notice exactly: Example Co model BAT-1, batch B1. Notice specifically recalls BAT-1 batteries from batch B1; no exclusion or remedy evidence provided."}
```
`can_release(1)` → `false`. **AFFECTED** verdict produced by a real LLM leader+validator round on StudioNet, not a mocked response.

### 4. Near-match, scope-excluded product (product_id = 2) — NOT_AFFECTED
`register_product("Example Co","BAT-9","B9","SERIAL-900","2026-05","sha256:zzz999")` then `open_assessment(2,1)` → assessment_id 2 → `resolve_assessment(2)`:
```json
{"id":2,"product_id":2,"notice_id":1,"status":2,
 "reason":"Recall covers Example Co model BAT-1 from batch B1 only. Product is model BAT-9, batch B9, which is affirmatively outside the recalled model and batch scope."}
```
`can_release(2)` → `true`.

### 5. Successful remedy with credible evidence (assessment 1)
`request_remedy(1, "Unit SERIAL-001 was repaired by authorized Example Co technician on 2026-10-15 ... service ticket EC-88213.")` → remedy_id 1, ACCEPTED.
`resolve_remedy(1)` → ACCEPTED. `get_assessment(1)`:
```json
{"id":1,"status":5,"generation":2,
 "reason":"Remedy verified: Unit SERIAL-001 was repaired by an authorized technician on 2026-10-15 with the specified replacement battery pack (BAT-1R) as per CPSC remedy instructions (ticket EC-88213)."}
```
`can_release(1)` → `true` (REMEDIATED clears the hold).

### 6. Failed/forged remedy, no credible evidence (product 3)
`register_product("Example Co","BAT-1","B1","SERIAL-777",...)` → product 3, assessed AFFECTED (assessment 3).
`request_remedy(3, "trust me it's fine")` → remedy_id 2 → `resolve_remedy(2)`:
```json
{"id":3,"status":3,"reason":"Remedy not independently established"}
```
`can_release(3)` → `false`. Validators correctly refused to clear a unit on unsubstantiated remedy text.

### 7. Appeal and re-evaluation with exculpatory evidence (product 4)
Product 4 (`Example Co BAT-1 B1 SERIAL-555`) initially assessed AFFECTED (assessment 4, same scope match as above).
`appeal_assessment(4, "Serial SERIAL-555 was manufactured in a separate pre-production test lot ... lot code B1-TEST, not released for sale ...")` → appeal_id 1, ACCEPTED (3 AGREE/2 IDLE).
`resolve_appeal(1)` → ACCEPTED (3 AGREE / 1 DISAGREE / 1 IDLE — genuine validator split, majority held).
```json
{"id":4,"status":2,"generation":2,"appealed":true,
 "reason":"Credible evidence establishes the unit was a pre-production test lot (B1-TEST) and was never part of the commercially sold batch B1 shipment, which is the sole scope of recall 26-500."}
```
`can_release(4)` → `true`.

### 8. Component propagation through an assembled product
`register_product("Assembler Inc","ASM-7","A7","SERIAL-ASM1",...)` → product 5.
`link_component(5, 1)` — links the (now-remediated) battery as a component, ACCEPTED 5/5 AGREE.
Before product 5 has its own assessment: `can_release(5)` → `false` — fail-closed, because the gate requires a current assessment for **every** product in the graph (including the assembled unit itself), not just its components.
`open_assessment(5,1)` → assessment 5 → `resolve_assessment(5)`:
```json
{"id":5,"status":2,"reason":"Product batch A7 and model ASM-7 are explicitly excluded from the recall, which only applies to Example Co BAT-1 batteries from batch B1."}
```
`can_release(5)` → `true` once both the assembled product and its remediated component are current and cleared.

### 9. Notice supersession and stale-notice invalidation
`supersede_notice(1, <revision 2 text widening scope to batch B1 and B2>, "sha256:notice-aaa222")` → notice_id 2, ACCEPTED 5/5 AGREE.
`get_notice(1)` → `active: false, version: 1`. `get_notice(2)` → `active: true, version: 2, previous_id: 1`.
`open_assessment(2, 1)` (product 2 against the **superseded** notice 1) — transaction ACCEPTED at the chain-lifecycle level, but contract execution reverts with `superseded notice`: confirmed by `get_assessment(6)` returning "unknown assessment" (no assessment 6 was created by that call).
`open_assessment(5, 2)` → assessment 6 → `resolve_assessment(6)`, tx hash `0x65e9e46c9ef3a379893c938e58a4b6485f7702a148593881b5f6f0a01339c9af`:
```json
{"id":6,"product_id":5,"notice_id":2,"status":2,
 "reason":"The product is manufactured by Assembler Inc (Model ASM-7, Batch A7), which does not match the recalled manufacturer (Example Co) or the specific affected batches (B1, B2) for model BAT-1."}
```

## What this demonstrates

- Real multi-validator consensus (round-based commit/reveal, majority rule, occasional genuine DISAGREE/IDLE votes) on every write, not a single-node mock.
- `gl.vm.run_nondet_unsafe` leader/validator re-execution producing independently-derived, structurally-validated verdicts (AFFECTED / NOT_AFFECTED / UNCERTAIN) from a real LLM call per `classify_prompt`, confirmed across affected, excluded, remedied, forged-remedy, and appealed scenarios.
- Fail-closed behavior holding under: an unassessed node in the dependency graph, an open/forged remedy, a superseded notice, and a structural revision.

## What this does **not** demonstrate (explicit scope limits)

- **Source verification is a re-fetch-and-compare consensus check, not cryptographic proof of government authorship.** `verify_source_notice` independently fetches the claimed URL via `gl.nondet.web.render` and has leader+validators agree the claimed text faithfully summarizes what was fetched; it does not verify TLS/domain ownership cryptographically beyond what the GenVM network's own HTTP fetch does, and it does not hold a CPSC-signed artifact. Domain trust is still anchored to the `AUTHORIZED_SOURCE_PREFIXES` allowlist (`cpsc.gov`/`www.cpsc.gov`) hardcoded in the contract, not to an on-chain governance process.
- **No staking/slashing economy.** Section C adds a single-admin authorized-filer allowlist, demonstrated live, which bounds who may call `file_notice` at all — but the admin is one address set at deployment, not an on-chain governance process, multisig, or stake-weighted mechanism. A compromised or malicious admin could authorize arbitrary filers. A flood of plausible-looking but ultimately-unverified notices from an authorized-but-careless filer was not load-tested, though each one that fails verification still cannot gate any product (see `can_release`, which skips unverified notices).
- A handful of transaction hashes from the section A run were not retained in the captured terminal output (truncated via `tail`, and the GenLayer explorer at `genlayer-explorer.vercel.app` returned `503 DEPLOYMENT_PAUSED` when checked afterward to recover them). Every transaction without a recorded hash in section A is still verified by its on-chain state read, not by narrative claim alone. Section B hashes were captured directly via `grep` on live command output.
- `ReleaseGuard`'s `authority` (the shipper allowed to call `record_release`) is a single address set at deployment, with no transfer or multi-shipper support — consistent with it being a minimal proof-of-integration contract, not a production shipping system.
- Only `cpsc.gov` was exercised as an authorized source domain; no other regulator domain was tested.
