import json
from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from corkjobradar.deadlines import hse_deadline_fields
from corkjobradar.verification import deadline_state
from corkjobradar.models import Job
from corkjobradar.repository import save_job
from scripts.backfill_hse_deadlines import backfill
from conftest import source


@pytest.mark.parametrize('published,normalized',[
    ('05/11/2026  15:00:00','2026-11-05T15:00:00'),
    ('05/11/2026 15:00','2026-11-05T15:00:00'),
    ('05/11/2026','2026-11-05'),
])
def test_exact_published_hse_formats(published,normalized):
    result=hse_deadline_fields({'Closing date':published})
    assert result['application_deadline_original']==published
    assert result['application_deadline']==normalized
    assert result['deadline_timezone']=='Europe/Dublin'
    assert deadline_state(result,datetime(2026,11,6,tzinfo=ZoneInfo('Europe/Dublin')))[0]=='EXPIRED'


def test_unknown_closing_date_is_explicitly_unverifiable():
    result=hse_deadline_fields({'Closing date':'Friday at noon'})
    assert 'application_deadline' not in result
    assert deadline_state(result)[0]=='UNPARSEABLE'


def test_backfill_preserves_history_and_does_not_claim_network_check(db,profile):
    source(db,'hse','hse-test')
    jid=save_job(db,'hse-test',Job(external_id='deadline-test',title='Synthetic Only',url='https://fixture.test/hse',
                 raw={'published_fields':{'Closing date':'05/11/2026  15:00:00'}}),profile=profile)
    before=db.rows('SELECT * FROM jobs')[0];snapshots=db.rows('SELECT * FROM job_snapshots')
    preview=backfill(db)
    assert preview['updates']==1 and preview['network_requests']==0 and preview['applied'] is False
    assert db.rows('SELECT * FROM jobs')[0]==before
    result=backfill(db,apply=True)
    after=db.rows('SELECT * FROM jobs')[0]
    assert result['updates']==1
    assert json.loads(after['raw'])['application_deadline']=='2026-11-05T15:00:00'
    assert after['last_verified_at']==before['last_verified_at']
    assert after['content_hash']==before['content_hash']
    assert snapshots==db.rows('SELECT * FROM job_snapshots')
    assert backfill(db,apply=True)['updates']==0
    audit=json.loads(db.rows("SELECT details FROM audit_events WHERE kind='HSE_DEADLINE_METADATA_BACKFILLED'")[0]['details'])
    assert audit['new_network_verification'] is False


def test_existing_conflicting_deadline_is_retained_for_review(db,profile):
    source(db,'hse','hse-test')
    raw={'published_fields':{'Closing date':'05/11/2026'},'application_deadline':'2026-12-01'}
    save_job(db,'hse-test',Job(external_id='conflict',title='Synthetic Only',url='https://fixture.test/conflict',raw=raw),profile=profile)
    before=db.rows('SELECT * FROM jobs')
    report=backfill(db,apply=True)
    assert report['updates']==0 and report['offers'][0]['status']=='CONFLICT_REQUIRES_REVIEW'
    assert db.rows('SELECT * FROM jobs')==before
