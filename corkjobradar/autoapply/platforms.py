"""Capabilities are code-owned, never inferred from a job page or a policy whitelist."""
from urllib.parse import urlsplit
import re
import hashlib

GREENHOUSE_HOSTS={'boards.greenhouse.io','job-boards.greenhouse.io','job-boards.eu.greenhouse.io'}


def platform_for(url):
    host=urlsplit(url).hostname
    if host in GREENHOUSE_HOSTS:
        return {'id':'greenhouse','version':'greenhouse-schema-2','verified':False,
                'automation_permitted':False,'inspection_supported':True,'preparation_supported':True,'hosted_form_verified':False,'live_supported':False}
    if host in {'jobs.lever.co','jobs.eu.lever.co'}:
        return {'id':'lever','version':'lever-hosted-inspect-1','verified':False,
                'automation_permitted':False,'inspection_supported':True,'preparation_supported':True,'hosted_form_verified':False,'live_supported':False}
    from .recruitee import tenant_host,VERSION
    if tenant_host(host):
        return {'id':'recruitee','version':VERSION,'verified':False,'automation_permitted':False,
                'inspection_supported':True,'preparation_supported':True,'hosted_form_verified':False,
                'api_submission_verified':False,'live_supported':False}
    return {'id':'unsupported','version':'none','verified':False,'automation_permitted':False,'live_supported':False}


def inspect_greenhouse(url,client):
    parsed=urlsplit(url)
    if parsed.scheme!='https' or parsed.hostname not in GREENHOUSE_HOSTS or parsed.username or parsed.password or parsed.port not in {None,443}:
        raise ValueError('UNSUPPORTED_GREENHOUSE_URL')
    match=re.fullmatch(r'/([a-zA-Z0-9_-]+)/jobs/(\d+)/?',parsed.path)
    if not match:raise ValueError('GREENHOUSE_POSTING_ID_REQUIRED')
    board,posting=match.groups()
    endpoint=f'https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{posting}?questions=true'
    response=client.get(endpoint,check_robots=True);response.raise_for_status();data=response.json()
    if str(data.get('id'))!=posting or not isinstance(data.get('questions'),list):raise ValueError('GREENHOUSE_SCHEMA_CHANGED')
    return {'platform':'greenhouse','adapter':'greenhouse-readonly-1','public_url':url,'endpoint':endpoint,
            'published_absolute_url':data.get('absolute_url'),
            'response_sha256':hashlib.sha256(response.content).hexdigest(),
            'posting_id':posting,'title':data.get('title'),'location':data.get('location'),
            'questions':data['questions'],'location_questions':data.get('location_questions',[]),
            'compliance':data.get('compliance'),
            'data_compliance':data.get('data_compliance',[]),'demographic_questions':data.get('demographic_questions'),
            'inspected_read_only':True,'submitted':False,'live_supported':False,
            'limitation':'GET público documentado. POST requiere credenciales de la empresa; no implica permiso para automatizar formularios alojados.'}


def greenhouse_offline_fixture(schema):
    """Render a LOCAL schema regression fixture; this is not the hosted Greenhouse DOM."""
    from html import escape
    parts=['<!doctype html><meta charset="utf-8"><h1>OFFLINE SCHEMA FIXTURE ONLY</h1><form method="post" action="/thanks">']
    for question in schema['questions']:
        fields=question.get('fields',[])
        # A resume file satisfies the documented file-or-text alternative.
        selected=[next(f for f in fields if f['type']=='input_file')] if any(f['type']=='input_file' for f in fields) else fields
        for f in selected:
            name=escape(f['name'],quote=True);label=escape(question['label'])
            required=' required' if question.get('required') else ''
            parts.append(f'<label for="{name}">{label}</label>')
            if f['type']=='input_file':parts.append(f'<input type="file" id="{name}" name="{name}"{required}>')
            elif f['type']=='input_text':parts.append(f'<input type="text" id="{name}" name="{name}"{required}>')
            elif f['type']=='textarea':parts.append(f'<textarea id="{name}" name="{name}"{required}></textarea>')
            elif f['type']=='multi_value_single_select':
                parts.append(f'<select id="{name}" name="{name}"{required}><option value="">Choose</option>')
                for option in f.get('values',[]):parts.append('<option value="'+escape(str(option['value']),quote=True)+'">'+escape(option['label'])+'</option>')
                parts.append('</select>')
            else:raise ValueError('UNSUPPORTED_GREENHOUSE_SCHEMA_FIELD')
    for index,consent in enumerate(schema.get('data_compliance',[])):
        for flag in ('requires_processing_consent','requires_retention_consent'):
            if consent.get(flag):
                name=f'legal_{index}_{flag}'
                parts.append(f'<label for="{name}">Synthetic fixture legal consent: {flag}</label><input type="checkbox" id="{name}" required>')
    parts.append('<button type="submit">Submit application</button></form>')
    return ''.join(parts)
