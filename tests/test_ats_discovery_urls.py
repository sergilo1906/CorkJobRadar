import pytest
from corkjobradar.sources import ats_endpoint,discover_ats


@pytest.mark.parametrize('target,kind,token,api',[
 ('https://job-boards.eu.greenhouse.io/globetech/jobs/4960319101','greenhouse','globetech','https://boards-api.greenhouse.io/v1/boards/globetech/jobs'),
 ('https://boards.greenhouse.io/embed/job_board?for=pulse','greenhouse','pulse','https://boards-api.greenhouse.io/v1/boards/pulse/jobs'),
 ('https://boards.greenhouse.io/embed/job_app?for=example&token=12345','greenhouse','example','https://boards-api.greenhouse.io/v1/boards/example/jobs'),
 ('https://jobs.eu.lever.co/company/job-id','lever','company','https://api.eu.lever.co/v0/postings/company'),
 ('https://jobs.ashbyhq.com/netgear/job-id','ashby','netgear','https://api.ashbyhq.com/posting-api/job-board/netgear'),
])
def test_explicit_identifiers_are_preserved(target,kind,token,api):
    assert ats_endpoint(target)=={'kind':kind,'token':token,'url':api}


@pytest.mark.parametrize('target',[
 'https://boards.greenhouse.io/embed/job_app?token=12345',
 'https://boards.greenhouse.io/embed/job_board?for=one&for=two',
 'https://evil.example/?next=https://jobs.lever.co/company',
 'https://jobs.lever.co.evil.example/company',
 'https://user:pass@jobs.lever.co/company',
 'https://jobs.ashbyhq.com/%2E%2E',
])
def test_ambiguous_or_untrusted_target_does_not_invent_an_ats(target):
    assert ats_endpoint(target) is None


def test_discovery_handles_eu_and_protocol_relative_iframe_without_duplicate(db):
    html='<iframe src="//boards.greenhouse.io/embed/job_board?for=pulse"></iframe><a href="https://job-boards.eu.greenhouse.io/globetech">Jobs</a>'
    items=discover_ats(db,'https://example.org/careers',None,html)
    assert len(items)==2 and all(not item['enabled'] for item in items)
    assert not discover_ats(db,'https://example.org/careers',None,html)
    assert {r['name'] for r in db.rows('SELECT name FROM sources')}=={'pulse','globetech'}
