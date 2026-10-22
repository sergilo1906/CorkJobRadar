"""Read-only production checks: authorized DAM version, private CV review UI, no sends."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
from urllib.parse import urlsplit
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now
from corkjobradar.db import Database
from corkjobradar.runtime import alive
from corkjobradar.autoapply.vault import candidate_snapshot
from corkjobradar.autoapply.documents import cv_review_bytes
from scripts.update_dam_completed_20261022 import FIELD,COMPLETED
from scripts.check_ui_redesign import navigate,idle


def main():
    from playwright.sync_api import sync_playwright,expect
    output=ROOT/'logs/ui-redesign-dam-completed-delivery.json'
    if output.exists():raise ValueError('PRESERVE_EXISTING_AUDIT')
    baseline=json.loads((ROOT/'logs/dam-completed-baseline-backup.json').read_text(encoding='utf-8'))
    backup=ROOT/baseline['path']
    for name,sha in baseline['hashes'].items():
        with (backup/name).open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==sha
    for name in ('encrypted-vault.zip','code-and-evidence.zip'):
        with zipfile.ZipFile(backup/name) as z:assert z.testzip() is None
    con=sqlite3.connect((ROOT/'data/radar.sqlite3').as_uri()+'?mode=ro',uri=True);con.row_factory=sqlite3.Row
    try:
        con.execute('ATTACH DATABASE ? AS prior',(str(backup/'radar.sqlite3'),));con.execute('BEGIN')
        assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not con.execute('PRAGMA foreign_key_check').fetchall()
        oldfacts=[dict(r) for r in con.execute('SELECT * FROM prior.candidate_facts')]
        old_id=next(r['id'] for r in oldfacts if r['field']==FIELD and r['revoked_at'] is None)
        for row in oldfacts:
            current=dict(con.execute('SELECT * FROM main.candidate_facts WHERE id=?',(row['id'],)).fetchone())
            if row['id']==old_id:
                assert current['revoked_at'];current['revoked_at']=row['revoked_at']
            assert row==current
        for row in con.execute('SELECT * FROM prior.candidate_documents').fetchall():
            row=dict(row);current=dict(con.execute('SELECT * FROM main.candidate_documents WHERE id=?',(row['id'],)).fetchone())
            assert current['revoked_at'];current['revoked_at']=row['revoked_at'];assert current==row
        untouched=['autoapply_control','autoapply_policies','application_plans','application_attempts','user_actions','manual_application_handoffs','manual_application_declarations','manual_application_evidence','application_receipt_evidence','autoapply_trial_consents','autoapply_form_inspections','manual_requirement_reviews','it_selection_origins','it_worksite_evidence']
        for table in untouched:
            assert not con.execute('SELECT * FROM prior.'+table+' EXCEPT SELECT * FROM main.'+table).fetchall(),table
            assert not con.execute('SELECT * FROM main.'+table+' EXCEPT SELECT * FROM prior.'+table).fetchall(),table
        assert not con.execute('SELECT id FROM prior.jobs EXCEPT SELECT id FROM main.jobs').fetchall()
        counts={t:con.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ('jobs','candidate_facts','candidate_documents','application_attempts','manual_application_handoffs','manual_application_declarations')}
        active=con.execute('SELECT COUNT(*) FROM candidate_facts WHERE revoked_at IS NULL').fetchone()[0]
        assert active==22 and counts['candidate_facts']==23 and counts['candidate_documents']==2
        runtime=dict(con.execute('SELECT desired,state,interval_hours,supervisor_pid,supervisor_stamp,owner_pid,owner_stamp,next_search_at FROM local_runtime').fetchone())
        assert alive(runtime['supervisor_pid'],runtime['supervisor_stamp']) and alive(runtime['owner_pid'],runtime['owner_stamp'])
        control=dict(con.execute('SELECT enabled,live_enabled,paused,epoch FROM autoapply_control').fetchone())
        assert control=={'enabled':0,'live_enabled':0,'paused':1,'epoch':0}
    finally:con.close()
    db=Database();candidate=candidate_snapshot(db)
    assert any(c['text_en']==COMPLETED['text_en'] for c in candidate['_claims'])
    assert not candidate.get('cv_document_id')
    did=db.rows("SELECT id FROM candidate_documents WHERE kind='CV' AND revoked_at IS NULL")[0]['id']
    _,_,_,text=cv_review_bytes(db,did)
    assert COMPLETED['text_en'] in ' '.join(text.split()) and 'ongoing; one final module remaining' not in text
    contacts=[candidate[k] for k in ('email','phone','linkedin_url') if candidate.get(k)]
    leaks=0
    for path in [*list((ROOT/'logs').glob('ui-redesign-*')),ROOT/'data/radar.sqlite3',ROOT/'data/radar.sqlite3-wal']:
        if not path.is_file() or path.suffix not in {'.json','.xml','.log','.sqlite3',''} and path.name!='radar.sqlite3-wal':continue
        data=path.read_bytes()
        leaks+=sum(v.encode(enc) in data for v in contacts for enc in ('utf-8','utf-16-le'))
    assert leaks==0
    with zipfile.ZipFile(backup/'encrypted-vault.zip') as z:
        for name in z.namelist():assert z.read(name)==(ROOT/name).read_bytes()
    folder=ROOT/'data/ui-redesign/dam-completed-v2';folder.mkdir(exist_ok=False)
    os.environ['PLAYWRIGHT_BROWSERS_PATH']=str(ROOT/'data/playwright-browsers')
    os.environ['TEMP']=os.environ['TMP']=str(ROOT/'data/browser-temp')
    external=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(args=['--disable-background-networking'])
        context=browser.new_context(viewport={'width':1440,'height':900},service_workers='block')
        def allowed(url):
            p=urlsplit(url);return p.hostname=='127.0.0.1' and p.port==8501
        def guard(route):
            if allowed(route.request.url):route.continue_()
            else:external.append(True);route.abort()
        context.route('**/*',guard);context.route_web_socket('**/*',lambda ws:ws.connect_to_server() if allowed(ws.url) else ws.close())
        page=context.new_page();page.goto('http://127.0.0.1:8501')
        page.get_by_role('heading',name='Tu próxima oportunidad IT',exact=True).wait_for(timeout=60000);idle(page)
        navigate(page,'Perfil y configuración')
        assert not page.get_by_test_id('stException').count()
        assert COMPLETED['text_en'] in ' '.join(' '.join(page.get_by_test_id('stText').all_text_contents()).split())
        expect(page.get_by_role('button',name='Aprobar esta versión del CV',exact=True)).to_be_disabled()
        expect(page.get_by_role('checkbox',name='He revisado íntegramente esta versión y apruebo este CV definitivo',exact=True)).not_to_be_checked()
        page.screenshot(path=str(folder/'profile-masked.png'),full_page=True,mask=[page.get_by_test_id('stText')])
        context.close();browser.close()
    assert not external
    assert db.rows('SELECT approved_at FROM candidate_documents WHERE id=?',(did,))[0]['approved_at'] is None
    result={'at':now(),'status':'PASS','main_integrity':'ok','foreign_key_errors':0,'prechange_backup_hashes_and_archives_verified':True,'counts':counts,
        'active_approved_facts':active,'only_authorized_fact_and_cv_revocations':True,'previous_encrypted_records_and_assets_retained':True,
        'all_previous_job_ids_retained':True,'cv_document_id':did,'cv_pending_user_review':True,'profile_browser_verified':True,
        'contacts_in_logs_or_databases':leaks,'browser_external_requests':len(external),'autoapply_control':control,'runtime':runtime,
        'unchanged_application_tables':untouched,'no_database_restored':True}
    output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))


if __name__=='__main__':main()
