# Build status — 21 October 2026

## Deployed and live

- `RecallCircuit` deployed to **StudioNet (chain 61999)** at `0x8485533fAB15D14F5231B97C51e7EDcE3fF12377`. Deploy tx `0x29a431c94f2b67ffc536d700d289d6f26370417c29aa3cc3801a413637743ca0`, **FINALIZED**, 5/5 validator `AGREE`.
- Real on-chain lifecycle executed and read back: product registration, notice filing, independent leader+validator AFFECTED/NOT_AFFECTED/UNCERTAIN classification, a successful remedy, a rejected forged remedy, an appeal reversing a verdict on new evidence, component propagation through an assembled product, and notice supersession correctly invalidating the old version. Full detail, exact reasons and vote tallies in [`docs/LIVE_PROOFS.md`](docs/LIVE_PROOFS.md).
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

- **No authoritative CPSC source verification.** `file_notice` still trusts claimant-supplied text/URL/hash; there is no `gl.nondet.web` fetch of the regulator's page, no domain allowlist, and no cryptographic binding to official CPSC content. This is the single largest gap against the original handoff brief (`CLAUDE_FINISH_PROMPT.md` item 2) and was not built in this session — it requires a genuinely supported GenVM nondeterministic web-access path to be designed, tested, and reviewed, not retrofitted quickly.
- **No DoS-resistant / authorized source registration** for notices (handoff item 3).
- A few early transaction hashes from this session's on-chain lifecycle run were not retained in captured CLI output (truncated before the hash line) and the public GenLayer explorer was returning `503 DEPLOYMENT_PAUSED` when I tried to recover them afterward; every such step is still backed by an on-chain state read, documented in `docs/LIVE_PROOFS.md`, rather than an unverifiable claim.
- `ReleaseGuard` (`contracts/recall_gate.py`) lints cleanly but was not deployed or exercised live this session.
- Stress tests, replay/race tests, and a dedicated CI run against the updated test suite were not performed this session.
- Real auditor identity, production manufacturer authenticity, and full legal regulatory compliance remain out of scope, as before.

See [`CLAUDE_FINISH_PROMPT.md`](CLAUDE_FINISH_PROMPT.md) for the full original checklist and [`docs/LIVE_PROOFS.md`](docs/LIVE_PROOFS.md) for exact on-chain evidence.
