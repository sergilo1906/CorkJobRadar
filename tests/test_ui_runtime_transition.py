"""Advanced runtime controls must follow the same pause guard as the main UI."""
import pytest
from streamlit.testing.v1 import AppTest
from corkjobradar import runtime as rt


@pytest.mark.parametrize('state',['PAUSING','STOPPING'])
def test_ui_advanced_runtime_has_no_resume_or_search_during_transition(db,state):
    rt.update(db,desired='PAUSED',state=state)
    app=AppTest.from_string('from corkjobradar.db import Database\n'
        'from corkjobradar.runtime_ui import render\n'
        'render(Database('+repr(str(db.path))+'))\n',default_timeout=30).run()
    assert not app.exception
    assert not any(b.label in {'Reanudar actividad','Buscar IT ahora'} for b in app.button)
    assert db.rows('SELECT live_enabled FROM autoapply_control')[0]['live_enabled']==0
