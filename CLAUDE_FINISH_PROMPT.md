# CLAUDE CODE — RECALLCIRCUIT IMPLEMENTATION, STUDIO-NET FINALIZATION & FULL PROOF

You are continuing an EXISTING substantial GenLayer project named **RecallCircuit**. Work on **https://github.com/Chinny070/RecallCircuit** using this supplied complete source ZIP as the authoritative starting material. The ZIP includes the full contract sources, frontend, 36 locally passing simulated/static checks, documentation and this handoff. The repo may initially be empty or contain only scaffolding: synchronize carefully, preserve source, and push complete tracked sources to the user's repo. **Do not start over, do not replace it with a toy/demo or transplant ContextFold code. No Codex and no Docker are needed.**

## Goal

A genuinely high-quality, distinct Intelligent Contract that independently assesses official product recall notices, adjudicates their application to registered assets, propagates component holds, supports appeals and independently attested remediation, and blocks downstream releases through live onchain state. Deliver authentic StudioNet 61999 deployment and receipts, a functioning frontend and polished reviewer evidence. No invented results, no test shortcuts, no screenshots presented as chain proof.

## Hard constraints

- Target ONLY StudioNet `61999` (`0xF22F`), `https://studio.genlayer.com/api`, explorer `https://explorer-studio.genlayer.com`. Never switch to Bradbury, Asimov, Studio Dev, Studio Next or another network in response to a blocker.
- Use the repository-local stable compatible GenLayer CLI/SDK. This project suggests local `genlayer@0.39.1`, front-end `genlayer-js@1.1.8`, but verify the current stable Studionet compatibility; record exact installed/working versions and lockfiles. Do not blindly upgrade GenVM runtime or mix preview chains.
- Use the owner's already-configured signer/wallet. **Never request, display, log, commit, or put secrets in chat**. Follow platform signing/transaction permission prompts. Execute authorized live lifecycle actions when your environment permits; do not invent transaction outcomes.
- No Docker; do not involve Codex. Work directly with existing source, CLI, Python, Node and available cloud connectors. Preserve all useful functionality and test evidence.
- No unrelated mock data in the production UI. Local test mocks must be clearly labeled and confined to tests. No fake numbers, fabricated explorer URLs, fake verifier votes, placeholder final addresses, or unsupported "ALL TESTS PASS" claims.
- Do not claim review score, legal regulatory authority, comprehensive product safety or real repair from AI consensus alone.

## First: audit, build and repair rather than restart

1. Read `README.md`, `BUILD_STATUS.md`, `docs/STATE_MACHINE.md`, `docs/THREAT_MODEL.md`, both Python contracts, the app, and all tests. Check the actual remote branch before writing; avoid overwriting new work.
2. Run `python -m pytest tests/test_protocol.py tests/test_quality.py -q` (locally recorded as **36 passed**). Run `python -m compileall -q contracts tests scripts` and `node --check frontend/src/app.js`. Preserve pass counts but diagnose anything that differs. Note the simulated SDK uses Python SHA3 (NOT exact Keccak) only to compare commitments inside its mock; live proof must check canonical Keccak against chain.
3. Install compatible GenVM tools and run BOTH `genvm-lint check contracts/recall_circuit.py --json` and `genvm-lint check contracts/recall_gate.py --json`. Address *every* substantive storage/type/AST/lazy-call error; do not suppress lint, remove the web/LLM validator, or replace real classification with a deterministic stub. Check actual deployed source size; split only if limits require it and preserve the security model.
4. Install the real `genlayer-test` Direct Mode runner compatible with StudioNet SDK. Run and fix `tests/direct/test_recallcircuit_direct.py`; extend to honest AFFECTED/CLEAR/UNCERTAIN, official source absent, mismatched official ID, false-positive/false-negative leader, malicious prompt injection, owner isolation, graph cycles and depth, competing notice versions, pending appeals, stale cases, forged remedy/unauthorized auditor, and secondary contract. Turn on pickling validation. Record exact test results and conditions without conflating mocked leader with real validators.
5. Audit all current design weaknesses. Priority: source/redirect allowlist and parsing, replay protection, gas/size bounds for 64 notices and 512 cases, graph cycles and ancestor depth, source-content hash/versioning, official recall ID/date canonicalization, credible *exclusions* (avoid falsely calling products safe), duplicate serials/issuer attestations, revision transition rollback, current-case coverage, and auditability. Add new tests for any fixed defect. Do not claim registered cases cover unsubmitted recalls.
6. Run `cd frontend && npm install && npm run check && npm run build`. Generate/commit lockfiles, test at 375px mobile, and verify SDK calls against the exact StudioNet version. The app must show real `LATEST_FINAL` only; preserve copy/disconnect/persistent wallet recheck, wrong-network switch, all write flows, meaningful errors, fee estimates and finalization handling. Do not use status returned from UI alone as consensus proof; cross-check receipt execution and final state. Document build limitations if unresolved.
7. Check read-only `python scripts/check_rpc.py` for chain 61999. If RPC is blocked, diagnose without bypassing chain guard or switching networks. Confirm the signer is ready without exposing keys.

## Live deployment and transaction lifecycle

8. Deploy `RecallCircuit` to StudioNet with correct compatible tooling and current source, capture **real contract address, deployment tx hash, FINALIZED status, execution SUCCESS/FAILURE, consensus outcome, and explorer URLs**. Fetch deployed source, normalize only known encoding/newline effects, hash and compare to repository source. If deployment fails, fix and redeploy, preserving prior failed attempts in the log rather than rewriting history.
9. Test the complete live protocol using honest, publicly available current CPSC recall sources; verify each source and exact notice ID. Avoid fictional CPSC web addresses used in unit tests (those are mocks only). When no appropriate real public remediation proof exists, **do not fake it**; demonstrate guarded refusal and state that positive remediation needs a genuine independently verifiable proof and accepted auditor.
10. Record finalized StudioNet lifecycle proofs for:
   - register genuine/clearly labeled test inventory; accept auditor from distinct signer where available;
   - submit a genuine CPSC recall URL and verify it independently with actual validator consensus;
   - AFFECTED item: public notice applicability, official scope, blocked release;
   - NOT_AFFECTED item: truly excluded model/batch/date with independent agreement, no blanket safety certification;
   - UNCERTAIN item: ambiguous evidence holds;
   - parent/component assembly: child recall propagates hold to a parent that would otherwise clear;
   - pending/denied/appeal: no early release; verify final state after adjudication;
   - malicious proposal or leader: demonstrate honest Direct Mode validator rejection if live fault-injection is impossible;
   - official notice revision: only same recall ID allowed, old clear invalidated until replacement scope is re-adjudicated;
   - separate auditor role; forged proof hash/unauthorized attestations refused;
   - remedy denial on missing evidence; legitimate positive remedy ONLY if authentic proof is actually available;
   - `is_release_allowed` readback for all stages and non-owner/unauthorized writes.
11. Only if StudioNet actually supports inter-contract read calls on this deployment, deploy `ReleaseGuard`, set the registry address, show live `record_release` rejected for affected and accepted for genuinely cleared assets with finalized receipts. If not supported, document `BLOCKED BY NETWORK CAPABILITY`, preserve source and do not fake a pass or switch chains.
12. Every live tx record must contain: method+args (redacting sensitive info), tx hash, receipt/consensus status, execution success, block/explorer link, observed state readback, and exact decision semantics. A tx reaching FINALIZED with failed execution is NOT a successful lifecycle demonstration.
13. After redeploy, update frontend `VITE_CONTRACT_ADDRESS`/production variables, deploy frontend (e.g. Vercel if already accessible), test actual wallet connection/refresh/StudioNet switching, current counter and detail reads, every applicable write form, mobile and keyboard access, error handling, transaction finality.
14. Push completed sources/lockfiles/tests/docs/verified network evidence to **Chinny070/RecallCircuit**. Add a concise README architecture diagram, threat model, deployment registry, real explorer links, source parity, reviewer demo path. Use a dedicated feature branch if needed, reconcile with remote; do not overwrite unrelated branches. Keep `main` clean and current after tests.

## Deliverables and completion definition

- A verified GitHub branch/commit and source parity with deployed contract.
- Core contract hardening and real Direct Mode adversarial tests in CI, consistent tested frontend.
- Onchain proof for an actual official recall, false exclusion challenge, UNCERTAIN hold, child dependency hold, appeal and notice revision; remediation only with real evidence.
- Honest `docs/DEPLOYMENT.md`, `docs/LIVE_PROOFS.md`, `BUILD_STATUS.md` with clear PASS/PARTIAL/BLOCKED labels.
- Screenshot/public URL only after actually working; no fabricated receipts, scores or proof.
- A final concise explanation of remaining genuine blockers (if any), with exact error outputs and the next safe action. **Do the implementation and live actions, not just describe plans.**

## Critical anti-regression rules

- Do not approve a case because the leader's JSON is merely well-formed; validators must independently re-fetch and re-derive the decision, comparing *substantive* findings.
- No clearing a case because the web is unavailable or the product record lacks batch/date information.
- No lifting a manual freeze while active case or component holds remain.
- No owner-only self-remedy shortcut and no treating auditor acceptance alone as physical proof.
- No bypassing current notice revision checks, unbounded recursion or view methods that silently convert error to "safe".
- No synthetic success or empty fake dashboard data: empty means empty and success requires finality + execution + readback.

Review references:
- https://docs.genlayer.com/developers/intelligent-contracts/equivalence-principle
- https://docs.genlayer.com/developers/intelligent-contracts/testing
- https://docs.genlayer.com/api-references/genlayer-js
- https://www.cpsc.gov/Recalls/CPSC-Recalls-Application-Program-Interface-API-Information
