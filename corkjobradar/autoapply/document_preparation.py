"""Resumable LOCAL drafts. No document approval, packet export or submission.

The existing selection queue supplies every assessed offer. Persisted immutable
versions are the recovery checkpoint; a later pass reuses current drafts and
never undoes a user's revocation of the same input version.
"""
import json
import re
from ..config import now
from ..worker import worker_lock
from .broad_selection import assess_selection
from .job_composition import COMPOSER_VERSION
from .job_documents import create_job_version, load_job_version
from .selection_queue import refresh_queue
from .vault import candidate_snapshot

PREPARATION_VERSION = 'LOCAL_REVIEW_DRAFTS_1'


def local_review_candidate(job, selection):
    """A locality hint allows drafting only; it never verifies a 50 km commute."""
    if not selection.get('preparation_allowed') or job['mode'] == 'REMOTE': return False
    geo = selection.get('geography', {}).get('state')
    if geo in {'REMOTE_SEPARATE', 'OUTSIDE_RADIUS'}: return False
    location = job['location'].strip()
    hint = re.search(r'\b(cork|ballinlough|cobh|midleton|carrigtwohill|ringaskiddy|little island|ballincollig|kinsale|mallow|fermoy|bandon|macroom|watergrasshill|glanmire|douglas)\b', location, re.I)
    unknown = not location or location.casefold() in {'unknown', 'not specified', 'ireland'}
    return bool(hint or unknown or geo == 'WITHIN_RADIUS')


def draft_review_rows(db):
    """Metadata for current drafts without a current approved export bundle.

    This count is separate from prepared applications. The export service still
    checks every permission, file and eligibility condition when a user acts.
    """
    facts = candidate_snapshot(db)['_facts_hash']
    rows = db.rows('''SELECT v.id,v.job_id,v.file_hash FROM job_document_versions v
        JOIN jobs j ON j.id=v.job_id
        WHERE v.id=(SELECT MAX(x.id) FROM job_document_versions x WHERE x.job_id=v.job_id)
        AND v.revoked_at IS NULL AND v.facts_hash=? AND v.job_content_hash=j.content_hash
        AND j.open_status<>'CLOSED_CONFIRMED'
        AND NOT EXISTS (SELECT 1 FROM it_application_queue q WHERE q.job_id=v.job_id
                        AND q.error_code='DOCUMENT_DRAFT_REVIEW_REQUIRED')
        AND NOT EXISTS (SELECT 1 FROM job_document_bundles b WHERE b.version_id=v.id
                        AND b.revoked_at IS NULL AND b.expires_at>?)
        ORDER BY v.id''', (facts, now()))
    from ..verification import deadline_state
    from .store import already_applied
    result=[]
    for row in rows:
        job=db.rows('SELECT * FROM jobs WHERE id=?',(row['job_id'],))[0]
        raw=json.loads(job['raw']) if isinstance(job['raw'],str) else job['raw']
        if deadline_state(raw)[0]!='EXPIRED' and not already_applied(db,job,'LIVE'):result.append(row)
    return result


def prepare_document_drafts(db, *, should_stop=None):
    counts = dict(assessed=0, candidates=0, created=0, reused=0, revoked=0,
                  held=0, skipped=0, external_requests=0, submitted=0)
    with worker_lock(db):
        report = refresh_queue(db)
        counts['assessed'] = report['jobs_processed']
        facts = candidate_snapshot(db)['_facts_hash']
        for item in report['offers']:
            if should_stop and should_stop():
                counts['paused'] = True; break
            candidate = candidate_snapshot(db)
            if candidate['_facts_hash'] != facts:
                counts['input_changed'] = True; break
            job = db.rows('SELECT * FROM jobs WHERE id=?', (item['job_id'],))[0]
            # Recheck policy and duplicates immediately before composing. HOLDs
            # for transport, academic acceptance or unknown answers remain HOLDs.
            selection = assess_selection(db, job, candidate)
            if not local_review_candidate(job, selection):
                counts['skipped'] += 1; continue
            counts['candidates'] += 1
            if not candidate.get('full_name') or not candidate.get('email') or not candidate.get('_claims'):
                counts['held'] += 1; continue
            versions = db.rows('SELECT * FROM job_document_versions WHERE job_id=? ORDER BY id DESC LIMIT 1', (job['id'],))
            latest = versions[0] if versions else None
            same_input = latest and latest['job_content_hash'] == job['content_hash'] and latest['facts_hash'] == facts
            if same_input and latest['revoked_at']:
                _clear_hold(db,job['id'])
                counts['revoked'] += 1; continue
            if same_input:
                try:
                    _, payload = load_job_version(db, latest['id'], require_latest=True)
                    if payload['plan']['composer_version'] == COMPOSER_VERSION:
                        _clear_hold(db,job['id'])
                        counts['reused'] += 1; continue
                except Exception as exc:
                    if str(exc) != 'JOB_DOCUMENT_DOSSIER_CHANGED':
                        # Preserve corrupt/missing evidence for review instead of
                        # silently replacing it with a newly generated document.
                        counts['held'] += 1
                        _hold(db,item)
                        continue
            try:
                create_job_version(db, job['id'], automatic=True)
                counts['created'] += 1
                _clear_hold(db,job['id'])
            except Exception as exc:
                if str(exc)=='USER_REVOKED_JOB_DOCUMENT_INPUT':
                    _clear_hold(db,job['id']);counts['revoked']+=1;continue
                # Do not log exception messages: renderers may include document text.
                counts['held'] += 1
                _hold(db,item)
        if candidate_snapshot(db)['_facts_hash'] != facts: counts['input_changed'] = True
    return counts


def _hold(db,item):
    db.execute("""UPDATE it_application_queue SET error_code='DOCUMENT_DRAFT_REVIEW_REQUIRED'
        WHERE job_id=? AND binding_hash=? AND workflow_state IN ('PENDING','INTERVENTION')""", (item['job_id'], item['binding_hash']))


def _clear_hold(db,job_id):
    db.execute("UPDATE it_application_queue SET error_code=NULL WHERE job_id=? AND error_code='DOCUMENT_DRAFT_REVIEW_REQUIRED'", (job_id,))
