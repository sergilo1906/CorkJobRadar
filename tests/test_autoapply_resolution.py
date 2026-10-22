import json
import pytest
from corkjobradar.autoapply.resolution import manual_resolution,retry_simulation_preparation
from corkjobradar.autoapply.store import transition,already_applied,quota_reason
from corkjobradar.autoapply.policy import current_policy,pause,event
from corkjobradar.autoapply.eligibility import Decision
from test_autoapply_pipeline import setup_attempt


def stamp(db,aid):
    return db.rows('SELECT updated_at FROM application_attempts WHERE id=?',(aid,))[0]['updated_at']


def test_manual_no_repeat_is_idempotent_and_keeps_deduplication(db,profile):
    aid,job=setup_attempt(db,profile)
    before=stamp(db,aid)
    with pytest.raises(ValueError):manual_resolution(db,aid,'NO_REPETIR',False,before)
    result=manual_resolution(db,aid,'NO_REPETIR',True,before)
    assert result['state']=='CANCELADA'
    manual_resolution(db,aid,'NO_REPETIR',True,stamp(db,aid))
    assert len(db.rows("SELECT id FROM application_events WHERE kind='MANUAL_NO_REPEAT'"))==1
    assert already_applied(db,job)
    assert len(db.rows('SELECT * FROM application_reservations'))==1
    with pytest.raises(PermissionError,match='RESOLUTION_FORBIDS'):retry_simulation_preparation(db,aid,True,stamp(db,aid))


def test_manual_resolution_never_manufactures_confirmation_or_releases_uncertainty(db,profile):
    aid,job=setup_attempt(db,profile)
    db.execute("UPDATE application_attempts SET state='ENVIO_INCIERTO' WHERE id=?",(aid,))
    result=manual_resolution(db,aid,'MARCAR_RESUELTA',True,stamp(db,aid))
    assert result['state']=='ENVIO_INCIERTO' and not result['external_confirmation_verified']
    assert already_applied(db,job) and not db.rows('SELECT * FROM user_actions')
    assert db.rows('SELECT confirmation_reference FROM application_attempts')[0]['confirmation_reference'] is None
    with pytest.raises(PermissionError):retry_simulation_preparation(db,aid,True,stamp(db,aid))


def test_retry_rejects_send_history_even_after_state_was_changed(db,profile):
    aid,job=setup_attempt(db,profile)
    transition(db,aid,'CANCELADA')
    event(db,'STATE_CHANGED',{},attempt_id=aid,before='ENVIANDO',after='ENVIO_INCIERTO')
    with pytest.raises(PermissionError,match='SEND_HISTORY'):retry_simulation_preparation(db,aid,True,stamp(db,aid))


def test_retry_prepares_same_attempt_and_reservation_without_network(db,profile,monkeypatch):
    import corkjobradar.autoapply.resolution as resolution
    aid,job=setup_attempt(db,profile)
    transition(db,aid,'CANCELADA')
    # Only the eligibility result is replaced in this isolated synthetic test;
    # documents, bindings, consent, transactions and prefinal checks remain real.
    calls=[]
    def allow(*args,**kwargs):
        calls.append(kwargs)
        return Decision('ALLOW',[],'synthetic-only',99)
    monkeypatch.setattr(resolution,'evaluate_autoapply',allow)
    result=retry_simulation_preparation(db,aid,True,stamp(db,aid))
    assert result['retry_prepared'] and result['state']=='REQUIERE_REVISION'
    assert result['public_forms_filled'] is False
    assert len(db.rows('SELECT * FROM application_attempts'))==1
    assert len(db.rows('SELECT * FROM application_reservations'))==1
    assert calls[0]['duplicate'] is False and calls[0]['quota_reason'] is None
    assert already_applied(db,job)
    assert not db.rows('SELECT * FROM user_actions')
    assert db.rows('PRAGMA foreign_key_check')==[]


def test_retry_recalculates_real_holds_and_rolls_back_on_invalid_cv(db,profile,monkeypatch):
    import corkjobradar.autoapply.resolution as resolution
    aid,job=setup_attempt(db,profile);transition(db,aid,'CANCELADA')
    result=retry_simulation_preparation(db,aid,True,stamp(db,aid))
    assert not result['retry_prepared'] and result['decision']['outcome']!='ALLOW'
    assert db.rows('SELECT state FROM application_attempts')[0]['state']=='CANCELADA'
    monkeypatch.setattr(resolution,'evaluate_autoapply',lambda *a,**kw:Decision('ALLOW',[],'fixture',99))
    def corrupt(*a,**kw):raise ValueError('SYNTHETIC_CORRUPT_CV')
    import corkjobradar.autoapply.documents as documents
    monkeypatch.setattr(documents,'document_bytes',corrupt)
    before=len(db.rows('SELECT id FROM application_events'))
    with pytest.raises(ValueError):retry_simulation_preparation(db,aid,True,stamp(db,aid))
    assert db.rows('SELECT state FROM application_attempts')[0]['state']=='CANCELADA'
    assert len(db.rows('SELECT id FROM application_events'))==before


def test_resolution_rejects_stale_ui_and_concurrent_worker(db,profile):
    from corkjobradar.worker import worker_lock
    aid,job=setup_attempt(db,profile)
    with pytest.raises(PermissionError,match='REFRESH_VIEW'):manual_resolution(db,aid,'NO_REPETIR',True,'old')
    with worker_lock(db),pytest.raises(OSError):manual_resolution(db,aid,'NO_REPETIR',True,stamp(db,aid))
    assert db.rows('SELECT state FROM application_attempts')[0]['state']=='APROBADA_POR_POLITICA'


def test_retry_cannot_bypass_pause_or_manual_applications(db,profile,monkeypatch):
    aid,job=setup_attempt(db,profile);transition(db,aid,'CANCELADA')
    pause(db)
    result=retry_simulation_preparation(db,aid,True,stamp(db,aid))
    codes={r['code'] for r in result['decision']['reasons']}
    assert 'POLICY_OFF_OR_PAUSED' in codes
    assert already_applied(db,job,'SIMULATION',exclude_attempt=aid) is False
    db.execute("INSERT INTO user_actions(job_id,action,notes,created_at) VALUES(?,'solicitada','SYNTHETIC ONLY',?)",(job['id'],stamp(db,aid)))
    assert already_applied(db,job,'SIMULATION',exclude_attempt=aid) is True
