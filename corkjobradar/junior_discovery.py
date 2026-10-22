"""Focused source discovery, using the existing full scan queue and source audit."""
import json
from pathlib import Path
from uuid import uuid4
import yaml
from .config import ROOT,load_profile,now
from .sources import upsert_source
from .worker import create_run,spawn_worker,run_worker

ROLE_QUERIES=['IT Support','Helpdesk','Service Desk','Desktop Support','IT Technician','Application Support',
              'Software Support','Junior Developer','QA Tester','IT Graduate','IT Trainee']


def source_catalog():
    return yaml.safe_load((ROOT/'config/junior_it_sources.yaml').read_text(encoding='utf-8'))['sources']


def manual_channels():
    return yaml.safe_load((ROOT/'config/junior_it_sources.yaml').read_text(encoding='utf-8'))['manual_channels']


def prepare_junior_search(db,*,automatic=False):
    # Same database transaction prevents overlapping jobs and changes to active source snapshots.
    with db.transaction() as con:
        if not con.in_transaction:con.execute('BEGIN IMMEDIATE')
        if db.rows("SELECT id FROM scan_runs WHERE status='running'"):raise RuntimeError('SEARCH_ALREADY_RUNNING')
        ids=[]
        for source in source_catalog():
            prior=db.rows('SELECT enabled,permission,url,kind,status FROM sources WHERE id=?',(source['id'],))
            if prior:
                if not prior[0]['enabled'] or prior[0]['permission']!=source['permission'] or prior[0]['url']!=source['url'] or prior[0]['kind']!=source['kind']:continue
                if automatic and prior[0]['status']=='BLOQUEADA':continue
            else:upsert_source(db,source)
            ids.append(source['id'])
        if not ids:raise RuntimeError('NO_REVIEWED_JUNIOR_SOURCES_ENABLED')
        profile={**load_profile(),'analyzer':'basic'}
        rid=create_run(db,ids,profile_override=profile)
        db.event('JUNIOR_IT_DISCOVERY_STARTED',{'sources':ids,'roles':ROLE_QUERIES,'no_ranking_stop':True,'submissions':0},rid)
        return rid


def start_junior_search(db):
    rid=prepare_junior_search(db)
    try:pid=spawn_worker(rid)
    except Exception:
        db.execute("UPDATE scan_runs SET status='partial',message='Worker launch failed' WHERE id=?",(rid,));raise
    return {'run_id':rid,'worker_pid':pid}


def discovery_report(db,rid):
    jobs=db.rows('''SELECT DISTINCT j.id,j.title,j.company,j.scope,j.analysis_status,j.open_status FROM jobs j
                   JOIN run_jobs r ON r.job_id=j.id WHERE r.run_id=? ORDER BY j.company,j.title''',(rid,))
    report={'generated_at':now(),'run':db.rows('SELECT id,status,started_at,finished_at FROM scan_runs WHERE id=?',(rid,))[0],
            'sources':db.rows('SELECT source_id,status,pages_visited,expected_total,observed,pagination_complete,message FROM source_runs WHERE run_id=?',(rid,)),
            'jobs':jobs,'all_retrieved_retained':len(jobs),'in_scope_or_pending':sum(j['scope']!='FUERA_DE_ALCANCE' for j in jobs),
            'tasks':db.rows('SELECT kind,status,COUNT(*) n FROM task_queue WHERE run_id=? GROUP BY kind,status',(rid,)),
            'external_posts':0,'live_enabled':False,'limit':'Fuentes y consulta indicadas; no es todo Cork ni filtro de aptitud. Las fuentes no disponibles siguen pendientes.'}
    output=ROOT/'logs'/('usable-it-discovery-'+str(rid)+'-'+uuid4().hex[:8]+'.json')
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report,output


def run_junior_search(db):
    rid=prepare_junior_search(db);run_worker(db,rid);return discovery_report(db,rid)
