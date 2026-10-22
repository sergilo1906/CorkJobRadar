import httpx
from conftest import client, source
from corkjobradar.discovery import start_discovery,resume_discovery,diagnose_omission
from corkjobradar.models import Job
from corkjobradar.repository import save_job
from corkjobradar.worker import create_run


def test_sitemap_feed_resume_all_candidates_and_no_live_jobs(db,profile):
    responses={
        '/careers':'<a href="https://jobs.lever.co/example">Careers</a><link type="application/rss+xml" href="/feed.xml">',
        '/robots.txt':'User-agent: *\nSitemap: https://fixture.test/index.xml',
        '/index.xml':'<sitemapindex><sitemap><loc>https://fixture.test/jobs.xml</loc></sitemap></sitemapindex>',
        '/jobs.xml':'<urlset>'+''.join(f'<url><loc>https://fixture.test/jobs/{i}</loc></url>' for i in range(1203))+'</urlset>',
        '/feed.xml':'<rss><channel><item><title>Fixture advert</title><link>https://fixture.test/jobs/rss</link></item></channel></rss>'}
    c=client(profile,lambda r:httpx.Response(200,text=responses[r.url.path]))
    rid=start_discovery(db,'https://fixture.test/careers')
    first=resume_discovery(db,rid,c,max_pages=1)
    assert first['status']=='partial'
    final=resume_discovery(db,rid,c)
    assert final['status']=='completed' and final['candidates']==1205
    assert not db.rows('SELECT * FROM jobs')  # URLs candidates are not invented jobs.
    assert db.rows('SELECT enabled FROM sources')[0]['enabled']==0
    assert resume_discovery(db,rid,c)['candidates']==1205


def test_blocked_resources_remain_auditable(db,profile):
    c=client(profile,lambda r:httpx.Response(200,text='User-agent: *\nDisallow: /private'))
    rid=start_discovery(db,'https://fixture.test/private')
    assert resume_discovery(db,rid,c)['status']=='partial'
    assert db.rows("SELECT status FROM discovery_resources WHERE url LIKE '%private'")[0]['status']=='blocked'


def test_omission_explains_existing_out_of_scope_record(db,profile):
    source(db,'html')
    save_job(db,'fixture',Job(external_id='1',title='Warehouse',location='Dublin',url='https://fixture.test/a?utm_source=test'),profile=profile)
    report=diagnose_omission(db,'https://fixture.test/a')
    causes={f['cause'] for f in report['findings']}
    assert {'YA_CONSERVADA','ARCHIVADA_POR_ALCANCE','FUENTE_SIN_BUSQUEDA'}<=causes
    assert 'CAUSA_EXACTA_NO_DETERMINADA' not in causes


def test_listing_detail_roundtrip_not_reported_as_change(db,profile):
    source(db,'html')
    full=Job(external_id='1',title='IT Support',location='Cork City office',url='https://fixture.test/a',description='Full text',detail_complete=True)
    save_job(db,'fixture',full,profile=profile)
    rid=create_run(db)
    card=full.model_copy(update={'location':'Cork','description':'','detail_complete':False})
    save_job(db,'fixture',card,rid,profile)
    save_job(db,'fixture',full,rid,profile)
    assert db.rows('SELECT change_status FROM run_jobs')[0]['change_status']=='REPEATED'
