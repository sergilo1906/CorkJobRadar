"""Isolated hypothetical permitted capability, never enabled on a public ATS."""
import json
import httpx
import pytest
from corkjobradar.config import now
from corkjobradar.autoapply.forms import inspect_job_form
from corkjobradar.autoapply.final_gate import final_submission_gate
from corkjobradar.autoapply.store import transition
from test_autoapply_network_e2e import setup_network_application
from test_autoapply_public_forms import schema
from conftest import client


def prepared(db,profile,monkeypatch):
    aid,job,data=setup_network_application(db,profile)
    form=schema();form['id']=1
    def response(req):return httpx.Response(200,text='User-agent: *\nAllow: /') if req.url.path=='/robots.txt' else httpx.Response(200,json=form)
    with client(profile,response) as web:inspection=inspect_job_form(db,job['id'],web)
    cap={**data['platform'],'api_submission_verified':True}
    import corkjobradar.autoapply.final_gate as gate
    monkeypatch.setattr(gate,'platform_for',lambda url:cap)
    db.execute('UPDATE application_attempts SET document_id=?,form_hash=? WHERE id=?',(data['candidate']['cv_document_id'],inspection['form_hash'],aid))
    for state in ('PREPARADA','RELLENANDO','LISTA_PARA_ENVIO'):transition(db,aid,state)
    return aid,job,inspection,cap


def test_full_gate_rechecks_actual_stored_application_without_dispatch(db,profile,monkeypatch):
    aid,job,inspection,cap=prepared(db,profile,monkeypatch)
    result=final_submission_gate(db,aid,inspection['inspection_id'])
    assert result['job_id']==job['id'] and not result['submitted'] and not result['live_activation_authorized']
    assert {'name','email','resume','linkedin'}==set(result['resolved_fields'])
    assert not db.rows('SELECT * FROM user_actions')
    assert db.rows('SELECT live_enabled FROM autoapply_control')[0]['live_enabled']==0


@pytest.mark.parametrize('changed,code',[
    ('route','NO_VERIFIED_ROUND_TRIP'),('new_analysis','REQUIREMENTS_ANALYSIS_INCOMPLETE'),
    ('permission','AUTOMATION_PERMISSION_MISSING'),('completion','COMPLETION_UNVERIFIED'),
    ('target','APPLICATION_TARGET_CHANGED'),('form','FINAL_FORM_HASH_CHANGED'),
])
def test_full_gate_catches_changes_not_covered_by_original_selection(db,profile,monkeypatch,changed,code):
    aid,job,inspection,cap=prepared(db,profile,monkeypatch)
    if changed=='route':db.execute('DELETE FROM commute_checks WHERE job_id=?',(job['id'],))
    if changed=='new_analysis':
        db.execute('INSERT INTO job_analyses(job_id,content_hash,profile_hash,analyzer_version,status,result,created_at) VALUES(?,?,?,?,?,?,?)',
            (job['id'],job['content_hash'],'SYNTHETIC','NEW_INCOMPLETE','PARCIAL',json.dumps({'analysis_completeness':'PARCIAL'}),now()))
    if changed=='permission':cap['automation_permitted']=False
    if changed=='completion':cap['api_submission_verified']=False
    if changed=='target':db.execute("UPDATE application_attempts SET target_url='https://example.org/changed' WHERE id=?",(aid,))
    if changed=='form':db.execute("UPDATE application_attempts SET form_hash='changed' WHERE id=?",(aid,))
    with pytest.raises(PermissionError,match=code):final_submission_gate(db,aid,inspection['inspection_id'])
    assert not db.rows('SELECT * FROM user_actions')
