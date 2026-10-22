"""Compare all pre-existing tables with this continuation's baseline; no PII output."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now
from corkjobradar.db import Database
from corkjobradar.autoapply.vault import candidate_snapshot


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-manifest',default='logs/verified-flow-baseline-backup.json')
    parser.add_argument('--report',default='logs/verified-flow-production-audit.json')
    parser.add_argument('--check-log-prefix',default='verified-flow-')
    parser.add_argument('--expected-jobs',type=int,default=459)
    args=parser.parse_args()
    manifest_path=(ROOT/args.baseline_manifest).resolve()
    report_path=(ROOT/args.report).resolve()
    if not manifest_path.is_relative_to(ROOT/'logs') or not report_path.is_relative_to(ROOT/'logs'):
        raise ValueError('AUDIT_PATH_OUTSIDE_PROJECT_LOGS')
    if not args.check_log_prefix or not all(c.isalnum() or c in '-_' for c in args.check_log_prefix):
        raise ValueError('INVALID_LOG_PREFIX')
    if report_path.exists():raise FileExistsError('PRESERVE_PREVIOUS_AUDIT_REPORT')
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    folder=(ROOT/manifest['path']).resolve()
    if not folder.is_relative_to(ROOT/'data/backups'):raise ValueError('BACKUP_OUTSIDE_PROJECT')
    backup=folder/'radar.sqlite3'
    with backup.open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==manifest['hashes']['radar.sqlite3']
    db=Database();tables={}
    with sqlite3.connect(db.path.as_uri()+'?mode=ro',uri=True) as con:
        con.execute('BEGIN')
        con.execute('ATTACH DATABASE ? AS baseline',(backup.as_uri()+'?mode=ro&immutable=1',))
        names=[r[0] for r in con.execute("SELECT name FROM baseline.sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        for table in names:
            assert table.replace('_','').isalnum()
            missing=con.execute('SELECT COUNT(*) FROM (SELECT * FROM baseline.'+table+' EXCEPT SELECT * FROM main.'+table+')').fetchone()[0]
            added=con.execute('SELECT COUNT(*) FROM (SELECT * FROM main.'+table+' EXCEPT SELECT * FROM baseline.'+table+')').fetchone()[0]
            tables[table]={'missing_or_changed':missing,'added_or_changed':added}
        integrity=con.execute('PRAGMA main.integrity_check').fetchone()[0]
        foreign_keys=con.execute('PRAGMA main.foreign_key_check').fetchall()
        new_names={r[0] for r in con.execute("SELECT name FROM main.sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}-set(names)
        new_tables={}
        for table in sorted(new_names):
            assert table.replace('_','').isalnum()
            new_tables[table]=con.execute('SELECT COUNT(*) FROM main.'+table).fetchone()[0]
    facts=candidate_snapshot(db);leaks=0
    contact_values=[facts[k] for k in ('email','phone','linkedin_url') if facts.get(k)]
    for path in (db.path,Path(str(db.path)+'-wal'),Path(str(db.path)+'-shm')):
        if path.exists():
            raw=path.read_bytes()
            leaks+=sum(value.encode('utf-8') in raw for value in contact_values)
    # Check both Python UTF-8 and PowerShell UTF-16 logs without exposing values.
    logs_checked=0;log_leaks=0
    for path in (ROOT/'logs').glob(args.check_log_prefix+'*'):
        if path.is_file():
            logs_checked+=1;raw=path.read_bytes()
            log_leaks+=sum(any(value.encode(encoding) in raw for encoding in ('utf-8','utf-16-le')) for value in contact_values)
    control=db.rows('SELECT enabled,live_enabled,paused,epoch FROM autoapply_control')[0]
    report={'checked_at':now(),'schema':db.rows('PRAGMA user_version')[0]['user_version'],'integrity':integrity,
            'foreign_key_errors':len(foreign_keys),'tables':tables,'all_previous_rows_unchanged':all(not v['missing_or_changed'] for v in tables.values()),
            'plaintext_contact_leaks':leaks,'log_contact_leaks':log_leaks,'logs_checked':logs_checked,
            'baseline_manifest':str(manifest_path.relative_to(ROOT)),'new_tables':new_tables,
            'control':control,'repository':'GIT_PRESENT_NOT_INSPECTED' if (ROOT/'.git').exists() else 'NO_GIT_REPOSITORY',
            'counts':{t:db.rows('SELECT COUNT(*) n FROM '+t)[0]['n'] for t in
                ('jobs','candidate_facts','candidate_documents','autoapply_policies','application_attempts','user_actions','application_receipt_evidence','autoapply_trial_consents','manual_application_handoffs','manual_application_declarations','autoapply_interventions','autoapply_intervention_commands','manual_application_evidence','manual_application_evidence_reviews','manual_requirement_reviews')},
            'approved_cv_documents':db.rows('SELECT COUNT(*) n FROM candidate_documents WHERE approved_at IS NOT NULL AND revoked_at IS NULL')[0]['n']}
    transport_backup=folder/'transport.sqlite3'
    with transport_backup.open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==manifest['hashes']['transport.sqlite3']
    with sqlite3.connect((ROOT/'data/transport.sqlite3').as_uri()+'?mode=ro',uri=True) as con:
        con.execute('BEGIN')
        con.execute('ATTACH DATABASE ? AS baseline',(transport_backup.as_uri()+'?mode=ro&immutable=1',))
        report['transport_integrity']=con.execute('PRAGMA integrity_check').fetchone()[0]
        report['transport_foreign_key_errors']=len(con.execute('PRAGMA foreign_key_check').fetchall())
        report['transport_tables']={}
        for (table,) in con.execute("SELECT name FROM baseline.sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
            assert table.replace('_','').isalnum()
            missing=con.execute('SELECT COUNT(*) FROM (SELECT * FROM baseline.'+table+' EXCEPT SELECT * FROM main.'+table+')').fetchone()[0]
            added=con.execute('SELECT COUNT(*) FROM (SELECT * FROM main.'+table+' EXCEPT SELECT * FROM baseline.'+table+')').fetchone()[0]
            report['transport_tables'][table]={'missing_or_changed':missing,'added_or_changed':added}
    report['both_databases_rows_unchanged']=all(not v['missing_or_changed'] and not v['added_or_changed'] for v in
                                              list(tables.values())+list(report['transport_tables'].values()))
    report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    assert report['all_previous_rows_unchanged'] and integrity=='ok' and not foreign_keys and not leaks and not log_leaks
    assert report['transport_integrity']=='ok' and not report['transport_foreign_key_errors']
    assert control=={'enabled':0,'live_enabled':0,'paused':1,'epoch':0}
    assert report['counts']['candidate_facts']==22 and report['counts']['jobs']==args.expected_jobs
    assert report['counts']['application_attempts']==report['counts']['user_actions']==report['counts']['autoapply_trial_consents']==0
    assert report['counts']['autoapply_interventions']==report['counts']['autoapply_intervention_commands']==0
    assert report['counts']['manual_application_evidence']==report['counts']['manual_application_evidence_reviews']==0
    assert report['counts']['manual_requirement_reviews']==0
    print(json.dumps({k:v for k,v in report.items() if k not in {'tables','transport_tables'}}))


if __name__=='__main__':main()
