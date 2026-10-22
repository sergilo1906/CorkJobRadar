"""Owned challenge only; synthetic identity. No external form, CAPTCHA or POST."""
from datetime import datetime,timedelta
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
import pytest
from corkjobradar.config import ROOT,now
from corkjobradar.db import Database
from corkjobradar.autoapply.browser import FormHold
from corkjobradar.autoapply.documents import document_bytes
from corkjobradar.autoapply.human_sessions import (create_intervention,request_command,session_row,validate_session,
    pending_interventions,session_lock,worker_alive,PAUSED,EXPIRED,context_for,require_owned_fixture)
from corkjobradar.autoapply.interactive_browser import InteractiveBrowser,detect_human_check
from corkjobradar.autoapply.interaction_modes import interaction_route,manual_target_url
from corkjobradar.autoapply.policy import pause
from corkjobradar.autoapply.store import already_applied,transition
from corkjobradar.autoapply.vault import candidate_snapshot,approve_fact
from human_verification_receiver import human_receiver
from test_autoapply_final_gate import prepared


@pytest.mark.parametrize('url,expected',[
 ('https://www.linkedin.com/jobs/view/123/?tracking=abc','LINKEDIN_MANUAL'),
 ('https://ie.linkedin.com/jobs/view/123','LINKEDIN_MANUAL'),
 ('https://ie.indeed.com/viewjob?jk=0123456789abcdef','INDEED_MANUAL'),
 ('https://www.indeed.co.uk/viewjob?jk=0123456789abcdef','INDEED_MANUAL'),
 ('https://linkedin.com.attacker.invalid/job','HOLD'),
 ('https://indeed.com.attacker.invalid/job','HOLD'),
 ('https://distilled.recruitee.com/o/snr-fe','HOLD'),
 ('http://127.0.0.1/form','HOLD'),('https://name:password@linkedin.com/job','HOLD'),
 ('https://linkedin.com:wrong/jobs','HOLD'),
])
def test_provider_modes_never_automate_restricted_or_unreviewed_targets(url,expected):
    result=interaction_route(url)
    assert result['mode']==expected and not result['automation_allowed']


def test_external_redirect_does_not_inherit_portal_permission():
    result=interaction_route('https://job-boards.greenhouse.io/synthetic/jobs/123',source_url='https://www.linkedin.com/jobs/view/1')
    assert result['mode']=='HOLD' and result['independent_employer_review_required']


def test_manual_links_keep_only_known_job_identifier_not_tracking_or_tokens():
    assert manual_target_url('https://ie.indeed.com/viewjob?jk=0123456789abcdef&token=SECRET')=='https://ie.indeed.com/viewjob?jk=0123456789abcdef'
    assert manual_target_url('https://www.linkedin.com/jobs/view/123/?trk=SECRET')=='https://www.linkedin.com/jobs/view/123/'
    with pytest.raises(ValueError):manual_target_url('https://jobs.example.org/form?token=SECRET')
    with pytest.raises(ValueError):manual_target_url('https://ie.indeed.com/viewjob?jk=SECRET')


def fixture_setup(db,profile,monkeypatch,*,receipt=True,verification='captcha',redirect=False):
    aid,job,inspection,cap=prepared(db,profile,monkeypatch)
    candidate=candidate_snapshot(db);_,_,sha=document_bytes(db,candidate['cv_document_id'])
    expected={'name':candidate['full_name'],'email':candidate['email'],'linkedin':candidate['linkedin_url']}
    receiver=human_receiver(db.path.parent/'human-receiver.sqlite3',job['id'],expected,sha,receipt=receipt,verification=verification,redirect=redirect)
    return aid,job,inspection,receiver


def manual_complete(actor):
    # This is ONLY the test's stand-in for the human, not application automation.
    actor.page.get_by_role('button',name='I complete the simulated verification',exact=True).click()
    actor.page.locator('#human').wait_for(state='hidden')


@pytest.mark.parametrize('verification',['captcha','mfa'])
def test_visible_or_headless_pause_preserves_fields_manual_resume_and_owned_receipt(db,profile,monkeypatch,verification):
    aid,job,inspection,receiver=fixture_setup(db,profile,monkeypatch,verification=verification)
    with receiver as server:
        sid=create_intervention(db,aid,inspection['inspection_id'],_fixture_url=server['url'])
        assert create_intervention(db,aid,inspection['inspection_id'],_fixture_url=server['url'])==sid
        with InteractiveBrowser(db,sid,headless=os.environ.get('CJR_HEADED_TEST')!='1') as actor:
            actor.open();row=session_row(db,sid)
            assert row['status']==PAUSED and row['filled_count']==3 and server['stats']['posts']==0
            assert detect_human_check(actor.page) in {'HUMAN_VERIFICATION_REQUIRED','AUTHENTICATION_REQUIRED'}
            name=actor.page.locator('#name').input_value();assert name==candidate_snapshot(db)['full_name']
            assert actor.page.locator('#resume').evaluate('(e)=>e.files.length')==1
            assert actor.page.locator('#linkedin').input_value()==''
            actor.continue_after_human();assert server['stats']['posts']==0
            manual_complete(actor)
            assert actor.page.locator('#name').input_value()==name  # Still the SAME page/session.
            actor.continue_after_human();row=session_row(db,sid)
            assert row['status']=='PRUEBA_LOCAL_CONFIRMADA' and row['local_receipt_verified']==1
            assert server['stats']['posts']==1
            with sqlite3.connect(server['db']) as con:assert con.execute('SELECT COUNT(*) FROM receipts').fetchone()[0]==1
            with pytest.raises((FormHold,PermissionError)):actor.continue_after_human()
            with pytest.raises(PermissionError):request_command(db,sid,'RECOVER')
            assert server['stats']['posts']==1
        assert already_applied(db,job)
        assert not db.rows('SELECT * FROM user_actions') and not db.rows('SELECT * FROM application_receipt_evidence')
        assert db.rows('SELECT state FROM application_attempts WHERE id=?',(aid,))[0]['state']!='ENVIADA_CONFIRMADA'
        with pytest.raises(PermissionError):transition(db,aid,'ENVIANDO')
        report={'checked_at':now(),'verification':verification,'visible_browser':os.environ.get('CJR_HEADED_TEST')=='1',
                'paused_before_post':True,'fields_preserved_same_session':True,'local_post_count':1,'local_receipt_verified':True,
                'external_post_count':0,'external_receipt_verified':False,'live_enabled':False}
        (ROOT/'logs'/('human-intervention-'+verification+'-'+db.path.parent.parent.name+'.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')


def test_server_success_without_correlated_receipt_stays_uncertain_no_retry(db,profile,monkeypatch):
    aid,job,inspection,receiver=fixture_setup(db,profile,monkeypatch,receipt=False)
    with receiver as server:
        sid=create_intervention(db,aid,inspection['inspection_id'],_fixture_url=server['url'])
        with InteractiveBrowser(db,sid,headless=True) as actor:
            actor.open();manual_complete(actor);actor.continue_after_human()
            row=session_row(db,sid)
            assert row['status']=='ENVIO_INCIERTO' and not row['local_receipt_verified']
            with pytest.raises(PermissionError):validate_session(db,sid)
            assert server['stats']['posts']==1 and not db.rows('SELECT * FROM user_actions')


def test_new_human_challenge_at_the_submit_event_stops_before_network_dispatch(db,profile,monkeypatch):
    aid,job,inspection,receiver=fixture_setup(db,profile,monkeypatch)
    with receiver as server:
        sid=create_intervention(db,aid,inspection['inspection_id'],_fixture_url=server['url'])
        with InteractiveBrowser(db,sid,headless=True) as actor:
            actor.open();manual_complete(actor)
            actor.page.locator('form').evaluate("f=>f.addEventListener('submit',()=>document.getElementById('human').hidden=false)")
            actor.continue_after_human()
            assert session_row(db,sid)['status']==PAUSED and server['stats']['posts']==0
            assert not session_row(db,sid)['submission_started']


def test_expired_or_closed_session_rebuilds_fields_but_requires_new_verification(db,profile,monkeypatch):
    aid,job,inspection,receiver=fixture_setup(db,profile,monkeypatch)
    with receiver as server:
        sid=create_intervention(db,aid,inspection['inspection_id'],_fixture_url=server['url'])
        with InteractiveBrowser(db,sid,headless=True) as actor:
            actor.open();manual_complete(actor);server['expire']();actor.continue_after_human()
            assert session_row(db,sid)['status']==EXPIRED and server['stats']['posts']==0
            actor.recover()
            assert session_row(db,sid)['status']==PAUSED and server['stats']['forms']==2
            assert detect_human_check(actor.page)=='HUMAN_VERIFICATION_REQUIRED'
            assert actor.page.locator('#email').input_value()==candidate_snapshot(db)['email']
            actor.page.close();actor.focus();assert session_row(db,sid)['status']==EXPIRED
            actor.recover();assert server['stats']['forms']==3
            actor.continue_after_human();assert server['stats']['posts']==0
            manual_complete(actor);actor.continue_after_human();assert server['stats']['posts']==1


@pytest.mark.parametrize('changed',['pause','non_it','route','deadline','quota','unknown_question','cv','field','attached_file','hidden_widget_only'])
def test_resume_rechecks_each_gate_without_posting(db,profile,monkeypatch,changed):
    aid,job,inspection,receiver=fixture_setup(db,profile,monkeypatch)
    with receiver as server:
        sid=create_intervention(db,aid,inspection['inspection_id'],_fixture_url=server['url'])
        with InteractiveBrowser(db,sid,headless=True) as actor:
            actor.open();manual_complete(actor)
            if changed=='pause':pause(db)
            elif changed=='non_it':db.execute("UPDATE jobs SET title='Warehouse Operative' WHERE id=?",(job['id'],))
            elif changed=='route':db.execute('DELETE FROM commute_checks WHERE job_id=?',(job['id'],))
            elif changed=='deadline':db.execute('UPDATE jobs SET raw=? WHERE id=?',(json.dumps({'_synthetic_fixture':True,'application_deadline':'2020-01-01'}),job['id']))
            elif changed=='quota':
                from corkjobradar.autoapply.policy import current_policy
                policy=current_policy(db)[2]
                # A real separate synthetic reservation, not this attempt counted twice.
                for index in range(policy.max_daily):
                    pid=db.execute("INSERT INTO application_plans(job_id,policy_id,content_hash,facts_hash,fingerprint,environment,decision,reasons,state,created_at) VALUES(?,NULL,?,?,?,'SIMULATION','HOLD','[]','PENDIENTE_VERIFICACION',?)",(job['id'],str(index),'synthetic',str(index),now()))
                    other=db.execute("INSERT INTO application_attempts(plan_id,state,adapter,target_url,started_at,updated_at,policy_epoch) VALUES(?,'CANCELADA','synthetic','https://example.invalid',?,?,0)",(pid,now(),now()))
                    db.execute("INSERT INTO application_reservations(attempt_id,environment,employer_key,reserved_at) VALUES(?,'SIMULATION','other',?)",(other,now()))
            elif changed=='unknown_question':actor.page.locator('form').evaluate("f=>{const e=document.createElement('input');e.id='unknown';e.required=true;f.append(e);}")
            elif changed=='cv':db.execute('UPDATE candidate_documents SET revoked_at=? WHERE id=?',(now(),candidate_snapshot(db)['cv_document_id']))
            elif changed=='field':actor.page.locator('#name').fill('SYNTHETIC unapproved edit')
            elif changed=='attached_file':actor.page.locator('#resume').set_input_files({'name':'CV.pdf','mimeType':'application/pdf','buffer':b'not approved'})
            elif changed=='hidden_widget_only':
                actor.recover();actor.page.locator('#human').evaluate('(e)=>e.hidden=true')
            if changed=='hidden_widget_only':
                actor.continue_after_human();assert session_row(db,sid)['reason_code']=='HUMAN_VERIFICATION_NOT_CONFIRMED'
            else:
                with pytest.raises((ValueError,PermissionError,FormHold,RuntimeError)):actor.continue_after_human()
            assert server['stats']['posts']==0


def test_metadata_commands_os_lock_and_lost_worker_detection(db,profile,monkeypatch):
    aid,job,inspection,receiver=fixture_setup(db,profile,monkeypatch)
    with receiver as server:
        sid=create_intervention(db,aid,inspection['inspection_id'],_fixture_url=server['url'])
        first=request_command(db,sid,'OPEN');assert request_command(db,sid,'OPEN')==first
        with session_lock(db,sid):
            with pytest.raises((OSError,PermissionError)):
                with session_lock(db,sid):pass
        db.execute("UPDATE autoapply_interventions SET status=?,form_state='CAMPOS_EN_MEMORIA',worker_pid=1,heartbeat=? WHERE id=?",(PAUSED,now(),sid))
        assert worker_alive(session_row(db,sid))
        request_command(db,sid,'CLOSE')
        db.execute("UPDATE autoapply_intervention_commands SET status='DONE' WHERE session_id=?",(sid,))
        request_command(db,sid,'CONTINUE')
        db.execute("UPDATE autoapply_interventions SET heartbeat='2020-01-01T00:00:00+00:00' WHERE id=?",(sid,))
        assert pending_interventions(db)[0]['status']==EXPIRED
        with pytest.raises(PermissionError):request_command(db,sid,'CONTINUE')
        request_command(db,sid,'RECOVER')
        dumped=json.dumps(db.rows('SELECT * FROM autoapply_interventions'))+json.dumps(db.rows('SELECT * FROM autoapply_intervention_commands'))
        assert candidate_snapshot(db)['email'] not in dumped and 'cookie' not in dumped.lower()


def test_fixture_switch_cannot_enable_real_job_or_database(db,profile,monkeypatch):
    aid,job,inspection,receiver=fixture_setup(db,profile,monkeypatch)
    with pytest.raises(PermissionError):create_intervention(db,aid,inspection['inspection_id'])
    with pytest.raises(PermissionError):create_intervention(db,aid,inspection['inspection_id'],_fixture_url='https://example.org/form')
    real={**job,'raw':'{}'}
    with pytest.raises(PermissionError):require_owned_fixture(db,real,'http://127.0.0.1:1234/form')
    assert not db.rows('SELECT * FROM autoapply_interventions')


def test_browser_redirect_is_blocked_before_contacting_restricted_provider(db,profile,monkeypatch):
    aid,job,inspection,receiver=fixture_setup(db,profile,monkeypatch,redirect=True)
    with receiver as server:
        sid=create_intervention(db,aid,inspection['inspection_id'],_fixture_url=server['url'])
        with InteractiveBrowser(db,sid,headless=True) as actor:
            actor.open()
            row=session_row(db,sid)
            assert row['status']=='HOLD' and row['reason_code']=='INDEPENDENT_DESTINATION_REVIEW_REQUIRED'
            assert actor.page.url!='https://redirect-target.invalid/form' and server['stats']['posts']==0


def test_independent_worker_keeps_paused_browser_across_dashboard_reads_then_closes(db,profile,monkeypatch):
    aid,job,inspection,receiver=fixture_setup(db,profile,monkeypatch)
    with receiver as server:
        sid=create_intervention(db,aid,inspection['inspection_id'],_fixture_url=server['url']);request_command(db,sid,'OPEN')
        flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
        child=subprocess.Popen([sys.executable,'-m','corkjobradar.autoapply.interactive_worker','--database',str(db.path),'--session',sid,'--owned-fixture-headless'],
                               cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags)
        try:
            limit=time.monotonic()+20
            while time.monotonic()<limit and session_row(db,sid)['status']!=PAUSED:
                if child.poll() is not None:break
                time.sleep(.1)
            row=session_row(db,sid)
            assert row['status']==PAUSED and row['worker_pid']!=os.getpid() and row['filled_count']==3
            owner_pid=row['worker_pid']  # Windows venv launcher and interpreter PIDs differ.
            for _ in range(3):
                assert pending_interventions(Database(db.path))[0]['worker_available']
                assert session_row(db,sid)['worker_pid']==owner_pid
            with pytest.raises(OSError):
                with session_lock(db,sid):pass
            request_command(db,sid,'FOCUS')
            limit=time.monotonic()+5
            while db.rows("SELECT id FROM autoapply_intervention_commands WHERE session_id=? AND status='PENDING'",(sid,)) and time.monotonic()<limit:time.sleep(.1)
            request_command(db,sid,'CLOSE');assert child.wait(timeout=15)==0
            assert session_row(db,sid)['status']=='CERRADA' and server['stats']['posts']==0
            assert session_row(db,sid)['worker_pid'] is None
            assert pending_interventions(db)[0]['status']==EXPIRED
            assert validate_session(db,sid)['binding']  # Closing before dispatch is recoverable.
        finally:
            if child.poll() is None:
                request_command(db,sid,'CLOSE')
                try:child.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    child.terminate();child.wait(timeout=15)


def test_dashboard_lists_intervention_and_continue_only_enqueues_revalidation(db,profile,monkeypatch):
    from streamlit.testing.v1 import AppTest
    aid,job,inspection,receiver=fixture_setup(db,profile,monkeypatch)
    with receiver as server:
        sid=create_intervention(db,aid,inspection['inspection_id'],_fixture_url=server['url'])
        db.execute("UPDATE autoapply_interventions SET status=?,form_state='CAMPOS_EN_MEMORIA',worker_pid=1,heartbeat=? WHERE id=?",(PAUSED,now(),sid))
        app=AppTest.from_string('from corkjobradar.db import Database\nfrom corkjobradar.autoapply.interventions_ui import render_interventions\nrender_interventions(Database('+repr(str(db.path))+'))').run(timeout=30)
        assert not app.exception and any(PAUSED in e.label for e in app.expander)
        button=next(b for b in app.button if b.label=='CONTINUAR CANDIDATURA');assert not button.disabled
        button.click().run(timeout=30)
        assert not app.exception and db.rows('SELECT command FROM autoapply_intervention_commands')[0]['command']=='CONTINUE'
        assert server['stats']['posts']==0
        assert not db.rows('SELECT * FROM user_actions')


@pytest.mark.parametrize('url,mode',[
 ('https://www.linkedin.com/jobs/view/123/?trk=SECRET','LINKEDIN_MANUAL'),
 ('https://ie.indeed.com/viewjob?jk=0123456789abcdef&tracking=SECRET','INDEED_MANUAL')])
def test_restricted_platform_manual_package_reuses_approved_cv_without_remote_calls(db,profile,monkeypatch,url,mode):
    from test_autoapply_manual_handoff import setup
    from corkjobradar.autoapply.handoff import prepare_handoff,load_handoff,handoff_download
    import corkjobradar.autoapply.handoff as handoff
    job,inspection,doc=setup(db,profile)
    monkeypatch.setattr(handoff,'validate_url',lambda url:url)  # No external DNS or browser.
    db.execute('UPDATE jobs SET url=?,apply_url=? WHERE id=?',(url,url,job['id']))
    result=prepare_handoff(db,job['id'])
    package=load_handoff(db,result['handoff_id'])
    assert package['interaction_mode']==mode and 'SECRET' not in package['target_url']
    assert package['document_id']==doc and handoff_download(db,result['handoff_id']).startswith(b'PK')
    assert not db.rows('SELECT * FROM application_attempts') and not db.rows('SELECT * FROM user_actions')


def test_erasing_profile_queues_browser_close_without_leaking_values(db,profile,monkeypatch):
    from corkjobradar.autoapply.vault import forget_professional_data
    aid,job,inspection,receiver=fixture_setup(db,profile,monkeypatch)
    with receiver as server:
        sid=create_intervention(db,aid,inspection['inspection_id'],_fixture_url=server['url'])
        db.execute('UPDATE autoapply_interventions SET worker_pid=1,heartbeat=? WHERE id=?',(now(),sid))
        forget_professional_data(db,True)
        assert db.rows('SELECT command FROM autoapply_intervention_commands')[0]['command']=='CLOSE'
        assert not candidate_snapshot(db).get('email')
        with pytest.raises(PermissionError):validate_session(db,sid)


def test_v7_additive_migration_preserves_all_old_rows_and_live_check(db):
    old=db.rows("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'autoapply_intervention%'")
    before={r['name']:db.rows('SELECT * FROM '+r['name']) for r in old}
    with db.connect() as con:
        con.executescript('DROP TABLE autoapply_intervention_commands; DROP TABLE autoapply_interventions; PRAGMA user_version=7;')
    reopened=Database(db.path)
    assert reopened.rows('PRAGMA user_version')[0]['user_version']==13
    assert all(reopened.rows('SELECT * FROM '+table)==rows for table,rows in before.items())
    assert reopened.rows('PRAGMA foreign_key_check')==[]
    with pytest.raises(sqlite3.IntegrityError):reopened.execute('UPDATE autoapply_control SET live_enabled=1')
