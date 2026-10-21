# Build status — 21 October 2026

## Security audit remediation (latest)

A security audit of the previous deployment found real fail-open bugs, not just missing features — most seriously, that re-running `verify_source_notice` on an already-verified notice could silently lift an established hold, and that `supersede_notice` dropped the predecessor's hold for a window before the successor was verified. All six findings were fixed, redeployed, and reproduced live against the real CPSC recall used throughout this project. **Current contract:** `0x6946f6912A3cbE14d0C1A8b793bbF1F6C7342b84`, deploy tx `0xb8f5db59c740b09eb23f745212c2c90317d31558c4410cbcb58ada399d40bb7c`, FINALIZED, 6/6 SUCCESS. **Current `ReleaseGuard`:** `0x251367Ba0388dE3bD9e2783C6d18B6354eE349Cc`. Full writeup with every revert payload and transaction hash in [`docs/LIVE_PROOFS.md`](docs/LIVE_PROOFS.md) section E. The exact deployed source hash is in [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

## Deployed and live (history)

- `RecallCircuit` deployed four times to **StudioNet (chain 61999)** this project as the contract gained features and had a security audit applied; see the section above for the current address. Earlier deployments remain live as evidence of their respective lifecycle runs: `0xFeBd68B38e06245c7F319C7e9684510D89923880` (authorized-filer allowlist, pre-audit), `0xE8F4522CA39001F2e073788623f0297f6d883963` (source verification only), `0x8485533fAB15D14F5231B97C51e7EDcE3fF12377` (core lifecycle only).
- **Real authoritative source verification against a genuine, currently-published CPSC recall.** `verify_source_notice` fetched `https://www.cpsc.gov/Recalls/2026/The-Blue-Cactus-Company-Reclining-Chair-Battery-Packs-Recalled-Due-to-Fire-and-Burn-Hazards-Sold-on-Amazon` live over `gl.nondet.web.render` inside GenVM, hashed it, and reached leader+validator consensus (with a genuine DISAGREE vote) that the claimed text matched — binding a real sha256 digest on-chain. A fabricated claim filed against the same real URL was independently fetched, correctly judged not to match, and left `verified=false` — permanently blocked from gating any product. Full detail in [`docs/LIVE_PROOFS.md`](docs/LIVE_PROOFS.md) section B.
- **Admin-gated authorized-filer allowlist, demonstrated live.** `file_notice` now also requires the sender to be the admin or an address the admin authorized. A second, unrelated local account was rejected before authorization, succeeded after `authorize_filer`, and was rejected again after `revoke_filer` — all on-chain, all against the current contract. Full detail in `docs/LIVE_PROOFS.md` section C.
- Real on-chain lifecycle executed and read back across deployments: product registration, notice filing, independent leader+validator AFFECTED/NOT_AFFECTED/UNCERTAIN classification, a successful remedy, a rejected forged remedy, an appeal reversing a verdict on new evidence, component propagation through an assembled product, and notice supersession correctly invalidating the old version.
- **`ReleaseGuard` deployed and exercised live, cross-contract.** `contracts/recall_gate.py` was stale against the abandoned API and has been fixed and deployed at `0xE703DAd1c30Bb469A3C0B3d32028D8Ab500AD647` pointing at the current `RecallCircuit`. Its `record_release` succeeded while the gate was open and reverted with the real on-chain message `"RecallCircuit blocked release"` once an AFFECTED product was registered and resolved — a genuine cross-contract call chain, not a local assumption. Full detail in `docs/LIVE_PROOFS.md` section D.
- StudioNet is gasless; no GEN was spent in this session.

## Fixed in this handoff

- `gltest.config.yaml` previously used an invalid schema (`network:` singular, missing `paths`/`networks.default`) and made `pytest`/`gltest` fail to even collect. Corrected to the real `gltest_cli` config schema.
- The entire `tests/` suite (`conftest.py`, `test_protocol.py`, the Direct Mode test) was written against an **earlier, abandoned contract API** (`register_asset`/`Asset`/`Case`/`propose_notice`/`open_case`/`is_release_allowed`, string-keyed LLM responses) that no longer matches `contracts/recall_circuit.py` (`register_product`/`Product`/`Notice`/`Assessment`/`can_release`, integer-coded structured verdicts). Every one of those 31 "passed" tests from the prior handoff was executing against mock classes that no longer corresponded to the real contract's methods — they were not meaningful evidence. The stale simulator (`tests/conftest.py`, `tests/test_protocol.py`) has been removed; `tests/direct/test_recallcircuit_direct.py` and `tests/test_quality.py` have been rewritten against the real contract API and now run through `genlayer-test`'s actual Direct Mode GenVM-SDK runtime (not a hand-rolled simulator). `tests/test_contract_static.py` was already aligned and is unchanged.
- `docs/STATE_MACHINE.md` was rewritten; it previously described the same abandoned API.
- Both contracts (`recall_circuit.py`, `recall_gate.py`) pass `genvm-lint check` (AST safety + SDK validation) with no errors, only an informational "newer runner available" notice.

## Verified locally this session

- `python -m pytest tests -q` → 38 passed (real Direct-Mode GenVM-SDK tests including the authorized-filer, source-verification, monotonic-verification, supersession-hold, digest-binding, evidence-binding, and assessment-uniqueness coverage; static/AST honesty tests; quality tests; and the static-contract parametrized cases).
- `genvm-lint check` on both contracts.

## CI

`.github/workflows/ci.yml` previously referenced the deleted `tests/test_protocol.py` and failed outright. Fixed to run `pytest tests` (the full current suite, including Direct Mode) and dropped the `frontend` job — RecallCircuit is a standalone Intelligent Contract with no required frontend to gate a release on. `requirements-dev.txt` now pins `genlayer-test==0.29.2` and `genvm-linter==0.11.1rc2` to match what was verified locally.

A follow-up fix was needed: `genlayer-test`'s Direct Mode resolves an unpinned SDK version via GitHub's `/releases/latest` redirect, which currently points at a release (`v0.3.0-rc7`) with no `genvm-universal` asset — this 404'd in a clean CI runner even though it worked locally (an already-cached older version masked it). Pinned `sdk_version='v0.2.16'` (confirmed to carry the asset) on every `direct_deploy` call in the test suite, verified against a cleared local cache.

**Latest run:** [39590792117](https://github.com/Chinny070/RecallCircuit/actions/runs/39590792117) — both jobs (`genvm-lint`, `python`) passed in full. This is CI, not live StudioNet proof; see `docs/LIVE_PROOFS.md` for that.

## Not completed / must not be claimed

- **Source verification is re-fetch-and-compare consensus, not cryptographic proof of government authorship.** `verify_source_notice` independently fetches the claimed URL and reaches leader+validator agreement that the claim matches it, binding a sha256 digest — demonstrated live against a real CPSC recall (see `docs/LIVE_PROOFS.md` section B). Trust in the domain itself still rests on a hardcoded allowlist (`AUTHORIZED_SOURCE_PREFIXES`), not an on-chain governance or signature mechanism, and GenVM's own HTTP fetch is trusted for TLS/domain integrity rather than independently re-verified by the contract.
- **No staking/governance for the filer allowlist** (handoff item 3, partially addressed) — authorization is gated by a single admin address, not a stake-weighted or multisig/governance process; a compromised admin could authorize an unreliable filer. A notice that fails verification still cannot gate a product, which limits but does not eliminate the griefing surface.
- **Appeal/remedy evidence_hash is an auditable commitment, not a verified artifact.** The audit fix (section E5) requires unit-bound text and a mandatory hash, but the contract never fetches or checks what that hash points to.
- A few early transaction hashes from the first deployment's lifecycle run were not retained in captured CLI output (truncated before the hash line) and the public GenLayer explorer was returning `503 DEPLOYMENT_PAUSED` when I tried to recover them afterward; every such step is still backed by an on-chain state read, documented in `docs/LIVE_PROOFS.md`, rather than an unverifiable claim. All second-deployment hashes were captured directly.
- Stress tests and replay/race tests were not performed this session.
- Real auditor identity, production manufacturer authenticity, and full legal regulatory compliance remain out of scope, as before.

See [`CLAUDE_FINISH_PROMPT.md`](CLAUDE_FINISH_PROMPT.md) for the full original checklist and [`docs/LIVE_PROOFS.md`](docs/LIVE_PROOFS.md) for exact on-chain evidence.
