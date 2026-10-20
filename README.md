# RecallCircuit

**A GenLayer Intelligent Contract that translates official product recalls into scoped, enforceable inventory holds and component-level release restrictions.**

**Target network: StudioNet only — chain ID `61999` (`0xF22F`), RPC `https://studio.genlayer.com/api`.** No Bradbury, preview, fabricated explorer receipts, or fake application data.

> **Build status (2026-10-20):** Substantial source implementation and frontend complete. **36 simulated/static checks passed locally.** Real `genlayer-test` Direct Mode, GenVM lint, StudioNet deployment, live source parity, and finalized consensus/consumer integration are **not yet verified**. See `BUILD_STATUS.md` and `CLAUDE_FINISH_PROMPT.md`.

## What makes this different

ContextFold audits semantic memory compression. RecallCircuit independently checks **whether an authoritative product recall applies to a registered product**, and uses that finding to block actions through a supply-chain dependency graph. It is neither a summary service nor a general-purpose escrow/dispute clone.

## Architecture

```text
Official CPSC URL proposal
  └── verify_notice(): independent live web + structured LLM audit
       └── VERIFIED official notice, with id/date/digest
             └── open_case(asset, notice): PENDING (hold)
                    └── resolve_case(): independent leader + validator re-execution
                         ├── AFFECTED        -> HOLD
                         ├── UNCERTAIN       -> HOLD
                         └── NOT_AFFECTED   -> scoped clearance for that notice

A product may include several registered component assets.
is_release_allowed(product) recursively checks its own cases, frozen state,
all component holds, and superseded-notice coverage.

AFFECTED -> independent auditor role acceptance -> owner proposes public remedy
         -> auditor signs commitment -> validators check notice and evidence
         -> REMEDIATED only if both real-world evidence review and auditor pass

Any current decision may be appealed twice; appeal immediately reactivates HOLD.
A verified notice revision invalidates earlier decisions until the successor
notice has a resolved case.
```

## Core files

| Path | Function |
| --- | --- |
| `contracts/recall_circuit.py` | Bounded notice, product, case, appeal, remediation and graph protocol |
| `contracts/recall_gate.py` | Optional cross-contract release consumer; integration on StudioNet not yet verified |
| `frontend/` | Real-chain dashboard, asset/notice/case/remedy forms, injected-wallet connection, StudioNet network switch and latest-final reads |
| `tests/test_protocol.py` | 30 **simulated SDK state-machine** tests; not live GenVM results |
| `tests/test_quality.py` | 6 static contract/UX checks |
| `tests/direct/` | Additional Direct Mode candidates; runtime execution is outstanding |
| `docs/THREAT_MODEL.md` | Trust boundaries and design limitations |
| `docs/STATE_MACHINE.md` | Formal transitions and invariants |
| `CLAUDE_FINISH_PROMPT.md` | Exact remaining verification/deployment tasks |

## Protocol API

| Function | Who can call | Semantics |
| --- | --- | --- |
| `register_asset(name,manufacturer,model,batch,serial,made_on,auditor)` | Any wallet | Registers immutable declared inventory identity, not independent authenticity proof |
| `accept_auditor(aid)` | Named separate auditor | Consent to attest future specific remedy evidence |
| `link_component(parent,child)` | Parent owner | Acyclic bounded product graph; must share owner and be linked before cases |
| `freeze_asset(aid)` / `unfreeze_asset(aid)` | Asset owner | Manual emergency hold; cannot lift while safety case holds |
| `propose_notice(url,parent_id)` | Any wallet, except revisions restricted to original proposer | Whitelisted official CPSC source and optional version lineage |
| `verify_notice(nid)` | Anyone | Independently re-fetches regulator source; verifies recall identity and date |
| `open_case(aid,nid)` | Asset owner | Starts default-deny case for one verified notice |
| `resolve_case(cid)` | Anyone | Independently classifies notice applicability; affected/uncertain remain held |
| `appeal_case(cid,grounds)` | Asset owner | Enters hold pending new independent determination, max two appeals |
| `propose_remedy(cid,proof_url)` | Asset owner | Initiates remedy evaluation, only from affected case |
| `attest_remedy(cid,approved,proof_hash)` | Accepted separate auditor | Signs exact proof-URL commitment (not independent physical verification itself) |
| `resolve_remedy(cid)` | Anyone | Checks public proof vs authoritative remedy; safe release only on verified match |
| `is_release_allowed(aid)` | Anyone / consumer contract | Fail-closed gate over active scoped cases and component holds |
| `get_asset/get_notice/get_case/get_stats` | Anyone | Auditable state and counters |

### Meaning of "clear"

A `NOT_AFFECTED` case means **not affected by the one specific verified recall**. It does not certify the product as generally safe or unaffected by recalls never submitted/assessed. `is_release_allowed` is a **registered-case and registered-component gate**, *not* a comprehensive regulator feed; unregistered products and products without any cases are refused. Businesses must integrate the optional release gate to make it effective.

## Local tests

```bash
python -m pip install -r requirements-dev.txt
python -m compileall -q contracts tests scripts
python -m pytest tests/test_protocol.py tests/test_quality.py -q
node --check frontend/src/app.js
```

The local Python suite uses an intentionally stubbed SDK. It validates state transitions and guards but **does not execute real GenVM, independently query live validators, or prove StudioNet finality**.

For official GenLayer Direct Mode, install a compatible SDK, `genlayer-test`, and GenVM runner, then run `python -m pytest tests/direct -q`. The three direct tests supplied are unverified candidates and should be refined with actual runner findings, not counted as passes.

## Frontend

```bash
cd frontend
cp .env.example .env
# Set VITE_CONTRACT_ADDRESS to a VERIFIED FINALIZED StudioNet deployment.
npm install
npm run check
npm run build
npm run dev
```

Features include a responsive light design, glowing hover cards, page navigation, real latest-final contract data, address-aware wallet menus (copy/disconnect), remembered wallet session re-check on refresh, injected wallet chain correction, CPSC notice submissions, case and appeal forms, and proof-URL hash generation. The app intentionally shows empty states rather than fabricated data. The network and contract address are never silently switched to another chain.

**Before submission:** Claude should confirm `genlayer-js@1.1.8` API/fee estimation semantics on chain 61999, generate/commit the lockfiles, test the built frontend, and demonstrate live reads and writes through an injected wallet.

## Real deployment & reviewer demo

See `CLAUDE_FINISH_PROMPT.md` for a StudioNet-only, source-hash-verified deployment plan and a finality-proof matrix. Do not publish invented tx hashes, claim remote consensus from mocked tests, or mark a safety outcome as final until receipt and latest-final state agree.

## Safety scope

This is a software protocol prototype, **not a CPSC affiliate, legal product recall determination, physical safety inspection, or guarantee that a repair occurred**. A manufacturer may self-declare identity fields. Auditors must be trusted by the integrating organization; an auditor signature alone is not proof of repair. Consult official regulators for real product safety actions.
