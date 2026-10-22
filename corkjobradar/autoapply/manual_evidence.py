"""User-provided manual receipts, encrypted. Never a verified ATS receipt.

Parsing an EML/PDF or a user reviewing it is not independent authentication of
the sender or delivery. Neither operation releases LIVE or marks ENVIADA.
"""
import base64
from datetime import datetime
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses,parsedate_to_datetime
import hashlib
import json
from pathlib import Path
import re
from ..config import now
from ..normalization import clean_html,normalized
from .documents import validate_document
from .handoff import _read_package
from .policy import event
from .vault import private_folder,protect

MAX_BYTES=5_000_000


def _declaration(db,declaration_id):
    rows=db.rows('SELECT * FROM manual_application_declarations WHERE id=?',(declaration_id,))
    if not rows:raise ValueError('DECLARED_MANUAL_APPLICATION_REQUIRED')
    return rows[0]


def _extract(content,extension):
    if not isinstance(content,bytes) or not 0<len(content)<=MAX_BYTES:raise ValueError('EVIDENCE_SIZE_INVALID')
    if extension=='pdf':
        return {'format':'pdf','text':validate_document(content,'pdf'),'sender':None,'subject':None,
                'date':None,'recipients':[],'message_id':None,'attachments_ignored':0}
    if extension!='eml':raise ValueError('EML_OR_PASSIVE_PDF_REQUIRED')
    message=BytesParser(policy=policy.default).parsebytes(content)
    parts=list(message.walk())
    if len(parts)>50 or message.defects or any(p.defects for p in parts):raise ValueError('UNSUPPORTED_OR_MALFORMED_EMAIL')
    for header in ('From','To','Date','Subject','Message-ID'):
        if len(message.get_all(header,[]))>1:raise ValueError('AMBIGUOUS_EMAIL_HEADERS')
    if any(p.get_content_type()=='message/rfc822' for p in parts):raise ValueError('FORWARDED_EMAIL_REQUIRES_ORIGINAL')
    body=message.get_body(preferencelist=('plain','html'))
    if body is None:raise ValueError('EMAIL_BODY_REQUIRED')
    text=body.get_content()
    if not isinstance(text,str) or not text.strip():raise ValueError('EMAIL_TEXT_REQUIRED')
    if body.get_content_type()=='text/html':text=clean_html(text)
    senders=getaddresses(message.get_all('From',[]))
    sender=senders[0][1] if len(senders)==1 else None
    recipients=[address.casefold() for _,address in getaddresses(message.get_all('To',[]))]
    try:
        stamp=parsedate_to_datetime(str(message.get('Date','')))
        stamp=stamp.isoformat() if stamp.tzinfo else None
    except (TypeError,ValueError,OverflowError):stamp=None
    return {'format':'eml','text':text[:250_000],'sender':sender,'subject':str(message.get('Subject',''))[:2000],
            'date':stamp,'recipients':recipients,'message_id':str(message.get('Message-ID',''))[:2000],
            'attachments_ignored':sum(p.get_content_disposition()=='attachment' for p in parts)}


def _signals(extracted,package):
    text=normalized((extracted['subject'] or '')+' '+extracted['text'])
    sender=extracted['sender'] or ''
    domain=sender.rsplit('@',1)[1].lower() if re.fullmatch(r'[^\s@<>]+@(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}',sender) else None
    return {'title_mentioned':normalized(package['title']) in text,
            'company_mentioned':normalized(package['company']) in text,
            'recipient_matches_application':str(package['contacts'].get('email','')).casefold() in extracted['recipients'] if extracted['recipients'] else False,
            'receipt_phrase_present':bool(re.search(r'application (?:was |has been )?received|successfully submitted|thank you for applying',text)),
            'dated_message':bool(extracted['date']),'message_id_present':bool(extracted['message_id']),
            'sender_domain_available':bool(domain),'sender_authenticated':False,
            'external_receipt_verified':False}


def retain_manual_evidence(db,declaration_id,content,extension,*,consent=False):
    if not consent:raise PermissionError('EXPLICIT_EVIDENCE_STORAGE_CONSENT_REQUIRED')
    declaration=_declaration(db,declaration_id)
    # Historical evidence can be attached after the prepared package expires;
    # it does not authorize reusing the old CV or submitting anything again.
    package=_read_package(db,declaration['handoff_id'])
    try:extracted=_extract(content,extension)
    except Exception:raise ValueError('EVIDENCE_VALIDATION_FAILED') from None
    sha=hashlib.sha256(content).hexdigest();signals=_signals(extracted,package)
    with db.transaction() as con:
        if not con.in_transaction:con.execute('BEGIN IMMEDIATE')
        prior=db.rows('SELECT id FROM manual_application_evidence WHERE declaration_id=? AND content_hash=?',(declaration_id,sha))
        if prior:return {'evidence_id':prior[0]['id'],'content_hash':sha,'duplicate_upload':True,'external_receipt_verified':False}
        payload={'version':1,'declaration_id':declaration_id,'handoff_id':declaration['handoff_id'],
                 'job_id':package['job_id'],'job_content_hash':package['job_content_hash'],'document_hash':package['document_hash'],
                 'raw_base64':base64.b64encode(content).decode('ascii'),'content_hash':sha,'extension':extension,
                 'extracted':extracted,'signals':signals,'stored_at':now()}
        raw=json.dumps(payload,ensure_ascii=False,sort_keys=True).encode('utf-8');payload_hash=hashlib.sha256(raw).hexdigest()
        path=private_folder(db)/(payload_hash+'.manual-evidence.dpapi')
        if not path.exists():path.write_bytes(protect(raw))
        eid=db.execute('''INSERT INTO manual_application_evidence(declaration_id,uploaded_at,extension,content_hash,payload_hash,encrypted_path,status)
                          VALUES(?,?,?,?,?,?,?)''',(declaration_id,now(),extension,sha,payload_hash,str(path),'USER_SUPPLIED_NOT_AUTHENTICATED'))
        event(db,'MANUAL_EVIDENCE_STORED',{'evidence_id':eid,'declaration_id':declaration_id,'content_hash':sha,'external_receipt_verified':False})
    return {'evidence_id':eid,'content_hash':sha,'signals':signals,'duplicate_upload':False,'external_receipt_verified':False}


def read_manual_evidence(db,evidence_id):
    rows=db.rows('SELECT * FROM manual_application_evidence WHERE id=?',(evidence_id,))
    if not rows:raise ValueError('MANUAL_EVIDENCE_NOT_FOUND')
    row=rows[0];path=Path(row['encrypted_path']).resolve()
    if not path.is_relative_to(private_folder(db)) or not path.name.endswith('.manual-evidence.dpapi'):raise ValueError('EVIDENCE_OUTSIDE_VAULT')
    raw=protect(path.read_bytes(),True)
    if hashlib.sha256(raw).hexdigest()!=row['payload_hash']:raise ValueError('EVIDENCE_PAYLOAD_CHANGED')
    data=json.loads(raw);content=base64.b64decode(data['raw_base64'],validate=True)
    if data['declaration_id']!=row['declaration_id'] or data['extension']!=row['extension'] or hashlib.sha256(content).hexdigest()!=row['content_hash'] or data['content_hash']!=row['content_hash']:
        raise ValueError('EVIDENCE_BINDING_CHANGED')
    data['external_receipt_verified']=False
    return data


def evidence_download(db,evidence_id):
    data=read_manual_evidence(db,evidence_id)
    return base64.b64decode(data['raw_base64'],validate=True),data['extension']


def review_manual_evidence(db,evidence_id,content_hash,*,acknowledged=False):
    if not acknowledged:raise PermissionError('EXPLICIT_MANUAL_EVIDENCE_REVIEW_REQUIRED')
    data=read_manual_evidence(db,evidence_id)
    if data['content_hash']!=content_hash:raise ValueError('EVIDENCE_REVIEW_VERSION_CHANGED')
    with db.transaction() as con:
        if not con.in_transaction:con.execute('BEGIN IMMEDIATE')
        old=db.rows('SELECT id FROM manual_application_evidence_reviews WHERE evidence_id=?',(evidence_id,))
        if old:return old[0]['id']
        rid=db.execute('INSERT INTO manual_application_evidence_reviews(evidence_id,content_hash,reviewed_at,status) VALUES(?,?,?,?)',
                       (evidence_id,content_hash,now(),'USER_REVIEWED_NOT_EXTERNALLY_AUTHENTICATED'))
        event(db,'MANUAL_EVIDENCE_REVIEWED',{'evidence_id':evidence_id,'external_receipt_verified':False})
        return rid
