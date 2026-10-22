import json
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .models import Job
from .normalization import clean_html, date_iso
from .config import digest

def jobpostings(html_text, base_url):
    soup = BeautifulSoup(html_text, 'lxml')
    found = []
    def walk(value):
        if isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            types = value.get('@type', [])
            types = [types] if isinstance(types,str) else types
            if 'JobPosting' in types:
                found.append(value)
            for key in ('@graph','mainEntity','itemListElement','item'):
                if key in value:
                    walk(value[key])
    malformed = 0
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            walk(json.loads(script.string or script.get_text()))
        except (ValueError, TypeError):
            malformed += 1
    if not found:
        # Algunas páginas oficiales usan microdatos schema.org, sin JSON-LD.
        for posting in soup.select('[itemscope][itemtype$="/JobPosting"]'):
            def prop(name, root=None):
                tag = (root or posting).select_one(f'[itemprop="{name}"]')
                return (tag.get('content') or tag.get('href') or tag.get_text(' ',strip=True)) if tag else None
            description = posting.select_one('[itemprop="description"]')
            company = posting.select_one('[itemprop="hiringOrganization"]')
            found.append({'@type':'JobPosting','title':prop('title'),'url':base_url,
                          'hiringOrganization':{'name':prop('name',company) if company else 'No indicado por la empresa'},
                          'description':str(description) if description else '',
                          'jobLocation':{'address':{k:prop(k) for k in ('addressLocality','addressRegion','addressCountry') if prop(k)}},
                          'datePosted':prop('datePosted'),'_format':'schema.org microdata'})
    jobs = []
    for raw in found:
        locations = raw.get('jobLocation', [])
        locations = locations if isinstance(locations,list) else [locations]
        names = []
        for loc in locations:
            address = loc.get('address', {}) if isinstance(loc,dict) else {}
            if isinstance(address,str):
                names.append(address)
            else:
                names.append(', '.join(str(address.get(k,'')) for k in
                                       ('streetAddress','addressLocality','addressRegion','addressCountry') if address.get(k)))
        remote = raw.get('jobLocationType') == 'TELECOMMUTE'
        if remote:
            eligible = raw.get('applicantLocationRequirements', [])
            eligible = eligible if isinstance(eligible,list) else [eligible]
            names.extend(x.get('name','') for x in eligible if isinstance(x,dict))
        employer = raw.get('hiringOrganization', {})
        identifier = raw.get('identifier', {})
        identifier = identifier.get('value') if isinstance(identifier,dict) else identifier
        url = urljoin(base_url, raw.get('url') or base_url)
        description = clean_html(raw.get('description',''))
        jobs.append(Job(external_id=str(identifier or digest(url)), title=raw.get('title') or 'Título no indicado',
                        company=employer.get('name','No indicado por la empresa') if isinstance(employer,dict) else str(employer),
                        location='; '.join(filter(None,names)) or 'No indicado por la empresa', url=url,
                        description=description, detail_complete=bool(description), posted_at=date_iso(raw.get('datePosted')),
                        mode='REMOTE' if remote else 'DESCONOCIDO', raw={'jsonld':raw, **raw}))
    return jobs, malformed
