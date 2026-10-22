import csv
import io
import json
from urllib.parse import urlsplit
from pypdf import PdfReader
from docx import Document
from .models import Job
from .config import digest, now
from .sources import upsert_source
from .repository import save_job
from .parsers import jobpostings
from .analysis import analyze_job
from .http import AccessBlocked

def manual_source(db, url):
    source = {'id':'manual','name':'Importación manual','kind':'manual','url':url,
              'enabled':False,'permission':'IMPORTACION_USUARIO','status':'MANUAL',
              'notes':'Contenedor local de registros aportados por el usuario; URL de una importación, sin rastreo automático'}
    upsert_source(db,source)
    return source['id']

def import_url(db,url,client,profile,run_id=None):
    p = urlsplit(url)
    if p.scheme not in {'http','https'} or not p.hostname or p.username or p.password:
        raise ValueError('Solo se aceptan URLs públicas HTTP(S)')
    if p.hostname == 'linkedin.com' or p.hostname.endswith('.linkedin.com'):
        raise ValueError('LinkedIn está excluido')
    source_id = manual_source(db, url)
    from .discovery import diagnose_omission, restricted_source
    diagnosis=diagnose_omission(db,url)
    job = Job(external_id=digest(url),title='Título pendiente de recuperación',url=url)
    job_id = save_job(db,source_id,job,run_id,profile)
    known = db.rows('SELECT id FROM sources WHERE url LIKE ? AND id<>?',('%'+p.hostname+'%',source_id))
    db.event('INVESTIGAR_OMISION',diagnosis,run_id,job_id)
    try:
        if restricted_source(db,url):
            raise AccessBlocked('Condiciones de reproducción pendientes de permiso; abrir el enlace original')
        response = client.get(url,check_robots=True,accept='text/html')
        jobs,malformed = jobpostings(response.text,str(response.url))
        if not jobs or malformed:
            raise ValueError('No se recuperó JobPosting íntegro; pegar/importar texto autorizado y revisar manualmente')
        ids = []
        for i,found in enumerate(jobs):
            found.external_id = digest(url) if i == 0 else digest(url)+f':{i}'
            ids.append(save_job(db,source_id,found,run_id,profile))
        for found_id in ids:
            analyze_job(db,found_id,profile)
        return ids
    except Exception as exc:
        db.error(source_id,type(exc).__name__,str(exc),run_id,job_id)
        db.execute("UPDATE jobs SET open_status=?,analysis_status='REVISIÓN_MANUAL' WHERE id=?",
                   ('ACCESS_BLOCKED' if isinstance(exc,AccessBlocked) else 'UNKNOWN',job_id))
        return [job_id]

def import_csv(db,text,profile):
    reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    required = {'title','url'}
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
        raise ValueError('CSV requiere columnas title,url; opcionales company,location,description,detail_complete,external_id,apply_url')
    ids = []
    for row in reader:
        if not row.get('url'):
            db.event('CSV_INVALID_ROW',{'reason':'Falta URL; registro no importable','line':reader.line_num})
            continue
        p = urlsplit(row['url'])
        if p.scheme not in {'http','https'} or not p.hostname or 'linkedin.com' in p.hostname:
            db.event('CSV_INVALID_ROW',{'reason':'URL no permitida','line':reader.line_num})
            continue
        source_id = manual_source(db,row['url'])
        job = Job(external_id=row.get('external_id') or digest(row['url']),title=row.get('title') or 'Título no indicado',
                  company=row.get('company') or 'No indicado por la empresa',location=row.get('location') or 'No indicado por la empresa',
                  url=row['url'],description=row.get('description') or '',apply_url=row.get('apply_url') or None,
                  detail_complete=row.get('detail_complete','').lower() in {'1','true','yes'},
                  raw={'manual_import':True,'imported_at':now()})
        job_id = save_job(db,source_id,job,profile=profile)
        analyze_job(db,job_id,profile)
        ids.append(job_id)
    return ids

def cv_skills(file_bytes, filename):
    stream = io.BytesIO(file_bytes)
    if filename.lower().endswith('.pdf'):
        text = '\n'.join(page.extract_text() or '' for page in PdfReader(stream).pages)
    elif filename.lower().endswith('.docx'):
        text = '\n'.join(p.text for p in Document(stream).paragraphs)
    else:
        raise ValueError('Formato no admitido; usar PDF o DOCX')
    import re
    candidates = ['Python','Java','JavaScript','SQL','HTML','CSS','Git','Windows','Linux','Active Directory',
                  'Microsoft 365','DAM','warehouse','stock','HVAC']
    return [skill for skill in candidates if re.search(r'(?<!\w)'+re.escape(skill)+r'(?!\w)',text,re.I)]
