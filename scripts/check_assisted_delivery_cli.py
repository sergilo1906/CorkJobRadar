"""Reproducible read-only health checks. LIVE rejection is required, never enabled."""
import json
from pathlib import Path
import subprocess
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now


def main(report_name='assisted-delivery-cli-check.json'):
    if not re.fullmatch(r'[a-z0-9-]+\.json',report_name):raise ValueError('INVALID_LOCAL_REPORT_NAME')
    output=ROOT/'logs'/report_name
    if output.exists():raise FileExistsError('PRESERVE_PRIOR_CLI_CHECK')
    checks=[]
    commands=[(['-m','pip','check'],0,False),
              (['-m','compileall','-q','corkjobradar','scripts','tests'],0,False),
              (['-m','corkjobradar','doctor'],0,True),
              (['-m','corkjobradar','autoapply','doctor'],0,True),
              (['-m','corkjobradar','autoapply','readiness'],0,True),
              (['-m','corkjobradar','autoapply','interventions'],0,True),
              (['-m','corkjobradar','autoapply','run','--live'],2,True)]
    for args,expected,as_json in commands:
        process=subprocess.run([sys.executable,'-X','utf8',*args],cwd=ROOT,capture_output=True,encoding='utf-8',timeout=90)
        check={'command':args,'exit_code':process.returncode,'expected_exit_code':expected,'passed':process.returncode==expected}
        if as_json:
            try:check['result']=json.loads(process.stdout)
            except ValueError:check['valid_json']=False;check['passed']=False
        else:check['no_dependency_conflicts']=not process.returncode if args[:3]==['-m','pip','check'] else None
        checks.append(check)
    report={'checked_at':now(),'checks':checks,'all_passed':all(c['passed'] for c in checks),'live_enabled':False}
    output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    assert report['all_passed']
    print(json.dumps({'checked_at':report['checked_at'],'checks':len(checks),'all_passed':True,'live_command_exit':checks[-1]['exit_code']}))


if __name__=='__main__':main()
