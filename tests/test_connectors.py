import gzip
import json
import httpx
import pytest
from corkjobradar.adapters import make_adapter
from corkjobradar.parsers import jobpostings
from corkjobradar.http import AccessBlocked,IncompleteSource
from conftest import fixture,source,client

@pytest.mark.parametrize('kind,file',[('greenhouse','greenhouse.json'),('lever','lever.json'),('ashby','ashby.json'),('smartrecruiters','smartrecruiters.json'),('html','jobposting.html')])
def test_connector_fixtures(db,profile,kind,file):
    src=source(db,kind,config={'pagination_verified':True,'company_identifier':'Fixture'})
    def handle(req):
        if req.url.path=='/robots.txt':
            return httpx.Response(404)
        data=fixture(file)
        if kind=='lever' and int(req.url.params.get('skip',0))>0:
            data=[]
        return httpx.Response(200,text=data,headers={'content-type':'text/html'}) if isinstance(data,str) else httpx.Response(200,json=data)
    with client(profile,handle,db) as c:
        adapter=make_adapter(src,c,profile)
        pages=list(adapter.discover())
    assert sum(len(p.jobs) for p in pages)==1
    assert pages[-1].complete is True
    job=pages[0].jobs[0]
    assert job.external_id and job.title and job.url
    assert job.detail_complete is (kind!='smartrecruiters')
    if kind=='greenhouse':
        assert job.posted_at is None  # updated_at no es fecha original.

def test_lever_long_pagination(profile,db):
    src=source(db,'lever',config={'page_size':2})
    raw=fixture('lever.json')[0]
    offsets=[]
    def handle(req):
        skip=int(req.url.params.get('skip',0))
        offsets.append(skip)
        return httpx.Response(200,json=[{**raw,'id':str(i)} for i in range(skip,min(skip+2,7))])
    with client(profile,handle) as c:
        pages=list(make_adapter(src,c,profile).discover())
    assert offsets==[0,2,4,6,7] and sum(len(p.jobs) for p in pages)==7

def test_repeated_page_and_changed_structure(profile,db):
    src=source(db,'lever')
    with client(profile,lambda r:httpx.Response(200,json=fixture('lever.json'))) as c:
        with pytest.raises(IncompleteSource):
            list(make_adapter(src,c,profile).discover())
    src=source(db,'greenhouse','changed')
    with client(profile,lambda r:httpx.Response(200,json={'unexpected':[]})) as c:
        with pytest.raises(IncompleteSource):
            list(make_adapter(src,c,profile).discover())

@pytest.mark.parametrize('code',[403,404,429,503])
def test_http_errors(profile,code):
    with client(profile,lambda r:httpx.Response(code)) as c:
        with pytest.raises(AccessBlocked if code==403 else httpx.HTTPStatusError):
            c.get('https://fixture.test/jobs')

def test_429_retry_after_and_gzip(profile,db):
    profile['http_retries']=1
    calls=[]
    sleeps=[]
    def handle(req):
        calls.append(req)
        if len(calls)==1:
            return httpx.Response(429,headers={'Retry-After':'3'})
        return httpx.Response(200,content=gzip.compress(b'{"jobs":[]}'),headers={'content-encoding':'gzip','content-type':'application/json'})
    with client(profile,handle,db,sleeps.append) as c:
        assert c.get('https://fixture.test/jobs').json()=={'jobs':[]}
    assert 3 in sleeps

def test_network_error_retries(profile):
    profile['http_retries']=1
    calls=[]
    def handle(req):
        calls.append(req)
        raise httpx.ConnectTimeout('SYNTHETIC TIMEOUT')
    with client(profile,handle) as c:
        with pytest.raises(httpx.ConnectTimeout):
            c.get('https://fixture.test/jobs')
    assert len(calls)==2

def test_jsonld_malformed_and_graph():
    jobs,errors=jobpostings(fixture('jobposting.html'),'https://fixture.test/jobs')
    assert len(jobs)==1 and errors==0
    assert jobpostings('<script type="application/ld+json">{bad</script>','https://fixture.test/jobs')[1]==1

def test_microdata_and_html_empty_not_complete(profile,db):
    html='''<main itemscope itemtype="http://schema.org/JobPosting"><h1 itemprop="title">Synthetic Role</h1>
    <div itemprop="hiringOrganization"><meta itemprop="name" content="SYNTHETIC TEST ONLY"></div>
    <meta itemprop="addressLocality" content="Cork City"><div itemprop="description">Synthetic full description.</div></main>'''
    rows,errors=jobpostings(html,'https://fixture.test/job/1')
    assert len(rows)==1 and rows[0].company=='SYNTHETIC TEST ONLY' and rows[0].detail_complete
    src=source(db,'html',config={'pagination_verified':True})
    with client(profile,lambda r:httpx.Response(404) if r.url.path=='/robots.txt' else httpx.Response(200,text='<html>No recognizable jobs</html>')) as c:
        with pytest.raises(IncompleteSource): list(make_adapter(src,c,profile).discover())

def test_html_loop(profile,db):
    src=source(db,'html',config={'pagination_verified':True})
    text=fixture('jobposting.html').replace('</body>','<a rel="next" href="/jobs">Next</a></body>')
    def handle(req):
        return httpx.Response(404) if req.url.path=='/robots.txt' else httpx.Response(200,text=text)
    with client(profile,handle) as c:
        with pytest.raises(IncompleteSource):
            list(make_adapter(src,c,profile).discover())
