"""Synthetic policy cases only; no external form submissions."""
import json
from copy import deepcopy
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import sqlite3
import pytest
from conftest import source
from corkjobradar.config import now
from corkjobradar.models import Job
from corkjobradar.repository import save_job
from corkjobradar.autoapply.policy import Policy, save_policy, pause, resume, current_policy, require_live
from corkjobradar.autoapply.eligibility import evaluate_autoapply, Decision
from corkjobradar.autoapply.store import save_plan,reserve,transition,reconcile,already_applied,quota_reason


IT_DESCRIPTION='Responsibilities\nProvide IT support to end users and troubleshoot Windows and Microsoft 365 incidents.\n'


def policy_config():
    return dict(expires_at='2030-01-01T00:00:00+00:00',categories=['IT'],modes=['ONSITE','REMOTE','HYBRID'],
        allowed_hosts=['boards.greenhouse.io','jobs.lever.co'],adapter_versions={'greenhouse':'test-1','lever':'test-1'},candidate_facts_hash='facts',authorized_document_ids=[1],
        window_start='00:00',window_end='23:59',permissions=dict(generate_cv=True,attach_cv=True,fill_forms=True),
        it=dict(schedules=['WEEKDAYS_DAY','WEEKEND_DAY'],contracts=['PERMANENT']))


def inputs(profile):
    job={'id':'synthetic','company':'SYNTHETIC ONLY','title':'IT Support','category':'IT','mode':'ONSITE','scope':'EN_ALCANCE',
         'url':'https://boards.greenhouse.io/synthetic/jobs/1','apply_url':None,'content_hash':'abc','detail_complete':True,
         'open_status':'OPEN_CONFIRMED','last_verified_at':'2026-10-19T10:00:00+01:00','raw':{},'description':IT_DESCRIPTION}
    analysis={'_content_hash':'abc','analysis_completeness':'COMPLETO','fit_score':90,'data_confidence':90}
    candidate={'full_name':'SYNTHETIC','email':'test@example.invalid','work_authorization':'IRELAND_AUTHORIZED','cv_document_id':1,'_facts_hash':'facts'}
    clearance={'content_hash':'abc','facts_hash':'facts','expires_at':'2026-11-01T00:00:00+00:00','requirements_met':True,
               'legal_eligibility':True,'experience_met':True,'schedule':'WEEKDAYS_DAY','contract':'PERMANENT','full_time':True,
               'shift_start':'09:00','shift_end':'17:00','days':['MON','TUE','WED','THU','FRI']}
    transport=[{'origin':'Ballinlough','mode':'bicycle','viability':'VERIFICADA','evidence_url':'https://example.org/test-evidence',
        'details':{'valid_until':'2030-01-01','job_content_hash':'abc','schedule':'WEEKDAYS_DAY','destination':'Synthetic Cork City',
                   'outbound':True,'return':True,'shift_compatible':True,'origin_access':True,
                   'shift_start':'09:00','shift_end':'17:00','days':['MON','TUE','WED','THU','FRI']}}]
    return dict(job=job,analysis=analysis,profile=profile,policy=Policy(**policy_config()),candidate=candidate,clearance=clearance,
                transport=transport,control={'enabled':1,'paused':0},platform={'id':'greenhouse','version':'test-1','verified':True,'automation_permitted':True},
                clock=datetime(2026,10,19,12,tzinfo=ZoneInfo('Europe/Dublin')))


def test_off_by_default_and_live_cannot_be_activated(db):
    c=db.rows('SELECT * FROM autoapply_control')[0]
    assert not c['enabled'] and not c['live_enabled'] and c['paused']
    with pytest.raises(PermissionError,match='LIVE_LOCKED'):require_live(db)
    with pytest.raises(sqlite3.IntegrityError):db.execute('UPDATE autoapply_control SET live_enabled=1')


def test_sector_routes_are_hard_gates(profile):
    data=inputs(profile)
    assert evaluate_autoapply(**data).outcome=='ALLOW'
    data['transport']=[]  # Car radius never substitutes for a real route.
    assert 'NO_VERIFIED_ROUND_TRIP_WITHOUT_CAR' in [r.code for r in evaluate_autoapply(**data).reasons]
    data=inputs(profile);data['clearance']['schedule']='WEEKEND_DAY';data['transport'][0]['details']['schedule']='WEEKEND_DAY'
    assert evaluate_autoapply(**data).outcome=='ALLOW'
    data=inputs(profile);data['transport'][0].update(mode='bus',transfers=0)
    assert evaluate_autoapply(**data).outcome=='ALLOW'
    data['transport'][0]['transfers']=1
    assert evaluate_autoapply(**data).outcome=='HOLD'
    data=inputs(profile);data['job'].update(category='Almacen',title='Warehouse Operative');data['clearance']['schedule']='WEEKEND_DAY'
    assert 'NON_IT_EXCLUDED' in [r.code for r in evaluate_autoapply(**data).reasons]


@pytest.mark.parametrize('mutation,code',[
 (lambda d:d['control'].update(enabled=0),'POLICY_OFF_OR_PAUSED'),
 (lambda d:d.update(duplicate=True),'ALREADY_APPLIED_OR_RESERVED'),
 (lambda d:d['job'].update(open_status='OPEN_LIKELY'),'APPLICATION_ACCEPTANCE_UNVERIFIED'),
 (lambda d:d['job'].update(detail_complete=False),'INCOMPLETE_DESCRIPTION'),
 (lambda d:d['candidate'].pop('cv_document_id'),'VERIFIED_CV_MISSING'),
 (lambda d:d['candidate'].pop('work_authorization'),'VERIFIED_WORK_AUTHORIZATION_MISSING'),
 (lambda d:d['platform'].update(blocked=True),'CAPTCHA_MFA_OR_ACCESS_BLOCK'),
 (lambda d:d['platform'].update(changed=True),'ADAPTER_CHANGED'),
 (lambda d:d['platform'].update(unresolved_questions=True),'UNRESOLVED_FORM_QUESTIONS'),
 (lambda d:d['job'].update(raw={'_listing_type':'BOLSA_DE_TALENTO_SIN_VACANTE_CONCRETA'}),'TALENT_POOL'),
 (lambda d:d['clearance'].update(schedule=None),'SCHEDULE_UNKNOWN_OR_REJECTED'),
 (lambda d:d['analysis'].update(data_confidence=10),'CONFIDENCE_BELOW_POLICY'),
 (lambda d:d['analysis'].update(_content_hash='old'),'ANALYSIS_STALE_OR_UNBOUND'),
 (lambda d:d.update(quota_reason='DAILY_QUOTA'),'DAILY_QUOTA'),
 (lambda d:d['policy'].__setattr__('expires_at','2020-01-01T00:00:00+00:00'),'POLICY_EXPIRED'),
])
def test_hard_gate_cannot_be_overridden_by_high_score(profile,mutation,code):
    data=inputs(profile);mutation(data);result=evaluate_autoapply(**data)
    assert result.outcome!='ALLOW' and code in [r.code for r in result.reasons]


def test_hard_salary_is_not_guessed(profile):
    data=inputs(profile);data['policy'].it.minimum_salary=30000.;data['policy'].it.salary_unit='year'
    assert 'HARD_SALARY_MINIMUM_UNVERIFIED' in [r.code for r in evaluate_autoapply(**data).reasons]
    data['clearance'].update(salary=29000,salary_unit='year',currency='EUR')
    assert evaluate_autoapply(**data).outcome=='BLOCK'


@pytest.mark.parametrize('field',['fit_score','data_confidence','salary'])
def test_nonfinite_numbers_never_pass_hard_gates(profile,field):
    data=inputs(profile)
    if field=='salary':
        data['policy'].it.minimum_salary=15.
        data['clearance'].update(salary=float('nan'),currency='EUR',salary_unit='hour')
    else:data['analysis'][field]=float('nan')
    assert evaluate_autoapply(**data).outcome=='HOLD'


def test_policy_is_immutable_revocable_and_profile_bound(db,profile):
    with pytest.raises(ValueError):save_policy(db,policy_config(),'')
    pid=save_policy(db,policy_config(),'AUTHORIZE_SIMULATION',profile)
    with pytest.raises(sqlite3.IntegrityError):db.execute('UPDATE autoapply_policies SET consent=? WHERE id=?',('x',pid))
    pause(db);assert current_policy(db,profile)[0]['paused']
    resume(db,'RESUME_SIMULATION',profile);assert not current_policy(db,profile)[0]['paused']
    changed=deepcopy(profile);changed['skills']=['CHANGED SYNTHETIC']
    assert current_policy(db,changed)[0]['paused']
    with pytest.raises(ValueError):resume(db,'RESUME_SIMULATION',changed)
    with pytest.raises(sqlite3.IntegrityError):db.execute('DELETE FROM application_events')


def stored_job(db,profile,external='a',url='https://boards.greenhouse.io/synthetic/jobs/1'):
    source(db,'html',sid=external)
    jid=save_job(db,external,Job(external_id=external,title='IT Support',company='SYNTHETIC ONLY',location='Cork City',url=url,description=IT_DESCRIPTION,detail_complete=True),profile=profile)
    return db.rows('SELECT * FROM jobs WHERE id=?',(jid,))[0]


def test_reservations_dedupe_cross_source_and_uncertain_never_retries(db,profile):
    pid=save_policy(db,policy_config(),'AUTHORIZE_SIMULATION')
    job=stored_job(db,profile);decision=Decision('ALLOW',[],'test',90)
    plan=save_plan(db,job,decision,pid);aid=reserve(db,plan,job)
    other=stored_job(db,profile,'other','https://jobs.lever.co/synthetic/other')
    assert already_applied(db,other)
    plan2=save_plan(db,other,decision,pid)
    with pytest.raises(PermissionError,match='ALREADY'):reserve(db,plan2,other)
    with pytest.raises(PermissionError,match='ALREADY'):reserve(db,plan,job)
    # An actual interrupted sending record can only come from a future release / controlled fixture.
    db.execute("UPDATE application_attempts SET state='ENVIANDO' WHERE id=?",(aid,))
    assert len(reconcile(db)['uncertain'])==1
    with pytest.raises(ValueError):transition(db,aid,'PREPARADA')
    assert already_applied(db,other)


def test_quota_and_pause_checked_inside_reservation(db,profile):
    cfg=policy_config();cfg['max_daily']=1;cfg['max_weekly']=1
    pid=save_policy(db,cfg,'AUTHORIZE_SIMULATION');job=stored_job(db,profile)
    plan=save_plan(db,job,Decision('ALLOW',[],'test',90),pid)
    pause(db)
    with pytest.raises(PermissionError,match='PAUSED'):reserve(db,plan,job)
    resume(db,'RESUME_SIMULATION');reserve(db,plan,job)
    assert quota_reason(db,Policy(**cfg),'DIFFERENT SYNTHETIC')=='DAILY_QUOTA'
    assert len(db.rows('SELECT * FROM application_reservations'))==1
