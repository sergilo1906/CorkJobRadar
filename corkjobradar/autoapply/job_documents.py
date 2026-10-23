"""Versioned per-vacancy reviews and explicit, export-only document bundles.

This module contains no HTTP client, browser actor, submission or LIVE switch.
Approval of a bundle cannot approve the general CV or an AutoApply policy.
"""
import base64
import hashlib
import io
import json
import zipfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from ..config import now, digest
from .document_storage import encode, save_asset, read_asset
from .documents import validate_document, document_bytes
from .job_composition import compose_plan, render_variant, cover_letter_content, render_cover_letter
from .professional_dossier import sync_dossier
from .reference_library import reference_bytes
from .vault import candidate_snapshot

_UNSET=object()


def _job(db, jid):
    from .handoff import _job as get_job
    return get_job(db, jid)


def _event(db, kind, *, job_id=None, version_id=None, bundle_id=None, **details):
    # Metadata only. No names, contact details, source passages or document text.
    db.execute('INSERT INTO job_document_events(job_id,version_id,bundle_id,kind,created_at,details) VALUES(?,?,?,?,?,?)',
               (job_id, version_id, bundle_id, kind, now(), json.dumps(details, sort_keys=True)))


def create_job_version(db, job_id, *, family=None, max_pages=1, automatic=False):
    """Generate PDF AND DOCX for review. Does not approve either document."""
    candidate = candidate_snapshot(db); job = _job(db, job_id)
    dossier_row, dossier = sync_dossier(db)
    plan = compose_plan(db, job, candidate, family=family)
    letter = cover_letter_content(candidate, job, plan)
    files = {}
    for kind in ('CV', 'COVER_LETTER'):
        for ext in ('pdf', 'docx'):
            raw = (render_variant(candidate, plan, ext, max_pages=max_pages) if kind == 'CV'
                   else render_cover_letter(candidate, letter, ext))
            name = kind + '.' + ext
            files[name] = {'base64': base64.b64encode(raw).decode('ascii'),
                           'sha256': hashlib.sha256(raw).hexdigest()}
    payload = {'version': 1, 'job_id': job_id, 'job_content_hash': job['content_hash'],
               'title': job['title'], 'company': job['company'],
               'facts_hash': candidate['_facts_hash'], 'cv_facts_hash': candidate['_cv_facts_hash'],
               'dossier_hash': dossier_row['file_hash'], 'plan': plan, 'letter': letter,
               'max_pages': max_pages, 'files': files, 'approved': False,
               'review_required': ['CONTENT', 'NEW_WORDING', 'LAYOUT', 'SELECTED_FORMAT'],
               'master_fact_ids': [e['fact_id'] for e in dossier['entries']]}
    payload['chronology_conflicts'] = [e['fact_id'] for e in dossier['entries']
                                     if any('CONTRADICTORY' in code for code in e['review_pending'])]
    with db.transaction() as con:
        if not con.in_transaction: con.execute('BEGIN IMMEDIATE')
        if candidate['_facts_hash'] != candidate_snapshot(db)['_facts_hash'] or job != _job(db, job_id):
            raise ValueError('COMPOSITION_INPUT_CHANGED')
        if automatic:
            latest=db.rows('SELECT * FROM job_document_versions WHERE job_id=? ORDER BY id DESC LIMIT 1',(job_id,))
            if latest and latest[0]['revoked_at'] and latest[0]['facts_hash']==candidate['_facts_hash'] and latest[0]['job_content_hash']==job['content_hash']:
                raise PermissionError('USER_REVOKED_JOB_DOCUMENT_INPUT')
            from .broad_selection import assess_selection
            selected=assess_selection(db,job,candidate)
            if not selected['preparation_allowed'] or selected['geography']['state']=='REMOTE_SEPARATE':
                raise PermissionError('AUTOMATIC_DRAFT_SELECTION_CHANGED')
        path, sha = save_asset(db, encode(payload), 'job-documents')
        rows = db.rows('SELECT id FROM job_document_versions WHERE job_id=? AND file_hash=?', (job_id, sha))
        if rows: return rows[0]['id']
        vid = db.execute('''INSERT INTO job_document_versions(job_id,job_content_hash,facts_hash,dossier_hash,encrypted_path,file_hash,created_at)
                            VALUES(?,?,?,?,?,?,?)''', (job_id, job['content_hash'], candidate['_facts_hash'], dossier_row['file_hash'], path, sha, now()))
        _event(db, 'DRAFT_CREATED_NO_APPROVAL', job_id=job_id, version_id=vid)
        return vid


def load_job_version(db, version_id, *, require_latest=False):
    rows = db.rows('SELECT * FROM job_document_versions WHERE id=? AND revoked_at IS NULL', (version_id,))
    if not rows: raise ValueError('JOB_DOCUMENT_VERSION_MISSING_OR_REVOKED')
    row = rows[0]; job = _job(db, row['job_id']); candidate = candidate_snapshot(db)
    if row['job_content_hash'] != job['content_hash'] or row['facts_hash'] != candidate['_facts_hash']:
        raise ValueError('JOB_DOCUMENT_INPUT_CHANGED')
    if require_latest:
        latest = db.rows('SELECT MAX(id) id FROM job_document_versions WHERE job_id=?', (row['job_id'],))[0]['id']
        if latest != version_id: raise ValueError('JOB_DOCUMENT_NEWER_VERSION_EXISTS')
    payload = json.loads(read_asset(db, row))
    dossier_row, _ = sync_dossier(db)
    if payload['dossier_hash'] != dossier_row['file_hash']: raise ValueError('JOB_DOCUMENT_DOSSIER_CHANGED')
    if (payload['job_id'] != row['job_id'] or payload['job_content_hash'] != row['job_content_hash'] or
            payload['facts_hash'] != row['facts_hash'] or payload['dossier_hash'] != row['dossier_hash']):
        raise ValueError('JOB_DOCUMENT_BINDING_CHANGED')
    return row, payload


def review_file(db, version_id, kind='CV', extension='pdf'):
    _, payload = load_job_version(db, version_id)
    if kind not in {'CV', 'COVER_LETTER'} or extension not in {'pdf', 'docx'}:
        raise ValueError('DOCUMENT_SELECTION_INVALID')
    asset = payload['files'][kind + '.' + extension]
    raw = base64.b64decode(asset['base64'], validate=True)
    if hashlib.sha256(raw).hexdigest() != asset['sha256']: raise ValueError('JOB_DOCUMENT_FILE_CHANGED')
    validate_document(raw, extension)
    return raw


def _reference_binding(db, rid):
    content, row = reference_bytes(db, rid, for_sharing=True)
    last_event = db.rows('SELECT MAX(id) id FROM reference_review_events WHERE reference_id=?', (rid,))[0]['id']
    return content, {'id': rid, 'sha256': row['file_hash'], 'review_event_id': last_event,
                     'type': row['metadata']['document_type'], 'issuer': row['metadata']['issuer']}


def approve_job_bundle(db, version_id, expected_version_hash, *, extension='pdf', include_letter=False,
                       reference_ids=(), reference_consents=(), acceptance=None, inspection_id=None,
                       expected_inspection_revision=_UNSET,expected_reference_bindings=_UNSET,
                       content_reviewed=False, design_reviewed=False, confirmed=False):
    if not (confirmed and content_reviewed and design_reviewed):
        raise PermissionError('EXPLICIT_CONTENT_AND_DESIGN_REVIEW_REQUIRED')
    if extension not in {'pdf', 'docx'}: raise ValueError('PDF_OR_DOCX_REQUIRED')
    ids = list(reference_ids)
    if len(ids) != len(set(ids)) or any(type(i) is not int for i in ids): raise ValueError('REFERENCE_SELECTION_INVALID')
    if set(ids) != set(reference_consents): raise PermissionError('PER_REFERENCE_SHARING_CONSENT_REQUIRED')
    if not isinstance(acceptance, dict) or not acceptance.get('cv'):
        raise PermissionError('DESTINATION_DOCUMENT_ACCEPTANCE_REQUIRED')
    if include_letter and not acceptance.get('cover_letter') or ids and not acceptance.get('references'):
        raise PermissionError('OPTIONAL_DOCUMENT_NOT_ACCEPTED_BY_DESTINATION')
    with db.transaction() as con:
        if not con.in_transaction: con.execute('BEGIN IMMEDIATE')
        row, version = load_job_version(db, version_id, require_latest=True)
        if row['file_hash'] != expected_version_hash: raise ValueError('DOCUMENT_REVIEW_VERSION_CHANGED')
        if version['chronology_conflicts']: raise PermissionError('PROFESSIONAL_DATES_REQUIRE_REVIEW')
        job = _job(db, row['job_id']); candidate = candidate_snapshot(db)
        from .interaction_modes import manual_target_url
        target = manual_target_url(job.get('apply_url') or job['url'])
        if acceptance.get('source_url') != target or not acceptance.get('user_verified'):
            raise PermissionError('DESTINATION_ACCEPTANCE_EVIDENCE_REQUIRED')
        from .broad_selection import assess_selection
        from .store import already_applied
        selection = assess_selection(db, job, candidate)
        if selection['exclusions']: raise PermissionError('EXCLUDED_BY_IT_50KM_MAX3_SELECTION')
        if already_applied(db, job, 'LIVE'): raise PermissionError('ALREADY_APPLIED_OR_RESERVED')
        inspection = None
        if inspection_id:
            from .forms import load_inspection
            inspection = load_inspection(db, inspection_id)
            if inspection['job_id'] != job['id']: raise ValueError('INSPECTION_JOB_MISMATCH')
        references = [_reference_binding(db, rid)[1] for rid in ids]
        if expected_reference_bindings is not _UNSET and expected_reference_bindings!=references:
            raise ValueError('REFERENCE_CHANGED_SINCE_DOCUMENT_REVIEW')
        # Approval is tied to the exact optional selections, never all references.
        revision=db.rows('SELECT MAX(id) id FROM autoapply_form_inspections WHERE job_id=?',(job['id'],))[0]['id']
        if expected_inspection_revision is not _UNSET and expected_inspection_revision!=revision:
            raise ValueError('FORM_CHANGED_SINCE_DOCUMENT_REVIEW')
        if inspection_id and inspection_id!=revision:raise ValueError('LATEST_FORM_REVIEW_REQUIRED')
        choices = {'version_hash': row['file_hash'], 'extension': extension, 'include_letter': bool(include_letter),
                   'references': references, 'acceptance': acceptance, 'inspection_id': inspection_id,
                   'inspection_revision': revision,
                   'form_hash': inspection['form_hash'] if inspection else None}
        choice_hash = digest(choices)
        for previous in db.rows('SELECT * FROM job_document_bundles WHERE version_id=? AND revoked_at IS NULL ORDER BY id DESC', (version_id,)):
            old = json.loads(read_asset(db, previous))
            if old['choice_hash'] == choice_hash and datetime.fromisoformat(previous['expires_at']) > datetime.fromisoformat(now()):
                load_job_bundle(db, previous['id'])
                return previous['id']
        approved_documents = []
        for kind in ('CV', 'COVER_LETTER') if include_letter else ('CV',):
            raw = review_file(db, version_id, kind, extension)
            path, sha = save_asset(db, raw, extension)
            fact_ids = version['plan']['selected_fact_ids'] if kind == 'CV' else version['letter']['fact_ids']
            did = db.execute('''INSERT INTO candidate_documents(kind,encrypted_path,file_hash,facts_hash,claim_ids,created_at,approved_at)
                                 VALUES(?,?,?,?,?,?,?)''', ('JOB_' + kind, path, sha, candidate['_cv_facts_hash'], json.dumps(fact_ids), now(), now()))
            approved_documents.append({'id': did, 'kind': kind, 'sha256': sha, 'extension': extension,
                                       'name': ('CV' if kind == 'CV' else 'Cover-letter') + '.' + extension})
        expires = (datetime.fromisoformat(now()) + timedelta(hours=24)).isoformat(timespec='seconds')
        bundle = {**choices, 'choice_hash': choice_hash, 'version_id': version_id, 'job_id': job['id'],
                  'job_content_hash': job['content_hash'], 'facts_hash': candidate['_facts_hash'],
                  'target_url': target, 'documents': approved_documents, 'created_at': now(), 'expires_at': expires,
                  'consent_scope': 'LOCAL_MANUAL_EXPORT_ONLY', 'submitted': False, 'external_receipt_verified': False}
        path, sha = save_asset(db, encode(bundle), 'job-bundle')
        db.execute('UPDATE job_document_bundles SET revoked_at=? WHERE job_id=? AND revoked_at IS NULL', (now(), job['id']))
        bid = db.execute('''INSERT INTO job_document_bundles(version_id,job_id,encrypted_path,file_hash,created_at,expires_at,approved_at)
                            VALUES(?,?,?,?,?,?,?)''', (version_id, job['id'], path, sha, now(), expires, now()))
        _event(db, 'USER_APPROVED_EXPORT_BUNDLE', job_id=job['id'], version_id=version_id, bundle_id=bid)
        return bid


def load_job_bundle(db, bundle_id):
    rows = db.rows('SELECT * FROM job_document_bundles WHERE id=? AND revoked_at IS NULL', (bundle_id,))
    if not rows: raise ValueError('DOCUMENT_BUNDLE_MISSING_OR_REVOKED')
    row = rows[0]; payload = json.loads(read_asset(db, row))
    version_row, _ = load_job_version(db, row['version_id'], require_latest=True)
    job = _job(db, row['job_id'])
    from .interaction_modes import manual_target_url
    from .broad_selection import assess_selection
    from .store import already_applied
    if datetime.fromisoformat(row['expires_at']) <= datetime.fromisoformat(now()): raise ValueError('DOCUMENT_BUNDLE_EXPIRED')
    if (payload['job_id'] != row['job_id'] or payload['version_id'] != row['version_id'] or
        payload['version_hash'] != version_row['file_hash'] or payload['target_url'] != manual_target_url(job.get('apply_url') or job['url']) or
        payload['job_content_hash'] != job['content_hash'] or payload['facts_hash'] != candidate_snapshot(db)['_facts_hash']):
        raise ValueError('DOCUMENT_BUNDLE_INPUT_CHANGED')
    if already_applied(db, job, 'LIVE'): raise PermissionError('ALREADY_APPLIED_OR_RESERVED')
    if assess_selection(db, job, candidate_snapshot(db))['exclusions']:
        raise PermissionError('EXCLUDED_BY_IT_50KM_MAX3_SELECTION')
    revision=db.rows('SELECT MAX(id) id FROM autoapply_form_inspections WHERE job_id=?',(job['id'],))[0]['id']
    if payload['inspection_revision'] != revision: raise ValueError('DOCUMENT_BUNDLE_FORM_REVISION_CHANGED')
    if payload['inspection_id']:
        from .forms import load_inspection
        if load_inspection(db, payload['inspection_id'])['form_hash'] != payload['form_hash']:
            raise ValueError('DOCUMENT_BUNDLE_FORM_CHANGED')
    for doc in payload['documents']:
        _, ext, sha = document_bytes(db, doc['id'])
        if ext != doc['extension'] or sha != doc['sha256']: raise ValueError('DOCUMENT_BUNDLE_FILE_CHANGED')
    for reference in payload['references']:
        if _reference_binding(db, reference['id'])[1] != reference:
            raise PermissionError('REFERENCE_PERMISSION_CHANGED')
    return payload


def bundle_files(db, bundle_id):
    payload = load_job_bundle(db, bundle_id); files = {}
    for doc in payload['documents']:
        files[doc['name']] = document_bytes(db, doc['id'])[0]
    for ref in payload['references']:
        files[f'Reference-{ref["id"]}-original.pdf'] = reference_bytes(db, ref['id'], for_sharing=True)[0]
    return payload, files


def export_job_bundle(db, bundle_id):
    """Use the existing assisted handoff for contacts, verified answers and holds."""
    from .handoff import prepare_handoff, handoff_download
    payload = load_job_bundle(db, bundle_id)
    prepared = prepare_handoff(db, payload['job_id'], payload['inspection_id'], bundle_id=bundle_id)
    raw=handoff_download(db, prepared['handoff_id'])
    with db.transaction() as con:
        if not con.in_transaction:con.execute('BEGIN IMMEDIATE')
        if not db.rows("SELECT id FROM job_document_events WHERE bundle_id=? AND kind='LOCAL_HANDOFF_PREPARED' AND json_extract(details,'$.handoff_id')=?",(bundle_id,prepared['handoff_id'])):
            _event(db,'LOCAL_HANDOFF_PREPARED',job_id=payload['job_id'],version_id=payload['version_id'],bundle_id=bundle_id,handoff_id=prepared['handoff_id'])
    return raw, prepared['handoff_id']


def revoke_job_version(db, version_id, *, confirmed=False):
    if not confirmed: raise PermissionError('EXPLICIT_DOCUMENT_REVOCATION_REQUIRED')
    with db.transaction():
        rows = db.rows('SELECT job_id FROM job_document_versions WHERE id=?', (version_id,))
        if not rows: raise ValueError('JOB_DOCUMENT_VERSION_MISSING_OR_REVOKED')
        db.execute('UPDATE job_document_versions SET revoked_at=? WHERE id=?', (now(), version_id))
        db.execute('UPDATE job_document_bundles SET revoked_at=? WHERE version_id=?', (now(), version_id))
        _event(db, 'VERSION_REVOKED', job_id=rows[0]['job_id'], version_id=version_id)
