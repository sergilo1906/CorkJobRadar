"""Refresh the final queue/report after tested literal function fixes; two new GET checks only."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now,load_profile
from corkjobradar.db import Database
from corkjobradar.http import WebClient
from corkjobradar.verification import verify_job,deadline_state
from corkjobradar.autoapply.selection_queue import refresh_queue
from corkjobradar.reevaluation import opportunity_report,report_markdown,report_excel


def main():
    output=ROOT/'logs/academic-reevaluation-final-summary.json'
    if output.exists():raise ValueError('PRESERVE_EXISTING_FINAL_REPORT')
    db=Database();checks=[];profile=load_profile();profile.update(http_timeout=15,http_retries=0)
    with WebClient(profile,db) as client:
        for jid in ['fb5b2b77d6b64862a228f91134ce3564','e64e8c7ca90347ad87e4538474f6d81b']:
            row=db.rows('SELECT * FROM jobs WHERE id=?',(jid,))[0]
            checks.append({'job_id':jid,'company':row['company'],'title':row['title'],'url':row['url'],'status':verify_job(db,jid,client),'deadline':deadline_state(json.loads(row['raw']))})
    refresh_queue(db);report=opportunity_report(db)
    (ROOT/'logs/academic-reevaluation-final-opportunities.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    original=ROOT/'docs/OPORTUNIDADES_IT_DAM_2026-10-22.md'
    saved=ROOT/'docs/history/academic-reevaluation/after-first-links.md';assert not saved.exists();saved.write_bytes(original.read_bytes())
    original.write_text(report_markdown(report),encoding='utf-8')
    excel=ROOT/'exports/Oportunidades-IT-DAM-2026-10-22.xlsx'
    saved_excel=ROOT/'exports/Oportunidades-IT-DAM-2026-10-22-after-first-links.xlsx';assert not saved_excel.exists();saved_excel.write_bytes(excel.read_bytes());excel.write_bytes(report_excel(report))
    result={'checked_at':now(),'status':'PASS','new_role_read_only_checks':checks,
        'summary':{k:v for k,v in report.items() if k not in {'offers','pending_it_reviews'}},
        'pending_it_reviews':report['pending_it_reviews'],'live_enabled':False,'documents_prepared':0,'applications_sent':0}
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result))


if __name__=='__main__':main()
