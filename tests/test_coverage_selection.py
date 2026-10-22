from corkjobradar.audit import coverage,coverage_markdown
from corkjobradar.worker import create_run
from conftest import source


def test_selected_sources_have_their_own_denominator(db):
    source(db,'greenhouse','selected')
    source(db,'lever','other-active')
    source(db,'ashby','disabled')
    db.execute("UPDATE sources SET enabled=0,notes='Pendiente de implementar' WHERE id='disabled'")
    rid=create_run(db,['selected'])
    db.execute("UPDATE source_runs SET status='completed',pagination_complete=1 WHERE run_id=?",(rid,))
    db.execute("UPDATE scan_runs SET status='completed' WHERE id=?",(rid,))
    report=coverage(db,rid)
    assert report['selected_sources']==1
    assert report['enabled_sources_current_catalog']==2
    assert report['selected_source_ids']==['selected']
    assert report['enabled_unselected_source_ids']==['other-active']
    assert report['fully_examined_sources']==1
    reasons={r['source']:r for r in report['uncovered_sources']}
    assert reasons['other-active']['reason']=='NO_SELECCIONADA_EN_ESTA_EJECUCION'
    assert reasons['disabled']['reason']=='DESACTIVADA_NO_SELECCIONADA'
    assert reasons['disabled']['catalog_note']=='Pendiente de implementar'
    assert 'Seleccionadas en esta ejecución: 1; activas actualmente: 2' in coverage_markdown(report)


def test_blocked_selected_source_keeps_actual_failure(db):
    source(db,'greenhouse','selected')
    rid=create_run(db)
    db.execute("UPDATE source_runs SET status='blocked',message='CAPTCHA: acceso manual' WHERE run_id=?",(rid,))
    report=coverage(db,rid)
    assert report['selected_sources']==1
    assert report['uncovered_sources'][0]['selected_in_run'] is True
    assert report['uncovered_sources'][0]['reason']=='CAPTCHA: acceso manual'
    assert report['listing_coverage_status']=='PARCIAL'
