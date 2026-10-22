"""Compare durable history to the recovery backup without restoring or rewriting either DB."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now
from corkjobradar.db import Database


def main():
    folder=ROOT/'data/backups/continuity-2026-10-19T193844+0100'
    candidates=list(folder.glob('*radar*.sqlite3'))
    if len(candidates)!=1:raise RuntimeError('Recovery backup identity must be unique')
    backup=candidates[0]
    history=('job_analyses','job_snapshots','verification_events','audit_events','user_actions',
             'autoapply_policies','application_events','application_answers')
    db=Database();report={'checked_at':now(),'backup':str(backup.relative_to(ROOT)),'restored_over_production':False,'history':{}}
    with db.read_snapshot() as view:
        view.rows('ATTACH DATABASE ? AS recovery',(str(backup),))
        for table in history:
            before=view.rows('SELECT COUNT(*) n FROM recovery.'+table)[0]['n']
            current=view.rows('SELECT COUNT(*) n FROM main.'+table)[0]['n']
            missing=view.rows('SELECT COUNT(*) n FROM (SELECT * FROM recovery.'+table+' EXCEPT SELECT * FROM main.'+table+')')[0]['n']
            report['history'][table]={'recovery_rows':before,'current_rows':current,'original_rows_missing_or_changed':missing}
        report['integrity']=view.rows('PRAGMA main.integrity_check')
        report['foreign_keys']=view.rows('PRAGMA main.foreign_key_check')
        report['current_counts']={t:view.rows('SELECT COUNT(*) n FROM '+t)[0]['n'] for t in ('jobs','sources','application_attempts','candidate_facts','candidate_documents','user_actions')}
        report['synthetic_job_markers']=view.rows("SELECT COUNT(*) n FROM jobs WHERE json_extract(raw,'$._synthetic_fixture') IS NOT NULL")[0]['n']
    report['all_original_history_preserved']=all(not r['original_rows_missing_or_changed'] for r in report['history'].values())
    (ROOT/'logs/continuity-data-preservation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True,indent=2))
    return 0 if report['all_original_history_preserved'] and not report['foreign_keys'] and not report['synthetic_job_markers'] else 2


if __name__=='__main__':raise SystemExit(main())
