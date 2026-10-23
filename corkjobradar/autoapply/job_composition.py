"""Local evidence selection and reviewable writing, never a grant of eligibility.

Capability relationships cover support/diagnostics/documentation/development;
exact tool identity and qualification level remain separate conservative checks.
All new connective wording requires document review, including generated summaries.
"""
import re
from ..config import digest
from ..passages import source_passages
from .it_scope import require_it_job
from .manual_requirements import checklist
from .professional_dossier import build_dossier, concepts

COMPOSER_VERSION = 'EVIDENCE_COMPOSER_4'
SECTION_ALIASES = {'what you will be doing':'duties', 'what you will do':'duties',
                   'what we are looking for':'mandatory', 'what you will gain':'benefits',
                   'nice to have':'desirable', 'why join netgear':'context', 'company statement':'context',
                   'role overview':'context', 'key details':'context'}
FAMILIES = {'IT_SUPPORT': 'IT Support | Helpdesk | Service Desk',
            'JUNIOR_DEVELOPER': 'Junior Developer | Software Development',
            'QA_TESTER': 'Junior QA | Software Testing'}
WEIGHTS = {
    'IT_SUPPORT': {'user_support': 6, 'communication': 4, 'documentation': 3, 'diagnostics': 3, 'foundation': 2},
    'JUNIOR_DEVELOPER': {'development': 9, 'documentation': 3, 'diagnostics': 2, 'education': 3},
    'QA_TESTER': {'documentation': 7, 'diagnostics': 5, 'development': 3, 'quality': 6, 'communication': 2},
}
TOOLS = ('JavaScript', 'Java', 'SQL', 'Python', 'Windows', 'macOS', 'Linux', 'Microsoft 365',
         'Outlook', 'Active Directory', 'Azure', 'AWS', 'Intune', 'Selenium', 'Playwright',
         'Astro', 'Tailwind', 'TinaCMS', 'GitHub', 'Firebase', 'TCP/IP', 'C#',
         'Kotlin', 'Swift', 'Android', 'iOS', 'CI/CD', 'Git', 'REST', 'React Native', 'Flutter')


def family_for(job):
    title = job['title']
    if re.search(r'\b(?:QA|tester|testing|quality assurance)\b', title, re.I): return 'QA_TESTER'
    if re.search(r'developer|programmer|software engineer', title, re.I): return 'JUNIOR_DEVELOPER'
    return 'IT_SUPPORT'


def tool_names(text):
    # Java is not JavaScript; Windows knowledge is not macOS proficiency.
    return [t for t in TOOLS if re.search(r'(?<![\w])' + re.escape(t) + r'(?![\w])', text, re.I)]


def _summary(candidate, family, selected):
    claims = {c['id']: c for c in candidate['_claims']}
    ids = lambda tag: [fid for fid in selected if tag in concepts(claims[fid]['text_en'])]
    support, documentation, development = ids('user_support'), ids('documentation'), ids('development')
    if family == 'IT_SUPPORT' and support and documentation:
        text = ('IT support background with first-line user assistance, issue documentation '
                'and follow-up of technical problems.')
        evidence = list(dict.fromkeys(support[:1] + documentation[:1]))
    elif family == 'JUNIOR_DEVELOPER' and development:
        text = 'Background in IT support and web development, with Java and SQL knowledge.'
        # Gate every phrase on actual evidence, not the requested job title.
        all_text = ' '.join(claims[i]['text_en'] for i in selected)
        if not support or not all(t in tool_names(all_text) for t in ('Java', 'SQL')) or not re.search(r'web development|website', all_text, re.I):
            return None
        evidence = list(dict.fromkeys(support[:1] + development))
    elif family == 'QA_TESTER' and documentation:
        text = ('IT support background with experience documenting recurring issues, '
                'investigating software problems and keeping follow-up actions clear.')
        if not support: return None
        diagnostics = ids('diagnostics')
        if not diagnostics: return None
        evidence = list(dict.fromkeys(support[:1] + documentation[:1] + diagnostics[:1]))
    else:
        return None
    return {'text': text, 'fact_ids': evidence, 'kind': 'NEW_WORDING_REQUIRES_REVIEW',
            'review_required': True, 'template': family + '_1'}


def compose_plan(db, job, candidate, *, family=None):
    require_it_job(job)
    if not candidate.get('full_name') or not candidate.get('email') or not candidate.get('_claims'):
        raise ValueError('VERIFIED_CONTACT_AND_CLAIMS_REQUIRED')
    family = family or family_for(job)
    if family not in FAMILIES: raise ValueError('UNSUPPORTED_DOCUMENT_FAMILY')
    dossier = build_dossier(candidate); entries = dossier['entries']; weights = WEIGHTS[family]
    passages, _ = source_passages(job['description'],section_aliases=SECTION_ALIASES)
    duties = [{'quote': p['text'].strip(), 'offset': p['offset'], 'concepts': concepts(p['text'])}
              for p in passages if p['section'] == 'duties']
    requirements = checklist(db, job, candidate,section_aliases=SECTION_ALIASES)
    needs = set(tag for d in duties for tag in d['concepts'])
    for item in requirements: needs.update(concepts(item['quote']))
    def score(entry):
        return sum(weights.get(t, 0) + (2 if t in needs else 0) for t in entry['concepts'])
    selected = set(); reasons = {}
    for entry in entries:
        mandatory = (entry['kind'] in {'employment', 'language', 'availability'} or
                     (entry['kind'] == 'education' and 'education' in entry['concepts']))
        if mandatory:
            selected.add(entry['fact_id']); reasons[entry['fact_id']] = 'Chronology, qualification, language or availability retained.'
    # Select relevant responsibilities within each employer, preserving headers
    # and chronology. Do not transfer an unassociated bullet to a different job.
    employers = [e for e in entries if e['kind'] == 'employment']
    for employer in employers:
        bullets = [e for e in entries if e.get('employment_fact_id') == employer['fact_id']]
        for entry in sorted(bullets, key=lambda e: -score(e))[:3]:
            if score(entry):
                selected.add(entry['fact_id']); reasons[entry['fact_id']] = 'Relevant responsibility at this employer; original wording retained.'
    for kind, limit in (('skill', 3), ('project', 2)):
        matching = [e for e in entries if e['kind'] == kind and score(e) > 0]
        for entry in sorted(matching, key=lambda e: -score(e))[:limit]:
            selected.add(entry['fact_id']); reasons[entry['fact_id']] = 'Accredited capability relevant to this role family and advertised needs.'
    # Java training may matter to a developer but need not occupy a support CV.
    if family == 'JUNIOR_DEVELOPER':
        for e in entries:
            if e['kind'] == 'education' and 'development' in e['concepts']:
                selected.add(e['fact_id']); reasons[e['fact_id']] = 'Relevant programming training; no certification inferred.'
    if not selected: raise ValueError('NO_ACCREDITED_CONTENT_FOR_DOCUMENT')
    # Keep duplicate statements in the master dossier but only once in this CV.
    seen_text = {}; duplicate_of = {}
    for entry in entries:
        fid = entry['fact_id']
        if fid not in selected: continue
        normalized = re.sub(r'[^\w]+', ' ', entry['approved_text'].casefold()).strip()
        if normalized in seen_text and entry['kind'] not in {'employment', 'education'}:
            selected.remove(fid); duplicate_of[fid] = seen_text[normalized]
        else: seen_text[normalized] = fid
    evidence_map = []
    for req in requirements:
        tags = set(concepts(req['quote'])); tools = tool_names(req['quote'])
        evidence = [e for e in entries if tags.intersection(e['concepts']) or
                    set(tools).intersection(tool_names(e['approved_text']))]
        known_tools = set(t for e in evidence for t in tool_names(e['approved_text']))
        missing_tools = [t for t in tools if t not in known_tools]
        evidence_map.append({**req, 'related_fact_ids': [e['fact_id'] for e in evidence],
            'tools_not_accredited': missing_tools,
            'relationship': 'USER_VERIFIED' if req['reviewed_at'] else 'RELEVANT_EVIDENCE_REQUIRES_REVIEW' if evidence else 'NO_EVIDENCE',
            'limitation': 'Related tasks are not proof of tool proficiency, years, degree equivalence or full compliance.'})
    # Explicit entries from pre-existing approved Profile claims are allowed;
    # no unapproved PDF text ever enters this selection.
    ordered = [e['fact_id'] for e in entries if e['fact_id'] in selected]
    summary = _summary(candidate, family, ordered)
    priorities = sorted([(e['fact_id'], score(e)) for e in entries if e['fact_id'] in selected], key=lambda x: -x[1])
    return {'composer_version': COMPOSER_VERSION, 'job_id': job['id'], 'job_content_hash': job['content_hash'],
            'family': family, 'headline': 'Target role: ' + FAMILIES[family],
            'selected_fact_ids': ordered, 'omitted_fact_ids': [e['fact_id'] for e in entries if e['fact_id'] not in selected],
            'selection_reasons': reasons, 'summary': summary, 'requirement_evidence': evidence_map,
            'duties': duties, 'priorities': priorities, 'human_wording_review_required': True,
            'eligibility_granted': False, 'source_facts_hash': candidate['_cv_facts_hash'],
            'master_fact_ids': [e['fact_id'] for e in entries],
            'duplicate_fact_ids_retained_in_master': duplicate_of,
            'unstructured_content_held': [e['fact_id'] for e in entries if e['kind'] == 'responsibility' and not e.get('employment_fact_id')]}


def selected_sections(candidate, plan):
    from .cv_layout import cv_sections
    chosen = set(plan['selected_fact_ids'])
    selected = {**candidate, '_claims': [c for c in candidate['_claims'] if c['id'] in chosen]}
    sections = cv_sections(selected)
    ranks = dict(plan['priorities'])
    by_text = {c['text_en']: ranks.get(c['id'], 0) for c in selected['_claims']}
    # Same employer and exact approved wording, with the relevant bullets first.
    entries = build_dossier(candidate)['entries']
    experience = []
    for employment in [e for e in entries if e['kind'] == 'employment' and e['section'] == 'Experience']:
        if employment['fact_id'] in chosen:
            experience.append(employment['approved_text'])
            bullets = [e for e in entries if e.get('employment_fact_id') == employment['fact_id'] and e['fact_id'] in chosen]
            experience.extend(e['approved_text'] for e in sorted(bullets, key=lambda e: -ranks.get(e['fact_id'], 0)))
    adapted = []
    for label, values in sections:
        if label == 'Experience' and experience: values = experience
        elif label in {'Core Capabilities', 'Selected Projects'}:
            values = sorted(values, key=lambda text: -by_text.get(text, 0))
            if label == 'Core Capabilities':
                def category(text):
                    if 'foundation' in concepts(text) and re.search(r'Active Directory|network|ticketing', text, re.I): return 'FOUNDATIONAL KNOWLEDGE'
                    if 'development' in concepts(text): return 'DEVELOPMENT'
                    return 'SYSTEMS & TOOLS'
                # Category headings are presentation, not replacements for facts.
                values = [category(text) + ': ' + text for text in values]
        adapted.append((label, values))
    sections = adapted
    if plan.get('summary'):
        sections = [('Professional Profile', [plan['summary']['text']])] + [(k, v) for k, v in sections if k != 'Professional Profile']
    return sections


def render_variant(candidate, plan, extension, *, max_pages=1):
    from .cv_layout import render_composed_cv
    from .documents import validate_document
    current = {c['id']: c for c in candidate['_claims']}
    ids = plan['selected_fact_ids']
    if plan['source_facts_hash'] != candidate['_cv_facts_hash'] or not set(ids).issubset(current):
        raise ValueError('COMPOSITION_FACTS_CHANGED')
    raw = render_composed_cv(candidate, selected_sections(candidate, plan), plan['headline'], extension, max_pages=max_pages)
    text = ' '.join(validate_document(raw, extension).split())
    for fid in ids:
        if ' '.join(current[fid]['text_en'].split()) not in text:
            raise ValueError('SELECTED_FACT_LOST_IN_RENDER')
    for field in ('full_name', 'email', 'phone', 'location', 'linkedin_url'):
        if candidate.get(field) and candidate[field] not in text:
            raise ValueError('APPROVED_CONTACT_LOST_IN_RENDER')
    return raw


def cover_letter_content(candidate, job, plan):
    from .cover_writing import propose_letter
    return propose_letter(candidate, job, plan)


def render_cover_letter(candidate, letter, extension):
    from .documents import _render_lines, validate_document
    approved_ids = {c['id'] for c in candidate['_claims']}
    if not set(letter['fact_ids']).issubset(approved_ids):
        raise ValueError('COVER_LETTER_FACTS_CHANGED')
    raw = _render_lines(letter['lines'], {**candidate, '_claims': []}, extension)
    text = ' '.join(validate_document(raw, extension).split())
    if any(' '.join(line.split()) not in text for line in letter['lines']):
        raise ValueError('COVER_LETTER_WORDING_LOST_IN_RENDER')
    return raw
