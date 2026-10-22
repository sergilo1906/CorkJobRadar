"""Documented Lever receipt verification, bound to dispatch. HTTP 200 alone proves nothing."""
import json
import hashlib
import re
from urllib.parse import urlsplit,urlunsplit,parse_qs
from ..config import now,digest
from .vault import private_folder,protect
from .policy import event,require_live


def safe_endpoint(url):
    try:
        parsed=urlsplit(url)
        if parsed.scheme!='https' or parsed.hostname not in {'api.lever.co','api.eu.lever.co'} or parsed.port not in {None,443} or parsed.username or parsed.password or parsed.fragment:return None
        if set(parse_qs(parsed.query))-{'key'}:return None
        if not re.fullmatch(r'/v0/postings/[A-Za-z0-9_-]+/[a-fA-F0-9-]{36}',parsed.path):return None
        return urlunsplit(('https',parsed.hostname,parsed.path,'',''))
    except ValueError:return None


def lever_receipt(status,body,request_url,response_url,expected_posting,send_started=False):
    """Pure parser; not evidence of a real send by itself. No lookup or resubmission."""
    request_url=safe_endpoint(request_url);response_url=safe_endpoint(response_url)
    if not send_started or status!=200 or not request_url or request_url!=response_url:return None
    parsed=urlsplit(request_url)
    match=re.fullmatch(r'/v0/postings/[A-Za-z0-9_-]+/([a-fA-F0-9-]{36})',parsed.path)
    if not match or match[1]!=expected_posting:return None
    try:data=json.loads(body) if isinstance(body,(bytes,str)) else body
    except (ValueError,UnicodeDecodeError):return None
    if not isinstance(data,dict) or data.get('ok') is not True:return None
    reference=data.get('applicationId')
    if not isinstance(reference,str) or not re.fullmatch(r'[A-Za-z0-9-]{5,120}',reference):return None
    return {'platform':'lever','reference':reference,'posting_id':expected_posting,'request_url':request_url,'evidence_hash':digest(data)}


def retain_receipt_evidence(db,attempt_id,status,body,request_url,response_url,expected_posting):
    request_url=safe_endpoint(request_url);response_url=safe_endpoint(response_url)
    if not request_url or not response_url:raise ValueError('UNSAFE_RECEIPT_ENDPOINT')
    rows=db.rows('''SELECT a.*,p.environment,p.job_id FROM application_attempts a
                   JOIN application_plans p ON p.id=a.plan_id WHERE a.id=?''',(attempt_id,))
    if not rows:raise ValueError('ATTEMPT_NOT_FOUND')
    attempt=rows[0]
    if attempt['environment']=='LIVE':
        require_live(db)
        from .platforms import platform_for
        platform=platform_for(attempt['target_url'])
        if platform['id']!='lever' or not platform.get('live_supported') or not platform.get('automation_permitted'):raise PermissionError('VERIFIED_LEVER_TRANSPORT_REQUIRED')
        target=urlsplit(attempt['target_url'])
        if not re.fullmatch(r'/[A-Za-z0-9_-]+/'+re.escape(expected_posting)+r'(?:/apply)?/?',target.path):raise PermissionError('RECEIPT_POSTING_MISMATCH')
        if attempt['state'] not in {'ENVIANDO','ENVIO_INCIERTO','ENVIADA_CONFIRMADA'}:raise PermissionError('RECEIPT_WITHOUT_SENDING_STATE')
    # Dispatch evidence must be written by a future authorized transport, not by UI imports.
    dispatch=db.rows("SELECT details FROM application_events WHERE attempt_id=? AND kind='TRANSPORT_DISPATCHED' ORDER BY id DESC LIMIT 1",(attempt_id,))
    proof=json.loads(dispatch[0]['details']) if dispatch else {}
    if proof.get('request_url')!=request_url or proof.get('posting_id')!=expected_posting or proof.get('method')!='POST':
        raise PermissionError('CORRELATED_DISPATCH_EVIDENCE_REQUIRED')
    receipt=lever_receipt(status,body,request_url,response_url,expected_posting,True)
    payload={'http_status':status,'request_url':request_url,'response_url':response_url,'body':body.decode('utf-8',errors='replace') if isinstance(body,bytes) else body,
             'receipt':receipt,'environment':attempt['environment']}
    content=json.dumps(payload,ensure_ascii=False).encode('utf-8');sha=hashlib.sha256(content).hexdigest()
    path=private_folder(db)/(sha+'.receipt.dpapi')
    if not path.exists():path.write_bytes(protect(content))
    label=('VERIFIED_REAL_RECEIPT' if attempt['environment']=='LIVE' else 'SIMULATION_RECEIPT') if receipt else 'UNCONFIRMED_RESPONSE'
    with db.transaction():
        db.execute('''INSERT OR IGNORE INTO application_receipt_evidence(attempt_id,received_at,environment,platform,evidence_hash,encrypted_path,status)
                      VALUES(?,?,?,?,?,?,?)''',(attempt_id,now(),attempt['environment'],'lever',sha,str(path),label))
        verified_live=label=='VERIFIED_REAL_RECEIPT'
        event(db,'RECEIPT_EVIDENCE_RETAINED',{'evidence_hash':sha,'status':label,'confirms_live_application':verified_live},attempt['plan_id'],attempt_id)
        if verified_live:
            evidence_id=db.rows('SELECT id FROM application_receipt_evidence WHERE attempt_id=? AND evidence_hash=?',(attempt_id,sha))[0]['id']
            from .store import transition
            if attempt['state']!='ENVIADA_CONFIRMADA':transition(db,attempt_id,'ENVIADA_CONFIRMADA',confirmation={**receipt,'receipt_id':evidence_id})
            if not db.rows("SELECT id FROM user_actions WHERE job_id=? AND action='solicitada'",(attempt['job_id'],)):
                db.execute("INSERT INTO user_actions(job_id,action,notes,application_date,created_at) VALUES(?,'solicitada',?,?,?)",
                           (attempt['job_id'],'AutoApply verified Lever receipt '+receipt['reference'],now()[:10],now()))
        elif attempt['environment']=='LIVE' and attempt['state']=='ENVIANDO':
            from .store import transition
            transition(db,attempt_id,'ENVIO_INCIERTO','NO_VERIFIABLE_CORRELATED_RECEIPT')
    # A simulation receipt never confirms a real application or writes user_actions.
    return {'status':label,'evidence_hash':sha,'confirms_live_application':label=='VERIFIED_REAL_RECEIPT','automatic_retry_allowed':False}
