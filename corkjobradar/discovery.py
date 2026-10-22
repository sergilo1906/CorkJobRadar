"""Resumable public resource discovery. Candidates are not verified job adverts."""
import json
import re
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup
from lxml import etree
from .config import now
from .http import AccessBlocked
from .normalization import canonical_url

JOB_PATH = re.compile(r'job|career|vacanc|recruit|employment|trabaj', re.I)


def start_discovery(db, url):
    # Network/DNS checks occur again for each resource and redirect in WebClient.
    if urlsplit(url).scheme not in {'https','http'} or not urlsplit(url).hostname:
        raise ValueError('Página pública HTTP(S) requerida')
    with db.connect() as con:
        rid=con.execute('INSERT INTO discovery_runs(seed_url,started_at) VALUES(?,?)',(url,now())).lastrowid
        root=urlsplit(url)
        for target,kind in [(url,'html'),(f'{root.scheme}://{root.netloc}/robots.txt','robots')]:
            con.execute('INSERT OR IGNORE INTO discovery_resources(discovery_id,url,kind) VALUES(?,?,?)',(rid,target,kind))
    return rid


def resume_discovery(db, rid, client, max_pages=20):
    run=db.rows('SELECT * FROM discovery_runs WHERE id=?',(rid,))
    if not run:
        raise ValueError('Descubrimiento inexistente')
    host=urlsplit(run[0]['seed_url']).hostname
    db.execute("UPDATE discovery_runs SET status='running',finished_at=NULL WHERE id=?",(rid,))
    processed=0
    pending_candidates=[]
    def queue(url,kind,parent):
        if urlsplit(url).hostname==host:
            db.execute('INSERT OR IGNORE INTO discovery_resources(discovery_id,url,kind,parent_url) VALUES(?,?,?,?)',(rid,url,kind,parent))
    def candidate(url,title,kind,parent):
        if urlsplit(url).scheme not in {'https','http'} or not urlsplit(url).hostname:
            return
        pending_candidates.append((rid,url,title,kind,parent,now()))
    while processed < max_pages:
        rows=db.rows("SELECT * FROM discovery_resources WHERE discovery_id=? AND status='pending' ORDER BY CASE WHEN url LIKE '%job%' OR url LIKE '%career%' THEN 0 ELSE 1 END,id LIMIT 1",(rid,))
        if not rows:
            break
        item=rows[0]; url=item['url']; processed+=1
        pending_candidates.clear()
        try:
            if restricted_source(db,url):
                raise AccessBlocked('Condiciones de fuente: reproducción/almacenamiento pendiente de permiso')
            response=client.get(url,check_robots=True,accept='text/html,application/xml,application/rss+xml;q=0.9,*/*;q=0.5')
            body=response.text
            if item['kind']=='robots':
                for target in re.findall(r'^Sitemap:\s*(\S+)',body,re.I|re.M):
                    queue(urljoin(url,target),'sitemap',url)
            elif item['kind'] in {'sitemap','feed'}:
                root=etree.fromstring(response.content,etree.XMLParser(resolve_entities=False,no_network=True,load_dtd=False))
                tag=etree.QName(root).localname
                if tag=='sitemapindex':
                    for loc in root.xpath('//*[local-name()="sitemap"]/*[local-name()="loc"]/text()'):
                        queue(urljoin(url,loc.strip()),'sitemap',url)
                elif tag=='urlset':
                    for loc in root.xpath('//*[local-name()="url"]/*[local-name()="loc"]/text()'):
                        target=urljoin(url,loc.strip())
                        if JOB_PATH.search(urlsplit(target).path):
                            candidate(target,None,'SITEMAP_CANDIDATE',url)
                elif tag in {'rss','feed','RDF'}:
                    for entry in root.xpath('//*[local-name()="item" or local-name()="entry"]'):
                        title=' '.join(entry.xpath('./*[local-name()="title"]/text()'))
                        links=entry.xpath('./*[local-name()="link"]/@href | ./*[local-name()="link"]/text()')
                        for link in links:
                            candidate(urljoin(url,link.strip()),title,'FEED_CANDIDATE',url)
                else:
                    raise ValueError('XML no reconocido como sitemap/feed; requiere revisión')
            else:
                soup=BeautifulSoup(body,'lxml')
                for link in soup.select('a[href],link[href],iframe[src]'):
                    target=urljoin(str(response.url),link.get('href') or link.get('src'))
                    path=urlsplit(target).path
                    if any(t in str(link.get('type','')).lower() for t in ('rss','atom')):
                        queue(target,'feed',url)
                    elif 'sitemap' in path.lower() and path.lower().endswith('.xml'):
                        queue(target,'sitemap',url)
                    elif JOB_PATH.search(path) or re.search(r'greenhouse\.io|lever\.co|ashbyhq\.com|smartrecruiters\.com',target):
                        candidate(target,link.get_text(' ',strip=True),'LINK_CANDIDATE',url)
                # Reuse ATS recognition on this already fetched response, no duplicate request.
                from .sources import discover_ats
                discover_ats(db,url,client,html=body)
            with db.connect() as con:
                con.executemany('''INSERT OR IGNORE INTO discovery_candidates(discovery_id,url,title,kind,parent_url,discovered_at)
                                   VALUES(?,?,?,?,?,?)''',pending_candidates)
                con.execute("UPDATE discovery_resources SET status='done',checked_at=?,error=NULL WHERE id=?",(now(),item['id']))
        except Exception as exc:
            db.execute('UPDATE discovery_resources SET status=?,checked_at=?,error=? WHERE id=?',
                       ('blocked' if isinstance(exc,AccessBlocked) else 'error',now(),str(exc)[:2000],item['id']))
            db.error(None,'DISCOVERY_RESOURCE',url+': '+str(exc))
    remaining=db.rows("SELECT status,count(*) n FROM discovery_resources WHERE discovery_id=? GROUP BY status",(rid,))
    complete=all(r['status']=='done' for r in remaining)
    status='completed' if complete else 'partial'
    db.execute('UPDATE discovery_runs SET status=?,finished_at=?,message=? WHERE id=?',
               (status,now(),'Recursos accesibles agotados; no demuestra cobertura del mercado' if complete else 'Recursos pendientes/bloqueados; reanudar para continuar',rid))
    result={'id':rid,'status':status,'resources':remaining,'candidates':db.rows('SELECT count(*) n FROM discovery_candidates WHERE discovery_id=?',(rid,))[0]['n']}
    db.event('DISCOVERY_COVERAGE',result)
    return result


def restricted_source(db,url):
    host=urlsplit(url).hostname
    for source in db.rows("SELECT * FROM sources WHERE permission='PERMISO_REPRODUCCION_REQUERIDO'"):
        if urlsplit(source['url']).hostname==host:
            return source
    return None


def diagnose_omission(db,url):
    """Evidence from local history only; absence alone cannot identify a parser error."""
    canonical=canonical_url(url); host=urlsplit(url).hostname
    matches=[{k:j[k] for k in ('id','url','scope','scope_reason','analysis_status','first_seen_at','last_seen_at')}
             for j in db.rows('SELECT * FROM jobs') if canonical_url(j['url'])==canonical]
    sources=[]
    for source in db.rows('SELECT * FROM sources'):
        config=json.loads(source['config'])
        urls=[source['url'],config.get('board_url',''),config.get('discovery_url','')]
        if host in {urlsplit(u).hostname for u in urls if u}:
            runs=db.rows('SELECT run_id,status,observed,expected_total,pages_visited,pagination_complete,message,finished_at FROM source_runs WHERE source_id=? ORDER BY id DESC LIMIT 3',(source['id'],))
            sources.append({'id':source['id'],'enabled':bool(source['enabled']),'permission':source['permission'],
                            'configured_url':source['url'],'config':config,'latest_runs':runs})
    findings=[]
    if matches:
        findings.append({'cause':'YA_CONSERVADA','evidence':matches})
        if any(j['scope']=='FUERA_DE_ALCANCE' for j in matches):
            findings.append({'cause':'ARCHIVADA_POR_ALCANCE','evidence':[j['scope_reason'] for j in matches]})
    if not sources:
        findings.append({'cause':'FUENTE_NO_REGISTRADA','evidence':host})
    for source in sources:
        if not source['enabled']:
            findings.append({'cause':'FUENTE_DESACTIVADA','evidence':{'id':source['id'],'permission':source['permission']}})
        elif not source['latest_runs']:
            findings.append({'cause':'FUENTE_SIN_BUSQUEDA','evidence':source['id']})
        elif source['latest_runs'][0]['status']!='completed':
            findings.append({'cause':'BUSQUEDA_INCOMPLETA','evidence':source['latest_runs'][0]})
    if not matches:
        findings.append({'cause':'CAUSA_EXACTA_NO_DETERMINADA','evidence':'Revisar consulta, fecha de publicación, página y parser. No se atribuye fallo sin reproducirlo.'})
    return {'url':url,'checked_at':now(),'matches':matches,'sources':sources,'findings':findings,
            'status':'EXPLICADA_POR_HISTORIAL' if matches else 'REQUIERE_REVISION'}
