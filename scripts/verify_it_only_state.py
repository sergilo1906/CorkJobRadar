"""Read-only production audit against the backup made before the IT-only change."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now
from corkjobradar.db import Database
from corkjobradar.autoapply.engine import report


def main():
    backup=ROOT/'data/backups/before-it-only-2026-10-19T213521+0100/radar.sqlite3'
    if not backup.is_file():raise RuntimeError('IT_ONLY_BASELINE_BACKUP_MISSING')
    db=Database()
    evidence={'checked_at':now(),'backup':str(backup.relative_to(ROOT)),
              'restored_over_production':False,'history':{}}
    with db.read_snapshot() as view:
        view.rows('ATTACH DATABASE ? AS baseline',(str(backup),))
        for table in ('job_analyses','job_snapshots','verification_events','audit_events','user_actions',
                      'autoapply_policies','application_events','application_answers'):
            before=view.rows('SELECT COUNT(*) n FROM baseline.'+table)[0]['n']
            missing=view.rows('SELECT COUNT(*) n FROM (SELECT * FROM baseline.'+table+' EXCEPT SELECT * FROM main.'+table+')')[0]['n']
            evidence['history'][table]={'baseline_rows':before,'original_rows_missing_or_changed':missing}
        evidence['missing_original_job_ids']=view.rows('SELECT id FROM baseline.jobs EXCEPT SELECT id FROM main.jobs')
        evidence['plans']={
            'missing_original_ids':view.rows('SELECT id FROM baseline.application_plans EXCEPT SELECT id FROM main.application_plans'),
            'updated_rows':view.rows('SELECT COUNT(*) n FROM (SELECT * FROM baseline.application_plans EXCEPT SELECT * FROM main.application_plans)')[0]['n'],
            'meaning':'Plans are mutable evaluations. Recalculation updates reasons; immutable application_events retain the audit history.'}
        evidence['counts']={t:view.rows('SELECT COUNT(*) n FROM '+t)[0]['n'] for t in
                           ('jobs','job_analyses','sources','application_plans','application_attempts','candidate_facts','candidate_documents','user_actions')}
        evidence['integrity']=view.rows('PRAGMA main.integrity_check')
        evidence['foreign_keys']=view.rows('PRAGMA main.foreign_key_check')
        evidence['synthetic_jobs']=view.rows("SELECT COUNT(*) n FROM jobs WHERE json_extract(raw,'$._synthetic_fixture') IS NOT NULL")[0]['n']
    evidence['status']=report(db)
    evidence['all_original_history_preserved']=not evidence['missing_original_job_ids'] and not evidence['plans']['missing_original_ids'] and all(
        not row['original_rows_missing_or_changed'] for row in evidence['history'].values())
    (ROOT/'logs/it-only-production-state.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(evidence,ensure_ascii=True,indent=2))
    return 0 if evidence['all_original_history_preserved'] and not evidence['foreign_keys'] and not evidence['synthetic_jobs'] and not evidence['status']['live_submission_enabled'] else 2


if __name__=='__main__':raise SystemExit(main())
