"""Complete durable LOCAL preparation queue; never dispatches external applications."""
import json
from datetime import datetime,timedelta
from uuid import uuid4
from ..config import now
from .broad_selection import selection_inventory,assess_selection


def _event(db,row,code):
    db.execute('INSERT INTO it_application_queue_events(job_id,occurred_at,binding_hash,workflow_state,code) VALUES(?,?,?,?,?)',
               (row['job_id'],now(),row['binding_hash'],row['workflow_state'],code))


def refresh_queue(db):
    report=selection_inventory(db)
    with db.transaction() as con:
        con.execute('BEGIN IMMEDIATE')
        for item in report['offers']:
            prior=db.rows('SELECT * FROM it_application_queue WHERE job_id=?',(item['job_id'],))
            prior=prior[0] if prior else None
            workflow=('CONFIRMED' if item['state']=='ENVIADA_CONFIRMADA' else 'UNCERTAIN' if item['state']=='ENVIO_INCIERTO' else
                      'EXCLUDED' if item['state']=='EXCLUIDA' else 'DUPLICATE' if item['duplicate'] else 'PENDING')
            if prior and prior['binding_hash']==item['binding_hash'] and prior['application_state']==item['state']:
                if prior['workflow_state']=='LEASED':
                    try:active=datetime.fromisoformat(prior['lease_until'])>datetime.fromisoformat(now())
                    except (ValueError,TypeError):active=False
                    if active:continue
                elif prior['workflow_state'] not in {'FAILED_RETRY'}:continue
            if prior and prior['workflow_state']=='LEASED':
                # Invalidate a changed binding. An old owner cannot commit using its token.
                pass
            data={'job_id':item['job_id'],'binding_hash':item['binding_hash'],'workflow_state':workflow}
            db.execute('''INSERT INTO it_application_queue(job_id,binding_hash,professional_state,application_state,workflow_state,route,assessment,updated_at)
                          VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(job_id) DO UPDATE SET binding_hash=excluded.binding_hash,
                          professional_state=excluded.professional_state,application_state=excluded.application_state,
                          workflow_state=excluded.workflow_state,route=excluded.route,assessment=excluded.assessment,
                          updated_at=excluded.updated_at,lease_token=NULL,lease_until=NULL,handoff_id=NULL,error_code=NULL''',
                       (item['job_id'],item['binding_hash'],item['professional_state'],item['state'],workflow,item['interaction_mode'],json.dumps(item,ensure_ascii=False),now()))
            _event(db,data,'RECLASSIFIED' if prior else 'QUEUED')
    return report


def claim_preparation(db):
    with db.transaction() as con:
        con.execute('BEGIN IMMEDIATE')
        rows=db.rows("SELECT * FROM it_application_queue WHERE workflow_state IN ('PENDING','FAILED_RETRY') OR (workflow_state='LEASED' AND lease_until<=?) ORDER BY updated_at,job_id LIMIT 1",(now(),))
        if not rows:return None
        row=rows[0];token=uuid4().hex
        db.execute("UPDATE it_application_queue SET workflow_state='LEASED',lease_token=?,lease_until=?,updated_at=? WHERE job_id=?",
                   (token,(datetime.fromisoformat(now())+timedelta(minutes=10)).isoformat(),now(),row['job_id']))
        result={**row,'lease_token':token,'workflow_state':'LEASED'};_event(db,result,'LOCAL_PREPARATION_CLAIMED')
        return result


def finish_preparation(db,claim,state,code,handoff_id=None):
    if state not in {'MANUAL_READY','INTERVENTION','EXCLUDED','DUPLICATE','UNCERTAIN','CONFIRMED','FAILED_RETRY'}:raise ValueError('INVALID_LOCAL_QUEUE_STATE')
    with db.transaction() as con:
        con.execute('BEGIN IMMEDIATE')
        rows=db.rows("SELECT * FROM it_application_queue WHERE job_id=? AND binding_hash=? AND lease_token=? AND workflow_state='LEASED' AND lease_until>?",
                     (claim['job_id'],claim['binding_hash'],claim['lease_token'],now()))
        if not rows:raise PermissionError('STALE_QUEUE_LEASE')
        db.execute('UPDATE it_application_queue SET workflow_state=?,handoff_id=?,error_code=?,lease_token=NULL,lease_until=NULL,updated_at=? WHERE job_id=?',
                   (state,handoff_id,code,now(),claim['job_id']))
        _event(db,{**claim,'workflow_state':state},code)


def prepare_all_local(db,*,should_stop=None):
    """All rows, no ranking/score cutoffs. Reuse the existing worker exclusion lock."""
    from ..worker import worker_lock
    from .handoff import prepare_handoff,load_handoff
    counts={'processed':0,'manual_ready':0,'intervention':0,'errors':0,'external_requests':0,'submitted':0}
    with worker_lock(db):
        refresh_queue(db)
        # Each durable item is visited once in this pass. Failures await the next explicit pass.
        seen=set()
        while True:
            if should_stop and should_stop():counts['paused']=True;break
            claim=claim_preparation(db)
            if not claim:break
            if claim['job_id'] in seen:
                finish_preparation(db,claim,'INTERVENTION','RETRY_NEXT_EXPLICIT_PASS');break
            seen.add(claim['job_id']);counts['processed']+=1
            try:
                job=db.rows('SELECT * FROM jobs WHERE id=?',(claim['job_id'],))[0]
                item=assess_selection(db,job)
                if item['binding_hash']!=claim['binding_hash']:raise PermissionError('SELECTION_BINDING_CHANGED')
                if item['geography']['state']=='REMOTE_SEPARATE':
                    finish_preparation(db,claim,'INTERVENTION','REMOTE_ADDITIONAL_AUTHORIZATION_REQUIRED');counts['intervention']+=1;continue
                if not item['preparation_allowed'] or not item['cv_approved']:
                    finish_preparation(db,claim,'INTERVENTION','FACTUAL_REVIEW_OR_CV_APPROVAL_REQUIRED');counts['intervention']+=1;continue
                # Reuse only a currently valid package; never duplicate a declaration or upload.
                existing=db.rows('SELECT id FROM manual_application_handoffs WHERE job_id=? ORDER BY id DESC',(job['id'],))
                from .forms import load_inspection
                inspection_id=None
                for inspection in db.rows('SELECT id FROM autoapply_form_inspections WHERE job_id=? ORDER BY id DESC',(job['id'],)):
                    try:load_inspection(db,inspection['id']);inspection_id=inspection['id'];break
                    except (ValueError,PermissionError):continue
                hid=None
                for row in existing:
                    try:
                        packet=load_handoff(db,row['id'])
                        if packet['inspection_id']!=inspection_id:continue
                        hid=row['id'];break
                    except (ValueError,PermissionError):continue
                if hid is None:hid=prepare_handoff(db,job['id'],inspection_id)['handoff_id']
                # Preparation can have warnings, but never invents a response or sends.
                finish_preparation(db,claim,'MANUAL_READY','LOCAL_PACKAGE_ONLY_NO_SUBMISSION',hid);counts['manual_ready']+=1
            except Exception:
                finish_preparation(db,claim,'INTERVENTION','LOCAL_PREPARATION_REVIEW_REQUIRED');counts['errors']+=1
    return counts


def queue_summary(db):
    return {'rows':db.rows('SELECT workflow_state,count(*) n FROM it_application_queue GROUP BY workflow_state'),
            'total':db.rows('SELECT count(*) n FROM it_application_queue')[0]['n'],'live_enabled':False}
