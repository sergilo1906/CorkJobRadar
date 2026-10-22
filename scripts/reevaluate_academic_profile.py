"""Reanalyse every retained record, preserve history, publish complete IT opportunities."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now
from corkjobradar.db import Database
from corkjobradar.reevaluation import reevaluate_all,opportunity_report,report_markdown,report_excel
from corkjobradar.autoapply.selection_queue import refresh_queue
from corkjobradar.autoapply.academic import assessment
from corkjobradar.autoapply.vault import candidate_snapshot,protect


def main():
    output=ROOT/'logs/academic-reevaluation-result.json'
    if output.exists():raise ValueError('PRESERVE_EXISTING_REPORT')
    baseline=json.loads((ROOT/'logs/academic-reevaluation-baseline-backup.json').read_text(encoding='utf-8'))
    assert baseline['integrity']=='ok'
    db=Database();candidate=candidate_snapshot(db)
    assert not candidate.get('cv_document_id'),'CV_APPROVAL_STATE_CHANGED_REVIEW_BEFORE_DELIVERY'
    # Historical fact is used ONLY for an explicitly labelled counterfactual comparison.
    # Never restore it, approve it again, or describe this computation as a past decision.
    past=db.rows("SELECT id,encrypted_value FROM candidate_facts WHERE field='claim:cv_dam_ongoing' AND revoked_at IS NOT NULL ORDER BY id DESC LIMIT 1")
    comparison=[];previous_assessments=db.rows('SELECT assessment FROM it_application_queue')
    known_codes={'DAM_PENDING','DAM_ONGOING','DAM_INCOMPLETE','EDUCATION_DAM_PENDING'}
    recorded_holds=sum(bool(known_codes.intersection(json.loads(r['assessment']).get('exclusions',[])+json.loads(r['assessment']).get('essential_pending',[]))) for r in previous_assessments)
    if past:
        historical=json.loads(protect(past[0]['encrypted_value'],decrypt=True))['value']
        previous={**candidate,'_claims':[{**c,**historical,'id':past[0]['id']} if 'Multiplatform Application Development' in c['text_en'] and c['section']=='Education' else c for c in candidate['_claims']]}
        for job in db.rows('SELECT * FROM jobs ORDER BY id'):
            before=assessment(job,previous);after=assessment(job,candidate)
            changes=[{'quote':a['quote'],'before_status':b['status'],'after_status':a['status'],'before_code':b['code'],'after_code':a['code']} for b,a in zip(before['items'],after['items']) if (b['status'],b['code'])!=(a['status'],a['code'])]
            if changes:comparison.append({'job_id':job['id'],'company':job['company'],'title':job['title'],'changes':changes})
    result=reevaluate_all(db)
    if not result['all_stored_jobs_processed'] or result['errors']:raise RuntimeError('INCOMPLETE_REEVALUATION_RESULTS_RETAINED')
    queue=refresh_queue(db);report=opportunity_report(db)
    result.update(queue_jobs=queue['jobs_processed'],preexisting_explicit_dam_holds=recorded_holds,
        counterfactual_comparison_not_historical_decisions=comparison,
        newly_satisfied_academic_requirements=sum(c['after_status']=='CUMPLIDO' and c['before_status']!='CUMPLIDO' for r in comparison for c in r['changes']),
        opportunities={k:v for k,v in report.items() if k!='offers'},status='PASS')
    (ROOT/'logs/academic-reevaluation-opportunities.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'docs/OPORTUNIDADES_IT_DAM_2026-10-22.md').write_text(report_markdown(report),encoding='utf-8')
    (ROOT/'exports/Oportunidades-IT-DAM-2026-10-22.xlsx').write_bytes(report_excel(report))
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in {'processed_job_ids','counterfactual_comparison_not_historical_decisions'}}))


if __name__=='__main__':main()
