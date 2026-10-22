import json
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import pytest
from streamlit.testing.v1 import AppTest
from corkjobradar.config import ROOT,now
from corkjobradar.repository import save_job
from corkjobradar.models import Job
from corkjobradar.autoapply.policy import save_policy,pause
from corkjobradar.autoapply.eligibility import Decision
from corkjobradar.autoapply.store import save_plan,reserve,reconcile,prefinal_check
from corkjobradar.autoapply.vault import candidate_snapshot
from corkjobradar.autoapply.documents import render_cv,store_document
from corkjobradar.autoapply.workbench import prepare_offline_attempt
from corkjobradar.autoapply.engine import run_simulation
from test_autoapply_policy import policy_config,IT_DESCRIPTION
from test_autoapply_vault import populate
from test_autoapply_browser import FORM,FIXTURE_ORIGIN
from conftest import source


def setup_attempt(db,profile):
    populate(db);did=store_document(db,render_cv(candidate_snapshot(db),'pdf'),'pdf',True)
    config=policy_config();candidate=candidate_snapshot(db)
    config.update(candidate_facts_hash=candidate['_facts_hash'],authorized_document_ids=[did])
    pid=save_policy(db,config,'AUTHORIZE_SIMULATION')
    source(db,'html')
    jid=save_job(db,'fixture',Job(external_id='autoapply-test',title='IT Support',company='SYNTHETIC ONLY',location='Cork City',
                url='https://boards.greenhouse.io/synthetic/jobs/2',description=IT_DESCRIPTION,detail_complete=True,raw={'_synthetic_fixture':True}),profile=profile)
    job=db.rows('SELECT * FROM jobs WHERE id=?',(jid,))[0]
    db.execute("UPDATE jobs SET open_status='OPEN_CONFIRMED',last_verified_at=? WHERE id=?",(now(),jid))
    job=db.rows('SELECT * FROM jobs WHERE id=?',(jid,))[0]
    plan=save_plan(db,job,Decision('ALLOW',[],'synthetic-offline-policy',99),pid,candidate['_facts_hash'])
    aid=reserve(db,plan,job)
    return aid,job


def test_full_offline_pipeline_retains_transitions_and_zero_submissions(db,profile):
    aid,job=setup_attempt(db,profile)
    result=prepare_offline_attempt(db,aid,{FIXTURE_ORIGIN+'/form':FORM})
    assert result['state']=='SIMULADA_SIN_ENVIO' and result['posts']==0
    events=db.rows('SELECT * FROM application_events WHERE attempt_id=?',(aid,))
    assert [e['after_state'] for e in events if e['kind']=='STATE_CHANGED']==['PREPARADA','RELLENANDO','LISTA_PARA_ENVIO','SIMULADA_SIN_ENVIO']
    assert len(db.rows('SELECT * FROM application_answers'))==2
    assert not db.rows('SELECT * FROM user_actions')
    assert not db.rows('SELECT id FROM application_attempts WHERE confirmation_reference IS NOT NULL')
    assert 'synthetic@example.invalid' not in json.dumps(events)


def test_pause_just_before_final_prevents_new_send_and_is_persistent(db,profile):
    aid,job=setup_attempt(db,profile)
    result=prepare_offline_attempt(db,aid,{FIXTURE_ORIGIN+'/form':FORM},before_final=lambda:pause(db))
    assert result['state']=='CANCELADA' and result['posts']==0
    assert db.rows('SELECT paused FROM autoapply_control')[0]['paused']==1
    assert len(db.rows('SELECT * FROM application_reservations'))==1


def test_profile_change_during_fill_is_not_silently_accepted(db,profile):
    from corkjobradar.autoapply.vault import approve_fact
    aid,job=setup_attempt(db,profile)
    result=prepare_offline_attempt(db,aid,{FIXTURE_ORIGIN+'/form':FORM},
        before_final=lambda:approve_fact(db,'availability','SYNTHETIC CHANGED','Synthetic fixture',True))
    assert result['state']=='CANCELADA' and result['posts']==0


def test_run_processes_every_job_with_disabled_policy_and_is_idempotent(db,profile):
    source(db,'html')
    for n in range(37):
        save_job(db,'fixture',Job(external_id=str(n),title='Synthetic only '+str(n),url='https://example.org/'+str(n)),profile=profile)
    result=run_simulation(db)
    assert result['processed']==37 and result['BLOCK']==37 and result['confirmed_live']==0
    again=run_simulation(db)
    assert again['processed']==37
    assert len(db.rows('SELECT * FROM application_plans'))==37
    assert not db.rows('SELECT * FROM application_attempts')


def test_autoapply_ui_off_pause_policy_validation_and_no_autostart(db,monkeypatch):
    import corkjobradar.db as database_module
    import corkjobradar.autoapply.ui as ui
    monkeypatch.setattr(database_module,'Database',lambda:db)
    launched=[];monkeypatch.setattr(ui,'launch_simulation',lambda:launched.append(True) or 123)
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
    assert not app.exception and len(app.radio(key='ui_area').options)==6 and launched==[]
    assert not db.rows('SELECT * FROM application_plans')
    app.radio(key='ui_area').set_value('AutoApply').run()
    app.checkbox(key='aa_tools').check().run()
    app.selectbox(key='aa_tool').set_value('Simulación y auditoría histórica').run()
    next(b for b in app.button if b.label=='PAUSAR TODO AUTOAPPLY').click().run()
    assert not app.exception and db.rows('SELECT paused FROM autoapply_control')[0]['paused']
    app.radio(key='ui_area').set_value('Perfil y configuración').run()
    app.selectbox(key='ui_profile_section').set_value('Política de candidaturas').run()
    next(b for b in app.button if b.label=='Guardar y autorizar simulación').click().run()
    assert not app.exception and not db.rows('SELECT * FROM autoapply_policies')
    app.radio(key='ui_area').set_value('AutoApply').run()
    app.checkbox(key='aa_tools').check().run()
    app.selectbox(key='aa_tool').set_value('Simulación y auditoría histórica').run()
    next(b for b in app.button if b.label=='Ejecutar simulación completa sin envíos').click().run()
    assert not app.exception and launched==[True]
