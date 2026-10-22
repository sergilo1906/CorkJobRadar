"""Check ALL local candidate links read-only, honoring robots and existing URL controls."""
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now,load_profile
from corkjobradar.db import Database
from corkjobradar.http import WebClient
from corkjobradar.verification import verify_job
from corkjobradar.ui.model import load_view
from corkjobradar.autoapply.selection_queue import refresh_queue
from corkjobradar.reevaluation import opportunity_report,report_markdown,report_excel


def main():
    output=ROOT/'logs/academic-reevaluation-live-links.json'
    if output.exists():raise ValueError('PRESERVE_EXISTING_LINK_REPORT')
    db=Database();rows=[j for j in load_view(db)['jobs'] if j['potential']]
    profile=load_profile();profile.update(http_timeout=15,http_retries=0)
    result=[]
    with WebClient(profile,db) as client:
        for job in rows:
            host=urlsplit(job.get('apply_url') or job['url']).hostname
            if host not in {'job-boards.greenhouse.io','job-boards.eu.greenhouse.io','jobs.solarwinds.com'}:
                result.append({'job_id':job['id'],'status':'HOLD','reason':'PUBLIC_READ_PERMISSION_REVIEW_REQUIRED'});continue
            status=verify_job(db,job['id'],client)
            result.append({'job_id':job['id'],'company':job['company'],'title':job['title'],'url':job.get('apply_url') or job['url'],'status':status})
    refresh_queue(db);report=opportunity_report(db)
    # Preserve the initial persisted report. This is the later link-checked version.
    (ROOT/'logs/academic-reevaluation-opportunities-link-checked.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    original=ROOT/'docs/OPORTUNIDADES_IT_DAM_2026-10-22.md'
    history=ROOT/'docs/history/academic-reevaluation';history.mkdir(parents=True,exist_ok=True)
    assert not (history/original.name).exists()
    (history/original.name).write_bytes(original.read_bytes())
    original.write_text(report_markdown(report),encoding='utf-8')
    initial=ROOT/'exports/Oportunidades-IT-DAM-2026-10-22.xlsx'
    prior=ROOT/'exports/Oportunidades-IT-DAM-2026-10-22-initial.xlsx'
    assert not prior.exists();prior.write_bytes(initial.read_bytes());initial.write_bytes(report_excel(report))
    proof={'checked_at':now(),'status':'COMPLETED_WITH_EXPLICIT_SOURCE_STATES','links_processed':len(result),'results':result,
        'opportunities_summary':{k:v for k,v in report.items() if k!='offers'},'methods':['GET','robots.txt'],
        'personal_data_sent':False,'applications_sent':0,'live_enabled':False}
    output.write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'links_processed':len(result),'states':[r['status'] for r in result],'summary':proof['opportunities_summary']}))


if __name__=='__main__':main()
