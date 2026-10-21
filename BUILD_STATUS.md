# Build status — 21 October 2026

## Deployed and live

- `RecallCircuit` deployed twice to **StudioNet (chain 61999)** this session. Current contract (with `verify_source_notice`) is at `0xE8F4522CA39001F2e073788623f0297f6d883963`, deploy tx `0xa9795ea75c725d3b3824cc725b3ee2339303837f6fa897d893380ba1ea6fa38d`, **FINALIZED**, 6/6 execution `SUCCESS`. An earlier deployment without source verification is at `0x8485533fAB15D14F5231B97C51e7EDcE3fF12377` (tx `0x29a431c94f2b67ffc536d700d289d6f26370417c29aa3cc3801a413637743ca0`, 5/5 `AGREE`) and remains live as evidence of the core lifecycle.
- **Real authoritative source verification against a genuine, currently-published CPSC recall.** `verify_source_notice` fetched `https://www.cpsc.gov/Recalls/2026/The-Blue-Cactus-Company-Reclining-Chair-Battery-Packs-Recalled-Due-to-Fire-and-Burn-Hazards-Sold-on-Amazon` live over `gl.nondet.web.render` inside GenVM, hashed it, and reached leader+validator consensus (with a genuine DISAGREE vote) that the claimed text matched — binding a real sha256 digest on-chain. A fabricated claim filed against the same real URL was independently fetched, correctly judged not to match, and left `verified=false` — permanently blocked from gating any product. Full detail in [`docs/LIVE_PROOFS.md`](docs/LIVE_PROOFS.md) section B.
- Real on-chain lifecycle executed and read back on both deployments: product registration, notice filing, independent leader+validator AFFECTED/NOT_AFFECTED/UNCERTAIN classification, a successful remedy, a rejected forged remedy, an appeal reversing a verdict on new evidence, component propagation through an assembled product, and notice supersession correctly invalidating the old version.
- StudioNet is gasless; no GEN was spent in this session.

## Fixed in this handoff

- `gltest.config.yaml` previously used an invalid schema (`network:` singular, missing `paths`/`networks.default`) and made `pytest`/`gltest` fail to even collect. Corrected to the real `gltest_cli` config schema.
- The entire `tests/` suite (`conftest.py`, `test_protocol.py`, the Direct Mode test) was written against an **earlier, abandoned contract API** (`register_asset`/`Asset`/`Case`/`propose_notice`/`open_case`/`is_release_allowed`, string-keyed LLM responses) that no longer matches `contracts/recall_circuit.py` (`register_product`/`Product`/`Notice`/`Assessment`/`can_release`, integer-coded structured verdicts). Every one of those 31 "passed" tests from the prior handoff was executing against mock classes that no longer corresponded to the real contract's methods — they were not meaningful evidence. The stale simulator (`tests/conftest.py`, `tests/test_protocol.py`) has been removed; `tests/direct/test_recallcircuit_direct.py` and `tests/test_quality.py` have been rewritten against the real contract API and now run through `genlayer-test`'s actual Direct Mode GenVM-SDK runtime (not a hand-rolled simulator). `tests/test_contract_static.py` was already aligned and is unchanged.
- `docs/STATE_MACHINE.md` was rewritten; it previously described the same abandoned API.
- Both contracts (`recall_circuit.py`, `recall_gate.py`) pass `genvm-lint check` (AST safety + SDK validation) with no errors, only an informational "newer runner available" notice.

## Verified locally this session

- `python -m pytest tests -q` → 22 passed (9 real Direct-Mode GenVM-SDK tests, 6 static/AST honesty tests, 2 quality tests, plus the static-contract parametrized cases).
- `genvm-lint check` on both contracts.

## Not completed / must not be claimed

- **Source verification is re-fetch-and-compare consensus, not cryptographic proof of government authorship.** `verify_source_notice` independently fetches the claimed URL and reaches leader+validator agreement that the claim matches it, binding a sha256 digest — demonstrated live against a real CPSC recall (see `docs/LIVE_PROOFS.md` section B). Trust in the domain itself still rests on a hardcoded allowlist (`AUTHORIZED_SOURCE_PREFIXES`), not an on-chain governance or signature mechanism, and GenVM's own HTTP fetch is trusted for TLS/domain integrity rather than independently re-verified by the contract.
- **No DoS-resistant / staked source registration** for notices (handoff item 3) — any address can still call `file_notice` against an allowlisted domain and attempt `verify_source_notice`; a notice that fails verification cannot gate a product, which limits but does not eliminate the griefing surface.
- A few early transaction hashes from the first deployment's lifecycle run were not retained in captured CLI output (truncated before the hash line) and the public GenLayer explorer was returning `503 DEPLOYMENT_PAUSED` when I tried to recover them afterward; every such step is still backed by an on-chain state read, documented in `docs/LIVE_PROOFS.md`, rather than an unverifiable claim. All second-deployment hashes were captured directly.
- `ReleaseGuard` (`contracts/recall_gate.py`) lints cleanly but was not deployed or exercised live this session.
- Stress tests, replay/race tests, and a dedicated CI run against the updated test suite were not performed this session.
- Real auditor identity, production manufacturer authenticity, and full legal regulatory compliance remain out of scope, as before.

See [`CLAUDE_FINISH_PROMPT.md`](CLAUDE_FINISH_PROMPT.md) for the full original checklist and [`docs/LIVE_PROOFS.md`](docs/LIVE_PROOFS.md) for exact on-chain evidence.
