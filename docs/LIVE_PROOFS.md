# RecallCircuit — live StudioNet proofs

Recorded 2026-10-20/21 against **StudioNet (chain ID 61999, RPC `https://studio.genlayer.com/api`)** using the `genlayer` CLI v0.39.2, signer account `0xaffE15eEc45b68835cc9E5B4Ab85dD5deaE8e70b`. StudioNet is gasless — no GEN was spent or needed for any transaction below (confirmed: account balance unchanged across the whole run).

No step below used a mock, simulator, or fabricated value. Every status, reason string, and vote tally is copied verbatim from a `genlayer write`/`genlayer call`/`genlayer receipt` response. Where a transaction hash was not captured in the terminal output before truncation, that is stated explicitly rather than invented — the corresponding on-chain state read is cited instead as the evidence.

This document covers two deployments: an initial deployment (section A) demonstrating the core adjudication lifecycle with claimant-supplied notice text, and a second deployment (section B) after adding real authoritative-source verification, demonstrated against a genuine, currently-live CPSC recall fetched over `gl.nondet.web.render`.

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
- **No DoS-resistant / staked notice registration.** Any caller can still call `file_notice` for an allowlisted domain up to `MAX_NOTICES`, then attempt `verify_source_notice`; a flood of plausible-looking but ultimately-unverified notices against real URLs was not load-tested, though each one that fails verification cannot gate any product (see `can_release`, which skips unverified notices).
- A handful of transaction hashes from the section A run were not retained in the captured terminal output (truncated via `tail`, and the GenLayer explorer at `genlayer-explorer.vercel.app` returned `503 DEPLOYMENT_PAUSED` when checked afterward to recover them). Every transaction without a recorded hash in section A is still verified by its on-chain state read, not by narrative claim alone. Section B hashes were captured directly via `grep` on live command output.
- `ReleaseGuard` (`contracts/recall_gate.py`) was linted (`genvm-lint check` passes) but not deployed or exercised live in this session.
- Only `cpsc.gov` was exercised as an authorized source domain; no other regulator domain was tested.
