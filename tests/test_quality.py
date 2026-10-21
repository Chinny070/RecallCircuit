"""Source-level honesty checks: no faked verification, real consensus wiring."""
from pathlib import Path

CORE = Path(__file__).resolve().parents[1] / 'contracts' / 'recall_circuit.py'


def test_independent_consensus_and_fail_closed_wiring_present():
    s = CORE.read_text()
    for fragment in ('gl.nondet.exec_prompt', 'gl.vm.run_nondet_unsafe', 'verdict_shape',
                      'can_release', 'dependency cycle', 'appeal_assessment', 'resolve_remedy',
                      'gl.nondet.web.render', 'AUTHORIZED_SOURCE_PREFIXES', 'verify_source_notice',
                      'match_shape', 'notice not source-verified'):
        assert fragment in s


def test_no_mocked_network_or_false_authenticity_claim():
    s = CORE.read_text()
    assert 'requests.get' not in s
    assert 'source verified' not in s.lower()
    assert 'source is authentic' not in s.lower()  # never asserted as fact in-contract
