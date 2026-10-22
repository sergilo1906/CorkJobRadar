from concurrent.futures import ThreadPoolExecutor
from corkjobradar.db import Database
from corkjobradar.worker import create_run
from conftest import source


def test_two_simultaneous_starts_create_one_active_run(db):
    source(db,'greenhouse')
    def start(_):
        try:return create_run(Database(db.path))
        except RuntimeError:return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(start,range(2)))
    assert len([r for r in results if r is not None])==1
    assert len(db.rows('SELECT * FROM scan_runs'))==1
    assert len(db.rows('SELECT * FROM source_runs'))==1
