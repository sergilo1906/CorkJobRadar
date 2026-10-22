"""Reproducible offline end-to-end trial. Only synthetic jobs in an isolated database."""
import json
from ..config import DB_PATH,now,digest
from .browser import offline_browser,OfflineFormAdapter,FIXTURE_ORIGIN,FormHold
from .vault import candidate_snapshot
from .documents import document_bytes
from .policy import event,pause
from .store import transition,prefinal_check


def prepare_offline_attempt(db,attempt_id,pages,platform='greenhouse',before_final=None):
    if db.path.resolve()==DB_PATH.resolve():raise PermissionError('TEST_WORKBENCH_REJECTS_PRODUCTION_DATABASE')
    attempt=db.rows('SELECT * FROM application_attempts WHERE id=?',(attempt_id,))[0]
    plan=db.rows('SELECT * FROM application_plans WHERE id=?',(attempt['plan_id'],))[0]
    job=db.rows('SELECT * FROM jobs WHERE id=?',(plan['job_id'],))[0]
    if plan['environment']!='SIMULATION' or not json.loads(job['raw']).get('_synthetic_fixture'):
        raise PermissionError('ISOLATED_SYNTHETIC_JOB_REQUIRED')
    from .it_scope import require_it_job
    require_it_job(job)
    candidate=candidate_snapshot(db)
    try:
        content,extension,sha=document_bytes(db,candidate['cv_document_id'])
        db.execute('UPDATE application_attempts SET document_id=?,adapter=? WHERE id=?',(candidate['cv_document_id'],'offline-'+platform+'-1',attempt_id))
        transition(db,attempt_id,'PREPARADA')
        with offline_browser(pages) as (page,traffic):
            page.goto(FIXTURE_ORIGIN+'/form')
            adapter=OfflineFormAdapter(page,platform);form=adapter.inspect_form()
            mapping=adapter.map_questions(form,candidate)
            transition(db,attempt_id,'RELLENANDO')
            adapter.fill(form,mapping,lambda did:document_bytes(db,did))
            for question,answer in mapping.items():
                if answer.get('fact_id'):
                    db.execute('INSERT INTO application_answers(attempt_id,question_hash,fact_id,answer_hash,created_at) VALUES(?,?,?,?,?)',
                               (attempt_id,digest(question),answer['fact_id'],digest(answer['value']),now()))
            adapter.validate_prefinal()
            db.execute('UPDATE application_attempts SET form_hash=? WHERE id=?',(form['hash'],attempt_id))
            transition(db,attempt_id,'LISTA_PARA_ENVIO')
            if before_final:before_final()
            prefinal_check(db,attempt_id)
            # Stop BEFORE the final click. No real or simulated POST in this production preparation path.
            transition(db,attempt_id,'SIMULADA_SIN_ENVIO')
            event(db,'OFFLINE_TRIAL_COMPLETED',{'form_hash':form['hash'],'document_hash':sha,'posts':traffic['fixture_posts']},plan['id'],attempt_id)
            return {'state':'SIMULADA_SIN_ENVIO','posts':traffic['fixture_posts'],'blocked':traffic['blocked'],'form_hash':form['hash']}
    except Exception as exc:
        state=db.rows('SELECT state FROM application_attempts WHERE id=?',(attempt_id,))[0]['state']
        target='CANCELADA' if isinstance(exc,PermissionError) else 'REQUIERE_REVISION'
        transition(db,attempt_id,target,'POLICY_CHANGED_OR_FORM_UNRESOLVED')
        event(db,'OFFLINE_TRIAL_HELD',{'error_type':type(exc).__name__},plan['id'],attempt_id)
        return {'state':target,'posts':0,'error_type':type(exc).__name__}
