import json
import pytest
from corkjobradar.adapters import Ashby
from corkjobradar.repository import save_job
from corkjobradar.analysis import analyze_job
from corkjobradar.reevaluation import repair_stored_ashby_modes,reevaluate_all
from conftest import source


@pytest.mark.parametrize('workplace,flag,mode',[('Hybrid',True,'HYBRID'),('OnSite',True,'ONSITE'),('Remote',True,'REMOTE'),(None,True,'REMOTE'),(None,False,'DESCONOCIDO')])
def test_explicit_ashby_workplace_enum_precedes_coarse_remote_flag(db,profile,workplace,flag,mode):
    s=source(db,'ashby');adapter=Ashby(s,None,profile)
    raw={'id':'synthetic','title':'SYNTHETIC IT Support','location':'Cork','jobUrl':'https://fixture.test/synthetic','descriptionPlain':'Provide IT support for Windows computers.','isRemote':flag,'workplaceType':workplace}
    assert adapter.normalize(raw).mode==mode


def test_stored_mode_repair_retains_snapshots_analyses_source_data_and_observation_times(db,profile):
    s=source(db,'ashby');adapter=Ashby(s,None,profile)
    raw={'id':'synthetic','title':'SYNTHETIC IT Support','location':'Cork','jobUrl':'https://fixture.test/synthetic','descriptionPlain':'Provide IT support for Windows computers. '*20,'isRemote':True,'workplaceType':'Hybrid'}
    old=adapter.normalize(raw).model_copy(update={'mode':'REMOTE'})
    jid=save_job(db,s['id'],old,profile=profile);analyze_job(db,jid,profile)
    before=db.rows('SELECT * FROM jobs')[0];analyses=db.rows('SELECT * FROM job_analyses');snapshots=db.rows('SELECT * FROM job_snapshots')
    changed=repair_stored_ashby_modes(db)
    assert len(changed)==1
    after=db.rows('SELECT * FROM jobs')[0]
    assert after['mode']=='HYBRID' and after['content_hash']!=before['content_hash']
    for key in ('raw','description','last_seen_at','last_verified_at','first_seen_at'):assert before[key]==after[key]
    for r in snapshots:assert db.rows('SELECT * FROM job_snapshots WHERE id=?',(r['id'],))[0]==r
    for r in analyses:assert db.rows('SELECT * FROM job_analyses WHERE id=?',(r['id'],))[0]==r
    assert not repair_stored_ashby_modes(db)
    result=reevaluate_all(db);assert result['new_analyses']==1
    assert len(db.rows('SELECT * FROM job_analyses'))==2
    assert not db.rows('SELECT * FROM application_attempts')
