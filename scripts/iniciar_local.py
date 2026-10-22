"""Optional per-user launcher. No registry, Startup installation or system service."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT
from corkjobradar.db import Database
from corkjobradar.worker import process_lock
from corkjobradar.runtime import Watchdog,state,alive,update,process_stamp,ensure_supervisor


def port_open(port=8501):
    with socket.socket() as sock:
        sock.settimeout(.3)
        return sock.connect_ex(('127.0.0.1',port))==0


def verified_port_owner(row):
    if not alive(row['owner_pid'],row['owner_stamp']):return False
    if os.name!='nt':return False
    query="$p=(Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess; if ($p) { $parent=(Get-CimInstance Win32_Process -Filter ('ProcessId='+$p)).ParentProcessId; Write-Output ($p.ToString()+','+$parent.ToString()) }"
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',query],capture_output=True,text=True,timeout=15,
                           creationflags=subprocess.CREATE_NO_WINDOW)
    try:pid,parent=map(int,result.stdout.strip().split(','))
    except ValueError:return False
    return row['owner_pid'] in {pid,parent}


def main():
    db=Database()
    with process_lock(db.path.with_suffix('.launcher.lock')):
        row=state(db)
        if port_open():
            if not verified_port_owner(row):raise RuntimeError('PORT_8501_IN_USE_OWNER_NOT_VERIFIED')
            ensure_supervisor(db,row['owner_pid']);return
        temp=ROOT/'data/runtime-temp';temp.mkdir(exist_ok=True)
        env=os.environ.copy();env.update(PYTHONIOENCODING='utf-8',TEMP=str(temp),TMP=str(temp))
        with (ROOT/'logs/local-runtime-streamlit.log').open('a',encoding='utf-8') as log:
            child=subprocess.Popen([sys.executable,'-m','streamlit','run',str(ROOT/'app.py'),'--server.address','127.0.0.1',
                '--server.port','8501','--server.headless','true','--browser.gatherUsageStats','false'],cwd=ROOT,env=env,stdout=log,stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        update(db,owner_pid=child.pid,owner_stamp=process_stamp(child.pid))
        watchdog=Watchdog(db.path,child.pid)
        deadline=time.monotonic()+30
        while not port_open():
            if child.poll() is not None or time.monotonic()>deadline:
                watchdog.close();raise RuntimeError('LOCAL_STREAMLIT_DID_NOT_START')
            time.sleep(.2)
    # A second launcher can now inspect and reuse this server; lifetime is not
    # the startup mutex. The watchdog remains alive without any browser tab.
    try:
        while child.poll() is None:time.sleep(2)
    finally:watchdog.close()


if __name__=='__main__':main()
