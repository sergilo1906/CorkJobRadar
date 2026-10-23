"""Persisted draft preparation using fictitious profiles; never external submission."""
import json
import pytest
from corkjobradar.config import digest,now
from corkjobradar.db import Database
from corkjobradar import runtime as rt
from corkjobradar.worker import worker_lock
from corkjobradar.autoapply import document_preparation as drafts
from corkjobradar.autoapply.job_documents import create_job_version, revoke_job_version, load_job_version
from corkjobradar.autoapply.vault import approve_fact, candidate_snapshot
from test_per_job_documents import prepared, approve_test_bundle


def clone(db, job, suffix, **changes):
    row={**job,'id':digest(suffix),'title':job['title']+' '+suffix,
         'url':'https://fixture.test/draft-'+suffix,'apply_url':None,**changes}
    row['content_hash']=digest(row['description']+row['title'])
    cols=list(row)
    db.execute('INSERT INTO jobs('+','.join(cols)+') VALUES('+','.join('?' for _ in cols)+')',tuple(row.values()))
    return row


def test_runtime_creates_actual_documents_without_general_cv_or_any_approval(db,prepared):
    job,_=prepared;before=db.rows('SELECT * FROM candidate_facts')
    rt.command(db,'START',search_now=False);rt.run_work(db,'PREPARE')
    versions=db.rows('SELECT * FROM job_document_versions');assert len(versions)==1
    _,payload=load_job_version(db,versions[0]['id'])
    assert set(payload['files'])=={'CV.pdf','CV.docx','COVER_LETTER.pdf','COVER_LETTER.docx'}
    assert not payload['approved'] and payload['review_required']
    assert not candidate_snapshot(db).get('cv_document_id')
    for table in ('candidate_documents','job_document_bundles','manual_application_handoffs','application_attempts','user_actions','autoapply_policies'):
        assert not db.rows('SELECT * FROM '+table)
    assert db.rows('SELECT * FROM candidate_facts')==before
    assert rt.snapshot(db)['document_drafts_for_review']==1
    assert rt.snapshot(db)['prepared']==0 and rt.snapshot(db)['live_enabled'] is False


def test_all_local_candidates_processed_and_reused_after_database_reopen(db,prepared):
    job,_=prepared
    for i in range(12):clone(db,job,'batch'+str(i))
    first=drafts.prepare_document_drafts(db)
    assert first['assessed']==13 and first['created']==13 and first['held']==0
    before=db.rows('SELECT * FROM job_document_versions')
    again=drafts.prepare_document_drafts(Database(db.path))
    assert again['created']==0 and again['reused']==13
    assert db.rows('SELECT * FROM job_document_versions')==before
    assert first['external_requests']==first['submitted']==0


@pytest.mark.parametrize('changes',[
    {'mode':'REMOTE','location':'Cork, Ireland'},
    {'location':'Dublin'},
    {'open_status':'CLOSED_CONFIRMED'},
    {'description':'Responsibilities\nProvide IT support and troubleshoot Windows.\nRequirements\n5 years of IT support experience required.'},
    {'title':'Warehouse assistant','description':'Move pallets and pack orders.'},
])
def test_excluded_or_separately_authorized_offers_remain_without_automatic_documents(db,prepared,changes):
    job,_=prepared;cols=list(changes)
    db.execute('UPDATE jobs SET '+','.join(c+'=?' for c in cols)+' WHERE id=?',(*changes.values(),job['id']))
    counts=drafts.prepare_document_drafts(db)
    assert counts['assessed']==1 and counts['created']==0 and counts['skipped']==1
    assert not db.rows('SELECT * FROM job_document_versions')


def test_desirable_shortfall_and_unverified_transit_allow_draft_but_never_eligibility(db,prepared):
    job,_=prepared
    text=job['description']+'\nPreferred skills\n5 years of Linux experience preferred.'
    db.execute('UPDATE jobs SET description=?,content_hash=? WHERE id=?',(text,digest(text),job['id']))
    r=drafts.prepare_document_drafts(db);assert r['created']==1
    selection=json.loads(db.rows('SELECT assessment FROM it_application_queue')[0]['assessment'])
    assert selection['state']=='INTERVENCION_REQUERIDA'
    assert 'COMMUTE_AND_SHIFT_PENDING' in selection['warnings']
    assert not db.rows('SELECT * FROM job_document_bundles')


def test_paused_batch_resumes_and_preserves_first_draft_without_duplicates(db,prepared):
    job,_=prepared
    for i in range(3):clone(db,job,'pause'+str(i))
    first=drafts.prepare_document_drafts(db,should_stop=lambda:len(db.rows('SELECT id FROM job_document_versions'))==1)
    assert first['created']==1 and first['paused']
    original=db.rows('SELECT * FROM job_document_versions')[0]
    second=drafts.prepare_document_drafts(Database(db.path))
    assert second['reused']==1 and second['created']==3
    assert db.rows('SELECT * FROM job_document_versions WHERE id=?',(original['id'],))[0]==original


def test_user_selected_two_page_family_is_reused_without_invalidating_approval(db,prepared):
    job,_=prepared;vid=create_job_version(db,job['id'],family='QA_TESTER',max_pages=2)
    bid=approve_test_bundle(db,vid)
    r=drafts.prepare_document_drafts(db);assert r['reused']==1 and r['created']==0
    _,payload=load_job_version(db,vid);assert payload['max_pages']==2 and payload['plan']['family']=='QA_TESTER'
    assert drafts.draft_review_rows(db)==[]
    assert db.rows('SELECT version_id FROM job_document_bundles WHERE id=?',(bid,))[0]['version_id']==vid


def test_revoked_version_is_not_restored_by_automatic_worker(db,prepared):
    job,_=prepared;vid=create_job_version(db,job['id']);revoke_job_version(db,vid,confirmed=True)
    r=drafts.prepare_document_drafts(db)
    assert r['revoked']==1 and r['created']==0 and len(db.rows('SELECT * FROM job_document_versions'))==1
    assert drafts.draft_review_rows(db)==[]


def test_changed_profile_creates_pending_successor_retaining_original(db,prepared):
    job,_=prepared;vid=create_job_version(db,job['id']);old=db.rows('SELECT * FROM job_document_versions')[0]
    approve_fact(db,'location','Ballinlough, Cork','SYNTHETIC TEST',True)
    r=drafts.prepare_document_drafts(db);assert r['created']==1
    assert db.rows('SELECT * FROM job_document_versions WHERE id=?',(vid,))[0]==old
    assert len(drafts.draft_review_rows(db))==1
    assert not db.rows('SELECT * FROM job_document_bundles')


def test_renderer_failure_keeps_safe_hold_and_continues_other_jobs(db,prepared,monkeypatch,capsys):
    job,_=prepared;clone(db,job,'failure');clone(db,job,'continue')
    real=drafts.create_job_version
    def render(database,jid,**options):
        if jid==job['id']:raise ValueError('PRIVATE_DOCUMENT_TEXT_DO_NOT_LOG')
        return real(database,jid,**options)
    monkeypatch.setattr(drafts,'create_job_version',render)
    r=drafts.prepare_document_drafts(db);rt.sync_notifications(db)
    assert r['held']==1 and r['created']==2
    assert db.rows('SELECT error_code FROM it_application_queue WHERE job_id=?',(job['id'],))[0]['error_code']=='DOCUMENT_DRAFT_REVIEW_REQUIRED'
    assert db.rows("SELECT * FROM local_runtime_notifications WHERE kind='DOCUMENT_DRAFT_HOLD'")
    assert 'PRIVATE_DOCUMENT_TEXT_DO_NOT_LOG' not in capsys.readouterr().out+json.dumps(db.rows('SELECT * FROM local_runtime_notifications'))


def test_notifications_deduplicate_and_resolve_on_user_revocation(db,prepared):
    job,_=prepared;vid=create_job_version(db,job['id'])
    rt.sync_notifications(db);rt.sync_notifications(db)
    rows=db.rows("SELECT * FROM local_runtime_notifications WHERE kind='DOCUMENT_REVIEW'");assert len(rows)==1
    assert rows[0]['reference_id']==str(vid) and rows[0]['resolved_at'] is None
    revoke_job_version(db,vid,confirmed=True);rt.sync_notifications(db)
    assert db.rows('SELECT resolved_at FROM local_runtime_notifications WHERE id=?',(rows[0]['id'],))[0]['resolved_at']


def test_disabled_automatic_preparation_does_not_generate_drafts(db,prepared):
    rt.configure(db,6,auto_prepare=False);rt.command(db,'START',search_now=False);rt.run_work(db,'PREPARE')
    assert not db.rows('SELECT * FROM job_document_versions')
    assert db.rows('SELECT * FROM it_application_queue')


def test_no_second_worker_can_render_while_existing_worker_holds_os_lock(db,prepared):
    with worker_lock(db):
        with pytest.raises(OSError):drafts.prepare_document_drafts(db)
    assert not db.rows('SELECT * FROM job_document_versions')


def test_profile_race_leaves_work_for_next_pass_without_marking_fingerprint_complete(db,prepared,monkeypatch):
    job,_=prepared;clone(db,job,'race');real=drafts.create_job_version
    def render(database,jid,**options):
        vid=real(database,jid,**options)
        approve_fact(db,'location','Ballinlough, Cork','SYNTHETIC TEST',True)
        return vid
    monkeypatch.setattr(drafts,'create_job_version',render)
    rt.command(db,'START',search_now=False);rt.run_work(db,'PREPARE')
    assert len(db.rows('SELECT * FROM job_document_versions'))==1
    assert rt.state(db)['last_prepare_fingerprint'] is None


def test_recorded_manual_application_blocks_further_drafting_and_review_notices(db,prepared):
    job,_=prepared;create_job_version(db,job['id'])
    db.execute('INSERT INTO user_actions(job_id,action,created_at) VALUES(?,?,?)',(job['id'],'solicitada',now()))
    r=drafts.prepare_document_drafts(db)
    assert r['created']==r['reused']==0 and r['skipped']==1
    assert drafts.draft_review_rows(db)==[]
    rt.sync_notifications(db)
    assert not db.rows("SELECT * FROM local_runtime_notifications WHERE kind='DOCUMENT_REVIEW'")


def test_corrupt_encrypted_draft_is_preserved_and_held_instead_of_silent_replacement(db,prepared):
    from pathlib import Path
    job,_=prepared;create_job_version(db,job['id'])
    row=db.rows('SELECT * FROM job_document_versions')[0];p=Path(row['encrypted_path'])
    p.write_bytes(b'SYNTHETIC CORRUPTED ASSET')
    r=drafts.prepare_document_drafts(db)
    assert r['held']==1 and r['created']==r['reused']==0
    assert p.read_bytes()==b'SYNTHETIC CORRUPTED ASSET'
    assert db.rows('SELECT * FROM job_document_versions')==[row]


def test_valid_replacement_resolves_prior_hold_and_exposes_review_without_approval(db,prepared):
    job,_=prepared;drafts.prepare_document_drafts(db)
    db.execute("UPDATE it_application_queue SET error_code='DOCUMENT_DRAFT_REVIEW_REQUIRED' WHERE job_id=?",(job['id'],))
    rt.sync_notifications(db)
    assert drafts.draft_review_rows(db)==[]
    create_job_version(db,job['id'],max_pages=2)
    result=drafts.prepare_document_drafts(db);rt.sync_notifications(db)
    assert result['reused']==1 and len(drafts.draft_review_rows(db))==1
    assert db.rows("SELECT resolved_at FROM local_runtime_notifications WHERE kind='DOCUMENT_DRAFT_HOLD'")[0]['resolved_at']
    assert not db.rows('SELECT * FROM job_document_bundles')


def test_revocation_during_automatic_render_is_rechecked_under_write_transaction(db,prepared,monkeypatch):
    job,_=prepared;vid=create_job_version(db,job['id'])
    original_load=drafts.load_job_version;original_create=drafts.create_job_version
    def old_composer(database,version_id,**options):
        row,payload=original_load(database,version_id,**options)
        payload['plan']['composer_version']='SYNTHETIC_OLDER_COMPOSER'
        return row,payload
    def concurrent_revocation(database,jid,**options):
        revoke_job_version(db,vid,confirmed=True)
        return original_create(database,jid,**options)
    monkeypatch.setattr(drafts,'load_job_version',old_composer)
    monkeypatch.setattr(drafts,'create_job_version',concurrent_revocation)
    r=drafts.prepare_document_drafts(db)
    assert r['revoked']==1 and r['created']==0
    assert len(db.rows('SELECT * FROM job_document_versions'))==1
    assert db.rows('SELECT revoked_at FROM job_document_versions')[0]['revoked_at']


def test_resolved_notification_reopens_when_cause_recurs_and_keeps_one_row(db,prepared):
    job,_=prepared;create_job_version(db,job['id']);rt.sync_notifications(db)
    row=db.rows("SELECT * FROM local_runtime_notifications WHERE kind='DOCUMENT_REVIEW'")[0]
    db.execute('UPDATE local_runtime_notifications SET resolved_at=?,acknowledged_at=? WHERE id=?',(now(),now(),row['id']))
    rt.sync_notifications(db)
    after=db.rows('SELECT * FROM local_runtime_notifications WHERE id=?',(row['id'],))[0]
    assert after['resolved_at'] is None and after['acknowledged_at'] is None
    db.execute('UPDATE local_runtime_notifications SET acknowledged_at=? WHERE id=?',(now(),row['id']))
    rt.sync_notifications(db)
    assert len(db.rows("SELECT * FROM local_runtime_notifications WHERE kind='DOCUMENT_REVIEW'"))==1
    assert db.rows('SELECT acknowledged_at FROM local_runtime_notifications WHERE id=?',(row['id'],))[0]['acknowledged_at']


def test_optional_sound_alerts_on_reopened_cause_without_repeating_active_alerts(db,prepared,monkeypatch):
    import sys
    from types import SimpleNamespace
    beeps=[]
    monkeypatch.setitem(sys.modules,'winsound',SimpleNamespace(MessageBeep=lambda flag:beeps.append(flag),MB_ICONEXCLAMATION=1))
    rt.configure(db,6,sound=True);rt.sync_notifications(db);assert len(beeps)==1
    rt.sync_notifications(db);assert len(beeps)==1
    db.execute('UPDATE local_runtime_notifications SET resolved_at=?',(now(),))
    rt.sync_notifications(db);assert len(beeps)==2
