"""Read a single real stored HSE page without touching application controls or attachments."""
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bs4 import BeautifulSoup
from corkjobradar.config import ROOT,now,load_profile
from corkjobradar.db import Database
from corkjobradar.http import WebClient
from corkjobradar.deadlines import hse_deadline_fields
from corkjobradar.verification import deadline_state


def main():
    db=Database()
    jobs=db.rows("SELECT j.id,j.url,j.title FROM jobs j JOIN job_sources s ON s.job_id=j.id JOIN sources f ON f.id=s.source_id WHERE f.kind='hse' ORDER BY j.id LIMIT 1")
    report={'checked_at':now(),'read_only':True,'candidate_data_sent':False,'attachments_requested':False}
    if not jobs:report['status']='NO_STORED_HSE_JOB'
    else:
        job=jobs[0];report.update(job_id=job['id'],url=job['url'],title=job['title'])
        try:
            with WebClient(load_profile()) as client:response=client.get(job['url'],check_robots=True,accept='text/html')
            soup=BeautifulSoup(response.text,'lxml');closing=None
            for heading in soup.select('main h2'):
                if heading.get_text(' ',strip=True).casefold()!='closing date':continue
                values=[]
                for sibling in heading.next_siblings:
                    if getattr(sibling,'name',None)=='h2':break
                    if getattr(sibling,'get_text',None):values.append(sibling.get_text(' ',strip=True))
                closing='\n'.join(values);break
            metadata=hse_deadline_fields({'Closing date':closing})
            report.update(status='PUBLISHED_DEADLINE_READ' if metadata else 'DEADLINE_NOT_FOUND',http_status=response.status_code,
                          final_url=str(response.url),body_sha256=hashlib.sha256(response.content).hexdigest(),
                          metadata=metadata,deadline_state=deadline_state(metadata))
        except Exception as exc:
            report.update(status='BLOCKED_OR_UNAVAILABLE',error_type=type(exc).__name__,reason=str(exc)[:500])
    (ROOT/'logs/continuity-hse-deadline-live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True,indent=2))


if __name__=='__main__':main()
