import json
import sqlite3
import pytest
from pathlib import Path
from corkjobradar.config import now
from corkjobradar.db import Database
from corkjobradar.autoapply.policy import event
from corkjobradar.autoapply.trials import create_trial_plan,authorize_trial,execute_trial,autonomous_cycle,TRIAL_CONSENT
from corkjobradar.autoapply.receipts import lever_receipt,retain_receipt_evidence
from test_autoapply_policy import stored_job
from test_autoapply_pipeline import setup_attempt

POSTING='11111111-2222-3333-4444-555555555555'
ENDPOINT='https://api.lever.co/v0/postings/synthetic/'+POSTING


def test_trial_draft_neither_authorizes_nor_sends_and_stale_review_is_rejected(db,profile):
    job=stored_job(db,profile)
    draft=create_trial_plan(db,job['id'])
    assert not draft['authorized'] and not draft['readiness']['ready']
    assert not db.rows('SELECT * FROM autoapply_trial_consents')
    with pytest.raises(ValueError,match='SPECIFIC'):authorize_trial(db,draft['trial_id'],draft['snapshot_hash'],'')
    with pytest.raises(PermissionError,match='NOT_READY'):authorize_trial(db,draft['trial_id'],draft['snapshot_hash'],TRIAL_CONSENT)
    db.execute("UPDATE jobs SET content_hash='changed' WHERE id=?",(job['id'],))
    with pytest.raises(ValueError,match='PACKAGE_CHANGED'):authorize_trial(db,draft['trial_id'],draft['snapshot_hash'],TRIAL_CONSENT)
    with pytest.raises(PermissionError,match='SPECIFIC'):execute_trial(db,draft['trial_id'])
    with pytest.raises(PermissionError,match='LIVE_LOCKED'):autonomous_cycle(db,live=True)
    assert not db.rows('SELECT * FROM application_attempts')


def test_trial_consent_is_single_use_version_bound_and_does_not_activate_live(db,profile,monkeypatch):
    import corkjobradar.autoapply.trials as trials
    job=stored_job(db,profile);draft=create_trial_plan(db,job['id'])
    monkeypatch.setattr(trials,'trial_readiness',lambda *args,**kwargs:{'ready':True})  # synthetic preconditions only
    cid=authorize_trial(db,draft['trial_id'],draft['snapshot_hash'],TRIAL_CONSENT)
    assert authorize_trial(db,draft['trial_id'],draft['snapshot_hash'],TRIAL_CONSENT)==cid
    assert db.rows('SELECT max_submissions FROM autoapply_trial_consents')[0]['max_submissions']==1
    with pytest.raises(sqlite3.IntegrityError):db.execute('UPDATE autoapply_trial_consents SET max_submissions=2')
    with pytest.raises(PermissionError,match='TRANSPORT_NOT_RELEASED'):execute_trial(db,draft['trial_id'])
    assert db.rows('SELECT live_enabled FROM autoapply_control')[0]['live_enabled']==0


@pytest.mark.parametrize('status,body,started,expected,response',[
    (200,{},True,POSTING,ENDPOINT),(200,{'ok':True},True,POSTING,ENDPOINT),
    (200,{'ok':True,'applicationId':'SYNTHETIC-123'},False,POSTING,ENDPOINT),
    (200,{'ok':True,'applicationId':'SYNTHETIC-123'},True,'wrong',ENDPOINT),
    (200,{'ok':True,'applicationId':'SYNTHETIC-123'},True,POSTING,'https://evil.invalid'),
    (429,{'ok':True,'applicationId':'SYNTHETIC-123'},True,POSTING,ENDPOINT),
    (200,{'ok':1,'applicationId':'SYNTHETIC-123'},True,POSTING,ENDPOINT),
])
def test_http_success_without_bound_explicit_receipt_does_not_confirm(status,body,started,expected,response):
    assert lever_receipt(status,body,ENDPOINT,response,expected,started) is None


def test_documented_lever_receipt_is_correlated_and_simulation_never_writes_real_history(db,profile):
    payload={'ok':True,'applicationId':'SYNTHETIC-123'}
    assert lever_receipt(200,payload,ENDPOINT,ENDPOINT,POSTING,True)['reference']=='SYNTHETIC-123'
    aid,job=setup_attempt(db,profile)
    with pytest.raises(PermissionError,match='DISPATCH'):retain_receipt_evidence(db,aid,200,payload,ENDPOINT,ENDPOINT,POSTING)
    event(db,'TRANSPORT_DISPATCHED',{'request_url':ENDPOINT,'posting_id':POSTING,'method':'POST'},attempt_id=aid)
    result=retain_receipt_evidence(db,aid,200,payload,ENDPOINT,ENDPOINT,POSTING)
    assert result['status']=='SIMULATION_RECEIPT' and not result['confirms_live_application'] and not result['automatic_retry_allowed']
    retain_receipt_evidence(db,aid,200,payload,ENDPOINT,ENDPOINT,POSTING)
    assert len(db.rows('SELECT * FROM application_receipt_evidence'))==1
    assert not db.rows('SELECT * FROM user_actions')
    path=Path(db.rows('SELECT encrypted_path FROM application_receipt_evidence')[0]['encrypted_path'])
    assert b'SYNTHETIC-123' not in path.read_bytes()


def test_api_key_is_not_retained_in_receipt_metadata(db,profile):
    from corkjobradar.autoapply.receipts import safe_endpoint
    payload={'ok':True,'applicationId':'SYNTHETIC-KEY-SAFE'}
    secret_url=ENDPOINT+'?key=SYNTHETIC_SECRET'
    assert safe_endpoint(secret_url)==ENDPOINT
    assert lever_receipt(200,payload,secret_url,secret_url,POSTING,True)['request_url']==ENDPOINT
    aid,job=setup_attempt(db,profile)
    event(db,'TRANSPORT_DISPATCHED',{'request_url':ENDPOINT,'posting_id':POSTING,'method':'POST'},attempt_id=aid)
    result=retain_receipt_evidence(db,aid,200,payload,secret_url,secret_url,POSTING)
    assert 'SYNTHETIC_SECRET' not in json.dumps(result)
    assert 'SYNTHETIC_SECRET' not in json.dumps(db.rows('SELECT * FROM application_events'))


def test_live_receipt_registry_is_release_locked_even_with_a_forged_sending_state(db,profile):
    aid,job=setup_attempt(db,profile)
    db.execute("UPDATE application_plans SET environment='LIVE'")
    db.execute("UPDATE application_attempts SET state='ENVIANDO' WHERE id=?",(aid,))
    with pytest.raises(PermissionError,match='LIVE_LOCKED'):
        retain_receipt_evidence(db,aid,200,{'ok':True,'applicationId':'SYNTHETIC-123'},ENDPOINT,ENDPOINT,POSTING)
    assert not db.rows('SELECT * FROM user_actions') and not db.rows('SELECT * FROM application_receipt_evidence')


def test_get_response_cannot_be_used_as_a_submission_receipt(db,profile):
    aid,job=setup_attempt(db,profile)
    event(db,'TRANSPORT_DISPATCHED',{'request_url':ENDPOINT,'posting_id':POSTING,'method':'GET'},attempt_id=aid)
    with pytest.raises(PermissionError,match='DISPATCH'):
        retain_receipt_evidence(db,aid,200,{'ok':True,'applicationId':'SYNTHETIC-123'},ENDPOINT,ENDPOINT,POSTING)
    assert not db.rows('SELECT * FROM application_receipt_evidence') and not db.rows('SELECT * FROM user_actions')


@pytest.mark.parametrize('body,expected_state,actions',[
    ({'ok':True,'applicationId':'SYNTHETIC-RECEIVED'},'ENVIADA_CONFIRMADA',1),
    ({'ok':True},'ENVIO_INCIERTO',0),
])
def test_future_receipt_path_on_isolated_synthetic_dispatch_only(db,profile,monkeypatch,body,expected_state,actions):
    # No HTTP requests. This tests the gated registry, not a real application or released adapter.
    import corkjobradar.autoapply.receipts as receipts
    import corkjobradar.autoapply.store as store
    import corkjobradar.autoapply.platforms as platforms
    aid,job=setup_attempt(db,profile)
    db.execute("UPDATE application_plans SET environment='LIVE'")
    db.execute("UPDATE application_attempts SET state='ENVIANDO',target_url=? WHERE id=?",('https://jobs.lever.co/synthetic/'+POSTING,aid))
    monkeypatch.setattr(receipts,'require_live',lambda db:None)
    monkeypatch.setattr(store,'require_live',lambda db:None)
    monkeypatch.setattr(platforms,'platform_for',lambda url:{'id':'lever','live_supported':True,'automation_permitted':True})
    event(db,'TRANSPORT_DISPATCHED',{'request_url':ENDPOINT,'posting_id':POSTING,'method':'POST'},attempt_id=aid)
    result=retain_receipt_evidence(db,aid,200,body,ENDPOINT,ENDPOINT,POSTING)
    assert db.rows('SELECT state FROM application_attempts')[0]['state']==expected_state
    assert len(db.rows('SELECT * FROM user_actions'))==actions
    if actions:
        retain_receipt_evidence(db,aid,200,body,ENDPOINT,ENDPOINT,POSTING)
        assert len(db.rows('SELECT * FROM user_actions'))==1
    assert not result['automatic_retry_allowed']


def test_additive_v5_to_current_migration_preserves_existing_facts_and_keeps_off(db):
    from test_autoapply_vault import populate
    populate(db)
    before=db.rows('SELECT * FROM candidate_facts')
    # Represent v5 by removing newer empty tables, only in this isolated fixture.
    with db.connect() as con:
        for name in ('manual_application_evidence_reviews','manual_application_evidence','autoapply_intervention_commands','autoapply_interventions','manual_application_declarations','manual_application_handoffs','autoapply_trial_consents','autoapply_trial_plans','application_receipt_evidence','autoapply_form_inspections'):
            con.execute('DROP TABLE '+name)
        con.execute('PRAGMA user_version=5')
    reopened=Database(db.path)
    assert reopened.rows('PRAGMA user_version')[0]['user_version']==12
    assert reopened.rows('SELECT * FROM candidate_facts')==before
    assert reopened.rows('SELECT live_enabled,enabled FROM autoapply_control')[0]=={'live_enabled':0,'enabled':0}
