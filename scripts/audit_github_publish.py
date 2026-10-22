"""Inspect exact staged Git blobs; never print personal values or candidate secrets."""
import hashlib
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now


def git(*args):
    return subprocess.run(['git',*args],cwd=ROOT,capture_output=True,check=True).stdout


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',default='github-staged-audit.json');args=parser.parse_args()
    if not re.fullmatch(r'github-[a-z0-9-]+\.json',args.report):raise ValueError('SAFE_REPORT_NAME_REQUIRED')
    rows=git('ls-files','--stage','-z').split(b'\0');files=[];issues=[];contacts={}
    if (ROOT/'data/radar.sqlite3').is_file():
        from corkjobradar.db import Database
        from corkjobradar.autoapply.vault import candidate_snapshot
        candidate=candidate_snapshot(Database())
        contacts={k:str(candidate[k]) for k in ('email','phone','linkedin_url','full_name') if candidate.get(k)}
    patterns={
        'PRIVATE_KEY':rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
        'GITHUB_TOKEN':rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b',
        'AWS_ACCESS_KEY':rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
        'OPENAI_TOKEN':rb'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_\-]{40,}\b',
        'GOOGLE_API_KEY':rb'\bAIza[0-9A-Za-z_\-]{35}\b',
    }
    for row in rows:
        if not row:continue
        metadata,path=row.split(b'\t',1);mode,oid,stage=metadata.split()
        name=path.decode('utf-8');p=Path(name)
        if mode not in {b'100644',b'100755'} or stage!=b'0':issues.append({'path':name,'kind':'NONREGULAR_OR_UNMERGED'})
        if p.parts[0].lower() in {'data','logs','exports','.venv','.git'} or p.suffix.lower() in {'.dpapi','.sqlite','.sqlite3','.db','.pem','.key','.pfx','.p12','.zip'} or p.name in {'.env','secrets.toml'} or p.name.startswith('.env.') and p.name!='.env.example':
            issues.append({'path':name,'kind':'PRIVATE_PATH'})
        if p.suffix.lower() in {'.pdf','.docx'} and p.parts[:2]!=('tests','fixtures'):issues.append({'path':name,'kind':'PRIVATE_DOCUMENT'})
        content=git('cat-file','blob',oid.decode('ascii'))
        for kind,pattern in patterns.items():
            if re.search(pattern,content):issues.append({'path':name,'kind':kind})
        for key,value in contacts.items():
            if any(value.lower().encode(enc) in content.lower() for enc in ('utf-8','utf-16-le')):issues.append({'path':name,'kind':'REAL_PROFILE_'+key.upper()})
        files.append({'path':name,'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()})
    result={'checked_at':now(),'status':'PASS' if not issues else 'FAIL','staged_files':len(files),'staged_bytes':sum(f['bytes'] for f in files),
        'private_or_secret_matches':issues,'real_contacts_checked':bool(contacts),'sensitive_values_logged':False,'files':files}
    target=ROOT/'logs'/args.report
    if target.exists():raise ValueError('PRESERVE_PRIOR_PUBLISH_AUDIT')
    target.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='files'}))
    if issues:raise SystemExit(1)


if __name__=='__main__':main()
