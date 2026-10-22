"""Synthetic identities only. No remote calls, approvals or production writes."""
import io
import json
import sqlite3
import zipfile
from pathlib import Path
import pytest
from corkjobradar.autoapply.handoff import prepare_handoff,load_handoff,handoff_download,declare_manual_submission
from corkjobradar.autoapply.vault import candidate_snapshot,approve_fact
from corkjobradar.autoapply.documents import render_cv,store_document,create_cv_review
from corkjobradar.autoapply.store import already_applied
from corkjobradar.autoapply.compatibility import compatibility_report
from test_autoapply_vault import populate
from test_autoapply_policy import stored_job
from test_autoapply_public_forms import inspected


def setup(db,profile):
    populate(db)
    approve_fact(db,'linkedin_url','https://www.linkedin.com/in/synthetic-only/','SYNTHETIC',True)
    doc=store_document(db,render_cv(candidate_snapshot(db),'pdf'),'pdf',True)
    job,inspection=inspected(db,profile)
    return job,inspection,doc


def test_approved_package_roundtrip_has_real_pdf_contacts_and_holds_without_sending(db,profile):
    job,inspection,doc=setup(db,profile)
    result=prepare_handoff(db,job['id'],inspection['inspection_id'])
    assert result['state']=='MANUAL_REVIEW_REQUIRED' and not result['submitted']
    assert result['blockers']
    package=load_handoff(db,result['handoff_id'])
    assert package['contacts']['linkedin_url'].endswith('/synthetic-only/')
    assert package['document_id']==doc and not package['external_receipt_verified']
    data=handoff_download(db,result['handoff_id'])
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert archive.read('CV.pdf').startswith(b'%PDF')
        assert json.loads(archive.read('datos-y-respuestas.json'))['contacts']['email']=='synthetic@example.invalid'
    assert not db.rows('SELECT * FROM user_actions') and not db.rows('SELECT * FROM application_attempts')
    row=db.rows('SELECT * FROM manual_application_handoffs')[0]
    assert b'synthetic@example.invalid' not in Path(row['encrypted_path']).read_bytes()
    assert 'synthetic@example.invalid' not in json.dumps(db.rows('SELECT * FROM application_events'))


def test_draft_does_not_authorize_export(db,profile):
    populate(db);create_cv_review(db,render_cv(candidate_snapshot(db)),'docx')
    job=stored_job(db,profile)
    with pytest.raises(PermissionError,match='APPROVED_CV'):prepare_handoff(db,job['id'])


@pytest.mark.parametrize('change',['non_it','content','target','profile','cv_revoked','corrupt'])
def test_package_revalidated_on_download(db,profile,change):
    job,inspection,doc=setup(db,profile);hid=prepare_handoff(db,job['id'],inspection['inspection_id'])['handoff_id']
    if change=='non_it':db.execute("UPDATE jobs SET title='Warehouse Operative' WHERE id=?",(job['id'],))
    if change=='content':db.execute("UPDATE jobs SET content_hash='changed' WHERE id=?",(job['id'],))
    if change=='target':db.execute("UPDATE jobs SET apply_url='https://example.org/changed' WHERE id=?",(job['id'],))
    if change=='profile':approve_fact(db,'availability','SYNTHETIC changed','SYNTHETIC',True)
    if change=='cv_revoked':db.execute("UPDATE candidate_documents SET revoked_at='revoked' WHERE id=?",(doc,))
    if change=='corrupt':
        path=Path(db.rows('SELECT encrypted_path FROM manual_application_handoffs')[0]['encrypted_path'])
        path.write_bytes(b'NOT DPAPI')
    with pytest.raises((ValueError,PermissionError,RuntimeError)):handoff_download(db,hid)


def test_manual_declaration_is_idempotent_blocks_duplicate_but_is_not_external_receipt(db,profile):
    job,inspection,_=setup(db,profile);hid=prepare_handoff(db,job['id'])['handoff_id']
    with pytest.raises(ValueError):declare_manual_submission(db,hid)
    aid=declare_manual_submission(db,hid,True)
    assert declare_manual_submission(db,hid,True)==aid
    assert already_applied(db,job,'LIVE')
    assert len(db.rows('SELECT * FROM user_actions'))==1
    assert db.rows('SELECT status FROM manual_application_declarations')[0]['status']=='DECLARED_NO_EXTERNAL_RECEIPT'
    assert not db.rows('SELECT * FROM application_receipt_evidence')
    with pytest.raises(PermissionError,match='ALREADY_APPLIED'):prepare_handoff(db,job['id'])
    with pytest.raises(PermissionError,match='ALREADY_APPLIED'):handoff_download(db,hid)


def test_handoff_erasure_removes_encrypted_personal_package(db,profile):
    from corkjobradar.autoapply.vault import forget_professional_data
    job,_,_=setup(db,profile);prepare_handoff(db,job['id'])
    path=Path(db.rows('SELECT encrypted_path FROM manual_application_handoffs')[0]['encrypted_path'])
    forget_professional_data(db,True)
    assert not path.exists()


def test_manual_past_submission_is_recordable_after_profile_change_without_reusing_old_cv(db,profile):
    job,_,_=setup(db,profile);hid=prepare_handoff(db,job['id'])['handoff_id']
    approve_fact(db,'availability','SYNTHETIC updated','SYNTHETIC',True)
    with pytest.raises(ValueError,match='PROFILE_OR_CV_CHANGED'):handoff_download(db,hid)
    assert declare_manual_submission(db,hid,True)
    assert already_applied(db,job,'LIVE')
    assert not db.rows('SELECT * FROM application_receipt_evidence')


def test_manual_ui_recovers_stored_package_without_starting_any_worker(db,profile,monkeypatch):
    from streamlit.testing.v1 import AppTest
    from corkjobradar.config import ROOT
    import corkjobradar.db as module
    import corkjobradar.autoapply.ui as ui
    job,inspection,_=setup(db,profile)
    hid=prepare_handoff(db,job['id'],inspection['inspection_id'])['handoff_id']
    monkeypatch.setattr(module,'Database',lambda:db)
    started=[];monkeypatch.setattr(ui,'launch_simulation',lambda:started.append(True))
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=45).run()
    assert not app.exception and not started
    app.radio(key='ui_area').set_value('AutoApply').run()
    app.checkbox(key='aa_tools').check().run()
    app.selectbox(key='aa_tool').set_value('Compatibilidad de plataformas').run()
    package=next(w for w in app.selectbox if w.label=='Paquete manual conservado')
    assert package.value==hid
    assert next(w for w in app.button if w.label=='Registrar mi declaración de envío manual').disabled
    assert not db.rows('SELECT * FROM user_actions')


def test_platform_catalogue_never_grants_submission_permission():
    from corkjobradar.autoapply.platforms import platform_for
    report=compatibility_report()
    assert report['allowed_and_verified_count']==0
    assert {'PENDING','MANUAL','PROHIBITED'}<={r['status'] for r in report['routes']}
    assert not platform_for('https://jobs.ashbyhq.com/example/posting')['live_supported']


def test_v6_to_v7_migration_preserves_history_and_live_lock(tmp_path):
    from corkjobradar.db import Database
    db=Database(tmp_path/'migration.sqlite3')
    before=db.rows('SELECT * FROM autoapply_control')
    with db.connect() as con:
        con.executescript('DROP TABLE manual_application_declarations; DROP TABLE manual_application_handoffs; PRAGMA user_version=6;')
    reopened=Database(db.path)
    assert reopened.rows('SELECT * FROM autoapply_control')==before
    assert reopened.rows('PRAGMA integrity_check')[0]['integrity_check']=='ok'
    assert not reopened.rows('PRAGMA foreign_key_check')
    with pytest.raises(sqlite3.IntegrityError):reopened.execute('UPDATE autoapply_control SET live_enabled=1')
