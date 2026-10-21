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
resolve_appeal(appeal_id):  re-runs independent classification with appeal evidence
    -> AFFECTED | NOT_AFFECTED | UNCERTAIN; generation += 1
request_remedy(assessment_id, evidence, evidence_hash):
    evidence must literally reference the product's serial number, else reverts
    only from AFFECTED; opens Remedy(OPEN)  [HOLD]
resolve_remedy(remedy_id):
    classification outcome == NOT_AFFECTED AND notice still active AND assessment not pending
        -> REMEDIATED(5)  [scoped clearance]
    else -> UNCERTAIN(3)  [HOLD; quarantine preserved]
```

`SUPERSEDED(4)` is a reserved enum value; the contract does not currently assign it to an assessment — a superseded notice instead blocks new assessments outright and leaves old ones as historical record.

**Assessment uniqueness.** `open_assessment` scans existing assessments and rejects a duplicate for the same `(product_id, notice_id, product.revision)` triple (`"assessment already exists for this product/notice/revision"`), bounded by `MAX_ASSESSMENTS`. The only sanctioned way to re-challenge a resolved assessment is `appeal_assessment` — a bounded, single-shot (`a.appealed` blocks a second appeal), auditable lifecycle — not by opening a fresh assessment and hoping for a different leader/validator outcome. A structural change (a new `link_component` call bumping `product.revision`) is what legitimately opens the door to a new assessment under the new revision.

**Evidence binding.** `Assessment.evidence_hash` is always the notice's independently-verified `source_digest`, never the claimant's unverified `file_notice` `source_hash` — the latter is never checked by anything and must not be cited as evidence (see `docs/LIVE_PROOFS.md` section E4). `appeal_assessment`/`request_remedy` additionally require the evidence text to name the product's exact serial number and a non-empty `evidence_hash` commitment, both stored and readable via `get_appeal`/`get_remedy` — an auditable commitment, not an independently fetched or cryptographically verified artifact (see Limitations).

## Core invariants (as implemented)

1. **Fail-closed by default.** `can_release(product_id)` returns `False` unless, for every currently-active notice and for the product and every linked component (recursively, bounded by `MAX_PRODUCTS`), the most recent assessment against that notice is resolved (`not pending`), not under an open appeal, has status `NOT_AFFECTED` or `REMEDIATED`, and matches the product's current `revision`.
2. **No scope laundering.** The validator independently re-runs the same classification prompt and the transaction only finalizes if its `outcome` integer matches the leader's; prose differences in `reason` are ignored, so a leader cannot smuggle a different verdict through wording.
3. **Malformed/ambiguous never clears.** `verdict_shape` rejects anything that isn't exactly `{"outcome": int in {1,2,3}, "reason": str 1..300 chars}`; any JSON parse failure, wrong type, or extra/missing key collapses to `UNCERTAIN`.
4. **Graph cycle and self-link rejection.** `link_component` runs a bounded DFS (capped at `MAX_PRODUCTS`) over existing links before accepting a new edge; self-reference and cycles revert.
5. **Owner-gated writes.** `link_component`, `appeal_assessment`, and `request_remedy` all require `gl.message.sender_address == product.owner`.
6. **Revision invalidation.** `link_component` increments the product's `revision`; `can_release` compares `assessment.product_revision` against the product's current `revision`, so a structural change invalidates prior clearances until reassessed.
7. **Remedy requires independent reclassification.** `resolve_remedy` does not accept the applicant's evidence text at face value — it re-runs the same leader+validator classification with the remedy evidence as additional context, and only a consensus `NOT_AFFECTED` outcome clears the hold.

## Bounds

`MAX_TEXT=1800` chars per text field, `MAX_PRODUCTS=500`, `MAX_LINKS=12` components per product, `MAX_NOTICES=100`, `MAX_ASSESSMENTS=2000`, `MAX_APPEALS=500`, `MAX_REMEDIES=500`. These are deliberate bounded-execution limits for GenVM gas/storage-scan cost, not production throughput targets. `can_release` is O(components × notices × assessments) per call and is the dominant cost; see Limitations.

## Important limitations (unresolved, must not be claimed as solved)

- **Source verification is domain-allowlisted re-fetch-and-compare, not a cryptographic authenticity proof.** `verify_source_notice` fetches the live page and reaches independent leader+validator consensus that the claimed text matches it, binding a `sha256` digest of the fetched content — but trust in the domain itself still rests on the hardcoded `AUTHORIZED_SOURCE_PREFIXES` allowlist, not an on-chain governance or signature-verification mechanism. See `docs/LIVE_PROOFS.md` section B for a live demonstration against a real, currently-published CPSC recall, including a fabricated-claim rejection.
- **The authorized-filer allowlist is single-admin, not governed.** `authorize_filer`/`revoke_filer` are gated on one `admin` address set at deployment; there is no multisig, stake, or on-chain governance process, and a compromised or careless admin could authorize an unreliable filer. An authorized filer can still file implausible notices against allowlisted domains up to `MAX_NOTICES` times, but each one that fails `verify_source_notice` cannot gate any product, which limits (but does not eliminate) the griefing surface.
- **No cryptographic remedy proof.** `resolve_remedy` relies on LLM classification of free-text evidence requiring the unit's serial number plus a hash commitment; there is no signed shop/vendor attestation, and the contract never fetches or checks what `evidence_hash` actually points to.
- **`can_release` cost is unbounded by notice count in the worst case.** It scans every notice and every assessment per call; this must be profiled before it is relied on for large registries.
- **Direct Mode vs. live StudioNet.** `tests/direct/` exercises the real GenVM SDK runtime (storage types, `gl.vm.run_nondet_unsafe` leader/validator wiring) with only the LLM boundary mocked — this is real SDK execution, not a hand-rolled simulator, but it is still not full multi-validator StudioNet consensus. See `docs/LIVE_PROOFS.md` for the actual StudioNet deployment and lifecycle evidence.
