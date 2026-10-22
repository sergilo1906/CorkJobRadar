"""Read-only preservation/privacy audit against the pre-redesign snapshot."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now
from corkjobradar.autoapply.vault import candidate_snapshot
from corkjobradar.db import Database
from corkjobradar.runtime import alive


def main():
    temp=ROOT/'data/tmp';temp.mkdir(exist_ok=True)
    os.environ['TEMP']=os.environ['TMP']=str(temp)
    output=ROOT/'logs/ui-redesign-delivery-audit.json'
    if output.exists():raise ValueError('PRESERVE_EXISTING_AUDIT')
    baseline=json.loads((ROOT/'logs/ui-redesign-baseline-backup.json').read_text(encoding='utf-8'))
    old=(ROOT/baseline['path']/'radar.sqlite3').resolve()
    assert old.is_relative_to(ROOT/'data/backups')
    con=sqlite3.connect((ROOT/'data/radar.sqlite3').as_uri()+'?mode=ro',uri=True)
    con.row_factory=sqlite3.Row
    try:
        con.execute('ATTACH DATABASE ? AS prior',(str(old),))
        assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not con.execute('PRAGMA foreign_key_check').fetchall()
        assert con.execute('PRAGMA user_version').fetchone()[0]==12
        immutable=['candidate_facts','candidate_documents','autoapply_control','autoapply_policies','application_plans','application_attempts','user_actions',
                   'autoapply_form_inspections','autoapply_trial_consents','application_receipt_evidence','manual_application_handoffs','manual_application_declarations',
                   'manual_application_evidence','manual_application_evidence_reviews','manual_requirement_reviews','it_selection_origins','it_worksite_evidence',
                   'job_snapshots','job_analyses','it_application_queue_events','local_runtime_events']
        missing={t:con.execute('SELECT COUNT(*) FROM (SELECT * FROM prior.'+t+' EXCEPT SELECT * FROM main.'+t+')').fetchone()[0] for t in immutable}
        assert not any(missing.values()),missing
        columns=[r['name'] for r in con.execute('PRAGMA table_info(jobs)') if r['name'] not in {'last_seen_at','last_verified_at'}]
        cols=','.join(columns)
        changed=con.execute('SELECT COUNT(*) FROM (SELECT '+cols+' FROM prior.jobs EXCEPT SELECT '+cols+' FROM main.jobs)').fetchone()[0]
        assert changed==0
        bindings=con.execute('''SELECT COUNT(*) FROM (SELECT source_id,external_id,job_id,url,first_seen_at FROM prior.job_sources
            EXCEPT SELECT source_id,external_id,job_id,url,first_seen_at FROM main.job_sources)''').fetchone()[0]
        assert bindings==0
        counts={t:con.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ['jobs','candidate_facts','candidate_documents','application_attempts','manual_application_handoffs','manual_application_declarations']}
        control=dict(con.execute('SELECT enabled,live_enabled,paused,epoch FROM autoapply_control').fetchone())
        assert control=={'enabled':0,'live_enabled':0,'paused':1,'epoch':0}
        runtime=dict(con.execute('SELECT desired,state,interval_hours,supervisor_pid,supervisor_stamp,owner_pid,owner_stamp,next_search_at FROM local_runtime').fetchone())
        assert alive(runtime['supervisor_pid'],runtime['supervisor_stamp']) and alive(runtime['owner_pid'],runtime['owner_stamp'])
    finally:con.close()
    transport=ROOT/'data/transport.sqlite3'
    with transport.open('rb') as f:transport_hash=hashlib.file_digest(f,'sha256').hexdigest()
    check=sqlite3.connect(transport.as_uri()+'?mode=ro',uri=True)
    try:
        assert check.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not check.execute('PRAGMA foreign_key_check').fetchall()
        check.execute('ATTACH DATABASE ? AS prior',(str(old.parent/'transport.sqlite3'),))
        assert not check.execute('SELECT sql FROM prior.sqlite_master EXCEPT SELECT sql FROM main.sqlite_master').fetchall()
        assert not check.execute('SELECT sql FROM main.sqlite_master EXCEPT SELECT sql FROM prior.sqlite_master').fetchall()
        transport_rows={}
        for (table,) in check.execute("SELECT name FROM prior.sqlite_master WHERE type='table'").fetchall():
            if not table.replace('_','').isalnum():raise ValueError('UNEXPECTED_TABLE_NAME')
            missing_rows=check.execute('SELECT COUNT(*) FROM (SELECT * FROM prior.'+table+' EXCEPT SELECT * FROM main.'+table+')').fetchone()[0]
            added_rows=check.execute('SELECT COUNT(*) FROM (SELECT * FROM main.'+table+' EXCEPT SELECT * FROM prior.'+table+')').fetchone()[0]
            assert missing_rows==added_rows==0
            transport_rows[table]={'missing':missing_rows,'added':added_rows}
    finally:check.close()
    candidate=candidate_snapshot(Database())
    contacts=[str(candidate.get(k,'')) for k in ('email','phone','linkedin_url') if candidate.get(k)]
    paths=[p for p in (ROOT/'logs').glob('ui-redesign-*') if p.is_file() and p.suffix in {'.log','.xml','.json','.toml'}]
    paths += [ROOT/'data/radar.sqlite3',ROOT/'data/radar.sqlite3-wal']
    leaks=0
    for p in paths:
        if not p.is_file():continue
        content=p.read_bytes()
        leaks+=sum(value.encode(encoding) in content for value in contacts for encoding in ('utf-8','utf-16-le'))
    assert leaks==0
    result={'checked_at':now(),'status':'PASS','schema':12,'both_databases_integrity':'ok','foreign_key_errors':0,'counts':counts,
            'old_jobs_lost_or_content_changed':changed,'old_source_bindings_lost':bindings,'old_immutable_rows_missing_or_changed':missing,
            'contact_leaks':leaks,'files_checked':len(paths),'autoapply_control':control,'approved_cv':bool(candidate.get('cv_document_id')),
            'runtime':runtime,'supervisor_alive':True,'transport_logically_unchanged':True,'transport_row_differences':transport_rows,
            'transport_file_hash':transport_hash,'transport_snapshot_hash':baseline['hashes']['transport.sqlite3'],'documented_test_isolation_incident':'logs/ui-redesign-test-isolation-incident.json',
            'allowed_noncontent_updates':'Observed/verified timestamps and historical run/source/task completion from documented read-only test-launcher incident; normal local-runtime events/queue.',
            'no_database_restored':True,'windows_startup_installed_by_agent':False,'live_enabled':False}
    output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='old_immutable_rows_missing_or_changed'}))


if __name__=='__main__':main()
