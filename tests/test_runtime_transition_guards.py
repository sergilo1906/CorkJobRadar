"""Prevent stale frontend/CLI commands from undoing a durable pause/stop."""
import pytest
from corkjobradar import runtime as rt


@pytest.mark.parametrize('state', ['PAUSING','STOPPING'])
@pytest.mark.parametrize('action', ['START','RESUME','SEARCH_NOW'])
def test_transition_guard_is_transactional_and_preserves_checkpoint(db,state,action):
    rt.update(db,desired='PAUSED' if state=='PAUSING' else 'STOPPED',state=state)
    before=rt.state(db)
    events=db.rows('SELECT * FROM local_runtime_events')
    with pytest.raises(ValueError,match='RUNTIME_TRANSITION_IN_PROGRESS'):
        rt.command(db,action)
    assert rt.state(db)==before
    assert db.rows('SELECT * FROM local_runtime_events')==events


def test_busy_search_now_does_not_schedule_another_search(db):
    rt.update(db,desired='RUNNING',state='PREPARING',active_kind='PREPARE')
    before=rt.state(db)
    with pytest.raises(ValueError,match='WORK_ALREADY_ACTIVE'):
        rt.command(db,'SEARCH_NOW')
    assert rt.state(db)==before


def test_pause_stop_and_resume_remain_idempotent_after_transition_finishes(db):
    rt.command(db,'START',search_now=False)
    rt.command(db,'PAUSE');rt.command(db,'PAUSE')
    assert rt.state(db)['state']=='PAUSED'
    rt.command(db,'RESUME',search_now=False)
    assert rt.state(db)['desired']=='RUNNING'
    rt.command(db,'STOP');rt.command(db,'STOP')
    assert rt.state(db)['desired']=='STOPPED'
    assert not db.rows('SELECT * FROM application_attempts')
