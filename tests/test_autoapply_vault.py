import io
import json
import pytest
from corkjobradar.autoapply.vault import approve_fact,candidate_snapshot,protect
from corkjobradar.autoapply.documents import render_cv,store_document,document_bytes,validate_document
from corkjobradar.autoapply.policy import save_policy,current_policy
from test_autoapply_policy import policy_config


def populate(db):
    approve_fact(db,'full_name','SYNTHETIC Á Test','Synthetic only, not a real identity',True)
    approve_fact(db,'email','synthetic@example.invalid','Synthetic test contact',True)
    approve_fact(db,'work_authorization','IRELAND_AUTHORIZED','SYNTHETIC fixture declaration, not a user fact',True)
    return approve_fact(db,'claim:education',{'section':'Education','text_en':'SYNTHETIC ONLY: studying software development.'},'Synthetic fixture',True)


@pytest.mark.parametrize('extension',['pdf','docx'])
def test_real_documents_dpapi_roundtrip_and_claims(db,extension):
    fid=populate(db);snapshot=candidate_snapshot(db)
    raw=render_cv(snapshot,extension)
    assert 'SYNTHETIC ONLY' in validate_document(raw,extension)
    did=store_document(db,raw,extension,approved=True)
    decoded,ext,sha=document_bytes(db,did)
    assert decoded==raw and ext==extension and len(sha)==64
    assert candidate_snapshot(db)['cv_document_id']==did
    record=db.rows('SELECT * FROM candidate_documents WHERE id=?',(did,))[0]
    from pathlib import Path
    assert raw!=Path(record['encrypted_path']).read_bytes()
    assert b'synthetic@example.invalid' not in db.path.read_bytes()
    assert 'synthetic@example.invalid' not in json.dumps(db.rows('SELECT * FROM application_events'))
    assert json.loads(record['claim_ids'])==[fid]


def test_facts_are_explicit_and_change_invalidates_cv_and_policy(db):
    with pytest.raises(ValueError):approve_fact(db,'email','bad','',False)
    with pytest.raises(ValueError):approve_fact(db,'work_authorization','yes','fixture',True)
    populate(db);doc=store_document(db,render_cv(candidate_snapshot(db)),'docx',True)
    save_policy(db,policy_config(),'AUTHORIZE_SIMULATION')
    approve_fact(db,'claim:skill',{'section':'Skills','text_en':'Synthetic software testing.'},'test',True)
    assert 'cv_document_id' not in candidate_snapshot(db)
    assert current_policy(db)[0]['paused']
    with pytest.raises(ValueError):document_bytes(db,doc)
    assert len(db.rows('SELECT * FROM candidate_facts'))==5


def test_unknown_document_and_unsupported_claims_rejected(db):
    populate(db)
    with pytest.raises(ValueError):store_document(db,render_cv(candidate_snapshot(db)),'docx',False)
    with pytest.raises(ValueError):validate_document(b'%PDF-not-a-real-pdf','pdf')
    with pytest.raises(ValueError):approve_fact(db,'claim:invented',{'section':'CEO','text_en':'invented'},'test',True)
    encrypted=protect(b'SYNTHETIC SECRET')
    assert protect(encrypted,True)==b'SYNTHETIC SECRET'
    with pytest.raises(RuntimeError):protect(b'not DPAPI',True)
