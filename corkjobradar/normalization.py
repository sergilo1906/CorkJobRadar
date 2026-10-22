import re
import html
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from bs4 import BeautifulSoup
from zoneinfo import ZoneInfo

def clean_html(value):
    soup = BeautifulSoup(html.unescape(html.unescape(str(value or ''))), 'lxml')
    for tag in soup(['script', 'style', 'noscript', 'iframe']):
        tag.decompose()
    return '\n'.join(line.strip() for line in soup.get_text('\n').splitlines() if line.strip())

def canonical_url(value):
    p = urlsplit(value.strip())
    query = [(k,v) for k,v in parse_qsl(p.query, keep_blank_values=True)
             if not k.lower().startswith('utm_') and k.lower() not in {'source','ref','lever-source'}]
    gh=[v for k,v in query if k=='gh_jid']
    if gh and len(set(gh))==1 and re.fullmatch(r'\d{1,20}',gh[0]):
        query=[(k,v) for k,v in query if k!='gh_jid']+[('gh_jid',gh[0])]
    path = p.path.rstrip('/') or '/'
    # SmartRecruiters añade un slug editorial tras el ID público estable.
    if (p.hostname or '').lower()=='jobs.smartrecruiters.com':
        path = re.sub(r'^(/[^/]+/\d+)-[^/]+$',r'\1',path)
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), path, urlencode(sorted(query)), ''))

def normalized(value):
    return re.sub(r'\s+', ' ', value.casefold()).strip()


def job_identity_url(job):
    """Internal identity only: distinct published roles may share one careers page."""
    import json
    raw=job.get('raw',{})
    raw=json.loads(raw) if isinstance(raw,str) else raw
    base=canonical_url(job['url']);section=raw.get('_career_section_id')
    return base+'#career-section='+str(section) if section else base

def date_iso(value):
    if not value:
        return None
    try:
        if isinstance(value, (float, int)):
            d = datetime.fromtimestamp(value / 1000, tz=ZoneInfo('UTC'))
        else:
            d = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
            if d.tzinfo is None:
                return str(value)  # Fecha publicada sin inventar hora/zona.
        return d.astimezone(ZoneInfo('Europe/Dublin')).isoformat()
    except (ValueError, OverflowError, OSError):
        return None

def category(title, department=''):
    text = normalized(title + ' ' + department)
    if re.search(r'\b(it|helpdesk|service desk|desktop support|software|developer|cyber|cybersecurity|soc analyst|devops|data engineer|qa engineer|technical support|application support|network engineer|systems engineer|test engineer|computer)\b', text):
        return 'IT'
    if re.search(r'warehouse|picker|packer|stockroom|inventory|dispatch|goods (in|out)|logistics', text):
        return 'Almacen'
    if re.search(r'production|manufacturing|product builder|cleanroom|assembly|packaging|general operative', text):
        return 'Produccion'
    if re.search(r'hvac|ventilation|maintenance|apprentice|technician|installation|field service', text):
        return 'Tecnicos'
    return 'Otras'

def salary(text):
    # Solo euros con unidad explícita; no convertir salarios por horas supuestas.
    pattern = r'(?:€|EUR\s*)\s*(\d[\d,.]*(?:\s*k)?)(?:\s*(?:[-–]|to)\s*(?:€|EUR)?\s*(\d[\d,.]*(?:\s*k)?))?\s*(?:gross\s*)?(?:per\s*|/|a\s*)\s*(hour|hr|annum|year|annual)'
    m = re.search(pattern, text, re.I)
    if not m:
        return None
    def number(s):
        s = s.replace(' ', '').lower()
        multiplier = 1000 if 'k' in s else 1
        s = s.replace('k','')
        if re.fullmatch(r'\d{1,3}(,\d{3})+(\.\d+)?', s):
            s = s.replace(',','')
        elif ',' in s and '.' not in s:
            s = s.replace(',','.')
        return float(s) * multiplier
    return {'min': number(m[1]), 'max': number(m[2] or m[1]),
            'currency': 'EUR', 'unit': 'hora' if m[3].lower() in {'hour','hr'} else 'año',
            'quote': m[0], 'gross': True if re.search('gross', m[0], re.I) else None}

def shifts(text):
    patterns = {'lunes_viernes': r'monday\s*(?:to|[-–])\s*friday',
                'fines_semana': r'weekends?|saturday|sunday',
                'noches': r'night shifts?|night work|overnight',
                'rotacion': r'rotating|rotation|rotational',
                'guardias': r'on.call|standby', 'diurno': r'day shift|daytime'}
    return {key: m[0] for key, pat in patterns.items() if (m := re.search(pat, text, re.I))}
