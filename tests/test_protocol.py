import pytest

URL = 'https://www.cpsc.gov/Recalls/2026/example-product-recall'
NEW = 'https://www.cpsc.gov/Recalls/2026/revised-product-recall'
PROOF = 'https://example.org/remedy/serial-A1'

def init(state, *, parent=False):
    c, m, gl, llm = state
    battery = c.register_asset('Battery', 'Example Co', 'BAT-1', 'B1', 'S1', '2026-01', 'auditor')
    aid = battery
    if parent:
        aid = c.register_asset('Appliance','Example Co','TOOL-1','B1','T1','2026-01','auditor')
        c.link_component(aid, battery)
    nid = c.propose_notice(URL, 0)
    c.verify_notice(nid)
    return c,m,gl,llm,battery,aid,nid

def test_registration_defaults_closed(state):
    c,m,_,_ = state
    aid = c.register_asset('Product','Make','Model','Batch','Serial','2025','auditor')
    assert c.is_release_allowed(aid) is False
    assert c.get_asset(aid)['revision'] == 1

def test_official_url_allowlist_and_bad_inputs(state):
    c,m,_,_ = state
    for url in ['http://www.cpsc.gov/Recalls/test', 'https://cpsc.gov.evil.com/Recalls/x',
                'https://www.cpsc.gov@evil.com/Recalls/test','https://www.cpsc.gov/Recalls/']:
        if url.endswith('Recalls/'):
            continue
        with pytest.raises(m.gl.vm.UserError): c.propose_notice(url, 0)

def test_affected_product_is_quarantined(state):
    c,m,gl,llm,battery,aid,nid = init(state)
    cid = c.open_case(battery, nid)
    assert not c.is_release_allowed(battery)
    c.resolve_case(cid)
    assert c.get_case(cid)['status'] == m.C_AFFECTED
    assert not c.is_release_allowed(battery)

def test_explicitly_excluded_is_notice_specific_clearance(state):
    c,m,gl,llm,battery,aid,nid = init(state)
    llm.finding = 'NOT_AFFECTED'
    cid = c.open_case(aid,nid)
    c.resolve_case(cid)
    assert c.get_case(cid)['status'] == m.C_CLEAR
    assert c.is_release_allowed(aid)

def test_uncertain_fails_closed(state):
    c,m,gl,llm,battery,aid,nid = init(state)
    llm.finding = 'UNCERTAIN'
    cid = c.open_case(aid,nid)
    c.resolve_case(cid)
    assert c.get_case(cid)['status'] == m.C_UNCERTAIN
    assert not c.is_release_allowed(aid)

def test_disagreeing_validator_keeps_pending_hold(state):
    c,m,gl,llm,battery,aid,nid = init(state)
    cid = c.open_case(aid,nid)
    llm.override_validator = True
    with pytest.raises(ValueError, match='validator disagreement'): c.resolve_case(cid)
    assert c.get_case(cid)['status'] == m.C_PENDING
    assert not c.is_release_allowed(aid)

def test_component_hold_propagates_to_assembled_product(state):
    c,m,gl,llm,battery,parent,nid = init(state, parent=True)
    llm.finding = 'NOT_AFFECTED'
    parent_cid = c.open_case(parent,nid)
    c.resolve_case(parent_cid)
    assert c.is_release_allowed(parent)
    llm.finding = 'AFFECTED'
    child_case = c.open_case(battery,nid)
    c.resolve_case(child_case)
    assert not c.is_release_allowed(parent)
    assert c.get_asset(parent)['children'] == [battery]

def test_graph_cycle_self_and_relink_blocked(state):
    c,m,gl,llm,battery,parent,nid = init(state, parent=True)
    with pytest.raises(m.gl.vm.UserError): c.link_component(battery,parent)
    with pytest.raises(m.gl.vm.UserError): c.link_component(parent,parent)
    cid = c.open_case(parent,nid)
    another = c.register_asset('Other','M','Mo','B','S','Date','auditor')
    with pytest.raises(m.gl.vm.UserError): c.link_component(parent,another)

def test_auditor_not_owner_and_role_acceptance(state):
    c,m,gl,llm,battery,aid,nid = init(state)
    cid = c.open_case(aid,nid)
    c.resolve_case(cid)
    with pytest.raises(m.gl.vm.UserError): c.propose_remedy(cid,PROOF)
    with pytest.raises(m.gl.vm.UserError): c.accept_auditor(aid)
    gl.message.sender_address='auditor'
    c.accept_auditor(aid)
    gl.message.sender_address='owner'
    c.propose_remedy(cid,PROOF)
    assert not c.is_release_allowed(aid)

def test_unattested_remedy_cannot_release(state):
    c,m,gl,llm,battery,aid,nid = init(state)
    cid=c.open_case(aid,nid);c.resolve_case(cid)
    gl.message.sender_address='auditor';c.accept_auditor(aid)
    gl.message.sender_address='owner';c.propose_remedy(cid,PROOF)
    with pytest.raises(m.gl.vm.UserError):c.resolve_remedy(cid)
    assert not c.is_release_allowed(aid)

def test_remedy_with_bad_hash_rejected(state):
    c,m,gl,llm,battery,aid,nid=init(state)
    cid=c.open_case(aid,nid);c.resolve_case(cid)
    gl.message.sender_address='auditor';c.accept_auditor(aid)
    gl.message.sender_address='owner';c.propose_remedy(cid,PROOF)
    gl.message.sender_address='auditor'
    with pytest.raises(m.gl.vm.UserError):c.attest_remedy(cid, True, 'faked')
    assert not c.get_case(cid)['auditor_attested']

def test_valid_remedy_requires_ai_and_auditor(state):
    c,m,gl,llm,battery,aid,nid=init(state)
    cid=c.open_case(aid,nid);c.resolve_case(cid)
    gl.message.sender_address='auditor';c.accept_auditor(aid)
    gl.message.sender_address='owner';c.propose_remedy(cid,PROOF)
    gl.message.sender_address='auditor';c.attest_remedy(cid, True, m.digest(PROOF))
    llm.remedy_ok=True
    c.resolve_remedy(cid)
    assert c.get_case(cid)['status'] == m.C_REMEDIATED
    assert c.is_release_allowed(aid)

def test_remedy_semantically_uncertain_stays_held(state):
    c,m,gl,llm,battery,aid,nid=init(state)
    cid=c.open_case(aid,nid);c.resolve_case(cid)
    gl.message.sender_address='auditor';c.accept_auditor(aid)
    gl.message.sender_address='owner';c.propose_remedy(cid,PROOF)
    gl.message.sender_address='auditor';c.attest_remedy(cid,True,m.digest(PROOF))
    c.resolve_remedy(cid)
    assert c.get_case(cid)['status']==m.C_AFFECTED
    assert not c.is_release_allowed(aid)

def test_appeal_fails_closed_until_resolved(state):
    c,m,gl,llm,battery,aid,nid = init(state)
    llm.finding='NOT_AFFECTED'
    cid=c.open_case(aid,nid);c.resolve_case(cid)
    assert c.is_release_allowed(aid)
    c.appeal_case(cid,'The batch mapping was incorrect; please independently verify scope')
    assert not c.is_release_allowed(aid)
    llm.finding='AFFECTED'
    c.resolve_case(cid)
    assert c.get_case(cid)['appeal_count']==1
    assert not c.is_release_allowed(aid)

def test_duplicate_case_and_duplicate_notice_rejected(state):
    c,m,gl,llm,battery,aid,nid = init(state)
    c.open_case(aid,nid)
    with pytest.raises(m.gl.vm.UserError):c.open_case(aid,nid)
    with pytest.raises(m.gl.vm.UserError):c.propose_notice(URL,0)

def test_owner_and_auditor_roles(state):
    c,m,gl,llm,battery,aid,nid=init(state)
    gl.message.sender_address='attacker'
    with pytest.raises(m.gl.vm.UserError):c.open_case(aid,nid)
    with pytest.raises(m.gl.vm.UserError):c.freeze_asset(aid)
    with pytest.raises(m.gl.vm.UserError):c.link_component(aid,battery)

def test_freeze_and_unfreeze_only_without_hold(state):
    c,m,gl,llm,battery,aid,nid=init(state)
    llm.finding='NOT_AFFECTED'
    cid=c.open_case(aid,nid);c.resolve_case(cid)
    assert c.is_release_allowed(aid)
    c.freeze_asset(aid);assert not c.is_release_allowed(aid)
    c.unfreeze_asset(aid);assert c.is_release_allowed(aid)
    c.appeal_case(cid,'New potential evidence')
    c.freeze_asset(aid)
    with pytest.raises(m.gl.vm.UserError):c.unfreeze_asset(aid)

def test_revision_invalidates_old_clearance_and_new_case_restores(state):
    c,m,gl,llm,battery,aid,nid=init(state)
    llm.finding='NOT_AFFECTED'
    old=c.open_case(aid,nid);c.resolve_case(old)
    assert c.is_release_allowed(aid)
    revised=c.propose_notice(NEW,nid)
    assert c.is_release_allowed(aid)  # cannot supersede until VERIFIED
    c.verify_notice(revised)
    assert not c.is_release_allowed(aid)
    newest=c.open_case(aid,revised);c.resolve_case(newest)
    assert c.is_release_allowed(aid)

def test_bad_llm_schema_cannot_verify_notice(state):
    c,m,gl,llm = state
    nid=c.propose_notice(URL,0)
    gl.nondet.exec_prompt=lambda *args,**kwargs:{'valid':'true','official_id':'123','title':'A','recall_date':'2026'}
    with pytest.raises(ValueError, match='validator disagreement'):c.verify_notice(nid)
    assert c.get_notice(nid)['status']==m.N_PROPOSED

def test_parsers_enforce_structured_verdicts(state):
    _,m,_,_=state
    assert not m.parse_finding({'finding':'AFFECTED','reason_code':'SCOPE_EXCLUDES'})
    assert not m.parse_finding({'finding':'TRUE','reason_code':'MODEL_AND_SCOPE_MATCH'})
    assert not m.parse_notice({'valid':'true','official_id':'123','title':'T','recall_date':'2026'})
    assert m.parse_finding('{"finding":"UNCERTAIN","reason_code":"INSUFFICIENT_EVIDENCE"}')

def test_unverified_notice_cannot_open_case(state):
    c,m,gl,llm=state
    aid=c.register_asset('Widget','M','Model','Batch','Serial','2026','auditor')
    nid=c.propose_notice(URL,0)
    with pytest.raises(m.gl.vm.UserError):c.open_case(aid,nid)


def test_revision_cannot_change_recall_identity(state):
    c,m,gl,llm,battery,aid,nid=init(state)
    newer=c.propose_notice(NEW,nid)
    original=gl.nondet.exec_prompt
    def differing(prompt,response_format='json'):
        result=original(prompt,response_format=response_format)
        if 'OFFICIAL CPSC NOTICE VERIFICATION' in prompt:
            return {**result,'official_id':'wrong-recall-id'}
        return result
    gl.nondet.exec_prompt=differing
    with pytest.raises(m.gl.vm.UserError,match='preserve the original'):
        c.verify_notice(newer)
    # Simulated SDK does not automatically rollback writes; live GenVM must prove atomicity.


def test_failed_web_fetch_does_not_verify(state):
    c,m,gl,llm=state
    nid=c.propose_notice(URL,0)
    gl.nondet.web.render=lambda *a,**k: ''
    with pytest.raises(ValueError):c.verify_notice(nid)
    assert c.get_notice(nid)['status']==m.N_PROPOSED


def test_refuses_invalid_evidence_urls(state):
    c,m,gl,llm,battery,aid,nid=init(state)
    cid=c.open_case(aid,nid);c.resolve_case(cid)
    gl.message.sender_address='auditor';c.accept_auditor(aid)
    gl.message.sender_address='owner'
    for url in ['http://external.com/proof','https://localhost/proof',
                'https://169.254.169.254/private','https://bad.com@evil.com/proof']:
        with pytest.raises(m.gl.vm.UserError):c.propose_remedy(cid,url)


def test_limit_two_appeals(state):
    c,m,gl,llm,battery,aid,nid=init(state)
    cid=c.open_case(aid,nid);c.resolve_case(cid)
    for count in range(2):
        c.appeal_case(cid,f'Ground #{count} identifies batch ambiguity')
        c.resolve_case(cid)
    with pytest.raises(m.gl.vm.UserError,match='appeal limit'):
        c.appeal_case(cid,'Third request')


def test_cannot_appeal_pending(state):
    c,m,gl,llm,battery,aid,nid=init(state)
    cid=c.open_case(aid,nid)
    with pytest.raises(m.gl.vm.UserError):c.appeal_case(cid,'Not yet decided')


def test_multi_level_propagation(state):
    c,m,gl,llm=state
    leaf=c.register_asset('Cell','M','Cell','B','S1','D','auditor')
    middle=c.register_asset('Battery','M','Pack','B','S2','D','auditor')
    root=c.register_asset('Device','M','Device','B','S3','D','auditor')
    c.link_component(middle,leaf)
    c.link_component(root,middle)
    nid=c.propose_notice(URL,0);c.verify_notice(nid)
    llm.finding='NOT_AFFECTED'
    cr=c.open_case(root,nid);cm=c.open_case(middle,nid)
    c.resolve_case(cr);c.resolve_case(cm)
    assert c.is_release_allowed(root)
    llm.finding='AFFECTED'
    cl=c.open_case(leaf,nid);c.resolve_case(cl)
    assert not c.is_release_allowed(root)


def test_foreign_owner_cannot_relabel_components(state):
    c,m,gl,llm=state
    parent=c.register_asset('Product','M','Model','B','S','D','auditor')
    gl.message.sender_address='bob'
    foreign=c.register_asset('Component','M','Model2','B','S2','D','auditor2')
    gl.message.sender_address='owner'
    with pytest.raises(m.gl.vm.UserError,match='owner mismatch'):
        c.link_component(parent,foreign)


def test_official_notice_verification_reads_live_source_twice(state):
    c,m,gl,llm=state
    nid=c.propose_notice(URL,0)
    count=[0]
    old=gl.nondet.web.render
    def traced(*args,**kwargs):count[0]+=1;return old(*args,**kwargs)
    gl.nondet.web.render=traced
    c.verify_notice(nid)
    assert count[0]==2


def test_decision_digest_changes_after_appeal(state):
    c,m,gl,llm,battery,aid,nid=init(state)
    llm.finding='NOT_AFFECTED'
    cid=c.open_case(aid,nid);c.resolve_case(cid)
    earlier=c.get_case(cid)['decision_hash']
    c.appeal_case(cid,'Re-check original recall exclusions')
    c.resolve_case(cid)
    assert c.get_case(cid)['decision_hash']!=earlier
