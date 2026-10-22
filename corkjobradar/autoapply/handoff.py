"""Encrypted manual handoff, never a remote filler or evidence of receipt."""
import base64
import hashlib
import io
import json
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
from ..config import now, digest
from ..http import validate_url
from .documents import document_bytes
from .forms import load_inspection, answer_plan
from .it_scope import require_it_job
from .policy import event
from .store import already_applied
from .vault import candidate_snapshot, private_folder, protect
from .interaction_modes import manual_target_url,interaction_route


def _job(db, job_id):
    rows=db.rows('SELECT * FROM jobs WHERE id=?',(job_id,))
    if not rows:raise ValueError('JOB_NOT_FOUND')
    require_it_job(rows[0])
    return rows[0]


def prepare_handoff(db, job_id, inspection_id=None):
    """Explicit local preparation only. Unknown fields remain visibly unanswered.

    No policy authorization is needed to prepare a manual package. This does not
    override transport/requirements/policy holds and cannot create a live attempt.
    """
    from .trials import trial_readiness
    with db.transaction() as con:
        if not con.in_transaction:con.execute('BEGIN IMMEDIATE')
        job=_job(db,job_id)
        if already_applied(db,job,'LIVE'):raise PermissionError('ALREADY_APPLIED_OR_RESERVED')
        candidate=candidate_snapshot(db)
        if not candidate.get('cv_document_id'):raise PermissionError('APPROVED_CV_REQUIRED')
        from .broad_selection import assess_selection
        selection=assess_selection(db,job,candidate)
        if selection['exclusions']:raise PermissionError('EXCLUDED_BY_IT_50KM_MAX3_SELECTION')
        content,ext,sha=document_bytes(db,candidate['cv_document_id'])
        target=job.get('apply_url') or job['url'];validate_url(target)
        # Never export URL credentials, fragments or query parameters as a shortcut.
        target=manual_target_url(target)
        inspection=load_inspection(db,inspection_id) if inspection_id else None
        if inspection and inspection['job_id']!=job_id:raise ValueError('INSPECTION_JOB_MISMATCH')
        plan=answer_plan(inspection,candidate) if inspection else {'mapping':{},'unresolved':[]}
        answers=[]
        for field in inspection['fields'] if inspection else []:
            answer=plan['mapping'].get(field['id'])
            if answer and 'value' in answer:
                answers.append({'question':field['label'],'answer':answer['value'],'fact_id':answer['fact_id']})
        blockers=trial_readiness(db,job_id,inspection_id)['blockers']
        checklist=[]
        for field in inspection['fields'] if inspection else []:
            answer=plan['mapping'].get(field['id'])
            checklist.append({'field':field['id'],'label':field['label'],'type':field['type'],'required':field['required'],
                              'status':'APPROVED_CV' if answer and 'document' in answer else 'VERIFIED_ANSWER' if answer else 'PENDING_REVIEW_OR_LEAVE_OPTIONAL_BLANK'})
        pending=list(plan['unresolved'])
        for item in checklist:
            if item['status']=='PENDING_REVIEW_OR_LEAVE_OPTIONAL_BLANK' and not any(q['field']==item['field'] for q in pending):
                pending.append({'field':item['field'],'label':item['label'],'required':item['required'],'code':'OPTIONAL_ANSWER_NOT_APPROVED'})
        payload={'version':2,'job_id':job_id,'job_content_hash':job['content_hash'],
                 'title':job['title'],'company':job['company'],'target_url':target,
                 'facts_hash':candidate['_facts_hash'],'document_id':candidate['cv_document_id'],
                 'document_hash':sha,'document_extension':ext,
                 'cv_base64':base64.b64encode(content).decode('ascii'),
                 'contacts':{k:candidate[k] for k in ('full_name','first_name','last_name','email','phone','location','linkedin_url') if candidate.get(k)},
                 'verified_answers':answers,'unresolved_questions':pending,'question_checklist':checklist,
                 'blockers':blockers,'inspection_id':inspection_id,'selection_review':selection,
                 'form_hash':inspection['form_hash'] if inspection else None,
                 'prepared_at':now(),'expires_at':(datetime.now(ZoneInfo('Europe/Dublin'))+timedelta(hours=24)).isoformat(timespec='seconds'),
                 'state':'MANUAL_REVIEW_REQUIRED','interaction_mode':interaction_route(target)['mode'],
                 'submitted':False,'external_receipt_verified':False}
        raw=json.dumps(payload,ensure_ascii=False,sort_keys=True).encode('utf-8');fingerprint=hashlib.sha256(raw).hexdigest()
        path=private_folder(db)/(fingerprint+'.manual-handoff.dpapi')
        path.write_bytes(protect(raw))
        hid=db.execute('''INSERT INTO manual_application_handoffs(job_id,created_at,expires_at,package_hash,encrypted_path)
                          VALUES(?,?,?,?,?)''',(job_id,now(),payload['expires_at'],fingerprint,str(path)))
        event(db,'MANUAL_HANDOFF_PREPARED',{'handoff_id':hid,'package_hash':fingerprint,'submitted':False})
        return {'handoff_id':hid,'package_hash':fingerprint,'blockers':blockers,'state':payload['state'],'submitted':False}


def _read_package(db,handoff_id):
    rows=db.rows('SELECT * FROM manual_application_handoffs WHERE id=?',(handoff_id,))
    if not rows:raise ValueError('HANDOFF_NOT_FOUND')
    row=rows[0];path=Path(row['encrypted_path']).resolve()
    if not path.is_relative_to(private_folder(db)):raise ValueError('HANDOFF_OUTSIDE_VAULT')
    raw=protect(path.read_bytes(),True)
    if hashlib.sha256(raw).hexdigest()!=row['package_hash']:raise ValueError('HANDOFF_HASH_MISMATCH')
    payload=json.loads(raw)
    if payload['job_id']!=row['job_id']:raise ValueError('HANDOFF_JOB_MISMATCH')
    return payload


def load_handoff(db, handoff_id):
    payload=_read_package(db,handoff_id);job=_job(db,payload['job_id']);candidate=candidate_snapshot(db)
    if datetime.fromisoformat(payload['expires_at'])<=datetime.now(ZoneInfo('Europe/Dublin')):raise ValueError('HANDOFF_EXPIRED')
    if payload['job_id']!=job['id'] or payload['job_content_hash']!=job['content_hash'] or payload['target_url']!=manual_target_url(job.get('apply_url') or job['url']):raise ValueError('HANDOFF_JOB_CHANGED')
    if payload['facts_hash']!=candidate['_facts_hash'] or payload['document_id']!=candidate.get('cv_document_id'):raise ValueError('HANDOFF_PROFILE_OR_CV_CHANGED')
    _,_,sha=document_bytes(db,payload['document_id'])
    if sha!=payload['document_hash']:raise ValueError('HANDOFF_DOCUMENT_CHANGED')
    if payload['inspection_id']:
        inspection=load_inspection(db,payload['inspection_id'])
        if inspection['form_hash']!=payload['form_hash']:raise ValueError('HANDOFF_FORM_CHANGED')
    if already_applied(db,job,'LIVE'):raise PermissionError('ALREADY_APPLIED_OR_RESERVED')
    # Holds are recalculated rather than trusting a previously displayed checklist.
    from .trials import trial_readiness
    payload['blockers']=trial_readiness(db,job['id'],payload['inspection_id'])['blockers']
    if 'selection_review' in payload:
        from .broad_selection import assess_selection
        payload['selection_review']=assess_selection(db,job,candidate_snapshot(db))
        if payload['selection_review']['exclusions']:raise PermissionError('EXCLUDED_BY_IT_50KM_MAX3_SELECTION')
    return payload


def handoff_download(db,handoff_id):
    payload=load_handoff(db,handoff_id)
    content=base64.b64decode(payload.pop('cv_base64'),validate=True)
    if hashlib.sha256(content).hexdigest()!=payload['document_hash']:raise ValueError('HANDOFF_CV_HASH_MISMATCH')
    text=('PAQUETE PARA REVISION Y PRESENTACION MANUAL\n\n'
          'Contiene datos personales y el CV aprobado. Descarga local explicita.\n'
          'No acredita elegibilidad, envio ni recepcion. Revisa TODOS los bloqueos\n'
          'y el formulario vigente antes de utilizarlo; no inventes respuestas.\n'
          'Abre el enlace oficial en tu propio navegador. No se automatiza ese sitio.\n'
          'Un clic o una declaracion manual no equivalen a confirmacion externa.\n\n'
          'Destino: '+payload['target_url']+'\nBloqueos: '+', '.join(payload['blockers'])+'\n')
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('CV.'+payload['document_extension'],content)
        archive.writestr('datos-y-respuestas.json',json.dumps(payload,ensure_ascii=False,indent=2))
        archive.writestr('LEEME.txt',text)
        archive.writestr('CANDIDATURA.txt',manual_application_text(payload).encode('utf-8'))
    return buffer.getvalue()


def manual_application_text(payload):
    """Human-readable material, exported only by the explicit download action."""
    lines=['CANDIDATURA PARA COMPLETAR MANUALMENTE - NO ENVIADA',
           payload['company']+' - '+payload['title'],'Enlace oficial: '+payload['target_url'],
           'Modo: '+payload.get('interaction_mode','MANUAL_REVIEW_REQUIRED'),
           'CV aprobado: '+str(payload['document_id'])+'; SHA-256 '+payload['document_hash'],
           'Preparado: '+payload['prepared_at'],'Caduca: '+payload['expires_at'],'','CONTACTOS APROBADOS']
    labels={'full_name':'Nombre','first_name':'Nombre de pila','last_name':'Apellidos','email':'Correo','phone':'Telefono','location':'Ubicacion','linkedin_url':'LinkedIn'}
    lines.extend(labels.get(key,key)+': '+str(value) for key,value in payload['contacts'].items())
    lines+=['','RESPUESTAS VERIFICADAS (copiar solo en la misma pregunta)']
    lines.extend(item['question']+'\n'+str(item['answer'])+'\n' for item in payload['verified_answers'])
    lines+=['','PREGUNTAS PENDIENTES (sin respuestas inventadas)']
    lines.extend(item['label']+' ['+item['code']+']' for item in payload['unresolved_questions'])
    if not payload['inspection_id']:lines.append('No hay esquema inspeccionado: revisar todas las preguntas en el sitio oficial.')
    lines+=['','COMPROBACIONES Y PROCEDIMIENTO',
            '1. Comprobar puesto abierto, funciones IT, centro dentro de 50 km y minimo obligatorio solicitado de hasta 3 anos. La experiencia real permanece sin redondear.',
            '2. Origen Ballinlough sin coche propio: transporte pendiente y dudas tecnicas/academicas menores son advertencias. Coche propio obligatorio, habilitacion/legalidad y otras incompatibilidades acreditadas bloquean.',
            '3. Abrir el enlace oficial en tu navegador y revisar las condiciones y avisos del destino.',
            '4. Adjuntar el CV indicado, copiar contactos/LinkedIn y usar solo respuestas verificadas para preguntas exactas.',
            '5. Revisar manualmente preguntas nuevas y consentimientos; no redondear experiencia, inferir titulos o inventar respuestas.',
            '6. La politica de AutoApply no es necesaria para una presentacion completamente manual. Sus bloqueos tecnicos no sustituyen los requisitos del puesto.',
            '7. Antes de presentar, revisar todos los campos y archivos; un clic no acredita recepcion.',
            '8. Si presentas la candidatura, registrar tu declaracion en Cork Job Radar para impedir duplicados.',
            '9. Guardar el correo original EML o justificante PDF y adjuntarlo a esa declaracion; aportarlo no autentica la recepcion externa.',
            '','BLOQUEOS OBSERVADOS DE AUTOAPPLY (incluyen permisos/politica/adaptador; no todos impiden el uso manual):',
            *payload['blockers']]
    if payload.get('selection_review'):
        r=payload['selection_review']
        lines+=['','SELECCION PROFESIONAL IT 50 KM / MINIMO SOLICITADO HASTA 3 ANOS:',r['professional_state'],
                'Exclusiones: '+', '.join(r['exclusions']),
                'Datos esenciales pendientes: '+', '.join(r['essential_pending']),
                'Advertencias (no equivalen a rechazo): '+', '.join(r['warnings']),
                'Los permisos/API/politica de AutoApply son independientes de la preparacion manual.',
                'CV: reutilizada la version aprobada sin modificar bytes ni atribuir nuevas competencias.']
    return '\n'.join(lines)+'\n'


def declare_manual_submission(db,handoff_id,confirmed=False):
    """User declaration prevents reapplication, but never asserts external receipt."""
    if not confirmed:raise ValueError('EXPLICIT_MANUAL_SUBMISSION_DECLARATION_REQUIRED')
    with db.transaction() as con:
        if not con.in_transaction:con.execute('BEGIN IMMEDIATE')
        prior=db.rows('SELECT user_action_id FROM manual_application_declarations WHERE handoff_id=?',(handoff_id,))
        if prior:return prior[0]['user_action_id']
        # Record a past manual submission even after a package expires or facts
        # change. This blocks reapplication; it grants no new sending permission.
        payload=_read_package(db,handoff_id)
        job=db.rows('SELECT * FROM jobs WHERE id=?',(payload['job_id'],))[0]
        if already_applied(db,job,'LIVE'):raise PermissionError('ALREADY_APPLIED_OR_RESERVED')
        aid=db.execute("INSERT INTO user_actions(job_id,action,notes,application_date,created_at) VALUES(?,'solicitada',?,?,?)",
                       (payload['job_id'],'USER_DECLARED_MANUAL_SUBMISSION; EXTERNAL_RECEIPT_UNVERIFIED',now()[:10],now()))
        db.execute('INSERT INTO manual_application_declarations(handoff_id,user_action_id,declared_at,status) VALUES(?,?,?,?)',
                   (handoff_id,aid,now(),'DECLARED_NO_EXTERNAL_RECEIPT'))
        event(db,'MANUAL_SUBMISSION_DECLARED',{'handoff_id':handoff_id,'user_action_id':aid,'external_receipt_verified':False})
        return aid
