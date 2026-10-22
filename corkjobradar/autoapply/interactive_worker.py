"""Single-owner visible Playwright session; commands survive Streamlit reruns."""
import argparse
import os
import time
from pathlib import Path
from ..config import ROOT,now
from ..db import Database
from .human_sessions import session_lock,session_row,update_session,EXPIRED,TERMINAL
from .interactive_browser import InteractiveBrowser


def run(db,sid,*,headless=False,_max_seconds=1800):
    with session_lock(db,sid),InteractiveBrowser(db,sid,headless=headless) as actor:
        db.execute('UPDATE autoapply_interventions SET worker_pid=?,heartbeat=? WHERE id=?',(os.getpid(),now(),sid))
        started=time.monotonic()
        try:
            while time.monotonic()-started<_max_seconds:
                row=session_row(db,sid)
                db.execute('UPDATE autoapply_interventions SET heartbeat=? WHERE id=?',(now(),sid))
                commands=db.rows("SELECT * FROM autoapply_intervention_commands WHERE session_id=? AND status='PENDING' ORDER BY id LIMIT 1",(sid,))
                if commands:
                    command=commands[0];action=command['command']
                    # Consume before acting: a crashed Continue can never replay.
                    db.execute("UPDATE autoapply_intervention_commands SET status='RUNNING' WHERE id=?",(command['id'],))
                    try:
                        if action=='CLOSE':
                            update_session(db,sid,'CERRADA','USER_CLOSED_BROWSER','RECONSTRUIR_CAMPOS_Y_VERIFICACION')
                        else:
                            {'OPEN':actor.open,'CONTINUE':actor.continue_after_human,'RECOVER':actor.recover,'FOCUS':actor.focus}[action]()
                        db.execute("UPDATE autoapply_intervention_commands SET status='DONE',processed_at=? WHERE id=?",(now(),command['id']))
                    except Exception:
                        current=session_row(db,sid)
                        if current['status'] not in TERMINAL:
                            update_session(db,sid,'ENVIO_INCIERTO' if current['submission_started'] else 'HOLD',
                                           'NO_AUTOMATIC_RETRY' if current['submission_started'] else 'REVALIDATION_OR_BROWSER_FAILED','CONSERVADO_SIN_REANUDAR')
                        db.execute("UPDATE autoapply_intervention_commands SET status='HELD',processed_at=? WHERE id=?",(now(),command['id']))
                    if action=='CLOSE':break
                    if session_row(db,sid)['status'] in TERMINAL:break
                if actor.page and actor.page.is_closed():
                    if session_row(db,sid)['status'] not in TERMINAL:
                        update_session(db,sid,EXPIRED,'BROWSER_CLOSED','RECONSTRUIR_CAMPOS_Y_VERIFICACION')
                    break
                # No polling the challenge, reading its tokens or interacting
                # with authentication while waiting. Only local command metadata.
                time.sleep(.2)
        finally:
            row=session_row(db,sid)
            if row['status'] not in TERMINAL and row['status']!='CERRADA' and row['form_state']!='SIN_ABRIR':
                update_session(db,sid,EXPIRED,'WORKER_SESSION_ENDED','RECONSTRUIR_CAMPOS_Y_VERIFICACION')
            db.execute('UPDATE autoapply_interventions SET worker_pid=NULL,heartbeat=NULL WHERE id=?',(sid,))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--database',required=True);parser.add_argument('--session',required=True)
    parser.add_argument('--owned-fixture-headless',action='store_true',help='Only an isolated owned synthetic test database')
    args=parser.parse_args()
    try:
        path=Path(args.database).resolve()
        if not path.is_relative_to(ROOT/'data') or not path.is_file():return 2
        db=Database(path);row=session_row(db,args.session)
        if args.owned_fixture_headless:
            from .human_sessions import validate_session
            if not row['fixture_url']:return 2
            validate_session(db,args.session)
        run(db,args.session,headless=args.owned_fixture_headless)
    except Exception:return 2  # Never dump exception messages containing a DOM/value.
    return 0


if __name__=='__main__':raise SystemExit(main())
