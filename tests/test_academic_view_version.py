import json
from corkjobradar.analysis import analyze_job
from corkjobradar.autoapply.vault import approve_fact,candidate_snapshot
from corkjobradar.autoapply.academic import VERSION
from corkjobradar.config import now
from corkjobradar.ui.model import load_view
from scripts.update_dam_completed_20261022 import FIELD,COMPLETED
from test_usable_it_workspace import case


def test_list_does_not_count_an_older_academic_rules_version_as_current(db,profile):
    job=case(db,profile,'Completed IT qualification required.')
    approve_fact(db,FIELD,COMPLETED,'SYNTHETIC',True)
    current=analyze_job(db,job['id'],profile)
    assert load_view(db)['academic_reviewed']==1
    obsolete={**current,'academic_review':{**current['academic_review'],'version':'OBSOLETE_TEST_VERSION'}}
    db.execute('INSERT INTO job_analyses(job_id,content_hash,profile_hash,analyzer_version,status,result,created_at) VALUES(?,?,?,?,?,?,?)',
        (job['id'],job['content_hash'],'synthetic','obsolete-test','REVISIÓN_MANUAL',json.dumps(obsolete),now()))
    view=load_view(db)
    assert view['academic_reviewed']==0
    assert view['jobs'][0]['academic_review']['version']==VERSION
    assert not view['jobs'][0]['academic_current']
