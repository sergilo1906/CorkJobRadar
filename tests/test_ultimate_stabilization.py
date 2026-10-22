import json
import sqlite3
from corkjobradar.db import Database,SCHEMA
from corkjobradar.models import Job
from corkjobradar.repository import save_job,all_jobs,latest_analyses
from corkjobradar.worker import create_run
from corkjobradar.config import now
from corkjobradar.audit import coverage
from conftest import source

def test_v1_migration_backed_up_without_losing_history(tmp_path):
    path=tmp_path/'existing.sqlite3'
    with sqlite3.connect(path) as con:
        con.executescript(SCHEMA+'\nPRAGMA user_version=1;')
        con.execute('INSERT INTO audit_events(created_at,kind,details) VALUES(?,?,?)',(now(),'HISTORICAL','{}'))
    db=Database(path)
    assert db.rows('PRAGMA user_version')[0]['user_version']==12
    assert db.rows('SELECT kind FROM audit_events')[0]['kind']=='HISTORICAL'
    copies=list((tmp_path/'backups').glob('*.sqlite3'))
    assert len(copies)==1
    with sqlite3.connect(copies[0]) as backup:
        assert backup.execute('PRAGMA user_version').fetchone()[0]==1
        assert backup.execute('SELECT count(*) FROM audit_events').fetchone()[0]==1
    assert db.rows('PRAGMA foreign_key_check')==[]

def test_new_repeated_changed_are_observations_not_current_state(db,profile):
    source(db,'greenhouse')
    job=Job(external_id='same',title='IT Support',company='Fixture',location='Cork City',url='https://fixture.test/same')
    for expected in ('NEW','REPEATED','CHANGED'):
        rid=create_run(db)
        if expected=='CHANGED': job.description='Updated description from fixture'
        save_job(db,'fixture',job,rid,profile)
        save_job(db,'fixture',job,rid,profile)  # Repetir la tarjeta no pierde NEW/CHANGED.
        assert coverage(db,rid)['changes']=={expected:1}
        db.execute("UPDATE scan_runs SET status='completed' WHERE id=?",(rid,))
    assert len(db.rows('SELECT * FROM jobs'))==1
    assert db.rows('SELECT change_status FROM run_jobs ORDER BY run_id')[0]['change_status']=='NEW'

def test_batch_query_count_is_constant_for_2000_jobs(db,profile):
    source(db,'greenhouse')
    with db.connect() as con:
        for index in range(2000):
            jid=str(index)
            con.execute('''INSERT INTO jobs(id,title,company,location,url,first_seen_at,last_seen_at,content_hash,raw)
                           VALUES(?,?,?,?,?,?,?,?,?)''',(jid,'SYNTHETIC ONLY','Fixture','Cork City',f'https://fixture.test/{index}',now(),now(),'hash','{}'))
            result={'facts':{'experience':{'value':0}},'depth':'ANALISIS_BASICO'}
            con.execute('''INSERT INTO job_analyses(job_id,content_hash,profile_hash,analyzer_version,status,result,created_at)
                           VALUES(?,?,?,?,?,?,?)''',(jid,'hash','test','test','PARCIAL_POR_DATOS',json.dumps(result),now()))
    queries=[]
    original=db.rows
    def counted(sql,params=()):
        queries.append(sql)
        return original(sql,params)
    db.rows=counted
    analyses=latest_analyses(db)
    rows=all_jobs(db,analyses)
    assert len(rows)==2000 and len(queries)==2
    assert rows[0]['experience']==0

def test_dns_rebinding_is_rejected_at_actual_connection(monkeypatch):
    from corkjobradar.http import PublicNetworkBackend
    import socket,pytest
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:[(socket.AF_INET,socket.SOCK_STREAM,6,'',('127.0.0.1',443))])
    with pytest.raises(ValueError,match='DNS'):
        PublicNetworkBackend().connect_tcp('public.example',443)

def test_connection_uses_checked_numeric_ip_not_hostname(monkeypatch):
    from corkjobradar.http import PublicNetworkBackend
    import socket,httpcore
    captured=[]
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:[(socket.AF_INET,socket.SOCK_STREAM,6,'',('1.1.1.1',443))])
    monkeypatch.setattr(httpcore.SyncBackend,'connect_tcp',lambda self,*args:captured.append(args) or 'stream')
    assert PublicNetworkBackend().connect_tcp('public.example',443)=='stream'
    assert captured[0][0]=='1.1.1.1'
