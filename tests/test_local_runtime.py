"""Durable scheduling, physical Windows locks, recovery and no live dispatch."""
from datetime import datetime,timedelta
import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import time
import pytest
from corkjobradar.config import now
from corkjobradar.db import Database
from corkjobradar import runtime as rt
from corkjobradar.worker import worker_lock,create_run,enqueue,run_worker
from conftest import source,client


def setup_manager(db,monkeypatch):
    clock=[datetime.fromisoformat(now())+timedelta(minutes=1)]
    live={os.getpid()};launched=[]
    original=rt.process_stamp
    monkeypatch.setattr(rt,'process_stamp',lambda pid:'TEST_STAMP' if pid in live and pid!=os.getpid() else original(pid) if pid==os.getpid() else None)
    def spawn(kind,rid):
        pid=800000+len(launched);live.add(pid)
        child=SimpleNamespace(pid=pid,poll=lambda:None if pid in live else 0)
        launched.append((kind,rid,child));return child
    manager=rt.Supervisor(db,clock=lambda:clock[0],spawn=spawn)
    return manager,clock,live,launched


def future_wait(db,clock):
    rt.update(db,desired='RUNNING',next_search_at=(clock+timedelta(hours=6)).isoformat(),last_prepare_fingerprint=rt.input_fingerprint(db,clock))


def test_defaults_are_off_no_windows_startup_or_live_approval(db):
    row=rt.state(db)
    assert row['desired']=='STOPPED' and row['interval_hours']==6
    assert rt.snapshot(db)['live_enabled'] is False
    assert not rt.ensure_supervisor(db)
    assert not db.rows('SELECT * FROM autoapply_policies')
    assert db.rows('SELECT live_enabled FROM autoapply_control')[0]['live_enabled']==0


@pytest.mark.parametrize('value',[0,-1,169,float('nan'),float('inf'),True,'6'])
def test_interval_validation(db,value):
    with pytest.raises(ValueError):rt.configure(db,value)


def test_commands_and_settings_persist_across_restart_without_enabling_live(db):
    rt.configure(db,2.5,True,False);rt.command(db,'START',search_now=False)
    reopened=Database(db.path);row=rt.state(reopened)
    assert row['desired']=='RUNNING' and row['interval_hours']==2.5 and row['next_search_at']
    rt.command(reopened,'PAUSE');assert rt.state(db)['desired']=='PAUSED'
    rt.command(db,'RESUME');assert rt.state(db)['desired']=='RUNNING'
    rt.command(db,'STOP');assert rt.state(db)['desired']=='STOPPED'
    assert not db.rows('SELECT * FROM application_attempts')


def test_sleep_gap_coalesces_overdue_searches_and_never_starts_second_child(db,profile,monkeypatch):
    manager,clock,live,launched=setup_manager(db,monkeypatch)
    s=source(db,'greenhouse',sid='synthetic')
    monkeypatch.setattr('corkjobradar.junior_discovery.source_catalog',lambda:[s])
    future_wait(db,clock[0]);manager.tick();assert not launched
    clock[0]+=timedelta(hours=24);manager.tick()
    assert len(launched)==1 and launched[0][0]=='SCAN'
    assert len(db.rows('SELECT * FROM scan_runs'))==1
    clock[0]+=timedelta(hours=24);manager.tick();assert len(launched)==1
    assert db.rows("SELECT * FROM local_runtime_events WHERE kind='TIME_GAP'")


def test_complete_search_schedules_from_completion_and_preserves_history(db,monkeypatch):
    manager,clock,live,launched=setup_manager(db,monkeypatch)
    s=source(db,'greenhouse',sid='synthetic');monkeypatch.setattr('corkjobradar.junior_discovery.source_catalog',lambda:[s])
    rt.command(db,'START');manager.tick();rid=launched[0][1]
    clock[0]+=timedelta(minutes=8)
    db.execute("UPDATE scan_runs SET status='completed',finished_at=? WHERE id=?",(clock[0].isoformat(),rid))
    rt.update(db,last_prepare_fingerprint=rt.input_fingerprint(db,clock[0]))
    live.remove(launched[0][2].pid);manager.tick();row=rt.state(db)
    assert datetime.fromisoformat(row['next_search_at'])==clock[0]+timedelta(hours=6)
    assert row['last_search_run']==rid and row['active_run'] is None
    assert row['state']=='WAITING' and len(launched)==1


def test_pause_stop_and_restart_keep_cursor_pending_tasks_and_resume_same_run(db,monkeypatch):
    manager,clock,live,launched=setup_manager(db,monkeypatch)
    s=source(db,'greenhouse',sid='synthetic');monkeypatch.setattr('corkjobradar.junior_discovery.source_catalog',lambda:[s])
    rt.command(db,'START');manager.tick();rid=launched[0][1]
    db.execute('UPDATE source_runs SET cursor=? WHERE run_id=?',('KEEP_CURSOR',rid))
    enqueue(db,rid,None,None,'health');db.execute("UPDATE task_queue SET status='running'")
    rt.command(db,'PAUSE');manager.tick();assert db.rows('SELECT cancel_requested FROM scan_runs')[0]['cancel_requested']==1
    db.execute("UPDATE scan_runs SET status='cancelled',worker_pid=NULL WHERE id=?",(rid,))
    live.remove(launched[0][2].pid);manager.tick();assert rt.state(db)['resume_run']==rid
    rt.command(db,'STOP');manager.tick()
    reopened=Database(db.path);rt.command(reopened,'RESUME');manager.tick()
    assert launched[-1][1]==rid and len(db.rows('SELECT * FROM scan_runs'))==1
    assert db.rows('SELECT cursor FROM source_runs')[0]['cursor']=='KEEP_CURSOR'
    assert db.rows('SELECT status FROM task_queue')[0]['status']=='pending'


def test_stale_heartbeat_never_steals_os_lock_or_live_process(db,monkeypatch):
    manager,clock,live,launched=setup_manager(db,monkeypatch)
    rt.command(db,'START')
    with worker_lock(db):manager.tick()
    assert not launched and rt.state(db)['state']=='OTHER_WORKER'
    rid=create_run(db)
    db.execute('UPDATE scan_runs SET worker_pid=?,heartbeat=? WHERE id=?',(os.getpid(),'2000-01-01T00:00:00+00:00',rid))
    manager.tick();assert not launched and rt.state(db)['state']=='OTHER_WORKER'


def test_crash_uses_backoff_then_reuses_pending_run_without_losing_tasks(db,monkeypatch):
    manager,clock,live,launched=setup_manager(db,monkeypatch)
    s=source(db,'greenhouse',sid='synthetic');monkeypatch.setattr('corkjobradar.junior_discovery.source_catalog',lambda:[s])
    rt.command(db,'START');manager.tick();rid=launched[0][1]
    live.remove(launched[0][2].pid);manager.tick()
    assert rt.state(db)['failures']==1 and rt.state(db)['state']=='RETRY_WAIT'
    manager.tick();assert len(launched)==1
    clock[0]+=timedelta(seconds=61);manager.tick()
    assert len(launched)==2 and launched[1][1]==rid


def test_blocked_sources_are_not_retried_automatically(db,profile,monkeypatch):
    from corkjobradar.junior_discovery import prepare_junior_search
    s=source(db,'greenhouse',sid='synthetic');monkeypatch.setattr('corkjobradar.junior_discovery.source_catalog',lambda:[s])
    db.execute("UPDATE sources SET status='BLOQUEADA'")
    with pytest.raises(RuntimeError,match='NO_REVIEWED'):prepare_junior_search(db,automatic=True)
    rid=create_run(db);db.execute("UPDATE source_runs SET status='blocked'")
    enqueue(db,rid,s['id'],None,'detail',{})
    web=client(profile,lambda req:pytest.fail('BLOCKED_SOURCE_MUST_NOT_BE_REQUESTED'),db)
    run_worker(db,rid,web,respect_blocked=True)
    assert db.rows('SELECT status FROM source_runs')[0]['status']=='blocked'
    assert db.rows('SELECT status FROM task_queue')[0]['status']=='retry'


def test_clock_moving_backward_does_not_stall_forever_or_launch_storm(db,monkeypatch):
    manager,clock,live,launched=setup_manager(db,monkeypatch)
    future_wait(db,clock[0]);manager.tick();clock[0]-=timedelta(days=1);manager.tick()
    assert not any(kind=='SCAN' for kind,_,_ in launched)
    assert datetime.fromisoformat(rt.state(db)['next_search_at'])==clock[0]+timedelta(hours=6)


def test_notifications_are_persistent_deduplicated_read_is_not_resolution(db,profile):
    rt.sync_notifications(db);rt.sync_notifications(db)
    rows=db.rows('SELECT * FROM local_runtime_notifications');assert len(rows)==1 and rows[0]['kind']=='APPROVED_CV_REQUIRED'
    db.execute('UPDATE local_runtime_notifications SET acknowledged_at=?',(now(),));rt.sync_notifications(db)
    assert len(db.rows('SELECT * FROM local_runtime_notifications'))==1
    assert db.rows('SELECT resolved_at FROM local_runtime_notifications')[0]['resolved_at'] is None
    assert not db.rows('SELECT * FROM candidate_documents')


def test_required_form_question_not_optional_notifies_without_storing_values(db,profile):
    from test_autoapply_public_forms import inspected,schema
    from test_autoapply_vault import populate
    populate(db);data=schema();data['questions'].append({'label':'Required unknown answer','required':True,'fields':[{'name':'custom','type':'input_text'}]})
    job,inspection=inspected(db,profile,data)
    rt.sync_notifications(db)
    rows=db.rows("SELECT * FROM local_runtime_notifications WHERE kind='ESSENTIAL_ANSWER'")
    assert len(rows)==1 and rows[0]['job_id']==job['id']
    assert 'synthetic@example.invalid' not in json.dumps(db.rows('SELECT * FROM local_runtime_notifications'))


def test_windows_process_identity_and_reused_pid_protection():
    stamp=rt.process_stamp(os.getpid());assert stamp and rt.alive(os.getpid(),stamp)
    assert not rt.alive(os.getpid(),'WRONG_CREATION_TIME') and rt.process_stamp(-1) is None


def wait_until(predicate,seconds=20):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if predicate():return
        time.sleep(.15)
    raise AssertionError('LOCAL_PROCESS_DID_NOT_REACH_EXPECTED_STATE')


def test_actual_windows_supervisor_singleton_recovers_after_process_termination(db):
    rt.command(db,'START',search_now=False)
    rt.update(db,last_prepare_fingerprint=rt.input_fingerprint(db),owner_pid=os.getpid(),owner_stamp=rt.process_stamp(os.getpid()))
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:rt.ensure_supervisor(db),range(2)))
        wait_until(lambda:rt.state(db)['supervisor_pid'] is not None)
        assert sum(results)==1
        row=rt.state(db);pid=row['supervisor_pid'];stamp=row['supervisor_stamp']
        assert rt.alive(pid,stamp) and not rt.lock_free(db,'.runtime.lock')
        # Only the process created for this isolated project test is terminated.
        assert db.path.name=='test.sqlite3' and rt.alive(pid,stamp)
        os.kill(pid,15)
        wait_until(lambda:not rt.alive(pid,stamp))
        rt.update(db,launch_after=None)
        assert rt.ensure_supervisor(db)
        wait_until(lambda:rt.state(db)['supervisor_pid'] not in {None,pid})
        assert rt.state(db)['desired']=='RUNNING'
    finally:
        rt.command(db,'STOP')
        wait_until(lambda:rt.lock_free(db,'.runtime.lock'))


def test_additive_migration_retains_old_rows_live_off_and_backup(db):
    old=db.rows('SELECT * FROM autoapply_control')
    for table in ['local_runtime_notifications','local_runtime_events','local_runtime']:db.execute('DROP TABLE '+table)
    db.execute('PRAGMA user_version=11');reopened=Database(db.path)
    assert reopened.rows('SELECT * FROM autoapply_control')==old and rt.state(reopened)['desired']=='STOPPED'
    assert not reopened.rows('PRAGMA foreign_key_check')
    with pytest.raises(sqlite3.IntegrityError):reopened.execute('UPDATE autoapply_control SET live_enabled=1')


def test_startup_offer_generates_only_a_download_not_installation(db):
    from corkjobradar.runtime_ui import startup_script
    payload=startup_script().decode('utf-16')
    assert 'pythonw.exe' in payload and 'iniciar_local.py' in payload
    assert rt.state(db)['desired']=='STOPPED'


def test_pending_advanced_analysis_needs_manual_resource_review(db,monkeypatch):
    manager,clock,live,launched=setup_manager(db,monkeypatch);rt.command(db,'START')
    rid=create_run(db,profile_override={'analyzer':'llama'})
    db.execute('UPDATE scan_runs SET heartbeat=? WHERE id=?',('2000-01-01T00:00:00+00:00',rid))
    manager.tick();assert not launched and rt.state(db)['state']=='MANUAL_RECOVERY_REQUIRED'


def test_launcher_does_not_reuse_unverified_port_or_install_startup(db,monkeypatch):
    from scripts import iniciar_local as launcher
    monkeypatch.setattr(launcher,'Database',lambda:db)
    monkeypatch.setattr(launcher,'port_open',lambda:True)
    monkeypatch.setattr(launcher,'verified_port_owner',lambda row:False)
    with pytest.raises(RuntimeError,match='OWNER_NOT_VERIFIED'):launcher.main()


def test_runtime_preparation_reuses_current_form_and_approved_answers_without_sending(db,profile,monkeypatch):
    from test_autoapply_public_forms import inspected,schema
    from test_autoapply_vault import populate
    from test_it_50km_selection import approve_synthetic_cv
    from corkjobradar.autoapply.vault import approve_fact
    from corkjobradar.autoapply import handoff
    populate(db);approve_fact(db,'linkedin_url','https://www.linkedin.com/in/synthetic-only/','SYNTHETIC',True)
    approve_synthetic_cv(db);data=schema()
    data['questions'].append({'label':'Required unknown answer','required':True,'fields':[{'name':'unknown','type':'input_text'}]})
    job,inspection=inspected(db,profile,data)
    monkeypatch.setattr(handoff,'validate_url',lambda url:url)
    rt.command(db,'START',search_now=False);rt.run_work(db,'PREPARE')
    row=db.rows('SELECT * FROM it_application_queue')[0]
    packet=handoff.load_handoff(db,row['handoff_id'])
    assert packet['inspection_id']==inspection['inspection_id']
    assert any(a['answer']=='synthetic@example.invalid' for a in packet['verified_answers'])
    assert any(a['answer']=='https://www.linkedin.com/in/synthetic-only/' for a in packet['verified_answers'])
    assert any(q['field']=='unknown' for q in packet['unresolved_questions'])
    assert db.rows("SELECT * FROM local_runtime_notifications WHERE kind='ESSENTIAL_ANSWER'")
    assert not db.rows('SELECT * FROM application_attempts') and not db.rows('SELECT * FROM user_actions')


def test_bulk_preparation_keeps_remote_separate_without_additional_authorization(db,profile):
    from test_it_50km_selection import placed,approve_synthetic_cv
    from corkjobradar.autoapply.selection_queue import prepare_all_local
    job=placed(db,profile);approve_synthetic_cv(db)
    db.execute("UPDATE jobs SET mode='REMOTE',location='Remote Ireland' WHERE id=?",(job['id'],))
    counts=prepare_all_local(db)
    assert counts['manual_ready']==0 and counts['intervention']==1
    row=db.rows('SELECT * FROM it_application_queue')[0]
    assert row['error_code']=='REMOTE_ADDITIONAL_AUTHORIZATION_REQUIRED'
    assert not db.rows('SELECT * FROM manual_application_handoffs')
