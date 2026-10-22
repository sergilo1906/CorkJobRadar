import json
import pytest
from conftest import source
from corkjobradar.config import now
from corkjobradar.models import Job
from corkjobradar.repository import save_job
from corkjobradar.reviews import approve_analysis


def draft(db,profile,validated=True):
    source(db,'html')
    jid=save_job(db,'fixture',Job(external_id='review',title='IT Support',location='Cork City',url='https://fixture.test/review',description='SYNTHETIC ONLY. '*50,detail_complete=True),profile=profile)
    job=db.rows('SELECT * FROM jobs WHERE id=?',(jid,))[0]
    result={'model_validation':'VALIDADO_MUESTRA_LIMITADA' if validated else 'RECHAZADO',
            'semantic':{'items':[{'field':'duties','quote':'SYNTHETIC ONLY.'}],'errors':[]},
            'facts':{'salary':{'value':None}},'analysis_completeness':'REVISIÓN_MANUAL','analyzer_version':'test'}
    aid=db.execute('INSERT INTO job_analyses(job_id,content_hash,profile_hash,analyzer_version,status,result,created_at) VALUES(?,?,?,?,?,?,?)',
                   (jid,job['content_hash'],'test','test','REVISIÓN_MANUAL',json.dumps(result),now()))
    return jid,aid


def test_manual_review_retains_prior_analysis_and_unknown_salary(db,profile):
    jid,aid=draft(db,profile)
    new=approve_analysis(db,jid,aid,'SYNTHETIC human review for isolated test')
    assert new!=aid and len(db.rows('SELECT * FROM job_analyses'))==2
    result=json.loads(db.rows('SELECT result FROM job_analyses WHERE id=?',(new,))[0]['result'])
    assert result['analysis_completeness']=='COMPLETO' and result['facts']['salary']['value'] is None
    assert db.rows("SELECT kind FROM audit_events")[0]['kind']=='ANALYSIS_REVIEWED'


def test_review_rejects_unvalidated_or_changed_content(db,profile):
    jid,aid=draft(db,profile,False)
    with pytest.raises(ValueError,match='borrador'):
        approve_analysis(db,jid,aid,'SYNTHETIC note')
    db.execute("UPDATE jobs SET content_hash='changed' WHERE id=?",(jid,))
    with pytest.raises(ValueError,match='cambió'):
        approve_analysis(db,jid,aid,'SYNTHETIC note')
    assert len(db.rows('SELECT * FROM job_analyses'))==1
