# RecallCircuit state machine and invariants

## Notice lifecycle

`PROPOSED(0) -> VERIFIED(1)` only after independent re-execution of official CPSC page and agreement on `official_id/title/recall_date/valid`. Invalid or unavailable sources keep the transaction unfinalized/failed, **not verified**. `REJECTED(2)` reserved as an enum for future governance; current implementation does not transition to it. A verified revision must preserve the official recall ID, and can supersede one earlier notice. A proposed revision does not affect current decisions; a verified revision does.

## Case lifecycle

```
open_case:           PENDING(0)       [HOLD]
resolve_case:        AFFECTED(1)      [HOLD]
                    CLEAR(2)         [scoped clearance]
                    UNCERTAIN(3)     [HOLD]
appeal_case:         APPEAL(4)        [HOLD, bounded to two]
resolve_case again:  AFFECTED|CLEAR|UNCERTAIN
propose_remedy:      REMEDY(5)        [HOLD, only from AFFECTED]
resolve_remedy:      REMEDIATED(6)    [scoped clearance, audited]
                    AFFECTED(1)      [HOLD if remedy insufficient]
revision/stale:     old case effectively HOLD until new current notice case clears
```

Local `C_STALE=7` occurs if the asset revision or notice lineage moves before resolution. All status values except `C_CLEAR` and `C_REMEDIATED` are blocking. `is_release_allowed` additionally checks ancestor component graph recursively, manual frozen flag, any missing registration coverage, outdated notice lineages and asset revisions.

## Core invariants

1. **No unadjudicated release.** A standalone product without any verified-notice case is not releasable.
2. **No scope laundering.** Affected and uncertain findings are never treated as safe; validator compares independently derived verdicts, not leader text formatting.
3. **No untrusted source privilege.** Only official CPSC URL namespaces can create regulator notices. External remedy proof is lower trust, additionally requiring a separate consenting auditor.
4. **No graph laundering.** Components cannot be linked after either asset is involved in a case. Graph cycles and different ownership are prohibited.
5. **No appeal bypass.** Opening an appeal instantly holds a previously cleared case. Unresolved validator disagreement leaves its original hold state.
6. **No stale revision bypass.** When a notice revision is verified, earlier scoped decisions no longer authorize shipment until a successor case is cleared.
7. **No owner self-remedy.** Asset owner and auditor must be different, and the auditor must accept appointment and attest the exact evidence URL commitment.
8. **Final-state consumer.** The frontend reads `LATEST_FINAL` and does not treat submitting a transaction or merely obtaining a hash as proof of execution success.

## Bounds

Up to 256 assets, 64 notices, 512 cases, 8 child references per asset, 4 recursion layers, and 12 cases per asset. These are deliberate bounded prototype limits, not throughput benchmarks. Notice classification prompts use bounded page excerpts. Materially larger recalls and graph workloads require profiling, pagination and perhaps separate indexing contracts.

## Important limitations

- `is_release_allowed` is a gate over **registered assessed cases**. It does not automatically fetch/scan every official recall for every registered inventory item. This must be made explicit in UI and scoring claims.
- Component edges require the same owner, limiting multi-supplier graphs. A production design needs signed cross-entity provenance attestations.
- Remedy evidence URLs can be forged; even with validator agreement, LLMs and auditors may both err. There is no cryptographic proof of physical repair.
- Parent-child depth guards are bounded; deeply nested graphs may become unreleasable (fail-closed) rather than incorrectly allowed.
- Direct Mode may expose GenVM syntax/storage constraints that the simulated SDK cannot catch. Keep contract code subject to real lint and consensus tests.
- `ReleaseGuard` must be explicitly verified against StudioNet intercontract call support, not assumed from SDK interfaces alone.
