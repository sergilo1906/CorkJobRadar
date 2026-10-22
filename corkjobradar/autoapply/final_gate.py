"""Complete last-moment revalidation; never performs a network submission."""
from ..config import load_profile
from ..repository import latest_analyses
from .documents import document_bytes
from .eligibility import evaluate_autoapply
from .forms import load_inspection,answer_plan
from .it_scope import require_it_job
from .platforms import platform_for
from .policy import current_policy
from .store import prefinal_check,already_applied,quota_reason
from .vault import candidate_snapshot,clearance_for


def final_submission_gate(db,attempt_id,inspection_id,*,_owned_local_fixture=False):
    """Recheck ALL gates against current DB, not the decision saved at selection.

    A future permitted transport must call this immediately before its one POST.
    Returning a packet does not authorize LIVE or establish external receipt.
    """
    with db.transaction() as con:
        if not con.in_transaction:con.execute('BEGIN IMMEDIATE')
        prefinal_check(db,attempt_id)
        attempt=db.rows('''SELECT a.*,p.job_id,p.environment FROM application_attempts a
                           JOIN application_plans p ON p.id=a.plan_id WHERE a.id=?''',(attempt_id,))[0]
        if attempt['state']!='LISTA_PARA_ENVIO':raise PermissionError('FINAL_FORM_STATE_REQUIRED')
        job=db.rows('SELECT * FROM jobs WHERE id=?',(attempt['job_id'],))[0];require_it_job(job)
        target=job.get('apply_url') or job['url']
        if attempt['target_url']!=target:raise PermissionError('APPLICATION_TARGET_CHANGED')
        inspection=load_inspection(db,inspection_id)
        if inspection['job_id']!=job['id'] or inspection['public_url']!=target:raise PermissionError('INSPECTION_TARGET_MISMATCH')
        if inspection['form_hash']!=attempt['form_hash']:raise PermissionError('FINAL_FORM_HASH_CHANGED')
        candidate=candidate_snapshot(db);control,_,policy=current_policy(db)
        answers=answer_plan(inspection,candidate)
        if answers['unresolved'] or inspection['blockers']:raise PermissionError('UNRESOLVED_FORM_OR_ACCESS_BLOCK')
        capability=platform_for(target)
        if _owned_local_fixture:
            from .human_sessions import require_owned_fixture
            require_owned_fixture(db,job)
            if attempt['environment']!='SIMULATION':raise PermissionError('OWNED_SIMULATION_ONLY')
            # This capability is ONLY our owned synthetic receiver, never an ATS.
            capability={'id':'greenhouse','version':'test-1','verified':True,'automation_permitted':True,'api_submission_verified':True}
        if not inspection.get('hosted_form_verified') and not capability.get('api_submission_verified'):
            raise PermissionError('ACTUAL_FORM_OR_API_COMPLETION_UNVERIFIED')
        decision=evaluate_autoapply(job,latest_analyses(db).get(job['id'],{}),load_profile(),policy,
            db.rows('SELECT * FROM commute_checks WHERE job_id=? ORDER BY id DESC',(job['id'],)),
            platform=capability,control=control,candidate=candidate,clearance=clearance_for(db,job['id']),db=db,
            duplicate=already_applied(db,job,attempt['environment'],attempt_id),
            quota_reason=quota_reason(db,policy,job['company'],attempt['environment'],exclude_attempt=attempt_id))
        if decision.outcome!='ALLOW':raise PermissionError('FINAL_ELIGIBILITY_HELD:'+','.join(r.code for r in decision.reasons))
        _,_,sha=document_bytes(db,candidate['cv_document_id'])
        return {'job_id':job['id'],'target_url':target,'facts_hash':candidate['_facts_hash'],
                'document_id':candidate['cv_document_id'],'document_hash':sha,'form_hash':inspection['form_hash'],
                'resolved_fields':sorted(answers['mapping']),'policy_epoch':control['epoch'],
                'submitted':False,'live_activation_authorized':False}
