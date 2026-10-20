"""Real genlayer-test Direct Mode candidate tests.

These are NOT included in the simulated unit suite and are UNVERIFIED here.
Claude must run against an actual installed Direct Mode runner, fix any SDK
version differences, and record outputs before claiming a pass.
"""
import json

CONTRACT = 'contracts/recall_circuit.py'
URL = 'https://www.cpsc.gov/Recalls/2026/example-battery-recall'
PAGE = ('CPSC Recall Number 26-500. Recall date October 1, 2026. Example Co '
        'BAT-1 batteries batch B1 must be replaced. Other batches are not recalled. '
        'Consumers should stop using recalled units and obtain replacements.')
NOTICE = json.dumps({'official_id':'26-500','title':'Example Co battery recall',
                     'recall_date':'2026-10-01','valid':True})
AFFECTED = json.dumps({'finding':'AFFECTED','reason_code':'MODEL_AND_SCOPE_MATCH'})
CLEAR = json.dumps({'finding':'NOT_AFFECTED','reason_code':'SCOPE_EXCLUDES'})


def setup(direct_vm, direct_deploy, direct_bob):
    direct_vm.mock_web(r'cpsc\.gov/Recalls/', {'status':200,'body':PAGE})
    direct_vm.mock_llm('RECALLCIRCUIT OFFICIAL CPSC NOTICE VERIFICATION', NOTICE)
    contract = direct_deploy(CONTRACT)
    aid = contract.register_asset('Battery', 'Example Co', 'BAT-1', 'B1',
                                  'SERIAL-001', '2026-01', direct_bob)
    nid = contract.propose_notice(URL, 0)
    contract.verify_notice(nid)
    return contract, aid, nid


def test_real_vm_affected_hold_and_validator_agreement(direct_vm, direct_deploy, direct_bob):
    contract, aid, nid = setup(direct_vm, direct_deploy, direct_bob)
    direct_vm.mock_llm('RECALLCIRCUIT INDEPENDENT APPLICABILITY AUDIT', AFFECTED)
    case_id = contract.open_case(aid, nid)
    assert contract.is_release_allowed(aid) is False
    contract.resolve_case(case_id)
    assert contract.get_case(case_id)['status'] == 1
    assert direct_vm.run_validator() is True
    assert contract.is_release_allowed(aid) is False


def test_real_vm_leader_forgery_does_not_validate(direct_vm, direct_deploy, direct_bob):
    contract, aid, nid = setup(direct_vm, direct_deploy, direct_bob)
    direct_vm.mock_llm('RECALLCIRCUIT INDEPENDENT APPLICABILITY AUDIT', AFFECTED)
    case_id = contract.open_case(aid, nid)
    contract.resolve_case(case_id)
    direct_vm.clear_mocks()
    direct_vm.mock_web(r'cpsc\.gov/Recalls/', {'status':200,'body':PAGE})
    direct_vm.mock_llm('RECALLCIRCUIT INDEPENDENT APPLICABILITY AUDIT', CLEAR)
    assert direct_vm.run_validator() is False


def test_real_vm_owner_isolation(direct_vm, direct_deploy, direct_bob):
    contract, aid, nid = setup(direct_vm, direct_deploy, direct_bob)
    with direct_vm.prank(direct_bob):
        with direct_vm.expect_revert('asset owner only'):
            contract.open_case(aid, nid)
