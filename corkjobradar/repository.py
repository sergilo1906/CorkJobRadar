import json
import re
from uuid import uuid4
from .config import now, digest, load_profile
from .normalization import canonical_url, normalized, category,job_identity_url
from .geography import scope_for

def unpack_job(row):
    row = dict(row)
    row['raw'] = json.loads(row['raw']) if isinstance(row['raw'],str) else row['raw']
    return row

def save_job(db, source_id, job, run_id=None, profile=None):
    data = job.model_dump() if hasattr(job,'model_dump') else dict(job)
    if re.search(r'register your c\.?v\.?|talent communit|talent pool|future (?:roles|opportunities)',data['title'],re.I):
        data.setdefault('raw',{})['_listing_type']='BOLSA_DE_TALENTO_SIN_VACANTE_CONCRETA'
    # La URL publicada se conserva para abrir el anuncio. Canonicalizar solo identidad.
    data['url'] = data['url'].strip()
    stamp = now()
    profile = profile or load_profile()
    with db.connect() as con:
        existing = con.execute('SELECT j.* FROM jobs j JOIN job_sources s ON s.job_id=j.id WHERE s.source_id=? AND s.external_id=?',
                               (source_id,data['external_id'])).fetchone()
        if not existing and not data.get('raw',{}).get('_parse_error'):
            existing=con.execute('SELECT * FROM jobs WHERE company=? AND identity_url=? LIMIT 1',
                                 (data['company'],job_identity_url(data))).fetchone()
        job_id = existing['id'] if existing else uuid4().hex
        if existing and not data['detail_complete'] and existing['detail_complete']:
            data['description'] = existing['description']
            data['detail_complete'] = True
            data['raw'] = {**json.loads(existing['raw']),**data.get('raw',{})}
            if data['url']==data['raw'].get('_detail_url'):
                data['url']=existing['url']
            if data.get('mode')=='DESCONOCIDO':
                data['mode']=existing['mode']
        if existing and not data.get('apply_url'):
            data['apply_url'] = existing['apply_url']
        cat = category(data['title'], str(data.get('raw',{}).get('departments','')) + ' ' + str(data.get('raw',{}).get('department','')))
        checks = [dict(c) for c in con.execute('SELECT * FROM commute_checks WHERE job_id=? ORDER BY id DESC',(job_id,))]
        scope, reason, area = scope_for(data,cat,profile,checks)
        data['raw']['_geographic_class'] = area
        content_hash = digest({k:data.get(k) for k in ('title','company','location','description','mode','apply_url')})
        changed = not existing or content_hash != existing['content_hash']
        possible = None
        if not existing:
            match = con.execute('SELECT id FROM jobs WHERE title=? AND company=? AND location=? LIMIT 1',
                                (data['title'],data['company'],data['location'])).fetchone()
            possible = match['id'] if match else None
        raw = json.dumps(data['raw'],ensure_ascii=False)
        con.execute('''INSERT INTO jobs(id,title,company,location,url,apply_url,description,detail_complete,category,
                    scope,scope_reason,mode,posted_at,first_seen_at,last_seen_at,content_hash,raw,possible_duplicate)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,company=excluded.company,location=excluded.location,url=excluded.url,
                    apply_url=COALESCE(excluded.apply_url,jobs.apply_url),description=excluded.description,
                    detail_complete=excluded.detail_complete,category=excluded.category,scope=excluded.scope,
                    scope_reason=excluded.scope_reason,mode=excluded.mode,posted_at=COALESCE(excluded.posted_at,jobs.posted_at),
                    last_seen_at=excluded.last_seen_at,content_hash=excluded.content_hash,raw=excluded.raw''',
                    (job_id,data['title'],data['company'],data['location'],data['url'],data.get('apply_url'),data['description'],
                     int(data['detail_complete']),cat,scope,reason,data.get('mode','DESCONOCIDO'),data.get('posted_at'),stamp,stamp,content_hash,raw,possible))
        if changed:
            con.execute("UPDATE jobs SET analysis_status='PENDIENTE' WHERE id=?",(job_id,))
        con.execute('''INSERT INTO job_sources(source_id,external_id,job_id,url,first_seen_at,last_seen_at)
                    VALUES(?,?,?,?,?,?) ON CONFLICT(source_id,external_id) DO UPDATE SET
                    last_seen_at=excluded.last_seen_at,url=excluded.url,missing_successes=0''',
                    (source_id,data['external_id'],job_id,data['url'],stamp,stamp))
        con.execute('UPDATE jobs SET identity_url=? WHERE id=?',(job_identity_url(data),job_id))
        if run_id:
            signature=con.execute('SELECT query_signature FROM source_runs WHERE run_id=? AND source_id=?',(run_id,source_id)).fetchone()
            if signature and signature['query_signature']:
                con.execute('UPDATE job_sources SET last_query_signature=? WHERE source_id=? AND external_id=?',
                            (signature['query_signature'],source_id,data['external_id']))
        con.execute('INSERT OR IGNORE INTO job_snapshots(job_id,content_hash,captured_at,description,raw) VALUES(?,?,?,?,?)',
                    (job_id,content_hash,stamp,data['description'],raw))
        if run_id:
            current=con.execute('SELECT change_status,baseline_hash FROM run_jobs WHERE run_id=? AND job_id=?',(run_id,job_id)).fetchall()
            baseline=current[0]['baseline_hash'] if current else existing['content_hash'] if existing else None
            status='NEW' if not existing or any(r['change_status']=='NEW' for r in current) else 'CHANGED' if baseline != content_hash else 'REPEATED'
            con.execute('''INSERT INTO run_jobs(run_id,source_id,external_id,job_id,content_hash,observed_at,change_status,baseline_hash)
                VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(run_id,source_id,external_id) DO UPDATE SET
                content_hash=excluded.content_hash,observed_at=excluded.observed_at,change_status=excluded.change_status''',
                (run_id,source_id,data['external_id'],job_id,content_hash,stamp,status,baseline))
    return job_id

def latest_analysis(db, job_id):
    rows = db.rows("SELECT * FROM job_analyses WHERE job_id=? AND COALESCE(json_extract(result,'$.model_validation'),'') NOT IN ('RECHAZADO','EN_EVALUACION') ORDER BY id DESC LIMIT 1",(job_id,))
    return json.loads(rows[0]['result']) if rows else {}

def latest_analyses(db):
    rows=db.rows('''SELECT a.job_id,a.result,a.content_hash FROM job_analyses a
                   JOIN (SELECT job_id,MAX(id) id FROM job_analyses
                         WHERE COALESCE(json_extract(result,'$.model_validation'),'') NOT IN ('RECHAZADO','EN_EVALUACION')
                         GROUP BY job_id) last ON a.id=last.id''')
    return {r['job_id']:{**json.loads(r['result']),'_content_hash':r['content_hash']} for r in rows}

def reconcile_duplicate_urls(db):
    """Fusionar solo URL oficial canónica y empleador idénticos, conservando procedencias e historial."""
    groups = {}
    merged = []
    with db.connect() as con:
        for row in con.execute('SELECT * FROM jobs ORDER BY first_seen_at,id').fetchall():
            if json.loads(row['raw']).get('_parse_error'):
                continue
            key=(job_identity_url(dict(row)),normalized(row['company']))
            if key not in groups:
                groups[key]=row['id']
                continue
            winner,loser=groups[key],row['id']
            if any(con.execute(f'SELECT 1 FROM {table} WHERE job_id IN (?,?) LIMIT 1',(winner,loser)).fetchone()
                   for table in ('application_plans','job_clearances','manual_application_handoffs','manual_requirement_reviews')):
                # Application references are immutable evidence. Keep both records and let identity keys prevent sends.
                con.execute('UPDATE jobs SET possible_duplicate=? WHERE id=?',(winner,loser))
                con.execute('INSERT INTO audit_events(job_id,created_at,kind,details) VALUES(?,?,?,?)',
                            (winner,now(),'DEDUP_AUTOAPPLY_REVIEW',json.dumps({'alias_id':loser,'master_id':winner})))
                continue
            history={table:[dict(x) for x in con.execute(f'SELECT * FROM {table} WHERE job_id=?',(loser,))]
                     for table in ('job_snapshots','job_analyses','task_queue')}
            con.execute('INSERT INTO audit_events(job_id,created_at,kind,details) VALUES(?,?,?,?)',
                        (winner,now(),'DEDUP_MERGE',json.dumps({'alias_id':loser,'master_id':winner,'original_job':dict(row),'preserved_collision_history':history},ensure_ascii=False)))
            for table in ('job_sources','run_jobs','verification_events','commute_checks','user_actions','source_errors','audit_events'):
                con.execute(f'UPDATE {table} SET job_id=? WHERE job_id=?',(winner,loser))
            for table in ('job_snapshots','job_analyses','task_queue'):
                con.execute(f'UPDATE OR IGNORE {table} SET job_id=? WHERE job_id=?',(winner,loser))
                # Solo quedan colisiones de índices; su contenido íntegro está en DEDUP_MERGE.
                con.execute(f'DELETE FROM {table} WHERE job_id=?',(loser,))
            con.execute('DELETE FROM jobs WHERE id=?',(loser,))
            merged.append({'master_id':winner,'alias_id':loser})
    return merged

def all_jobs(db, analyses=None):
    rows = db.rows('''SELECT j.*, (SELECT group_concat(s.name, '; ') FROM job_sources js JOIN sources s ON s.id=js.source_id
                     WHERE js.job_id=j.id) AS sources FROM jobs j ORDER BY first_seen_at DESC,id''')
    analyses=latest_analyses(db) if analyses is None else analyses
    for job in rows:
        result = analyses.get(job['id'],{})
        job['analysis_stale']=bool(result and result.get('_content_hash',job['content_hash'])!=job['content_hash'])
        job['fit_score'] = result.get('fit_score')
        job['data_confidence'] = result.get('data_confidence')
        job['depth'] = result.get('depth','PENDIENTE')
        if job['analysis_stale']:
            job.update(fit_score=None,data_confidence=None,depth='ANALISIS_DESACTUALIZADO')
        facts = result.get('facts',{})
        for key in ('salary','schedule','contract','experience'):
            value = facts.get(key,{}).get('value')
            job[key] = json.dumps(value,ensure_ascii=False) if isinstance(value,(dict,list)) else value if value is not None else 'No indicado por la empresa'
    return rows

def run_observations(db,run_id):
    rows=db.rows('''SELECT job_id,MAX(CASE change_status WHEN 'NEW' THEN 4 WHEN 'CHANGED' THEN 3
        WHEN 'REPEATED' THEN 2 ELSE 1 END) rank FROM run_jobs WHERE run_id=? GROUP BY job_id''',(run_id,))
    return {r['job_id']:{4:'NEW',3:'CHANGED',2:'REPEATED',1:'LEGACY_UNKNOWN'}[r['rank']] for r in rows}
