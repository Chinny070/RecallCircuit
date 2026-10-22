# RecallCircuit state machine and invariants

This reflects the actual `RecallCircuit` contract in `contracts/recall_circuit.py` as deployed. It supersedes any earlier draft describing `Asset`/`Case`/`propose_notice` — those methods do not exist in the shipped contract.

## Notice lifecycle

`file_notice` first requires `gl.message.sender_address` to be the contract `admin` (the deployer) or an address the admin explicitly authorized via `authorize_filer` (revocable with `revoke_filer`; checked with `is_authorized_filer`). This is a simple admin-gated allowlist, not a staking or governance mechanism, and bounds who may attempt to file a notice at all (`CLAUDE_FINISH_PROMPT.md` item 3) independent of the domain checks below.

Once the sender is authorized, `file_notice` accepts a claimant-submitted notice (`authority`, `source_url` must start with an allowlisted regulator prefix in `AUTHORIZED_SOURCE_PREFIXES` — currently `https://www.cpsc.gov/` and `https://cpsc.gov/` — `source_id`, `notice_text`, `source_hash`), marks it `active`, and leaves it `verified = False`. A notice in this state **cannot** be used to open an assessment.

`verify_source_notice(notice_id)` is a second, separate write call (anyone may call it) that runs a real leader+validator consensus round: the leader fetches the live page at `source_url` via `gl.nondet.web.render`, hashes it (`source_digest`, sha256 hex), and asks an LLM whether the claimed `notice_text` is a faithful, non-misleading summary of that live page; each validator independently re-fetches, independently recomputes its own digest, and the transaction only finalizes `verified = True` if the leader's and every validator's `match` boolean **and** `digest` agree exactly (full expected shape `{'match','reason','digest'}`; no partial match, no permissive coercion). A failed fetch, an empty page, a malformed LLM response, a validator-detected content mismatch, or a digest disagreement all collapse to `verified = False`. **This is an independent re-fetch-and-compare check, not cryptographic proof of regulator authorship** — see Limitations.

**Verification is monotonic.** Once `verified` is `True`, `verify_source_notice` refuses outright (`"notice already verified"`) rather than running the check again. This matters because `can_release` only counts a notice while it is both `active` and `verified`: without this guard, a later call that happened to fail (a transient fetch error, an edited live page) would silently flip `verified` back to `False` and stop that notice from gating an already-affected product — a real fail-open bug this closes (see `docs/LIVE_PROOFS.md` section E1).

`supersede_notice(old_id, text, source_hash)` creates a new notice (`version = old.version + 1`, `previous_id = old_id`, preserving `authority`/`source_url`/`source_id`, starting `verified = False`) but **does not deactivate the predecessor**. The predecessor only retires — as a side effect of `verify_source_notice` succeeding on the successor — once the successor is independently verified ("safe replacement activation"). If the successor is never verified, or fails verification (e.g. its text doesn't match the live page), the predecessor keeps gating indefinitely; this is the safe failure mode, not a bug (see `docs/LIVE_PROOFS.md` section E2 for both outcomes demonstrated live against a real recall). Any assessment opened against a currently-inactive notice reverts (`open_assessment` → `superseded notice`); assessments already resolved against a retired notice remain readable but do not satisfy `can_release`.

## Assessment lifecycle

```
open_assessment(product_id, notice_id):
    rejects a duplicate for the same (product_id, notice_id, product.revision)
    status=UNCERTAIN, pending=True, evidence_hash=notice.source_digest   [HOLD]
resolve_assessment(assessment_id):
    notice inactive or product.revision changed since open -> UNCERTAIN  [HOLD]
    else -> independent leader+validator classification:
        AFFECTED(1)      [HOLD]
        NOT_AFFECTED(2)  [scoped clearance, this notice only]
        UNCERTAIN(3)     [HOLD — malformed/unavailable/ambiguous always falls here]
appeal_assessment(assessment_id, evidence, evidence_hash):
    evidence must literally reference the product's serial number, else reverts
    appealed=True, opens Appeal(OPEN)   [HOLD regardless of outcome until resolved]
resolve_appeal(appeal_id):
    requires a current, matching, ACTIVE, non-consumed SCOPE_EXCLUSION Attestation
    (see Independent evidence attestation below) -- missing/invalid => UNCERTAIN
    else re-runs independent classification using the ATTESTATION's evidence_description
    (never the appellant's own `evidence`) -> AFFECTED | NOT_AFFECTED | UNCERTAIN
    attestation.consumed=True only if the outcome is NOT_AFFECTED; generation += 1
request_remedy(assessment_id, evidence, evidence_hash):
    evidence must literally reference the product's serial number, else reverts
    only from AFFECTED; opens Remedy(OPEN)  [HOLD]
resolve_remedy(remedy_id):
    requires a current, matching, ACTIVE, non-consumed REMEDY_COMPLETED Attestation
    -- missing/invalid => UNCERTAIN, quarantine preserved
    else classification (using the ATTESTATION's evidence_description) outcome == NOT_AFFECTED
    AND notice still active AND assessment not pending
        -> REMEDIATED(5)  [scoped clearance]; attestation.consumed=True
    else -> UNCERTAIN(3)  [HOLD; quarantine preserved]
```

`SUPERSEDED(4)` is a reserved enum value; the contract does not currently assign it to an assessment — a superseded notice instead blocks new assessments outright and leaves old ones as historical record.

**Assessment uniqueness.** `open_assessment` scans existing assessments and rejects a duplicate for the same `(product_id, notice_id, product.revision)` triple (`"assessment already exists for this product/notice/revision"`), bounded by `MAX_ASSESSMENTS`. The only sanctioned way to re-challenge a resolved assessment is `appeal_assessment` — a bounded, single-shot (`a.appealed` blocks a second appeal), auditable lifecycle — not by opening a fresh assessment and hoping for a different leader/validator outcome. A structural change (a new `link_component` call bumping `product.revision`) is what legitimately opens the door to a new assessment under the new revision.

**Evidence binding.** `Assessment.evidence_hash` is always the notice's independently-verified `source_digest`, never the claimant's unverified `file_notice` `source_hash` — the latter is never checked by anything and must not be cited as evidence (see `docs/LIVE_PROOFS.md` section E4). `appeal_assessment`/`request_remedy` additionally require the evidence text to name the product's exact serial number and a non-empty `evidence_hash` commitment, both stored and readable via `get_appeal`/`get_remedy` — these are the *claimant's own* submission, kept only as an audit trail and **never read by the clearance evaluator** (see below).

## Independent evidence attestation (mandatory for NOT_AFFECTED / REMEDIATED)

A claimant's own appeal/remedy text, however convincing and however it names the serial number, is **never sufficient** to clear a hold — this closed a real bypass where the original free-text evaluator could be convinced by prose alone. Clearance now requires a separate, independent **Attestation**:

- `authorize_issuer(who)` / `revoke_issuer(who)` (admin-only; checked with `is_authorized_issuer`): an admin-managed registry of addresses the admin designates as independent evidence issuers — meant to represent a real manufacturer, authorized repair provider, or other independent authority. **Unlike `authorize_filer`, the admin is never auto-granted issuer status** — issuer trust is never implicit.
- `submit_attestation(assessment_id, evidence_type, evidence_commitment, evidence_description, source_url)`: the sender must be an authorized issuer and must **not** be the product's own owner (checked against live state, not a role flag the owner could forge). `evidence_type` is `EVIDENCE_SCOPE_EXCLUSION` (1) or `EVIDENCE_REMEDY_COMPLETED` (2). `evidence_commitment` must match the canonical format `sha256:<64 lowercase hex chars>` (`canonical_commitment`) — a made-up string is rejected before anything else runs. Every identity field — `product_id`, `serial`, `notice_id`, `notice_digest`, `product_revision`, `assessment_generation` — is captured by the contract itself from live chain state at submission time, **never supplied by the issuer**, so an attestation cannot be aimed at the wrong unit, notice, or case. If `source_url` is given (optional), it is independently fetched and compared to `evidence_description` via the same leader+validator nondet pattern used for notice verification (`_verify_evidence_source`), binding a real `source_digest`; if omitted, the attestation rests on the issuer's authenticated identity alone. A duplicate active, non-consumed attestation of the same type for the same case/generation is rejected outright (`"an active attestation of this type already exists for this case"`).
- `revoke_attestation(attestation_id)` (admin or the original issuer): sets `status = ATT_REVOKED`.
- `_current_valid_attestation` (internal, used by `resolve_appeal`/`resolve_remedy`): a matching attestation must have the correct `assessment_id` and `evidence_type`, `status == ATT_ACTIVE`, `consumed == False`, `assessment_generation` equal to the assessment's **current** generation, `product_revision` equal to the assessment's revision, `notice_digest` equal to the notice's **current** `source_digest`, and (if a source was checked) `source_match == True`. Any mismatch on any of these — including simply being stale because the assessment moved to a new generation since the attestation was submitted — is treated identically to "no attestation at all": the hold is preserved.
- Only once a matching attestation exists does `resolve_appeal`/`resolve_remedy` even call the leader+validator classifier, and it is fed the **issuer's** `evidence_description`, never the claimant's own `evidence` field. A clearing outcome additionally marks the attestation `consumed = True`, so it cannot be reused for a different resolution attempt.

This mechanism is demonstrated live on StudioNet (`docs/LIVE_PROOFS.md` section F) using a GenLayer test wallet as the "issuer" — **that demonstrates the authorization/binding mechanism works, not that any given address is really a manufacturer or repair provider**, which this contract cannot prove on its own. Adversarial cases (wrong-case reuse, tampered public source, duplicate/replay, revoked/stale attestation, leader tampering) are Direct Mode evidence (`tests/direct/test_recallcircuit_direct.py`).

## Core invariants (as implemented)

1. **Fail-closed by default.** `can_release(product_id)` returns `False` unless, for every currently-active notice and for the product and every linked component (recursively, bounded by `MAX_PRODUCTS`), the most recent assessment against that notice is resolved (`not pending`), not under an open appeal, has status `NOT_AFFECTED` or `REMEDIATED`, and matches the product's current `revision`.
2. **No scope laundering.** The validator independently re-runs the same classification prompt and the transaction only finalizes if its `outcome` integer matches the leader's; prose differences in `reason` are ignored, so a leader cannot smuggle a different verdict through wording.
3. **Malformed/ambiguous never clears.** `verdict_shape` rejects anything that isn't exactly `{"outcome": int in {1,2,3}, "reason": str 1..300 chars}`; any JSON parse failure, wrong type, or extra/missing key collapses to `UNCERTAIN`.
4. **Graph cycle and self-link rejection.** `link_component` runs a bounded DFS (capped at `MAX_PRODUCTS`) over existing links before accepting a new edge; self-reference and cycles revert.
5. **Owner-gated writes.** `link_component`, `appeal_assessment`, and `request_remedy` all require `gl.message.sender_address == product.owner`.
6. **Revision invalidation.** `link_component` increments the product's `revision`; `can_release` compares `assessment.product_revision` against the product's current `revision`, so a structural change invalidates prior clearances until reassessed.
7. **Remedy and appeal require an independent, non-self, case-bound attestation plus reclassification.** `resolve_remedy`/`resolve_appeal` never accept the applicant's own evidence text at face value — they require a matching Attestation from an authorized, non-owner issuer (see above) before even running the leader+validator classification, which is then fed the issuer's attested facts, not the claimant's.

## Bounds

`MAX_TEXT=1800` chars per text field, `MAX_PRODUCTS=500`, `MAX_LINKS=12` components per product, `MAX_NOTICES=100`, `MAX_ASSESSMENTS=2000`, `MAX_APPEALS=500`, `MAX_REMEDIES=500`, `MAX_ATTESTATIONS=1000`. These are deliberate bounded-execution limits for GenVM gas/storage-scan cost, not production throughput targets. `can_release` is O(components × notices × assessments) per call and is the dominant cost; see Limitations.

## Important limitations (unresolved, must not be claimed as solved)

- **Source verification is domain-allowlisted re-fetch-and-compare, not a cryptographic authenticity proof.** `verify_source_notice` fetches the live page and reaches independent leader+validator consensus that the claimed text matches it, binding a `sha256` digest of the fetched content — but trust in the domain itself still rests on the hardcoded `AUTHORIZED_SOURCE_PREFIXES` allowlist, not an on-chain governance or signature-verification mechanism. See `docs/LIVE_PROOFS.md` section B for a live demonstration against a real, currently-published CPSC recall, including a fabricated-claim rejection.
- **The authorized-filer allowlist is single-admin, not governed.** `authorize_filer`/`revoke_filer` are gated on one `admin` address set at deployment; there is no multisig, stake, or on-chain governance process, and a compromised or careless admin could authorize an unreliable filer. An authorized filer can still file implausible notices against allowlisted domains up to `MAX_NOTICES` times, but each one that fails `verify_source_notice` cannot gate any product, which limits (but does not eliminate) the griefing surface.
- **Issuer authorization is a privilege grant, not identity proof.** `authorize_issuer` lets the admin designate an address as a trusted evidence issuer, but the contract has no way to verify that address really belongs to a manufacturer or repair provider — this is a known, explicit limitation, not an oversight (see `docs/LIVE_PROOFS.md` section F's honesty note, where a GenLayer test wallet stands in for a real attestor).
- **`evidence_commitment`/`source_url` are auditable commitments, not full cryptographic proof chains.** The contract enforces a canonical hash format and, when a `source_url` is given, independently fetches and compares it — but it does not verify the committed artifact's chain of custody beyond that single fetch.
- **The issuer registry is single-admin, like the filer registry.** `authorize_issuer`/`revoke_issuer` are gated on the same one `admin` address; there is no multisig, stake, or on-chain governance process for either registry.
- **`can_release` cost is unbounded by notice count in the worst case.** It scans every notice and every assessment per call; this must be profiled before it is relied on for large registries.
- **Direct Mode vs. live StudioNet.** `tests/direct/` exercises the real GenVM SDK runtime (storage types, `gl.vm.run_nondet_unsafe` leader/validator wiring) with only the LLM boundary mocked — this is real SDK execution, not a hand-rolled simulator, but it is still not full multi-validator StudioNet consensus. See `docs/LIVE_PROOFS.md` for the actual StudioNet deployment and lifecycle evidence.
