"""One locally evidenced normalization repair, then reuse/reanalyse and publish all results."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now
from corkjobradar.db import Database
from corkjobradar.reevaluation import repair_stored_ashby_modes,reevaluate_all,opportunity_report,report_markdown,report_excel
from corkjobradar.autoapply.selection_queue import refresh_queue


def main():
    output=ROOT/'logs/academic-reevaluation-ashby-normalization.json'
    if output.exists():raise ValueError('PRESERVE_PREVIOUS_REPAIR')
    assert (ROOT/'logs/academic-reevaluation-baseline-backup.json').exists()
    db=Database();changes=repair_stored_ashby_modes(db);reanalysis=reevaluate_all(db)
    assert reanalysis['all_stored_jobs_processed'] and not reanalysis['errors']
    refresh_queue(db);report=opportunity_report(db)
    (ROOT/'logs/academic-reevaluation-delivered-opportunities.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    original=ROOT/'docs/OPORTUNIDADES_IT_DAM_2026-10-22.md';saved=ROOT/'docs/history/academic-reevaluation/before-ashby-mode-correction.md'
    assert not saved.exists();saved.write_bytes(original.read_bytes());original.write_text(report_markdown(report),encoding='utf-8')
    excel=ROOT/'exports/Oportunidades-IT-DAM-2026-10-22.xlsx';saved_excel=ROOT/'exports/Oportunidades-IT-DAM-2026-10-22-before-ashby-mode-correction.xlsx'
    assert not saved_excel.exists();saved_excel.write_bytes(excel.read_bytes());excel.write_bytes(report_excel(report))
    result={'at':now(),'status':'PASS','changes':changes,'reanalysis':reanalysis,
        'summary':{k:v for k,v in report.items() if k not in {'offers','pending_it_reviews'}},
        'official_documentation':'https://developers.ashbyhq.com/docs/public-job-posting-api',
        'old_snapshots_and_analyses_retained':True,'fresh_source_observation_not_claimed':True,'live_enabled':False,'applications_sent':0}
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k not in {'changes','reanalysis'}}))


if __name__=='__main__':main()
