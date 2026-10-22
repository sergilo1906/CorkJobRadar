"""Actual model evaluation on five stored real descriptions; keeps every result."""
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,load_profile,now
from corkjobradar.db import Database
from corkjobradar.local_model import local_server
from corkjobradar.analysis import analyze_job


db=Database();profile=load_profile();profile['analyzer']='llama'
titles=['Purchase To Pay Administrator - 12 month FTC','Production Administrator','Production Operator - 12 month FTC',
        'Localisation QA Engineer with English - Australian Market','Localisation QA Engineer with Danish']
if '--probe-one' in sys.argv:
    titles=titles[:1]  # Explicit model diagnostic scope; never a scan/production processing limit.
report={'started_at':now(),'jobs':[]}
try:
    runtime=ROOT/'data/local-model-gpu/runtime_config.json' if '--gpu' in sys.argv else None
    with local_server(runtime,evaluation=True) as info:
        report['runtime']=info
        print('Runtime started',info,flush=True)
        for title in titles:
            job=db.rows('SELECT id,title,company,url,description FROM jobs WHERE title=? AND detail_complete=1',(title,))
            if not job:
                report['jobs'].append({'title':title,'error':'Actual complete description unavailable'})
                continue
            job=job[0];start=time.monotonic()
            print('Analysing',job['id'],job['title'],flush=True)
            result=analyze_job(db,job['id'],profile)
            report['jobs'].append({'id':job['id'],'title':title,'url':job['url'],'seconds':round(time.monotonic()-start,2),'result':result})
            (ROOT/'logs/ultimate-local-model-evaluation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print('Recorded',result['depth'],result.get('semantic',{}).get('chunks_validated'),flush=True)
except Exception as exc:
    report['startup_error']=str(exc)
    raise
finally:
    report['finished_at']=now()
    (ROOT/'logs/ultimate-local-model-evaluation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
