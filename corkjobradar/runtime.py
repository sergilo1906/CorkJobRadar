"""Durable local supervisor. Own process, single OS lock, no submission transport."""
import ctypes
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from datetime import datetime,timedelta
from .config import ROOT,now,digest
from .db import Database
from .worker import process_lock,worker_lock


def database_path(value):
    p=Path(value).resolve()
    if not p.is_relative_to(ROOT.resolve()) or p.suffix!='.sqlite3':raise ValueError('PROJECT_SQLITE_REQUIRED')
    return p


def process_stamp(pid):
    """Creation time prevents a reused PID from becoming an owner/worker."""
    if not isinstance(pid,int) or pid<=0:return None
    if os.name!='nt':
        try:return Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()[19]
        except (OSError,IndexError):return None
    from ctypes import wintypes
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    kernel.GetProcessTimes.argtypes=[wintypes.HANDLE]+[ctypes.POINTER(wintypes.FILETIME)]*4
    kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
    handle=kernel.OpenProcess(0x1000,False,pid)
    if not handle:return None
    try:
        code=wintypes.DWORD()
        if not kernel.GetExitCodeProcess(handle,ctypes.byref(code)) or code.value!=259:return None
        fields=[wintypes.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle,*[ctypes.byref(f) for f in fields]):return None
        return str((fields[0].dwHighDateTime<<32)|fields[0].dwLowDateTime)
    finally:kernel.CloseHandle(handle)


def alive(pid,stamp):
    return bool(stamp and process_stamp(pid)==stamp)


def state(db):
    return db.rows('SELECT * FROM local_runtime WHERE id=1')[0]


def record(db,kind,code,run_id=None):
    db.execute('INSERT INTO local_runtime_events(occurred_at,kind,code,run_id) VALUES(?,?,?,?)',(now(),kind,code,run_id))


def update(db,**fields):
    if not fields:return
    allowed=set(state(db))-{'id'}
    if not set(fields)<=allowed:raise ValueError('UNKNOWN_RUNTIME_FIELD')
    fields['updated_at']=now()
    db.execute('UPDATE local_runtime SET '+','.join(k+'=?' for k in fields)+' WHERE id=1',tuple(fields.values()))


def lock_free(db,suffix='.worker.lock'):
    try:
        with process_lock(db.path.with_suffix(suffix)):return True
    except OSError:return False


def configure(db,interval_hours,auto_prepare=True,sound=False):
    if isinstance(interval_hours,bool) or not isinstance(interval_hours,(int,float)) or not math.isfinite(interval_hours) or not .25<=interval_hours<=168:raise ValueError('INTERVAL_0_25_TO_168_HOURS_REQUIRED')
    if type(auto_prepare)!=bool or type(sound)!=bool:raise ValueError('BOOLEAN_OPTIONS_REQUIRED')
    with db.transaction() as con:
        con.execute('BEGIN IMMEDIATE')
        row=state(db);fields={'interval_hours':float(interval_hours),'auto_prepare':int(auto_prepare),'sound':int(sound)}
        if row['next_search_at']:fields['next_search_at']=(datetime.fromisoformat(now())+timedelta(hours=interval_hours)).isoformat()
        update(db,**fields);record(db,'CONFIGURATION','LOCAL_ONLY_LIVE_OFF')


def command(db,action,*,search_now=True):
    if action not in {'START','PAUSE','RESUME','STOP','SEARCH_NOW'}:raise ValueError('INVALID_RUNTIME_COMMAND')
    with db.transaction() as con:
        con.execute('BEGIN IMMEDIATE')
        row=state(db)
        # A stale UI/CLI callback must not undo an in-flight pause/stop. Check
        # under the write transaction, not only in the visibility layer.
        if action in {'START','RESUME','SEARCH_NOW'} and row['state'] in {'PAUSING','STOPPING'}:
            raise ValueError('RUNTIME_TRANSITION_IN_PROGRESS')
        if action=='SEARCH_NOW' and row.get('active_kind'):
            raise ValueError('WORK_ALREADY_ACTIVE')
        if action in {'PAUSE','STOP'}:
            update(db,desired='PAUSED' if action=='PAUSE' else 'STOPPED',state='PAUSING' if row['child_pid'] else ('PAUSED' if action=='PAUSE' else 'STOPPED'))
            if row['active_run']:db.execute('UPDATE scan_runs SET cancel_requested=1 WHERE id=?',(row['active_run'],))
        else:
            fields={'desired':'RUNNING','last_error_code':None,'failures':0,'restart_after':None}
            if action=='SEARCH_NOW' or action=='START' and search_now:fields['next_search_at']=now()
            elif not row['next_search_at']:fields['next_search_at']=(datetime.fromisoformat(now())+timedelta(hours=row['interval_hours'])).isoformat()
            update(db,**fields)
        record(db,'COMMAND',action)


def _spawn(db,args,log_name):
    folder=db.path.parent/'runtime-logs';folder.mkdir(exist_ok=True)
    tmp=ROOT/'data/runtime-temp';tmp.mkdir(exist_ok=True)
    env=os.environ.copy();env.update(PYTHONIOENCODING='utf-8',TEMP=str(tmp),TMP=str(tmp))
    with (folder/log_name).open('a',encoding='utf-8') as log:
        return subprocess.Popen([sys.executable,'-m','corkjobradar','local-runtime',*args,'--database',str(db.path.resolve())],cwd=ROOT,
            env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)


def ensure_supervisor(db,owner_pid=None):
    owner_pid=owner_pid or os.getpid();stamp=process_stamp(owner_pid)
    if not stamp or state(db)['desired']=='STOPPED':return False
    try:
        with process_lock(db.path.with_suffix('.runtime-start.lock')):
            update(db,owner_pid=owner_pid,owner_stamp=stamp)
            if not lock_free(db,'.runtime.lock'):return False
            row=state(db);clock=datetime.fromisoformat(now())
            if row['launch_after'] and datetime.fromisoformat(row['launch_after'])>clock:return False
            update(db,launch_after=(clock+timedelta(seconds=15)).isoformat())
            _spawn(db,['serve'],'supervisor.log')
            # Hold the launch lock until the child owns the lifetime lock.
            for _ in range(50):
                if not lock_free(db,'.runtime.lock'):break
                time.sleep(.1)
            return True
    except OSError:return False


def input_fingerprint(db,clock=None):
    clock=clock or datetime.fromisoformat(now())
    data={'hour':clock.isoformat()[:13]}
    for table,columns in (
        ('jobs','id,content_hash,open_status,last_verified_at,possible_duplicate'),
        ('candidate_facts','id,revoked_at'),('candidate_documents','id,approved_at,revoked_at'),
        ('commute_checks','id'),('manual_requirement_reviews','id'),('it_worksite_evidence','id'),
        ('it_selection_origins','id'),('autoapply_form_inspections','id'),('user_actions','id')):
        data[table]=db.rows('SELECT '+columns+' FROM '+table+' ORDER BY id')
    data['interventions']=db.rows('SELECT id,status,reason_code FROM autoapply_interventions ORDER BY id')
    data['sources']=db.rows('SELECT id,status,enabled,permission FROM sources ORDER BY id')
    return digest(data)


def notify(db,kind,key,job_id=None,reference_id=None):
    return db.execute('INSERT OR IGNORE INTO local_runtime_notifications(created_at,kind,job_id,reference_id,dedupe_key) VALUES(?,?,?,?,?)',
                      (now(),kind,job_id,str(reference_id) if reference_id is not None else None,key))


def sync_notifications(db):
    """Persist codes/IDs only. No answers, cookies, challenge tokens or contacts."""
    active=set()
    previous=db.rows('SELECT coalesce(max(id),0) n FROM local_runtime_notifications')[0]['n']
    docs=db.rows('''SELECT id FROM candidate_documents WHERE approved_at IS NOT NULL AND revoked_at IS NULL''')
    if not docs:
        key='APPROVED_CV_REQUIRED';active.add(key);notify(db,key,key)
    for item in db.rows("""SELECT i.id,p.job_id,i.reason_code FROM autoapply_interventions i
                          JOIN application_attempts a ON a.id=i.attempt_id JOIN application_plans p ON p.id=a.plan_id
                          WHERE i.status='INTERVENCION_HUMANA_REQUERIDA'"""):
        key='HUMAN:'+item['id'];active.add(key);notify(db,'HUMAN_VERIFICATION',key,item['job_id'],item['id'])
    for row in db.rows("SELECT job_id,binding_hash,assessment,error_code FROM it_application_queue WHERE workflow_state IN ('INTERVENTION','PENDING')"):
        assessment=json.loads(row['assessment'])
        if assessment.get('it_status')=='CONFIRMED_IT' and 'ESSENTIAL_LEGAL_OR_LICENSE_ANSWER_PENDING' in assessment.get('essential_pending',[]):
            key='ESSENTIAL:'+row['job_id']+':'+row['binding_hash'];active.add(key);notify(db,'ESSENTIAL_ANSWER',key,row['job_id'])
        if row['error_code']=='LOCAL_PREPARATION_REVIEW_REQUIRED':
            key='PREPARATION:'+row['job_id']+':'+row['binding_hash'];active.add(key);notify(db,'PREPARATION_REVIEW',key,row['job_id'])
    for row in db.rows("SELECT id FROM sources WHERE enabled=1 AND status='BLOQUEADA'"):
        key='SOURCE:'+row['id'];active.add(key);notify(db,'SOURCE_ACCESS_REVIEW',key,reference_id=row['id'])
    from .autoapply.forms import load_inspection,answer_plan
    from .autoapply.vault import candidate_snapshot
    candidate=None
    for row in db.rows('SELECT max(id) id FROM autoapply_form_inspections GROUP BY job_id'):
        try:inspection=load_inspection(db,row['id'])
        except (ValueError,PermissionError):continue
        candidate=candidate or candidate_snapshot(db);plan=answer_plan(inspection,candidate)
        required={f['id'] for f in inspection['fields'] if f['required'] and f['type']!='file'}
        if any(f['field'] in required for f in plan['unresolved']):
            key='FORM:'+str(row['id']);active.add(key);notify(db,'ESSENTIAL_ANSWER',key,inspection['job_id'],row['id'])
    for row in db.rows('SELECT id,dedupe_key FROM local_runtime_notifications WHERE resolved_at IS NULL'):
        if row['dedupe_key'] not in active and not row['dedupe_key'].startswith('FAILURE:'):
            db.execute('UPDATE local_runtime_notifications SET resolved_at=? WHERE id=?',(now(),row['id']))
    latest=db.rows('SELECT coalesce(max(id),0) n FROM local_runtime_notifications')[0]['n']
    if latest>previous and state(db)['sound'] and os.name=='nt':
        import winsound
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)


class Supervisor:
    def __init__(self,db,*,clock=None,spawn=None):
        self.db=db;self.clock=clock or (lambda:datetime.fromisoformat(now()));self.spawn=spawn or self._spawn_work
        self.child=None;self.exit_requested=False;self.last_notification_check=0

    def _spawn_work(self,kind,run_id=None):
        args=['work','--kind',kind]
        if run_id is not None:args+=['--run-id',str(run_id)]
        child=_spawn(self.db,args,'work-'+str(run_id or 'preparation')+'.log')
        return child

    def _start(self,kind,run_id=None):
        child=self.spawn(kind,run_id);self.child=child
        update(self.db,child_pid=child.pid,child_stamp=process_stamp(child.pid),active_kind=kind,active_run=run_id,
               state='SEARCHING' if kind=='SCAN' else 'PREPARING',resume_run=None,
               last_error_code=None,
               last_search_started=self.clock().isoformat() if kind=='SCAN' else state(self.db)['last_search_started'])
        record(self.db,'WORK_STARTED',kind,run_id)

    def _finished(self,row):
        clock=self.clock();fields={'child_pid':None,'child_stamp':None,'active_run':None,'active_kind':None}
        failed=bool(self.child and self.child.poll() not in {None,0}) or bool(row['last_error_code'])
        if row['active_kind']=='SCAN' and row['active_run']:
            run=self.db.rows('SELECT * FROM scan_runs WHERE id=?',(row['active_run'],))[0]
            if run['status']=='running':
                failed=True;fields['resume_run']=run['id']
                self.db.execute("UPDATE scan_runs SET status='partial',worker_pid=NULL,message='Local worker interrupted' WHERE id=?",(run['id'],))
            elif run['status']=='cancelled':fields['resume_run']=run['id']
            else:
                fields.update(last_search_run=run['id'],last_search_finished=run['finished_at'] or clock.isoformat(),
                              next_search_at=(clock+timedelta(hours=row['interval_hours'])).isoformat(),resume_run=None,failures=0)
        if failed:
            failures=row['failures']+1;fields.update(failures=failures,last_error_code='WORKER_INTERRUPTED',restart_after=(clock+timedelta(seconds=min(60*2**(failures-1),3600))).isoformat())
            if failures>=3:fields.update(desired='PAUSED',state='ERROR');notify(self.db,'REPEATED_FAILURE','FAILURE:'+str(row['active_run']))
        update(self.db,**fields);record(self.db,'WORK_FINISHED','INTERRUPTED' if failed else 'CHECK_PERSISTED_RESULT',row['active_run']);self.child=None

    def tick(self):
        db=self.db;row=state(db);clock=self.clock()
        if row['last_tick']:
            gap=(clock-datetime.fromisoformat(row['last_tick'])).total_seconds()
            if gap>60:record(db,'TIME_GAP','SUSPEND_OR_SCHEDULING_DELAY')
            if gap < -300:
                update(db,next_search_at=(clock+timedelta(hours=row['interval_hours'])).isoformat());record(db,'CLOCK','CLOCK_MOVED_BACK')
        update(db,heartbeat=clock.isoformat(),last_tick=clock.isoformat())
        if row['child_pid'] and not alive(row['child_pid'],row['child_stamp']):
            self._finished(row);row=state(db)
        if row['desired']!='RUNNING' or self.exit_requested:
            if row['active_run']:db.execute('UPDATE scan_runs SET cancel_requested=1 WHERE id=?',(row['active_run'],))
            update(db,state='STOPPING' if row['child_pid'] else ('STOPPED' if self.exit_requested else row['desired']))
            return
        if row['child_pid']:return
        if row['restart_after'] and datetime.fromisoformat(row['restart_after'])>clock:
            update(db,state='RETRY_WAIT');return
        if not lock_free(db):update(db,state='OTHER_WORKER');return
        active=db.rows("SELECT * FROM scan_runs WHERE status='running' ORDER BY id")
        if active:
            run=active[0]
            if process_stamp(run['worker_pid']) or (clock-datetime.fromisoformat(run['heartbeat'] or run['started_at'])).total_seconds()<30:
                update(db,state='OTHER_WORKER');return
            if json.loads(run['profile']).get('analyzer','basic')!='basic':
                update(db,state='MANUAL_RECOVERY_REQUIRED',last_error_code='ADVANCED_ANALYSIS_REQUIRES_MANUAL_RESUME');return
            # Physical OS lock is free AND no live recorded process; not heartbeat alone.
            update(db,resume_run=run['id']);row=state(db)
        if row['resume_run']:
            rid=row['resume_run']
            with worker_lock(db):
                db.execute("UPDATE task_queue SET status='pending' WHERE run_id=? AND status='running'",(rid,))
                db.execute("UPDATE scan_runs SET status='running',cancel_requested=0,heartbeat=? WHERE id=?",(clock.isoformat(),rid))
            self._start('SCAN',rid);return
        if not row['next_search_at'] or datetime.fromisoformat(row['next_search_at'])<=clock:
            from .junior_discovery import prepare_junior_search
            rid=prepare_junior_search(db,automatic=True);self._start('SCAN',rid);return
        fingerprint=input_fingerprint(db,clock)
        if fingerprint!=row['last_prepare_fingerprint']:
            self._start('PREPARE');return
        update(db,state='WAITING')


def run_work(db,kind,run_id=None):
    from .autoapply.selection_queue import prepare_all_local,refresh_queue
    from .autoapply.vault import candidate_snapshot
    if state(db)['desired']!='RUNNING':return
    if kind=='SCAN':
        from .worker import run_worker
        db._runtime_stop=lambda:state(db)['desired']!='RUNNING' or state(db)['state']=='STOPPING'
        run_worker(db,run_id,respect_blocked=True)
    if state(db)['desired']!='RUNNING' or state(db)['state']=='STOPPING':return
    from .reevaluation import reevaluate_all
    reevaluate_all(db,should_stop=lambda:state(db)['desired']!='RUNNING' or state(db)['state']=='STOPPING')
    if state(db)['desired']!='RUNNING' or state(db)['state']=='STOPPING':return
    if state(db)['auto_prepare'] and candidate_snapshot(db).get('cv_document_id'):
        prepare_all_local(db,should_stop=lambda:state(db)['desired']!='RUNNING' or state(db)['state']=='STOPPING')
    else:refresh_queue(db)
    sync_notifications(db)
    update(db,last_prepare_fingerprint=input_fingerprint(db),last_prepare_at=now())


def serve(db):
    with process_lock(db.path.with_suffix('.runtime.lock')):
        update(db,supervisor_pid=os.getpid(),supervisor_stamp=process_stamp(os.getpid()),launch_after=None)
        manager=Supervisor(db);record(db,'SUPERVISOR','STARTED')
        try:
            while True:
                row=state(db)
                if not alive(row['owner_pid'],row['owner_stamp']):manager.exit_requested=True
                if time.monotonic()-manager.last_notification_check>=30:
                    try:sync_notifications(db)
                    except Exception as exc:record(db,'NOTIFICATION_ERROR',type(exc).__name__)
                    manager.last_notification_check=time.monotonic()
                try:manager.tick()
                except Exception as exc:
                    clock=datetime.fromisoformat(now());row=state(db)
                    code='NO_REVIEWED_SOURCES_AVAILABLE' if str(exc)=='NO_REVIEWED_JUNIOR_SOURCES_ENABLED' else type(exc).__name__
                    update(db,state='ERROR',last_error_code=code,restart_after=(clock+timedelta(seconds=60)).isoformat())
                    record(db,'ERROR',code)
                row=state(db)
                if (manager.exit_requested or row['desired']=='STOPPED') and not row['child_pid']:break
                time.sleep(2)
        finally:
            update(db,supervisor_pid=None,supervisor_stamp=None,state='STOPPED' if state(db)['desired']=='STOPPED' or manager.exit_requested else 'INTERRUPTED')
            record(db,'SUPERVISOR','EXITED_CHECKPOINT_RETAINED')


class Watchdog:
    """Lives in the Streamlit process, independent of browser sessions/reruns."""
    def __init__(self,path,owner_pid=None):
        self.path=database_path(path);self.owner_pid=owner_pid or os.getpid();self.stop_event=threading.Event()
        self.thread=threading.Thread(target=self._loop,name='CorkJobRadar-local-watchdog',daemon=True);self.thread.start()
    def _loop(self):
        previous_error=None
        while not self.stop_event.is_set():
            try:ensure_supervisor(Database(self.path),self.owner_pid)
            except Exception as exc:
                code=type(exc).__name__
                if code!=previous_error:
                    try:record(Database(self.path),'WATCHDOG_ERROR',code)
                    except Exception:pass
                previous_error=code
            self.stop_event.wait(5)
    def close(self):self.stop_event.set()


def snapshot(db):
    row=state(db)
    return {'control':row,'supervisor_alive':alive(row['supervisor_pid'],row['supervisor_stamp']),
            'pending_tasks':db.rows("SELECT status,count(*) n FROM task_queue WHERE status<>'done' GROUP BY status"),
            'queue':db.rows('SELECT workflow_state,count(*) n FROM it_application_queue GROUP BY workflow_state'),
            'prepared':db.rows("SELECT count(*) n FROM it_application_queue WHERE workflow_state='MANUAL_READY'")[0]['n'],
            'confirmed_external':db.rows("SELECT count(*) n FROM application_attempts a JOIN application_plans p ON p.id=a.plan_id WHERE p.environment='LIVE' AND a.state='ENVIADA_CONFIRMADA'")[0]['n'],
            'manual_declarations':db.rows('SELECT count(*) n FROM manual_application_declarations')[0]['n'],
            'notifications':db.rows('SELECT * FROM local_runtime_notifications WHERE resolved_at IS NULL ORDER BY id DESC'),
            'events':db.rows('SELECT * FROM local_runtime_events ORDER BY id DESC LIMIT 25'),'live_enabled':False}


def main(argv=None):
    import argparse
    parser=argparse.ArgumentParser(description='Actividad local Cork Job Radar, LIVE OFF')
    parser.add_argument('action',choices=['serve','work','status','start','pause','resume','stop'])
    parser.add_argument('--database',default=str(ROOT/'data/radar.sqlite3'))
    parser.add_argument('--kind',choices=['SCAN','PREPARE']);parser.add_argument('--run-id',type=int)
    parser.add_argument('--defer-search',action='store_true')
    args=parser.parse_args(argv);db=Database(database_path(args.database))
    if args.action=='work' and (not args.kind or args.kind=='SCAN' and args.run_id is None):parser.error('work requiere kind y run-id para SCAN')
    if args.action=='serve':return serve(db)
    if args.action=='work':
        try:run_work(db,args.kind,args.run_id)
        except Exception as exc:
            update(db,last_error_code=type(exc).__name__);record(db,'WORK_ERROR',type(exc).__name__,args.run_id);return 1
        return 0
    if args.action=='status':print(json.dumps(snapshot(db)));return 0
    command(db,{'start':'START','pause':'PAUSE','resume':'RESUME','stop':'STOP'}[args.action],search_now=not args.defer_search)
    print(json.dumps({'desired':state(db)['desired'],'live_enabled':False}))
    return 0
