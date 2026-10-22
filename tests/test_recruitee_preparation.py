"""Real captured schema replay + synthetic candidate; zero external submissions."""
from copy import deepcopy
from datetime import date
import hashlib
import json
import httpx
import pytest
from pathlib import Path
from conftest import client
from corkjobradar.config import ROOT,digest
from corkjobradar.autoapply.recruitee import target,inspect_recruitee,normalize_offer,prepare_request,VERSION
from corkjobradar.autoapply.forms import inspect_job_form,answer_plan,disconnected_preparation,load_inspection
from corkjobradar.autoapply.documents import render_cv,store_document,document_bytes
from corkjobradar.autoapply.vault import candidate_snapshot,approve_fact
from test_autoapply_vault import populate
from test_autoapply_policy import stored_job

PUBLIC_URL='https://distilled.recruitee.com/o/snr-fe/c/new'


def public_schema():return json.loads((ROOT/'tests/fixtures/autoapply/recruitee-distilled-public-20261020.json').read_text(encoding='utf-8'))


def inspected(db,profile,data=None):
    job=stored_job(db,profile,url=PUBLIC_URL)
    requests=[]
    def handler(req):
        requests.append(req.method)
        return httpx.Response(200,text='User-agent: *\nAllow: /') if req.url.path=='/robots.txt' else httpx.Response(200,json=data or public_schema())
    with client(profile,handler) as web:result=inspect_job_form(db,job['id'],web)
    assert set(requests)=={'GET'}
    return result


def test_actual_captured_schema_preserved_and_not_relabelled_as_compatible(db,profile):
    data=public_schema();offer=data['offers'][0]
    assert data['provenance']['real_public_source'] and digest(offer)==data['provenance']['fragment_sha256']
    result=inspected(db,profile)
    assert result['posting_id']==str(offer['id']) and result['platform']=='recruitee'
    assert len([f for f in result['fields'] if f.get('question_id')])==len(offer['open_questions'])
    assert {'EMPLOYER_AUTOMATION_SCOPE_UNVERIFIED','HOSTED_PRIVACY_AND_ACCESS_REVIEW_REQUIRED'}<=set(result['blockers'])
    assert not result['submitted'] and not result['live_supported']
    assert load_inspection(db,result['inspection_id'])['form_hash']==result['form_hash']


@pytest.mark.parametrize('url',[
 'http://distilled.recruitee.com/o/example','https://distilled.recruitee.com.evil.invalid/o/example',
 'https://recruitee.com/o/example','https://app.recruitee.com/o/example','https://a.b.recruitee.com/o/example',
 'https://distilled.recruitee.com/api/offers/example/candidates','https://distilled.recruitee.com/o/example?token=secret',
 'https://user:secret@distilled.recruitee.com/o/example','https://distilled.recruitee.com:9443/o/example',
 'https://127.0.0.1/o/example','https://distilled.recruitee.com/o/%2e%2e',
])
def test_noncanonical_or_untrusted_targets_fail_before_network(url):
    with pytest.raises(ValueError):target(url)


def test_token_deadline_fails_closed_before_network(profile):
    calls=[]
    with client(profile,lambda req:calls.append(req)) as web:
        with pytest.raises(PermissionError,match='TOKEN_REQUIRED'):inspect_recruitee(PUBLIC_URL,web,today=date(2027,2,10))
    assert calls==[]


@pytest.mark.parametrize('change',['removed','duplicate','url','status','new_kind','missing_option'])
def test_schema_changes_and_unknowns_hold_or_reject(db,profile,change):
    data=public_schema();offer=data['offers'][0]
    if change=='removed':data['offers']=[]
    if change=='duplicate':data['offers']*=2
    if change=='url':offer['careers_apply_url']='https://evil.invalid/steal'
    if change=='status':offer['status']='draft'
    if change=='new_kind':offer['open_questions'][0]['kind']='unknown_video_signature'
    if change=='missing_option':offer.pop('options_cv')
    if change in {'removed','duplicate','url'}:
        with pytest.raises(ValueError):inspected(db,profile,data)
    else:
        result=inspected(db,profile,data)
        assert result['blockers'] and not result['live_supported']


def test_real_schema_local_browser_uses_pdf_contacts_and_verified_linkedin_without_post(db,profile):
    populate(db)
    for key,value in [('phone','+353000000000'),('linkedin_url','https://www.linkedin.com/in/synthetic-only/')]:approve_fact(db,key,value,'SYNTHETIC ONLY',True)
    did=store_document(db,render_cv(candidate_snapshot(db),'pdf'),'pdf',True)
    result=inspected(db,profile)
    review=disconnected_preparation(db,result['inspection_id'])
    assert review['state']=='HOLD' and review['posts']==0 and review['browser_fields_checked']
    assert {'name','email','phone','cv'}<=set(review['resolved_fields'])
    assert review['unresolved_questions'] and not review['external_personal_data_sent']
    request=prepare_request(result,candidate_snapshot(db),lambda doc:document_bytes(db,doc))
    assert request.files['candidate[cv]'][1]==document_bytes(db,did)[0]
    from corkjobradar.autoapply.documents import validate_document
    assert 'linkedin.com/in/synthetic-only' in validate_document(request.files['candidate[cv]'][1],'pdf')
    assert request.data['candidate[email]']=='synthetic@example.invalid'
    assert 'synthetic@example.invalid' not in repr(request) and 'synthetic@example.invalid' not in json.dumps(request.summary())
    assert request.summary()['state']=='HOLD' and not request.summary()['external_receipt_verified']
    assert not db.rows('SELECT * FROM application_attempts') and not db.rows('SELECT * FROM user_actions')


def test_documented_multipart_encoding_preserves_ids_boolean_values_and_linkedin(db,profile):
    data=public_schema();offer=data['offers'][0]
    # Explicit synthetic questions; the real captured form above remains unchanged.
    offer['open_questions']=[{'id':11,'body':'LinkedIn Profile','kind':'string','required':True},
                             {'id':12,'body':'SYNTHETIC verified question','kind':'boolean','required':True}]
    populate(db)
    approve_fact(db,'phone','+353000000000','SYNTHETIC ONLY',True)
    approve_fact(db,'linkedin_url','https://www.linkedin.com/in/synthetic-only/','SYNTHETIC ONLY',True)
    approve_fact(db,'answer:boolean',{'question':'SYNTHETIC verified question','host':'distilled.recruitee.com','answer':'false'},'SYNTHETIC ONLY',True)
    store_document(db,render_cv(candidate_snapshot(db),'pdf'),'pdf',True)
    result=inspected(db,profile,data)
    prepared=prepare_request(result,candidate_snapshot(db),lambda doc:document_bytes(db,doc))
    assert prepared.data['candidate[open_question_answers_attributes][0][content]'].endswith('/synthetic-only/')
    assert prepared.data['candidate[open_question_answers_attributes][0][open_question_id]']=='11'
    assert prepared.data['candidate[open_question_answers_attributes][1][flag]']=='false'
    request=httpx.Request('POST',prepared.endpoint,data=prepared.data,files=prepared.files)
    raw=request.read()  # Encodes in memory; no client or network is used.
    assert b'name="candidate[cv]"' in raw and b'Content-Type: application/pdf' in raw
    assert prepared.summary()['state']=='HOLD' and not prepared.summary()['submitted']


def test_unapproved_document_and_forged_destination_or_multipart_field_rejected(db,profile):
    populate(db);result=inspected(db,profile)
    candidate=candidate_snapshot(db);candidate['cv_document_id']=999
    with pytest.raises(ValueError,match='APPROVED_DOCUMENT'):prepare_request(result,candidate,lambda doc:document_bytes(db,doc))
    changed=deepcopy(result);changed['endpoint']='https://evil.invalid/steal'
    with pytest.raises(ValueError,match='TARGET_OR_ADAPTER_CHANGED'):prepare_request(changed,candidate,lambda doc:document_bytes(db,doc))
    changed=deepcopy(result);changed['fields'][0]['wire']='candidate[unauthorized_admin_field]'
    with pytest.raises(ValueError,match='UNSUPPORTED_MULTIPART_FIELD'):prepare_request(changed,candidate,lambda doc:document_bytes(db,doc))


def test_documented_multipart_reaches_owned_receiver_once_with_exact_file_and_answers(db,profile):
    """Real socket to our own server only; NOT an external ATS receipt test."""
    import sqlite3
    from local_application_receiver import application_receiver
    populate(db);approve_fact(db,'phone','+353000000000','SYNTHETIC ONLY',True)
    store_document(db,render_cv(candidate_snapshot(db),'pdf'),'pdf',True)
    result=inspected(db,profile)
    packet=prepare_request(result,candidate_snapshot(db),lambda doc:document_bytes(db,doc))
    sha=hashlib.sha256(packet.files['candidate[cv]'][1]).hexdigest()
    with application_receiver(db.path.parent/'api-receiver.sqlite3','SYNTHETIC-API-POST',packet.data,sha,cv_field='candidate[cv]') as receiver:
        with httpx.Client(trust_env=False,follow_redirects=False,timeout=10) as web:
            response=web.post(receiver['submit_url'],data=packet.data,files=packet.files,headers={'Origin':receiver['origin']})
            assert response.status_code==200
            receipt=response.json()
            assert receipt['environment']=='OWNED_LOCAL_TEST_ONLY' and receipt['cv_hash']==sha
            duplicate=web.post(receiver['submit_url'],data=packet.data,files=packet.files,headers={'Origin':receiver['origin']})
            assert duplicate.status_code==409
        with sqlite3.connect(receiver['db']) as con:assert con.execute('SELECT COUNT(*) FROM receipts').fetchone()[0]==1
    assert packet.summary()['state']=='HOLD'  # Local test cannot release the real target.
    assert not db.rows('SELECT * FROM application_attempts') and not db.rows('SELECT * FROM user_actions')


def test_legal_type_requires_explicit_sensitive_answer_even_if_label_looks_like_contact():
    from corkjobradar.autoapply.browser import OfflineFormAdapter,FormHold
    question={'id':'q','label':'Full name','type':'select-one','required':True,'disabled':False,'options':[{'value':'true','text':'Yes'}],'legal':True}
    candidate={'full_name':'SYNTHETIC','_answers':[{'id':1,'host':'distilled.recruitee.com','question':'Full name','answer':'true'}]}
    form={'action':PUBLIC_URL,'fields':[question]}
    with pytest.raises(FormHold):OfflineFormAdapter(None,'recruitee').map_questions(form,candidate)
    candidate['_answers'][0]['explicit_sensitive']=True
    assert OfflineFormAdapter(None,'recruitee').map_questions(form,candidate)['q']['value']=='true'


def test_optional_infobox_and_unknown_required_file_are_never_silently_accepted():
    offer=deepcopy(public_schema()['offers'][0]);offer['open_questions']=[{'id':1,'body':'Employer notice','kind':'infobox','required':False},
        {'id':2,'body':'Upload your certificate','kind':'file','required':True}]
    fields,blockers,notices=normalize_offer(offer)
    assert notices[0]['text']=='Employer notice' and 'INFORMATIONAL_NOTICE_REQUIRES_REVIEW' in blockers
    assert next(f for f in fields if f.get('question_id')==2)['required']


def test_final_request_entry_point_rechecks_paused_policy_before_loading_personal_packet(db,profile):
    from test_autoapply_network_e2e import setup_network_application
    from corkjobradar.autoapply.recruitee import final_prepared_request
    from corkjobradar.autoapply.policy import pause
    aid,job,data=setup_network_application(db,profile)
    pause(db)
    with pytest.raises(PermissionError,match='POLICY_CHANGED_OR_PAUSED'):final_prepared_request(db,aid,999)
    assert not db.rows('SELECT * FROM user_actions')
