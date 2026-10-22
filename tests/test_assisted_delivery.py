"""New manual proofs/diagnosis only; synthetic identity, no CAPTCHA replay or POST."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta
from email.message import EmailMessage
from email import policy
import io
import json
from pathlib import Path
import sqlite3
import zipfile
import pytest
from corkjobradar.config import now
from corkjobradar.db import Database
from corkjobradar.autoapply.blocker_report import build_blocker_report
from corkjobradar.autoapply.documents import render_cv
from corkjobradar.autoapply.handoff import prepare_handoff,declare_manual_submission,handoff_download,load_handoff
from corkjobradar.autoapply.manual_evidence import retain_manual_evidence,read_manual_evidence,evidence_download,review_manual_evidence,MAX_BYTES
from corkjobradar.autoapply.store import already_applied
from corkjobradar.autoapply.vault import candidate_snapshot,forget_professional_data,approve_fact
from test_autoapply_manual_handoff import setup
from test_autoapply_public_forms import schema


def message(job,recipient='synthetic@example.invalid',*,html=False,receipt=True):
    msg=EmailMessage();msg['From']='Recruitment <applications@example.invalid>';msg['To']=recipient
    msg['Date']='Wed, 21 Oct 2026 10:00:00 +0100';msg['Message-ID']='<SYNTHETIC-RECEIPT@example.invalid>'
    msg['Subject']='Application received: '+job['title']
    text=('Your application was received. ' if receipt else 'Your profile was viewed. ')+job['company']+' '+job['title']
    msg.set_content('<html><p>'+text+'</p><img src="https://do-not-load.invalid/pixel"><script>notExecuted()</script></html>' if html else text,subtype='html' if html else 'plain')
    return msg.as_bytes(policy=policy.SMTP)


def manual_case(db,profile):
    job,inspection,doc=setup(db,profile);hid=prepare_handoff(db,job['id'],inspection['inspection_id'])['handoff_id']
    action=declare_manual_submission(db,hid,True)
    decl=db.rows('SELECT id FROM manual_application_declarations WHERE handoff_id=?',(hid,))[0]['id']
    return job,hid,decl,action


def test_manual_package_readable_contacts_linkedin_cv_and_optional_questions(db,profile):
    from test_autoapply_vault import populate
    from test_autoapply_public_forms import inspected
    from corkjobradar.autoapply.documents import store_document
    populate(db);approve_fact(db,'linkedin_url','https://www.linkedin.com/in/synthetic-only/','SYNTHETIC',True)
    doc=store_document(db,render_cv(candidate_snapshot(db),'pdf'),'pdf',True)
    data=schema();data['questions'].append({'label':'Optional unknown question','required':False,'fields':[{'name':'extra','type':'input_text'}]})
    job,inspection=inspected(db,profile,data);hid=prepare_handoff(db,job['id'],inspection['inspection_id'])['handoff_id']
    package=load_handoff(db,hid)
    assert package['document_id']==doc and any(q['field']=='extra' for q in package['unresolved_questions'])
    with zipfile.ZipFile(io.BytesIO(handoff_download(db,hid))) as archive:
        text=archive.read('CANDIDATURA.txt').decode('utf-8')
        assert 'synthetic@example.invalid' in text and 'linkedin.com/in/synthetic-only/' in text
        assert 'Optional unknown question' in text and job['url'] in text and 'coche' in text
        assert archive.read('CV.pdf').startswith(b'%PDF')
    assert not db.rows('SELECT * FROM user_actions')


@pytest.mark.parametrize('fmt',['eml','pdf','html_eml'])
def test_manual_proof_dpapi_roundtrip_review_and_download_are_not_external_confirmation(db,profile,fmt):
    job,hid,decl,action=manual_case(db,profile)
    content=render_cv(candidate_snapshot(db),'pdf') if fmt=='pdf' else message(job,html=fmt=='html_eml')
    ext='pdf' if fmt=='pdf' else 'eml'
    with pytest.raises(PermissionError):retain_manual_evidence(db,decl,content,ext)
    result=retain_manual_evidence(db,decl,content,ext,consent=True);eid=result['evidence_id']
    packet=read_manual_evidence(db,eid)
    assert evidence_download(db,eid)==(content,ext)
    assert not packet['signals']['sender_authenticated'] and not packet['external_receipt_verified']
    if ext=='eml':
        assert packet['signals']['recipient_matches_application'] and packet['signals']['receipt_phrase_present']
        assert packet['signals']['title_mentioned'] and packet['signals']['company_mentioned']
    if fmt=='html_eml':assert '<img' not in packet['extracted']['text'] and '<script' not in packet['extracted']['text']
    path=Path(db.rows('SELECT encrypted_path FROM manual_application_evidence')[0]['encrypted_path'])
    assert b'synthetic@example.invalid' not in path.read_bytes()
    with pytest.raises(PermissionError):review_manual_evidence(db,eid,result['content_hash'])
    with pytest.raises(ValueError):review_manual_evidence(db,eid,'changed',acknowledged=True)
    rid=review_manual_evidence(db,eid,result['content_hash'],acknowledged=True)
    assert review_manual_evidence(db,eid,result['content_hash'],acknowledged=True)==rid
    assert db.rows('SELECT status FROM manual_application_evidence_reviews')[0]['status']=='USER_REVIEWED_NOT_EXTERNALLY_AUTHENTICATED'
    assert not db.rows('SELECT * FROM application_receipt_evidence') and not db.rows('SELECT * FROM application_attempts')
    assert db.rows('SELECT id FROM user_actions')[0]['id']==action and already_applied(db,job,'LIVE')
    assert db.rows('SELECT enabled,live_enabled FROM autoapply_control')[0]['live_enabled']==0
    public=json.dumps(db.rows('SELECT * FROM application_events'))+json.dumps(db.rows('SELECT * FROM manual_application_evidence'))
    assert 'synthetic@example.invalid' not in public and 'applications@example.invalid' not in public
    with pytest.raises(sqlite3.IntegrityError):db.execute("UPDATE manual_application_evidence SET status='VERIFIED' WHERE id=?",(eid,))
    with pytest.raises(sqlite3.IntegrityError):db.execute('DELETE FROM manual_application_evidence WHERE id=?',(eid,))


def test_parallel_duplicate_upload_keeps_single_evidence_and_no_new_application(db,profile):
    job,hid,decl,action=manual_case(db,profile);content=message(job)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:retain_manual_evidence(Database(db.path),decl,content,'eml',consent=True),range(2)))
    assert len({r['evidence_id'] for r in results})==1 and len(db.rows('SELECT * FROM manual_application_evidence'))==1
    assert len(db.rows('SELECT * FROM user_actions'))==1


@pytest.mark.parametrize('kind',['size','empty','exe','broken_email','duplicate_from','forwarded','active_pdf'])
def test_untrusted_evidence_rejected_without_persisting_personal_values(db,profile,kind):
    job,hid,decl,action=manual_case(db,profile);ext='eml';content=message(job)
    if kind=='size':content=b'x'*(MAX_BYTES+1)
    if kind=='empty':content=b''
    if kind=='exe':ext='exe';content=b'MZnotAllowed'
    if kind=='broken_email':content=b'not an email'
    if kind=='duplicate_from':content=b'From: attacker@example.invalid\r\n'+content
    if kind=='forwarded':
        msg=EmailMessage();msg['From']='forwarder@example.invalid';msg['To']='synthetic@example.invalid';msg.set_content('Forwarded');msg.add_attachment(EmailMessage());content=msg.as_bytes()
    if kind=='active_pdf':
        from pypdf import PdfReader,PdfWriter
        reader=PdfReader(io.BytesIO(render_cv(candidate_snapshot(db),'pdf')));writer=PdfWriter();writer.append(reader);writer.add_js('app.alert("NO")');buf=io.BytesIO();writer.write(buf);content=buf.getvalue();ext='pdf'
    with pytest.raises(ValueError):retain_manual_evidence(db,decl,content,ext,consent=True)
    assert not db.rows('SELECT * FROM manual_application_evidence')


def test_wrong_recipient_and_unrelated_message_stay_unverified(db,profile):
    job,hid,decl,action=manual_case(db,profile)
    content=message(job,'someone@example.invalid',receipt=False).replace(b'Application received:',b'Profile update:')
    result=retain_manual_evidence(db,decl,content,'eml',consent=True)
    assert not result['signals']['recipient_matches_application'] and not result['signals']['receipt_phrase_present']
    assert not result['external_receipt_verified']


def test_expired_package_or_changed_current_profile_does_not_erase_historical_proof(db,profile,monkeypatch):
    import corkjobradar.autoapply.handoff as handoff
    job,hid,decl,action=manual_case(db,profile)
    class Later(datetime):
        @classmethod
        def now(cls,tz=None):return datetime.now(tz)+timedelta(days=2)
    monkeypatch.setattr(handoff,'datetime',Later)
    with pytest.raises(ValueError):load_handoff(db,hid)
    approve_fact(db,'email','new-profile@example.invalid','SYNTHETIC CHANGED',True)
    result=retain_manual_evidence(db,decl,message(job),'eml',consent=True)
    assert result['signals']['recipient_matches_application']  # Bound to archived application.


def test_proof_integrity_and_profile_erasure_cover_new_vault_asset(db,profile):
    job,hid,decl,action=manual_case(db,profile)
    result=retain_manual_evidence(db,decl,message(job),'eml',consent=True)
    path=Path(db.rows('SELECT encrypted_path FROM manual_application_evidence')[0]['encrypted_path']);saved=path.read_bytes()
    path.write_bytes(b'not encrypted')
    with pytest.raises(Exception):read_manual_evidence(db,result['evidence_id'])
    path.write_bytes(saved);forget_professional_data(db,True)
    assert not path.exists() and db.rows('SELECT id FROM manual_application_evidence')
    with pytest.raises(Exception):evidence_download(db,result['evidence_id'])


def test_v8_to_v9_preserves_every_existing_row_and_live_lock(db,profile):
    job,hid,decl,action=manual_case(db,profile)
    tables=[r['name'] for r in db.rows("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'manual_application_evidence%'")]
    before={t:db.rows('SELECT * FROM '+t) for t in tables}
    with db.connect() as con:con.executescript('DROP TABLE manual_application_evidence_reviews; DROP TABLE manual_application_evidence; PRAGMA user_version=8;')
    reopened=Database(db.path)
    assert reopened.rows('PRAGMA user_version')[0]['user_version']==12
    assert all(reopened.rows('SELECT * FROM '+t)==rows for t,rows in before.items())
    assert not reopened.rows('PRAGMA foreign_key_check')
    with pytest.raises(sqlite3.IntegrityError):reopened.execute('UPDATE autoapply_control SET live_enabled=1')


def test_independent_axes_do_not_hide_other_causes_behind_policy_off(db,profile):
    job,inspection,doc=setup(db,profile)
    db.execute('UPDATE candidate_documents SET approved_at=NULL WHERE id=?',(doc,))
    before={t:db.rows('SELECT COUNT(*) n FROM '+t)[0]['n'] for t in ('jobs','candidate_facts','application_attempts','user_actions')}
    report=build_blocker_report(db);row=next(r for r in report['offers'] if r['job_id']==job['id'])
    assert set(row['axes'])=={'permission','adapter','human_access','answers','transport','cv_policy','compatible_offer'}
    assert row['axes']['permission']['status']=='NOT_GRANTED' and row['axes']['adapter']['status']=='PREPARATION_ONLY'
    assert row['axes']['transport']['status']=='UNVERIFIED' and not row['axes']['cv_policy']['approved_cv_available']
    assert not row['axes']['cv_policy']['authorized_policy_available'] and not row['ready_to_submit']
    assert before=={t:db.rows('SELECT COUNT(*) n FROM '+t)[0]['n'] for t in before}
    assert candidate_snapshot(db)['email'] not in json.dumps(report)


def test_readiness_ui_lists_separate_causes_without_starting_workers(db,profile):
    from streamlit.testing.v1 import AppTest
    setup(db,profile)
    app=AppTest.from_string('from corkjobradar.db import Database\nfrom corkjobradar.autoapply.assisted_ui import render_assisted_diagnostics,render_manual_evidence\ndb=Database('+repr(str(db.path))+')\nrender_assisted_diagnostics(db)\nrender_manual_evidence(db)').run(timeout=30)
    next(b for b in app.button if b.label=='Diagnosticar todos los bloqueos por separado').click().run(timeout=30)
    assert not app.exception and any(b.label=='Descargar diagnóstico separado' for b in app.get('download_button'))
    assert not db.rows('SELECT * FROM autoapply_interventions') and not db.rows('SELECT * FROM user_actions')


def test_manual_evidence_ui_review_is_bound_to_one_file_and_private_preview_is_opt_in(db,profile):
    from streamlit.testing.v1 import AppTest
    job,hid,decl,action=manual_case(db,profile)
    first=retain_manual_evidence(db,decl,message(job),'eml',consent=True)['evidence_id']
    second=retain_manual_evidence(db,decl,message(job,recipient='other@example.invalid'),'eml',consent=True)['evidence_id']
    code='from corkjobradar.db import Database\nfrom corkjobradar.autoapply.assisted_ui import render_manual_evidence\nrender_manual_evidence(Database('+repr(str(db.path))+'))'
    app=AppTest.from_string(code).run(timeout=30)
    assert not app.exception
    review=lambda:next(b for b in app.button if b.label=='Registrar mi revisión del justificante')
    private=lambda:next(c for c in app.checkbox if c.label=='Mostrar el texto privado del justificante')
    ack=lambda:next(c for c in app.checkbox if c.label.startswith('He contrastado personalmente'))
    assert review().disabled and not private().value
    private().check().run();ack().check().run()
    assert not review().disabled and any('Application received' in t.value for t in app.text)
    review().click().run()
    assert len(db.rows('SELECT * FROM manual_application_evidence_reviews'))==1
    next(s for s in app.selectbox if s.label=='Justificante para revisar o descargar').set_value(first).run()
    assert review().disabled and not private().value
    assert len(db.rows('SELECT * FROM manual_application_evidence_reviews'))==1
    assert not db.rows('SELECT * FROM application_receipt_evidence')
    assert db.rows('SELECT id FROM user_actions')==[{'id':action}]
