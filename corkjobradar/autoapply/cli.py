import argparse
import json
from pathlib import Path
import importlib.metadata
import yaml
from ..config import ROOT,load_profile,now
from ..db import Database
from .policy import current_policy,save_policy,pause,resume,require_live,Policy
from .engine import preview,run_simulation,report
from .store import reconcile


def doctor(db):
    dependencies={}
    for name in ('playwright','reportlab','pypdfium2'):
        try:dependencies[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:dependencies[name]=None
    from .platforms import platform_for
    return {**report(db),'database_schema':db.rows('PRAGMA user_version')[0]['user_version'],
            'database_integrity':db.rows('PRAGMA integrity_check')[0]['integrity_check'],
            'dependencies':dependencies,'browser_installed':bool(list((ROOT/'data/playwright-browsers').glob('chromium*'))),
            'visible_browser_installed':bool(list((ROOT/'data/playwright-browsers').glob('chromium-*/chrome-win64/chrome.exe'))),
            'interactive_external_release_gate':False,
            'live_release_gate':False,'individual_submission_approval_required_after_future_activation':False}


def main(argv=None):
    parser=argparse.ArgumentParser(description='Cork Job Radar AutoApply — simulación; live bloqueado hasta ensayo autorizado')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor')
    p=sub.add_parser('policy');p.add_argument('action',choices=['show','validate','accept']);p.add_argument('--file');p.add_argument('--consent')
    p=sub.add_parser('preview');p.add_argument('--limit',type=int,default=25);p.add_argument('--include-other',action='store_true')
    p=sub.add_parser('run');group=p.add_mutually_exclusive_group(required=True);group.add_argument('--dry-run',action='store_true');group.add_argument('--live',action='store_true')
    sub.add_parser('pause');sub.add_parser('revoke')
    p=sub.add_parser('resume');p.add_argument('--consent',required=True)
    sub.add_parser('reconcile');sub.add_parser('report')
    p=sub.add_parser('resolve');p.add_argument('--attempt',required=True,type=int)
    p.add_argument('--action',required=True,choices=['NO_REPETIR','MARCAR_RESUELTA','REINTENTAR_PREPARACION_SIMULADA'])
    p.add_argument('--expected-updated-at',required=True);p.add_argument('--acknowledge',action='store_true')
    p=sub.add_parser('inspect');p.add_argument('--job',required=True)
    p=sub.add_parser('form-inspect');p.add_argument('--job',required=True);p.add_argument('--hosted-readonly',action='store_true')
    p=sub.add_parser('form-prepare');p.add_argument('--inspection',required=True,type=int);p.add_argument('--review-document',type=int)
    p=sub.add_parser('api-prepare');p.add_argument('--inspection',required=True,type=int)
    p=sub.add_parser('trial');p.add_argument('action',choices=['plan','status','authorize','execute']);p.add_argument('--job');p.add_argument('--inspection',type=int);p.add_argument('--trial',type=int);p.add_argument('--hash');p.add_argument('--consent')
    sub.add_parser('readiness')
    sub.add_parser('platforms')
    sub.add_parser('ats-inventory')
    sub.add_parser('interventions')
    sub.add_parser('blockers')
    p=sub.add_parser('selection');p.add_argument('--refresh-queue',action='store_true');p.add_argument('--prepare-local',action='store_true')
    p=sub.add_parser('manual-prepare');p.add_argument('--job',required=True);p.add_argument('--inspection',type=int)
    p=sub.add_parser('cv');p.add_argument('action',choices=['prepare','approve']);p.add_argument('--format',choices=['pdf','docx'],default='pdf');p.add_argument('--document',type=int);p.add_argument('--hash');p.add_argument('--facts-hash');p.add_argument('--consent')
    args=parser.parse_args(argv);db=Database()
    try:
        if args.command=='doctor':result=doctor(db)
        elif args.command=='selection':
            from .broad_selection import selection_inventory
            from .selection_queue import refresh_queue,prepare_all_local
            result=prepare_all_local(db) if args.prepare_local else refresh_queue(db) if args.refresh_queue else selection_inventory(db)
        elif args.command=='policy':
            control,row,policy=current_policy(db)
            if args.action=='show':result={'control':control,'policy':policy.model_dump() if policy else None}
            else:
                raw=yaml.safe_load(Path(args.file).read_text(encoding='utf-8')) if args.file else policy.model_dump() if policy else None
                if isinstance(raw,dict) and 'policy' in raw:raw=raw['policy']
                validated=Policy.model_validate(raw)
                result={'valid':True,'active':False,'validation_is_not_consent':True}
                if args.action=='accept':result={'policy_id':save_policy(db,validated.model_dump(),args.consent),'mode':'SIMULACION'}
        elif args.command=='preview':
            if args.limit<1:raise ValueError('POSITIVE_VIEW_LIMIT_REQUIRED')
            result=preview(db,args.limit,it_only=not args.include_other)
        elif args.command=='run':
            if args.live:require_live(db)
            result=run_simulation(db)
        elif args.command=='pause':pause(db);result={'paused':True}
        elif args.command=='revoke':pause(db,revoke=True);result={'revoked':True}
        elif args.command=='resume':resume(db,args.consent);result={'mode':'SIMULACION'}
        elif args.command=='reconcile':
            from ..worker import worker_lock
            with worker_lock(db):result=reconcile(db)
        elif args.command=='inspect':
            from ..http import WebClient
            from .platforms import inspect_greenhouse
            rows=db.rows('SELECT * FROM jobs WHERE id=?',(args.job,))
            if not rows:raise ValueError('JOB_NOT_FOUND')
            with WebClient(load_profile(),db) as client:result=inspect_greenhouse(rows[0]['url'],client)
            file=ROOT/'logs'/('autoapply-greenhouse-inspection-'+args.job+'.json')
            file.write_text(json.dumps({**result,'checked_at':now()},ensure_ascii=False,indent=2),encoding='utf-8')
        elif args.command=='form-inspect':
            from ..http import WebClient
            from .forms import inspect_job_form
            with WebClient(load_profile(),db) as client:result=inspect_job_form(db,args.job,client,args.hosted_readonly)
        elif args.command=='form-prepare':
            from .forms import disconnected_preparation
            result=disconnected_preparation(db,args.inspection,args.review_document)
        elif args.command=='api-prepare':
            from .forms import load_inspection
            from .vault import candidate_snapshot
            from .documents import document_bytes
            from .recruitee import prepare_request
            result=prepare_request(load_inspection(db,args.inspection),candidate_snapshot(db),lambda did:document_bytes(db,did)).summary()
        elif args.command=='readiness':
            from .trials import autonomous_readiness
            result=autonomous_readiness(db)
        elif args.command=='platforms':
            from .compatibility import compatibility_report
            result=compatibility_report()
        elif args.command=='ats-inventory':
            from .opportunities import persist_inventory
            report,path=persist_inventory(db)
            result={**{k:v for k,v in report.items() if k!='offers'},'inventory_path':str(path.relative_to(ROOT))}
        elif args.command=='interventions':
            from .human_sessions import pending_interventions
            result={'live_enabled':False,'interventions':[{k:r[k] for k in ('id','company','title','status','reason_code','form_state','last_verified_at','worker_available')} for r in pending_interventions(db)]}
        elif args.command=='blockers':
            from .blocker_report import persist_blocker_report
            report,path=persist_blocker_report(db)
            result={k:v for k,v in report.items() if k!='offers'}
            result['report_path']=str(path.relative_to(ROOT))
        elif args.command=='manual-prepare':
            from .handoff import prepare_handoff
            result=prepare_handoff(db,args.job,args.inspection)
        elif args.command=='trial':
            from .trials import create_trial_plan,trial_readiness,authorize_trial,execute_trial
            if args.action=='plan':result=create_trial_plan(db,args.job,args.inspection)
            elif args.action=='status':result=trial_readiness(db,args.job,args.inspection)
            elif args.action=='authorize':result={'authorization_id':authorize_trial(db,args.trial,args.hash,args.consent),'submitted':False}
            else:result=execute_trial(db,args.trial)
        elif args.command=='cv':
            from .documents import render_cv,create_cv_review,cv_review_bytes,approve_cv_review
            from .vault import candidate_snapshot
            if args.action=='prepare':
                did=create_cv_review(db,render_cv(candidate_snapshot(db),args.format),args.format)
                _,_,sha,_=cv_review_bytes(db,did)
                result={'document_id':did,'file_hash':sha,'facts_hash':candidate_snapshot(db)['_facts_hash'],'approved':False}
            else:
                result={'document_id':approve_cv_review(db,args.document,args.hash,args.facts_hash,args.consent=='APPROVE_REVIEWED_CV'),'submitted':False}
        elif args.command=='resolve':
            from .resolution import manual_resolution,retry_simulation_preparation
            result=(retry_simulation_preparation(db,args.attempt,args.acknowledge,args.expected_updated_at) if args.action=='REINTENTAR_PREPARACION_SIMULADA'
                    else manual_resolution(db,args.attempt,args.action,args.acknowledge,args.expected_updated_at))
        else:result=report(db)
    except Exception as exc:
        # Do not dump exception messages: browser/parser libraries can include submitted values.
        known=str(exc) if isinstance(exc,PermissionError) and str(exc).startswith('LIVE_LOCKED') else type(exc).__name__
        print(json.dumps({'error':known,'live_submission_enabled':False}));return 2
    print(json.dumps(result,ensure_ascii=False,indent=2));return 0


if __name__=='__main__':raise SystemExit(main())
