"""One explicit local continuation; no service, scheduler, live sends or blind restart."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now
from corkjobradar.db import Database

PHASES=(
    ('hse-metadata',('scripts/backfill_hse_deadlines.py','--apply')),
    ('all-enabled-sources',('-m','corkjobradar','scan','--all')),
    ('doc5-all-readings',('-m','corkjobradar','analyze','--local','--pending')),
    ('simulation-all-offers',('-m','corkjobradar','autoapply','run','--dry-run')),
    ('export',('-m','corkjobradar','export','--xlsx')),
    ('doctor',('-m','corkjobradar','doctor')),
    ('autoapply-doctor',('-m','corkjobradar','autoapply','doctor')),
    ('refresh-documents',('scripts/refresh_continuity_status.py',)),
)


def checkpoint(path,state,documents=True):
    state['updated_at']=now()
    temporary=path.with_name(path.name+'.'+uuid4().hex+'.tmp')
    temporary.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    # Windows readers/indexers can briefly deny replacement. Keep the previous
    # durable checkpoint until a bounded retry succeeds; never truncate it.
    for attempt in range(6):
        try:temporary.replace(path);break
        except PermissionError:
            if attempt==5:raise
            time.sleep(.1*(2**attempt))
    if not documents:return
    marker='<!-- CONTINUITY_WORKFLOW_STATUS -->'
    note=('\n\n'+marker+'\n## Continuación local supervisada\n\n'
          f"Actualizado: {state['updated_at']}. Estado: **{state['status']}**; después de ejecución {state['after_run']}. "
          f"Fase: {state.get('phase','esperando')}. Registro preciso: `data/{path.name}`; logs `logs/continuity-workflow-{state['after_run']}-*.log`. "
          'Proyecto EN DESARROLLO, envío real OFF. Este proceso no es un servicio y no arranca con Windows. '
          'Una cancelación de la ejecución esperada detiene la continuación. No relanzar fases iniciadas sin revisar su resultado.\n')
    for document in ('PROGRESO.md','NEXT_STEPS.md','docs/SESSION_CHECKPOINT.md'):
        target=ROOT/document
        original=target.read_text(encoding='utf-8') if target.exists() else ''
        target.write_text(original.split(marker)[0].rstrip()+note,encoding='utf-8')


def execute_phase(arguments,log):
    if '--local' in arguments:
        from corkjobradar.local_model import available_ram,is_validated_model
        free=available_ram()
        if free is not None and free<1_500_000_000:raise RuntimeError('READER_INSUFFICIENT_FREE_RAM')
        if not is_validated_model():raise RuntimeError('READER_VALIDATION_NO_LONGER_CURRENT')
    environment=os.environ.copy();environment.update(PYTHONIOENCODING='utf-8',TEMP=str(ROOT/'data/tmp'),TMP=str(ROOT/'data/tmp'))
    with log.open('w',encoding='utf-8') as stream:
        process=subprocess.Popen([sys.executable,*arguments],cwd=ROOT,env=environment,stdout=stream,stderr=stream,
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        return process.wait()


def continue_once(db,after_run,state_path,executor=execute_phase,sleeper=time.sleep,documents=True):
    if state_path.exists():
        existing=json.loads(state_path.read_text(encoding='utf-8'))
        if existing.get('status')=='COMPLETED':return existing
        # A child can outlive its wrapper. Never guess which external work completed.
        raise RuntimeError('EXISTING_WORKFLOW_REQUIRES_REVIEW_NOT_BLIND_RESTART')
    state={'after_run':after_run,'started_at':now(),'status':'WAITING_FOR_READER','phase':None,'phases':[],
           'live_enabled':False,'automatic_windows_start':False}
    # Exclusive initial claim prevents two wrappers scheduling the same phases.
    with state_path.open('x',encoding='utf-8') as stream:json.dump(state,stream,ensure_ascii=False,indent=2)
    checkpoint(state_path,state,documents)
    while True:
        parent=db.rows('SELECT status,cancel_requested,heartbeat FROM scan_runs WHERE id=?',(after_run,))
        if not parent or parent[0]['cancel_requested'] or parent[0]['status'] in {'cancelled','partial','error'}:
            state.update(status='STOPPED_PARENT_NOT_COMPLETED',parent_state=parent)
            checkpoint(state_path,state,documents);return state
        if parent[0]['status']=='completed':break
        if parent[0]['status']!='running':
            state.update(status='STOPPED_UNEXPECTED_PARENT_STATE',parent_state=parent)
            checkpoint(state_path,state,documents);return state
        sleeper(30)
    for phase,arguments in PHASES:
        active=db.rows("SELECT id FROM scan_runs WHERE status='running'")
        if active:
            state.update(status='STOPPED_OTHER_RUN_ACTIVE',phase=phase,active_runs=active)
            checkpoint(state_path,state,documents);return state
        state.update(status='RUNNING_PHASE',phase=phase)
        item={'name':phase,'arguments':list(arguments),'started_at':now(),'status':'RUNNING'}
        state['phases'].append(item);checkpoint(state_path,state,documents)
        log=ROOT/'logs'/f'continuity-workflow-{after_run}-{phase}.log'
        try:code=executor(arguments,log)
        except Exception as exc:
            item.update(status='ERROR',error_type=type(exc).__name__,finished_at=now())
            if str(exc).startswith('READER_'):item['reason_code']=str(exc)
            state['status']='STOPPED_PHASE_ERROR';checkpoint(state_path,state,documents);return state
        item.update(status='COMPLETED' if code==0 else 'ERROR',exit_code=code,finished_at=now(),log=str(log.relative_to(ROOT)))
        if code:
            state['status']='STOPPED_PHASE_ERROR';checkpoint(state_path,state,documents);return state
        # CLI scan can complete partially with zero exit status; preserve that
        # distinction while still processing every recovered offer afterwards.
        if phase in {'all-enabled-sources','doc5-all-readings'}:
            item['scan_run']=db.rows('SELECT id,status,finished_at FROM scan_runs ORDER BY id DESC LIMIT 1')
            if item['scan_run'] and item['scan_run'][0]['status']=='cancelled':
                state['status']='STOPPED_PHASE_CANCELLED';checkpoint(state_path,state,documents);return state
        checkpoint(state_path,state,documents)
    state.update(status='COMPLETED',finished_at=now(),project_status='EN DESARROLLO')
    checkpoint(state_path,state,documents);return state


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--after-run',type=int,required=True);parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    if not args.execute:
        print(json.dumps({'planned_phases':PHASES,'changes':False,'live_enabled':False}));raise SystemExit(0)
    state=continue_once(Database(),args.after_run,ROOT/'data'/f'continuity-workflow-{args.after_run}.json')
    print(json.dumps(state,ensure_ascii=True,indent=2))
