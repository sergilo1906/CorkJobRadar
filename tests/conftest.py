import json
from pathlib import Path
import pytest
import httpx
from corkjobradar.config import load_profile
from corkjobradar.db import Database
from corkjobradar.http import WebClient
from corkjobradar.sources import upsert_source

FIXTURES = Path(__file__).parent/'fixtures'


@pytest.fixture(autouse=True)
def prohibit_unmocked_processes_in_apptest(request,monkeypatch):
    """UI widget tests mock launching; real process/browser tests use explicit owned fixtures."""
    name=request.node.name
    if name.startswith('test_ui_') or '_ui_' in name:
        # Configure only this project's isolated encrypted fixture before blocking
        # child processes. DPAPI setup legitimately needs whoami/icacls once.
        from corkjobradar.autoapply.vault import private_folder
        private_folder(request.getfixturevalue('db'))
        import subprocess
        def blocked(*args,**kwargs):raise AssertionError('APPTEST_MUST_NOT_LAUNCH_REAL_PROCESSES')
        monkeypatch.setattr(subprocess,'Popen',blocked)

@pytest.fixture
def db(tmp_path):
    return Database(tmp_path/'test.sqlite3')

@pytest.fixture
def profile():
    p = load_profile()
    p.update(http_retries=0,domain_interval_seconds=0,analyzer='basic')
    return p

def fixture(name):
    path = FIXTURES/name
    text = path.read_text(encoding='utf-8')
    return json.loads(text) if path.suffix=='.json' else text

def source(db,kind,sid='fixture',url='https://fixture.test/jobs',config=None):
    row = {'id':sid,'name':'SYNTHETIC TEST ONLY','kind':kind,'url':url,'enabled':True,
           'permission':'HTML_PUBLICO_REVISADO' if kind=='html' else 'PUBLIC_API_DOCUMENTADA','config':config or {}}
    upsert_source(db,row)
    return db.rows('SELECT * FROM sources WHERE id=?',(sid,))[0]

def client(profile,handler,db=None,sleep=lambda x:None):
    return WebClient(profile,db,httpx.MockTransport(handler),sleep,validator=lambda u:u)
