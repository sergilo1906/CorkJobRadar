from corkjobradar.db import Database
from corkjobradar.config import load_profile
from corkjobradar.cli import doctor

def test_clean_db_and_restart(tmp_path):
    path = tmp_path / 'radar.sqlite3'
    db = Database(path)
    assert db.rows('SELECT * FROM jobs') == []
    db.event('INSTALL', {'test':True})
    assert len(Database(path).rows('SELECT * FROM audit_events')) == 1
    assert doctor(db)['sqlite'] == 'ok'

def test_profile_no_car():
    p = load_profile()
    assert p['origin_neighborhood'] == 'Ballinlough'
    assert p['owns_car'] is False
    assert p['non_it_max_bus_transfers'] == 0
    assert p['it_weekdays_required'] is False
