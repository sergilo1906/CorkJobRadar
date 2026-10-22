import json
import httpx
import pytest
from corkjobradar.autoapply.forms import greenhouse_fields,inspect_job_form,load_inspection,answer_plan,disconnected_preparation,inspect_lever
from corkjobradar.autoapply.vault import candidate_snapshot,approve_fact
from corkjobradar.autoapply.documents import render_cv,store_document
from test_autoapply_vault import populate
from test_autoapply_policy import stored_job
from conftest import client


def schema():
    return {'id':321,'questions':[
        {'label':'Full name','required':True,'fields':[{'name':'name','type':'input_text'}]},
        {'label':'Email','required':True,'fields':[{'name':'email','type':'input_text'}]},
        {'label':'Resume/CV','required':True,'fields':[{'name':'resume','type':'input_file'},{'name':'resume_text','type':'textarea'}]},
        {'label':'LinkedIn Profile','required':True,'fields':[{'name':'linkedin','type':'input_text'}]}]}


def inspected(db,profile,data=None):
    job=stored_job(db,profile,url='https://job-boards.greenhouse.io/synthetic/jobs/321')
    requests=[]
    def handler(req):
        requests.append((req.method,str(req.url)))
        return httpx.Response(200,text='User-agent: *\nAllow: /') if req.url.path=='/robots.txt' else httpx.Response(200,json=data or schema())
    with client(profile,handler) as web:inspection=inspect_job_form(db,job['id'],web)
    assert all(method=='GET' for method,url in requests)
    return job,inspection


def test_real_schema_adapter_disconnected_e2e_includes_cv_contacts_and_linkedin(db,profile):
    populate(db)
    approve_fact(db,'linkedin_url','https://www.linkedin.com/in/synthetic-only/','synthetic',True)
    store_document(db,render_cv(candidate_snapshot(db)),'docx',True)
    job,inspection=inspected(db,profile)
    assert inspection['source_kind']=='PUBLIC_JOB_BOARD_API_GET' and not inspection['live_supported']
    result=disconnected_preparation(db,inspection['inspection_id'])
    assert result['state']=='PREPARED_OFFLINE' and result['browser_validation'] and result['posts']==0
    assert set(result['resolved_fields'])=={'name','email','resume','linkedin'}
    assert not result['external_personal_data_sent'] and not result['hosted_form_verified']
    assert not db.rows('SELECT * FROM application_attempts') and not db.rows('SELECT * FROM user_actions')
    assert 'synthetic@example.invalid' not in json.dumps(db.rows('SELECT * FROM application_events'))


def test_native_language_and_legal_consent_are_never_guessed(db,profile):
    populate(db)
    data=schema();data['questions'].append({'label':'What is your native language?','required':True,'fields':[{'name':'native','type':'input_text'}]})
    data['data_compliance']=[{'requires_processing_consent':True}]
    job,inspection=inspected(db,profile,data)
    plan=answer_plan(inspection,candidate_snapshot(db))
    assert {'native','compliance_0_requires_processing_consent'}<={q['field'] for q in plan['unresolved']}
    result=disconnected_preparation(db,inspection['inspection_id'])
    assert result['state']=='HOLD' and not result['browser_validation'] and result['posts']==0


def test_verified_answers_bind_to_exact_real_host_and_question(db,profile):
    populate(db)
    data=schema();data['questions'].append({'label':'Verified custom question','required':True,'fields':[{'name':'q','type':'input_text'}]})
    job,inspection=inspected(db,profile,data)
    approve_fact(db,'answer:custom',{'question':'Verified custom question','host':'other.invalid','answer':'SYNTHETIC AUTHORIZED'},'synthetic',True)
    assert 'q' not in answer_plan(inspection,candidate_snapshot(db))['mapping']
    approve_fact(db,'answer:custom',{'question':'Verified custom question','host':'job-boards.greenhouse.io','answer':'SYNTHETIC AUTHORIZED'},'synthetic',True)
    assert answer_plan(inspection,candidate_snapshot(db))['mapping']['q']['value']=='SYNTHETIC AUTHORIZED'


def test_approved_work_authorization_reused_without_guessing_future_or_experience(db,profile):
    populate(db)
    data=schema()
    for name,label in [('right','Are you authorized to work in Ireland for any employer?'),
                       ('future','Will you now or in the future require employer sponsorship?'),
                       ('years','Do you have 2+ years of IT experience?')]:
        data['questions'].append({'label':label,'required':True,'fields':[{'name':name,'type':'multi_value_single_select','values':[{'label':'Yes','value':1},{'label':'No','value':0}]}]})
    job,inspection=inspected(db,profile,data)
    plan=answer_plan(inspection,candidate_snapshot(db))
    assert plan['mapping']['right']['value']=='1'
    assert {'future','years'}<={q['field'] for q in plan['unresolved']}


def test_empty_or_unknown_schema_retained_and_posting_change_invalidates_inspection(db,profile):
    assert 'EMPTY_APPLICATION_FORM' in greenhouse_fields({'questions':[]})[1]
    unknown={'questions':[{'label':'Complex unknown','fields':[{'name':'q','type':'unknown'}]}]}
    assert 'UNSUPPORTED_SCHEMA_FIELD' in greenhouse_fields(unknown)[1]
    job,inspection=inspected(db,profile)
    db.execute("UPDATE jobs SET content_hash='changed' WHERE id=?",(job['id'],))
    with pytest.raises(ValueError,match='STALE'):load_inspection(db,inspection['inspection_id'])
    db.execute("UPDATE jobs SET content_hash=?,title='Warehouse Operative' WHERE id=?",(job['content_hash'],job['id']))
    with pytest.raises(PermissionError,match='NON_IT_EXCLUDED'):load_inspection(db,inspection['inspection_id'])


def test_draft_cv_is_only_used_in_disconnected_review_without_approving_it(db,profile):
    from corkjobradar.autoapply.documents import create_cv_review
    populate(db)
    approve_fact(db,'linkedin_url','https://www.linkedin.com/in/synthetic-only/','synthetic',True)
    draft=create_cv_review(db,render_cv(candidate_snapshot(db)),'docx')
    job,inspection=inspected(db,profile)
    result=disconnected_preparation(db,inspection['inspection_id'],draft)
    assert result['state']=='REVIEW_ONLY' and result['browser_validation']
    assert result['using_unapproved_cv_for_local_review_only'] and not result['ready_for_submission'] and result['posts']==0
    assert not candidate_snapshot(db).get('cv_document_id')
    assert not db.rows('SELECT * FROM application_attempts')


def test_old_form_inspection_expires_even_if_job_did_not_change(db,profile):
    from datetime import datetime,timedelta
    job,inspection=inspected(db,profile)
    later=datetime.fromisoformat(inspection['checked_at'])+timedelta(hours=25)
    with pytest.raises(ValueError,match='EXPIRED'):load_inspection(db,inspection['inspection_id'],later)


def test_hosted_captcha_assessment_is_preserved_as_blocker(db,profile,monkeypatch):
    import corkjobradar.autoapply.hosted_probe as probe
    monkeypatch.setattr(probe,'inspect_hosted_greenhouse',lambda url:{'captcha_detected':True,'submissions':0})
    job=stored_job(db,profile,url='https://job-boards.greenhouse.io/synthetic/jobs/321')
    def handler(req):
        return httpx.Response(200,text='User-agent: *\nAllow: /') if req.url.path=='/robots.txt' else httpx.Response(200,json=schema())
    with client(profile,handler) as web:inspection=inspect_job_form(db,job['id'],web,include_hosted=True)
    loaded=load_inspection(db,inspection['inspection_id'])
    assert 'HOSTED_CAPTCHA_DECLARED_OR_DETECTED' in loaded['blockers']
    assert loaded['hosted_assessment']['submissions']==0


def test_lever_captcha_and_untrusted_actions_remain_blocked(profile):
    posting='11111111-2222-3333-4444-555555555555'
    def handler(req):
        if req.url.path=='/robots.txt':return httpx.Response(200,text='User-agent: *\nAllow: /')
        return httpx.Response(200,text='<form method="POST" action="https://evil.invalid/steal"><label for="name">Full name</label><input id="name" name="name" required><div class="hcaptcha"></div></form>')
    with client(profile,handler) as web:result=inspect_lever('https://jobs.lever.co/synthetic/'+posting,web)
    assert {'CAPTCHA_MFA_OR_ACCESS_BLOCK','UNAUTHORIZED_FORM_ACTION'}<=set(result['blockers'])
    assert not result['submitted']
