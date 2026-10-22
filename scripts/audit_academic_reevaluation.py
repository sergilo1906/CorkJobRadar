"""Read-only preservation and safety audit after reanalysis, against its consistent backup."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now
from corkjobradar.db import Database
from corkjobradar.runtime import alive
from corkjobradar.autoapply.vault import candidate_snapshot


def main():
    output=ROOT/'logs/academic-reevaluation-preservation.json'
    if output.exists():raise ValueError('PRESERVE_EXISTING_AUDIT')
    baseline=json.loads((ROOT/'logs/academic-reevaluation-baseline-backup.json').read_text(encoding='utf-8'));folder=ROOT/baseline['path']
    for name,expected in baseline['hashes'].items():
        with (folder/name).open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==expected
    con=sqlite3.connect((ROOT/'data/radar.sqlite3').as_uri()+'?mode=ro',uri=True);con.row_factory=sqlite3.Row
    try:
        con.execute('ATTACH DATABASE ? AS prior',(str(folder/'radar.sqlite3'),));con.execute('BEGIN')
        assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not con.execute('PRAGMA foreign_key_check').fetchall()
        assert con.execute('PRAGMA user_version').fetchone()[0]==12
        exact=['candidate_facts','candidate_documents','autoapply_control','autoapply_policies','application_plans','application_attempts',
            'user_actions','autoapply_form_inspections','autoapply_trial_consents','application_receipt_evidence','manual_application_handoffs',
            'manual_application_declarations','manual_application_evidence','manual_application_evidence_reviews','manual_requirement_reviews',
            'it_selection_origins','it_worksite_evidence']
        retained=['job_snapshots','job_analyses','it_application_queue_events','verification_events','local_runtime_events']
        for table in exact+retained:
            assert not con.execute('SELECT * FROM prior.'+table+' EXCEPT SELECT * FROM main.'+table+' LIMIT 1').fetchall(),table
            if table in exact:assert not con.execute('SELECT * FROM main.'+table+' EXCEPT SELECT * FROM prior.'+table+' LIMIT 1').fetchall(),table
        assert not con.execute('SELECT id,title,company,location,url,apply_url,description,raw FROM prior.jobs EXCEPT SELECT id,title,company,location,url,apply_url,description,raw FROM main.jobs').fetchall()
        repair=json.loads((ROOT/'logs/academic-reevaluation-ashby-normalization.json').read_text(encoding='utf-8'))
        corrections={r['job_id']:r for r in repair['changes']}
        changed=con.execute('SELECT p.id,p.content_hash old_hash,j.content_hash new_hash,p.mode old_mode,j.mode new_mode FROM prior.jobs p JOIN main.jobs j ON j.id=p.id WHERE p.content_hash<>j.content_hash').fetchall()
        assert {r['id'] for r in changed}==set(corrections)
        for row in changed:
            expected=corrections[row['id']]
            assert all(row[k]==expected[k] for k in ('old_hash','new_hash','old_mode','new_mode'))
            assert con.execute('SELECT 1 FROM job_snapshots WHERE job_id=? AND content_hash=?',(row['id'],row['old_hash'])).fetchone()
        assert not con.execute('SELECT source_id,external_id,job_id,first_seen_at FROM prior.job_sources EXCEPT SELECT source_id,external_id,job_id,first_seen_at FROM main.job_sources').fetchall()
        old_analyses=con.execute('SELECT COUNT(*) FROM prior.job_analyses').fetchone()[0]
        counts={t:con.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ('jobs','job_analyses','candidate_facts','candidate_documents','it_application_queue','application_attempts')}
        runtime=dict(con.execute('SELECT desired,state,interval_hours,supervisor_pid,supervisor_stamp,owner_pid,owner_stamp,next_search_at FROM local_runtime').fetchone())
        assert runtime['desired']=='RUNNING' and runtime['interval_hours']==6
        assert alive(runtime['supervisor_pid'],runtime['supervisor_stamp']) and alive(runtime['owner_pid'],runtime['owner_stamp'])
    finally:con.close()
    db=Database();candidate=candidate_snapshot(db)
    assert not candidate.get('cv_document_id')
    current=db.rows("SELECT COUNT(DISTINCT a.job_id) n FROM job_analyses a JOIN jobs j ON a.job_id=j.id AND a.content_hash=j.content_hash WHERE json_extract(a.result,'$.candidate_facts_hash')=?",(candidate['_cv_facts_hash'],))[0]['n']
    assert current==counts['jobs'] and counts['it_application_queue']==counts['jobs']
    assert db.rows('SELECT enabled,live_enabled,paused,epoch FROM autoapply_control')[0]=={'enabled':0,'live_enabled':0,'paused':1,'epoch':0}
    with zipfile.ZipFile(folder/'encrypted-vault.zip') as archive:
        assert archive.testzip() is None
        for name in archive.namelist():assert archive.read(name)==(ROOT/name).read_bytes()
    transport=sqlite3.connect((ROOT/'data/transport.sqlite3').as_uri()+'?mode=ro',uri=True)
    try:
        assert transport.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not transport.execute('PRAGMA foreign_key_check').fetchall()
        transport.execute('ATTACH DATABASE ? AS prior',(str(folder/'transport.sqlite3'),))
        tables=[r[0] for r in transport.execute("SELECT name FROM main.sqlite_master WHERE type='table'")]
        for table in tables:
            assert table.replace('_','').isalnum()
            for a,b in [('main','prior'),('prior','main')]:assert not transport.execute('SELECT * FROM '+a+'.'+table+' EXCEPT SELECT * FROM '+b+'.'+table+' LIMIT 1').fetchall(),table
    finally:transport.close()
    contacts=[candidate[k] for k in ('email','phone','linkedin_url') if candidate.get(k)];leaks=0
    paths=[p for p in (ROOT/'logs').glob('academic-reevaluation-*') if p.is_file()]+[ROOT/'data/radar.sqlite3',ROOT/'data/radar.sqlite3-wal',ROOT/'docs/OPORTUNIDADES_IT_DAM_2026-10-22.md']
    for p in paths:
        if p.exists():leaks+=sum(v.encode(enc) in p.read_bytes() for v in contacts for enc in ('utf-8','utf-16-le'))
    assert leaks==0
    result={'checked_at':now(),'status':'PASS','main_and_transport_integrity':'ok','foreign_key_errors':0,'schema':12,'counts':counts,
        'old_analyses_retained_unchanged':old_analyses,'current_academic_evaluations':current,'all_old_jobs_and_source_links_retained':True,
        'documented_mode_corrections_with_old_snapshots':len(changed),
        'professional_documents_permissions_unchanged':True,'previous_encrypted_assets_unchanged':True,'transport_tables_unchanged':len(tables),
        'contact_leaks':leaks,'cv_version_2_pending':True,'live_enabled':False,'applications_sent':0,'runtime':runtime,'no_database_restored':True}
    output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))


if __name__=='__main__':main()
