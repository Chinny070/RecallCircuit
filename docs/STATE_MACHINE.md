# RecallCircuit state machine and invariants

This reflects the actual `RecallCircuit` contract in `contracts/recall_circuit.py` as deployed. It supersedes any earlier draft describing `Asset`/`Case`/`propose_notice` — those methods do not exist in the shipped contract.

## Notice lifecycle

`file_notice` accepts a claimant-submitted notice (`authority`, `source_url` must be `https://`, `source_id`, `notice_text`, `source_hash`) and marks it `active`. **The contract does not fetch or cryptographically verify the regulator's page itself** — there is no live web-fetch step in this build (see Limitations). A notice's authenticity is therefore established outside the contract (off-chain operational trust in who is allowed to call `file_notice`), and `get_notice`/`gate_explanation` must not be presented as proof of regulator authenticity.

`supersede_notice(old_id, text, source_hash)` deactivates `old_id` and creates a new notice with `version = old.version + 1`, `previous_id = old_id`, preserving `authority`/`source_url`/`source_id`. Any assessment opened against a deactivated notice cannot be created (`open_assessment` reverts with `superseded notice`); assessments already resolved against the old version remain readable but do not satisfy `can_release` for the new version.

## Assessment lifecycle

```
open_assessment(product_id, notice_id):   status=UNCERTAIN, pending=True   [HOLD]
resolve_assessment(assessment_id):
    notice inactive or product.revision changed since open -> UNCERTAIN  [HOLD]
    else -> independent leader+validator classification:
        AFFECTED(1)      [HOLD]
        NOT_AFFECTED(2)  [scoped clearance, this notice only]
        UNCERTAIN(3)     [HOLD — malformed/unavailable/ambiguous always falls here]
appeal_assessment(assessment_id, evidence):  appealed=True, opens Appeal(OPEN)   [HOLD regardless of outcome until resolved]
resolve_appeal(appeal_id):  re-runs independent classification with appeal evidence
    -> AFFECTED | NOT_AFFECTED | UNCERTAIN; generation += 1
request_remedy(assessment_id, evidence):  only from AFFECTED; opens Remedy(OPEN)  [HOLD]
resolve_remedy(remedy_id):
    classification outcome == NOT_AFFECTED AND notice still active AND assessment not pending
        -> REMEDIATED(5)  [scoped clearance]
    else -> UNCERTAIN(3)  [HOLD; quarantine preserved]
```

`SUPERSEDED(4)` is a reserved enum value; the contract does not currently assign it to an assessment — a superseded notice instead blocks new assessments outright and leaves old ones as historical record.

## Core invariants (as implemented)

1. **Fail-closed by default.** `can_release(product_id)` returns `False` unless, for every currently-active notice and for the product and every linked component (recursively, bounded by `MAX_PRODUCTS`), the most recent assessment against that notice is resolved (`not pending`), not under an open appeal, has status `NOT_AFFECTED` or `REMEDIATED`, and matches the product's current `revision`.
2. **No scope laundering.** The validator independently re-runs the same classification prompt and the transaction only finalizes if its `outcome` integer matches the leader's; prose differences in `reason` are ignored, so a leader cannot smuggle a different verdict through wording.
3. **Malformed/ambiguous never clears.** `verdict_shape` rejects anything that isn't exactly `{"outcome": int in {1,2,3}, "reason": str 1..300 chars}`; any JSON parse failure, wrong type, or extra/missing key collapses to `UNCERTAIN`.
4. **Graph cycle and self-link rejection.** `link_component` runs a bounded DFS (capped at `MAX_PRODUCTS`) over existing links before accepting a new edge; self-reference and cycles revert.
5. **Owner-gated writes.** `link_component`, `appeal_assessment`, and `request_remedy` all require `gl.message.sender_address == product.owner`.
6. **Revision invalidation.** `link_component` increments the product's `revision`; `can_release` compares `assessment.product_revision` against the product's current `revision`, so a structural change invalidates prior clearances until reassessed.
7. **Remedy requires independent reclassification.** `resolve_remedy` does not accept the applicant's evidence text at face value — it re-runs the same leader+validator classification with the remedy evidence as additional context, and only a consensus `NOT_AFFECTED` outcome clears the hold.

## Bounds

`MAX_TEXT=1800` chars per text field, `MAX_PRODUCTS=500`, `MAX_LINKS=12` components per product, `MAX_NOTICES=100`. These are deliberate bounded-execution limits for GenVM gas/storage-scan cost, not production throughput targets. `can_release` is O(components × notices × assessments) per call and is the dominant cost; see Limitations.

## Important limitations (unresolved, must not be claimed as solved)

- **No authoritative source verification.** `file_notice` trusts the caller's text, URL, and hash. There is no `gl.nondet.web` fetch of the regulator's page, no domain allowlist, and no cryptographic binding to a CPSC-signed artifact in this build. A notice is only as trustworthy as whoever is permitted to call `file_notice` off-chain — this must be stated plainly in any public description of the system, and the contract must not be marketed as a verified-authenticity recall registry until this is built.
- **No DoS-resistant source registration.** Any address can call `file_notice` up to `MAX_NOTICES` times; there is no stake, allowlist, or independent-acceptance step gating who can file a notice that blocks products.
- **No cryptographic remedy proof.** `resolve_remedy` relies on LLM classification of free-text evidence; there is no signed shop/vendor attestation or serial-binding cryptography.
- **`can_release` cost is unbounded by notice count in the worst case.** It scans every notice and every assessment per call; this must be profiled before it is relied on for large registries.
- **Direct Mode vs. live StudioNet.** `tests/direct/` exercises the real GenVM SDK runtime (storage types, `gl.vm.run_nondet_unsafe` leader/validator wiring) with only the LLM boundary mocked — this is real SDK execution, not a hand-rolled simulator, but it is still not full multi-validator StudioNet consensus. See `docs/LIVE_PROOFS.md` for the actual StudioNet deployment and lifecycle evidence.
