"""Evaluate existing local GPU model against real adverts in a separate database copy."""
import json
from pathlib import Path
import sqlite3
import sys
from datetime import datetime
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now
from corkjobradar.db import Database
from corkjobradar.local_model import local_server
from corkjobradar.translation import translate_job


def main():
    stamp=now().replace(':','');destination=ROOT/'data'/('translation-evaluation-'+stamp+'.sqlite3')
    with sqlite3.connect((ROOT/'data/radar.sqlite3').as_uri()+'?mode=ro',uri=True) as src,sqlite3.connect(destination) as dst:src.backup(dst)
    db=Database(destination)
    titles=['Purchase To Pay Administrator - 12 month FTC','Production Administrator','Production Operator - 12 month FTC',
            'Localisation QA Engineer with English - Australian Market','Localisation QA Engineer with Danish']
    report={'started_at':now(),'evaluation_database':str(destination),'jobs':[],'live_submissions':False}
    path=ROOT/'logs'/('translation-evaluation-'+stamp+'.json')
    try:
        with local_server(ROOT/'data/local-model-gpu/runtime_config.json',evaluation=True) as runtime:
            report['runtime']=runtime
            for title in titles:
                job=db.rows('SELECT * FROM jobs WHERE title=? AND detail_complete=1 LIMIT 1',(title,))[0]
                print('TRANSLATING',job['id'],title,flush=True)
                result=translate_job(db,job)
                report['jobs'].append({'job_id':job['id'],'title':title,'source':job['url'],'semantic':result})
                path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
                print('RECORDED',result['passages_translated'],'/',result['passages_total'],'ERRORS',len(result['errors']),'SECONDS',result['seconds'],flush=True)
    finally:
        report['finished_at']=now();path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        (ROOT/'logs/translation-evaluation-latest.json').write_text(json.dumps({'report':str(path)},indent=2),encoding='utf-8')
        print('REPORT',path,flush=True)


if __name__=='__main__':main()
