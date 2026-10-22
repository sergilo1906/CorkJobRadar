"""Append corrected reading versions; original model responses and job history remain intact."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now
from corkjobradar.db import Database
from corkjobradar.reading_qa import reviewed_analysis,QA_VERSION


def apply_corrections(db):
    changed=[]
    with db.transaction() as con:
        if not con.in_transaction:con.execute('BEGIN IMMEDIATE')
        rows=db.rows('''SELECT a.* FROM job_analyses a WHERE a.id=(SELECT MAX(b.id) FROM job_analyses b
            WHERE b.job_id=a.job_id AND COALESCE(json_extract(b.result,'$.model_validation'),'') NOT IN ('RECHAZADO','EN_EVALUACION'))''')
        for row in rows:
            before=json.loads(row['result']);after=reviewed_analysis(before)
            old=before.get('semantic',{});new=after.get('semantic',{})
            if old.get('items')==new.get('items') and old.get('errors')==new.get('errors'):continue
            job=db.rows('SELECT content_hash FROM jobs WHERE id=?',(row['job_id'],))[0]
            if job['content_hash']!=row['content_hash']:continue
            version=row['analyzer_version']+':'+QA_VERSION+':'+str(row['id'])
            status='PENDIENTE_PROFUNDO' if new.get('errors') else 'REVISIÓN_MANUAL'
            if after.get('manual_review'):after['previous_manual_review']=after.pop('manual_review')
            after.update(analyzer_version=version,analysis_completeness=status)
            aid=db.execute('INSERT INTO job_analyses(job_id,content_hash,profile_hash,analyzer_version,status,result,created_at) VALUES(?,?,?,?,?,?,?)',
                (row['job_id'],row['content_hash'],row['profile_hash'],version,status,json.dumps(after,ensure_ascii=False),now()))
            db.execute('UPDATE jobs SET analysis_status=? WHERE id=?',(status,row['job_id']))
            event={'previous_analysis_id':row['id'],'analysis_id':aid,'qa_version':QA_VERSION,
                   'corrections':new.get('passages_from_reviewed_corrections',0),'requires_review':True}
            db.event('READING_LITERAL_REVIEW',event,job_id=row['job_id']);changed.append(event)
    return {'checked_at':now(),'changed_readings':changed,'original_versions_preserved':True,'live_enabled':False}


if __name__=='__main__':
    report=apply_corrections(Database())
    (ROOT/'logs/continuity-reading-corrections.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True))
