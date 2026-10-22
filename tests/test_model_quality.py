import json
import pytest
from conftest import source
from corkjobradar.models import Job
from corkjobradar.repository import save_job,latest_analyses
from corkjobradar.analysis import analyze_job
from corkjobradar.config import now


def test_rejected_output_preserved_without_overriding_documentary_result(db,profile):
    source(db,'html')
    jid=save_job(db,'fixture',Job(external_id='quality',title='IT Support',location='Cork City',url='https://fixture.test/q'),profile=profile)
    basic=analyze_job(db,jid,profile)
    row=db.rows('SELECT * FROM job_analyses')[0]
    rejected={'model_validation':'RECHAZADO','summary_es':'SYNTHETIC WRONG OUTPUT','semantic':{'rejected_items':[]}}
    db.execute('INSERT INTO job_analyses(job_id,content_hash,profile_hash,analyzer_version,status,result,created_at) VALUES(?,?,?,?,?,?,?)',
               (jid,row['content_hash'],row['profile_hash'],'test-rejected','REVISIÓN_MANUAL',json.dumps(rejected),now()))
    assert latest_analyses(db)[jid]['summary_es']==basic['summary_es']
    assert len(db.rows('SELECT * FROM job_analyses'))==2


def test_unvalidated_model_never_starts_a_process(tmp_path,monkeypatch):
    import corkjobradar.local_model as local
    folder=tmp_path/'data/local-model';(folder/'runtime').mkdir(parents=True)
    (folder/'runtime/llama-server.exe').touch();(folder/'qwen2.5-1.5b-instruct-q4_k_m.gguf').touch()
    (folder/'manifest.json').write_text('{}')
    monkeypatch.setattr(local,'ROOT',tmp_path)
    monkeypatch.setattr(local,'model_quality',lambda _: 'RECHAZADO')
    monkeypatch.setattr(local.subprocess,'Popen',lambda *a,**k:pytest.fail('Unvalidated model must not be launched'))
    with pytest.raises(RuntimeError,match='validación semántica'):
        with local.local_server():
            pytest.fail('Unvalidated runtime entered')
