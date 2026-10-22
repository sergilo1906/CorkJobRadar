import json
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import pytest
from corkjobradar.config import now
from corkjobradar.autoapply.store import prefinal_check,save_plan,reserve
from corkjobradar.autoapply.eligibility import Decision
from corkjobradar.autoapply.policy import save_policy
from corkjobradar.autoapply.vault import candidate_snapshot
from test_autoapply_pipeline import setup_attempt
from test_autoapply_policy import stored_job


def prepared(db,profile):
    aid,job=setup_attempt(db,profile)
    candidate=candidate_snapshot(db)
    db.execute('UPDATE application_attempts SET document_id=? WHERE id=?',(candidate['cv_document_id'],aid))
    return aid,job


@pytest.mark.parametrize('deadline,code',[
    ({'validThrough':'2020-01-01T12:00:00Z'},'VACANCY_CLOSED_BEFORE_FINAL'),
    ({'application_deadline':'2026-11-01T12:00:00'},'DEADLINE_NOT_VERIFIABLE'),
    ({'application_deadline_original':'date not yet announced'},'DEADLINE_NOT_VERIFIABLE'),
])
def test_deadline_is_rechecked_even_with_recent_open_confirmation(db,profile,deadline,code):
    aid,job=prepared(db,profile)
    raw=json.loads(job['raw']);raw.update(deadline)
    db.execute('UPDATE jobs SET raw=? WHERE id=?',(json.dumps(raw),job['id']))
    with pytest.raises(PermissionError,match=code):prefinal_check(db,aid)
    assert db.rows('SELECT confirmation_reference FROM application_attempts')[0]['confirmation_reference'] is None


def test_manual_application_during_preparation_blocks_final(db,profile):
    aid,job=prepared(db,profile)
    db.execute("INSERT INTO user_actions(job_id,action,notes,created_at) VALUES(?,'solicitada','SYNTHETIC ONLY',?)",(job['id'],now()))
    with pytest.raises(PermissionError,match='DUPLICATE_DISCOVERED'):prefinal_check(db,aid)


def test_reserved_attempt_does_not_double_count_its_own_quota(db,profile):
    aid,job=prepared(db,profile)
    assert prefinal_check(db,aid)['live_enabled']==0
    policy_id=db.rows('SELECT policy_id FROM autoapply_control')[0]['policy_id']
    for index in range(2):
        other=stored_job(db,profile,'quota-'+str(index),'https://boards.greenhouse.io/synthetic/jobs/'+str(index+200))
        db.execute('UPDATE jobs SET company=?,title=? WHERE id=?',('OTHER SYNTHETIC '+str(index),'Other '+str(index),other['id']))
        other=db.rows('SELECT * FROM jobs WHERE id=?',(other['id'],))[0]
        plan=save_plan(db,other,Decision('ALLOW',[],'fixture',99),policy_id)
        reserve(db,plan,other)
    # Three slots are used, including this attempt: there is no extra slot needed.
    assert prefinal_check(db,aid)['live_enabled']==0
    # Moving its own reservation to yesterday means today's three other slots
    # must be checked before it can possibly send today.
    yesterday=(datetime.now(ZoneInfo('Europe/Dublin'))-timedelta(days=1)).isoformat()
    db.execute('UPDATE application_reservations SET reserved_at=? WHERE attempt_id=?',(yesterday,aid))
    other=stored_job(db,profile,'quota-last','https://boards.greenhouse.io/synthetic/jobs/299')
    db.execute("UPDATE jobs SET company='LAST SYNTHETIC',title='Last' WHERE id=?",(other['id'],))
    other=db.rows('SELECT * FROM jobs WHERE id=?',(other['id'],))[0]
    plan=save_plan(db,other,Decision('ALLOW',[],'fixture',99),policy_id);reserve(db,plan,other)
    with pytest.raises(PermissionError,match='DAILY_QUOTA'):prefinal_check(db,aid)


def test_prefinal_moves_old_reservation_to_today_and_requires_reservation(db,profile):
    aid,job=prepared(db,profile)
    yesterday=(datetime.now(ZoneInfo('Europe/Dublin'))-timedelta(days=1)).isoformat()
    db.execute('UPDATE application_reservations SET reserved_at=? WHERE attempt_id=?',(yesterday,aid))
    prefinal_check(db,aid)
    stored=db.rows('SELECT reserved_at FROM application_reservations WHERE attempt_id=?',(aid,))[0]['reserved_at']
    assert datetime.fromisoformat(stored).date()==datetime.now(ZoneInfo('Europe/Dublin')).date()
    assert db.rows("SELECT id FROM application_events WHERE attempt_id=? AND kind='RESERVATION_MOVED_TO_FINAL_DAY'",(aid,))
    db.execute('DELETE FROM application_reservations WHERE attempt_id=?',(aid,))
    with pytest.raises(PermissionError,match='RESERVATION_MISSING'):prefinal_check(db,aid)
