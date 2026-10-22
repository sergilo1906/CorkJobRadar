import json
from corkjobradar.autoapply.opportunities import identify_ats,inventory,requirement_signals
from corkjobradar.autoapply.platforms import platform_for
from test_autoapply_policy import stored_job


def test_inventory_retains_every_job_including_non_it_and_never_grants_permission(db,profile):
    job=stored_job(db,profile)
    other=stored_job(db,profile,external='other',url='https://jobs.ashbyhq.com/example/role')
    db.execute("UPDATE jobs SET title='Warehouse Operative',scope='FUERA_DE_ALCANCE' WHERE id=?",(other['id'],))
    control=db.rows('SELECT * FROM autoapply_control');rows=db.rows('SELECT * FROM jobs')
    report=inventory(db)
    assert report['jobs_processed']==2 and {r['job_id'] for r in report['offers']}=={job['id'],other['id']}
    assert all(r['reasons'] and not r['trial_ready'] for r in report['offers'])
    assert not report['compatible_real_trial_identified']
    assert db.rows('SELECT * FROM jobs')==rows and db.rows('SELECT * FROM autoapply_control')==control
    assert not db.rows('SELECT * FROM application_attempts')


def test_ats_identification_is_separate_from_submission_capability():
    assert identify_ats('https://jobs.ashbyhq.com/netgear/role')=='ashby'
    assert identify_ats('https://jobs.smartrecruiters.com/Company/123')=='smartrecruiters'
    assert identify_ats('https://distilled.recruitee.com/o/example')=='recruitee'
    assert not platform_for('https://distilled.recruitee.com/o/example')['automation_permitted']


def test_mandatory_signals_keep_literal_offsets_and_exclude_desirable():
    text='Requirements\n2+ years of experience in IT support\nA Level 8 degree completed by November 2026.\nPreferred Qualifications\n5 years of experience would be an advantage.\n'
    result=requirement_signals(text)
    assert len(result)==2
    assert all(text[r['offset']:r['offset']+len(r['quote'])]==r['quote'] for r in result)
    assert not any('5 years' in r['quote'] for r in result)


def test_inventory_ui_never_starts_worker_or_records_a_submission(db,profile,monkeypatch):
    from streamlit.testing.v1 import AppTest
    from corkjobradar.config import ROOT
    import corkjobradar.db as module
    import corkjobradar.autoapply.ui as ui
    stored_job(db,profile)
    monkeypatch.setattr(module,'Database',lambda:db)
    started=[];monkeypatch.setattr(ui,'launch_simulation',lambda:started.append(True))
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=45).run()
    app.radio(key='ui_area').set_value('AutoApply').run()
    app.checkbox(key='aa_tools').check().run()
    app.selectbox(key='aa_tool').set_value('Compatibilidad de plataformas').run()
    next(b for b in app.button if b.label=='Auditar plataformas y retenciones de todas las ofertas guardadas').click().run()
    assert not app.exception and not started
    assert app.session_state['aa_ats_inventory']['jobs_processed']==1
    assert not db.rows('SELECT * FROM application_attempts') and not db.rows('SELECT * FROM user_actions')
