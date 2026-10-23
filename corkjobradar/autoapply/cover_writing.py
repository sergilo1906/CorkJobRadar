"""Conservative, traceable wording proposals. Every proposal needs human review.

Only positively stated, recognised approved evidence activates a template.
Unknown wording falls back to the exact approved statement. No remote model.
"""
import re
from .professional_dossier import build_dossier, concepts


def _recognised(entry, start, terms):
    text = entry['approved_text']
    if not re.search(start, text, re.I): return False
    if re.search(r'\b(?:never|did not|have not|without experience|not used)\b', text, re.I): return False
    return all(re.search(pattern, text, re.I) for pattern in terms)


def propose_letter(candidate, job, plan):
    chosen = set(plan['selected_fact_ids'])
    entries = [e for e in build_dossier(candidate)['entries'] if e['fact_id'] in chosen]
    proposals = {}
    for entry in entries:
        text = entry['approved_text']; key = None; sentence = None
        if _recognised(entry, r'^Provided first.line', ('software','workstation','gathering symptoms','basic troubleshooting','escalat')):
            key = 'support'
            sentence = ('I provided first-line support for users, software and workstations, gathering symptoms, '
                        'performing basic troubleshooting, explaining solutions and escalating issues that needed deeper technical work.')
        elif _recognised(entry, r'^Tracked recurring', ('issues','documented','fixes','follow.up')):
            key = 'documentation'
            sentence = 'I tracked recurring issues, documented common fixes and kept follow-up actions clear.'
        elif _recognised(entry, r'^Supported non.technical', ('step.by.step','communicated progress','issues')):
            key = 'communication'
            sentence = 'I guided non-technical users step by step and communicated progress when problems could not be resolved immediately.'
        elif _recognised(entry, r'^Developed and maintained the company website', ('Astro','Tailwind CSS','TinaCMS')):
            key = 'website'
            sentence = 'I developed and maintained the company website with Astro, Tailwind CSS and TinaCMS.'
        elif _recognised(entry, r'^Java[;,]', (r'\bSQL\b','web development')):
            key = 'development'
            sentence = 'My technical knowledge includes Java, SQL and web development.'
        elif _recognised(entry, r'^Windows[;,]', ('Microsoft 365','Outlook','end.user')):
            key = 'tools'
            sentence = 'My use of Windows and Microsoft 365/Outlook is at end-user level.'
        elif _recognised(entry, r'^Foundational', ('Active Directory','networking','ticketing concepts')):
            key = 'foundation'
            sentence = 'My knowledge of Active Directory, networking and enterprise ticketing concepts is foundational.'
        elif _recognised(entry, r'^Java SE 11', ('Programming I','additional formal training','object.oriented fundamentals')):
            key = 'training'
            sentence = 'I have also undertaken additional formal training in Java programming and object-oriented fundamentals.'
        if key and key not in proposals:
            proposals[key] = {'text':sentence, 'fact_ids':[entry['fact_id']], 'source_texts':[text],
                              'concepts':entry['concepts'], 'review_required':True}

    # Group complementary evidence. Three needs/evidence links, not a recital of
    # the complete profile, with no repeated introductory boilerplate.
    groups = {'IT_SUPPORT': [('support',), ('documentation','communication'), ('tools','foundation')],
              'JUNIOR_DEVELOPER': [('website',), ('development','training'), ('documentation',)],
              'QA_TESTER': [('documentation',), ('support',), ('communication','development')]}
    family = plan['family']; blocks = []
    advertised = plan.get('duties', []) + [
        {'quote':r['quote'], 'concepts':concepts(r['quote'])} for r in plan.get('requirement_evidence', [])]
    for keys in groups[family]:
        available = [proposals[key] for key in keys if key in proposals]
        if not available: continue
        tags = set(t for p in available for t in p['concepts'])
        quotes = list(dict.fromkeys(d['quote'] for d in advertised if tags.intersection(d['concepts'])))[:2]
        blocks.append({'text':' '.join(p['text'] for p in available),
                       'fact_ids':list(dict.fromkeys(fid for p in available for fid in p['fact_ids'])),
                       'source_texts':[t for p in available for t in p['source_texts']],
                       'advertised_need_quotes':quotes, 'review_required':True})
    if not blocks:
        # Other users/profiles are not forced into these recognised templates.
        relevant = [e for e in entries if e['kind'] in {'responsibility','skill','education'}][:3]
        blocks = [{'text':e['approved_text'], 'fact_ids':[e['fact_id']], 'source_texts':[e['approved_text']],
                   'advertised_need_quotes':[], 'review_required':True} for e in relevant]
    if not blocks: raise ValueError('COVER_LETTER_EVIDENCE_REQUIRED')
    education = next((e for e in entries if e['kind']=='education' and e.get('completed') and
                      '(CFGS DAM)' in e['approved_text'] and 'final examination passed' in e['approved_text'] and
                      all(k in e['fields'] for k in ('institution','period'))), None)
    if education:
        f=education['fields'];block=blocks[min(1,len(blocks)-1)]
        block['text'] += (' I have completed my Higher Technician qualification in Multiplatform Application Development '
                          f'(CFGS DAM) at {f["institution"]["value"]} ({f["period"]["value"]}), with the final examination passed.')
        block['fact_ids'].append(education['fact_id']);block['source_texts'].append(education['approved_text'])

    # Use employment chronology only when it was explicitly present and parsed.
    employment = next((e for e in entries if e['kind'] == 'employment' and
                       all(k in e['fields'] for k in ('role','employer','from','to'))), None)
    role_sentence = None
    if employment:
        f = employment['fields']
        role_sentence = (f'I worked as a {f["role"]["value"]} at {f["employer"]["value"]} '
                         f'from {f["from"]["value"]} to {f["to"]["value"]}.')
        blocks[0]['text'] = role_sentence + ' ' + blocks[0]['text']
        blocks[0]['fact_ids'].insert(0, employment['fact_id'])
        blocks[0]['source_texts'].insert(0, employment['approved_text'])

    # A short role-specific connection uses only advertised, source-bound needs.
    connections = {
        'IT_SUPPORT': 'This background is relevant to the user support and communication duties described in your vacancy.',
        'JUNIOR_DEVELOPER': 'I would welcome discussing how this background relates to the development and quality responsibilities in your team.',
        'QA_TESTER': 'This experience offers a relevant foundation for discussing the issue investigation and documentation involved in the role.',
    }
    if any(block['advertised_need_quotes'] for block in blocks):
        blocks[-1]['text'] += ' ' + connections[family]
    lines = [candidate['full_name'], candidate['email'], 'Dear Hiring Team,',
             f'I am applying for the {job["title"]} position at {job["company"]}. '
             'I would like to bring the experience and technical background outlined below to your consideration.',
             *[block['text'] for block in blocks],
             'My CV provides further detail on my experience, qualifications and current skills. '
             'I would welcome the opportunity to discuss your requirements and how I could contribute to the advertised work. '
             'Thank you for considering my application.',
             'Kind regards,', candidate['full_name']]
    return {'lines':lines, 'fact_ids':list(dict.fromkeys(fid for block in blocks for fid in block['fact_ids'])),
            'links':blocks, 'word_count':len(' '.join(lines[2:]).split()), 'review_required':True,
            'writing_version':'GROUNDED_REVIEW_PROPOSALS_2', 'automatic_semantic_approval':False,
            'document_type':'CANDIDATE_COVER_LETTER_NOT_EMPLOYER_REFERENCE'}
