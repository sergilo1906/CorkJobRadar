"""Reclassify every production record locally, no HTTP or application submission."""
import json
import sys
import re
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now
from corkjobradar.db import Database
from corkjobradar.autoapply.selection_queue import refresh_queue,queue_summary


def main(report_stem='it-50km-inventory'):
    if not re.fullmatch('it-50km-[a-z0-9-]+',report_stem):raise ValueError('SAFE_LOCAL_REPORT_NAME_REQUIRED')
    path=ROOT/'logs'/(report_stem+'.json');summary_path=ROOT/'logs'/(report_stem+'-summary.json')
    if path.exists() or summary_path.exists():raise FileExistsError('PRESERVE_PRIOR_INVENTORY')
    db=Database();report=refresh_queue(db)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    summary={k:v for k,v in report.items() if k!='offers'}
    summary['geography_states']=dict(Counter(r['geography']['state'] for r in report['offers']))
    summary['exclusion_codes']=dict(Counter(code for r in report['offers'] for code in r['exclusions']))
    summary['essential_pending_codes']=dict(Counter(code for r in report['offers'] for code in r['essential_pending']))
    summary['it_preparable_after_cv_approval']=sum(r['preparation_allowed'] for r in report['offers'])
    summary['it_excluded_minimum_over3']=sum(r['it_status']=='CONFIRMED_IT' and 'MANDATORY_MINIMUM_EXPERIENCE_OVER_3' in r['exclusions'] for r in report['offers'])
    summary['queue']=queue_summary(db)
    summary['facts_approved']=db.rows('SELECT count(*) n FROM candidate_facts WHERE revoked_at IS NULL')[0]['n']
    summary['production_schema']=db.rows('PRAGMA user_version')[0]['user_version']
    summary['external_requests']=summary['submitted']=0
    summary_path.write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary))


if __name__=='__main__':main()
