import json
import pytest
from scripts.continue_after_reader import continue_once,PHASES
from corkjobradar.worker import create_run


def test_workflow_waits_for_reader_then_executes_all_phases_once(db,tmp_path):
    rid=create_run(db,kind='analyze');path=tmp_path/'workflow.json';calls=[]
    def finish(_):db.execute("UPDATE scan_runs SET status='completed' WHERE id=?",(rid,))
    def execute(arguments,log):calls.append(arguments);return 0
    result=continue_once(db,rid,path,executor=execute,sleeper=finish,documents=False)
    assert result['status']=='COMPLETED' and result['live_enabled'] is False
    assert calls==[args for name,args in PHASES]
    assert continue_once(db,rid,path,executor=execute,documents=False)==result
    assert len(calls)==len(PHASES)
    assert not any('--live' in args for args in calls)


def test_workflow_cancellation_stops_without_next_scan(db,tmp_path):
    rid=create_run(db,kind='analyze');db.execute('UPDATE scan_runs SET cancel_requested=1 WHERE id=?',(rid,))
    result=continue_once(db,rid,tmp_path/'workflow.json',executor=lambda *a:pytest.fail('Cancelled parent must stop'),documents=False)
    assert result['status']=='STOPPED_PARENT_NOT_COMPLETED'


def test_workflow_records_failure_and_never_blindly_restarts(db,tmp_path):
    rid=create_run(db,kind='analyze');db.execute("UPDATE scan_runs SET status='completed' WHERE id=?",(rid,))
    path=tmp_path/'workflow.json';calls=[]
    def fail(args,log):calls.append(args);return 2
    result=continue_once(db,rid,path,executor=fail,documents=False)
    assert result['status']=='STOPPED_PHASE_ERROR' and len(calls)==1
    assert result['phases'][0]['exit_code']==2
    with pytest.raises(RuntimeError,match='REVIEW_NOT_BLIND_RESTART'):continue_once(db,rid,path,executor=fail,documents=False)


def test_workflow_does_not_overwrite_readings_when_resources_are_low(tmp_path,monkeypatch):
    import corkjobradar.local_model as model
    from scripts.continue_after_reader import execute_phase
    monkeypatch.setattr(model,'available_ram',lambda:700_000_000)
    with pytest.raises(RuntimeError,match='INSUFFICIENT_FREE_RAM'):
        execute_phase(('-m','corkjobradar','analyze','--local','--pending'),tmp_path/'not-started.log')
    assert not (tmp_path/'not-started.log').exists()


def test_checkpoint_retries_transient_windows_replace_without_truncating(tmp_path,monkeypatch):
    from pathlib import Path
    from scripts.continue_after_reader import checkpoint
    import scripts.continue_after_reader as workflow
    target=tmp_path/'state.json';target.write_text('{"previous":true}',encoding='utf-8')
    original=Path.replace;calls=[]
    def busy(self,destination):
        calls.append(str(self))
        if len(calls)==1:
            assert json.loads(target.read_text())=={'previous':True}
            raise PermissionError('SYNTHETIC_TRANSIENT_WINDOWS_FILE_LOCK')
        return original(self,destination)
    monkeypatch.setattr(Path,'replace',busy);monkeypatch.setattr(workflow.time,'sleep',lambda _:None)
    checkpoint(target,{'status':'NEW'},documents=False)
    assert len(calls)==2 and json.loads(target.read_text())['status']=='NEW'
