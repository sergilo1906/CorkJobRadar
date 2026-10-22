import json
import csv
import io
import re
from urllib.parse import urlsplit,urljoin,parse_qs,unquote
import yaml
from bs4 import BeautifulSoup
from .config import ROOT, now, digest
from .http import validate_url, AccessBlocked
from .adapters import make_adapter

def query_signature(source):
    config=source.get('config',{})
    config=json.loads(config) if isinstance(config,str) else config
    keys=('query','scope','job_link_selector','next_selector','pagination_verified','allow_empty_verified')
    return digest({'url':source['url'],'kind':source['kind'],'query_config':{k:config[k] for k in keys if k in config}})

def upsert_source(db, source):
    required = ('id','name','kind','url')
    if any(not source.get(k) for k in required):
        raise ValueError('Fuente requiere id, name, kind y url')
    p = urlsplit(source['url'])
    if p.scheme not in {'https','http'} or not p.hostname or p.username or p.password:
        raise ValueError('URL de fuente inválida')
    if p.hostname.endswith('linkedin.com'):
        raise ValueError('LinkedIn excluido')
    config = source.get('config',{})
    if isinstance(config,str):
        config = json.loads(config)
    enabled = source.get('enabled',False)
    if isinstance(enabled,str):
        enabled = enabled.lower() in {'true','1','yes'}
    if enabled and source.get('permission') != 'PUBLIC_API_DOCUMENTADA' and source.get('permission') != 'HTML_PUBLICO_REVISADO':
        raise ValueError('Para activar una fuente debe documentarse su vía permitida de consulta')
    db.execute('''INSERT INTO sources(id,name,kind,url,config,enabled,permission,status,checked_at,notes)
               VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,kind=excluded.kind,url=excluded.url,
               config=excluded.config,enabled=excluded.enabled,permission=excluded.permission,notes=excluded.notes''',
               (source['id'],source['name'],source['kind'],source['url'],json.dumps(config,ensure_ascii=False),int(enabled),
                source.get('permission','PENDIENTE'),source.get('status','SIN_COMPROBAR'),source.get('checked_at'),source.get('notes','')))

def import_sources(db, text, fmt='yaml'):
    sources = yaml.safe_load(text).get('sources',[]) if fmt == 'yaml' else list(csv.DictReader(io.StringIO(text)))
    for source in sources:
        upsert_source(db,source)
    return len(sources)

def load_catalog(db):
    return import_sources(db,(ROOT/'config/sources.yaml').read_text(encoding='utf-8'))

def export_sources(db, fmt='yaml'):
    rows = db.rows('SELECT * FROM sources ORDER BY id')
    if fmt == 'yaml':
        for row in rows:
            row['config'] = json.loads(row['config'])
            row['enabled'] = bool(row['enabled'])
        return yaml.safe_dump({'sources':rows},allow_unicode=True,sort_keys=False)
    out = io.StringIO()
    if rows:
        writer = csv.DictWriter(out,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return out.getvalue()

def health_sources(db, client, profile):
    results = []
    for source in db.rows('SELECT * FROM sources ORDER BY id'):
        if not source['enabled']:
            results.append({'source':source['id'],'status':source['status'],'reason':'No activada; no se consulta automáticamente'})
            continue
        try:
            page = make_adapter(source,client,profile).health_check()
            status,reason = 'ACCESIBLE',f'Primera página: {len(page.jobs)} registros; no es auditoría completa'
        except AccessBlocked as exc:
            status,reason = 'BLOQUEADA',str(exc)
        except Exception as exc:
            status,reason = 'ERROR',str(exc)
        db.execute('UPDATE sources SET status=?,checked_at=? WHERE id=?',(status,now(),source['id']))
        results.append({'source':source['id'],'status':status,'reason':reason})
        db.event('SOURCE_HEALTH',results[-1])
    return results

def ats_endpoint(target):
    """Derive identifiers only from documented URLs, never from a requisition token."""
    try:
        parsed=urlsplit(target)
        if parsed.scheme!='https' or parsed.username or parsed.password or parsed.port not in {None,443}:return None
        host=parsed.hostname;parts=[unquote(p) for p in parsed.path.split('/') if p]
        token=None;kind=None;endpoint=None
        if host in {'boards.greenhouse.io','job-boards.greenhouse.io','job-boards.eu.greenhouse.io'}:
            kind='greenhouse'
            if parts and parts[0]=='embed':
                values=parse_qs(parsed.query).get('for',[])
                token=values[0] if len(values)==1 else None
            elif parts:token=parts[0]
            if token:endpoint=f'https://boards-api.greenhouse.io/v1/boards/{token}/jobs'
        elif host in {'jobs.lever.co','jobs.eu.lever.co'} and parts:
            kind='lever';token=parts[0]
            endpoint=f'https://api.{"eu." if host=="jobs.eu.lever.co" else ""}lever.co/v0/postings/{token}'
        elif host=='jobs.ashbyhq.com' and parts:
            kind='ashby';token=parts[0];endpoint=f'https://api.ashbyhq.com/posting-api/job-board/{token}'
        elif host in {'jobs.smartrecruiters.com','careers.smartrecruiters.com'} and parts:
            kind='smartrecruiters';token=parts[0];endpoint=f'https://api.smartrecruiters.com/v1/companies/{token}/postings'
        if not token or not re.fullmatch(r'[A-Za-z0-9_-]+',token):return None
        return {'kind':kind,'token':token,'url':endpoint}
    except ValueError:return None


def discover_ats(db, url, client, html=None):
    if html is None:
        response = client.get(url,check_robots=True,accept='text/html')
        html=response.text
    soup = BeautifulSoup(html,'lxml')
    discovered = []
    for tag in soup.select('a[href],iframe[src]'):
        target=urljoin(url,tag.get('href') or tag.get('src',''))
        match=ats_endpoint(target)
        if match:
            token=match['token'];api=match['url'];kind=match['kind'];sid=digest(api)[:20]
            if not db.rows('SELECT id FROM sources WHERE url=?',(api,)):
                item={'id':sid,'name':token,'kind':kind,'url':api,'enabled':False,
                      'permission':'PENDIENTE','notes':f'ATS enlazado en {url}; enlace {target}; revisar antes de activar',
                      'config':{'discovery_url':url,'board_url':target,'company_identifier':token},'checked_at':now()}
                upsert_source(db,item);discovered.append(item)
    db.event('DISCOVERY',{'url':url,'new_sources':len(discovered)})
    return discovered
