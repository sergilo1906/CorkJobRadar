"""New read-only discovery, real public HTML fixture, no live forms or identity."""
import json
from pathlib import Path
import httpx
import pytest
from corkjobradar.adapters import CareerTabs
from corkjobradar.junior_discovery import prepare_junior_search,discovery_report
from corkjobradar.repository import save_job,reconcile_duplicate_urls
from corkjobradar.autoapply.store import already_applied
from corkjobradar.worker import run_worker
from conftest import source,client

FIXTURE=Path(__file__).parent/'fixtures/usable-it/evosoft-career-tabs-20261021.html'


def test_installed_catalog_is_valid_and_distinguishes_manual_and_public_read_channels():
    from corkjobradar.junior_discovery import source_catalog,manual_channels,ROLE_QUERIES
    assert len(source_catalog())==3 and len(manual_channels())==6
    assert all(s['enabled'] and s['permission'] in {'PUBLIC_API_DOCUMENTADA','HTML_PUBLICO_REVISADO'} for s in source_catalog())
    assert all(not c.get('enabled') for c in manual_channels()) and len(ROLE_QUERIES)==11


def test_dedup_preserves_immutable_manual_requirement_reviews(db,profile):
    from test_usable_it_workspace import case
    from test_autoapply_policy import stored_job
    from corkjobradar.autoapply.manual_requirements import requirement_items,review_requirement
    from corkjobradar.autoapply.vault import candidate_snapshot
    first=stored_job(db,profile,external='other',url='https://employer.example/first')
    reviewed=case(db,profile,'Basic SQL knowledge required.');candidate=candidate_snapshot(db)
    item=requirement_items(reviewed)[0]
    rid=review_requirement(db,reviewed['id'],item['id'],'PENDIENTE',[],reviewed['content_hash'],candidate['_facts_hash'],confirmed=True)
    db.execute('UPDATE jobs SET url=?,company=? WHERE id=?',(first['url'],first['company'],reviewed['id']))
    assert not reconcile_duplicate_urls(db)
    assert len(db.rows('SELECT id FROM jobs'))==2 and db.rows('SELECT id FROM manual_requirement_reviews')==[{'id':rid}]
    assert not db.rows('PRAGMA foreign_key_check')


def parsed(db,profile,body=None):
    src=source(db,'career_tabs',url='https://synthetic.example/careers')
    def handler(req):return httpx.Response(200,text='User-agent: *\nAllow: /' if req.url.path=='/robots.txt' else body or FIXTURE.read_text(encoding='utf-8'))
    with client(profile,handler) as web:page=next(CareerTabs(src,web,profile).discover())
    return src,page


def test_real_public_career_tabs_keep_roles_separate_and_never_borrow_senior_duties(db,profile):
    src,page=parsed(db,profile)
    assert len(page.jobs)==4 and page.complete
    junior=next(j for j in page.jobs if j.title=='Junior Support Technician')
    assert 'business logic is desirable' in junior.description and 'mentor a team' not in junior.description
    assert junior.location=='No indicado por la empresa' and junior.mode=='DESCONOCIDO'
    ids=[save_job(db,src['id'],job,profile=profile) for job in page.jobs]
    assert len(set(ids))==4 and len(db.rows('SELECT id FROM jobs'))==4
    assert ids==[save_job(db,src['id'],job,profile=profile) for job in page.jobs]
    assert not reconcile_duplicate_urls(db) and len(db.rows('SELECT id FROM jobs'))==4
    # One shared form cannot collapse all jobs or incorrectly block other published positions.
    db.execute("INSERT INTO user_actions(job_id,action,notes,created_at) VALUES(?,?,?,?)",(ids[0],'solicitada','','2026-10-21T12:00:00+01:00'))
    assert already_applied(db,db.rows('SELECT * FROM jobs WHERE id=?',(ids[0],))[0],'LIVE')
    assert not already_applied(db,db.rows('SELECT * FROM jobs WHERE id=?',(ids[3],))[0],'LIVE')


def test_missing_panel_is_retained_as_explicit_error_instead_of_losing_other_roles(db,profile):
    body=FIXTURE.read_text(encoding='utf-8').replace('aria-controls="elementor-tab-content-1744"','aria-controls="MISSING"')
    src,page=parsed(db,profile,body)
    assert len(page.jobs)==4 and not page.complete
    held=next(j for j in page.jobs if j.title=='Junior Support Technician')
    assert held.raw['_parse_error']=='CAREER_PANEL_BINDING_FAILED' and not held.detail_complete


def test_focused_scan_uses_existing_queue_keeps_every_record_and_disabled_sources(db,profile,monkeypatch):
    import corkjobradar.junior_discovery as discovery
    src=source(db,'career_tabs',url='https://synthetic.example/careers')
    monkeypatch.setattr(discovery,'source_catalog',lambda:[{**src,'enabled':True}])
    monkeypatch.setattr(discovery,'load_profile',lambda:profile)
    requests=[]
    def handler(req):
        requests.append(req.method)
        return httpx.Response(200,text='User-agent: *\nAllow: /' if req.url.path=='/robots.txt' else FIXTURE.read_text(encoding='utf-8'))
    rid=prepare_junior_search(db)
    with pytest.raises(RuntimeError):prepare_junior_search(db)
    with client(profile,handler) as web:run_worker(db,rid,web)
    report,path=discovery_report(db,rid)
    assert report['run']['status']=='completed' and report['all_retrieved_retained']==4
    assert all(j['analysis_status']!='PENDIENTE' for j in report['jobs'])
    assert set(requests)=={'GET'} and not db.rows('SELECT * FROM application_attempts')
    assert not db.rows('SELECT * FROM user_actions')
    assert db.rows('SELECT live_enabled FROM autoapply_control')[0]['live_enabled']==0
    db.execute('UPDATE sources SET enabled=0 WHERE id=?',(src['id'],))
    with pytest.raises(RuntimeError,match='NO_REVIEWED'):prepare_junior_search(db)


def test_actual_internship_duties_confirm_application_support_without_using_employer_or_title(db,profile):
    from corkjobradar.adapters import Greenhouse
    from corkjobradar.autoapply.it_scope import classify_it_functions
    raw=json.loads((FIXTURE.parent/'solarwinds-support-internship-20261021.json').read_text(encoding='utf-8'))
    src=source(db,'greenhouse');job=Greenhouse(src,None,profile).normalize(raw).model_dump()
    job['category']='IT'
    result=classify_it_functions(job)
    assert result.status=='CONFIRMED_IT' and 'APPLICATION_SUPPORT' in result.families
    assert all(e['quote'] in job['description'] for e in result.evidence)
    # Same employer/title without those functions cannot confer IT eligibility.
    job['description']='Responsibilities\nServe food and drinks to customers.\nRequirements\nWindows knowledge preferred.'
    assert classify_it_functions(job).status=='NON_IT'


@pytest.mark.parametrize('variant,expected',[('exact','OPEN_CONFIRMED'),('no_option','OPEN_LIKELY'),('removed','UNLISTED'),('changed','UNKNOWN')])
def test_shared_page_form_never_confirms_a_missing_or_changed_role(db,profile,variant,expected):
    from corkjobradar.verification import verify_job
    src,page=parsed(db,profile);job=page.jobs[-1];jid=save_job(db,src['id'],job,profile=profile)
    body=FIXTURE.read_text(encoding='utf-8')
    if variant=='removed':body=body.replace('Junior Support Technician','A different role')
    if variant=='changed':body=body.replace('expanding support','changed support')
    if variant!='no_option':body+='<form><select><option>Junior Support Technician</option></select><input type="file"></form>'
    def handler(req):return httpx.Response(200,text='User-agent: *\nAllow: /' if req.url.path=='/robots.txt' else body)
    with client(profile,handler) as web:assert verify_job(db,jid,web)==expected
