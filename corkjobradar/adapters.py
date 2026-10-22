import json
from urllib.parse import urlencode, urljoin, urlsplit
from bs4 import BeautifulSoup
from .models import Job, Page
from .normalization import clean_html, date_iso
from .parsers import jobpostings
from .config import digest
from .http import IncompleteSource
import re

def published_mode(location, text=''):
    if re.search(r'\bhybrid\b',location,re.I) or re.search(r'\b(?:a|is|this)\s+(?:a\s+)?hybrid (?:position|role)',text[:1500],re.I):
        return 'HYBRID'
    if re.search(r'\bremote\b',location,re.I):
        return 'REMOTE'
    return 'DESCONOCIDO'

class Adapter:
    def __init__(self, source, client, profile):
        self.source, self.client, self.profile = source, client, profile
        self.config = json.loads(source['config']) if isinstance(source.get('config'),str) else source.get('config',{})

    def health_check(self):
        return next(self.discover())

    def fetch_detail(self, job):
        return Job.model_validate(job)

    def normalize(self, raw):
        raise NotImplementedError

    def normalize_many(self,rows):
        result=[]
        for raw in rows:
            try:
                result.append(self.normalize(raw))
            except Exception as exc:
                # No perder las demás tarjetas ni este registro malformado.
                safe_raw=raw if isinstance(raw,dict) else {'original':raw}
                result.append(Job(external_id=str(safe_raw.get('id') or digest(safe_raw)),
                    title=str(safe_raw.get('title') or safe_raw.get('text') or safe_raw.get('name') or 'Registro con error de extracción'),
                    company=self.source['name'],url=self.source['url'],
                    raw={**safe_raw,'_parse_error':str(exc)[:1000]}))
        return result

    def discover(self, cursor=None):
        raise NotImplementedError

class Greenhouse(Adapter):
    def normalize(self, raw):
        description = clean_html(raw.get('content',''))
        raw=dict(raw)
        if 'internal_job_id' in raw and raw['internal_job_id'] is None:
            raw['_listing_type']='BOLSA_DE_TALENTO_SIN_VACANTE_CONCRETA'
        return Job(external_id=str(raw['id']), title=raw['title'], company=raw.get('company_name') or self.source['name'],
                   location=raw.get('location',{}).get('name') or 'No indicado por la empresa',
                   url=raw['absolute_url'], description=description, detail_complete=bool(description),
                   posted_at=date_iso(raw.get('first_published')),mode=published_mode(raw.get('location',{}).get('name',''),description),raw=raw)

    def discover(self, cursor=None):
        response = self.client.get(self.source['url'] + ('&' if '?' in self.source['url'] else '?') + 'content=true').json()
        if not isinstance(response.get('jobs'),list):
            raise IncompleteSource('Greenhouse: cambió la estructura jobs')
        jobs = self.normalize_many(response['jobs'])
        total = response.get('meta',{}).get('total')
        yield Page(jobs, None, total, True if total is None or len(jobs) == total else False,
                   {'method':'documented_all_jobs_endpoint','updated_at_is_not_posted_at':True})

    def fetch_detail(self, job):
        base = self.source['url'].split('?')[0].rstrip('/')
        raw = self.client.get(f"{base}/{job['external_id']}?questions=true").json()
        return self.normalize(raw)

class Lever(Adapter):
    def normalize(self, raw):
        cats = raw.get('categories',{})
        blocks = [raw.get('description','')]
        blocks.extend(str(x.get('text','')) + '\n' + str(x.get('content','')) for x in raw.get('lists',[]))
        blocks.extend([raw.get('additional',''),raw.get('closing','')])
        text = clean_html('\n'.join(blocks))
        return Job(external_id=str(raw['id']),title=raw['text'],company=self.source['name'],
                   location='; '.join(raw.get('categories',{}).get('allLocations') or [cats.get('location') or 'No indicado por la empresa']),
                   url=raw['hostedUrl'], apply_url=raw.get('applyUrl'), description=text,
                   detail_complete=bool(raw.get('description') or raw.get('lists')),
                   mode={'remote':'REMOTE','hybrid':'HYBRID','on-site':'ONSITE'}.get(raw.get('workplaceType'),'DESCONOCIDO'),
                   posted_at=date_iso(raw.get('createdAt')),raw=raw)

    def discover(self, cursor=None):
        offset = int(cursor or 0)
        limit = int(self.config.get('page_size',100))
        seen = set()
        for _ in range(self.profile['safety_max_pages']):
            url = self.source['url'] + '?' + urlencode({'mode':'json','skip':offset,'limit':limit})
            data = self.client.get(url).json()
            if not isinstance(data,list):
                raise IncompleteSource('Lever: respuesta no es lista')
            signature = digest([x.get('id') for x in data])
            if data and signature in seen:
                raise IncompleteSource('Lever repite una página; paginación incompleta')
            seen.add(signature)
            jobs = self.normalize_many(data)
            # Página vacía demuestra terminación incluso si el servidor limita page_size.
            end = len(data) == 0
            offset += len(data)
            yield Page(jobs, None if end else str(offset), None, True if end else None)
            if end:
                return
        raise IncompleteSource('Límite técnico de páginas alcanzado; se requiere reanudar')

    def fetch_detail(self, job):
        return self.normalize(self.client.get(self.source['url'].rstrip('/') + '/' + job['external_id'] + '?mode=json').json())

class Ashby(Adapter):
    def normalize(self, raw):
        locations = [raw.get('location','')]
        locations.extend(x.get('location','') for x in raw.get('secondaryLocations',[]))
        text = raw.get('descriptionPlain') or clean_html(raw.get('descriptionHtml',''))
        return Job(external_id=str(raw['id']),title=raw['title'],company=self.source['name'],
                   location='; '.join(filter(None, locations)) or 'No indicado por la empresa',
                   url=raw['jobUrl'],apply_url=raw.get('applyUrl'), description=text,
                   detail_complete=bool(text), posted_at=date_iso(raw.get('publishedAt')),
                   mode={'Hybrid':'HYBRID','OnSite':'ONSITE','Remote':'REMOTE'}.get(raw.get('workplaceType'),'REMOTE' if raw.get('isRemote') else 'DESCONOCIDO'),raw=raw)

    def discover(self, cursor=None):
        data = self.client.get(self.source['url'] + '?includeCompensation=true').json()
        if not isinstance(data.get('jobs'),list):
            raise IncompleteSource('Ashby: cambió la estructura jobs')
        yield Page(self.normalize_many(data['jobs']), None,len(data['jobs']),True,
                   {'method':'documented_all_jobs_endpoint'})

class SmartRecruiters(Adapter):
    def normalize(self, raw):
        loc = raw.get('location',{})
        sections = raw.get('jobAd',{}).get('sections',{})
        text = clean_html('\n'.join(str(x.get('title',''))+'\n'+str(x.get('text','')) for x in sections.values()))
        raw = dict(raw)
        raw['_detail_url'] = raw.get('ref') or self.source['url'].rstrip('/') + '/' + str(raw['id'])
        url = raw.get('postingUrl') or raw.get('_posting_url')
        if not url:
            url = raw['_detail_url']  # URL pública aportada por la fuente; no fabricar un enlace web.
        return Job(external_id=str(raw['id']),title=raw['name'],company=raw.get('company',{}).get('name') or self.source['name'],
                   location='; '.join(filter(None,[', '.join(str(loc[k]) for k in ('city','region','country') if loc.get(k)),loc.get('hybridDescription')])) or 'No indicado por la empresa',
                   url=url,apply_url=raw.get('applyUrl'),description=text,detail_complete=bool(sections),
                   mode='REMOTE' if loc.get('remote') else 'HYBRID' if loc.get('hybrid') else 'DESCONOCIDO',posted_at=date_iso(raw.get('releasedDate')),raw=raw)

    def discover(self, cursor=None):
        offset, limit = int(cursor or 0),int(self.config.get('page_size',100))
        seen = set()
        query = self.config.get('query',{})
        for _ in range(self.profile['safety_max_pages']):
            data = self.client.get(self.source['url'] + '?' + urlencode({**query,'offset':offset,'limit':limit})).json()
            rows = data.get('content')
            if not isinstance(rows,list):
                raise IncompleteSource('SmartRecruiters: cambió la estructura content')
            total = data.get('totalFound')
            signature = digest([x.get('id') for x in rows])
            if rows and signature in seen:
                raise IncompleteSource('SmartRecruiters repite una página')
            seen.add(signature)
            offset += len(rows)
            end = (total is not None and offset >= total) or not rows
            complete = True if end and (total is None or offset == total) else (False if end else None)
            yield Page(self.normalize_many(rows), None if end else str(offset),total,complete)
            if end:
                return
        raise IncompleteSource('Límite técnico de páginas; búsqueda parcial')

    def fetch_detail(self, job):
        raw = self.client.get(job['raw']['_detail_url']).json()
        raw['_posting_url'] = job['url']
        return self.normalize(raw)

class GenericHTML(Adapter):
    def discover(self, cursor=None):
        url = cursor or self.source['url']
        visited, signatures = set(), set()
        for _ in range(self.profile['safety_max_pages']):
            if url in visited:
                raise IncompleteSource('HTML: bucle de enlaces siguiente')
            visited.add(url)
            response = self.client.get(url,check_robots=True,accept='text/html')
            soup = BeautifulSoup(response.text,'lxml')
            jobs, malformed = jobpostings(response.text,str(response.url))
            links = soup.select(self.config['job_link_selector']) if self.config.get('job_link_selector') else []
            known = {job.url for job in jobs}
            for link in links:
                target = urljoin(str(response.url),link.get('href',''))
                if target not in known:
                    known.add(target)
                    jobs.append(Job(external_id=digest(target),title=link.get_text(' ',strip=True) or 'Título pendiente',
                                    company=self.source['name'],url=target))
            if malformed:
                # Guardar primero las tarjetas válidas, después declarar el error.
                yield Page(jobs,url,None,False,{'malformed_jsonld':malformed})
                raise IncompleteSource('JSON-LD defectuoso; se conservaron las ofertas válidas')
            if not jobs and not self.config.get('allow_empty_verified',False):
                raise IncompleteSource('HTML sin ofertas reconocibles; no se presume listado vacío ni completo')
            next_link = soup.select_one(self.config.get('next_selector','a[rel~=next]'))
            next_url = urljoin(str(response.url),next_link.get('href','')) if next_link else None
            signature = digest([job.url for job in jobs])
            if jobs and signature in signatures:
                raise IncompleteSource('HTML: resultados repetidos en paginación')
            signatures.add(signature)
            end_proven = bool(self.config.get('pagination_verified')) and next_url is None
            yield Page(jobs,next_url,None,True if end_proven else None,
                       {'url':url,'pagination_verified':bool(self.config.get('pagination_verified'))})
            if not next_url:
                return
            url = next_url
        raise IncompleteSource('HTML: límite técnico de páginas; búsqueda parcial')

    def fetch_detail(self, job):
        response = self.client.get(job['url'],check_robots=True,accept='text/html')
        jobs, errors = jobpostings(response.text,str(response.url))
        if not errors and len(jobs) == 1:
            jobs[0].external_id = job['external_id']
            return jobs[0]
        original = Job.model_validate(job)
        original.raw['manual_review_reason'] = 'No se pudo identificar una única descripción JobPosting íntegra'
        return original

class CareerTabs(Adapter):
    """Read published Elementor career tabs, each role bound to its own panel.

    This is a narrow public read adapter, not a form/submission adapter. No
    employer address, junior requirements or duties are inferred from siblings.
    """
    def discover(self,cursor=None):
        response=self.client.get(self.source['url'],check_robots=True,accept='text/html')
        soup=BeautifulSoup(response.text,'lxml');jobs=[];seen=set();errors=0
        for title in soup.select('.elementor-tab-desktop-title[data-tab]'):
            label=title.get_text(' ',strip=True);panel=soup.find(id=title.get('aria-controls','MISSING_PANEL'))
            key=digest(label.casefold())[:24]
            if not panel or 'elementor-tab-content' not in panel.get('class',[]) or panel.get('data-tab')!=title['data-tab']:
                errors+=1
                jobs.append(Job(external_id=key,title=label or 'Puesto pendiente de recuperar',company=self.source['name'],url=str(response.url),
                                raw={'_career_section_id':key,'_parse_error':'CAREER_PANEL_BINDING_FAILED'}));continue
            if key in seen:raise IncompleteSource('Career tabs: puesto repetido o ambiguo')
            seen.add(key)
            text=clean_html(str(panel))
            if not text.strip():raise IncompleteSource('Career tabs: descripción vacía')
            jobs.append(Job(external_id=key,title=label,company=self.source['name'],
                            url=str(response.url)+'#'+title['id'],apply_url=str(response.url),description=text,detail_complete=True,
                            raw={'_career_section_id':key,'_published_section_id':title['id'],
                                 '_location_review_required':True,'_source_document_hash':digest(response.text)}))
        if not jobs:raise IncompleteSource('Career tabs: estructura no reconocida; no presumir lista vacía')
        yield Page(jobs,None,len(jobs),not errors,{'method':'published_career_tabs','scope':'ONLY_THIS_PAGE','no_submission':True,'retained_parse_errors':errors})


class HSE(Adapter):
    """Public HSE county search, using its published total and disabled Next state."""
    def discover(self, cursor=None):
        url = cursor or self.source['url']
        visited, signatures = set(), set()
        for _ in range(self.profile['safety_max_pages']):
            if url in visited:
                raise IncompleteSource('HSE: bucle de paginación')
            visited.add(url)
            response = self.client.get(url, check_robots=True, accept='text/html')
            soup = BeautifulSoup(response.text, 'lxml')
            heading = soup.select_one('[data-testid="hse-listing__title"]')
            count = re.search(r'Showing\s+(\d+)\s+to\s+(\d+)\s+of\s+(\d+)\s+results',
                              heading.get_text(' ', strip=True) if heading else '')
            if not count:
                raise IncompleteSource('HSE: total/rango no reconocible; no se presume listado vacío')
            start, end, total = map(int, count.groups())
            jobs = []
            for article in soup.select('article'):
                link = article.select_one('a.hse-listing__link[href]')
                if not link:
                    continue
                target = urljoin(str(response.url), link['href'])
                text = article.get_text('\n', strip=True)
                county = re.search(r'County:\s*([^\n]+)', text)
                date = article.select_one('time[datetime]')
                jobs.append(Job(external_id=urlsplit(target).path.rstrip('/').split('/')[-1],
                    title=link.get_text(' ', strip=True), company='HSE', url=target,
                    location=county[1] if county else 'No indicado por la empresa',
                    posted_at=date_iso(date['datetime']) if date else None,
                    raw={'listing_text':text,'listing_url':str(response.url)}))
            if len(jobs) != end - start + 1:
                raise IncompleteSource('HSE: tarjetas extraídas no coinciden con el rango publicado')
            signature = digest([job.url for job in jobs])
            if signature in signatures:
                raise IncompleteSource('HSE repite resultados')
            signatures.add(signature)
            following = soup.select_one('a[aria-label="Next Page"]')
            last = following is not None and following.get('aria-disabled') == 'true'
            next_url = urljoin(str(response.url), following['href']) if following and not last else None
            if next_url and urlsplit(next_url).netloc != urlsplit(self.source['url']).netloc:
                raise IncompleteSource('HSE: siguiente página fuera del dominio de la fuente')
            yield Page(jobs, next_url, total, True if last and end == total else None,
                       {'range_start':start,'range_end':end,'url':str(response.url),
                        'next_disabled':last,'scope':'County Cork, incluye puestos multilocalización'})
            if not next_url:
                return
            url = next_url
        raise IncompleteSource('HSE: límite técnico de páginas; reanudar, cobertura parcial')

    def fetch_detail(self, job):
        from .documents import document_text
        response = self.client.get(job['url'], check_robots=True, accept='text/html')
        soup = BeautifulSoup(response.text, 'lxml')
        main = soup.select_one('main')
        if not main or not main.select_one('h1'):
            raise IncompleteSource('HSE: ficha sin título/contenido principal')
        original = Job.model_validate(job)
        original.description = main.get_text('\n', strip=True)
        original.raw = dict(original.raw)
        fields = {}
        for heading in main.select('h2'):
            values = []
            for sibling in heading.next_siblings:
                if getattr(sibling, 'name', None) == 'h2':
                    break
                if getattr(sibling, 'get_text', None):
                    values.append(sibling.get_text(' ', strip=True))
            fields[heading.get_text(' ', strip=True)] = '\n'.join(values)
        original.raw['published_fields'] = fields
        from .deadlines import hse_deadline_fields
        original.raw.update(hse_deadline_fields(fields))
        original.location = fields.get('Location') or fields.get('County') or original.location
        attachments = []
        blocked_domains = set()
        for link in main.select('a.hse-doc-link__link[href]'):
            title = link.select_one('.hse-doc-link__title')
            label = title.get_text(' ', strip=True) if title else link.get_text(' ', strip=True)
            # Blank application forms do not contain role requirements. Keep every URL.
            item = {'label':label,'url':urljoin(str(response.url), link['href']),
                    'status':'FORMULARIO_NO_ANALIZADO' if 'application form' in label.lower() else 'PENDIENTE'}
            attachments.append(item)
            if item['status'] != 'PENDIENTE':
                continue
            try:
                if urlsplit(item['url']).netloc in blocked_domains:
                    raise IncompleteSource('Dominio de adjuntos suspendido tras restricción de acceso/robots')
                doc = self.client.get(item['url'], check_robots=True, accept='*/*')
                text = document_text(doc.content, item['url'])
                original.description += '\n\nDocumento: ' + label + '\nFuente: ' + item['url'] + '\n' + text
                item.update(status='EXTRAIDO',text_hash=digest(text),words=len(text.split()))
            except Exception as exc:
                from .http import AccessBlocked
                if isinstance(exc,AccessBlocked):
                    blocked_domains.add(urlsplit(item['url']).netloc)
                item.update(status='REVISION_MANUAL',error=str(exc)[:1000])
        original.raw['attachments'] = attachments
        required = [x for x in attachments if x['status'] != 'FORMULARIO_NO_ANALIZADO']
        original.detail_complete = bool(required) and all(x['status']=='EXTRAIDO' for x in required)
        if not original.detail_complete:
            original.raw['manual_review_reason'] = 'Ficha recuperada; documentación completa no acreditada. Revisar adjuntos/enlace externo.'
        return original


ADAPTERS = {'greenhouse':Greenhouse,'lever':Lever,'ashby':Ashby,'smartrecruiters':SmartRecruiters,'html':GenericHTML,'hse':HSE,'career_tabs':CareerTabs}

def make_adapter(source,client,profile):
    if source['kind'] not in ADAPTERS:
        raise NotImplementedError('Fuente de importación manual o conector no implementado')
    return ADAPTERS[source['kind']](source,client,profile)
