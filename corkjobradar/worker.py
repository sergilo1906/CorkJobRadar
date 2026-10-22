import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from .config import ROOT, now, load_profile
from .db import Database
from .http import WebClient, AccessBlocked, IncompleteSource
from .adapters import make_adapter
from .models import Job
from .repository import save_job, unpack_job
from .analysis import analyze_job
from .verification import evidence_status, record_verification, reconcile_absences, verify_job

@contextmanager
def process_lock(path):
    handle = path.open('a+b')
    handle.seek(0)
    if path.stat().st_size == 0:
        handle.write(b'0')
        handle.flush()
    handle.seek(0)
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield
    finally:
        handle.close()


@contextmanager
def worker_lock(db):
    with process_lock(db.path.with_suffix('.worker.lock')):
        yield

def create_run(db, source_ids=None, kind='scan', profile_override=None):
    with db.connect() as con:
        if not con.in_transaction:con.execute('BEGIN IMMEDIATE')
        active = con.execute("SELECT id FROM scan_runs WHERE status='running'").fetchone()
        if active:
            raise RuntimeError(f"Ya hay una ejecución activa: {active['id']}. Cancelar o reanudar antes de iniciar otra")
        run_id = con.execute('INSERT INTO scan_runs(started_at,status,profile,heartbeat) VALUES(?,?,?,?)',
                             (now(),'running',json.dumps(profile_override or load_profile(),ensure_ascii=False),now())).lastrowid
        if kind == 'scan':
            for source in con.execute('SELECT * FROM sources WHERE enabled=1'):
                if source_ids and source['id'] not in source_ids:
                    continue
                from .sources import query_signature
                con.execute('INSERT INTO source_runs(run_id,source_id,source_snapshot,query_signature) VALUES(?,?,?,?)',
                            (run_id,source['id'],json.dumps(dict(source),ensure_ascii=False),query_signature(dict(source))))
        elif kind in {'analyze','verify'}:
            for row in con.execute('SELECT id FROM jobs'):
                con.execute('INSERT INTO task_queue(run_id,job_id,kind,updated_at) VALUES(?,?,?,?)',
                            (run_id,row['id'],kind,now()))
    return run_id

def enqueue(db, run_id, source_id, job_id, kind, payload=None):
    if not db.rows('SELECT id FROM task_queue WHERE run_id=? AND source_id IS ? AND job_id=? AND kind=?',
                   (run_id,source_id,job_id,kind)):
        db.execute('INSERT INTO task_queue(run_id,source_id,job_id,kind,payload,updated_at) VALUES(?,?,?,?,?,?)',
                   (run_id,source_id,job_id,kind,json.dumps(payload or {},ensure_ascii=False),now()))

def cancelled(db,run_id):
    stop=getattr(db,'_runtime_stop',None)
    if stop and stop():db.execute('UPDATE scan_runs SET cancel_requested=1 WHERE id=?',(run_id,))
    clock=time.monotonic()
    if clock-getattr(db,'_last_worker_heartbeat',0)>3:
        db.execute('UPDATE scan_runs SET heartbeat=? WHERE id=?',(now(),run_id))
        db._last_worker_heartbeat=clock
    return bool(db.rows('SELECT cancel_requested FROM scan_runs WHERE id=?',(run_id,))[0]['cancel_requested'])

def scan_source(db, run_id, sr, client, profile):
    source = db.rows('SELECT * FROM sources WHERE id=?',(sr['source_id'],))[0]
    if not source['enabled'] or source['permission'] not in {'PUBLIC_API_DOCUMENTADA','HTML_PUBLICO_REVISADO'}:
        raise AccessBlocked('Fuente no activada con método de acceso documentado')
    if sr.get('source_snapshot'):
        source=json.loads(sr['source_snapshot'])
    else:
        # Legacy runs keep their history but cannot prove their original configuration.
        db.event('LEGACY_QUERY_UNKNOWN',{'source':source['id'],'reason':'Ejecución histórica sin configuración congelada'},run_id)
    adapter = make_adapter(source,client,profile)
    db.execute("UPDATE source_runs SET status='running',started_at=COALESCE(started_at,?) WHERE id=?",(now(),sr['id']))
    final = None
    for page in adapter.discover(sr['cursor']):
        # Guardar todos antes de puntuar o decidir la profundidad del análisis.
        for job in page.jobs:
            with db.transaction():
                job_id = save_job(db,source['id'],job,run_id,profile)
                if job.raw.get('_parse_error'):
                    db.error(source['id'],'PARSE_RECORD',job.raw['_parse_error'],run_id,job_id)
                    db.execute("UPDATE jobs SET analysis_status='ERROR' WHERE id=?",(job_id,))
                    continue
                saved = db.rows('SELECT * FROM jobs WHERE id=?',(job_id,))[0]
                if saved['scope'] != 'FUERA_DE_ALCANCE':
                    if not job.detail_complete:
                        enqueue(db,run_id,source['id'],job_id,'detail',job.model_dump())
                    else:
                        enqueue(db,run_id,source['id'],job_id,'analyze')
                status,evidence = evidence_status(job.model_dump())
                record_verification(db,job_id,source['id'],status,evidence)
        observed = db.rows('SELECT count(*) AS n FROM run_jobs WHERE run_id=? AND source_id=?',(run_id,source['id']))[0]['n']
        db.execute('''UPDATE source_runs SET pages_visited=pages_visited+1,expected_total=?,observed=?,cursor=?,pagination_complete=? WHERE id=?''',
                   (page.expected_total,observed,page.cursor,None if page.complete is None else int(page.complete),sr['id']))
        db.event('PAGE',{'source':source['id'],'records':len(page.jobs),'cursor':page.cursor,'evidence':page.evidence},run_id)
        final = page
        if cancelled(db,run_id):
            return
    complete = final is not None and final.complete is True
    if db.rows("SELECT id FROM source_errors WHERE run_id=? AND source_id=? AND kind='PARSE_RECORD'",(run_id,source['id'])):
        complete=False
    if final and final.expected_total is not None:
        observed = db.rows('SELECT observed FROM source_runs WHERE id=?',(sr['id'],))[0]['observed']
        complete = complete and observed == final.expected_total
    if complete:
        reconcile_absences(db,run_id,source['id'])
        previous=db.rows("SELECT observed FROM source_runs WHERE source_id=? AND run_id<>? AND status='completed' ORDER BY id DESC LIMIT 1",(source['id'],run_id))
        current=db.rows('SELECT observed FROM source_runs WHERE id=?',(sr['id'],))[0]['observed']
        if previous and previous[0]['observed']>0 and abs(current-previous[0]['observed'])/previous[0]['observed']>.5:
            db.event('SOURCE_COUNT_ANOMALY',{'source':source['id'],'previous':previous[0]['observed'],'current':current,
                                          'warning':'Variación superior al 50%; revisar cambios de consulta/estructura'},run_id)
    db.execute('UPDATE source_runs SET status=?,finished_at=?,message=? WHERE id=?',
               ('completed' if complete else 'partial',now(),'Listado completo demostrado' if complete else 'Fin de paginación no demostrado',sr['id']))
    db.execute('UPDATE sources SET status=?,checked_at=?,last_success=CASE WHEN ? THEN ? ELSE last_success END WHERE id=?',
               ('ACCESIBLE' if complete else 'PARCIAL',now(),complete,now(),source['id']))

def process_task(db,task,client,profile):
    payload = json.loads(task['payload'])
    if task['kind'] == 'health':
        from .sources import health_sources
        health_sources(db,client,profile)
    elif task['kind'] == 'discover':
        from .discovery import start_discovery,resume_discovery
        rid=payload.get('discovery_id') or start_discovery(db,payload['url'])
        resume_discovery(db,rid,client,profile.get('discovery_max_pages',20))
    elif task['kind'] == 'detail':
        source = db.rows('SELECT * FROM sources WHERE id=?',(task['source_id'],))[0]
        if not source['enabled'] or source['permission'] not in {'PUBLIC_API_DOCUMENTADA','HTML_PUBLICO_REVISADO'}:
            raise AccessBlocked('Permiso de la fuente retirado; detalle pendiente')
        frozen=db.rows('SELECT source_snapshot FROM source_runs WHERE run_id=? AND source_id=?',(task['run_id'],task['source_id']))
        if frozen and frozen[0]['source_snapshot']:
            source=json.loads(frozen[0]['source_snapshot'])
        adapter = make_adapter(source,client,profile)
        job = adapter.fetch_detail(payload)
        job_id = save_job(db,source['id'],job,task['run_id'],profile)
        for attachment in job.raw.get('attachments',[]):
            if attachment.get('status') == 'REVISION_MANUAL':
                db.error(source['id'],'DOCUMENT_PENDING',attachment.get('url','') + ': ' + attachment.get('error',''),task['run_id'],job_id)
        status,evidence = evidence_status(job.model_dump())
        record_verification(db,job_id,source['id'],status,evidence)
        # Aun un texto incompleto recibe análisis básico explícito.
        enqueue(db,task['run_id'],source['id'],job_id,'analyze')
    elif task['kind'] == 'analyze':
        analyze_job(db,task['job_id'],profile)
    elif task['kind'] == 'verify':
        status=verify_job(db,task['job_id'],client)
        if status=='ACCESS_BLOCKED':
            from urllib.parse import urlsplit
            job=db.rows('SELECT url,apply_url FROM jobs WHERE id=?',(task['job_id'],))[0]
            domain=urlsplit(job['apply_url'] or job['url']).netloc
            for pending in db.rows("SELECT t.id,j.url,j.apply_url FROM task_queue t JOIN jobs j ON j.id=t.job_id WHERE t.run_id=? AND t.kind='verify' AND t.status='pending'",(task['run_id'],)):
                if urlsplit(pending['apply_url'] or pending['url']).netloc==domain:
                    db.execute("UPDATE task_queue SET status='retry',error=? WHERE id=?",('Dominio de verificación suspendido tras bloqueo: '+domain,pending['id']))
    elif task['kind'] == 'import_url':
        from .imports import import_url
        import_url(db,payload['url'],client,profile,task['run_id'])
    elif task['kind']=='transit_refresh':
        from .transit import refresh_bus_data
        db.event('TRANSIT_REFRESH',refresh_bus_data(),task['run_id'])
    else:
        raise ValueError('Tipo de tarea desconocido')

def run_worker(db,run_id,client=None,*,respect_blocked=False):
    with worker_lock(db):
        run = db.rows('SELECT * FROM scan_runs WHERE id=?',(run_id,))
        if not run:
            raise ValueError('Ejecución inexistente')
        profile = json.loads(run[0]['profile'])
        profile['_run_id']=run_id
        own_client = client is None
        client = client or WebClient(profile,db)
        from contextlib import ExitStack
        resources=ExitStack()
        try:
            if profile.get('analyzer')=='llama':
                from .local_model import local_server
                try:
                    info=resources.enter_context(local_server())
                    db.event('LOCAL_MODEL_STARTED',info,run_id)
                except Exception as exc:
                    db.error(None,'LOCAL_MODEL_START',str(exc),run_id)
                    profile['_local_model_unavailable']=str(exc)
            db.execute("UPDATE scan_runs SET status='running',finished_at=NULL,cancel_requested=0,worker_pid=?,heartbeat=? WHERE id=?",(os.getpid(),now(),run_id))
            db.execute("UPDATE task_queue SET status='pending' WHERE run_id=? AND status='running'",(run_id,))
            for sr in db.rows("SELECT * FROM source_runs WHERE run_id=? AND status<>'completed' ORDER BY id",(run_id,)):
                if cancelled(db,run_id):
                    break
                if respect_blocked and (sr['status']=='blocked' or db.rows('SELECT status FROM sources WHERE id=?',(sr['source_id'],))[0]['status']=='BLOQUEADA'):
                    db.execute("UPDATE source_runs SET status='blocked',message='Manual access review required' WHERE id=?",(sr['id'],))
                    continue
                try:
                    scan_source(db,run_id,sr,client,profile)
                except Exception as exc:
                    blocked = isinstance(exc,AccessBlocked)
                    db.error(sr['source_id'],type(exc).__name__,str(exc),run_id)
                    db.execute('UPDATE source_runs SET status=?,message=?,pagination_complete=0,finished_at=? WHERE id=?',
                               ('blocked' if blocked else 'error',str(exc)[:2000],now(),sr['id']))
                    db.execute('UPDATE sources SET status=?,checked_at=? WHERE id=?',('BLOQUEADA' if blocked else 'ERROR',now(),sr['source_id']))
            while not cancelled(db,run_id):
                tasks = db.rows("SELECT * FROM task_queue WHERE run_id=? AND status='pending' ORDER BY CASE kind WHEN 'detail' THEN 0 ELSE 1 END,id LIMIT 1",(run_id,))
                if not tasks:
                    break
                task = tasks[0]
                if respect_blocked and task['kind']=='detail' and task['source_id'] and db.rows('SELECT status FROM sources WHERE id=?',(task['source_id'],))[0]['status']=='BLOQUEADA':
                    db.execute("UPDATE task_queue SET status='retry',error='Fuente bloqueada: revision manual requerida',updated_at=? WHERE id=?",(now(),task['id']))
                    continue
                try:
                    from contextlib import nullcontext
                    atomic=db.transaction() if task['kind']=='analyze' and profile.get('analyzer','basic')=='basic' else nullcontext()
                    with atomic:
                        db.execute("UPDATE task_queue SET status='running',attempts=attempts+1,updated_at=? WHERE id=?",(now(),task['id']))
                        process_task(db,task,client,profile)
                        db.execute("UPDATE task_queue SET status='done',error=NULL,updated_at=? WHERE id=?",(now(),task['id']))
                except Exception as exc:
                    db.error(task['source_id'],type(exc).__name__,str(exc),run_id,task['job_id'])
                    db.execute("UPDATE task_queue SET status='retry',error=?,updated_at=? WHERE id=?",(str(exc)[:2000],now(),task['id']))
                    if isinstance(exc,AccessBlocked) and task['source_id']:
                        db.execute("UPDATE task_queue SET status='retry',error='Fuente suspendida tras bloqueo' WHERE run_id=? AND source_id=? AND kind='detail' AND status='pending'",(run_id,task['source_id']))
                        db.execute("UPDATE source_runs SET status='blocked',message=? WHERE run_id=? AND source_id=?",('Bloqueo de detalle: '+str(exc)[:1000],run_id,task['source_id']))
                        db.execute("UPDATE sources SET status='BLOQUEADA' WHERE id=?",(task['source_id'],))
                    if task['job_id']:
                        db.execute("UPDATE jobs SET analysis_status='PENDIENTE' WHERE id=?",(task['job_id'],))
            has_errors = bool(db.rows("SELECT 1 FROM source_runs WHERE run_id=? AND status<>'completed'",(run_id,))) or bool(
                db.rows("SELECT 1 FROM task_queue WHERE run_id=? AND status<>'done'",(run_id,)))
            has_work = bool(db.rows('SELECT 1 FROM source_runs WHERE run_id=?',(run_id,))) or bool(db.rows('SELECT 1 FROM task_queue WHERE run_id=?',(run_id,)))
            status = 'cancelled' if cancelled(db,run_id) else 'partial' if has_errors or not has_work else 'completed'
            db.execute('UPDATE scan_runs SET status=?,finished_at=?,heartbeat=?,worker_pid=NULL WHERE id=?',(status,now(),now(),run_id))
        except BaseException as exc:
            db.execute("UPDATE scan_runs SET status='partial',message=?,worker_pid=NULL WHERE id=?",(type(exc).__name__,run_id))
            raise
        finally:
            resources.close()
            if own_client:
                client.close()

def prepare_resume(db,run_id):
    # El bloqueo de archivo determina si aún existe un trabajador; no se roba por tiempo.
    with worker_lock(db):
        if not db.rows('SELECT id FROM scan_runs WHERE id=?',(run_id,)):
            raise ValueError('Ejecución inexistente')
        db.execute("UPDATE task_queue SET status='pending' WHERE run_id=? AND status IN ('retry','running')",(run_id,))
        db.execute("UPDATE scan_runs SET status='running',cancel_requested=0,heartbeat=? WHERE id=?",(now(),run_id))

def spawn_worker(run_id):
    log = (ROOT/'logs'/f'worker-{run_id}.log').open('a',encoding='utf-8')
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    env['TEMP'] = env['TMP'] = str(ROOT/'data'/'tmp')
    (ROOT/'data'/'tmp').mkdir(exist_ok=True)
    try:
        return subprocess.Popen([sys.executable,'-m','corkjobradar','worker','--run-id',str(run_id)],cwd=ROOT,
                                stdout=log,stderr=log,env=env,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0).pid
    finally:
        log.close()
