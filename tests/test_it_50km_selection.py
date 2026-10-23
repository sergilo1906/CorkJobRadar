"""User's broad IT policy, real SQLite/DPAPI/queue and guarded final eligibility."""
import json
import math
import sqlite3
from datetime import datetime,timedelta
from concurrent.futures import ThreadPoolExecutor
import pytest
from corkjobradar.config import digest,now
from corkjobradar.autoapply.broad_selection import assess_selection,selection_inventory,experience_requirements,RULES_VERSION
from corkjobradar.autoapply.radius import DEFAULT_ORIGIN,distance_km,save_origin,origin,save_worksite
from corkjobradar.autoapply.selection_queue import refresh_queue,claim_preparation,finish_preparation,prepare_all_local
from corkjobradar.autoapply.vault import candidate_snapshot
from corkjobradar.autoapply.eligibility import evaluate_autoapply
from corkjobradar.autoapply.it_scope import classify_it_functions
from test_usable_it_workspace import case


def placed(db,profile,requirements='2 years of IT support experience required.',distance=20):
    job=case(db,profile,requirements)
    db.execute('UPDATE jobs SET open_status=?,last_verified_at=? WHERE id=?',('OPEN_CONFIRMED',now(),job['id']))
    job=db.rows('SELECT * FROM jobs WHERE id=?',(job['id'],))[0]
    lat=DEFAULT_ORIGIN['latitude']+math.degrees(distance/6371.0088)
    save_worksite(db,job['id'],lat,DEFAULT_ORIGIN['longitude'],'https://employer.example/careers',job['content_hash'],confirmed=True)
    return job


@pytest.mark.parametrize('km,state',[(49,'WITHIN_RADIUS'),(50,'WITHIN_RADIUS'),(51,'OUTSIDE_RADIUS')])
def test_exact_radius_uses_unrounded_great_circle_distance(db,profile,km,state):
    job=placed(db,profile,distance=km);r=assess_selection(db,job)
    assert r['geography']['state']==state
    assert r['geography']['distance_km']==pytest.approx(km,abs=1e-9)
    assert ('OUTSIDE_50_KM' in r['exclusions'])==(km>50)
    assert distance_km(0,0,0,0)==0


@pytest.mark.parametrize('q,excluded',[
 ('0 years of IT support experience required.',False),
 ('1 year of IT support experience required.',False),
 ('2 years of IT support experience required.',False),
 ('3 years of IT support experience required.',False),
 ('3+ years of IT support experience required.',False),
 ('3–5 years of IT support experience required.',False),
 ('At least three years of experience in IT support.',False),
 ('A minimum of 3 years plus experience in IT support.',False),
 ('4 years of IT support experience required.',True),
 ('5 years of IT support experience required.',True),
 ('At least four years of experience in SQL required.',True),
 ('More than 3 years of experience required.',True),
 ('Over 3 years of experience required.',True),
 ('36 months of experience required.',False),
 ('37 months of experience required.',True),
 ('5 years of experience preferred.',False),
 ('5 years of experience is a plus.',False),
 ('No experience required.',False),
 ('Windows knowledge required.',False),
 ('Degree or 5 years of IT support experience required.',False),
    ('4 years of experience with Windows required; 5 years of SQL experience preferred.',True),
    ('4 years of experience required, 5 years preferred.',True),
    ('3 years of experience required and 5 years preferred.',False),
    ('Up to 5 years of experience required.',False),
    ('No more than 5 years of experience required.',False),
    ('4 yrs of experience required.',True),
    ('3+ yrs experience required.',False),
    ('36 mos experience required.',False),
    ('4 years in IT support required.',True),
    ('3 years in IT support required.',False),
    ('4 year contract, no experience required.',False),
])
def test_minimum_experience_is_requested_requirement_not_candidate_claim(db,profile,q,excluded):
    job=placed(db,profile,q);r=assess_selection(db,job)
    assert ('MANDATORY_MINIMUM_EXPERIENCE_OVER_3' in r['exclusions'])==excluded
    assert any('1 year and 10 months' in c['text_en'] for c in candidate_snapshot(db)['_claims'])
    assert not db.rows('SELECT * FROM autoapply_policies')


def test_shortfall_and_academic_technical_doubts_are_warnings_not_false_success(db,profile):
    job=placed(db,profile,'3 years of IT support experience required.\nDegree in computing required.\nAzure experience preferred.')
    r=assess_selection(db,job)
    assert r['professional_state']=='ENVIABLE_CON_ADVERTENCIAS'
    assert 'EXPERIENCE_SHORTFALL_DISCLOSED' in r['warnings']
    assert r['selection_eligible'] and r['state']=='INTERVENCION_REQUERIDA'
    assert r['operational_pending']==['APPROVED_CV_PENDING'] and not r['exclusions']
    assert not r['live_enabled']


@pytest.mark.parametrize('heading,quote,excluded',[
    ('Experience','4+ years.',True),
    ('Required experience','3–5 years.',False),
    ('Preferred experience','5 years.',False),
    ('Requirements','4 year degree in computing required.',False),
    ('Requirements','4 year contract required.',False),
])
def test_experience_section_context_without_mistaking_education_or_contract_years(db,profile,heading,quote,excluded):
    job=placed(db,profile,heading+'\n'+quote)
    assert ('MANDATORY_MINIMUM_EXPERIENCE_OVER_3' in assess_selection(db,job)['exclusions'])==excluded


@pytest.mark.parametrize('q,exclusion',[
 ('Own car required.','OWN_CAR_REQUIRED'),
 ('Must own a personal vehicle.','OWN_CAR_REQUIRED'),
])
def test_explicit_own_car_requirement_blocks_even_without_route(db,profile,q,exclusion):
    job=placed(db,profile,q);r=assess_selection(db,job)
    assert r['state']=='EXCLUIDA' and (exclusion in r['exclusions'] or 'PROVEN_MANDATORY_INCOMPATIBILITY' in r['exclusions'])


@pytest.mark.parametrize('q',['Own car or reliable public transport required.','Own car is not required.'])
def test_car_alternatives_and_negation_do_not_exclude(db,profile,q):
    job=placed(db,profile,q);assert not assess_selection(db,job)['exclusions']


def test_unknown_legal_answer_is_essential_and_optional_legal_is_warning(db,profile):
    job=placed(db,profile,'Security clearance required.\nDriving licence preferred.')
    r=assess_selection(db,job);assert r['professional_state']=='INTERVENCION_REQUERIDA'
    assert r['essential_pending']==['ESSENTIAL_LEGAL_OR_LICENSE_ANSWER_PENDING']


def test_pending_route_warns_and_failed_bus_is_not_total_incompatibility(db,profile):
    job=placed(db,profile);r=assess_selection(db,job)
    assert r['selection_eligible'] and 'COMMUTE_AND_SHIFT_PENDING' in r['warnings']
    details={'job_content_hash':job['content_hash'],'valid_until':now()[:10]}
    db.execute('INSERT INTO commute_checks(job_id,origin,mode,viability,evidence_url,checked_at,details) VALUES(?,?,?,?,?,?,?)',
               (job['id'],'Ballinlough','bus','NO_VIABLE','https://www.transportforireland.ie/',now(),json.dumps(details)))
    assert assess_selection(db,job)['selection_eligible']
    details['all_available_modes_incompatible']=True
    db.execute('UPDATE commute_checks SET details=?',(json.dumps(details),))
    assert 'PROVEN_COMMUTE_INCOMPATIBILITY' in assess_selection(db,job)['exclusions']


def test_location_unknown_is_kept_remote_is_separate_and_old_scope_not_radius(db,profile):
    job=case(db,profile);db.execute("UPDATE jobs SET scope='FUERA_DE_ALCANCE' WHERE id=?",(job['id'],))
    job=db.rows('SELECT * FROM jobs WHERE id=?',(job['id'],))[0]
    r=assess_selection(db,job);assert not r['exclusions'] and 'WORKSITE_RADIUS_PENDING' in r['essential_pending']
    job['mode']='REMOTE';job['location']='Remote Ireland'
    assert assess_selection(db,job)['geography']['state']=='REMOTE_SEPARATE'
    assert 'REMOTE_ADDITIONAL_AUTHORIZATION_REQUIRED' in assess_selection(db,job)['essential_pending']


def test_published_coordinate_without_address_is_not_proved_worksite(db,profile):
    job=case(db,profile);raw=json.loads(job['raw'])
    raw['jobLocation']={'geo':{'latitude':51.89,'longitude':-8.45},'address':{'addressLocality':'Cork'}}
    job['raw']=json.dumps(raw)
    assert assess_selection(db,job)['geography']['state']=='LOCATION_PENDING'
    raw['jobLocation']['address']['streetAddress']='SYNTHETIC WORKSITE'
    job['raw']=json.dumps(raw)
    assert assess_selection(db,job)['geography']['state']=='WITHIN_RADIUS'


@pytest.mark.parametrize('title,duty,expected',[
 ('Junior Java Developer','Develop Java software applications.','CONFIRMED_IT'),
 ('Web Developer','Build websites using HTML and CSS.','CONFIRMED_IT'),
 ('Software Tester','Execute automated software tests and report software bugs.','CONFIRMED_IT'),
 ('Application Support','Troubleshoot application incidents and database errors.','CONFIRMED_IT'),
 ('Junior Networks','Configure computer networks and maintain Linux servers.','CONFIRMED_IT'),
 ('Warehouse operative','Pick and pack goods and orders.','NON_IT'),
 ('Customer Service','Handle billing and delivery complaints.','NON_IT'),
 ('IT Technician','Welcome to our computer company.','AMBIGUOUS'),
])
def test_dam_related_roles_need_actual_technical_functions(db,profile,title,duty,expected):
    job=case(db,profile);job.update(title=title,category='Otras',description='Responsibilities\n'+duty+'\nRequirements\nWillingness to learn.')
    assert classify_it_functions(job).status==expected


def test_private_origin_is_encrypted_bound_and_never_in_report(db,profile):
    job=placed(db,profile);before=assess_selection(db,job)
    with pytest.raises(PermissionError):save_origin(db,51.890123456,-8.440987654)
    save_origin(db,51.890123456,-8.440987654,confirmed=True)
    assert origin(db)['latitude']==51.890123456
    report=json.dumps(selection_inventory(db));assert '51.890123456' not in report and '-8.440987654' not in report
    row=db.rows('SELECT * FROM it_selection_origins')[0];assert b'51.890123456' not in row['encrypted_value']
    assert assess_selection(db,job)['origin_hash']!=before['origin_hash']
    assert len(db.rows('SELECT * FROM candidate_facts'))==len(candidate_snapshot(db)['_fact_ids'])+len(candidate_snapshot(db)['_claims'])


def test_worksite_binding_stales_after_description_change_and_requires_consent(db,profile):
    job=placed(db,profile)
    with pytest.raises(PermissionError):save_worksite(db,job['id'],51.89,-8.45,'https://employer.example',job['content_hash'])
    job['content_hash']='changed';assert assess_selection(db,job)['geography']['state']=='LOCATION_PENDING'


def test_all_rows_persist_idempotently_and_claims_survive_restart(db,profile):
    job=placed(db,profile)
    from corkjobradar.repository import save_job
    from corkjobradar.models import Job
    for i in range(26):save_job(db,'a',Job(external_id=str(800+i),company='SYNTHETIC',title='IT Support',url='https://jobs.example/'+str(i),description=job['description'],detail_complete=True),profile=profile)
    report=refresh_queue(db);assert report['jobs_processed']==27
    events=db.rows('SELECT * FROM it_application_queue_events');refresh_queue(db)
    assert db.rows('SELECT * FROM it_application_queue_events')==events
    from corkjobradar.db import Database
    reopened=Database(db.path)
    assert len(reopened.rows('SELECT * FROM it_application_queue'))==27
    with ThreadPoolExecutor(max_workers=2) as pool:claims=list(pool.map(lambda _:claim_preparation(db),range(2)))
    assert claims[0]['job_id']!=claims[1]['job_id']
    finish_preparation(db,claims[0],'INTERVENTION','SYNTHETIC_TEST')
    with pytest.raises(PermissionError):finish_preparation(db,claims[0],'MANUAL_READY','INVALID_OLD_OWNER')
    db.execute('UPDATE it_application_queue SET lease_until=? WHERE job_id=?',('2000-01-01T00:00:00+00:00',claims[1]['job_id']))
    refresh_queue(db)
    assert reopened.rows("SELECT workflow_state FROM it_application_queue WHERE job_id=?",(claims[1]['job_id'],))[0]['workflow_state']=='PENDING'
    assert not db.rows('SELECT * FROM application_attempts')


def test_duplicate_is_retained_but_not_prepared_or_confirmed(db,profile):
    job=placed(db,profile)
    db.execute('INSERT INTO user_actions(job_id,action,created_at) VALUES(?,?,?)',(job['id'],'solicitada',now()))
    r=assess_selection(db,job);assert r['duplicate'] and not r['preparation_allowed']
    assert r['state']=='INTERVENCION_REQUERIDA' and 'ALREADY_APPLIED_OR_RESERVED' in r['operational_pending']
    refresh_queue(db);assert db.rows('SELECT workflow_state FROM it_application_queue')[0]['workflow_state']=='DUPLICATE'


def test_local_preparation_stops_at_cv_consent_and_does_not_create_attempts(db,profile):
    placed(db,profile);counts=prepare_all_local(db)
    assert counts['intervention']==1 and counts['submitted']==counts['external_requests']==0
    assert not db.rows('SELECT * FROM manual_application_handoffs') and not db.rows('SELECT * FROM application_attempts')
    assert not db.rows('SELECT * FROM autoapply_policies')
    assert db.rows('SELECT live_enabled FROM autoapply_control')[0]['live_enabled']==0


def test_broad_auto_gate_has_no_score_shortfall_or_route_hold_but_keeps_permission_and_cv(db,profile):
    job=placed(db,profile,'3 years of IT support experience required.')
    from corkjobradar.autoapply.policy import Policy
    candidate=candidate_snapshot(db);o=origin(db)
    config={'expires_at':(datetime.fromisoformat(now())+timedelta(days=1)).isoformat(),
            'selection_mode':'IT_50KM_MAX3','selection_rules_version':RULES_VERSION,'selection_origin_hash':o['binding_hash'],
            'modes':['ONSITE','DESCONOCIDO'],'allowed_hosts':['job-boards.greenhouse.io'],
            'candidate_facts_hash':candidate['_facts_hash'],'authorized_document_ids':[],
            'permissions':{'generate_cv':True,'attach_cv':True,'fill_forms':True},'it':{'full_time_required':False}}
    policy=Policy.model_validate(config)
    data=dict(job=job,analysis={},profile=profile,policy=policy,control={'enabled':1,'paused':0},candidate=candidate,db=db)
    reasons={r.code for r in evaluate_autoapply(**data).reasons}
    assert {'VERIFIED_CV_MISSING','AUTOMATION_PERMISSION_MISSING'}.issubset(reasons)
    assert not {'SCORE_BELOW_POLICY','CONFIDENCE_BELOW_POLICY','MANDATORY_REQUIREMENTS_UNRESOLVED','EXPERIENCE_INCOMPATIBLE_OR_UNKNOWN','NO_VERIFIED_ROUND_TRIP_WITHOUT_CAR','VERIFIED_REQUIREMENTS_AND_TERMS_MISSING'}&reasons
    save_origin(db,52.8,-8.4,confirmed=True)
    assert 'RADIUS_POLICY_BINDING_CHANGED' in {r.code for r in evaluate_autoapply(**data).reasons}


@pytest.mark.parametrize('url,mode',[('https://www.linkedin.com/jobs/view/123','LINKEDIN_MANUAL'),('https://ie.indeed.com/viewjob?jk=abcdef12345678','INDEED_MANUAL')])
def test_eligibility_does_not_automate_forbidden_platforms(db,profile,url,mode):
    job=placed(db,profile);job['apply_url']=url
    result=assess_selection(db,job)
    assert result['interaction_mode']==mode and result['professional_state']=='ENVIABLE_CON_ADVERTENCIAS'
    assert not result['live_enabled']


def test_additive_schema_keeps_all_old_rows_and_live_constraint(db,profile):
    from corkjobradar.db import Database
    job=placed(db,profile);before=db.rows('SELECT * FROM jobs')
    for table in ['it_application_queue_events','it_application_queue','it_worksite_evidence','it_selection_origins']:db.execute('DROP TABLE '+table)
    db.execute('PRAGMA user_version=10')
    reopened=Database(db.path)
    assert reopened.rows('SELECT * FROM jobs')==before
    assert reopened.rows('PRAGMA user_version')[0]['user_version']==13
    assert not reopened.rows('PRAGMA foreign_key_check')
    with pytest.raises(sqlite3.IntegrityError):reopened.execute('UPDATE autoapply_control SET live_enabled=1')


def approve_synthetic_cv(db):
    from corkjobradar.autoapply.documents import render_cv,create_cv_review,cv_review_bytes,approve_cv_review
    candidate=candidate_snapshot(db);did=create_cv_review(db,render_cv(candidate,'pdf'),'pdf')
    _,_,sha,_=cv_review_bytes(db,did)
    approve_cv_review(db,did,sha,candidate['_facts_hash'],confirmed=True)
    return did


def test_complete_local_queue_uses_approved_cv_without_rewriting_facts_or_sending(db,profile):
    job=placed(db,profile,'3 years of IT support experience required.\nAzure knowledge preferred.')
    from corkjobradar.autoapply.vault import approve_fact
    approve_fact(db,'linkedin_url','https://www.linkedin.com/in/synthetic-only/','SYNTHETIC',True)
    did=approve_synthetic_cv(db);facts=db.rows('SELECT * FROM candidate_facts')
    counts=prepare_all_local(db)
    assert counts['processed']==counts['manual_ready']==1 and counts['errors']==counts['submitted']==0
    from corkjobradar.autoapply.handoff import load_handoff,handoff_download
    row=db.rows('SELECT * FROM it_application_queue')[0]
    payload=load_handoff(db,row['handoff_id'])
    assert payload['document_id']==did and payload['contacts']['email']=='synthetic@example.invalid'
    assert payload['contacts']['linkedin_url'].startswith('https://www.linkedin.com/')
    assert payload['selection_review']['professional_state']=='ENVIABLE_CON_ADVERTENCIAS'
    import io,zipfile
    with zipfile.ZipFile(io.BytesIO(handoff_download(db,row['handoff_id']))) as archive:
        assert archive.read('CV.pdf').startswith(b'%PDF')
        assert 'Advertencias' in archive.read('CANDIDATURA.txt').decode()
    assert prepare_all_local(db)['processed']==0
    assert db.rows('SELECT * FROM candidate_facts')==facts
    assert not db.rows('SELECT * FROM application_attempts') and not db.rows('SELECT * FROM user_actions')
    assert not db.rows('SELECT * FROM autoapply_policies')


def test_broad_policy_can_allow_owned_simulation_without_score_route_or_experience_met(db,profile):
    job=placed(db,profile,'3 years of IT support experience required.');did=approve_synthetic_cv(db)
    from corkjobradar.autoapply.policy import Policy
    from urllib.parse import urlsplit
    candidate=candidate_snapshot(db)
    config={'expires_at':(datetime.fromisoformat(now())+timedelta(days=1)).isoformat(),
            'selection_mode':'IT_50KM_MAX3','selection_rules_version':RULES_VERSION,'selection_origin_hash':origin(db)['binding_hash'],
            'modes':[job['mode']],'allowed_hosts':[urlsplit(job.get('apply_url') or job['url']).hostname],
            'candidate_facts_hash':candidate['_facts_hash'],'authorized_document_ids':[did],
            'adapter_versions':{'owned-synthetic':'v1'},'window_start':'00:00','window_end':'23:59',
            'permissions':{'generate_cv':True,'attach_cv':True,'fill_forms':True},'it':{'full_time_required':False}}
    policy=Policy.model_validate(config)
    args=dict(job=job,analysis={},profile=profile,policy=policy,control={'enabled':1,'paused':0},candidate=candidate,db=db,
              platform={'id':'owned-synthetic','version':'v1','verified':True,'automation_permitted':True})
    result=evaluate_autoapply(**args)
    assert result.outcome=='ALLOW',result.to_dict()
    # This proves selection only, not a released remote transport or LIVE consent.
    assert db.rows('SELECT live_enabled FROM autoapply_control')[0]['live_enabled']==0
    args['platform']['automation_permitted']=False
    assert 'AUTOMATION_PERMISSION_MISSING' in {r.code for r in evaluate_autoapply(**args).reasons}


def test_uncertain_queue_never_retries_and_a_local_receipt_cannot_confirm_external(db,profile):
    job=placed(db,profile)
    from corkjobradar.autoapply.store import save_plan,identities
    from corkjobradar.autoapply.eligibility import Decision
    pid=save_plan(db,job,Decision('HOLD',[],None,None),None,environment='LIVE')
    aid=db.execute('INSERT INTO application_attempts(plan_id,state,adapter,target_url,started_at,updated_at,policy_epoch) VALUES(?,?,?,?,?,?,?)',
                   (pid,'ENVIO_INCIERTO','SYNTHETIC_STATE_ONLY',job['url'],now(),now(),0))
    for key in identities(job):db.execute('INSERT INTO application_identities VALUES(?,?,?)',(key,'LIVE',aid))
    assert assess_selection(db,job)['state']=='ENVIO_INCIERTO'
    refresh_queue(db);assert db.rows('SELECT workflow_state FROM it_application_queue')[0]['workflow_state']=='UNCERTAIN'
    assert prepare_all_local(db)['processed']==0
    db.execute("UPDATE application_attempts SET state='ENVIADA_CONFIRMADA' WHERE id=?",(aid,))
    db.execute('INSERT INTO application_receipt_evidence(attempt_id,received_at,environment,platform,evidence_hash,encrypted_path,status) VALUES(?,?,?,?,?,?,?)',
               (aid,now(),'SIMULATION','synthetic','fake-local-hash','not-a-real-file','VERIFIED_REAL_RECEIPT'))
    assert assess_selection(db,job)['state']=='ENVIO_INCIERTO'


def test_preparation_visits_more_than_twenty_eligible_records_and_resumes_without_duplicates(db,profile,monkeypatch):
    # Reserved synthetic host has no DNS. No production URL validation is relaxed.
    from corkjobradar.autoapply import handoff
    monkeypatch.setattr(handoff,'validate_url',lambda url:url)
    job=placed(db,profile);approve_synthetic_cv(db)
    from corkjobradar.repository import save_job
    from corkjobradar.models import Job
    for index in range(26):
        save_job(db,'a',Job(external_id=str(1900+index),title='IT Support '+str(index),company='SYNTHETIC '+str(index),
                 url='https://jobs.example/it-'+str(index),description=job['description'],detail_complete=True),profile=profile)
    counts=prepare_all_local(db)
    assert counts['processed']==counts['manual_ready']==27 and counts['errors']==0
    assert len(db.rows('SELECT * FROM manual_application_handoffs'))==27
    assert prepare_all_local(db)['processed']==0
    assert len(db.rows('SELECT * FROM manual_application_handoffs'))==27
    assert not db.rows('SELECT * FROM application_attempts') and not db.rows('SELECT * FROM user_actions')
