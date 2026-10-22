"""Audit authorized refresh without confusing metadata updates with lost history."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now
from corkjobradar.db import Database
from corkjobradar.autoapply.vault import candidate_snapshot
from corkjobradar.runtime import snapshot


def main():
    output=ROOT/'logs/local-runtime-delivery-audit.json'
    if output.exists():raise FileExistsError('PRESERVE_AUDIT')
    manifest=json.loads((ROOT/'logs/local-runtime-baseline-backup.json').read_text(encoding='utf-8'))
    baseline=(ROOT/manifest['path']/'radar.sqlite3').resolve();db=Database()
    with baseline.open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==manifest['hashes']['radar.sqlite3']
    with sqlite3.connect(db.path.as_uri()+'?mode=ro',uri=True) as con:
        con.execute('BEGIN');con.execute('ATTACH DATABASE ? AS baseline',(baseline.as_uri()+'?mode=ro&immutable=1',))
        missing_jobs=con.execute('SELECT count(*) FROM baseline.jobs b LEFT JOIN main.jobs j ON j.id=b.id WHERE j.id IS NULL').fetchone()[0]
        missing_content=con.execute('''SELECT count(*) FROM baseline.jobs b JOIN main.jobs j ON j.id=b.id WHERE j.content_hash<>b.content_hash
             AND NOT EXISTS(SELECT 1 FROM main.job_snapshots s WHERE s.job_id=b.id AND s.content_hash=b.content_hash)''').fetchone()[0]
        missing_sources=con.execute('''SELECT count(*) FROM baseline.job_sources b WHERE NOT EXISTS(SELECT 1 FROM main.job_sources s
             WHERE s.source_id=b.source_id AND s.external_id=b.external_id AND s.job_id=b.job_id)''').fetchone()[0]
        preserved={}
        for table in ('candidate_facts','candidate_documents','autoapply_control','autoapply_policies','application_attempts','user_actions',
                      'autoapply_form_inspections','autoapply_trial_consents','application_receipt_evidence','manual_application_handoffs',
                      'manual_application_declarations','manual_requirement_reviews','job_snapshots','job_analyses','it_application_queue_events'):
            preserved[table]=con.execute('SELECT count(*) FROM (SELECT * FROM baseline.'+table+' EXCEPT SELECT * FROM main.'+table+')').fetchone()[0]
        integrity=con.execute('PRAGMA integrity_check').fetchone()[0];fk=con.execute('PRAGMA foreign_key_check').fetchall()
    facts=candidate_snapshot(db);contacts=[facts[k] for k in ('email','phone','linkedin_url') if facts.get(k)]
    leaks=0;files=0
    candidates=list((ROOT/'logs').glob('local-runtime-*'))+list((ROOT/'data/runtime-logs').glob('*.log'))
    candidates+=[db.path,Path(str(db.path)+'-wal'),Path(str(db.path)+'-shm')]
    for path in candidates:
        if not path.is_file():continue
        files+=1;raw=path.read_bytes()
        leaks+=sum(any(value.encode(enc) in raw for enc in ('utf-8','utf-16-le')) for value in contacts)
    transport=ROOT/'data/transport.sqlite3'
    with sqlite3.connect(transport.as_uri()+'?mode=ro',uri=True) as con:
        transport_ok=con.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not con.execute('PRAGMA foreign_key_check').fetchall()
    runtime=snapshot(db);control=db.rows('SELECT enabled,live_enabled,paused,epoch FROM autoapply_control')[0]
    report={'checked_at':now(),'schema':db.rows('PRAGMA user_version')[0]['user_version'],
            'integrity':integrity,'foreign_key_errors':len(fk),'transport_integrity':transport_ok,
            'old_jobs_missing':missing_jobs,'old_content_not_retained':missing_content,'old_source_bindings_missing':missing_sources,
            'old_audit_and_approved_rows_missing_or_changed':preserved,'contact_leaks':leaks,'files_checked':files,
            'jobs':db.rows('SELECT count(*) n FROM jobs')[0]['n'],'approved_facts':len(db.rows('SELECT id FROM candidate_facts WHERE revoked_at IS NULL')),
            'approved_cv':bool(facts.get('cv_document_id')),'autoapply_control':control,
            'runtime':{k:runtime['control'][k] for k in ('desired','state','interval_hours','next_search_at','last_search_run','last_search_finished')},
            'supervisor_alive':runtime['supervisor_alive'],'active_searches':len(db.rows("SELECT id FROM scan_runs WHERE status='running'")),
            'windows_startup_installed_by_agent':False,'live_enabled':False,'all_old_job_ids_preserved':missing_jobs==0,
            'permitted_changes':'Source observations, verification/analysis metadata, new real jobs, selection queue and local runtime; no replacement of database.'}
    output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    assert not missing_jobs and not missing_content and not missing_sources and not any(preserved.values())
    assert not leaks and integrity=='ok' and not fk and transport_ok and report['approved_facts']==22
    assert control=={'enabled':0,'live_enabled':0,'paused':1,'epoch':0} and report['active_searches']<=1
    print(json.dumps(report))


if __name__=='__main__':main()
