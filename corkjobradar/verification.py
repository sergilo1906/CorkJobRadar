import json
import re
from datetime import datetime,time
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from .config import now
from .http import AccessBlocked

def deadline_state(raw,clock=None):
    """A date-only deadline lasts through that local day; explicit times retain their zone."""
    value=raw.get('validThrough') or raw.get('application_deadline')
    if not value and not raw.get('application_deadline_original'):
        # Some public ATS APIs put the ONLY closing date in their description.
        # Parse an explicit English day/month/year; never infer a year or a timezone
        # for ambiguous date-times. Date-only deadlines use the app's Dublin rule.
        description=raw.get('descriptionPlain') or raw.get('descriptionHtml') or ''
        if not isinstance(description,str):description=''
        text=BeautifulSoup(description,'lxml').get_text(' ',strip=True) if '<' in description else description
        labels=list(re.finditer(r'\b(?:closing date|application deadline|applications close)\s*:\s*([^\n.]{1,100})',text,re.I))
        if labels:
            dates=[]
            months={name.lower():i for i,name in enumerate(('January','February','March','April','May','June','July','August','September','October','November','December'),1)}
            for label in labels:
                match=re.match(r'(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(\d{4})\s*$',label[1].strip())
                try:
                    if not match:raise ValueError()
                    dates.append(datetime(int(match[3]),months[match[2].lower()],int(match[1])).date().isoformat())
                except (ValueError,KeyError):return 'UNPARSEABLE','Fecha límite textual pendiente de aclarar'
            if len(set(dates))!=1:return 'UNPARSEABLE','Fechas límite textuales contradictorias'
            value=dates[0]
    if not value:
        original=raw.get('application_deadline_original')
        return ('UNPARSEABLE',str(original)) if original else ('ABSENT',None)
    clock=clock or datetime.fromisoformat(now())
    try:
        value=str(value).strip()
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):
            instant=datetime.combine(datetime.fromisoformat(value).date(),time.max,ZoneInfo('Europe/Dublin'))
        else:
            instant=datetime.fromisoformat(value.replace('Z','+00:00'))
            if instant.tzinfo is None:
                if not raw.get('deadline_timezone'):return 'UNKNOWN_TIMEZONE',value
                zone=ZoneInfo(raw['deadline_timezone'])
                if instant.replace(tzinfo=zone,fold=0).utcoffset()!=instant.replace(tzinfo=zone,fold=1).utcoffset():return 'AMBIGUOUS_LOCAL_TIME',value
                instant=instant.replace(tzinfo=zone)
        return ('EXPIRED' if instant<clock else 'NOT_EXPIRED'),instant.isoformat()
    except (ValueError,TypeError,KeyError):return 'UNPARSEABLE',str(value)


def evidence_status(job,clock=None):
    text = job['description']
    raw = job.get('raw',{})
    if raw.get('_listing_type')=='BOLSA_DE_TALENTO_SIN_VACANTE_CONCRETA' or re.search(r'register your c\.?v\.?|talent communit|talent pool|future (?:roles|opportunities)',job.get('title',''),re.I):
        return 'UNKNOWN','Registro de talento/futuras oportunidades; no demuestra vacante concreta'
    if raw.get('active') is False:
        return 'CLOSED_CONFIRMED','API oficial indica active=false'
    closed = re.search(r'(?:this (?:job|position|vacancy|role) (?:is|has been) (?:closed|filled)|no longer accepting applications|applications (?:are|have) closed)',text,re.I)
    if closed:
        return 'CLOSED_CONFIRMED',closed[0]
    deadline_status,deadline=deadline_state(raw,clock)
    if deadline_status=='EXPIRED':return 'CLOSED_CONFIRMED',f'Fecha/hora límite publicada vencida: {deadline}'
    if job.get('description') and job.get('detail_complete'):
        return 'OPEN_LIKELY','Descripción visible en fuente; candidatura no verificada'
    return 'UNKNOWN','Datos insuficientes para determinar vigencia'

def record_verification(db,job_id,source_id,status,evidence):
    stamp = now()
    db.execute('INSERT INTO verification_events(job_id,source_id,checked_at,status,evidence) VALUES(?,?,?,?,?)',
               (job_id,source_id,stamp,status,evidence))
    db.execute('UPDATE jobs SET open_status=?,last_verified_at=? WHERE id=?',(status,stamp,job_id))

def verify_job(db,job_id,client):
    rows = db.rows('SELECT * FROM jobs WHERE id=?',(job_id,))
    job = rows[0]
    job['raw'] = json.loads(job['raw'])
    if evidence_status(job)[1].startswith('Registro de talento'):
        record_verification(db,job_id,None,'UNKNOWN','Bolsa de talento: no demuestra una vacante concreta, aunque exista formulario')
        return 'UNKNOWN'
    try:
        response = client.get(job.get('apply_url') or job['url'],check_robots=True,accept='text/html')
        soup = BeautifulSoup(response.text,'lxml')
        page_text = soup.get_text(' ',strip=True)
        status,evidence = evidence_status({**job,'description':page_text})
        if job['raw'].get('_career_section_id') and status!='CLOSED_CONFIRMED':
            from .normalization import normalized,clean_html
            titles=[t for t in soup.select('.elementor-tab-desktop-title[data-tab]') if normalized(t.get_text(' ',strip=True))==normalized(job['title'])]
            status,evidence='UNLISTED','La sección del puesto no figura en la página actual; no prueba cierre definitivo'
            if len(titles)==1:
                panel=soup.find(id=titles[0].get('aria-controls','MISSING'))
                if panel and clean_html(str(panel))==job['description']:
                    exact_option=any(normalized(job['title'])==normalized(o.get_text(' ',strip=True)) for o in soup.select('form select option'))
                    status,evidence=('OPEN_CONFIRMED','Sección del puesto vigente y opción exacta de selección en formulario visible; sin enviar') if exact_option else ('OPEN_LIKELY','Sección exacta del puesto visible; formulario de esa posición pendiente de confirmar')
                else:status,evidence='UNKNOWN','Sección o descripción cambiada; recuperar antes de usar la candidatura'
            record_verification(db,job_id,None,status,evidence)
            return status
        if status != 'CLOSED_CONFIRMED':
            form = soup.find('form')
            if form and form.find(['input','textarea']) and re.search(r'apply|application|resume|curriculum|submit application',form.get_text(' ',strip=True),re.I):
                status,evidence = 'OPEN_CONFIRMED','Formulario de candidatura visible con campos; no se ha enviado nada'
            else:
                status,evidence = 'OPEN_LIKELY','Anuncio visible; formulario dinámico o no confirmado'
        record_verification(db,job_id,None,status,evidence)
        return status
    except AccessBlocked as exc:
        record_verification(db,job_id,None,'ACCESS_BLOCKED',str(exc))
    except Exception as exc:
        record_verification(db,job_id,None,'UNKNOWN',str(exc)[:2000])
    return db.rows('SELECT open_status FROM jobs WHERE id=?',(job_id,))[0]['open_status']

def reconcile_absences(db,run_id,source_id):
    # Solo llamar una vez tras completar satisfactoriamente todas las páginas.
    with db.connect() as con:
        query=con.execute('SELECT query_signature FROM source_runs WHERE run_id=? AND source_id=?',(run_id,source_id)).fetchone()
        if not query or not query['query_signature']:
            return  # No historical query proof: absence cannot safely establish removal.
        con.execute('''UPDATE job_sources SET missing_successes=missing_successes+1 WHERE source_id=?
                    AND last_query_signature=?
                    AND external_id NOT IN (SELECT external_id FROM run_jobs WHERE run_id=? AND source_id=?)''',
                    (source_id,query['query_signature'],run_id,source_id))
        for row in con.execute('SELECT job_id FROM job_sources WHERE source_id=? AND last_query_signature=? AND missing_successes>=2',(source_id,query['query_signature'])):
            # Una procedencia todavía visible impide declarar ausencia de la vacante global.
            active = con.execute('SELECT 1 FROM job_sources WHERE job_id=? AND missing_successes<2',(row['job_id'],)).fetchone()
            if not active:
                con.execute("UPDATE jobs SET open_status='UNLISTED',last_verified_at=? WHERE id=?",(now(),row['job_id']))
                con.execute('INSERT INTO verification_events(job_id,source_id,checked_at,status,evidence) VALUES(?,?,?,?,?)',
                            (row['job_id'],source_id,now(),'UNLISTED','Ausente tras dos listados completos; no acredita cierre del mercado total'))
