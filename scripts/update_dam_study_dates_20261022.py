"""Correct the user-confirmed DAM study dates without approving a CV or sending jobs.

Run without flags for a read-only preview:
    .\\.venv\\Scripts\\python.exe scripts/update_dam_study_dates_20261022.py

To apply after making sure LIVE is OFF:
    .\\.venv\\Scripts\\python.exe scripts/update_dam_study_dates_20261022.py --apply-user-confirmation

The approved claim is versioned; prior encrypted evidence remains in SQLite.
The newly generated CV is an unapproved draft and requires review in the app.
"""
import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from uuid import uuid4
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from corkjobradar.config import ROOT
from corkjobradar.db import Database
from corkjobradar.autoapply.documents import create_cv_review, render_cv
from corkjobradar.autoapply.vault import approve_fact, candidate_snapshot
from scripts.update_dam_completed_20261022 import FIELD, COMPLETED

UPDATED = {
    'section': 'Education',
    'text_en': (
        'Higher Technician qualification in Multiplatform Application Development '
        '(CFGS DAM), Institut Baix Camp (2022-2024): completed; final examination passed.'
    ),
}
ORIGIN = 'USER_CONFIRMED_DAM_STUDY_DATES_2022_2024_2026_10_22'


def _current_claim(db):
    facts = candidate_snapshot(db)
    claims = [claim for claim in facts['_claims'] if claim['section'] == 'Education'
              and any(row['field'] == FIELD and row['id'] == claim['id']
                      for row in db.rows('SELECT id, field FROM candidate_facts WHERE revoked_at IS NULL'))]
    if len(claims) != 1:
        raise ValueError('EXACTLY_ONE_CURRENT_DAM_EDUCATION_CLAIM_REQUIRED')
    return facts, claims[0]


def update(db):
    """Version the exact prior statement; never approve the CV or turn on LIVE."""
    facts, existing = _current_claim(db)
    before = {'section': existing['section'], 'text_en': existing['text_en']}
    if before == UPDATED:
        return {'already_current': True, 'new_cv_draft_id': None}
    if before != COMPLETED:
        raise ValueError('DAM_FACT_CHANGED_OR_DIFFERENT_FROM_EXPECTED:REVIEW_MANUALLY')

    preview = dict(facts)
    preview['_claims'] = [{**claim, **UPDATED} if claim['id'] == existing['id'] else claim
                          for claim in facts['_claims']]
    new_cv_bytes = render_cv(preview, 'pdf')
    if not new_cv_bytes.startswith(b'%PDF-'):
        raise ValueError('CV_RENDER_FAILED')
    with db.transaction() as con:
        con.execute('BEGIN IMMEDIATE')
        if candidate_snapshot(db)['_facts_hash'] != facts['_facts_hash']:
            raise ValueError('FACTS_CHANGED_WHILE_PREPARING')
        current = db.rows('SELECT enabled, live_enabled FROM autoapply_control')[0]
        if current['enabled'] or current['live_enabled']:
            raise ValueError('AUTOAPPLY_MUST_BE_OFF')
        fact_id = approve_fact(db, FIELD, UPDATED, ORIGIN, confirmed=True)
        draft_id = create_cv_review(db, new_cv_bytes, 'pdf')
        current_facts = candidate_snapshot(db)
        if current_facts.get('cv_document_id'):
            raise ValueError('NEW_CV_MUST_REMAIN_UNAPPROVED')
    return {'already_current': False, 'new_fact_id': fact_id,
            'new_cv_draft_id': draft_id, 'requires_explicit_cv_review': True}


def _backup_db(db):
    folder = ROOT / 'data' / 'backups'
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    dest = folder / ('before-dam-dates-' + stamp + '-' + uuid4().hex[:8] + '.sqlite3')
    with sqlite3.connect(str(db.path)) as source, sqlite3.connect(str(dest)) as target:
        source.backup(target)
        if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('BACKUP_INTEGRITY_FAILED')
    return dest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply-user-confirmation', action='store_true',
                        help='Version the approved education fact and create a new CV draft.')
    args = parser.parse_args()
    db = Database()
    facts, existing = _current_claim(db)
    before = {'section': existing['section'], 'text_en': existing['text_en']}
    if before not in (COMPLETED, UPDATED):
        raise ValueError('UNEXPECTED_DAM_FACT_REVIEW_IN_UI')
    current = db.rows('SELECT enabled, live_enabled FROM autoapply_control')[0]
    status = {'target_study_years': '2022-2024',
              'qualification': 'CFGS DAM completed',
              'already_current': before == UPDATED,
              'live_enabled': bool(current['live_enabled']),
              'cv_approved_after_change': False}
    if not args.apply_user_confirmation:
        status['action'] = 'PREVIEW_ONLY'
        print(json.dumps(status, indent=2))
        return
    if current['enabled'] or current['live_enabled']:
        raise ValueError('AUTOAPPLY_MUST_BE_OFF')
    if before == UPDATED:
        print(json.dumps({**status, 'action': 'NO_CHANGE'}, indent=2))
        return
    backup = _backup_db(db)
    result = update(db)
    # Only metadata and a backup filename are printed: never CV text or contacts.
    print(json.dumps({**status, **result, 'action': 'UPDATED_NEW_CV_NEEDS_REVIEW',
                      'backup_file': str(backup.relative_to(ROOT))}, indent=2))


if __name__ == '__main__':
    main()
