import pytest
from corkjobradar.autoapply.hosted_probe import allowed_probe_get

SOURCE='https://job-boards.greenhouse.io/synthetic/jobs/321'


@pytest.mark.parametrize('url,method,allowed',[
    (SOURCE,'GET',True),(SOURCE,'POST',False),
    ('https://job-boards.greenhouse.io/robots.txt','GET',True),
    ('https://job-boards.greenhouse.io/_next/static/123/app.js','GET',True),
    ('https://boards-api.greenhouse.io/v1/boards/synthetic/jobs/321?questions=true','GET',True),
    ('https://boards-api.greenhouse.io/v1/boards/another/jobs/321','GET',False),
    ('https://job-boards.greenhouse.io/api/applications','GET',False),
    ('https://evil.invalid/collect','GET',False),('http://127.0.0.1/','GET',False),
    (SOURCE+'?email=synthetic@example.invalid','GET',False),
    ('https://job-boards.greenhouse.io:8443/synthetic/jobs/321','GET',False),
])
def test_hosted_probe_cannot_fill_submit_or_send_query_data(url,method,allowed):
    assert allowed_probe_get(url,SOURCE,method) is allowed
