"""Verify final local delivery without restoring production."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now


def main():
    output=ROOT/'logs/academic-reevaluation-backup-verification.json'
    if output.exists():raise ValueError('PRESERVE_EXISTING_PROOF')
    report=json.loads((ROOT/'logs/academic-reevaluation-final-backup.json').read_text(encoding='utf-8'));folder=(ROOT/report['path']).resolve()
    assert folder.is_relative_to(ROOT/'data/backups')
    assert json.loads((folder/'manifest.json').read_text(encoding='utf-8'))==report
    for name,expected in report['hashes'].items():
        with (folder/name).open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==expected
    checked=0
    with zipfile.ZipFile(folder/'code-and-evidence.zip') as z:
        assert z.testzip() is None
        for name in ['corkjobradar/autoapply/academic.py','corkjobradar/reevaluation.py','PROGRESO.md','NEXT_STEPS.md','docs/SESSION_CHECKPOINT.md',
            'docs/ACADEMIC_REEVALUATION_2026-10-22.md','docs/OPORTUNIDADES_IT_DAM_2026-10-22.md','exports/Oportunidades-IT-DAM-2026-10-22.xlsx',
            'logs/academic-reevaluation-full.xml','logs/academic-reevaluation-preservation.json','logs/academic-reevaluation-delivery-browser.json']:
            assert name in z.namelist(),name
        for name in z.namelist():
            if name.startswith('logs/') or name.startswith('data/runtime-logs/'):continue
            assert z.read(name)==(ROOT/name).read_bytes(),name
            checked+=1
    for name in ('radar.sqlite3','transport.sqlite3'):
        c=sqlite3.connect((folder/name).as_uri()+'?mode=ro&immutable=1',uri=True)
        try:
            assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            assert not c.execute('PRAGMA foreign_key_check').fetchall()
            if name=='radar.sqlite3':
                assert c.execute('SELECT COUNT(*) FROM candidate_facts WHERE revoked_at IS NULL').fetchone()[0]==22
                assert c.execute('SELECT COUNT(*) FROM application_attempts').fetchone()[0]==0
                assert c.execute('SELECT live_enabled FROM autoapply_control').fetchone()[0]==0
                assert c.execute('SELECT approved_at,revoked_at FROM candidate_documents WHERE id=2').fetchone()==(None,None)
        finally:c.close()
    with zipfile.ZipFile(folder/'encrypted-vault.zip') as z:
        assert z.testzip() is None and len(z.namelist())==report['encrypted_assets']==5
        for name in z.namelist():assert z.read(name)==(ROOT/name).read_bytes()
    result={'checked_at':now(),'status':'PASS','backup':report['path'],'all_manifest_hashes_verified':True,'zip_crc_verified':True,
        'archived_code_docs_exports_screenshots_match_current':checked,'both_database_integrity':'ok','foreign_key_errors':0,
        'encrypted_assets_verified':5,'counts':report['counts'],'active_professional_facts':22,'cv_2_pending':True,'live_enabled':False,'applications_sent':0,'restored_over_production':False}
    output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))


if __name__=='__main__':main()
