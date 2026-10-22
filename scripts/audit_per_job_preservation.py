"""Read-only historical/DPAPI/privacy checks against the verified phase backup."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now
from corkjobradar.db import Database
from corkjobradar.autoapply.vault import candidate_snapshot,protect
from corkjobradar import runtime as rt


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--label',required=True);args=p.parse_args()
    if not re.fullmatch(r'per-job-[a-z0-9-]+',args.label):raise ValueError('SAFE_LABEL_REQUIRED')
    target=ROOT/'logs'/(args.label+'.json')
    if target.exists():raise ValueError('PRESERVE_PREVIOUS_EVIDENCE')
    baseline=json.loads((ROOT/'logs/per-job-start-backup.json').read_text(encoding='utf-8'))
    folder=(ROOT/baseline['path']).resolve()
    assert folder.is_relative_to((ROOT/'data/backups').resolve())
    for name,sha in baseline['hashes'].items():
        with (folder/name).open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==sha
    db=Database();candidate=candidate_snapshot(db)
    checked=[]
    with sqlite3.connect(db.path.as_uri()+'?mode=ro',uri=True) as con:
        assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not con.execute('PRAGMA foreign_key_check').fetchall()
        con.execute('ATTACH DATABASE ? AS baseline',((folder/'radar.sqlite3').as_uri()+'?mode=ro&immutable=1',))
        tables=('jobs','job_sources','job_snapshots','job_analyses','candidate_facts','candidate_documents','autoapply_control',
                'autoapply_policies','application_attempts','application_receipt_evidence','manual_application_handoffs',
                'manual_application_declarations','manual_application_evidence','manual_requirement_reviews','autoapply_form_inspections')
        for table in tables:
            assert not con.execute(f'SELECT * FROM baseline.{table} EXCEPT SELECT * FROM main.{table}').fetchall(), 'HISTORICAL_ROWS_CHANGED:'+table
            checked.append(table)
    asset_count=0
    with zipfile.ZipFile(folder/'encrypted-vault.zip') as archive:
        assert archive.testzip() is None
        for name in archive.namelist():
            path=(ROOT/name).resolve();assert path.is_relative_to(ROOT/'data/autoapply-private')
            assert path.read_bytes()==archive.read(name);asset_count+=1
    transport=sqlite3.connect((ROOT/'data/transport.sqlite3').as_uri()+'?mode=ro',uri=True)
    try:
        assert transport.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not transport.execute('PRAGMA foreign_key_check').fetchall()
        transport.execute('ATTACH DATABASE ? AS baseline',((folder/'transport.sqlite3').as_uri()+'?mode=ro&immutable=1',))
        transport_tables=[r[0] for r in transport.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for table in transport_tables:
            assert re.fullmatch(r'[a-zA-Z0-9_]+',table)
            assert not transport.execute(f'SELECT * FROM baseline.{table} EXCEPT SELECT * FROM main.{table}').fetchall()
            assert not transport.execute(f'SELECT * FROM main.{table} EXCEPT SELECT * FROM baseline.{table}').fetchall()
    finally:transport.close()
    needles=[str(candidate[key]).encode('utf-8') for key in ('full_name','email','phone','linkedin_url') if candidate.get(key) and len(str(candidate[key]))>=8]
    paths=[p for p in (ROOT/'logs').glob('per-job-*') if p.is_file()]+[db.path]
    for suffix in ('-wal','-shm'):
        path=Path(str(db.path)+suffix)
        if path.exists():paths.append(path)
    leaks=sum(1 for path in paths if any(needle in path.read_bytes() for needle in needles))
    assert leaks==0, 'PRIVATE_DATA_IN_LOG_OR_SQLITE'
    refs=db.rows('SELECT * FROM reference_originals')
    for row in refs:
        assert not row['reviewed_at'] and not json.loads(protect(row['metadata'],True))['share_authorized']
    assert not db.rows('SELECT * FROM job_document_bundles')
    assert not db.rows('SELECT * FROM application_attempts')
    assert not db.rows('SELECT * FROM application_receipt_evidence')
    runtime=rt.state(db)
    assert rt.alive(runtime['supervisor_pid'],runtime['supervisor_stamp'])
    assert runtime['desired']=='RUNNING' and runtime['interval_hours']==6
    report={'created_at':now(),'status':'PASS','preserved_tables':checked,'original_encrypted_assets_unchanged':asset_count,
            'transport_tables_identical':len(transport_tables),'integrity':'ok','foreign_key_errors':0,
            'active_approved_facts':len(candidate['_claims'])+len(candidate['_fact_ids']),
            'general_documents':len(db.rows('SELECT id FROM candidate_documents')),'references_pending':len(refs),
            'job_document_versions':len(db.rows('SELECT id FROM job_document_versions')),
            'approved_bundles':0,'plaintext_contact_matches':leaks,'files_checked_for_privacy':len(paths),
            'live_enabled':False,'applications_sent':0,'supervisor_alive':True,'interval_hours':6}
    target.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))


if __name__=='__main__':main()
