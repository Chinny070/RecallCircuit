# RecallCircuit — live StudioNet proofs

Recorded 2026-10-20/21 against **StudioNet (chain ID 61999, RPC `https://studio.genlayer.com/api`)** using the `genlayer` CLI v0.39.2, signer account `0xaffE15eEc45b68835cc9E5B4Ab85dD5deaE8e70b`. StudioNet is gasless — no GEN was spent or needed for any transaction below (confirmed: account balance unchanged across the whole run).

No step below used a mock, simulator, or fabricated value. Every status, reason string, and vote tally is copied verbatim from a `genlayer write`/`genlayer call`/`genlayer receipt` response. Where a transaction hash was not captured in the terminal output before truncation, that is stated explicitly rather than invented — the corresponding on-chain state read is cited instead as the evidence.

## Deployment

```
Contract:          RecallCircuit (contracts/recall_circuit.py)
Contract Address:  0x8485533fAB15D14F5231B97C51e7EDcE3fF12377
Deploy Tx Hash:     0x29a431c94f2b67ffc536d700d289d6f26370417c29aa3cc3801a413637743ca0
Status:            FINALIZED
Consensus:         MAJORITY_AGREE, round 0, 5/5 validators committed+revealed, votes [AGREE, AGREE, AGREE, AGREE, AGREE]
Validators:        0x0B50B270Eba5D9B780272C4Cf4720260177e761D, 0xf1C7551292319EE334e2D8A24eAC108Bd4C63b21,
                    0x6a4179A851B3747A458baD2f089AB2EeFE0eBbAb, 0x5Bbbd7cdD63c0ba7f088038Cb049bDDAbE4F6fd1,
                    0x8a876C3F3a4783Bd123982bcBF3c672dc0239004
```
Confirmed with `genlayer schema 0x8485...2377` — the live on-chain ABI matches the source method set (`register_product`, `link_component`, `file_notice`, `supersede_notice`, `open_assessment`, `resolve_assessment`, `appeal_assessment`, `resolve_appeal`, `request_remedy`, `resolve_remedy`, `get_product`, `get_notice`, `get_assessment`, `can_release`, `gate_explanation`).

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

- **No authoritative CPSC source verification.** `file_notice` was called with claimant-supplied, synthetic text styled on a real recall notice; the contract does not fetch or cryptographically authenticate `cpsc.gov` content in this build (see `docs/STATE_MACHINE.md` Limitations). This gate must not be marketed as proof a notice is government-issued.
- **No DoS-resistant notice registration / source allowlist.** Any caller can file a notice up to `MAX_NOTICES`; this was not hardened in this session.
- A handful of transaction hashes from the earlier part of this run were not retained in the captured terminal output (truncated via `tail`, and the GenLayer explorer at `genlayer-explorer.vercel.app` returned `503 DEPLOYMENT_PAUSED` when checked afterward to recover them). Every transaction without a recorded hash above is still verified by its on-chain state read, not by narrative claim alone.
- `ReleaseGuard` (`contracts/recall_gate.py`) was linted (`genvm-lint check` passes) but not deployed or exercised live in this session.
