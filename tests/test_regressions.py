import json
import httpx
from corkjobradar.worker import create_run,run_worker
from corkjobradar.models import Job
from corkjobradar.config import load_profile
from corkjobradar.geography import scope_for
from corkjobradar.analysis import extract
from conftest import source,client,fixture

def test_malformed_card_is_preserved_and_does_not_hide_valid_cards(db,profile):
    source(db,'greenhouse')
    data=fixture('greenhouse.json')
    data['jobs'].append({'id':102,'title':'Invalid URL Job','absolute_url':'javascript:alert(1)'})
    data['meta']['total']=2
    rid=create_run(db)
    with client(profile,lambda r:httpx.Response(200,json=data)) as c: run_worker(db,rid,c)
    assert len(db.rows('SELECT * FROM jobs'))==2
    assert len(db.rows('SELECT * FROM job_sources'))==2
    assert len(db.rows("SELECT * FROM jobs WHERE analysis_status='ERROR'"))==1
    assert db.rows('SELECT status FROM source_runs')[0]['status']=='partial'

def test_accept_html_and_json_have_independent_cache(db,profile):
    requests=[]
    def handle(req):
        requests.append(req)
        return httpx.Response(200,text=req.headers['accept'],headers={'ETag':req.headers['accept']})
    with client(profile,handle,db) as c:
        c.get('https://fixture.test/page')
        response=c.get('https://fixture.test/page',accept='text/html')
        assert response.text=='text/html'
    assert 'if-none-match' not in requests[1].headers

def test_explicit_remote_us_is_outside_but_cork_it_is_retained(profile):
    assert scope_for({'location':'Remote, US','mode':'REMOTE'},'IT',profile)[0]=='FUERA_DE_ALCANCE'
    assert scope_for({'location':'County Cork, Ireland','mode':'HYBRID'},'IT',profile)[0]=='ACCESIBILIDAD_PENDIENTE'
    assert scope_for({'location':'Remote, Ireland','mode':'REMOTE'},'IT',profile)[0]=='EN_ALCANCE'

def test_published_url_keeps_slug_while_identity_deduplicates(db,profile):
    from corkjobradar.repository import save_job
    source(db,'smartrecruiters','one')
    source(db,'html','two')
    url='https://jobs.smartrecruiters.com/Fixture/123-published-slug'
    job=Job(external_id='1',title='Role',company='Fixture',url=url)
    a=save_job(db,'one',job,profile=profile)
    assert db.rows('SELECT url FROM jobs')[0]['url']==url
    job.external_id='2'
    b=save_job(db,'two',job,profile=profile)
    assert a==b

def test_captcha_widget_is_not_itself_access_challenge(profile):
    html='<html>Public job description<form>Apply<input name="resume"></form><div class="g-recaptcha"></div></html>'
    with client(profile,lambda r:httpx.Response(200,text=html,headers={'content-type':'text/html'})) as c:
        assert c.get('https://fixture.test/job').status_code==200
