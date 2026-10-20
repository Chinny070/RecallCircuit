from pathlib import Path
import ast

ROOT=Path(__file__).resolve().parents[1]
CORE=ROOT/'contracts/recall_circuit.py'
APP=ROOT/'frontend/src/app.js'

def test_core_compiles():
    ast.parse(CORE.read_text(encoding='utf8'))

def test_consensus_reexecutes_official_web_not_leader_justification():
    s=CORE.read_text()
    for fragment in ('gl.nondet.web.render','gl.nondet.exec_prompt',
                     'agree_finding(result', 'independently_classify(url, asset_info, appeal)',
                     'gl.vm.run_nondet_unsafe', 'is_release_allowed'):
        assert fragment in s

def test_no_bradbury_preview_rpc_or_fake_chain():
    for p in [CORE, ROOT/'contracts/recall_gate.py', APP, ROOT/'frontend/.env.example']:
        s=p.read_text().lower()
        assert 'bradbury' not in s and '61997' not in s

def test_frontend_requires_verified_contract_and_final_state():
    s=APP.read_text()
    assert 'VITE_CONTRACT_ADDRESS' in s
    assert 'LATEST_FINAL' in s
    assert 'estimateTransactionFeesForWrite' in s
    assert 'waitForFinalization' in s
    assert 'recallcircuit.wallet' in s
    assert 'disconnectWallet' in s and 'switchNetwork' in s

def test_no_synthetic_sample_data_shipped_as_chain_state():
    s=APP.read_text()
    assert 'stats: null, assets: [], notices: [], cases: []' in s
    assert 'No finalized assets found' in s

def test_new_project_does_not_include_contextfold_logic():
    s=CORE.read_text().lower()
    assert 'propose_fold' not in s and 'current_capsule' not in s
