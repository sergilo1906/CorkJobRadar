import json
import httpx
import pytest
from conftest import source,client
from corkjobradar.models import Job
from corkjobradar.worker import create_run,run_worker
from corkjobradar.repository import save_job
from corkjobradar.verification import reconcile_absences
from corkjobradar.audit import coverage
from corkjobradar.sources import upsert_source


def test_2003_offers_all_pages_and_low_scores_processed(db,profile):
    source(db,'lever','long','https://fixture.test/list',{'page_size':777})
    source(db,'greenhouse','copies','https://fixture.test/copies')
    total=2003;requests=[]
    def text(i):
        return ('SYNTHETIC TEST ONLY. Responsibilities\nMaintain computers, document incidents and assist users with technical issues. '
                'Coordinate support requests, diagnose hardware and software faults, install equipment and work with colleagues. '
                'This isolated test advert is not a real job.\nEssential requirements\n'+
                ('Minimum of 12 years experience required. Night shifts.' if i>1700 else 'No experience required. Full training provided. Monday to Friday.'))
    def handler(r):
        requests.append(str(r.url))
        if r.url.path=='/copies':
            return httpx.Response(200,json={'meta':{'total':50},'jobs':[{'id':i,'title':f'IT Support {i}',
                'company_name':'SYNTHETIC TEST ONLY','location':{'name':'Cork City'},
                'absolute_url':f'https://fixture.test/job/{i}','content':text(i)} for i in range(50)]})
        offset=int(r.url.params.get('skip',0))
        return httpx.Response(200,json=[{'id':str(i),'text':f'IT Support {i}','categories':{'location':'Cork City'},
            'hostedUrl':f'https://fixture.test/job/{i}','description':text(i)} for i in range(offset,min(offset+183,total))])
    rid=create_run(db)
    with client(profile,handler) as c:
        run_worker(db,rid,c)
    report=coverage(db,rid)
    assert report['reconciled'] and report['observed_postings']==2053 and report['unique_jobs']==2003
    assert report['analysis_groups']=={'basico_o_parcial':2003}
    assert len(db.rows('SELECT * FROM job_analyses'))==2003
    assert db.rows('SELECT pages_visited FROM source_runs WHERE source_id=?',('long',))[0]['pages_visited']==12
    assert not db.rows("SELECT 1 FROM task_queue WHERE status<>'done'")
    assert db.rows("SELECT status FROM scan_runs WHERE id=?",(rid,))[0]['status']=='completed'


def test_query_change_cannot_mark_old_publications_unlisted(db,profile):
    src=source(db,'greenhouse')
    rid=create_run(db)
    job=Job(external_id='1',title='IT Support',location='Cork City',url='https://fixture.test/1')
    save_job(db,'fixture',job,rid,profile)
    db.execute("UPDATE scan_runs SET status='completed' WHERE id=?",(rid,))
    src['url']='https://fixture.test/different-query';upsert_source(db,src)
    for _ in range(3):
        rid=create_run(db);reconcile_absences(db,rid,'fixture')
        db.execute("UPDATE scan_runs SET status='completed' WHERE id=?",(rid,))
    assert db.rows('SELECT open_status FROM jobs')[0]['open_status']!='UNLISTED'
    assert db.rows('SELECT missing_successes FROM job_sources')[0]['missing_successes']==0


def test_short_transaction_rolls_back_all_nested_writes(db):
    with pytest.raises(RuntimeError):
        with db.transaction():
            db.execute("INSERT INTO audit_events(created_at,kind,details) VALUES('test','rollback','{}')")
            with db.transaction():
                db.execute("INSERT INTO audit_events(created_at,kind,details) VALUES('test','nested','{}')")
            raise RuntimeError('SYNTHETIC rollback')
    assert not db.rows('SELECT * FROM audit_events')
