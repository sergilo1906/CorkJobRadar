"""Durable human handoff metadata/commands. No cookies, tokens or personal fields."""
from contextlib import contextmanager
from datetime import datetime,timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit
from uuid import uuid4
from zoneinfo import ZoneInfo
from ..config import ROOT,DB_PATH,now,digest
from .browser import FormHold
from .documents import document_bytes
from .forms import load_inspection,answer_plan
from .interaction_modes import interaction_route,EMPLOYER_SITE_ALLOWED,HUMAN_VERIFICATION
from .policy import event,require_live
from .vault import candidate_snapshot

PAUSED='INTERVENCION_HUMANA_REQUERIDA'
EXPIRED='SESION_CADUCADA'
TERMINAL={'PRUEBA_LOCAL_CONFIRMADA','ENVIO_INCIERTO'}


def require_owned_fixture(db,job,url=None):
    raw=job.get('raw') or {}
    if isinstance(raw,str):raw=json.loads(raw)
    path=db.path.resolve()
    if path==Path(DB_PATH).resolve() or path.name!='test.sqlite3' or not path.is_relative_to(ROOT/'data') or raw.get('_synthetic_fixture') is not True:
        raise PermissionError('OWNED_SYNTHETIC_DATABASE_REQUIRED')
    if url is not None:
        p=urlsplit(url)
        if p.scheme!='http' or p.hostname!='127.0.0.1' or not p.port or p.username or p.password or p.query or p.fragment or p.path!='/form':
            raise PermissionError('OWNED_LOOPBACK_FORM_REQUIRED')


def session_row(db,sid):
    rows=db.rows('SELECT * FROM autoapply_interventions WHERE id=?',(sid,))
    if not rows:raise ValueError('INTERVENTION_NOT_FOUND')
    return rows[0]


def context_for(db,attempt_id,inspection_id,fixture_url=None):
    attempt=db.rows('''SELECT a.*,p.job_id,p.environment FROM application_attempts a
                      JOIN application_plans p ON p.id=a.plan_id WHERE a.id=?''',(attempt_id,))
    if not attempt:raise ValueError('APPLICATION_ATTEMPT_REQUIRED')
    attempt=attempt[0];job=db.rows('SELECT * FROM jobs WHERE id=?',(attempt['job_id'],))[0]
    if fixture_url:
        require_owned_fixture(db,job,fixture_url)
        if attempt['environment']!='SIMULATION':raise PermissionError('OWNED_SIMULATION_ONLY')
    else:
        route=interaction_route(job.get('apply_url') or job['url'],source_url=job['url'])
        if route['mode'] not in {EMPLOYER_SITE_ALLOWED,HUMAN_VERIFICATION}:raise PermissionError('DESTINATION_AUTOMATION_NOT_ALLOWED')
        # Filling/uploads can already transmit personal data. LIVE OFF forbids
        # even opening this personal-data session at a public destination.
        require_live(db)
    from .final_gate import final_submission_gate
    binding=final_submission_gate(db,attempt_id,inspection_id,_owned_local_fixture=bool(fixture_url))
    inspection=load_inspection(db,inspection_id);candidate=candidate_snapshot(db)
    plan=answer_plan(inspection,candidate)
    if plan['unresolved']:raise FormHold('UNVERIFIED_QUESTIONS')
    return {'binding':binding,'binding_hash':digest(binding),'inspection':inspection,'candidate':candidate,
            'mapping':plan['mapping'],'target_url':fixture_url or binding['target_url'],'job':job}


def create_intervention(db,attempt_id,inspection_id,*,_fixture_url=None):
    with db.transaction() as con:
        if not con.in_transaction:con.execute('BEGIN IMMEDIATE')
        ctx=context_for(db,attempt_id,inspection_id,_fixture_url)
        previous=db.rows('SELECT * FROM autoapply_interventions WHERE attempt_id=?',(attempt_id,))
        if previous:
            row=previous[0]
            if row['inspection_id']!=inspection_id or row['fixture_url']!=_fixture_url or row['binding_hash']!=ctx['binding_hash']:
                raise PermissionError('INTERVENTION_BINDING_CHANGED')
            return row['id']
        sid=uuid4().hex
        db.execute('''INSERT INTO autoapply_interventions(id,attempt_id,inspection_id,created_at,updated_at,status,
                      reason_code,form_state,binding_hash,fixture_url) VALUES(?,?,?,?,?,?,?,?,?,?)''',
                   (sid,attempt_id,inspection_id,now(),now(),'PREPARADA','NOT_OPENED','SIN_ABRIR',ctx['binding_hash'],_fixture_url))
        event(db,'INTERVENTION_PREPARED',{'session_id':sid,'external':not bool(_fixture_url)},attempt_id=attempt_id)
        return sid


def validate_session(db,sid):
    row=session_row(db,sid)
    if row['submission_started'] or row['status'] in TERMINAL:raise PermissionError('NO_AUTOMATIC_RETRY_AFTER_DISPATCH')
    ctx=context_for(db,row['attempt_id'],row['inspection_id'],row['fixture_url'])
    if ctx['binding_hash']!=row['binding_hash']:raise PermissionError('INTERVENTION_VERSIONS_CHANGED')
    db.execute('UPDATE autoapply_interventions SET last_verified_at=? WHERE id=?',(now(),sid))
    return ctx


def update_session(db,sid,status,code,form_state,filled_count=None):
    # Only application-defined codes, never a browser exception/body/URL.
    if not all(c.isupper() or c.isdigit() or c=='_' for c in code):raise ValueError('SAFE_INTERVENTION_CODE_REQUIRED')
    row=session_row(db,sid)
    db.execute('''UPDATE autoapply_interventions SET status=?,reason_code=?,form_state=?,updated_at=?,
                  filled_count=COALESCE(?,filled_count) WHERE id=?''',(status,code,form_state,now(),filled_count,sid))
    if row['status']!=status or row['reason_code']!=code:
        event(db,'HUMAN_SESSION_STATE',{'session_id':sid,'code':code,'state':status},attempt_id=row['attempt_id'])


def worker_alive(row,clock=None):
    try:
        heartbeat=datetime.fromisoformat(row['heartbeat'])
        return bool(row['worker_pid'] and timedelta(0)<=(clock or datetime.now(ZoneInfo('Europe/Dublin')))-heartbeat<timedelta(seconds=20))
    except (TypeError,ValueError):return False


def pending_interventions(db):
    rows=db.rows('''SELECT s.*,j.company,j.title,j.url,j.apply_url FROM autoapply_interventions s
                   JOIN application_attempts a ON a.id=s.attempt_id JOIN application_plans p ON p.id=a.plan_id
                   JOIN jobs j ON j.id=p.job_id ORDER BY s.updated_at DESC''')
    for row in rows:
        row['worker_available']=worker_alive(row)
        if row['status'] not in TERMINAL and row['form_state']!='SIN_ABRIR' and not row['worker_available']:
            row.update(status=EXPIRED,reason_code='BROWSER_WORKER_UNAVAILABLE',form_state='RECONSTRUIR_CAMPOS_Y_VERIFICACION')
    return rows


def request_command(db,sid,command):
    if command not in {'OPEN','CONTINUE','RECOVER','FOCUS','CLOSE'}:raise ValueError('UNKNOWN_INTERVENTION_COMMAND')
    with db.transaction() as con:
        if not con.in_transaction:con.execute('BEGIN IMMEDIATE')
        row=session_row(db,sid)
        if command not in {'CLOSE','FOCUS'}:validate_session(db,sid)
        if command=='CONTINUE' and (row['status']!=PAUSED or not worker_alive(row)):
            raise PermissionError('OPEN_PAUSED_SESSION_REQUIRED')
        if command=='RECOVER' and row['submission_started']:raise PermissionError('UNCERTAIN_SUBMISSION_NO_RETRY')
        pending=db.rows("SELECT id,command FROM autoapply_intervention_commands WHERE session_id=? AND status='PENDING'",(sid,))
        if pending:
            if pending[0]['command']==command:return pending[0]['id']
            if command!='CLOSE' and not (command in {'OPEN','RECOVER'} and not worker_alive(row)):
                raise PermissionError('INTERVENTION_COMMAND_ALREADY_PENDING')
            db.execute("UPDATE autoapply_intervention_commands SET status='CANCELLED',processed_at=? WHERE id=?",(now(),pending[0]['id']))
        return db.execute('INSERT INTO autoapply_intervention_commands(session_id,command,requested_at) VALUES(?,?,?)',(sid,command,now()))


@contextmanager
def session_lock(db,sid):
    if not __import__('re').fullmatch('[a-f0-9]{32}',sid):raise ValueError('INVALID_SESSION_ID')
    # Reuse the OS locking primitive on a per-session path, not the scan lock.
    from ..worker import worker_lock
    class LockTarget:path=db.path.parent/('interactive-'+sid+'.sqlite3')
    with worker_lock(LockTarget()):yield


def launch_session(db,sid,command='OPEN'):
    # Validate before starting any process. Two racing launchers are serialized
    # by the OS session lock; the second worker exits without opening a browser.
    validate_session(db,sid);row=session_row(db,sid)
    if row['fixture_url']:raise PermissionError('LOCAL_FIXTURE_WORKER_TEST_ONLY')
    if worker_alive(row):
        request_command(db,sid,'FOCUS' if command=='OPEN' else command)
        return {'session_id':sid,'worker_reused':True}
    request_command(db,sid,command)
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    child=subprocess.Popen([sys.executable,'-m','corkjobradar.autoapply.interactive_worker','--database',str(db.path),'--session',sid],
                           cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags)
    return {'session_id':sid,'worker_reused':False,'pid':child.pid}
