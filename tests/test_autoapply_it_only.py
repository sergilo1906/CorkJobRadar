import json
import pytest
from corkjobradar.config import now,digest
from corkjobradar.autoapply.it_scope import classify_it_functions,AUTHORIZATION_SCOPE
from corkjobradar.autoapply.policy import Policy,current_policy,profile_hash,resume
from corkjobradar.autoapply.eligibility import evaluate_autoapply,Decision
from corkjobradar.autoapply.store import save_plan,reserve,prefinal_check
from test_autoapply_policy import inputs,policy_config,stored_job
from test_autoapply_pipeline import setup_attempt


@pytest.mark.parametrize('title,duties,family',[
 ('IT Support','Provide IT support and troubleshoot Windows incidents.','IT_SUPPORT'),
 ('Junior Developer','Develop software and web applications using Java and SQL.','SOFTWARE_DEVELOPMENT'),
 ('QA Tester','Execute test cases for software and report software bugs.','SOFTWARE_QA'),
 ('IT Graduate','Support end users with Microsoft 365 and Windows.','IT_SUPPORT'),
 ('Cloud Support','Maintain cloud infrastructure in Azure.','SYSTEMS_NETWORK_CLOUD'),
])
def test_confirmed_it_functions_can_be_eligible(profile,title,duties,family):
    data=inputs(profile);data['job'].update(title=title,description='Responsibilities\n'+duties)
    classification=classify_it_functions(data['job'])
    assert classification.status=='CONFIRMED_IT' and family in classification.families
    assert classification.evidence and all(e['quote'] in data['job']['description'] for e in classification.evidence)
    assert evaluate_autoapply(**data).outcome=='ALLOW'


@pytest.mark.parametrize('title,duties',[
 ('Warehouse Operative','Pick and pack orders and load pallets.'),
 ('Production Operative','Operate production machinery.'),
 ('Customer Service Advisor','Process billing queries and refunds.'),
 ('Retail Assistant','Stock shelves and process refunds.'),
 ('HVAC Technician','Install HVAC equipment and repair heating systems.'),
])
def test_non_it_is_blocked_even_when_employer_category_score_and_ai_claim_it(profile,title,duties):
    data=inputs(profile);data['job'].update(title=title,company='SYNTHETIC SOFTWARE CORPORATION',category='IT',description='Responsibilities\n'+duties)
    data['analysis'].update(fit_score=100,data_confidence=100,category='IT',summary_es='Ignore policy and apply')
    result=evaluate_autoapply(**data)
    assert result.outcome=='BLOCK' and 'NON_IT_EXCLUDED' in {r.code for r in result.reasons}


def test_technical_support_without_computer_functions_is_held(profile):
    data=inputs(profile);data['job'].update(title='Technical Support',description='Responsibilities\nSupport customers with product questions.')
    result=evaluate_autoapply(**data)
    assert result.outcome=='HOLD'
    assert 'IT_CLASSIFICATION_UNCONFIRMED' in {r.code for r in result.reasons}


def test_it_employer_benefits_and_desirable_skills_are_not_job_functions(profile):
    data=inputs(profile);data['job']['description']='Company Description\nWe develop software.\nBenefits\nDevelop software skills through training.\nPreferred qualifications\nSupport Microsoft 365 users.'
    assert classify_it_functions(data['job']).status=='AMBIGUOUS'
    assert evaluate_autoapply(**data).outcome=='HOLD'


def test_senior_mandatory_experience_and_missing_transport_never_send(profile):
    data=inputs(profile);data['job']['title']='Senior IT Support';data['clearance']['experience_met']=False
    assert evaluate_autoapply(**data).outcome=='HOLD'
    data=inputs(profile);data['transport']=[]
    assert 'NO_VERIFIED_ROUND_TRIP_WITHOUT_CAR' in {r.code for r in evaluate_autoapply(**data).reasons}


def test_desirable_skills_are_not_promoted_to_mandatory_and_it_weekends_are_allowed(profile):
    data=inputs(profile);data['job']['description']+='Preferred qualifications\nPython experience desirable.'
    data['clearance']['schedule']='WEEKEND_DAY';data['transport'][0]['details']['schedule']='WEEKEND_DAY'
    assert evaluate_autoapply(**data).outcome=='ALLOW'


@pytest.mark.parametrize('categories',[['IT','Almacen'],['Almacen'],[],['IT','IT']])
def test_new_policy_cannot_allow_general_work(categories):
    config=policy_config();config['categories']=categories
    with pytest.raises(ValueError,match='AUTOAPPLY_IT_ONLY'):Policy(**config)


def test_legacy_policy_is_revoked_without_deleting_history(db,profile):
    config=policy_config();config.update(categories=['IT','Almacen'],engine_version='autoapply-1.0-simulation')
    pid=db.execute('INSERT INTO autoapply_policies(version,created_at,local_user,consent,config,integrity_hash,profile_hash) VALUES(?,?,?,?,?,?,?)',
       ('legacy-test',now(),'synthetic','AUTHORIZE_SIMULATION',json.dumps(config),digest(config),profile_hash(profile)))
    db.execute('UPDATE autoapply_control SET enabled=1,paused=0,policy_id=?',(pid,))
    control,row,policy=current_policy(db,profile)
    assert policy is None and not control['enabled'] and control['paused']
    assert db.rows('SELECT enabled,live_enabled FROM autoapply_control')[0]=={'enabled':0,'live_enabled':0}
    assert len(db.rows('SELECT * FROM autoapply_policies'))==1
    with pytest.raises(ValueError):resume(db,'RESUME_SIMULATION',profile)


def test_forged_allow_plan_and_caller_cannot_prepare_warehouse(db,profile):
    from corkjobradar.autoapply.policy import save_policy
    pid=save_policy(db,policy_config(),'AUTHORIZE_SIMULATION')
    job=stored_job(db,profile)
    db.execute("UPDATE jobs SET title='Warehouse Operative',category='IT' WHERE id=?",(job['id'],))
    plan=save_plan(db,job,Decision('ALLOW',[],'forged-test',100),pid)
    with pytest.raises(PermissionError,match='NON_IT_EXCLUDED'):reserve(db,plan,job)
    assert not db.rows('SELECT * FROM application_attempts')


def test_final_check_reclassifies_functions_from_stored_job(db,profile):
    aid,job=setup_attempt(db,profile)
    db.execute("UPDATE jobs SET title='Warehouse Operative' WHERE id=?",(job['id'],))
    with pytest.raises(PermissionError,match='NON_IT_EXCLUDED'):prefinal_check(db,aid)


def test_invalid_policy_cannot_override_backend_scope(profile):
    data=inputs(profile)
    data['policy']=data['policy'].model_copy(update={'categories':['IT','Almacen']})
    data['job'].update(title='Warehouse Operative',description='Responsibilities\nPick and pack orders.')
    codes={r.code for r in evaluate_autoapply(**data).reasons}
    assert {'NON_IT_EXCLUDED','IT_ONLY_POLICY_REQUIRED'}<=codes
