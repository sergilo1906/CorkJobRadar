"""Apply the user's 22/10/2026 DAM confirmation; retain encrypted history and draft only."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now
from corkjobradar.db import Database
from corkjobradar.autoapply.vault import approve_fact,candidate_snapshot
from corkjobradar.autoapply.documents import render_cv,create_cv_review,cv_review_bytes

# Keep the existing stable field key to replace its version, rather than leaving
# contradictory ongoing/completed claims active. The key is not printed in the CV.
FIELD='claim:cv_dam_ongoing'
COMPLETED={'section':'Education','text_en':'Higher Technician qualification in Multiplatform Application Development (CFGS DAM): completed; final examination passed.'}
ORIGIN='USER_CONFIRMED_DAM_COMPLETED_2026-10-22'


def update(db):
    """Caller must have the user's explicit confirmation. No document consent here."""
    before=candidate_snapshot(db)
    rows=db.rows('SELECT id FROM candidate_facts WHERE field=? AND revoked_at IS NULL',(FIELD,))
    if len(rows)!=1:raise ValueError('EXACTLY_ONE_EXISTING_DAM_FACT_REQUIRED')
    previous_id=rows[0]['id']
    previous=next(c for c in before['_claims'] if c['id']==previous_id)
    if {k:previous[k] for k in ('section','text_en')}==COMPLETED:
        # Re-running must not revoke the pending draft or append another fact.
        drafts=db.rows("SELECT id FROM candidate_documents WHERE kind='CV' AND facts_hash=? AND revoked_at IS NULL ORDER BY id DESC",(before['_cv_facts_hash'],))
        if not drafts:raise ValueError('CURRENT_DAM_CV_DRAFT_MISSING')
        return {'fact_id':previous_id,'cv_document_id':drafts[0]['id'],'already_current':True}
    preview={**before,'_claims':[{**c,**COMPLETED} if c['id']==previous_id else c for c in before['_claims']]}
    content=render_cv(preview,'pdf')  # In memory; fail before changing facts if rendering fails.
    with db.transaction() as con:
        con.execute('BEGIN IMMEDIATE')
        if candidate_snapshot(db)['_facts_hash']!=before['_facts_hash']:raise ValueError('PROFILE_CHANGED_RETRY_REVIEW')
        fid=approve_fact(db,FIELD,COMPLETED,ORIGIN,confirmed=True)
        did=create_cv_review(db,content,'pdf')
        _,_,_,text=cv_review_bytes(db,did)
        assert COMPLETED['text_en'] in ' '.join(text.split())
        assert previous['text_en'] not in text
        assert not candidate_snapshot(db).get('cv_document_id')
    return {'previous_fact_id':previous_id,'fact_id':fid,'cv_document_id':did,'already_current':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply-user-confirmation',action='store_true',required=True)
    parser.parse_args()
    output=ROOT/'logs/ui-redesign-dam-completed-update.json'
    if output.exists():raise ValueError('PRESERVE_EXISTING_UPDATE_REPORT')
    backup=json.loads((ROOT/'logs/dam-completed-baseline-backup.json').read_text(encoding='utf-8'))
    assert backup['integrity']=='ok' and (ROOT/backup['path']/'radar.sqlite3').is_file()
    db=Database()
    assert db.rows('SELECT enabled,live_enabled FROM autoapply_control')[0]=={'enabled':0,'live_enabled':0}
    result=update(db)
    result.update(checked_at=now(),status='PASS',user_confirmation='2026-10-22: DAM completed and exam passed',
        approved_facts=len(db.rows('SELECT id FROM candidate_facts WHERE revoked_at IS NULL')),
        historical_facts=len(db.rows('SELECT id FROM candidate_facts')),cv_approved=False,
        live_enabled=False,external_applications_sent=0,backup='logs/dam-completed-baseline-backup.json')
    output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
