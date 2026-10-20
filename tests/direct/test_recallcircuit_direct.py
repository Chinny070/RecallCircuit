"""Real genlayer-test Direct Mode tests for RecallCircuit.

These run the actual contract source through the GenVM SDK's runtime
machinery (storage types, @allow_storage dataclasses, gl.vm.run_nondet_unsafe
leader/validator wiring) with only the LLM boundary mocked via
direct_vm.mock_llm. This is real GenVM-SDK execution, not a hand-rolled
simulator; gltest.config.yaml documents the StudioNet-only integration path
used for live consensus evidence.
"""
import json

CONTRACT = 'contracts/recall_circuit.py'
NOTICE_TEXT = ('CPSC Recall Number 26-500. Example Co BAT-1 batteries from batch B1 '
               'must be replaced. Other batches are not recalled.')
AFFECTED = json.dumps({'outcome': 1, 'reason': 'Model BAT-1 batch B1 matches recalled scope'})
NOT_AFFECTED = json.dumps({'outcome': 2, 'reason': 'Batch excluded by notice scope'})
UNCERTAIN = json.dumps({'outcome': 3, 'reason': 'Scope cannot be established'})


def setup(direct_vm, direct_deploy, direct_bob):
    direct_vm.mock_llm('.*', AFFECTED)
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_bob
    pid = contract.register_product('Example Co', 'BAT-1', 'B1', 'SERIAL-001', '2026-01', 'hash-1')
    nid = contract.file_notice('CPSC', 'https://www.cpsc.gov/Recalls/2026/example', '26-500',
                                NOTICE_TEXT, 'notice-hash-1')
    aid = contract.open_assessment(pid, nid)
    return contract, pid, nid, aid


def test_affected_hold_and_validator_agreement(direct_vm, direct_deploy, direct_bob):
    contract, pid, nid, aid = setup(direct_vm, direct_deploy, direct_bob)
    direct_vm.sender = direct_bob
    assert contract.can_release(pid) is False
    contract.resolve_assessment(aid)
    assert contract.get_assessment(aid)['status'] == 1  # AFFECTED
    assert direct_vm.run_validator() is True
    assert contract.can_release(pid) is False


def test_leader_forgery_does_not_validate(direct_vm, direct_deploy, direct_bob):
    contract, pid, nid, aid = setup(direct_vm, direct_deploy, direct_bob)
    direct_vm.sender = direct_bob
    contract.resolve_assessment(aid)
    direct_vm.clear_mocks()
    direct_vm.mock_llm('.*', NOT_AFFECTED)
    # Validator independently re-executes the prompt; disagreement must fail.
    assert direct_vm.run_validator() is False


def test_malformed_leader_response_stays_uncertain(direct_vm, direct_deploy, direct_bob):
    direct_vm.mock_llm('.*', 'not json at all')
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_bob
    pid = contract.register_product('Example Co', 'BAT-1', 'B1', 'SERIAL-001', '2026-01', 'hash-1')
    nid = contract.file_notice('CPSC', 'https://www.cpsc.gov/Recalls/2026/example', '26-500',
                                NOTICE_TEXT, 'notice-hash-1')
    aid = contract.open_assessment(pid, nid)
    contract.resolve_assessment(aid)
    assert contract.get_assessment(aid)['status'] == 3  # UNCERTAIN
    assert contract.can_release(pid) is False


def test_not_affected_clears_gate(direct_vm, direct_deploy, direct_bob):
    direct_vm.mock_llm('.*', NOT_AFFECTED)
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_bob
    pid = contract.register_product('Example Co', 'BAT-2', 'B9', 'SERIAL-002', '2026-02', 'hash-2')
    nid = contract.file_notice('CPSC', 'https://www.cpsc.gov/Recalls/2026/example', '26-500',
                                NOTICE_TEXT, 'notice-hash-1')
    aid = contract.open_assessment(pid, nid)
    contract.resolve_assessment(aid)
    assert contract.get_assessment(aid)['status'] == 2  # NOT_AFFECTED
    assert contract.can_release(pid) is True


def test_owner_isolation_on_component_link(direct_vm, direct_deploy, direct_bob, direct_charlie):
    direct_vm.mock_llm('.*', AFFECTED)
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_bob
    pid = contract.register_product('Example Co', 'BAT-1', 'B1', 'SERIAL-001', '2026-01', 'hash-1')
    direct_vm.sender = direct_charlie
    comp_id = contract.register_product('Part Co', 'CELL-9', 'C9', 'SERIAL-900', '2026-01', 'hash-9')
    with direct_vm.expect_revert('owner only'):
        contract.link_component(pid, comp_id)


def test_dependency_cycle_rejected(direct_vm, direct_deploy, direct_bob):
    direct_vm.mock_llm('.*', AFFECTED)
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_bob
    a = contract.register_product('A', 'A', 'A', 'A', '2026-01', 'h')
    b = contract.register_product('B', 'B', 'B', 'B', '2026-01', 'h')
    contract.link_component(a, b)
    with direct_vm.expect_revert('dependency cycle'):
        contract.link_component(b, a)


def test_appeal_reevaluates_with_evidence(direct_vm, direct_deploy, direct_bob):
    direct_vm.mock_llm('.*', AFFECTED)
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_bob
    pid = contract.register_product('Example Co', 'BAT-1', 'B1', 'SERIAL-001', '2026-01', 'hash-1')
    nid = contract.file_notice('CPSC', 'https://www.cpsc.gov/Recalls/2026/example', '26-500',
                                NOTICE_TEXT, 'notice-hash-1')
    aid = contract.open_assessment(pid, nid)
    contract.resolve_assessment(aid)
    assert contract.get_assessment(aid)['status'] == 1
    appeal_id = contract.appeal_assessment(aid, 'Serial number is outside the recalled batch')
    direct_vm.clear_mocks()
    direct_vm.mock_llm('.*', NOT_AFFECTED)
    contract.resolve_appeal(appeal_id)
    assert contract.get_assessment(aid)['status'] == 2


def test_remedy_flow_clears_affected_unit(direct_vm, direct_deploy, direct_bob):
    direct_vm.mock_llm('.*', AFFECTED)
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_bob
    pid = contract.register_product('Example Co', 'BAT-1', 'B1', 'SERIAL-001', '2026-01', 'hash-1')
    nid = contract.file_notice('CPSC', 'https://www.cpsc.gov/Recalls/2026/example', '26-500',
                                NOTICE_TEXT, 'notice-hash-1')
    aid = contract.open_assessment(pid, nid)
    contract.resolve_assessment(aid)
    remedy_id = contract.request_remedy(aid, 'Replacement unit installed per CPSC instructions')
    direct_vm.clear_mocks()
    direct_vm.mock_llm('.*', NOT_AFFECTED)
    contract.resolve_remedy(remedy_id)
    assert contract.get_assessment(aid)['status'] == 5  # REMEDIATED
    assert contract.can_release(pid) is True


def test_notice_supersede_invalidates_old_version(direct_vm, direct_deploy, direct_bob):
    direct_vm.mock_llm('.*', NOT_AFFECTED)
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_bob
    pid = contract.register_product('Example Co', 'BAT-1', 'B1', 'SERIAL-001', '2026-01', 'hash-1')
    nid = contract.file_notice('CPSC', 'https://www.cpsc.gov/Recalls/2026/example', '26-500',
                                NOTICE_TEXT, 'notice-hash-1')
    new_nid = contract.supersede_notice(nid, NOTICE_TEXT + ' Revised scope.', 'notice-hash-2')
    with direct_vm.expect_revert('superseded notice'):
        contract.open_assessment(pid, nid)
    aid2 = contract.open_assessment(pid, new_nid)
    contract.resolve_assessment(aid2)
    assert contract.get_assessment(aid2)['status'] == 2
