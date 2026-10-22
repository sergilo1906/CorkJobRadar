"""Real local HTTP integration; synthetic candidate; ZERO external ATS sends.

This cannot satisfy F4/F5 or unlock LIVE. It tests our own receiver only.
"""
import hashlib
import json
import os
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit
import pytest
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from corkjobradar.config import ROOT,now
from corkjobradar.autoapply.browser import OfflineFormAdapter
from corkjobradar.autoapply.eligibility import evaluate_autoapply
from corkjobradar.autoapply.policy import current_policy,pause,event
from corkjobradar.autoapply.store import prefinal_check,transition,already_applied,save_plan,reserve
from corkjobradar.autoapply.vault import candidate_snapshot,approve_fact,private_folder,protect,save_clearance
from corkjobradar.autoapply.documents import document_bytes,render_cv,store_document
from test_autoapply_policy import inputs
from test_autoapply_vault import populate
from test_autoapply_policy import policy_config,stored_job
from corkjobradar.autoapply.policy import save_policy
from local_application_receiver import application_receiver


def setup_network_application(db,profile):
    assert db.path.name=='test.sqlite3' and db.path.resolve().is_relative_to(ROOT/'data')
    populate(db)
    for key,value in {'phone':'+353000000000','linkedin_url':'https://www.linkedin.com/in/synthetic-only/','availability':'SYNTHETIC available'}.items():
        approve_fact(db,key,value,'EXPLICIT SYNTHETIC FIXTURE ONLY',True)
    approve_fact(db,'answer:task',{'question':'Which support task can you perform?','host':'127.0.0.1','answer':'SYNTHETIC user incident documentation'},'EXPLICIT SYNTHETIC FIXTURE ONLY',True)
    did=store_document(db,render_cv(candidate_snapshot(db),'pdf'),'pdf',True)
    candidate=candidate_snapshot(db);config=policy_config()
    config.update(candidate_facts_hash=candidate['_facts_hash'],authorized_document_ids=[did])
    pid=save_policy(db,config,'AUTHORIZE_SIMULATION')
    job=stored_job(db,profile)
    db.execute("UPDATE jobs SET open_status='OPEN_CONFIRMED',mode='ONSITE',last_verified_at=?,raw=? WHERE id=?",(now(),json.dumps({'_synthetic_fixture':True}),job['id']))
    job=db.rows('SELECT * FROM jobs WHERE id=?',(job['id'],))[0]
    data=inputs(profile);data.update(job=job,candidate=candidate,policy=current_policy(db)[2],clock=datetime.now(ZoneInfo('Europe/Dublin')))
    data['analysis']['_content_hash']=job['content_hash']
    clearance=data['clearance'];clearance.update(content_hash=job['content_hash'],facts_hash=candidate['_facts_hash'],expires_at=(data['clock']+timedelta(days=1)).isoformat())
    payload={k:v for k,v in clearance.items() if k not in {'content_hash','facts_hash','expires_at'}}
    payload['evidence']={k:{'quote':job['description'],'fact_ids':[candidate['_claims'][0]['id']]} for k in payload}
    save_clearance(db,job['id'],payload,clearance['expires_at'],True)
    data['transport'][0]['details']['job_content_hash']=job['content_hash']
    route=data['transport'][0]
    db.execute('INSERT INTO commute_checks(job_id,origin,mode,transfers,viability,evidence_url,checked_at,details) VALUES(?,?,?,?,?,?,?,?)',
               (job['id'],route['origin'],route['mode'],0,route['viability'],route['evidence_url'],now(),json.dumps(route['details'])))
    analysis_id=db.execute('INSERT INTO job_analyses(job_id,content_hash,profile_hash,analyzer_version,status,result,created_at) VALUES(?,?,?,?,?,?,?)',
                          (job['id'],job['content_hash'],'SYNTHETIC','OWNED_NETWORK_TEST','COMPLETO',json.dumps(data['analysis']),now()))
    decision=evaluate_autoapply(**data);assert decision.outcome=='ALLOW'
    plan=save_plan(db,job,decision,pid,candidate['_facts_hash'],analysis_id)
    aid=reserve(db,plan,job)
    return aid,job,data


@pytest.mark.parametrize('scenario',['receipt','no_receipt','pause','non_it','unknown_field'])
def test_selection_to_multipart_and_durable_owned_receipt(db,profile,monkeypatch,scenario):
    aid,job,data=setup_network_application(db,profile)
    candidate=candidate_snapshot(db)
    cv,ext,sha=document_bytes(db,candidate['cv_document_id'])
    expected={'name':candidate['full_name'],'email':candidate['email'],'phone':candidate['phone'],
              'linkedin':candidate['linkedin_url'],'availability':candidate['availability'],'question':candidate['_answers'][0]['answer']}
    temp=ROOT/'data/browser-temp';temp.mkdir(exist_ok=True)
    for key,value in {'PLAYWRIGHT_BROWSERS_PATH':ROOT/'data/playwright-browsers','TEMP':temp,'TMP':temp}.items():monkeypatch.setenv(key,str(value))
    from playwright.sync_api import sync_playwright
    post_count=0;verified=False;blocked=[]
    with application_receiver(db.path.parent/'receiver.sqlite3',job['id'],expected,sha,response_mode=scenario) as receiver,sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=['--disable-background-networking','--disable-breakpad'])
        context=browser.new_context(service_workers='block')
        def guard(route):
            if route.request.url in {receiver['form_url'],receiver['submit_url']} and route.request.method in {'GET','POST'}:route.continue_()
            else:blocked.append(True);route.abort()
        context.route('**/*',guard);context.route_web_socket('**/*',lambda ws:ws.close())
        page=context.new_page();page.goto(receiver['form_url'])
        try:
            fields=page.locator('form').evaluate('''f=>[...f.querySelectorAll('input')].map(e=>({id:e.id,name:e.name,type:e.type,required:e.required,disabled:e.disabled,label:[...e.labels].map(l=>l.innerText).join(' '),options:[]}))''')
            if scenario=='unknown_field':fields.append({'id':'unknown','name':'unknown','type':'text','required':True,'disabled':False,'label':'Unapproved future legal condition','options':[]})
            try:mapping=OfflineFormAdapter(None,'greenhouse').map_questions({'fields':fields,'action':receiver['submit_url']},candidate)
            except RuntimeError:
                assert scenario=='unknown_field';mapping=None
            db.execute('UPDATE application_attempts SET document_id=? WHERE id=?',(candidate['cv_document_id'],aid))
            transition(db,aid,'PREPARADA');transition(db,aid,'RELLENANDO')
            if mapping:
                for field in fields:
                    answer=mapping[field['id']];locator=page.locator('#'+field['id'])
                    if 'document' in answer:locator.set_input_files({'name':'CV.pdf','mimeType':'application/pdf','buffer':cv})
                    else:
                        locator.fill(answer['value']);assert locator.input_value()==answer['value']
                assert page.locator('form').evaluate('(f)=>f.checkValidity()')
                transition(db,aid,'LISTA_PARA_ENVIO')
                if scenario=='pause':pause(db)
                if scenario=='non_it':db.execute("UPDATE jobs SET title='Warehouse Operative' WHERE id=?",(job['id'],))
                # Reclassify stored duties and recheck policy immediately before POST.
                try:prefinal_check(db,aid)
                except PermissionError:assert scenario in {'pause','non_it'}
                else:
                    # Complete eligibility is also exercised. Capabilities below describe
                    # this OWNED synthetic test, never a public ATS adapter capability.
                    data.update(job=db.rows('SELECT * FROM jobs WHERE id=?',(job['id'],))[0],control=current_policy(db)[0],candidate=candidate_snapshot(db))
                    assert evaluate_autoapply(**data).outcome=='ALLOW'
                    event(db,'OWNED_LOCAL_TEST_DISPATCH',{'attempt_id':aid,'method':'POST','external_ats':False})
                    with page.expect_response(lambda r:r.request.method=='POST' and r.url==receiver['submit_url']) as captured:
                        page.get_by_role('button',name='Submit owned test').click()
                    response=captured.value;post_count+=1
                    body=response.body();receipt=json.loads(body)
                    request_hash=hashlib.sha256(response.request.post_data_buffer).hexdigest()
                    verified=(response.status==200 and receipt.get('received') is True and receipt.get('environment')=='OWNED_LOCAL_TEST_ONLY'
                        and receipt.get('job_id')==job['id'] and receipt.get('cv_hash')==sha and receipt.get('request_hash')==request_hash
                        and str(receipt.get('reference','')).startswith('OWNED-TEST-'))
                    proof={'response':receipt,'request_hash':request_hash,'status':response.status,'verified_owned_receiver_only':verified}
                    (private_folder(db)/'owned-network-evidence.dpapi').write_bytes(protect(json.dumps(proof).encode('utf-8')))
                    assert verified==(scenario=='receipt')
            with sqlite3.connect(receiver['db']) as con:server_rows=con.execute('SELECT job_id,request_hash,cv_hash FROM receipts').fetchall()
            assert len(server_rows)==post_count
            if post_count:assert server_rows[0]==(job['id'],request_hash,sha)
            state=db.rows('SELECT state FROM application_attempts WHERE id=?',(aid,))[0]['state']
            transition(db,aid,'SIMULADA_SIN_ENVIO' if state=='LISTA_PARA_ENVIO' else 'CANCELADA')
            assert already_applied(db,job)  # Reservation survives success, hold and uncertainty.
            assert not db.rows('SELECT * FROM user_actions') and not db.rows('SELECT * FROM application_receipt_evidence')
            assert not db.rows('SELECT id FROM application_attempts WHERE confirmation_reference IS NOT NULL')
            report={'checked_at':now(),'scenario':scenario,'mechanism':'CHROMIUM_MULTIPART_OVER_LOOPBACK_TCP',
                    'payload_fields':sorted(expected),'cv_sha256':sha,'http_posts':post_count,'durable_receiver_rows':len(server_rows),
                    'owned_test_receipt_verified':verified,'external_ats_posts':0,'real_user_data_used':False,
                    'external_confirmation_verified':False,'live_enabled':False,'external_requests_permitted':False}
            (ROOT/'logs'/('verified-flow-network-'+scenario+'-'+db.path.parent.parent.name+'.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
        finally:context.close();browser.close()
