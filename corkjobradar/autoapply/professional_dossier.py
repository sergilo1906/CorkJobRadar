"""Versioned evidence model, derived conservatively from already approved facts.

No source PDF, reference letter or job advert can silently add a professional fact.
Extracted fields contain exact source substrings; absent fields remain unknown.
"""
import json
import re
from ..config import now
from .document_storage import encode, save_asset, read_asset
from .vault import candidate_snapshot

MODEL_VERSION = 'APPROVED_EVIDENCE_2'

# Concept families describe tasks, rather than ranking identical words. They do
# not assert that transferable experience fulfils a technical requirement.
CONCEPTS = {
    'user_support': r'first.line|help.?desk|service desk|user.{0,20}support|support.{0,35}user|gathering symptoms|step.by.step guidance|workstation',
    'diagnostics': r'troubleshoot|diagnos|gathering symptoms|incident|issues?|defects?|bugs?',
    'documentation': r'document|recurring|follow.up|knowledge base|reproduc|record.{0,15}(?:fix|issue)',
    'communication': r'non.technical|communicat|explain|guidance|stakeholder|customer',
    'development': r'\bJava\b|\bSQL\b|web development|website|Astro|Tailwind|TinaCMS|programming|object.oriented|software development|building features|develop(?:ing)? applications|coding|production code|writing code',
    'quality': r'test(?:ing|er| cases?)|quality assurance|\bQA\b|defect|bugs?|reproduc|regression|validat',
    'foundation': r'foundational|basic|concepts|fundamentals|end.user',
    'education': r'qualification|CFGS|\bDAM\b|degree|diploma',
}


def concepts(text):
    return [key for key, pattern in CONCEPTS.items() if re.search(pattern, text, re.I)]


def _field(text, start, end, fact_id):
    return {'value': text[start:end], 'fact_ids': [fact_id], 'span': [start, end]}


def build_dossier(candidate):
    entries = []; current_job = None
    for claim in candidate.get('_claims', []):
        text = claim['text_en']; fid = claim['id']; section = claim['section']
        entry = {'fact_id': fid, 'section': section, 'approved_text': text,
                 'concepts': concepts(text), 'evidence': {'fact_ids': [fid], 'source': 'APPROVED_FACT'},
                 'kind': {'Education':'education', 'Projects':'project', 'Skills':'skill',
                          'Languages':'language', 'Availability':'availability'}.get(section, 'statement'),
                 'fields': {}, 'review_pending': []}
        # Parse only explicit employment headings, not a guessed company from
        # technologies or a recommendation. Multi-employment association is sequential.
        heading = re.match(r'(?P<role>[^.;|]{3,100}?) at (?P<employer>[^();|]{2,100}?)\s*\(', text)
        if section in {'Experience', 'Additional Experience'} and heading:
            entry['kind'] = 'employment'; current_job = fid
            for key in ('role', 'employer'):
                entry['fields'][key] = _field(text, *heading.span(key), fid)
            period = re.search(r'(?P<from>(?:January|February|March|April|May|June|July|August|September|October|November|December) \d{4})\s*[-–]\s*(?P<to>(?:January|February|March|April|May|June|July|August|September|October|November|December) \d{4})', text)
            if period:
                for key in ('from', 'to'):
                    entry['fields'][key] = _field(text, *period.span(key), fid)
            else:
                entry['review_pending'].append('EMPLOYMENT_DATES_NOT_STRUCTURED')
            entry['review_pending'].append('LOCATION_NOT_SEPARATELY_APPROVED')
        elif section == 'Experience':
            entry['kind'] = 'responsibility'; entry['employment_fact_id'] = current_job
            if current_job is None:
                entry['review_pending'].append('EMPLOYMENT_ASSOCIATION_UNKNOWN')
        if section == 'Education':
            for key, pattern in [('institution', r'(?P<v>Institut Baix Camp)'),
                                 ('period', r'(?P<v>\b\d{4}[-–]\d{4}\b)')]:
                match = re.search(pattern, text)
                if match:
                    entry['fields'][key] = _field(text, *match.span('v'), fid)
            entry['completed'] = bool(re.search(r'\bcompleted\b', text, re.I))
            entry['equivalence'] = None  # Never derive Bachelor/NFQ8 from DAM.
        if section == 'Skills':
            entry['level'] = 'FOUNDATIONAL_OR_END_USER' if 'foundation' in entry['concepts'] else 'AS_APPROVED'
        if section == 'Languages':
            entry['cefr_equivalence'] = None
        if entry['kind'] == 'project':
            entry['approved_links'] = re.findall(r'https://[^\s<>]+', text)
        entries.append(entry)
    for entry in entries:
        if entry['kind'] == 'employment':
            entry['responsibility_fact_ids'] = [e['fact_id'] for e in entries if e.get('employment_fact_id') == entry['fact_id']]
            entry['proven_results'] = []  # A responsibility does not imply a quantified achievement.
            fields = entry['fields']
            if 'from' in fields and 'to' in fields:
                from datetime import datetime
                if datetime.strptime(fields['from']['value'], '%B %Y') > datetime.strptime(fields['to']['value'], '%B %Y'):
                    entry['review_pending'].append('EMPLOYMENT_DATES_CONTRADICTORY')
        if entry['kind'] == 'education' and 'period' in entry['fields']:
            start, end = re.split('[-–]', entry['fields']['period']['value'])
            if int(start) > int(end): entry['review_pending'].append('EDUCATION_DATES_CONTRADICTORY')
    return {'version': MODEL_VERSION, 'facts_hash': candidate['_cv_facts_hash'],
            'contact_fact_ids': candidate.get('_fact_ids', {}), 'entries': entries,
            'unapproved_source_material_included': False}


def sync_dossier(db):
    candidate = candidate_snapshot(db); dossier = build_dossier(candidate)
    raw = encode(dossier)
    with db.transaction() as con:
        if not con.in_transaction: con.execute('BEGIN IMMEDIATE')
        rows = db.rows('SELECT * FROM professional_dossiers WHERE facts_hash=? AND model_version=?',
                       (candidate['_cv_facts_hash'], MODEL_VERSION))
        if rows:
            if read_asset(db, rows[0]) != raw: raise ValueError('DOSSIER_DERIVATION_CHANGED')
            return rows[0], dossier
        path, sha = save_asset(db, raw, 'professional-dossier')
        did = db.execute('INSERT INTO professional_dossiers(facts_hash,model_version,encrypted_path,file_hash,created_at) VALUES(?,?,?,?,?)',
                         (candidate['_cv_facts_hash'], MODEL_VERSION, path, sha, now()))
        return db.rows('SELECT * FROM professional_dossiers WHERE id=?', (did,))[0], dossier
