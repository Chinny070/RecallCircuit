# Not part of this submission

**This frontend is stale and non-functional against the current contract.**
It was written against an earlier, abandoned contract API
(`register_asset`/`propose_notice`/`open_case`/`is_release_allowed`, etc.)
that no longer matches `contracts/recall_circuit.py`'s real method names
(`register_product`/`file_notice`/`open_assessment`/`can_release`, etc. — see
`docs/STATE_MACHINE.md`). It has not been updated, has not been verified to
build or run against a live wallet, and must not be presented, deployed, or
referenced as a working interface to RecallCircuit.

RecallCircuit is submitted as a **standalone GenLayer Intelligent Contract**;
no frontend is required or claimed as part of this submission. Interacting
with the deployed contract (see `docs/LIVE_PROOFS.md` for addresses) is done
directly via the `genlayer` CLI, as documented in `docs/DEPLOYMENT.md` and the
project `README.md`.

Rebuilding this frontend against the current contract API is optional,
future work — not a requirement of this submission.
