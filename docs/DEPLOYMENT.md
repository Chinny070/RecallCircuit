# RecallCircuit — reproducible deployment procedure

This records the exact tool versions and steps used to lint, test, and deploy
`contracts/recall_circuit.py` to GenLayer StudioNet (chain 61999), so the
result can be reproduced or audited against a specific commit.

## Pinned versions (verified together this session)

| Tool | Version |
|---|---|
| `genlayer` CLI (`package.json`) | `0.39.2` |
| `genlayer-test` / `genvm-linter` (`requirements-dev.txt`) | `0.29.2` / `0.11.1rc2` |
| Direct Mode GenVM SDK (`tests/direct/test_recallcircuit_direct.py::SDK_VERSION`) | `v0.2.16` |
| Contract GenVM runner (`contracts/recall_circuit.py` header `Depends`) | `py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6` |

These are pinned deliberately rather than left to "latest": `genlayer-test`
resolves an unpinned Direct Mode SDK version via GitHub's `/releases/latest`
redirect, which at one point during this project pointed at a pre-release
with no usable asset — see `BUILD_STATUS.md`'s CI section for the concrete
failure this caused. Pin exact versions, don't rely on "latest" resolving to
something that still exists.

## Exact deployable source hash

The sha256 of the contract file actually deployed to StudioNet as of the
current (evidence-attestor) revision:

```
sha256(contracts/recall_circuit.py) = 1b0258a6b42f8242efc02230bb21d639e2316a13ca32d7be181289ead34c0f59
sha256(contracts/recall_gate.py)    = 11d877c8c3e06f587b1ca2b74ac5ffa773479fecb8db61094427979c71023463
```

(The first-audit-round revision, deployed to `0x6946f6912A3cbE14d0C1A8b793bbF1F6C7342b84`, hashed to
`a3ec5f424e860b9c1c784b101b811da16cc51293c8d4e578cca2685e69f5e233` — see `docs/LIVE_PROOFS.md` section E for that deployment's own evidence.)

`SOURCE_MANIFEST.json` carries the same hashes for every tracked file as of
each commit; `docs/LIVE_PROOFS.md` records which git commit and which hash
corresponds to each deployed contract address, so a reader can `git show
<commit>:contracts/recall_circuit.py | sha256sum` and compare directly
against what is live on-chain (`genlayer code <address> | sha256sum`).

## Clean procedure

```bash
# 1. Install pinned tooling
npm install -g genlayer@0.39.2
pip install -r requirements-dev.txt   # genlayer-test==0.29.2, genvm-linter==0.11.1rc2, pytest==9.0.2

# 2. Lint (AST safety + SDK validation)
genvm-lint check contracts/recall_circuit.py --json
genvm-lint check contracts/recall_gate.py --json

# 3. Test (static honesty checks + real Direct Mode GenVM-SDK execution)
python -m compileall -q contracts tests scripts
python -m pytest tests -q

# 4. Confirm the target network before deploying anything
genlayer network info   # must show chainId 61999, StudioNet

# 5. Deploy (gasless on StudioNet)
genlayer deploy --contract contracts/recall_circuit.py
genlayer receipt <deployTxHash> --status FINALIZED

# 6. Confirm the deployed ABI matches the source before using the address
genlayer schema <contractAddress>
```

Redeployment is warranted only when the contract's logic changes (a fix, a
new method, a changed invariant) — not for documentation, test, or CI
changes. Each redeployment in this project's history is recorded with its
reason, address, and deploy transaction hash in `docs/LIVE_PROOFS.md`.
