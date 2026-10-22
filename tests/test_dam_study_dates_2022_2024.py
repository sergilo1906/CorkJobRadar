"""Regression tests for the user's confirmed 2022-2024 DAM study dates.

These tests use the isolated Windows test DB / DPAPI fixtures. Never production.
"""
import pytest
from corkjobradar.autoapply.vault import approve_fact, candidate_snapshot
from corkjobradar.autoapply.documents import render_cv, create_cv_review, approve_cv_review, cv_review_bytes
from scripts.update_dam_completed_20261022 import FIELD, COMPLETED
from scripts.update_dam_study_dates_20261022 import UPDATED, update
from test_autoapply_vault import populate


def test_updates_dates_preserves_history_and_requires_new_cv_review(db):
    populate(db)
    old_id = approve_fact(db, FIELD, COMPLETED, 'SYNTHETIC previous approval', confirmed=True)
    previous = candidate_snapshot(db)
    existing_draft_id = create_cv_review(db, render_cv(previous, 'pdf'), 'pdf')
    _, _, sha, _ = cv_review_bytes(db, existing_draft_id)
    approve_cv_review(db, existing_draft_id, sha, previous['_facts_hash'], confirmed=True)
    untouched = {r['id']: r for r in db.rows('SELECT * FROM candidate_facts') if r['id'] != old_id}

    result = update(db)
    assert not result['already_current']
    assert result['requires_explicit_cv_review']
    current = candidate_snapshot(db)
    assert current.get('cv_document_id') is None
    assert len([c for c in current['_claims'] if c['section'] == 'Education' and c['text_en'] == UPDATED['text_en']]) == 1
    assert db.rows('SELECT revoked_at FROM candidate_facts WHERE id=?', (old_id,))[0]['revoked_at']
    assert all(db.rows('SELECT * FROM candidate_facts WHERE id=?', (id_,))[0] == row for id_, row in untouched.items())
    content, ext, _, extracted = cv_review_bytes(db, result['new_cv_draft_id'])
    assert ext == 'pdf' and content.startswith(b'%PDF-')
    assert '2022-2024' in extracted
    assert '2022-2026' not in extracted and 'MP13 remaining' not in extracted
    assert 'final examination passed' in extracted
    assert not db.rows('SELECT id FROM application_attempts')
    assert db.rows('SELECT live_enabled FROM autoapply_control')[0]['live_enabled'] == 0
    assert update(db)['already_current']


def test_refuses_unexpected_education_version(db):
    populate(db)
    approve_fact(db, FIELD, {'section':'Education','text_en':'SYNTHETIC unrelated version'}, 'SYNTHETIC', confirmed=True)
    with pytest.raises(ValueError, match='DAM_FACT_CHANGED'):
        update(db)
    assert not db.rows('SELECT * FROM candidate_documents')


def test_active_preparation_lock_prevents_profile_change(db):
    from corkjobradar.worker import worker_lock
    populate(db)
    approve_fact(db, FIELD, COMPLETED, 'SYNTHETIC', confirmed=True)
    before = db.rows('SELECT * FROM candidate_facts')
    with worker_lock(db), pytest.raises(RuntimeError, match='WORKER_ACTIVE'):
        update(db)
    assert db.rows('SELECT * FROM candidate_facts') == before
    assert not db.rows('SELECT * FROM candidate_documents')


def test_render_failure_preserves_fact_and_approved_cv(db, monkeypatch):
    import scripts.update_dam_study_dates_20261022 as migration
    populate(db)
    approve_fact(db, FIELD, COMPLETED, 'SYNTHETIC', confirmed=True)
    current = candidate_snapshot(db)
    did = create_cv_review(db, render_cv(current, 'pdf'), 'pdf')
    _, _, sha, _ = cv_review_bytes(db, did)
    approve_cv_review(db, did, sha, current['_facts_hash'], confirmed=True)
    before = {t: db.rows('SELECT * FROM ' + t) for t in ('candidate_facts', 'candidate_documents')}
    def fail(*args, **kwargs):
        raise ValueError('SYNTHETIC_RENDER_FAILED')
    monkeypatch.setattr(migration, 'render_cv', fail)
    with pytest.raises(ValueError, match='SYNTHETIC_RENDER_FAILED'):
        migration.update(db)
    assert all(db.rows('SELECT * FROM ' + t) == rows for t, rows in before.items())


def test_corrected_education_invalidates_previously_prepared_packet(db, profile, monkeypatch):
    from test_usable_it_workspace import case
    from corkjobradar.autoapply import handoff
    job = case(db, profile)
    approve_fact(db, FIELD, COMPLETED, 'SYNTHETIC', confirmed=True)
    current = candidate_snapshot(db)
    did = create_cv_review(db, render_cv(current, 'pdf'), 'pdf')
    _, _, sha, _ = cv_review_bytes(db, did)
    approve_cv_review(db, did, sha, current['_facts_hash'], confirmed=True)
    monkeypatch.setattr(handoff, 'validate_url', lambda url: url)
    packet = handoff.prepare_handoff(db, job['id'])
    before = db.rows('SELECT * FROM manual_application_handoffs')
    update(db)
    with pytest.raises(ValueError, match='HANDOFF_PROFILE_OR_CV_CHANGED'):
        handoff.load_handoff(db, packet['handoff_id'])
    assert db.rows('SELECT * FROM manual_application_handoffs') == before
    assert not db.rows('SELECT * FROM application_attempts')
