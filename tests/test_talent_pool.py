from corkjobradar.models import Job
from corkjobradar.repository import save_job
from corkjobradar.verification import verify_job,evidence_status
from corkjobradar.analysis import analyze_job
from conftest import source,client

def test_talent_form_does_not_imply_real_vacancy(db,profile):
    source(db,'greenhouse')
    job=Job(external_id='pool',title='Register your C.V. for upcoming positions',url='https://fixture.test/pool',
            location='Cork',description='Synthetic talent pool. '+('Future expressions of interest, not a concrete job. '*10),detail_complete=True)
    jid=save_job(db,'fixture',job,profile=profile)
    with client(profile,lambda r:(_ for _ in ()).throw(AssertionError('Must not fetch form'))) as c:
        assert verify_job(db,jid,c)=='UNKNOWN'
    assert 'bolsa de talento' in analyze_job(db,jid,profile)['summary_es'].lower()
