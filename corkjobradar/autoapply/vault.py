"""Windows user-bound DPAPI vault. Plain files exist only in explicit downloads or short-lived workspaces."""
import ctypes
from ctypes import wintypes
import csv
import getpass
import io
import json
import os
from pathlib import Path
import re
import subprocess
from uuid import uuid4
from datetime import datetime
from ..config import ROOT, now, digest
from .policy import event, pause


class Blob(ctypes.Structure):
    _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]


def protect(data:bytes, decrypt=False):
    if os.name!='nt':raise RuntimeError('VAULT_REQUIRES_WINDOWS_DPAPI')
    buffer=ctypes.create_string_buffer(data)
    source=Blob(len(data),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)));target=Blob()
    crypt=ctypes.WinDLL('crypt32',use_last_error=True)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    fn=crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    fn.restype=wintypes.BOOL
    if not fn(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target)):
        raise RuntimeError('DPAPI_OPERATION_FAILED')
    try:return ctypes.string_at(target.data,target.size)
    finally:kernel.LocalFree(target.data)


def private_folder(db):
    folder=(db.path.parent/'autoapply-private').resolve()
    # All databases used by this app/tests stay under the project. Reject an external destination.
    if not folder.is_relative_to(ROOT.resolve()):raise ValueError('VAULT_PATH_OUTSIDE_PROJECT')
    folder.mkdir(exist_ok=True)
    marker=folder/'.acl-configured'
    if os.name=='nt' and not marker.exists():
        result=subprocess.run(['whoami','/user','/fo','csv','/nh'],capture_output=True,text=True,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
        sid=list(csv.reader(io.StringIO(result.stdout.strip())))[0][1]
        if not re.fullmatch(r'S-1-[0-9-]+',sid):raise RuntimeError('LOCAL_USER_SID_UNAVAILABLE')
        subprocess.run(['icacls',str(folder),'/inheritance:r','/grant:r','*'+sid+':(OI)(CI)F','/grant:r','*S-1-5-18:(OI)(CI)F'],
                       capture_output=True,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
        marker.write_text('Windows current user and SYSTEM only',encoding='utf-8')
    return folder


def approve_fact(db, field, value, origin, confirmed=False):
    simple={'full_name','first_name','last_name','email','phone','location','linkedin_url','work_authorization','availability'}
    if field not in simple and not re.fullmatch(r'(claim|answer):[a-z0-9_-]{1,80}',field):raise ValueError('UNSUPPORTED_FACT_FIELD')
    if not confirmed or not origin.strip():raise ValueError('EXPLICIT_FACT_APPROVAL_REQUIRED')
    if field in simple and (not isinstance(value,str) or not value.strip() or len(value)>10000):raise ValueError('FACT_REQUIRES_BOUNDED_TEXT')
    if field=='work_authorization' and value not in {'IRELAND_AUTHORIZED','SPONSORSHIP_REQUIRED','UNKNOWN'}:raise ValueError('INVALID_WORK_AUTHORIZATION')
    if field=='email' and (not isinstance(value,str) or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value)):raise ValueError('INVALID_EMAIL')
    if field=='linkedin_url' and not re.fullmatch(r'https://(?:www\.)?linkedin\.com/in/[A-Za-z0-9_%\-]+/?',value):raise ValueError('INVALID_LINKEDIN_PROFILE_URL')
    if not isinstance(value,(str,dict)) or not value:raise ValueError('EMPTY_OR_INVALID_FACT')
    if field.startswith('claim:') and (not isinstance(value,dict) or value.get('section') not in {'Profile','Projects','Additional Experience','Education','Experience','Skills','Languages','Availability'} or not value.get('text_en')):
        raise ValueError('CLAIM_REQUIRES_APPROVED_ENGLISH_TEXT_AND_SECTION')
    if field.startswith('answer:') and (not isinstance(value,dict) or not all(value.get(k) for k in ('question','host','answer'))):
        raise ValueError('ANSWER_REQUIRES_EXACT_QUESTION_HOST_AND_ANSWER')
    encrypted=protect(json.dumps({'value':value,'origin':origin},ensure_ascii=False).encode('utf-8'))
    with db.transaction():
        db.execute('UPDATE candidate_facts SET revoked_at=? WHERE field=? AND revoked_at IS NULL',(now(),field))
        fid=db.execute('INSERT INTO candidate_facts(field,encrypted_value,origin,approved_at,local_user) VALUES(?,?,?,?,?)',
                       (field,encrypted,'USER_CONFIRMED',now(),getpass.getuser()))
        if not field.startswith('answer:'):
            db.execute('UPDATE candidate_documents SET revoked_at=? WHERE revoked_at IS NULL',(now(),))
        event(db,'FACT_APPROVED',{'fact_id':fid,'field_hash':digest(field)})
        if db.rows('SELECT enabled FROM autoapply_control')[0]['enabled']:pause(db,'CANDIDATE_FACTS_CHANGED',alert=True)
    return fid


def candidate_snapshot(db):
    rows=db.rows('SELECT * FROM candidate_facts WHERE revoked_at IS NULL ORDER BY id')
    result={};ids={};claims=[];answers=[]
    for row in rows:
        value=json.loads(protect(row['encrypted_value'],decrypt=True))['value']
        if row['field'].startswith('claim:'):claims.append({'id':row['id'],**value})
        elif row['field'].startswith('answer:'):answers.append({'id':row['id'],**value})
        else:result[row['field']]=value;ids[row['field']]=row['id']
    result.update(_facts_hash=digest([(r['id'],r['field']) for r in rows]),
                  _cv_facts_hash=digest([(r['id'],r['field']) for r in rows if not r['field'].startswith('answer:')]),
                  _fact_ids=ids,_claims=claims,_answers=answers)
    docs=db.rows("SELECT id FROM candidate_documents WHERE kind='CV' AND facts_hash=? AND approved_at IS NOT NULL AND revoked_at IS NULL ORDER BY approved_at DESC,id DESC LIMIT 1",(result['_cv_facts_hash'],))
    if docs:result['cv_document_id']=docs[0]['id']
    return result


def save_clearance(db,job_id,payload,expires_at,confirmed=False):
    """Record factual checks; this does not approve sending an individual application."""
    if not confirmed:raise ValueError('EXPLICIT_FACTUAL_REVIEW_REQUIRED')
    from zoneinfo import ZoneInfo
    if datetime.fromisoformat(expires_at)<=datetime.now(ZoneInfo('Europe/Dublin')):raise ValueError('CLEARANCE_ALREADY_EXPIRED')
    job=db.rows('SELECT * FROM jobs WHERE id=?',(job_id,))[0]
    allowed={'requirements_met','legal_eligibility','experience_met','schedule','contract','full_time','salary','salary_unit','currency','remote_from_ireland','evidence','shift_start','shift_end','days'}
    if not isinstance(payload,dict) or set(payload)-allowed:raise ValueError('INVALID_CLEARANCE_FIELDS')
    evidence=payload.get('evidence',{})
    if not isinstance(evidence,dict) or not evidence:raise ValueError('SOURCE_QUOTES_AND_FACT_IDS_REQUIRED')
    facts=candidate_snapshot(db);claim_ids={r['id'] for r in facts['_claims']}|set(facts['_fact_ids'].values())
    checked_fields=['requirements_met','legal_eligibility','experience_met','schedule','contract','full_time']
    checked_fields.extend(k for k in ('salary','remote_from_ireland','shift_start','shift_end','days') if payload.get(k) is not None)
    for field in ('requirements_met','legal_eligibility','experience_met','full_time','remote_from_ireland'):
        if field in payload and not isinstance(payload[field],bool):raise ValueError('BOOLEAN_CLEARANCE_FIELD_REQUIRED')
    for field in checked_fields:
        e=evidence.get(field,{})
        if field not in payload or not e.get('quote') or e['quote'] not in job['description'] or not e.get('fact_ids') or not set(e['fact_ids']).issubset(claim_ids):
            raise ValueError('CLEARANCE_REQUIRES_LITERAL_QUOTE_AND_APPROVED_FACTS:'+field)
    return db.execute('''INSERT INTO job_clearances(job_id,content_hash,facts_hash,payload,approved_at,expires_at,local_user)
                         VALUES(?,?,?,?,?,?,?)''',(job_id,job['content_hash'],facts['_facts_hash'],json.dumps(payload),now(),expires_at,getpass.getuser()))


def clearance_for(db,job_id):
    rows=db.rows('SELECT * FROM job_clearances WHERE job_id=? ORDER BY id DESC LIMIT 1',(job_id,))
    if not rows:return {}
    row=rows[0]
    return {**json.loads(row['payload']),**{k:row[k] for k in ('content_hash','facts_hash','expires_at')}}


def approve_route(db,job_id,mode,evidence_url,details,transfers=0,confirmed=False):
    from ..http import validate_url
    from ..config import load_profile
    from ..geography import valid_commute
    if not confirmed or mode not in {'bicycle','bus'}:raise ValueError('EXPLICIT_NON_CAR_ROUTE_REVIEW_REQUIRED')
    validate_url(evidence_url)
    job=db.rows('SELECT * FROM jobs WHERE id=?',(job_id,))[0]
    mandatory=('destination','outbound','return','shift_compatible','origin_access','valid_until','shift_start','shift_end','days','schedule')
    if not all(details.get(k) for k in mandatory):raise ValueError('EXACT_SHIFT_AND_ROUND_TRIP_EVIDENCE_REQUIRED')
    profile=load_profile();payload={**details,'job_content_hash':job['content_hash'],'method':'USER_VERIFIED_EXACT_SHIFT'}
    check={'origin':profile['origin_neighborhood'],'mode':mode,'viability':'VERIFICADA','transfers':transfers,'evidence_url':evidence_url,'details':payload}
    if not valid_commute(check,profile):raise ValueError('ROUTE_NOT_COMPATIBLE_WITH_PROFILE')
    return db.execute('INSERT INTO commute_checks(job_id,origin,mode,transfers,viability,evidence_url,checked_at,details) VALUES(?,?,?,?,?,?,?,?)',
                      (job_id,check['origin'],mode,transfers,'VERIFICADA',evidence_url,now(),json.dumps(payload)))


def forget_professional_data(db,confirmed=False):
    if not confirmed:raise ValueError('EXPLICIT_ERASURE_CONFIRMATION_REQUIRED')
    folder=private_folder(db)
    rows=db.rows('SELECT * FROM candidate_documents')
    paths={Path(r['encrypted_path']).resolve() for r in rows}
    paths.update(Path(r['encrypted_path']).resolve() for r in db.rows('SELECT encrypted_path FROM application_receipt_evidence'))
    paths.update(Path(r['encrypted_path']).resolve() for r in db.rows('SELECT encrypted_path FROM manual_application_handoffs'))
    paths.update(Path(r['encrypted_path']).resolve() for r in db.rows('SELECT encrypted_path FROM manual_application_evidence'))
    if any(not p.is_relative_to(folder) for p in paths):raise ValueError('DOCUMENT_PATH_OUTSIDE_VAULT')
    tombstone=protect(json.dumps({'value':'ERASED','origin':'ERASED'}).encode())
    with db.transaction():
        pause(db,'PROFESSIONAL_DATA_ERASED',revoke=True)
        # Close any live browser memory too; commands contain no professional data.
        from .human_sessions import request_command
        for session in db.rows("SELECT id FROM autoapply_interventions WHERE worker_pid IS NOT NULL"):
            request_command(db,session['id'],'CLOSE')
        db.execute('UPDATE candidate_facts SET encrypted_value=?,revoked_at=?',(tombstone,now()))
        db.execute('UPDATE candidate_documents SET revoked_at=?',(now(),))
        event(db,'PROFESSIONAL_DATA_ERASED',{'documents':len(rows)})
    # Each resolved file was checked above; no recursive removal and no external paths.
    for path in paths:
        if path.exists():path.unlink()
    return {'documents_erased':len(paths),'previous_backups_changed':False,'minimal_audit_retained':True}
