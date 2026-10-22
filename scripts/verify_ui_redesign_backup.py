"""Verify final snapshots, encrypted assets and archived delivery files without restoring."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import zipfile
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now
from corkjobradar.db import Database
from corkjobradar.runtime import alive


def main():
    output=ROOT/'logs/ui-redesign-backup-verification.json'
    if output.exists():raise ValueError('PRESERVE_EXISTING_VERIFICATION')
    report=json.loads((ROOT/'logs/ui-redesign-final-backup.json').read_text(encoding='utf-8'))
    folder=(ROOT/report['path']).resolve();assert folder.is_relative_to(ROOT/'data/backups')
    assert json.loads((folder/'manifest.json').read_text(encoding='utf-8'))==report
    for name,expected in report['hashes'].items():
        with (folder/name).open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==expected
    checked=0
    with zipfile.ZipFile(folder/'code-and-evidence.zip') as archive:
        assert archive.testzip() is None
        required=['app.py','.streamlit/config.toml','PROGRESO.md','NEXT_STEPS.md','docs/SESSION_CHECKPOINT.md','corkjobradar/ui/pages.py','corkjobradar/ui/styles.css',
            'scripts/update_dam_completed_20261022.py','scripts/check_dam_completed_delivery.py','scripts/verify_ui_redesign_backup.py',
            'tests/test_dam_completed_update.py','logs/ui-redesign-dam-completed.xml','logs/ui-redesign-final-adjustments.json',
            'logs/ui-redesign-dam-completed-delivery.json','logs/dam-completed-baseline-backup.json']
        assert set(required).issubset(archive.namelist())
        for name in archive.namelist():
            if name.startswith('logs/') or name.startswith('data/runtime-logs/'):continue
            assert archive.read(name)==(ROOT/name).read_bytes(),name
            checked+=1
    con=sqlite3.connect((folder/'radar.sqlite3').as_uri()+'?mode=ro&immutable=1',uri=True);con.row_factory=sqlite3.Row
    try:
        assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not con.execute('PRAGMA foreign_key_check').fetchall()
        assert con.execute('PRAGMA user_version').fetchone()[0]==12
        assert con.execute('SELECT COUNT(*) FROM candidate_facts WHERE revoked_at IS NULL').fetchone()[0]==22
        assert con.execute('SELECT COUNT(*) FROM candidate_facts').fetchone()[0]==23
        assert con.execute("SELECT COUNT(*) FROM candidate_documents WHERE kind='CV' AND approved_at IS NULL AND revoked_at IS NULL").fetchone()[0]==1
        assert con.execute('SELECT COUNT(*) FROM application_attempts').fetchone()[0]==0
        assert con.execute('SELECT live_enabled FROM autoapply_control').fetchone()[0]==0
        assets=set()
        for table in ('candidate_documents','autoapply_form_inspections','application_receipt_evidence','manual_application_handoffs','manual_application_evidence'):
            assets.update(Path(row[0]).resolve() for row in con.execute('SELECT encrypted_path FROM '+table))
    finally:con.close()
    with zipfile.ZipFile(folder/'encrypted-vault.zip') as archive:
        assert archive.testzip() is None
        assert len(assets)==report['encrypted_assets']==5
        assert set(archive.namelist())=={p.relative_to(ROOT).as_posix() for p in assets}
        for asset in assets:assert archive.read(asset.relative_to(ROOT).as_posix())==asset.read_bytes()
    baseline=json.loads((ROOT/'logs/ui-redesign-baseline-backup.json').read_text(encoding='utf-8'))
    transport=sqlite3.connect((folder/'transport.sqlite3').as_uri()+'?mode=ro&immutable=1',uri=True)
    try:
        assert transport.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not transport.execute('PRAGMA foreign_key_check').fetchall()
        transport.execute('ATTACH DATABASE ? AS prior',(str(ROOT/baseline['path']/'transport.sqlite3'),))
        assert not transport.execute('SELECT sql FROM prior.sqlite_master EXCEPT SELECT sql FROM main.sqlite_master').fetchall()
        assert not transport.execute('SELECT sql FROM main.sqlite_master EXCEPT SELECT sql FROM prior.sqlite_master').fetchall()
        tables=[r[0] for r in transport.execute("SELECT name FROM main.sqlite_master WHERE type='table'")]
        for table in tables:
            assert table.replace('_','').isalnum()
            for a,b in [('main','prior'),('prior','main')]:
                assert not transport.execute('SELECT * FROM '+a+'.'+table+' EXCEPT SELECT * FROM '+b+'.'+table+' LIMIT 1').fetchall(),table
    finally:transport.close()
    db=Database();runtime=db.rows('SELECT desired,state,supervisor_pid,supervisor_stamp,owner_pid,owner_stamp,next_search_at FROM local_runtime')[0]
    assert alive(runtime['supervisor_pid'],runtime['supervisor_stamp']) and alive(runtime['owner_pid'],runtime['owner_stamp'])
    assert db.rows('SELECT enabled,live_enabled,paused,epoch FROM autoapply_control')[0]=={'enabled':0,'live_enabled':0,'paused':1,'epoch':0}
    assert httpx.get('http://127.0.0.1:8501/_stcore/health',timeout=10,trust_env=False).status_code==200
    result={'checked_at':now(),'status':'PASS','backup':report['path'],'all_manifest_hashes_verified':True,'zip_crc_verified':True,
        'archived_immutable_files_match_current':checked,'encrypted_assets_verified':len(assets),'both_database_integrity':'ok',
        'foreign_key_errors':0,'schema':12,'snapshot_counts':report['counts'],'transport_logically_unchanged':True,
        'transport_tables_compared':len(tables),'active_approved_facts':22,'historical_facts':23,'cv_version_2_pending':True,
        'live_enabled':False,'external_applications_sent':0,'app_health':200,'runtime':runtime,'no_database_restored':True}
    output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))


if __name__=='__main__':main()
