"""Backfill metadata from existing HSE evidence; never claims a new network verification."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now
from corkjobradar.db import Database
from corkjobradar.deadlines import hse_deadline_fields
from corkjobradar.worker import worker_lock


def backfill(db,apply=False):
    report={'generated_at':now(),'applied':apply,'network_requests':0,'offers':[]}
    rows=db.rows("SELECT DISTINCT j.* FROM jobs j JOIN job_sources s ON s.job_id=j.id JOIN sources f ON f.id=s.source_id WHERE f.kind='hse'")
    changes=[]
    for job in rows:
        raw=json.loads(job['raw']);metadata=hse_deadline_fields(raw.get('published_fields',{}))
        if not metadata or all(raw.get(k)==v for k,v in metadata.items()):continue
        if raw.get('application_deadline') and raw['application_deadline']!=metadata.get('application_deadline'):
            report['offers'].append({'job_id':job['id'],'status':'CONFLICT_REQUIRES_REVIEW'});continue
        changes.append((job,raw,metadata))
        report['offers'].append({'job_id':job['id'],'status':'METADATA_FROM_SAVED_HSE_EVIDENCE',**metadata})
    if apply:
        with worker_lock(db),db.transaction() as con:
            if not con.in_transaction:con.execute('BEGIN IMMEDIATE')
            for job,raw,metadata in changes:
                current=db.rows('SELECT raw FROM jobs WHERE id=?',(job['id'],))[0]
                if current['raw']!=job['raw']:raise RuntimeError('SOURCE_CHANGED_RESTART_BACKFILL')
                raw.update(metadata)
                db.execute('UPDATE jobs SET raw=? WHERE id=?',(json.dumps(raw,ensure_ascii=False),job['id']))
                db.event('HSE_DEADLINE_METADATA_BACKFILLED',{'source':'published_fields saved previously','new_network_verification':False,**metadata},job_id=job['id'])
    report['updates']=len(changes)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    report=backfill(Database(),args.apply)
    (ROOT/'logs'/('continuity-hse-deadlines-applied.json' if args.apply else 'continuity-hse-deadlines-preview.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True,indent=2))
