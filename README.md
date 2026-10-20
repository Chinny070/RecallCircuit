# RecallCircuit

**Safety-first, notice-scoped product recall adjudication and component quarantine on GenLayer.**

Status: **deployed and live on StudioNet (chain 61999)**, with real multi-validator consensus demonstrated across affected/excluded/remedy/appeal/supersession flows — see [`docs/LIVE_PROOFS.md`](docs/LIVE_PROOFS.md) for the contract address, transaction evidence and reads. Not audited. Notice URL and text are **claimant-supplied**, not independently fetched or authenticated from the regulator by the contract (see Constraints below) — this is not a public-product-safety certification.

## Why GenLayer?

Recall notices describe manufacturer, batch, model, manufacturing date, serial ranges, exclusions and remedy rules in natural language. The contract asks independently executing validators whether an identified item falls in scope. It does *not* ask an LLM to perform inventory graph traversal; graph propagation is deterministic.

## Core workflow

1. `register_product` creates immutable identity data, controlled by creator; `link_component` adds a bounded, cycle-free dependency edge.
2. `file_notice` records an untrusted source statement and its alleged origin. `supersede_notice` retires an earlier version without rewriting history.
3. `open_assessment` places the product in unresolved hold status, even before semantic resolution.
4. `resolve_assessment` invokes leader and validator LLM judgment on the same original evidence; comparison is over a structured scope outcome. Malformed or unavailable consensus results remain unresolved.
5. Product owner may `appeal_assessment`; anyone may call `resolve_appeal`. Evidence is treated as untrusted data.
6. Affected owners can `request_remedy`; anyone can `resolve_remedy`. A validated remedy records `REMEDIATED`, distinct from never being affected.
7. `can_release(product_id)` traverses parts and requires a current, resolved NOT_AFFECTED or REMEDIATED assessment for **every active registered notice** for **every component**. An absent or uncertain result is never clearance.

### Result codes

`0 PENDING`, `1 AFFECTED`, `2 NOT_AFFECTED`, `3 UNCERTAIN`, `4 SUPERSEDED`, `5 REMEDIATED`.

## Constraints and deliberate safety limitations

- All notices are initially **unverified uploads**. The contract's LLM classification does **not** authenticate HTTPS provenance, document content, regulator authorization, or update freshness. **Do not deploy as a public clearance engine until an official-source authenticated retrieval/provenance design is added and tested.**
- A registered notice is globally considered when evaluating the gate. This is conservatively fail-closed but can cause griefing/denial-of-service because notice submissions are permissionless. Production must constrain notice publication with a robust governance/source verification mechanism.
- `can_release` is bounded but currently does linear scans through registered products, notices, and assessments. Profile GenVM transaction limits on StudioNet; replace with indexed per-product/notice pointers if needed.
- Current statuses are *notice-specific*, not claims of general product safety; consumers must explicitly enforce the gate.
- No wallet funds, escrow, transfers, automatic physical seizure, or certification promises.
- Semantic verdict agreement may be wrong, including correlated validator mistakes. The remedy decision must prove the **specific registered unit** was corrected; claimant assertions are not enough.
- Pending appeals hold an item. Changed product topology invalidates parent assessment via revision. Superseded notices are not counted as current, but new version requires new assessment.
- No frontend is required for a standalone Intelligent Contract submission; provide visualization separately only after real call semantics are verified.

## Testing

```bash
pip install -r requirements-test.txt -r requirements-dev.txt
genvm-lint check contracts/recall_circuit.py
python -m pytest tests -q
```

`tests/direct/` runs the real GenVM SDK runtime in Direct Mode (actual `@allow_storage` storage types, `gl.vm.run_nondet_unsafe` leader/validator wiring) with only the LLM boundary mocked via `direct_vm.mock_llm`. `tests/test_contract_static.py` and `tests/test_quality.py` are static/AST-level honesty checks. None of this is full multi-validator StudioNet consensus — for that, see [`docs/LIVE_PROOFS.md`](docs/LIVE_PROOFS.md), which documents the actual deployed contract address and on-chain lifecycle runs on StudioNet.

Target chain: **GenLayer StudioNet 61999**, RPC `https://studio.genlayer.com/api` (gasless). No other chain target is intended.
