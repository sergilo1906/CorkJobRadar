"""Intact third-party evidence, separately consented from the candidate's CV.

An extracted page is a viewing derivative, NEVER an original signed document.
Multi-document source packets cannot be attached as one selected reference.
"""
import io
import json
from datetime import date
from ..config import now
from .document_storage import encode, save_asset, read_asset
from .vault import protect

TYPES = {'IT_RECOMMENDATION', 'EMPLOYMENT_RECOMMENDATION', 'EMPLOYMENT_CONFIRMATION'}
ISSUERS = {'SIE': 'IT_RECOMMENDATION', 'GAS_REUSENSE': 'EMPLOYMENT_RECOMMENDATION',
           'CARRIAGE_FOOD_SERVICES': 'EMPLOYMENT_CONFIRMATION'}


def inspect_reference(content):
    """Accept passive scans and signature fields without rewriting original bytes."""
    try:
        from pypdf import PdfReader
        from pypdf.generic import IndirectObject
        if len(content) > 10_000_000 or not content.startswith(b'%PDF-'):
            raise ValueError()
        pdf = PdfReader(io.BytesIO(content))
        if pdf.is_encrypted or not 1 <= len(pdf.pages) <= 20: raise ValueError()
        visited = set(); budget = [0]
        def walk(node):
            budget[0] += 1
            if budget[0] > 50000: raise ValueError()
            if isinstance(node, IndirectObject):
                key = (node.idnum, node.generation)
                if key in visited: return
                visited.add(key); node = node.get_object()
            if isinstance(node, dict):
                if any(key in node for key in ('/JS', '/JavaScript', '/OpenAction', '/AA', '/EmbeddedFiles', '/RichMediaContent', '/XFA')):
                    raise ValueError()
                if str(node.get('/S')) in {'/JavaScript', '/Launch', '/SubmitForm', '/ImportData', '/GoToR'}:
                    raise ValueError()
                for key, value in node.items():
                    if key not in {'/Parent', '/Prev'}: walk(value)
            elif isinstance(node, (list, tuple)):
                for value in node: walk(value)
        walk(pdf.trailer['/Root'])
        return {'page_count': len(pdf.pages),
                'text_available': [bool((p.extract_text() or '').strip()) for p in pdf.pages],
                'cryptographic_signature_validated': False}
    except Exception:
        raise ValueError('REFERENCE_PDF_VALIDATION_FAILED') from None


def import_reference(db, content, *, issuer, document_type, source_page=1,
                     issued_on=None, related_role='', notes='', standalone_document=None, consent_to_store=False):
    if not consent_to_store: raise PermissionError('REFERENCE_STORAGE_CONSENT_REQUIRED')
    if issuer not in ISSUERS or document_type not in TYPES or ISSUERS[issuer] != document_type:
        raise ValueError('REFERENCE_CLASSIFICATION_MISMATCH')
    if issued_on is not None:
        try: date.fromisoformat(issued_on)
        except (ValueError, TypeError): raise ValueError('REFERENCE_DATE_REVIEW_REQUIRED') from None
    if any(not isinstance(v, str) or len(v) > 3000 for v in (related_role, notes)):
        raise ValueError('REFERENCE_METADATA_INVALID')
    inspection = inspect_reference(content)
    if type(source_page) is not int or not 1 <= source_page <= inspection['page_count']:
        raise ValueError('REFERENCE_SOURCE_PAGE_INVALID')
    if standalone_document is not None and type(standalone_document) is not bool:
        raise ValueError('REFERENCE_SOURCE_CLASSIFICATION_REQUIRED')
    standalone = inspection['page_count'] == 1 if standalone_document is None else standalone_document
    if standalone and source_page != 1: raise ValueError('REFERENCE_STANDALONE_MUST_START_AT_PAGE_ONE')
    metadata = {'issuer': issuer, 'document_type': document_type, 'issued_on': issued_on,
                'related_role': related_role, 'notes': notes, 'source_page': source_page,
                **inspection, 'share_authorized': False, 'consistency_reviewed': False,
                'source_contains_only_this_reference': standalone,
                'source_is_intact': True, 'view_derivative_is_original': False}
    with db.transaction() as con:
        if not con.in_transaction: con.execute('BEGIN IMMEDIATE')
        path, sha = save_asset(db, content, 'reference-original')
        existing = db.rows('SELECT * FROM reference_originals WHERE file_hash=? AND source_page=?', (sha, source_page))
        if existing:
            previous = json.loads(protect(existing[0]['metadata'], True))
            if previous['issuer'] != issuer or previous['document_type'] != document_type:
                raise ValueError('REFERENCE_EXISTING_CLASSIFICATION_CONFLICT')
            return existing[0]['id']  # No reimport to reset a revocation or consent.
        rid = db.execute('''INSERT INTO reference_originals(encrypted_path,file_hash,metadata,source_page,page_count,imported_at)
                            VALUES(?,?,?,?,?,?)''', (path, sha, protect(encode(metadata)), source_page, inspection['page_count'], now()))
        _event(db, rid, 'IMPORTED_NOT_AUTHORIZED', {'original_hash': sha})
        return rid


def _event(db, rid, kind, metadata):
    db.execute('INSERT INTO reference_review_events(reference_id,kind,created_at,metadata) VALUES(?,?,?,?)',
               (rid, kind, now(), protect(encode(metadata))))


def reference_record(db, rid, *, include_revoked=False):
    rows = db.rows('SELECT * FROM reference_originals WHERE id=?', (rid,))
    if not rows or (rows[0]['revoked_at'] and not include_revoked):
        raise ValueError('REFERENCE_MISSING_OR_REVOKED')
    row = rows[0]
    return {**row, 'metadata': json.loads(protect(row['metadata'], True))}


def reference_bytes(db, rid, *, for_sharing=False):
    row = reference_record(db, rid)
    if for_sharing:
        if not row['reviewed_at'] or not row['metadata'].get('share_authorized'):
            raise PermissionError('REFERENCE_SHARING_NOT_AUTHORIZED')
        if not row['metadata'].get('consistency_reviewed'):
            raise PermissionError('REFERENCE_CONTRADICTIONS_REQUIRE_REVIEW')
        from .vault import candidate_snapshot
        if row['metadata'].get('reviewed_profile_hash') != candidate_snapshot(db)['_cv_facts_hash']:
            raise PermissionError('REFERENCE_PROFILE_REVIEW_CHANGED')
        if not row['metadata'].get('source_contains_only_this_reference'):
            raise PermissionError('REFERENCE_STANDALONE_ORIGINAL_REQUIRED')
    content = read_asset(db, row)
    inspect_reference(content)
    return content, row


def review_reference(db, rid, expected_hash, *, consistency_reviewed=False,
                     authorize_sharing=False, confirmed=False):
    if not confirmed or not consistency_reviewed:
        raise PermissionError('EXPLICIT_REFERENCE_REVIEW_REQUIRED')
    with db.transaction() as con:
        if not con.in_transaction: con.execute('BEGIN IMMEDIATE')
        _, row = reference_bytes(db, rid)
        if row['file_hash'] != expected_hash: raise ValueError('REFERENCE_CHANGED')
        from .vault import candidate_snapshot
        metadata = {**row['metadata'], 'consistency_reviewed': True,
                    'reviewed_profile_hash': candidate_snapshot(db)['_cv_facts_hash'],
                    'share_authorized': bool(authorize_sharing)}
        db.execute('UPDATE reference_originals SET metadata=?,reviewed_at=? WHERE id=?',
                   (protect(encode(metadata)), now(), rid))
        _event(db, rid, 'HUMAN_REVIEW', {'share_authorized': bool(authorize_sharing), 'original_hash': expected_hash})


def revoke_reference(db, rid, *, confirmed=False):
    if not confirmed: raise PermissionError('EXPLICIT_REFERENCE_REVOCATION_REQUIRED')
    with db.transaction():
        reference_record(db, rid)
        db.execute('UPDATE reference_originals SET revoked_at=? WHERE id=?', (now(), rid))
        _event(db, rid, 'REVOKED', {})


def reference_preview(db, rid, page_number=None):
    """Raster viewing copy only; original remains byte-identical in the vault."""
    from .cv_preview import render_pdf_page
    content, row = reference_bytes(db, rid)
    page = row['source_page'] - 1 if page_number is None else page_number
    if page != row['source_page'] - 1 and not row['metadata'].get('source_contains_only_this_reference'):
        raise ValueError('REFERENCE_PREVIEW_SOURCE_PAGE_MISMATCH')
    return render_pdf_page(content, page)
