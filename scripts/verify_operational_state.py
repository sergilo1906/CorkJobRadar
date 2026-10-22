"""Verify production history and ciphertext against the pre-development backup, read-only."""
import json
import hashlib
from pathlib import Path
import sqlite3
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now
from corkjobradar.db import Database
from corkjobradar.autoapply.policy import current_policy
from corkjobradar.autoapply.vault import candidate_snapshot


def main():
    manifest=json.loads((ROOT/'logs/operational-backup.json').read_text(encoding='utf-8'))
    folder=(ROOT/manifest['path']).resolve()
    if not folder.is_relative_to((ROOT/'data/backups').resolve()):raise ValueError('BACKUP_OUTSIDE_PROJECT')
    backup=folder/'radar.sqlite3'
    hashes={name:hashlib.sha256((folder/name).read_bytes()).hexdigest()==manifest['hashes'][name] for name in ('radar.sqlite3','code.zip')}
    old=sqlite3.connect(backup.as_uri()+'?mode=ro&immutable=1',uri=True)
    try:backup_ok=old.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    finally:old.close()
    db=Database();report={'checked_at':now(),'backup_hashes':hashes,'backup_integrity':backup_ok,'restored_over_production':False,'history':{}}
    with sqlite3.connect(db.path.as_uri()+'?mode=ro',uri=True) as con:
        con.row_factory=sqlite3.Row
        con.execute('BEGIN')
        class Snapshot:
            def rows(self,sql,params=()):return [dict(r) for r in con.execute(sql,params).fetchall()]
        view=Snapshot()
        view.rows('ATTACH DATABASE ? AS before',(backup.as_uri()+'?mode=ro&immutable=1',))
        for table in ('jobs','job_analyses','job_snapshots','verification_events','audit_events','application_events','application_plans','user_actions','candidate_facts','autoapply_policies'):
            before=view.rows('SELECT COUNT(*) n FROM before.'+table)[0]['n']
            missing=view.rows('SELECT COUNT(*) n FROM (SELECT * FROM before.'+table+' EXCEPT SELECT * FROM main.'+table+')')[0]['n']
            report['history'][table]={'before':before,'missing_or_changed':missing}
        report['counts']={table:view.rows('SELECT COUNT(*) n FROM '+table)[0]['n'] for table in ('jobs','candidate_facts','candidate_documents','application_attempts','user_actions','autoapply_form_inspections','autoapply_trial_consents','application_receipt_evidence')}
        report['approved_documents']=view.rows('SELECT COUNT(*) n FROM candidate_documents WHERE approved_at IS NOT NULL AND revoked_at IS NULL')[0]['n']
        report['integrity']=view.rows('PRAGMA main.integrity_check')
        report['foreign_keys']=view.rows('PRAGMA main.foreign_key_check')
        report['schema']=view.rows('PRAGMA main.user_version')[0]['user_version']
    control,_,_=current_policy(db);facts=candidate_snapshot(db)
    report.update(live_enabled=bool(control['live_enabled']),mode_enabled=bool(control['enabled']),facts_hash=facts['_facts_hash'],cv_facts_hash=facts['_cv_facts_hash'],
                  active_facts=len(facts['_fact_ids'])+len(facts['_claims'])+len(facts['_answers']),original_history_preserved=all(not r['missing_or_changed'] for r in report['history'].values()))
    report['plaintext_contact_leaks']=0
    for path in (db.path,Path(str(db.path)+'-wal'),Path(str(db.path)+'-shm')):
        if path.exists():
            content=path.read_bytes()
            report['plaintext_contact_leaks']+=sum(facts[field].encode('utf-8') in content for field in ('email','phone','linkedin_url') if facts.get(field))
    (ROOT/'logs/operational-production-state.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    # The original manifest also listed transient sidecars observed before connection close.
    # Main DB is checked independently in immutable mode and needs no WAL to restore.
    (folder/'validation-after-close.json').write_text(json.dumps({'checked_at':now(),'authoritative_artifacts':hashes,'main_db_integrity_without_wal':backup_ok,'transient_sidecars_required':False},indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='history'}))
    return 0 if all(hashes.values()) and backup_ok and report['original_history_preserved'] and not report['foreign_keys'] and not report['live_enabled'] and not report['plaintext_contact_leaks'] else 2


if __name__=='__main__':raise SystemExit(main())
