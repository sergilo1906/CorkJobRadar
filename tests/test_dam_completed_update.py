"""The user's confirmed education replaces its prior version; CV approval stays separate."""
from pathlib import Path
import pytest
from corkjobradar.autoapply.vault import approve_fact,candidate_snapshot,protect
from corkjobradar.autoapply.documents import render_cv,store_document,cv_review_bytes,document_bytes,approve_cv_review
from scripts.update_dam_completed_20261022 import update,FIELD,COMPLETED
from test_autoapply_vault import populate


def test_dam_completion_versions_history_and_creates_unapproved_cv(db):
    populate(db)
    old=approve_fact(db,FIELD,{'section':'Education','text_en':'SYNTHETIC: DAM ongoing; MP13 remaining.'},'SYNTHETIC fixture',True)
    java=approve_fact(db,'claim:java_training',{'section':'Education','text_en':'SYNTHETIC: Java programming training.'},'SYNTHETIC fixture',True)
    old_cv=store_document(db,render_cv(candidate_snapshot(db),'pdf'),'pdf',approved=True)
    prior_facts=db.rows('SELECT * FROM candidate_facts ORDER BY id')
    old_cipher=db.rows('SELECT encrypted_value FROM candidate_facts WHERE id=?',(old,))[0]['encrypted_value']
    result=update(db);current=candidate_snapshot(db)
    assert current.get('cv_document_id') is None
    assert len(db.rows('SELECT id FROM candidate_facts WHERE revoked_at IS NULL'))==len(prior_facts)
    for row in prior_facts:
        retained=db.rows('SELECT * FROM candidate_facts WHERE id=?',(row['id'],))[0]
        assert retained['encrypted_value']==row['encrypted_value']
        if row['id']==old:assert retained['revoked_at']
        else:assert retained==row
    assert b'SYNTHETIC: DAM ongoing' in protect(old_cipher,decrypt=True)
    assert any(c['id']==java and c['text_en']=='SYNTHETIC: Java programming training.' for c in current['_claims'])
    _,ext,sha,text=cv_review_bytes(db,result['cv_document_id'])
    assert ext=='pdf' and COMPLETED['text_en'] in ' '.join(text.split())
    assert 'ongoing' not in text and 'MP13 remaining' not in text
    record=db.rows('SELECT * FROM candidate_documents WHERE id=?',(result['cv_document_id'],))[0]
    assert record['approved_at'] is None and record['revoked_at'] is None
    assert 'completed; final examination passed' not in Path(record['encrypted_path']).read_bytes().decode('ascii',errors='ignore')
    with pytest.raises(ValueError,match='APPROVED_DOCUMENT_MISSING'):document_bytes(db,old_cv)
    with pytest.raises(ValueError,match='EXPLICIT_DOCUMENT_REVIEW_REQUIRED'):
        approve_cv_review(db,record['id'],sha,current['_facts_hash'],confirmed=False)
    assert not db.rows('SELECT * FROM application_attempts')
    assert not db.rows('SELECT * FROM autoapply_policies')
    assert db.rows('SELECT live_enabled FROM autoapply_control')[0]['live_enabled']==0
    again=update(db)
    assert again['already_current'] and again['cv_document_id']==result['cv_document_id']
    assert len(db.rows('SELECT id FROM candidate_documents'))==2
    assert len(db.rows('SELECT id FROM candidate_facts'))==len(prior_facts)+1
