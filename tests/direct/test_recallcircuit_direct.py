"""Real genlayer-test Direct Mode tests for RecallCircuit.

These run the actual contract source through the GenVM SDK's runtime
machinery (storage types, @allow_storage dataclasses, gl.vm.run_nondet_unsafe
leader/validator wiring) with only the web/LLM boundary mocked via
direct_vm.mock_web / direct_vm.mock_llm. This is real GenVM-SDK execution,
not a hand-rolled simulator; gltest.config.yaml documents the StudioNet-only
integration path used for live consensus evidence. Cross-contract release
decisions (ReleaseGuard) are not exercised here -- Direct Mode deploys one
contract at a time -- and are instead demonstrated live on StudioNet; see
docs/LIVE_PROOFS.md section D.
"""
import json

CONTRACT = 'contracts/recall_circuit.py'
SDK_VERSION = 'v0.2.16'  # pinned: latest genvm release lacks a genvm-universal asset as of this writing
URL = 'https://www.cpsc.gov/Recalls/2026/example-battery-recall'
LIVE_PAGE = ('CPSC Recall Number 26-500. Example Co BAT-1 batteries from batch B1 '
             'must be replaced. Other batches are not recalled.')
NOTICE_TEXT = LIVE_PAGE  # claimant text matches the live page in the happy path
SERIAL = 'SERIAL-001'

AFFECTED = json.dumps({'outcome': 1, 'reason': 'Model BAT-1 batch B1 matches recalled scope'})
NOT_AFFECTED = json.dumps({'outcome': 2, 'reason': 'Batch excluded by notice scope'})
MATCH = json.dumps({'match': True, 'reason': 'Claimed text faithfully summarizes the live page'})
MISMATCH = json.dumps({'match': False, 'reason': 'Claimed text adds scope absent from the live page'})

SCOPE_PATTERN = 'INDEPENDENT SCOPE ADJUDICATION'
SOURCE_PATTERN = 'INDEPENDENT SOURCE AUTHENTICITY CHECK'


def mock_happy_source(direct_vm):
    direct_vm.mock_web(r'cpsc\.gov', {'status': 200, 'body': LIVE_PAGE})
    direct_vm.mock_llm(SOURCE_PATTERN, MATCH)


def deploy_and_authorize(direct_deploy, direct_vm, filer):
    """Deploy (deployer becomes admin) then authorize `filer` to call file_notice."""
    contract = direct_deploy(CONTRACT, sdk_version=SDK_VERSION)
    contract.authorize_filer(filer)
    direct_vm.sender = filer
    return contract


def file_and_verify(contract, direct_vm, text=NOTICE_TEXT, url=URL, source_hash='notice-hash-1'):
    nid = contract.file_notice('CPSC', url, '26-500', text, source_hash)
    contract.verify_source_notice(nid)
    return nid


def setup(direct_vm, direct_deploy, direct_bob, serial=SERIAL):
    mock_happy_source(direct_vm)
    direct_vm.mock_llm(SCOPE_PATTERN, AFFECTED)
    contract = deploy_and_authorize(direct_deploy, direct_vm, direct_bob)
    pid = contract.register_product('Example Co', 'BAT-1', 'B1', serial, '2026-01', 'hash-1')
    nid = file_and_verify(contract, direct_vm)
    aid = contract.open_assessment(pid, nid)
    return contract, pid, nid, aid


# --- authorized-filer allowlist ---------------------------------------------

def test_unauthorized_filer_cannot_file_notice(direct_vm, direct_deploy, direct_bob):
    contract = direct_deploy(CONTRACT, sdk_version=SDK_VERSION)  # deployer is admin; bob is never authorized
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert('sender not an authorized filer'):
        contract.file_notice('CPSC', URL, '26-500', NOTICE_TEXT, 'h')


def test_admin_can_revoke_filer(direct_vm, direct_deploy, direct_bob):
    contract = direct_deploy(CONTRACT, sdk_version=SDK_VERSION)
    contract.authorize_filer(direct_bob)
    assert contract.is_authorized_filer(direct_bob) is True
    contract.revoke_filer(direct_bob)
    assert contract.is_authorized_filer(direct_bob) is False
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert('sender not an authorized filer'):
        contract.file_notice('CPSC', URL, '26-500', NOTICE_TEXT, 'h')


def test_non_admin_cannot_authorize_filers(direct_vm, direct_deploy, direct_bob, direct_charlie):
    contract = direct_deploy(CONTRACT, sdk_version=SDK_VERSION)
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert('admin only'):
        contract.authorize_filer(direct_charlie)


# --- source verification: domain, fetch failure, mismatch, digest binding ---

def test_unauthorized_domain_rejected(direct_vm, direct_deploy, direct_bob):
    contract = deploy_and_authorize(direct_deploy, direct_vm, direct_bob)
    with direct_vm.expect_revert('source domain not authorized'):
        contract.file_notice('CPSC', 'https://not-cpsc.example/recall', '26-500', NOTICE_TEXT, 'h')


def test_unreachable_source_stays_unverified_and_blocks_assessment(direct_vm, direct_deploy, direct_bob):
    # No web mock registered -> fetch fails inside _fetch_and_match's try/except.
    direct_vm.strict_mocks = False
    contract = deploy_and_authorize(direct_deploy, direct_vm, direct_bob)
    pid = contract.register_product('Example Co', 'BAT-1', 'B1', SERIAL, '2026-01', 'hash-1')
    nid = contract.file_notice('CPSC', URL, '26-500', NOTICE_TEXT, 'notice-hash-1')
    contract.verify_source_notice(nid)
    assert contract.get_notice(nid)['verified'] is False
    with direct_vm.expect_revert('notice not source-verified'):
        contract.open_assessment(pid, nid)


def test_mismatched_claim_stays_unverified(direct_vm, direct_deploy, direct_bob):
    direct_vm.mock_web(r'cpsc\.gov', {'status': 200, 'body': LIVE_PAGE})
    direct_vm.mock_llm(SOURCE_PATTERN, MISMATCH)
    contract = deploy_and_authorize(direct_deploy, direct_vm, direct_bob)
    nid = contract.file_notice('CPSC', URL, '26-500', 'A completely different fabricated recall claim.', 'h')
    contract.verify_source_notice(nid)
    assert contract.get_notice(nid)['verified'] is False


def test_verified_notice_binds_source_digest(direct_vm, direct_deploy, direct_bob):
    mock_happy_source(direct_vm)
    contract = deploy_and_authorize(direct_deploy, direct_vm, direct_bob)
    nid = file_and_verify(contract, direct_vm)
    notice = contract.get_notice(nid)
    assert notice['verified'] is True
    assert len(notice['source_digest']) == 64  # sha256 hex


def test_already_verified_notice_cannot_be_reverified(direct_vm, direct_deploy, direct_bob):
    """Monotonic verification: a passing re-check can never un-verify a notice,
    but re-running the check at all is refused outright once verified, so a
    later fetch failure or edited page can never flip an established hold off.
    """
    mock_happy_source(direct_vm)
    contract = deploy_and_authorize(direct_deploy, direct_vm, direct_bob)
    nid = file_and_verify(contract, direct_vm)
    assert contract.get_notice(nid)['verified'] is True
    with direct_vm.expect_revert('notice already verified'):
        contract.verify_source_notice(nid)


def test_validator_rejects_fabricated_digest_even_if_match_agrees(direct_vm, direct_deploy, direct_bob):
    """The validator must independently recompute the digest, not just the
    match verdict -- a leader cannot bind a fabricated digest by getting the
    boolean right while the underlying content differs between fetches.
    """
    contract = deploy_and_authorize(direct_deploy, direct_vm, direct_bob)
    direct_vm.mock_web(r'cpsc\.gov', {'status': 200, 'body': LIVE_PAGE})
    direct_vm.mock_llm(SOURCE_PATTERN, MATCH)
    nid = contract.file_notice('CPSC', URL, '26-500', NOTICE_TEXT, 'h')
    contract.verify_source_notice(nid)
    assert contract.get_notice(nid)['verified'] is True
    # Simulate the live page having changed between the leader's fetch and the
    # validator's independent re-fetch: same match verdict, different content
    # -> different digest -> validator must disagree.
    direct_vm.clear_mocks()
    direct_vm.mock_web(r'cpsc\.gov', {'status': 200, 'body': LIVE_PAGE + ' EDITED AFTER THE FACT'})
    direct_vm.mock_llm(SOURCE_PATTERN, MATCH)
    assert direct_vm.run_validator() is False


# --- supersession: hold preserved until safe replacement activation --------

def test_supersede_preserves_hold_until_successor_verified(direct_vm, direct_deploy, direct_bob):
    contract, pid, nid, aid = setup(direct_vm, direct_deploy, direct_bob)
    contract.resolve_assessment(aid)
    assert contract.get_assessment(aid)['status'] == 1  # AFFECTED
    assert contract.can_release(pid) is False

    new_nid = contract.supersede_notice(nid, NOTICE_TEXT + ' Revised scope applies to batch B1 and B2.',
                                         'notice-hash-2')
    # The predecessor must still be active and still gating -- no window where
    # neither notice counts against the product.
    assert contract.get_notice(nid)['active'] is True
    assert contract.can_release(pid) is False

    with direct_vm.expect_revert('notice not source-verified'):
        contract.open_assessment(pid, new_nid)

    # Safe replacement activation: verifying the successor retires the
    # predecessor as a side effect, exactly once, and only now.
    contract.verify_source_notice(new_nid)
    assert contract.get_notice(nid)['active'] is False
    assert contract.get_notice(new_nid)['active'] is True

    with direct_vm.expect_revert('superseded notice'):
        contract.open_assessment(pid, nid)

    aid2 = contract.open_assessment(pid, new_nid)
    contract.resolve_assessment(aid2)
    assert contract.get_assessment(aid2)['status'] == 1  # still affected under the revised notice


def test_supersede_successor_never_verified_keeps_predecessor_gating_forever(direct_vm, direct_deploy, direct_bob):
    contract, pid, nid, aid = setup(direct_vm, direct_deploy, direct_bob)
    contract.resolve_assessment(aid)
    assert contract.can_release(pid) is False
    contract.supersede_notice(nid, NOTICE_TEXT + ' Revised.', 'notice-hash-2')
    # No one ever verifies the successor -- the predecessor's hold is the
    # permanent, safe failure mode, not a silent release.
    assert contract.get_notice(nid)['active'] is True
    assert contract.can_release(pid) is False


# --- scope classification lifecycle -----------------------------------------

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
    mock_happy_source(direct_vm)
    direct_vm.mock_llm(SCOPE_PATTERN, NOT_AFFECTED)
    # Validator independently re-executes the prompt; disagreement must fail.
    assert direct_vm.run_validator() is False


def test_malformed_leader_response_stays_uncertain(direct_vm, direct_deploy, direct_bob):
    mock_happy_source(direct_vm)
    direct_vm.mock_llm(SCOPE_PATTERN, 'not json at all')
    contract = deploy_and_authorize(direct_deploy, direct_vm, direct_bob)
    pid = contract.register_product('Example Co', 'BAT-1', 'B1', SERIAL, '2026-01', 'hash-1')
    nid = file_and_verify(contract, direct_vm)
    aid = contract.open_assessment(pid, nid)
    contract.resolve_assessment(aid)
    assert contract.get_assessment(aid)['status'] == 3  # UNCERTAIN
    assert contract.can_release(pid) is False


def test_not_affected_clears_gate(direct_vm, direct_deploy, direct_bob):
    mock_happy_source(direct_vm)
    direct_vm.mock_llm(SCOPE_PATTERN, NOT_AFFECTED)
    contract = deploy_and_authorize(direct_deploy, direct_vm, direct_bob)
    pid = contract.register_product('Example Co', 'BAT-2', 'B9', 'SERIAL-002', '2026-02', 'hash-2')
    nid = file_and_verify(contract, direct_vm)
    aid = contract.open_assessment(pid, nid)
    contract.resolve_assessment(aid)
    assert contract.get_assessment(aid)['status'] == 2  # NOT_AFFECTED
    assert contract.can_release(pid) is True


def test_assessment_evidence_hash_binds_to_verified_source_digest(direct_vm, direct_deploy, direct_bob):
    """Assessment.evidence_hash must come from the independently verified
    source_digest, never from the claimant's unverified file_notice source_hash.
    """
    contract, pid, nid, aid = setup(direct_vm, direct_deploy, direct_bob)
    notice = contract.get_notice(nid)
    assessment = contract.get_assessment(aid)
    assert assessment['evidence_hash'] == notice['source_digest']
    assert assessment['evidence_hash'] != 'notice-hash-1'  # the claimant-supplied, unverified value


# --- assessment uniqueness / retry lifecycle --------------------------------

def test_duplicate_assessment_for_same_revision_rejected(direct_vm, direct_deploy, direct_bob):
    contract, pid, nid, aid = setup(direct_vm, direct_deploy, direct_bob)
    with direct_vm.expect_revert('assessment already exists for this product/notice/revision'):
        contract.open_assessment(pid, nid)


def test_revision_bump_allows_a_fresh_assessment(direct_vm, direct_deploy, direct_bob, direct_charlie):
    contract, pid, nid, aid = setup(direct_vm, direct_deploy, direct_bob)
    comp_id = contract.register_product('Part Co', 'CELL-9', 'C9', 'SERIAL-900', '2026-01', 'hash-9')
    contract.link_component(pid, comp_id)  # bumps pid's revision
    aid2 = contract.open_assessment(pid, nid)
    assert aid2 != aid


# --- component graph ---------------------------------------------------------

def test_owner_isolation_on_component_link(direct_vm, direct_deploy, direct_bob, direct_charlie):
    contract = deploy_and_authorize(direct_deploy, direct_vm, direct_bob)
    pid = contract.register_product('Example Co', 'BAT-1', 'B1', SERIAL, '2026-01', 'hash-1')
    direct_vm.sender = direct_charlie
    comp_id = contract.register_product('Part Co', 'CELL-9', 'C9', 'SERIAL-900', '2026-01', 'hash-9')
    with direct_vm.expect_revert('owner only'):
        contract.link_component(pid, comp_id)


def test_dependency_cycle_rejected(direct_vm, direct_deploy, direct_bob):
    contract = deploy_and_authorize(direct_deploy, direct_vm, direct_bob)
    a = contract.register_product('A', 'A', 'A', 'A', '2026-01', 'h')
    b = contract.register_product('B', 'B', 'B', 'B', '2026-01', 'h')
    contract.link_component(a, b)
    with direct_vm.expect_revert('dependency cycle'):
        contract.link_component(b, a)


# --- unit-bound, independently-committed appeal/remedy evidence ------------

def test_appeal_evidence_must_reference_unit_serial(direct_vm, direct_deploy, direct_bob):
    contract, pid, nid, aid = setup(direct_vm, direct_deploy, direct_bob)
    contract.resolve_assessment(aid)
    with direct_vm.expect_revert('evidence must reference the unit serial number'):
        contract.appeal_assessment(aid, 'This unit was never affected, trust me.', 'evidence-hash-1')


def test_remedy_evidence_must_reference_unit_serial(direct_vm, direct_deploy, direct_bob):
    contract, pid, nid, aid = setup(direct_vm, direct_deploy, direct_bob)
    contract.resolve_assessment(aid)
    with direct_vm.expect_revert('evidence must reference the unit serial number'):
        contract.request_remedy(aid, 'Replacement installed per instructions.', 'evidence-hash-1')


def test_appeal_reevaluates_with_evidence(direct_vm, direct_deploy, direct_bob):
    contract, pid, nid, aid = setup(direct_vm, direct_deploy, direct_bob)
    contract.resolve_assessment(aid)
    assert contract.get_assessment(aid)['status'] == 1
    appeal_id = contract.appeal_assessment(
        aid, f'Serial number {SERIAL} is outside the recalled batch', 'evidence-hash-1')
    appeal = contract.get_appeal(appeal_id)
    assert appeal['evidence_hash'] == 'evidence-hash-1'
    direct_vm.clear_mocks()
    mock_happy_source(direct_vm)
    direct_vm.mock_llm(SCOPE_PATTERN, NOT_AFFECTED)
    contract.resolve_appeal(appeal_id)
    assert contract.get_assessment(aid)['status'] == 2


def test_remedy_flow_clears_affected_unit(direct_vm, direct_deploy, direct_bob):
    contract, pid, nid, aid = setup(direct_vm, direct_deploy, direct_bob)
    contract.resolve_assessment(aid)
    remedy_id = contract.request_remedy(
        aid, f'Replacement unit installed on {SERIAL} per CPSC instructions', 'evidence-hash-1')
    remedy = contract.get_remedy(remedy_id)
    assert remedy['evidence_hash'] == 'evidence-hash-1'
    direct_vm.clear_mocks()
    mock_happy_source(direct_vm)
    direct_vm.mock_llm(SCOPE_PATTERN, NOT_AFFECTED)
    contract.resolve_remedy(remedy_id)
    assert contract.get_assessment(aid)['status'] == 5  # REMEDIATED
    assert contract.can_release(pid) is True


def test_forged_remedy_without_matching_evidence_stays_held(direct_vm, direct_deploy, direct_bob):
    contract, pid, nid, aid = setup(direct_vm, direct_deploy, direct_bob)
    contract.resolve_assessment(aid)
    remedy_id = contract.request_remedy(
        aid, f'Unit {SERIAL}: trust me it is fine now', 'evidence-hash-1')
    direct_vm.clear_mocks()
    mock_happy_source(direct_vm)
    direct_vm.mock_llm(SCOPE_PATTERN, AFFECTED)  # independent re-check still finds it affected
    contract.resolve_remedy(remedy_id)
    assert contract.get_assessment(aid)['status'] == 3  # UNCERTAIN, not cleared
    assert contract.can_release(pid) is False
