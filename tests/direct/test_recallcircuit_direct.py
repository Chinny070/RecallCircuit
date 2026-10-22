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
EVIDENCE_PATTERN = 'INDEPENDENT EVIDENCE SOURCE CHECK'

EVIDENCE_SCOPE_EXCLUSION, EVIDENCE_REMEDY_COMPLETED = 1, 2
VALID_COMMITMENT = 'sha256:' + 'ab' * 32  # 64 lowercase hex chars


def mock_happy_source(direct_vm):
    direct_vm.mock_web(r'cpsc\.gov', {'status': 200, 'body': LIVE_PAGE})
    direct_vm.mock_llm(SOURCE_PATTERN, MATCH)


def as_admin_authorize_issuer(contract, direct_vm, admin, issuer):
    """direct_owner is the deployer/admin: the pytest_plugin fixture for it is
    literally named '(default sender)', the same address direct_vm.sender
    starts as before any test switches it."""
    direct_vm.sender = admin
    contract.authorize_issuer(issuer)


def submit_attestation(contract, direct_vm, issuer, assessment_id, evidence_type, description,
                        commitment=VALID_COMMITMENT, source_url=''):
    direct_vm.sender = issuer
    return contract.submit_attestation(assessment_id, evidence_type, commitment, description, source_url)


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


def test_appeal_reevaluates_with_evidence(direct_vm, direct_deploy, direct_bob, direct_charlie, direct_owner):
    """Clearance now requires BOTH the owner's appeal AND an independent,
    authorized, non-owner issuer's case-bound attestation AND validator
    agreement -- not the owner's text alone."""
    contract, pid, nid, aid = setup(direct_vm, direct_deploy, direct_bob)
    contract.resolve_assessment(aid)
    assert contract.get_assessment(aid)['status'] == 1
    direct_vm.sender = direct_bob
    appeal_id = contract.appeal_assessment(
        aid, f'Serial number {SERIAL} is outside the recalled batch', 'evidence-hash-1')
    appeal = contract.get_appeal(appeal_id)
    assert appeal['evidence_hash'] == 'evidence-hash-1'

    as_admin_authorize_issuer(contract, direct_vm, direct_owner, direct_charlie)
    att_id = submit_attestation(
        contract, direct_vm, direct_charlie, aid, EVIDENCE_SCOPE_EXCLUSION,
        f'Factory QA log confirms unit {SERIAL} is a pre-production test lot, never commercially sold.')

    direct_vm.clear_mocks()
    mock_happy_source(direct_vm)
    direct_vm.mock_llm(SCOPE_PATTERN, NOT_AFFECTED)
    direct_vm.sender = direct_bob
    contract.resolve_appeal(appeal_id)
    assert contract.get_assessment(aid)['status'] == 2
    assert contract.get_attestation(att_id)['consumed'] is True


def test_remedy_flow_clears_affected_unit(direct_vm, direct_deploy, direct_bob, direct_charlie, direct_owner):
    contract, pid, nid, aid = setup(direct_vm, direct_deploy, direct_bob)
    contract.resolve_assessment(aid)
    direct_vm.sender = direct_bob
    remedy_id = contract.request_remedy(
        aid, f'Replacement unit installed on {SERIAL} per CPSC instructions', 'evidence-hash-1')
    remedy = contract.get_remedy(remedy_id)
    assert remedy['evidence_hash'] == 'evidence-hash-1'

    as_admin_authorize_issuer(contract, direct_vm, direct_owner, direct_charlie)
    att_id = submit_attestation(
        contract, direct_vm, direct_charlie, aid, EVIDENCE_REMEDY_COMPLETED,
        f'Authorized repair provider confirms unit {SERIAL} received the CPSC-specified replacement part.')

    direct_vm.clear_mocks()
    mock_happy_source(direct_vm)
    direct_vm.mock_llm(SCOPE_PATTERN, NOT_AFFECTED)
    direct_vm.sender = direct_bob
    contract.resolve_remedy(remedy_id)
    assert contract.get_assessment(aid)['status'] == 5  # REMEDIATED
    assert contract.can_release(pid) is True
    assert contract.get_attestation(att_id)['consumed'] is True


def test_forged_remedy_without_matching_evidence_stays_held(direct_vm, direct_deploy, direct_bob):
    """No attestation at all: the claimant's own convincing text, and even an
    LLM willing to accept it, must never be enough -- missing attestation is
    checked before any LLM call is even made."""
    contract, pid, nid, aid = setup(direct_vm, direct_deploy, direct_bob)
    contract.resolve_assessment(aid)
    direct_vm.sender = direct_bob
    remedy_id = contract.request_remedy(
        aid, f'Unit {SERIAL}: trust me it is fine now', 'evidence-hash-1')
    direct_vm.clear_mocks()
    mock_happy_source(direct_vm)
    direct_vm.mock_llm(SCOPE_PATTERN, AFFECTED)  # irrelevant: never reached without an attestation
    contract.resolve_remedy(remedy_id)
    assert contract.get_assessment(aid)['status'] == 3  # UNCERTAIN, not cleared
    assert contract.can_release(pid) is False


# --- independent evidence attestors: authorization, binding, mandatory gating

def test_unauthorized_issuer_cannot_attest(direct_vm, direct_deploy, direct_bob, direct_charlie):
    contract, pid, nid, aid = setup(direct_vm, direct_deploy, direct_bob)
    contract.resolve_assessment(aid)
    direct_vm.sender = direct_charlie  # never authorized as an issuer
    with direct_vm.expect_revert('sender not an authorized evidence issuer'):
        contract.submit_attestation(aid, EVIDENCE_SCOPE_EXCLUSION, VALID_COMMITMENT, f'Unit {SERIAL} excluded.', '')


def test_admin_is_never_an_implicit_issuer_and_cannot_self_attest(direct_vm, direct_deploy, direct_bob, direct_owner):
    """The admin gets no automatic issuer trust -- unlike authorize_filer,
    where the deployer is auto-trusted, issuer trust is never implicit."""
    contract, pid, nid, aid = setup(direct_vm, direct_deploy, direct_bob)
    contract.resolve_assessment(aid)
    direct_vm.sender = direct_owner
    with direct_vm.expect_revert('sender not an authorized evidence issuer'):
        contract.submit_attestation(aid, EVIDENCE_SCOPE_EXCLUSION, VALID_COMMITMENT, f'Unit {SERIAL} excluded.', '')


def test_product_owner_cannot_attest_own_case_even_if_authorized_as_issuer(direct_vm, direct_deploy, direct_bob, direct_owner):
    """No bypass through the product owner: even if the admin mistakenly (or
    maliciously) authorizes the owner as an issuer, self-attestation is still
    refused at submission time."""
    contract, pid, nid, aid = setup(direct_vm, direct_deploy, direct_bob)
    contract.resolve_assessment(aid)
    as_admin_authorize_issuer(contract, direct_vm, direct_owner, direct_bob)
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert('issuer must be independent of the product owner'):
        contract.submit_attestation(aid, EVIDENCE_SCOPE_EXCLUSION, VALID_COMMITMENT, f'Unit {SERIAL} excluded.', '')


def test_invented_hash_rejected_as_malformed_commitment(direct_vm, direct_deploy, direct_bob, direct_charlie, direct_owner):
    """A claimant -- or even an authorized issuer -- cannot substitute a
    made-up string for the required canonical sha256:<64-hex> commitment."""
    contract, pid, nid, aid = setup(direct_vm, direct_deploy, direct_bob)
    contract.resolve_assessment(aid)
    as_admin_authorize_issuer(contract, direct_vm, direct_owner, direct_charlie)
    direct_vm.sender = direct_charlie
    with direct_vm.expect_revert('evidence commitment must be sha256:<64-hex>'):
        contract.submit_attestation(aid, EVIDENCE_SCOPE_EXCLUSION, 'i-made-this-up', f'Unit {SERIAL} excluded.', '')


def test_attestation_bound_to_one_case_cannot_clear_a_different_case(
        direct_vm, direct_deploy, direct_bob, direct_charlie, direct_alice, direct_owner):
    """Wrong-unit / wrong-notice evidence: an attestation is captured against
    one specific assessment_id at submission time. An otherwise-valid
    attestation for case 1 is structurally inapplicable to case 2, regardless
    of how similar the claimed facts look."""
    mock_happy_source(direct_vm)
    direct_vm.mock_llm(SCOPE_PATTERN, AFFECTED)
    contract = deploy_and_authorize(direct_deploy, direct_vm, direct_bob)
    pid1 = contract.register_product('Example Co', 'BAT-1', 'B1', 'SERIAL-AAA', '2026-01', 'h1')
    nid = file_and_verify(contract, direct_vm)
    aid1 = contract.open_assessment(pid1, nid)
    contract.resolve_assessment(aid1)
    assert contract.get_assessment(aid1)['status'] == 1

    direct_vm.sender = direct_charlie
    pid2 = contract.register_product('Example Co', 'BAT-1', 'B1', 'SERIAL-BBB', '2026-01', 'h2')
    aid2 = contract.open_assessment(pid2, nid)
    contract.resolve_assessment(aid2)
    assert contract.get_assessment(aid2)['status'] == 1

    as_admin_authorize_issuer(contract, direct_vm, direct_owner, direct_alice)
    direct_vm.sender = direct_bob
    appeal1 = contract.appeal_assessment(aid1, 'Serial number SERIAL-AAA is outside the recalled batch', 'h')
    submit_attestation(contract, direct_vm, direct_alice, aid1, EVIDENCE_SCOPE_EXCLUSION,
                        'Factory QA log confirms unit SERIAL-AAA is a pre-production test lot.')

    direct_vm.sender = direct_charlie
    appeal2 = contract.appeal_assessment(aid2, 'Serial number SERIAL-BBB is outside the recalled batch', 'h')

    direct_vm.clear_mocks()
    mock_happy_source(direct_vm)
    direct_vm.mock_llm(SCOPE_PATTERN, NOT_AFFECTED)
    contract.resolve_appeal(appeal2)
    assert contract.get_assessment(aid2)['status'] == 3  # case 1's attestation cannot clear case 2

    contract.resolve_appeal(appeal1)
    assert contract.get_assessment(aid1)['status'] == 2  # its own matching attestation does clear it


def test_tampered_evidence_source_fails_independent_check(direct_vm, direct_deploy, direct_bob, direct_charlie, direct_owner):
    """Modified/tampered evidence: an issuer cites a real, reachable public
    source, but what it actually says doesn't support the claimed facts --
    the independent fetch-and-compare must catch this, not just trust the
    issuer's description."""
    contract, pid, nid, aid = setup(direct_vm, direct_deploy, direct_bob)
    contract.resolve_assessment(aid)
    direct_vm.sender = direct_bob
    appeal_id = contract.appeal_assessment(aid, f'Serial number {SERIAL} is outside the recalled batch', 'h')

    as_admin_authorize_issuer(contract, direct_vm, direct_owner, direct_charlie)
    direct_vm.mock_web(r'manufacturer\.example', {'status': 200, 'body': 'Unrelated maintenance notice; no mention of this unit.'})
    direct_vm.mock_llm(EVIDENCE_PATTERN, MISMATCH)
    direct_vm.sender = direct_charlie
    contract.submit_attestation(aid, EVIDENCE_SCOPE_EXCLUSION, VALID_COMMITMENT,
                                 f'Manufacturer confirms unit {SERIAL} is excluded', 'https://manufacturer.example/records/1')
    att = contract.get_attestation(1)
    assert att['source_checked'] is True
    assert att['source_match'] is False

    direct_vm.clear_mocks()
    direct_vm.sender = direct_bob
    contract.resolve_appeal(appeal_id)
    assert contract.get_assessment(aid)['status'] == 3  # failed source check invalidates the attestation


def test_source_fetch_failure_invalidates_attestation(direct_vm, direct_deploy, direct_bob, direct_charlie, direct_owner):
    contract, pid, nid, aid = setup(direct_vm, direct_deploy, direct_bob)
    contract.resolve_assessment(aid)
    direct_vm.sender = direct_bob
    appeal_id = contract.appeal_assessment(aid, f'Serial number {SERIAL} is outside the recalled batch', 'h')

    as_admin_authorize_issuer(contract, direct_vm, direct_owner, direct_charlie)
    direct_vm.strict_mocks = False  # no web mock registered -> fetch fails
    direct_vm.sender = direct_charlie
    contract.submit_attestation(aid, EVIDENCE_SCOPE_EXCLUSION, VALID_COMMITMENT,
                                 f'Manufacturer confirms unit {SERIAL} is excluded', 'https://manufacturer.example/records/1')
    att = contract.get_attestation(1)
    assert att['source_checked'] is True
    assert att['source_match'] is False

    direct_vm.clear_mocks()
    direct_vm.sender = direct_bob
    contract.resolve_appeal(appeal_id)
    assert contract.get_assessment(aid)['status'] == 3


def test_duplicate_active_attestation_for_same_case_rejected(direct_vm, direct_deploy, direct_bob, direct_charlie, direct_owner):
    contract, pid, nid, aid = setup(direct_vm, direct_deploy, direct_bob)
    contract.resolve_assessment(aid)
    as_admin_authorize_issuer(contract, direct_vm, direct_owner, direct_charlie)
    submit_attestation(contract, direct_vm, direct_charlie, aid, EVIDENCE_SCOPE_EXCLUSION,
                        f'Unit {SERIAL} excluded per factory records.')
    with direct_vm.expect_revert('an active attestation of this type already exists for this case'):
        submit_attestation(contract, direct_vm, direct_charlie, aid, EVIDENCE_SCOPE_EXCLUSION,
                            f'Unit {SERIAL} excluded again, replayed.')


def test_revoked_attestation_cannot_clear(direct_vm, direct_deploy, direct_bob, direct_charlie, direct_owner):
    contract, pid, nid, aid = setup(direct_vm, direct_deploy, direct_bob)
    contract.resolve_assessment(aid)
    direct_vm.sender = direct_bob
    appeal_id = contract.appeal_assessment(aid, f'Serial number {SERIAL} is outside the recalled batch', 'h')

    as_admin_authorize_issuer(contract, direct_vm, direct_owner, direct_charlie)
    att_id = submit_attestation(contract, direct_vm, direct_charlie, aid, EVIDENCE_SCOPE_EXCLUSION,
                                 f'Unit {SERIAL} excluded per factory records.')
    direct_vm.sender = direct_charlie
    contract.revoke_attestation(att_id)
    assert contract.get_attestation(att_id)['status'] == 2  # ATT_REVOKED

    direct_vm.clear_mocks()
    mock_happy_source(direct_vm)
    direct_vm.mock_llm(SCOPE_PATTERN, NOT_AFFECTED)
    direct_vm.sender = direct_bob
    contract.resolve_appeal(appeal_id)
    assert contract.get_assessment(aid)['status'] == 3


def test_stale_attestation_after_generation_change_cannot_clear(direct_vm, direct_deploy, direct_bob, direct_charlie, direct_owner):
    """Expiry is modeled by assessment generation rather than wall-clock time
    (GenVM gives no reliable shared clock for this): once the assessment's
    generation moves on, an attestation captured at the old generation is
    stale and must not be reusable, even though nothing about it was revoked."""
    contract, pid, nid, aid = setup(direct_vm, direct_deploy, direct_bob)
    contract.resolve_assessment(aid)
    direct_vm.sender = direct_bob
    remedy_id = contract.request_remedy(aid, f'Unit {SERIAL} repaired.', 'h')

    as_admin_authorize_issuer(contract, direct_vm, direct_owner, direct_charlie)
    att_id = submit_attestation(contract, direct_vm, direct_charlie, aid, EVIDENCE_REMEDY_COMPLETED,
                                 f'Repair provider confirms unit {SERIAL} replacement completed.')
    assert contract.get_attestation(att_id)['assessment_generation'] == 1

    direct_vm.sender = direct_bob
    appeal_id = contract.appeal_assessment(aid, f'Serial number {SERIAL} appeal text', 'h')
    direct_vm.clear_mocks()
    mock_happy_source(direct_vm)
    direct_vm.mock_llm(SCOPE_PATTERN, AFFECTED)
    contract.resolve_appeal(appeal_id)  # no matching scope attestation; still bumps generation
    assert contract.get_assessment(aid)['generation'] == 2

    direct_vm.clear_mocks()
    mock_happy_source(direct_vm)
    direct_vm.mock_llm(SCOPE_PATTERN, NOT_AFFECTED)
    contract.resolve_remedy(remedy_id)
    assert contract.get_assessment(aid)['status'] == 3  # stale (generation 1) attestation rejected, not REMEDIATED


def test_leader_tampering_in_attested_remedy_detected_by_validator(direct_vm, direct_deploy, direct_bob, direct_charlie, direct_owner):
    contract, pid, nid, aid = setup(direct_vm, direct_deploy, direct_bob)
    contract.resolve_assessment(aid)
    direct_vm.sender = direct_bob
    remedy_id = contract.request_remedy(aid, f'Unit {SERIAL} repaired.', 'h')
    as_admin_authorize_issuer(contract, direct_vm, direct_owner, direct_charlie)
    submit_attestation(contract, direct_vm, direct_charlie, aid, EVIDENCE_REMEDY_COMPLETED,
                        f'Repair provider confirms unit {SERIAL} replacement completed.')

    direct_vm.clear_mocks()
    mock_happy_source(direct_vm)
    direct_vm.mock_llm(SCOPE_PATTERN, NOT_AFFECTED)
    direct_vm.sender = direct_bob
    contract.resolve_remedy(remedy_id)
    assert contract.get_assessment(aid)['status'] == 5  # REMEDIATED

    # Even with a valid attestation, a leader's favorable outcome must still
    # agree with an independent validator re-execution.
    direct_vm.clear_mocks()
    mock_happy_source(direct_vm)
    direct_vm.mock_llm(SCOPE_PATTERN, AFFECTED)
    assert direct_vm.run_validator() is False


def test_release_blocked_throughout_unresolved_attested_case(direct_vm, direct_deploy, direct_bob, direct_charlie, direct_owner):
    """Single-contract equivalent of 'ReleaseGuard remains blocked throughout
    unresolved cases' -- cross-contract wiring itself is demonstrated live on
    StudioNet (see docs/LIVE_PROOFS.md section D), since Direct Mode deploys
    one contract at a time."""
    contract, pid, nid, aid = setup(direct_vm, direct_deploy, direct_bob)
    assert contract.can_release(pid) is False  # pending
    contract.resolve_assessment(aid)
    assert contract.can_release(pid) is False  # AFFECTED
    direct_vm.sender = direct_bob
    remedy_id = contract.request_remedy(aid, f'Unit {SERIAL} repaired.', 'h')
    assert contract.can_release(pid) is False  # remedy open, unresolved

    as_admin_authorize_issuer(contract, direct_vm, direct_owner, direct_charlie)
    submit_attestation(contract, direct_vm, direct_charlie, aid, EVIDENCE_REMEDY_COMPLETED,
                        f'Repair provider confirms unit {SERIAL} replacement completed.')
    assert contract.can_release(pid) is False  # attestation alone, unresolved, still blocked

    direct_vm.clear_mocks()
    mock_happy_source(direct_vm)
    direct_vm.mock_llm(SCOPE_PATTERN, NOT_AFFECTED)
    direct_vm.sender = direct_bob
    contract.resolve_remedy(remedy_id)
    assert contract.can_release(pid) is True  # only now: attestation + validator agreement


# --- revocation stays effective both before and after resolution -----------

def test_issuer_revocation_before_resolution_blocks_clearance(direct_vm, direct_deploy, direct_bob, direct_charlie, direct_owner):
    """If the issuer is revoked after submitting an attestation but before
    anyone calls resolve_remedy, _current_valid_attestation must re-check
    CURRENT authorization, not whatever was true at submission time."""
    contract, pid, nid, aid = setup(direct_vm, direct_deploy, direct_bob)
    contract.resolve_assessment(aid)
    direct_vm.sender = direct_bob
    remedy_id = contract.request_remedy(aid, f'Unit {SERIAL} repaired.', 'h')

    as_admin_authorize_issuer(contract, direct_vm, direct_owner, direct_charlie)
    submit_attestation(contract, direct_vm, direct_charlie, aid, EVIDENCE_REMEDY_COMPLETED,
                        f'Repair provider confirms unit {SERIAL} replacement completed.')

    direct_vm.sender = direct_owner
    contract.revoke_issuer(direct_charlie)
    assert contract.is_authorized_issuer(direct_charlie) is False

    direct_vm.clear_mocks()
    mock_happy_source(direct_vm)
    direct_vm.mock_llm(SCOPE_PATTERN, NOT_AFFECTED)
    direct_vm.sender = direct_bob
    contract.resolve_remedy(remedy_id)
    assert contract.get_assessment(aid)['status'] == 3  # UNCERTAIN, not REMEDIATED
    assert contract.can_release(pid) is False


def test_attestation_revocation_after_clearance_fails_the_gate_closed_again(
        direct_vm, direct_deploy, direct_bob, direct_charlie, direct_owner):
    """Revocation must remain effective AFTER a clearance already happened:
    can_release re-checks the clearing attestation on every call, not just
    once at resolution time."""
    contract, pid, nid, aid = setup(direct_vm, direct_deploy, direct_bob)
    contract.resolve_assessment(aid)
    direct_vm.sender = direct_bob
    remedy_id = contract.request_remedy(aid, f'Unit {SERIAL} repaired.', 'h')
    as_admin_authorize_issuer(contract, direct_vm, direct_owner, direct_charlie)
    att_id = submit_attestation(contract, direct_vm, direct_charlie, aid, EVIDENCE_REMEDY_COMPLETED,
                                 f'Repair provider confirms unit {SERIAL} replacement completed.')

    direct_vm.clear_mocks()
    mock_happy_source(direct_vm)
    direct_vm.mock_llm(SCOPE_PATTERN, NOT_AFFECTED)
    direct_vm.sender = direct_bob
    contract.resolve_remedy(remedy_id)
    assert contract.get_assessment(aid)['status'] == 5  # REMEDIATED
    assert contract.get_assessment(aid)['clearing_attestation_id'] == att_id
    assert contract.can_release(pid) is True

    direct_vm.sender = direct_charlie  # the issuer may revoke their own attestation
    contract.revoke_attestation(att_id)
    assert contract.can_release(pid) is False  # fails closed immediately, with no re-resolution


def test_issuer_revocation_after_clearance_fails_the_gate_closed_again(
        direct_vm, direct_deploy, direct_bob, direct_charlie, direct_owner):
    """Same as above, but the admin revokes the issuer's whole registry
    entry rather than one specific attestation."""
    contract, pid, nid, aid = setup(direct_vm, direct_deploy, direct_bob)
    contract.resolve_assessment(aid)
    direct_vm.sender = direct_bob
    remedy_id = contract.request_remedy(aid, f'Unit {SERIAL} repaired.', 'h')
    as_admin_authorize_issuer(contract, direct_vm, direct_owner, direct_charlie)
    submit_attestation(contract, direct_vm, direct_charlie, aid, EVIDENCE_REMEDY_COMPLETED,
                        f'Repair provider confirms unit {SERIAL} replacement completed.')

    direct_vm.clear_mocks()
    mock_happy_source(direct_vm)
    direct_vm.mock_llm(SCOPE_PATTERN, NOT_AFFECTED)
    direct_vm.sender = direct_bob
    contract.resolve_remedy(remedy_id)
    assert contract.can_release(pid) is True

    direct_vm.sender = direct_owner
    contract.revoke_issuer(direct_charlie)
    assert contract.can_release(pid) is False  # the issuer's disauthorization alone is enough


def test_ordinary_not_affected_assessment_is_unaffected_by_issuer_revocation(
        direct_vm, direct_deploy, direct_bob, direct_charlie, direct_owner):
    """An initial resolve_assessment NOT_AFFECTED never depended on any
    attestation (clearing_attestation_id stays 0) and must keep clearing the
    gate even after an unrelated issuer is revoked elsewhere."""
    mock_happy_source(direct_vm)
    direct_vm.mock_llm(SCOPE_PATTERN, NOT_AFFECTED)
    contract = deploy_and_authorize(direct_deploy, direct_vm, direct_bob)
    pid = contract.register_product('Example Co', 'BAT-2', 'B9', 'SERIAL-002', '2026-02', 'hash-2')
    nid = file_and_verify(contract, direct_vm)
    aid = contract.open_assessment(pid, nid)
    contract.resolve_assessment(aid)
    assert contract.get_assessment(aid)['status'] == 2  # NOT_AFFECTED
    assert contract.get_assessment(aid)['clearing_attestation_id'] == 0
    assert contract.can_release(pid) is True

    as_admin_authorize_issuer(contract, direct_vm, direct_owner, direct_charlie)
    direct_vm.sender = direct_owner
    contract.revoke_issuer(direct_charlie)  # unrelated to this assessment entirely
    assert contract.can_release(pid) is True  # still cleared; never depended on any attestation
