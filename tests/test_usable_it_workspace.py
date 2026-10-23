"""New assisted workflow: literal requirements, explicit CV review and no sending."""
import json
from datetime import datetime,timedelta
import sqlite3
import pytest
from streamlit.testing.v1 import AppTest
from corkjobradar.config import digest,now
from corkjobradar.db import Database
from corkjobradar.passages import source_passages
from corkjobradar.autoapply.manual_requirements import requirement_items,checklist,review_requirement
from corkjobradar.autoapply.manual_workspace import assess_manual_job,manual_inventory
from corkjobradar.autoapply.vault import approve_fact,candidate_snapshot
from test_autoapply_policy import stored_job
from test_autoapply_vault import populate


def case(db,profile,requirements='1 year of IT support experience required.\nLinux experience preferred.'):
    populate(db)
    approve_fact(db,'claim:duration',{'section':'Experience','text_en':'IT support experience: 1 year and 10 months.'},'SYNTHETIC',True)
    job=stored_job(db,profile)
    description='Responsibilities\nProvide IT support and troubleshoot Windows incidents.\nRequirements\n'+requirements
    db.execute('UPDATE jobs SET description=?,content_hash=?,scope=? WHERE id=?',(description,digest(description),'EN_ALCANCE',job['id']))
    return db.rows('SELECT * FROM jobs WHERE id=?',(job['id'],))[0]


def test_desirable_experience_is_visible_without_disqualifying_or_rounding_duration(db,profile):
    job=case(db,profile);rows=checklist(db,job)
    assert rows[0]['status']=='CUMPLIDO' and rows[0]['level']=='OBLIGATORIO'
    assert rows[1]['status']=='PENDIENTE' and rows[1]['level']=='DESEABLE'
    assessed=assess_manual_job(db,job)
    assert assessed['unmet_mandatory']==0 and assessed['pending_mandatory']==0
    assert not assessed['compatible_verified'] and 'TRANSPORTE_Y_HORARIO_PENDIENTES' in assessed['reasons']
    assert not assessed['api_authorization_required_for_manual']
    assert all('POLICY' not in r and 'PERMISSION' not in r for r in assessed['reasons'])


@pytest.mark.parametrize('quote,status,level',[
 ('2+ years of IT support experience required.','NO_CUMPLIDO','OBLIGATORIO'),
 ('2+ years of experience in IT support, service desk, desktop support or a related technical role.','NO_CUMPLIDO','OBLIGATORIO'),
 ('3 years of IT support experience preferred.','PENDIENTE','DESEABLE'),
 ('Degree or 2+ years of IT support experience required.','PENDIENTE','OBLIGATORIO'),
 ('2+ years of Azure IT support experience required.','PENDIENTE','OBLIGATORIO'),
 ('1 year of IT support experience using Intune required.','PENDIENTE','OBLIGATORIO'),
 ('Own car required.','NO_CUMPLIDO','OBLIGATORIO'),
 ('Own car is not required.','PENDIENTE','DESEABLE'),
 ('Own car or reliable public transport required.','PENDIENTE','OBLIGATORIO'),
 ('Windows required and Linux preferred.','PENDIENTE','POR_ACLARAR'),
 ('Own car required if working at client sites.','PENDIENTE','POR_ACLARAR'),
 ('Must have the right to work in Ireland.','CUMPLIDO','OBLIGATORIO'),
 ('Must have the right to work in Ireland without future sponsorship.','PENDIENTE','OBLIGATORIO')])
def test_atomic_requirements_do_not_invent_education_future_rights_or_tool_experience(db,profile,quote,status,level):
    job=case(db,profile,quote);rows=checklist(db,job)
    assert len(rows)==1 and rows[0]['status']==status and rows[0]['level']==level
    assert job['description'][rows[0]['offset']:rows[0]['offset']+len(rows[0]['quote'])]==rows[0]['quote']


def test_mixed_mandatory_preferred_clauses_and_new_headings_keep_source_quotes(db,profile):
    job=case(db,profile,'Windows knowledge required; Linux knowledge preferred.')
    rows=requirement_items(job)
    assert [r['level'] for r in rows]==['OBLIGATORIO','DESEABLE']
    for heading,field in [('Your Experience','mandatory'),('Your Impact','duties'),('Technical Skills','mandatory')]:
        units,_=source_passages(heading+'\nWindows knowledge required.')
        assert units[0]['section']==field


def test_native_language_and_soft_requirements_are_never_omitted(db,profile):
    job=case(db,profile,'Native Danish speaker.\nExcellent communication skills.\nFrench is desirable.')
    rows=checklist(db,job)
    assert len(rows)==3 and [r['level'] for r in rows]==['OBLIGATORIO','OBLIGATORIO','DESEABLE']
    assert all(r['status']=='PENDIENTE' for r in rows)


def test_user_requirement_review_is_factual_idempotent_immutable_and_version_bound(db,profile):
    job=case(db,profile,'Basic SQL knowledge required.');candidate=candidate_snapshot(db);item=checklist(db,job)[0]
    fid=candidate['_claims'][0]['id']
    def save(**kw):return review_requirement(db,job['id'],item['id'],'CUMPLIDO',[fid],job['content_hash'],candidate['_facts_hash'],**kw)
    with pytest.raises(PermissionError):save()
    rid=save(confirmed=True);assert save(confirmed=True)==rid
    assert checklist(db,job)[0]['status']=='CUMPLIDO'
    with pytest.raises(sqlite3.IntegrityError):db.execute('DELETE FROM manual_requirement_reviews WHERE id=?',(rid,))
    approve_fact(db,'availability','SYNTHETIC changed','SYNTHETIC',True)
    assert checklist(db,job)[0]['status']=='PENDIENTE'
    with pytest.raises(ValueError):save(confirmed=True)
    assert not db.rows('SELECT * FROM application_attempts') and not db.rows('SELECT * FROM user_actions')
    assert not db.rows('SELECT * FROM autoapply_policies') and not db.rows('SELECT * FROM job_clearances')


def test_unknown_requirements_empty_list_and_stale_verification_never_mean_eligible(db,profile):
    job=case(db,profile,'Welcome to the team.')
    db.execute('UPDATE jobs SET open_status=?,last_verified_at=? WHERE id=?',('OPEN_CONFIRMED',(datetime.fromisoformat(now())-timedelta(days=2)).isoformat(),job['id']))
    job=db.rows('SELECT * FROM jobs WHERE id=?',(job['id'],))[0];result=assess_manual_job(db,job)
    assert result['pending_mandatory'] and not result['open_confirmed'] and not result['compatible_verified']


def test_manual_inventory_processes_every_job_and_never_limits_to_few_good_ones(db,profile):
    job=case(db,profile)
    from corkjobradar.repository import save_job
    from corkjobradar.models import Job
    for index in range(6):save_job(db,'a',Job(external_id=str(700+index),title='IT Support',company='SYNTHETIC',url='https://job-boards.greenhouse.io/synthetic/jobs/'+str(700+index),description=job['description'],detail_complete=True),profile=profile)
    inventory=manual_inventory(db)
    assert inventory['jobs_processed']==len(db.rows('SELECT id FROM jobs'))==7
    assert len(inventory['offers'])==7 and not inventory['live_enabled']
    assert candidate_snapshot(db)['email'] not in json.dumps(inventory)


def test_workspace_ui_allows_document_review_but_never_approves_on_preparation(db,profile):
    job=case(db,profile)
    code='from corkjobradar.db import Database\nfrom corkjobradar.autoapply.manual_workspace_ui import render_manual_workspace\nrender_manual_workspace(Database('+repr(str(db.path))+'))'
    app=AppTest.from_string(code).run(timeout=30)
    assert not app.exception
    next(b for b in app.button if b.label=='Preparar CV para este puesto y revisar').click().run(timeout=30)
    assert not app.exception and db.rows('SELECT approved_at FROM candidate_documents')==[{'approved_at':None}]
    assert next(b for b in app.button if b.label=='Aprobar esta versión del CV').disabled
    assert next(b for b in app.button if b.label=='Preparar solicitud manual con mi CV aprobado').disabled
    assert any(c.value=='synthetic@example.invalid' for c in app.code)
    next(c for c in app.checkbox if c.label.startswith('He revisado íntegramente')).check().run()
    next(b for b in app.button if b.label=='Aprobar esta versión del CV').click().run(timeout=30)
    assert not app.exception and candidate_snapshot(db).get('cv_document_id')
    assert not next(b for b in app.button if b.label=='Preparar solicitud manual con mi CV aprobado').disabled
    assert any(b.label=='Descargar CV definitivo aprobado' for b in app.get('download_button'))
    next(b for b in app.button if b.label=='Preparar solicitud manual con mi CV aprobado').click().run(timeout=30)
    assert not app.exception and db.rows('SELECT id FROM manual_application_handoffs')
    assert not db.rows('SELECT * FROM application_attempts') and not db.rows('SELECT * FROM user_actions')


def test_additive_v9_to_v10_keeps_old_rows_and_live_check(db,profile):
    case(db,profile);before=db.rows('SELECT * FROM candidate_facts')
    with db.connect() as con:con.executescript('DROP TABLE manual_requirement_reviews; PRAGMA user_version=9;')
    reopened=Database(db.path)
    assert reopened.rows('PRAGMA user_version')[0]['user_version']==13 and reopened.rows('SELECT * FROM candidate_facts')==before
    assert not reopened.rows('PRAGMA foreign_key_check')
    with pytest.raises(sqlite3.IntegrityError):reopened.execute('UPDATE autoapply_control SET live_enabled=1')


def test_public_greenhouse_job_query_survives_manual_open_without_tracking_or_automation():
    from corkjobradar.autoapply.interaction_modes import manual_target_url,interaction_route
    from corkjobradar.normalization import canonical_url
    url='https://employer.example/job-detail/?gh_jid=12345&gh_jid=12345&utm_source=test&token=SECRET'
    clean=manual_target_url(url)
    assert clean=='https://employer.example/job-detail/?gh_jid=12345'
    assert not interaction_route(clean)['automation_allowed']
    assert canonical_url('https://employer.example/job-detail/?gh_jid=12345&gh_jid=12345')==canonical_url(clean)
    with pytest.raises(ValueError):manual_target_url('https://employer.example/job-detail/?gh_jid=123&gh_jid=456')
    with pytest.raises(ValueError):manual_target_url('https://employer.example/job-detail/?session=SECRET')


def test_assisted_route_can_be_reviewed_without_autoapply_clearance_or_policy(db,profile,monkeypatch):
    from corkjobradar.autoapply.manual_workspace import save_manual_transport
    import corkjobradar.http as http
    monkeypatch.setattr(http,'validate_url',lambda url:url)
    job=case(db,profile)
    details={'destination':'SYNTHETIC work site','outbound':'SYNTHETIC checked bicycle outbound','return':'SYNTHETIC checked bicycle return',
             'origin_access':'SYNTHETIC access from Ballinlough','days':['Monday','Tuesday'],'shift_start':'09:00','shift_end':'17:00',
             'shift_compatible':True,'duration_minutes':25,'valid_until':(datetime.fromisoformat(now())+timedelta(days=1)).date().isoformat()}
    with pytest.raises(PermissionError):save_manual_transport(db,job['id'],'bicycle','https://evidence.invalid/route',details,job['content_hash'])
    save_manual_transport(db,job['id'],'bicycle','https://evidence.invalid/route',details,job['content_hash'],confirmed=True)
    assessed=assess_manual_job(db,job)
    assert assessed['transport_verified'] and assessed['shift_start']=='09:00'
    db.execute('UPDATE jobs SET open_status=?,last_verified_at=? WHERE id=?',('OPEN_CONFIRMED',now(),job['id']))
    current=db.rows('SELECT * FROM jobs WHERE id=?',(job['id'],))[0]
    assert assess_manual_job(db,current)['state']=='COMPATIBLE_VERIFICADA'
    missing_auth=candidate_snapshot(db);missing_auth.pop('work_authorization')
    assert not assess_manual_job(db,current,missing_auth)['compatible_verified']
    assert not db.rows('SELECT * FROM job_clearances') and not db.rows('SELECT * FROM autoapply_policies')
    assert db.rows('SELECT live_enabled FROM autoapply_control')[0]['live_enabled']==0
    changed={**job,'content_hash':'CHANGED'}
    assert not assess_manual_job(db,changed)['transport_verified']
    for update in ({'days':[]},{'days':['A day']},{'shift_end':'07:00'},{'duration_minutes':0},{'shift_compatible':False}):
        with pytest.raises(ValueError):save_manual_transport(db,job['id'],'bicycle','https://evidence.invalid/route',{**details,**update},job['content_hash'],confirmed=True)


def test_introduction_uses_only_approved_claims_for_an_entry_level_profile(db,profile):
    from corkjobradar.autoapply.manual_workspace import factual_introduction
    job=case(db,profile);candidate=candidate_snapshot(db)
    candidate['_claims']=[c for c in candidate['_claims'] if c['section']!='Experience']
    text=factual_introduction(candidate,job)
    assert candidate['_claims'][0]['text_en'] in text and 'My verified background includes' in text
    assert 'certified' not in text.lower() and 'fluent' not in text.lower()


@pytest.mark.parametrize('change',['none','url_mismatch','source_revoked'])
def test_custom_employer_greenhouse_questions_use_bound_public_source_without_granting_automation(db,profile,change):
    import httpx
    from conftest import client
    from test_autoapply_public_forms import schema
    from corkjobradar.autoapply.forms import inspect_job_form,load_inspection,answer_plan
    from corkjobradar.autoapply.platforms import platform_for
    populate(db);job=stored_job(db,profile,url='https://employer.example/job-detail/?gh_jid=321')
    db.execute("UPDATE sources SET kind='greenhouse',url='https://boards-api.greenhouse.io/v1/boards/synthetic/jobs',permission='PUBLIC_API_DOCUMENTADA' WHERE id='a'")
    db.execute("UPDATE job_sources SET external_id='321' WHERE job_id=?",(job['id'],))
    data={**schema(),'absolute_url':job['url'] if change!='url_mismatch' else 'https://other.example/job/321'}
    seen=[]
    def handler(req):
        seen.append((req.method,str(req.url)))
        return httpx.Response(200,text='User-agent: *\nAllow: /') if req.url.path=='/robots.txt' else httpx.Response(200,json=data)
    with client(profile,handler) as web:
        if change=='url_mismatch':
            with pytest.raises(ValueError,match='URL_MISMATCH'):inspect_job_form(db,job['id'],web)
            assert not db.rows('SELECT * FROM autoapply_form_inspections');return
        inspection=inspect_job_form(db,job['id'],web)
    assert all(method=='GET' and 'employer.example' not in url for method,url in seen)
    assert not platform_for(job['url'])['automation_permitted'] and not inspection['remote_fill_authorized']
    assert load_inspection(db,inspection['inspection_id'])['public_url']==job['url']
    plan=answer_plan(inspection,candidate_snapshot(db));assert plan['answer_host']=='employer.example'
    if change=='source_revoked':
        db.execute("UPDATE sources SET enabled=0 WHERE id='a'")
        with pytest.raises(ValueError):load_inspection(db,inspection['inspection_id'])
    assert not db.rows('SELECT * FROM application_attempts') and not db.rows('SELECT * FROM user_actions')


def test_ambiguous_role_does_not_prevent_general_cv_review_or_clear_it_hold(db,profile):
    job=case(db,profile)
    db.execute('UPDATE jobs SET description=? WHERE id=?',('Requirements\nExcellent IT skills required.',job['id']))
    app=AppTest.from_string('from corkjobradar.db import Database\nfrom corkjobradar.autoapply.manual_workspace_ui import render_manual_workspace\nrender_manual_workspace(Database('+repr(str(db.path))+'))').run(timeout=30)
    next(b for b in app.button if b.label=='Preparar CV general con mis hechos para revisar').click().run(timeout=30)
    assert not app.exception and db.rows('SELECT approved_at FROM candidate_documents')==[{'approved_at':None}]
    assert next(b for b in app.button if b.label=='Preparar solicitud manual con mi CV aprobado').disabled
    assert assess_manual_job(db,db.rows('SELECT * FROM jobs WHERE id=?',(job['id'],))[0])['it_status']=='AMBIGUOUS'
