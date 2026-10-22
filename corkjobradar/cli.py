import argparse
import json
import sys
import platform
import importlib.metadata
import shutil
from .config import ROOT, load_profile, now
from .db import Database

def doctor(db=None):
    db = db or Database()
    profile = load_profile()
    result = {'fecha':now(), 'python':sys.version.split()[0], 'plataforma':platform.platform(),
              'directorio':str(ROOT), 'database':str(db.path),
              'sqlite':db.rows('PRAGMA integrity_check')[0]['integrity_check'],
              'origen':profile['origin_neighborhood'], 'coche_propio':profile['owns_car'],
              'ollama_executable':shutil.which('ollama'),
              'dependencias':{name:importlib.metadata.version(name) for name in
                              ['streamlit','httpx','openpyxl','pydantic','pytest']}}
    return result

def main(argv=None):
    argv=sys.argv[1:] if argv is None else argv
    if argv and argv[0]=='local-runtime':
        from .runtime import main as runtime_main
        return runtime_main(argv[1:])
    if argv and argv[0]=='autoapply':
        from .autoapply.cli import main as autoapply_main
        return autoapply_main(argv[1:])
    parser = argparse.ArgumentParser(description='Cork Job Radar — investigación local')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor')
    sub.add_parser('junior-it',help='Recorrer fuentes IT revisadas, conservar y analizar todas las ofertas en alcance')
    sources = sub.add_parser('sources')
    sources.add_argument('--refresh',action='store_true')
    sources.add_argument('--load',action='store_true')
    sources.add_argument('--import-file')
    sources.add_argument('--export-file')
    sources.add_argument('--format',choices=['yaml','csv'],default='yaml')
    scan = sub.add_parser('scan')
    scan.add_argument('--all',action='store_true')
    scan.add_argument('--source',action='append')
    for name in ('resume','worker'):
        p = sub.add_parser(name)
        p.add_argument('--run-id',type=int,required=True)
    cancel = sub.add_parser('cancel')
    cancel.add_argument('--run-id',type=int,required=True)
    analyze = sub.add_parser('analyze')
    analyze.add_argument('--pending',action='store_true')
    analyze.add_argument('--local',action='store_true',help='Lectura local en español; requiere revisión humana')
    analyze.add_argument('--job',action='append',help='ID conservado; repetir para varias ofertas')
    verify = sub.add_parser('verify')
    verify.add_argument('--all',action='store_true')
    export = sub.add_parser('export')
    export.add_argument('--xlsx',action='store_true')
    export.add_argument('--run-id',type=int)
    export.add_argument('--output-dir')
    audit = sub.add_parser('audit')
    audit.add_argument('--run-id',type=int)
    imp = sub.add_parser('import-url')
    imp.add_argument('url')
    csvp = sub.add_parser('import-csv')
    csvp.add_argument('file')
    discovery = sub.add_parser('discover')
    discovery.add_argument('--url',required=True)
    crawl=sub.add_parser('discover-resources')
    crawl.add_argument('--url')
    crawl.add_argument('--resume',type=int)
    crawl.add_argument('--max-pages',type=int,default=20)
    omission=sub.add_parser('omission')
    omission.add_argument('url')
    args = parser.parse_args(argv)
    db = Database()
    if args.command=='junior-it':
        from .junior_discovery import run_junior_search
        report,path=run_junior_search(db)
        print(json.dumps({'run':report['run'],'sources':report['sources'],'all_retrieved_retained':report['all_retrieved_retained'],
                          'in_scope_or_pending':report['in_scope_or_pending'],'report':str(path.relative_to(ROOT)),'live_enabled':False},ensure_ascii=False))
        return
    if args.command == 'doctor':
        print(json.dumps(doctor(db), ensure_ascii=False, indent=2))
        return
    from pathlib import Path
    from .sources import load_catalog, import_sources, export_sources, health_sources, discover_ats
    from .http import WebClient
    from .worker import create_run, run_worker, prepare_resume
    profile = load_profile()
    result = None
    if args.command == 'sources':
        if args.load:
            result = {'imported':load_catalog(db)}
        if args.import_file:
            result = {'imported':import_sources(db,Path(args.import_file).read_text(encoding='utf-8-sig'),args.format)}
        if args.refresh:
            with WebClient(profile,db) as client:
                result = health_sources(db,client,profile)
        if args.export_file:
            Path(args.export_file).write_text(export_sources(db,args.format),encoding='utf-8-sig')
            result = {'file':args.export_file}
        if result is None:
            result = db.rows('SELECT id,name,kind,url,enabled,permission,status,checked_at,last_success,notes FROM sources')
    elif args.command in {'scan','analyze','verify'}:
        kind = {'scan':'scan','analyze':'analyze','verify':'verify'}[args.command]
        if kind == 'scan' and not args.all and not args.source:
            parser.error('scan requiere --all o --source ID')
        override={**profile,'analyzer':'llama'} if args.command=='analyze' and args.local else None
        individual=args.command=='analyze' and args.job
        if individual:
            if any(not db.rows('SELECT id FROM jobs WHERE id=?',(jid,)) for jid in args.job):
                parser.error('ID de oferta inexistente; no se ha creado ninguna tarea')
        run_id = create_run(db,args.source if kind=='scan' else None,'deep' if individual else kind,override)
        if individual:
            from .worker import enqueue
            for jid in args.job:
                enqueue(db,run_id,None,jid,'analyze')
        run_worker(db,run_id)
        result = db.rows('SELECT id,status,started_at,finished_at,message FROM scan_runs WHERE id=?',(run_id,))
    elif args.command in {'resume','worker'}:
        if args.command == 'resume':
            prepare_resume(db,args.run_id)
        run_worker(db,args.run_id)
        result = db.rows('SELECT id,status,finished_at FROM scan_runs WHERE id=?',(args.run_id,))
    elif args.command == 'cancel':
        db.execute('UPDATE scan_runs SET cancel_requested=1 WHERE id=?',(args.run_id,))
        result = {'cancel_requested':args.run_id}
    elif args.command == 'export':
        from .exporting import export_all
        result = export_all(db,args.output_dir,args.run_id)
    elif args.command == 'audit':
        from .audit import coverage
        result = coverage(db,args.run_id)
    elif args.command=='omission':
        from .discovery import diagnose_omission
        result=diagnose_omission(db,args.url)
        db.event('INVESTIGAR_OMISION',result)
    elif args.command=='discover-resources':
        from .discovery import start_discovery,resume_discovery
        if not args.url and not args.resume:
            parser.error('discover-resources requiere --url o --resume')
        if args.max_pages<1:
            parser.error('--max-pages debe ser positivo')
        rid=args.resume or start_discovery(db,args.url)
        with WebClient(profile,db) as client:
            result=resume_discovery(db,rid,client,args.max_pages)
    elif args.command in {'import-url','import-csv','discover'}:
        from .imports import import_url, import_csv
        if args.command == 'import-csv':
            result = import_csv(db,Path(args.file).read_text(encoding='utf-8-sig'),profile)
        else:
            with WebClient(profile,db) as client:
                result = import_url(db,args.url,client,profile) if args.command=='import-url' else discover_ats(db,args.url,client)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__ == '__main__':
    main()
