import json
import httpx
from corkjobradar.config import now
from corkjobradar.worker import create_run,run_worker
from corkjobradar.audit import coverage
from corkjobradar.geography import scope_for
from corkjobradar.imports import cv_skills
from conftest import source,client,fixture

def test_default_audit_remains_last_discovery_after_analysis(db,profile):
    source(db,'greenhouse')
    rid=create_run(db)
    with client(profile,lambda r:httpx.Response(200,json=fixture('greenhouse.json'))) as c: run_worker(db,rid,c)
    second=create_run(db,kind='analyze')
    with client(profile,lambda r:httpx.Response(200)) as c: run_worker(db,second,c)
    assert coverage(db)['run_id']==rid
    assert coverage(db)['unique_jobs']==1

def test_newer_manual_route_supersedes_old_verified_route(profile):
    details=json.dumps({'destination':'SYNTHETIC','origin_access':'SYNTHETIC','outbound':'SYNTHETIC','return':'SYNTHETIC','shift_compatible':True})
    verified={'origin':'Ballinlough','mode':'bus','transfers':0,'viability':'VERIFICADA','evidence_url':'https://fixture.test/route','details':details}
    newer={**verified,'viability':'NO_VIABLE'}
    assert scope_for({'location':'Little Island'},'Almacen',profile,[newer,verified])[0]=='FUERA_DE_ALCANCE'

def test_large_count_drop_generates_audit_warning(db,profile):
    source(db,'greenhouse')
    data=fixture('greenhouse.json')
    first={**data,'jobs':[{**data['jobs'][0],'id':i,'absolute_url':f'https://fixture.test/{i}'} for i in range(4)],'meta':{'total':4}}
    for payload in (first,{'jobs':[],'meta':{'total':0}}):
        rid=create_run(db)
        with client(profile,lambda r:httpx.Response(200,json=payload)) as c: run_worker(db,rid,c)
    assert len(db.rows("SELECT * FROM audit_events WHERE kind='SOURCE_COUNT_ANOMALY'"))==1

def test_pdf_without_embedded_text_has_no_invented_skills():
    from pypdf import PdfWriter
    import io
    writer=PdfWriter();writer.add_blank_page(200,200);stream=io.BytesIO();writer.write(stream)
    assert cv_skills(stream.getvalue(),'synthetic.pdf')==[]
