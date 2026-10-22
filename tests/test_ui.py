from streamlit.testing.v1 import AppTest
from corkjobradar.models import Job
from corkjobradar.repository import save_job
from corkjobradar.analysis import analyze_job
from corkjobradar.config import ROOT
from corkjobradar.exporting import export_all
from conftest import source

def test_ui_filters_details_and_xlsx_on_isolated_database(db,profile,monkeypatch,tmp_path):
    import corkjobradar.db as database_module
    import corkjobradar.exporting as exporting_module
    source(db,'greenhouse')
    for index,title in enumerate(['IT Support','Warehouse Operative','Production Operative']):
        jid=save_job(db,'fixture',Job(external_id=str(index),title=title,company='SYNTHETIC TEST ONLY',
                     location='Cork City',url=f'https://fixture.test/{index}',description=('Synthetic tasks and duties, training provided. '*15),detail_complete=True),profile=profile)
        analyze_job(db,jid,profile)
    monkeypatch.setattr(database_module,'Database',lambda:db)
    monkeypatch.setattr(exporting_module,'export_all',lambda _db:export_all(_db,tmp_path/'ui-exports'))
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
    assert not app.exception
    assert len(app.radio(key='ui_area').options)==6
    app.radio(key='ui_area').set_value('Ofertas de empleo').run()
    app.toggle(key='offers_advanced_table').set_value(True).run()
    assert next(d.value for d in app.dataframe if 'title' in d.value.columns and 'company' in d.value.columns).shape[0]==3
    next(m for m in app.multiselect if m.label=='Sector').set_value(['IT']).run()
    assert not app.exception
    table=next(d.value for d in app.dataframe if 'title' in d.value.columns and 'company' in d.value.columns)
    assert table.shape[0]==1
    assert table.iloc[0]['title']=='IT Support'
    app.radio(key='ui_area').set_value('Actividad y notificaciones').run()
    app.selectbox(key='activity_section').set_value('Exportar informes').run()
    next(b for b in app.button if b.label=='Exportar todo').click().run()
    assert not app.exception
    assert len(list((tmp_path/'ui-exports').glob('*.xlsx')))==1

def test_ui_starts_persistent_worker_without_blocking(db,monkeypatch):
    import corkjobradar.db as database_module
    import corkjobradar.worker as worker_module
    source(db,'greenhouse')
    launched=[]
    monkeypatch.setattr(database_module,'Database',lambda:db)
    monkeypatch.setattr(worker_module,'spawn_worker',lambda rid:launched.append(rid))
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
    app.radio(key='ui_area').set_value('Actividad y notificaciones').run()
    app.selectbox(key='activity_section').set_value('Avanzado').run()
    app.selectbox(key='activity_tool').set_value('Operaciones de mantenimiento').run()
    next(s for s in app.selectbox if s.label=='Operación').set_value('Buscar catálogo completo').run()
    next(b for b in app.button if b.label=='Ejecutar operación seleccionada').click().run()
    assert not app.exception
    assert len(launched)==1
    assert db.rows('SELECT status FROM scan_runs')[0]['status']=='running'
    assert len(db.rows('SELECT * FROM source_runs'))==1

def test_ui_records_response_and_queues_one_local_analysis(db,profile,monkeypatch):
    import corkjobradar.db as database_module
    import corkjobradar.worker as worker_module
    import corkjobradar.local_model as model_module
    monkeypatch.setattr(model_module,'is_validated_model',lambda:True)
    source(db,'greenhouse')
    jid=save_job(db,'fixture',Job(external_id='ui-new',title='IT Support',company='SYNTHETIC TEST ONLY',
                 location='Cork City',url='https://fixture.test/ui',description='Synthetic only. '*40,detail_complete=True),profile=profile)
    monkeypatch.setattr(database_module,'Database',lambda:db)
    launched=[];monkeypatch.setattr(worker_module,'spawn_worker',lambda rid:launched.append(rid))
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
    app.radio(key='ui_area').set_value('Ofertas de empleo').run()
    app.selectbox(key='offer_scope').set_value('Todas las ofertas').run()
    next(b for b in app.button if b.label=='Ver oferta').click().run()
    app.checkbox(key='detail_advanced').check().run()
    next(s for s in app.selectbox if s.label=='Marcar oferta').set_value('entrevista')
    next(t for t in app.text_area if t.label=='Notas personales').set_value('SYNTHETIC response')
    next(b for b in app.button if b.label=='Guardar marca y notas').click().run()
    assert not app.exception and db.rows('SELECT action FROM user_actions')[0]['action']=='entrevista'
    next(b for b in app.button if b.label=='Leer esta oferta en español con el modelo local').click().run()
    assert not app.exception and len(launched)==1
    import json
    assert json.loads(db.rows('SELECT profile FROM scan_runs')[0]['profile'])['analyzer']=='llama'
    assert db.rows('SELECT job_id,kind FROM task_queue')==[{'job_id':jid,'kind':'analyze'}]

def test_ui_calculates_gtfs_both_directions_on_isolated_feed(db,profile,monkeypatch,tmp_path):
    import corkjobradar.db as database_module
    import corkjobradar.ui_transport as ui_transit
    from corkjobradar.transit import Transit,import_gtfs
    from test_transit import make_feed
    from datetime import date,time
    feed=tmp_path/'synthetic.zip';make_feed(feed);transport_path=tmp_path/'transport.sqlite3'
    import_gtfs(feed,{'url':'https://fixture.test/GTFS'},transport_path)
    monkeypatch.setattr(ui_transit,'TRANSIT_PATH',transport_path)
    monkeypatch.setattr(ui_transit,'Transit',lambda:Transit(transport_path))
    source(db,'html')
    save_job(db,'fixture',Job(external_id='route-ui',title='Warehouse Operative',url='https://fixture.test/route-job',location='Cork City'),profile=profile)
    monkeypatch.setattr(database_module,'Database',lambda:db)
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
    app.radio(key='ui_area').set_value('Perfil y configuración').run()
    app.selectbox(key='ui_profile_section').set_value('Sistema avanzado').run()
    for key,value in [('origin_out','a'),('destination_out','b'),('origin_back','b'),('destination_back','a')]:
        app.selectbox(key=key).set_value(value)
    app.date_input(key='bus_day').set_value(date(2026,10,19))
    app.time_input(key='shift_start').set_value(time(9));app.time_input(key='shift_end').set_value(time(17))
    for input in app.number_input:
        if input.label.startswith(('Minutos a pie comprobados','Vuelta: minutos')):input.set_value(5)
    next(b for b in app.button if b.label=='Calcular ida y vuelta sin transbordos').click().run()
    assert not app.exception
    plan=app.session_state['bus_plan']
    assert plan['outbound_count']==plan['return_count']==1
    assert plan['schedule_check']['checked_shift_count']==1
    assert not plan['schedule_check']['route_autoapproved']
    assert not db.rows('SELECT * FROM commute_checks')  # Calculation alone never asserts accessibility.
