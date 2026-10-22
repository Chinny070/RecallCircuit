"""Source-level honesty checks: no faked verification, real consensus wiring."""
from pathlib import Path

CORE = Path(__file__).resolve().parents[1] / 'contracts' / 'recall_circuit.py'


def test_independent_consensus_and_fail_closed_wiring_present():
    s = CORE.read_text()
    for fragment in ('gl.nondet.exec_prompt', 'gl.vm.run_nondet_unsafe', 'verdict_shape',
                      'can_release', 'dependency cycle', 'appeal_assessment', 'resolve_remedy',
                      'gl.nondet.web.render', 'AUTHORIZED_SOURCE_PREFIXES', 'verify_source_notice',
                      'match_shape', 'notice not source-verified', 'authorize_filer',
                      'sender not an authorized filer', 'notice already verified',
                      'assessment already exists', 'evidence must reference the unit serial number',
                      'authorize_issuer', 'submit_attestation', 'sender not an authorized evidence issuer',
                      'issuer must be independent of the product owner', 'canonical_commitment',
                      'No valid independent scope-exclusion attestation',
                      'No valid independent remedy-completion attestation',
                      'clearing_attestation_id', '_clearing_attestation_still_valid',
                      '_is_authorized_issuer(att.issuer)'):
        assert fragment in s


def test_no_mocked_network_or_false_authenticity_claim():
    s = CORE.read_text()
    assert 'requests.get' not in s
    assert 'source verified' not in s.lower()
    assert 'source is authentic' not in s.lower()  # never asserted as fact in-contract


def test_claimant_text_never_feeds_the_clearance_evaluator():
    """resolve_appeal/resolve_remedy must evaluate the issuer-attested
    evidence_description, never the appellant/applicant's own record.evidence
    or obj.evidence -- a claimant's free text must never reach the clearance
    judgment call, no matter how convincing it reads."""
    s = CORE.read_text()
    assert "str(record.evidence)" not in s
    assert "str(obj.evidence)" not in s
    assert "str(att.evidence_description)" in s
