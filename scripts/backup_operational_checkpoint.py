"""Consistent local checkpoint with explicit connection close and encrypted-vault assets."""
import hashlib
import argparse
import json
from pathlib import Path
import sqlite3
import re
import sys
from uuid import uuid4
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now
from corkjobradar.db import Database


def file_hash(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--label',default='operational-tested')
    parser.add_argument('--report',default='operational-checkpoint-backup.json')
    args=parser.parse_args()
    if not re.fullmatch(r'[a-z0-9-]+',args.label) or not re.fullmatch(r'[a-z0-9-]+\.json',args.report):raise ValueError('INVALID_LOCAL_BACKUP_NAME')
    if (ROOT/'logs'/args.report).exists():raise ValueError('PRESERVE_EXISTING_BACKUP_REPORT')
    db=Database()
    folder=(ROOT/'data/backups'/(args.label+'-'+now().replace(':','')+'-'+uuid4().hex[:6])).resolve()
    if not folder.is_relative_to((ROOT/'data/backups').resolve()):raise ValueError('BACKUP_OUTSIDE_PROJECT')
    folder.mkdir(parents=True,exist_ok=False)
    source=sqlite3.connect(db.path.as_uri()+'?mode=ro',uri=True)
    destination=sqlite3.connect(folder/'radar.sqlite3')
    try:source.backup(destination)
    finally:destination.close();source.close()
    snapshot=sqlite3.connect((folder/'radar.sqlite3').as_uri()+'?mode=ro&immutable=1',uri=True)
    try:
        assert snapshot.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not snapshot.execute('PRAGMA foreign_key_check').fetchall()
        tables={r[0] for r in snapshot.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        counts={t:snapshot.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ('jobs','job_analyses','job_snapshots','scan_runs','source_runs','task_queue','candidate_facts','candidate_documents','autoapply_form_inspections','application_attempts','application_receipt_evidence','user_actions','autoapply_interventions','autoapply_intervention_commands','manual_application_handoffs','manual_application_declarations','manual_application_evidence','manual_application_evidence_reviews','manual_requirement_reviews','it_selection_origins','it_worksite_evidence','it_application_queue','it_application_queue_events','local_runtime','local_runtime_events','local_runtime_notifications') if t in tables}
        paths=set()
        for table in ('candidate_documents','autoapply_form_inspections','application_receipt_evidence','manual_application_handoffs','manual_application_evidence'):
            if table not in tables:continue
            paths.update(Path(row[0]).resolve() for row in snapshot.execute('SELECT encrypted_path FROM '+table))
    finally:snapshot.close()
    transport=ROOT/'data/transport.sqlite3'
    if transport.exists():
        original=sqlite3.connect(transport.as_uri()+'?mode=ro',uri=True)
        copied=sqlite3.connect(folder/'transport.sqlite3')
        try:original.backup(copied)
        finally:copied.close();original.close()
        checked=sqlite3.connect((folder/'transport.sqlite3').as_uri()+'?mode=ro&immutable=1',uri=True)
        try:
            assert checked.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            assert not checked.execute('PRAGMA foreign_key_check').fetchall()
        finally:checked.close()
    private=(ROOT/'data/autoapply-private').resolve()
    if any(not path.is_relative_to(private) or not path.name.endswith('.dpapi') for path in paths):raise ValueError('VAULT_ASSET_OUTSIDE_PROJECT')
    with zipfile.ZipFile(folder/'encrypted-vault.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(paths):archive.write(path,path.relative_to(ROOT))
    with zipfile.ZipFile(folder/'code-and-evidence.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for directory in ('corkjobradar','scripts','tests','docs','config'):
            for path in (ROOT/directory).rglob('*'):
                if path.is_file() and '__pycache__' not in path.parts:
                    if not path.resolve().is_relative_to(ROOT):raise ValueError('CODE_LINK_OUTSIDE_PROJECT')
                    archive.write(path,path.relative_to(ROOT))
        for name in ('app.py','README.md','PROGRESO.md','NEXT_STEPS.md','requirements-lock.txt','requirements-autoapply-lock.txt','instalar-autoapply.ps1','.streamlit/config.toml'):
            archive.write(ROOT/name,name)
        for pattern in ('operational-*','verified-flow-*','external-adapter-*','human-intervention-*','assisted-delivery-*','usable-it-*','it-50km-*','local-runtime-*','ui-redesign-*','dam-completed-*','academic-reevaluation-*','approved-cv-facts-import.json','pr23-*','reference-cv-*','pr2-windows-*','pr3-windows-*','pr1-cv-*'):
            for path in (ROOT/'logs').glob(pattern):
                if path.is_file():archive.write(path,path.relative_to(ROOT))
        for path in (ROOT/'data/runtime-logs').glob('*.log'):
            if path.is_file() and path.resolve().is_relative_to(ROOT):archive.write(path,path.relative_to(ROOT))
        for path in (ROOT/'data/ui-redesign').rglob('*.png'):
            if not path.resolve().is_relative_to(ROOT/'data/ui-redesign'):raise ValueError('UI_SCREENSHOT_OUTSIDE_PROJECT')
            archive.write(path,path.relative_to(ROOT))
        for path in (ROOT/'exports').glob('Oportunidades-IT-DAM-*.xlsx'):
            if not path.resolve().is_relative_to(ROOT/'exports'):raise ValueError('REPORT_OUTSIDE_PROJECT')
            archive.write(path,path.relative_to(ROOT))
        for path in (ROOT/'data/public-probes').glob('*'):
            if not path.is_file():continue
            if not path.resolve().is_relative_to(ROOT/'data/public-probes'):raise ValueError('PUBLIC_CAPTURE_OUTSIDE_PROJECT')
            archive.write(path,path.relative_to(ROOT))
        for path in (ROOT/'data/ats-reviews').glob('*.json'):
            if not path.resolve().is_relative_to(ROOT/'data/ats-reviews'):raise ValueError('ATS_REVIEW_OUTSIDE_PROJECT')
            archive.write(path,path.relative_to(ROOT))
    for filename in ('encrypted-vault.zip','code-and-evidence.zip'):
        with zipfile.ZipFile(folder/filename) as archive:assert archive.testzip() is None
    report={'created_at':now(),'path':str(folder.relative_to(ROOT)),'integrity':'ok','foreign_key_errors':0,'counts':counts,
            'encrypted_assets':len(paths),'plaintext_cv_files':0,'restored_over_production':False,'live_enabled':False,
            'hashes':{path.name:file_hash(path) for path in folder.iterdir() if path.is_file()}}
    (folder/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (ROOT/'logs'/args.report).write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__':main()
