"""Real public GET cycle via supervisor, isolated copy; no external application."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now
from corkjobradar.db import Database
from corkjobradar import runtime as rt


def main():
    output=ROOT/'logs/local-runtime-real-scan.json'
    if output.exists():raise FileExistsError('PRESERVE_PREVIOUS_REAL_RUN')
    source=Database();critical=['jobs','candidate_facts','candidate_documents','autoapply_control','autoapply_policies','application_attempts','user_actions']
    def signatures():return {t:hashlib.sha256(repr(source.rows('SELECT * FROM '+t+' ORDER BY rowid')).encode()).hexdigest() for t in critical}
    before=signatures();folder=ROOT/'data/runtime-validation'/('real-'+now().replace(':','')+'-'+uuid4().hex[:6]);folder.mkdir(parents=True)
    target=folder/'radar.sqlite3'
    with sqlite3.connect(source.path) as original,sqlite3.connect(target) as copied:original.backup(copied)
    db=Database(target)
    rt.update(db,desired='STOPPED',supervisor_pid=None,supervisor_stamp=None,child_pid=None,child_stamp=None,active_run=None,resume_run=None,launch_after=None,last_prepare_fingerprint=None)
    rt.command(db,'START');first=db.rows('SELECT coalesce(max(id),0) n FROM scan_runs')[0]['n']
    try:
        assert rt.ensure_supervisor(db)
        deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            row=rt.state(db)
            if row['last_search_run'] and row['last_search_run']>first and not row['child_pid']:break
            if row['last_error_code']:raise RuntimeError('REAL_READ_CYCLE_ERROR:'+row['last_error_code'])
            time.sleep(.5)
        else:raise TimeoutError('REAL_READ_CYCLE_TIMEOUT')
        rid=row['last_search_run'];run=db.rows('SELECT id,status,started_at,finished_at FROM scan_runs WHERE id=?',(rid,))[0]
        sources=db.rows('SELECT source_id,status,pages_visited,expected_total,observed,pagination_complete FROM source_runs WHERE run_id=?',(rid,))
        report={'checked_at':now(),'database_copy':str(target.relative_to(ROOT)),'real_public_get':True,'supervisor_process':True,
                'run':run,'sources':sources,'tasks':db.rows('SELECT kind,status,count(*) n FROM task_queue WHERE run_id=? GROUP BY kind,status',(rid,)),
                'jobs_in_copy':db.rows('SELECT count(*) n FROM jobs')[0]['n'],'facts':db.rows('SELECT count(*) n FROM candidate_facts WHERE revoked_at IS NULL')[0]['n'],
                'original_critical_tables_unchanged':before==signatures(),'approved_cv':db.rows('SELECT count(*) n FROM candidate_documents WHERE approved_at IS NOT NULL AND revoked_at IS NULL')[0]['n'],
                'application_attempts':db.rows('SELECT count(*) n FROM application_attempts')[0]['n'],'external_application_posts':0,'live_enabled':False,
                'integrity':db.rows('PRAGMA integrity_check')[0]['integrity_check'],'foreign_key_errors':len(db.rows('PRAGMA foreign_key_check'))}
        assert report['original_critical_tables_unchanged'] and report['facts']==22 and report['application_attempts']==0
        output.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
    finally:
        rt.command(db,'STOP');deadline=time.monotonic()+30
        while not rt.lock_free(db,'.runtime.lock') and time.monotonic()<deadline:time.sleep(.2)
        assert rt.lock_free(db,'.runtime.lock')


if __name__=='__main__':main()
