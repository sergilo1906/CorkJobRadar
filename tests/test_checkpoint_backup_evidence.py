"""Backups retain encrypted CV and the current regression evidence, without PII."""
import hashlib
import json
import sys
import zipfile
from pathlib import Path
import pytest
from scripts import backup_operational_checkpoint as backup
from corkjobradar.db import Database
from corkjobradar.autoapply.documents import render_cv,create_cv_review
from corkjobradar.autoapply.vault import candidate_snapshot
from test_autoapply_vault import populate


def test_backup_includes_new_evidence_and_encrypted_assets_without_optional_probe_folder(tmp_path,monkeypatch):
    db=Database(tmp_path/'data/radar.sqlite3')
    populate(db)
    create_cv_review(db,render_cv(candidate_snapshot(db),'pdf'),'pdf')
    monkeypatch.setattr(backup,'ROOT',tmp_path)
    monkeypatch.setattr(backup,'Database',lambda:db)
    for name in ('app.py','README.md','PROGRESO.md','NEXT_STEPS.md','requirements-lock.txt',
                 'requirements-autoapply-lock.txt','instalar-autoapply.ps1','.streamlit/config.toml'):
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('SYNTHETIC',encoding='utf-8')
    logs=tmp_path/'logs';logs.mkdir()
    (logs/'pr23-regression.xml').write_text('<testsuite tests="1"/>',encoding='utf-8')
    (logs/'reference-cv-proof.json').write_text('{"synthetic":true}',encoding='utf-8')
    # No public-probes directory exists on a fresh installation.
    monkeypatch.setattr(sys,'argv',['backup','--label','synthetic','--report','pr23-synthetic.json'])
    backup.main()
    result=json.loads((logs/'pr23-synthetic.json').read_text())
    folder=tmp_path/result['path']
    assert result['integrity']=='ok' and result['encrypted_assets']==1
    assert result['counts']['job_analyses']==0
    assert result['counts']['manual_application_handoffs']==0
    for name,sha in result['hashes'].items():
        with (folder/name).open('rb') as stream:
            assert hashlib.file_digest(stream,'sha256').hexdigest()==sha
    with zipfile.ZipFile(folder/'code-and-evidence.zip') as archive:
        assert 'logs/pr23-regression.xml' in archive.namelist()
        assert 'logs/reference-cv-proof.json' in archive.namelist()
        assert not any(name.endswith(('.pdf','.docx')) for name in archive.namelist())
    with zipfile.ZipFile(folder/'encrypted-vault.zip') as archive:
        assert len(archive.namelist())==1
        assert archive.namelist()[0].endswith('.dpapi')
    with pytest.raises(ValueError,match='PRESERVE_EXISTING_BACKUP_REPORT'):
        backup.main()
