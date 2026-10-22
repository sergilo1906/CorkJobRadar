import pytest
from streamlit.testing.v1 import AppTest
from corkjobradar.config import ROOT
from corkjobradar.ui.visibility import PAGES,runtime_actions,actions_for,application_state,APPLICATION_STATES
from corkjobradar.ui.model import load_view,filter_jobs
from corkjobradar.models import Job
from corkjobradar.repository import save_job
from corkjobradar.analysis import analyze_job
from conftest import source


@pytest.mark.parametrize('desired,state,expected',[
    ('RUNNING','WAITING',('PAUSE','STOP')),('RUNNING','RUNNING',('PAUSE','STOP')),
    ('PAUSED','PAUSED',('RESUME','STOP')),('PAUSED','PAUSING',()),('RUNNING','PAUSING',()),('STOPPED','STOPPED',('START',)),
    ('STOPPED','STOPPING',()),('PAUSED','STOPPING',())])
def test_runtime_visibility_matrix(desired,state,expected):
    assert runtime_actions(dict(desired=desired,state=state))==expected


def test_search_now_blocked_during_pause_even_without_child():
    from corkjobradar.ui.visibility import safe_controls
    with pytest.raises(ValueError,match='WORK_ALREADY_ACTIVE'):
        safe_controls(dict(desired='PAUSED',state='PAUSING',active_kind=None),'SEARCH_NOW')


@pytest.mark.parametrize('state',APPLICATION_STATES[3:])
def test_recorded_closed_or_uncertain_never_offers_another_submission(state):
    controls=actions_for(cv_approved=True,preparation_allowed=True,application=state,channel_validated=True,policy_authorized=True,live_released=True)
    assert not controls['prepare'] and not controls['send'] and not controls['open_application']


def test_confirmed_requires_proof_and_manual_is_separate():
    assert application_state(manual=True)==APPLICATION_STATES[3]
    assert application_state(uncertain=True,prepared=True)==APPLICATION_STATES[5]
    assert application_state(confirmed=True,manual=True)==APPLICATION_STATES[4]


@pytest.mark.parametrize('delivery',[{'confirmed':True},{'manual':True}])
def test_closed_followup_preserves_the_delivery_history_but_changes_current_stage(delivery):
    assert application_state(closed=True,**delivery)==APPLICATION_STATES[6]


def test_later_interview_or_rejection_does_not_erase_a_declared_submission(db,profile):
    from corkjobradar.config import now
    jid=seed(db,profile)[0]
    for action in ['solicitada','entrevista','rechazada']:
        db.execute('INSERT INTO user_actions(job_id,action,notes,created_at) VALUES(?,?,?,?)',(jid,action,'SYNTHETIC',now()))
    view=load_view(db);row=next(j for j in view['jobs'] if j['id']==jid)
    assert row['application']==APPLICATION_STATES[6] and row['manual_declared']
    assert view['manual']==1 and view['confirmed']==0


def test_cancel_search_is_scoped_and_idempotent(db,profile):
    from corkjobradar.worker import create_run
    from corkjobradar.ui.pages import cancel_search
    one=create_run(db,kind='analyze',profile_override=profile)
    cancel_search(db,one);cancel_search(db,one)
    assert db.rows('SELECT cancel_requested FROM scan_runs WHERE id=?',(one,))[0]['cancel_requested']==1


def app_for(db,monkeypatch):
    import corkjobradar.db as module
    import corkjobradar.runtime_ui as runtime_ui
    monkeypatch.setattr(module,'Database',lambda:db)
    monkeypatch.setattr(runtime_ui,'bootstrap',lambda db:None)
    return AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()


def seed(db,profile):
    source(db,'greenhouse')
    ids=[]
    for i,title in enumerate(['IT Support Technician','Warehouse Operative']):
        jid=save_job(db,'fixture',Job(external_id='redesign-'+str(i),title=title,company='SYNTHETIC ONLY',location='Cork City',url='https://fixture.test/redesign-'+str(i),description='Provide technical support, troubleshoot Windows computers and resolve helpdesk tickets. '*10 if i==0 else 'Warehouse tasks. '*10,detail_complete=True),profile=profile)
        analyze_job(db,jid,profile);ids.append(jid)
    return ids


def test_six_lazy_screens_and_no_private_values_or_debug_on_home(db,monkeypatch):
    app=app_for(db,monkeypatch)
    assert not app.exception
    assert app.radio(key='ui_area').options==list(PAGES)
    assert not app.tabs and not app.text_input and not app.text_area
    assert not app.json and not app.dataframe
    for page in PAGES:
        app.radio(key='ui_area').set_value(page).run()
        assert not app.exception,page
    assert not db.rows('SELECT * FROM application_attempts')
    assert db.rows('SELECT live_enabled FROM autoapply_control')[0]['live_enabled']==0


def test_batched_list_no_per_row_queries_and_filters(db,profile,monkeypatch):
    seed(db,profile)
    count=0;original=db.rows
    def measured(*args,**kwargs):
        nonlocal count
        count+=1
        return original(*args,**kwargs)
    monkeypatch.setattr(db,'rows',measured)
    view=load_view(db)
    assert count<20
    assert len(view['jobs'])==2
    assert len(filter_jobs(view['jobs']))==1
    assert len(filter_jobs(view['jobs'],scope='Todas las ofertas'))==2
    assert filter_jobs(view['jobs'],query='unmatched')==[]
    assert all(j['salary_label']=='No publicado' and j['distance_label']=='Distancia pendiente' for j in view['jobs'])


def test_offer_detail_return_keeps_filters_and_cv_gate(db,profile,monkeypatch):
    seed(db,profile);app=app_for(db,monkeypatch)
    app.radio(key='ui_area').set_value('Ofertas de empleo').run()
    app.text_input(key='offer_search').set_value('Support').run()
    next(b for b in app.button if b.label=='Ver oferta').click().run()
    assert not app.exception
    next(b for b in app.button if b.label=='Preparar candidatura').click().run()
    assert not app.exception
    assert not any(b.label=='Preparar solicitud manual con mi CV aprobado' for b in app.button)
    next(b for b in app.button if b.label=='Revisar y aprobar CV').click().run()
    assert app.selectbox(key='ui_profile_section').value=='CV definitivo'
    app.radio(key='ui_area').set_value('Ofertas de empleo').run()
    assert app.text_input(key='offer_search').value=='Support'


def test_followup_is_accessible_within_application_and_retains_submission(db,profile,monkeypatch):
    from corkjobradar.config import now
    jid=seed(db,profile)[0]
    db.execute('INSERT INTO user_actions(job_id,action,notes,created_at) VALUES(?,?,?,?)',(jid,'solicitada','SYNTHETIC',now()))
    app=app_for(db,monkeypatch)
    app.radio(key='ui_area').set_value('Mis candidaturas').run()
    app.selectbox(key='applications_state').set_value(APPLICATION_STATES[3]).run()
    next(b for b in app.button if b.label=='Abrir candidatura').click().run()
    app.selectbox(key='ui_job_step').set_value('Seguimiento').run()
    next(w for w in app.selectbox if w.label=='Resultado que has contrastado').set_value('rechazada')
    next(w for w in app.text_area if w.label.startswith('Referencia del mensaje')).set_value('SYNTHETIC rejection message reviewed')
    next(b for b in app.button if b.label=='Guardar seguimiento').click().run()
    assert not app.exception
    view=load_view(db);row=next(j for j in view['jobs'] if j['id']==jid)
    assert row['application']==APPLICATION_STATES[6] and view['manual']==1 and view['confirmed']==0
