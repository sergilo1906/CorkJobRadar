import json
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
from corkjobradar.config import ROOT
from corkjobradar.db import Database
from corkjobradar.autoapply.documents import render_cv,create_cv_review,cv_review_bytes,approve_cv_review,document_bytes
from corkjobradar.autoapply.vault import candidate_snapshot,approve_fact
from test_autoapply_vault import populate


def test_cv_review_survives_restart_and_requires_document_consent(db):
    populate(db);facts=candidate_snapshot(db);content=render_cv(facts,'pdf')
    did=create_cv_review(db,content,'pdf')
    reopened=Database(db.path)
    decoded,extension,sha,text=cv_review_bytes(reopened,did)
    assert decoded==content and extension=='pdf' and 'SYNTHETIC ONLY' in text
    assert 'cv_document_id' not in candidate_snapshot(reopened)
    assert not reopened.rows('SELECT * FROM autoapply_policies')
    with pytest.raises(ValueError,match='EXPLICIT_DOCUMENT_REVIEW'):approve_cv_review(reopened,did,sha,facts['_facts_hash'],False)
    with pytest.raises(ValueError,match='CHANGED'):approve_cv_review(reopened,did,'wrong',facts['_facts_hash'],True)
    assert approve_cv_review(reopened,did,sha,facts['_facts_hash'],True)==did
    assert approve_cv_review(reopened,did,sha,facts['_facts_hash'],True)==did
    assert candidate_snapshot(reopened)['cv_document_id']==did
    assert document_bytes(reopened,did)[0]==content
    assert len(reopened.rows("SELECT * FROM application_events WHERE kind='CV_REVIEW_APPROVED'"))==1
    assert not reopened.rows('SELECT * FROM application_attempts')


def test_changed_facts_or_tampered_draft_cannot_be_approved(db):
    populate(db);facts=candidate_snapshot(db)
    did=create_cv_review(db,render_cv(facts),'docx')
    _,_,sha,_=cv_review_bytes(db,did)
    approve_fact(db,'availability','SYNTHETIC changed','synthetic',True)
    with pytest.raises(ValueError):approve_cv_review(db,did,sha,facts['_facts_hash'],True)
    assert 'cv_document_id' not in candidate_snapshot(db)
    current=candidate_snapshot(db)
    fresh=create_cv_review(db,render_cv(current),'docx')
    path=Path(db.rows('SELECT encrypted_path FROM candidate_documents WHERE id=?',(fresh,))[0]['encrypted_path'])
    path.write_bytes(b'corrupted encrypted synthetic document')
    with pytest.raises(RuntimeError):cv_review_bytes(db,fresh)


def test_answer_templates_do_not_force_reapproval_of_unchanged_cv_but_pause_policy(db):
    from corkjobradar.autoapply.documents import store_document
    from corkjobradar.autoapply.policy import save_policy
    from test_autoapply_policy import policy_config
    populate(db);candidate=candidate_snapshot(db)
    did=store_document(db,render_cv(candidate),'docx',True)
    config=policy_config();config.update(candidate_facts_hash=candidate['_facts_hash'],authorized_document_ids=[did])
    save_policy(db,config,'AUTHORIZE_SIMULATION')
    approve_fact(db,'answer:question',{'question':'Exact synthetic question','host':'example.invalid','answer':'Truthful synthetic answer'},'synthetic',True)
    updated=candidate_snapshot(db)
    assert updated['cv_document_id']==did and updated['_cv_facts_hash']==candidate['_cv_facts_hash']
    assert updated['_facts_hash']!=candidate['_facts_hash']
    assert document_bytes(db,did)[0]
    assert db.rows('SELECT paused FROM autoapply_control')[0]['paused']==1


def test_ui_cv_review_and_guided_policy_survive_reload_without_starting_worker(db,monkeypatch):
    import corkjobradar.db as db_module
    import corkjobradar.autoapply.ui as ui
    monkeypatch.setattr(db_module,'Database',lambda:db)
    launched=[];monkeypatch.setattr(ui,'launch_simulation',lambda:launched.append(True))
    populate(db)
    def widget(items,label):return next(x for x in items if x.label==label)
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=45).run()
    app.radio(key='ui_area').set_value('Perfil y configuración').run()
    app.checkbox(key='profile_cv_import').check().run()
    widget(app.button,'Preparar CV inglés para revisar').click().run()
    assert not app.exception and not candidate_snapshot(db).get('cv_document_id')
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=45).run()
    app.radio(key='ui_area').set_value('Perfil y configuración').run()
    app.checkbox(key='profile_cv_import').check().run()
    assert not app.exception
    assert widget(app.button,'Guardar esta versión validada del CV').disabled
    widget(app.checkbox,'He revisado el CV completo: todas sus afirmaciones son veraces y están respaldadas por mi ficha').check()
    widget(app.button,'Guardar esta versión validada del CV').click().run()
    assert not app.exception and candidate_snapshot(db).get('cv_document_id')
    app.selectbox(key='ui_profile_section').set_value('Política de candidaturas').run()
    widget(app.multiselect,'Modalidades autorizadas').set_value(['REMOTE'])
    widget(app.multiselect,'Plataformas autorizadas').set_value(['Greenhouse'])
    widget(app.text_area,'Dominios exactos autorizados, uno por línea').set_value('job-boards.greenhouse.io')
    widget(app.multiselect,'Horarios y turnos aceptados').set_value(['WEEKDAYS_DAY'])
    widget(app.multiselect,'Contratos aceptados').set_value(['PERMANENT'])
    for label in ('Permito generar CV con mis hechos aprobados','Permito adjuntar la versión aprobada del CV','Permito preparar los campos con respuestas verificadas',
                  'Autorizo esta política SOLO para simulación con las versiones actuales de mi ficha y CV; no autoriza envíos reales'):
        widget(app.checkbox,label).check()
    widget(app.button,'Guardar y autorizar simulación').click().run()
    assert not app.exception
    control=db.rows('SELECT * FROM autoapply_control')[0]
    assert control['enabled']==1 and control['live_enabled']==0 and not launched
    saved=json.loads(db.rows('SELECT config FROM autoapply_policies')[0]['config'])
    assert saved['categories']==['IT'] and saved['allowed_hosts']==['job-boards.greenhouse.io']
    assert saved['authorized_document_ids']==[candidate_snapshot(db)['cv_document_id']]
    AppTest.from_file(str(ROOT/'app.py'),default_timeout=45).run()
    assert len(db.rows('SELECT * FROM autoapply_policies'))==1 and not launched


def test_policy_location_and_commute_limits_are_hard_gates(profile):
    from test_autoapply_policy import inputs
    from corkjobradar.autoapply.eligibility import evaluate_autoapply
    data=inputs(profile);data['policy']=data['policy'].model_copy(update={'max_commute_minutes':15})
    data['transport'][0]['details']['duration_minutes']=30
    assert evaluate_autoapply(**data).outcome=='HOLD'
    data=inputs(profile);data['policy']=data['policy'].model_copy(update={'location_scope':'CORK_CITY'})
    data['job']['location']='County Cork'
    assert 'CORK_CITY_LOCATION_UNVERIFIED' in [r.code for r in evaluate_autoapply(**data).reasons]
