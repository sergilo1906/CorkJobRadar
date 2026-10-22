"""Reproduce inspection regressions from captured public pages, without Internet or PII."""
import hashlib
import json
from pathlib import Path
import sys
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,load_profile,now
from corkjobradar.http import WebClient
from corkjobradar.autoapply.forms import greenhouse_fields,inspect_lever


def main():
    folder=ROOT/'tests/fixtures/autoapply'
    schema=json.loads((folder/'greenhouse-keeper-public-20261020.json').read_text(encoding='utf-8'))
    fields,blockers=greenhouse_fields(schema)
    assert schema['provenance']['real_public_source'] and not schema['provenance']['submission_tested']
    assert any(f['label']=='LinkedIn Profile' and f['required'] for f in fields)
    assert any('2+ years' in f['label'] and f['required'] for f in fields)
    assert any('sponsorship' in f['label'].lower() and f['required'] for f in fields)
    html=(folder/'lever-public-20261020.html').read_bytes()
    provenance=json.loads((folder/'lever-public-20261020.provenance.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(html).hexdigest()==provenance['sha256']
    requests=[]
    def handler(request):
        requests.append(request.method)
        return httpx.Response(200,text='User-agent: *\nAllow: /') if request.url.path=='/robots.txt' else httpx.Response(200,content=html)
    profile=load_profile();profile.update(http_retries=0,domain_interval_seconds=0)
    with WebClient(profile,transport=httpx.MockTransport(handler),sleep=lambda _:None,validator=lambda url:url) as client:
        lever=inspect_lever(provenance['url'],client)
    assert 'CAPTCHA_MFA_OR_ACCESS_BLOCK' in lever['blockers']
    assert set(requests)=={'GET'} and not lever['submitted']
    report={'checked_at':now(),'mode':'CAPTURED_PUBLIC_SOURCES_REPLAYED_OFFLINE','greenhouse_fields':len(fields),
            'greenhouse_blockers':blockers,'mandatory_linkedin_verified':True,'mandatory_experience_question_preserved':True,
            'lever_fields':len(lever['fields']),'lever_captcha_retained':True,'external_requests':0,'submissions':0,
            'hosted_form_completion_tested':False,'personal_data_used':False}
    (ROOT/'logs/operational-source-regressions.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__':main()
