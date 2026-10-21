# RecallCircuit

**Safety-first, notice-scoped product recall adjudication and component quarantine on GenLayer.**

Status: **deployed and live on StudioNet (chain 61999)**, with real multi-validator consensus demonstrated across affected/excluded/remedy/appeal/supersession flows, and real **authoritative source verification** against a genuine, currently-published CPSC recall fetched live via `gl.nondet.web.render` — including a fabricated-claim rejection. See [`docs/LIVE_PROOFS.md`](docs/LIVE_PROOFS.md) for contract addresses, transaction evidence and reads. Not audited. Source verification is a domain-allowlisted re-fetch-and-compare consensus check, not a cryptographic proof of government authorship (see Constraints below) — this is not a public-product-safety certification.

## Why GenLayer?

Recall notices describe manufacturer, batch, model, manufacturing date, serial ranges, exclusions and remedy rules in natural language. The contract asks independently executing validators whether an identified item falls in scope. It does *not* ask an LLM to perform inventory graph traversal; graph propagation is deterministic.

## Core workflow

1. `register_product` creates immutable identity data, controlled by creator; `link_component` adds a bounded, cycle-free dependency edge.
2. `file_notice` — restricted to the admin or an address the admin explicitly `authorize_filer`'d — records a claimant source statement against an allowlisted regulator domain. `verify_source_notice` independently re-fetches that URL and reaches leader+validator consensus on whether the claim faithfully matches the live page, binding a sha256 digest; only then is the notice usable. `supersede_notice` retires an earlier version without rewriting history and requires its own re-verification.
3. `open_assessment` (only against a verified, active notice) places the product in unresolved hold status, even before semantic resolution.
4. `resolve_assessment` invokes leader and validator LLM judgment on the same original evidence; comparison is over a structured scope outcome. Malformed or unavailable consensus results remain unresolved.
5. Product owner may `appeal_assessment`; anyone may call `resolve_appeal`. Evidence is treated as untrusted data.
6. Affected owners can `request_remedy`; anyone can `resolve_remedy`. A validated remedy records `REMEDIATED`, distinct from never being affected.
7. `can_release(product_id)` traverses parts and requires a current, resolved NOT_AFFECTED or REMEDIATED assessment for **every active registered notice** for **every component**. An absent or uncertain result is never clearance.

### Result codes

`0 PENDING`, `1 AFFECTED`, `2 NOT_AFFECTED`, `3 UNCERTAIN`, `4 SUPERSEDED`, `5 REMEDIATED`.

## Constraints and deliberate safety limitations

- All notices start **unverified**; `verify_source_notice` independently re-fetches the claimed URL and reaches leader+validator consensus that the claim matches it, but this is domain-allowlisting plus re-fetch-and-compare, not a cryptographic proof of regulator authorship or a signed CPSC artifact. **Do not market this as a government-certified feed** — see `docs/LIVE_PROOFS.md` section B for what was actually demonstrated against a real CPSC recall.
- Only a *verified* notice is considered when evaluating the gate; an unverified or verification-failed notice cannot block a product. `file_notice` itself is also admin-gated (`authorize_filer`/`revoke_filer`) — it is not permissionless — but that admin is a single address, not a stake-weighted or governed process.
- `can_release` is bounded but currently does linear scans through registered products, notices, and assessments. Profile GenVM transaction limits on StudioNet; replace with indexed per-product/notice pointers if needed.
- Current statuses are *notice-specific*, not claims of general product safety; consumers must explicitly enforce the gate.
- No wallet funds, escrow, transfers, automatic physical seizure, or certification promises.
- Semantic verdict agreement may be wrong, including correlated validator mistakes. The remedy decision must prove the **specific registered unit** was corrected; claimant assertions are not enough.
- Pending appeals hold an item. Changed product topology invalidates parent assessment via revision. Superseded notices are not counted as current, but new version requires new assessment.
- No frontend is required for a standalone Intelligent Contract submission; provide visualization separately only after real call semantics are verified.

## Testing

```bash
pip install -r requirements-dev.txt
genvm-lint check contracts/recall_circuit.py
python -m pytest tests -q
```

`tests/direct/` runs the real GenVM SDK runtime in Direct Mode (actual `@allow_storage` storage types, `gl.vm.run_nondet_unsafe` leader/validator wiring) with only the LLM boundary mocked via `direct_vm.mock_llm`. `tests/test_contract_static.py` and `tests/test_quality.py` are static/AST-level honesty checks. None of this is full multi-validator StudioNet consensus — for that, see [`docs/LIVE_PROOFS.md`](docs/LIVE_PROOFS.md), which documents the actual deployed contract address and on-chain lifecycle runs on StudioNet.

Target chain: **GenLayer StudioNet 61999**, RPC `https://studio.genlayer.com/api` (gasless). No other chain target is intended.
