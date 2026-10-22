import json
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from uuid import uuid4
import streamlit as st
import yaml
from ..config import ROOT,now
from .policy import current_policy,save_policy,pause,resume,Policy
from .vault import approve_fact,candidate_snapshot,save_clearance,approve_route,forget_professional_data
from .documents import render_cv,render_letter,store_document,document_bytes,create_cv_review,cv_review_bytes,approve_cv_review
from .engine import preview,report


def launch_simulation():
    import subprocess,sys,os
    folder=ROOT/'logs';folder.mkdir(exist_ok=True)
    log=(folder/('autoapply-worker-'+uuid4().hex[:12]+'.log')).open('w',encoding='utf-8')
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    try:
        child=subprocess.Popen([sys.executable,'-m','corkjobradar','autoapply','run','--dry-run'],cwd=ROOT,
                               stdout=log,stderr=log,creationflags=flags)
    finally:log.close()
    return child.pid


def render(db):
    from .manual_workspace_ui import render_manual_workspace
    from .assisted_ui import render_manual_evidence
    with st.container(key='aa_manual_workspace_container'):render_manual_workspace(db)
    with st.container(key='aa_manual_evidence_container'):render_manual_evidence(db)
    with st.expander('Vía B · AutoApply y herramientas avanzadas · LIVE OFF'):
        render_autoapply_controls(db)


def render_autoapply_controls(db):
    st.subheader('Candidaturas automáticas — modo A')
    state=report(db)
    st.write('Estado actual: '+state['mode'])
    st.info('Simulación únicamente. El modo real futuro enviará sin aprobación individual dentro de tu política. Falta un ensayo real específico autorizado; el envío real está bloqueado.')
    from .it_scope import classify_it_functions
    st.warning('AutoApply exclusivamente IT: las funciones informáticas deben estar confirmadas. Empleos generales excluidos; casos ambiguos retenidos. La búsqueda general conserva todas las ofertas.')
    st.write('Clasificación por funciones reales:',state['it_classification_counts'])
    include_other=st.checkbox('Consultar también candidaturas ambiguas y ofertas generales excluidas',value=False)
    buttons=st.columns(3)
    if buttons[0].button('PAUSAR TODO AUTOAPPLY',type='primary'):
        pause(db);st.success('Pausa guardada; se consulta de nuevo antes del paso final.')
    if buttons[1].button('Revocar permiso de envío'):
        pause(db,revoke=True);st.success('Permiso revocado. No se borró el historial.')
    deliberate=st.checkbox('Entiendo que reanudar solo continúa la simulación con mi política vigente')
    if buttons[2].button('Reanudar simulación',disabled=not deliberate):
        try:resume(db,'RESUME_SIMULATION');st.success('Simulación reanudada')
        except ValueError:st.error('Política caducada, revocada o modificada. Revisa y acepta una versión nueva.')
    control,row,policy=current_policy(db);candidate=candidate_snapshot(db)
    with st.expander('Ficha profesional y afirmaciones verificadas',expanded=False):
        st.caption('Vacío significa desconocido. No se deducen permisos, títulos ni experiencia del perfil de búsqueda.')
        st.write({k:v for k,v in candidate.items() if not k.startswith('_')})
        st.dataframe(candidate['_claims'],hide_index=True)
        with st.form('aa_fact_form',clear_on_submit=True):
            field=st.selectbox('Dato profesional',['full_name','first_name','last_name','email','phone','location','linkedin_url','work_authorization','availability'])
            value=st.text_input('Valor confirmado (permiso laboral: IRELAND_AUTHORIZED / SPONSORSHIP_REQUIRED / UNKNOWN)')
            origin=st.text_input('Origen de verificación del dato')
            confirmed=st.checkbox('Confirmo la veracidad de este dato y autorizo guardarlo localmente cifrado')
            if st.form_submit_button('Guardar dato validado'):
                try:approve_fact(db,field,value,origin,confirmed);st.success('Dato cifrado guardado. Los CV anteriores se invalidan.')
                except Exception:st.error('No se pudo guardar: comprueba formato, origen y confirmación explícita.')
        with st.form('aa_claim_form',clear_on_submit=True):
            section=st.selectbox('Sección del CV',['Profile','Skills','Experience','Projects','Education','Additional Experience','Languages','Availability'])
            text=st.text_area('Afirmación exacta en inglés para el CV')
            origin=st.text_input('Evidencia de esta afirmación')
            approved=st.checkbox('He comprobado esta afirmación; no contiene experiencia ni títulos inventados')
            if st.form_submit_button('Aprobar afirmación para el CV'):
                try:approve_fact(db,'claim:'+uuid4().hex,{'section':section,'text_en':text},origin,approved);st.success('Afirmación aprobada y versionada')
                except Exception:st.error('Falta texto, evidencia o aprobación explícita.')
        with st.form('aa_answer_form',clear_on_submit=True):
            question=st.text_input('Pregunta exacta autorizada del formulario')
            host=st.text_input('Dominio exacto para esa respuesta')
            answer=st.text_area('Respuesta veraz preaprobada')
            sensitive=st.checkbox('Autorizo expresamente esta respuesta sensible o aceptación legal exacta')
            approved=st.checkbox('He revisado pregunta, dominio y respuesta; autorizo esta plantilla')
            if st.form_submit_button('Guardar respuesta preaprobada'):
                try:approve_fact(db,'answer:'+uuid4().hex,{'question':question,'host':host,'answer':answer,'explicit_sensitive':sensitive},'USER_EXACT_ANSWER_TEMPLATE',approved);st.success('Respuesta cifrada guardada')
                except Exception:st.error('Revisa la pregunta, dominio, respuesta y autorización.')
    with st.expander('CV fundamentado en inglés: preparar, revisar y guardar'):
        st.caption('Plantilla ATS fiel a las afirmaciones aprobadas. No se inventa adaptación semántica. Los archivos guardados se cifran; las descargas explícitas son legibles.')
        extension=st.selectbox('Formato CV',['pdf','docx'])
        roles=[j for j in db.rows('SELECT id,title,company,url,apply_url,description,category,detail_complete FROM jobs ORDER BY id')
               if classify_it_functions(j).status=='CONFIRMED_IT']
        role_id=st.selectbox('Ordenar CV para una oferta (opcional)',['Sin adaptación']+[j['id'] for j in roles],
                            format_func=lambda key:key if key=='Sin adaptación' else next(j['title']+' · '+j['company'] for j in roles if j['id']==key))
        role=next((j for j in roles if j['id']==role_id),None)
        if st.button('Preparar CV inglés para revisar'):
            try:
                st.session_state['aa_review_id']=create_cv_review(db,render_cv(candidate_snapshot(db),extension,role),extension)
            except Exception:st.error('Completa nombre, contacto y al menos una afirmación aprobada; verifica las dependencias opcionales.')
        upload=st.file_uploader('CV propio para revisión local',type=['pdf','docx'],key='aa_upload')
        prepared=None
        if upload:
            prepared=None
            try:
                suffix=Path(upload.name).suffix.lower().lstrip('.')
                content=upload.getvalue()
                if suffix=='pdf':
                    from .cv_import import review_cv_pdf
                    review=review_cv_pdf(content)
                    content=review.primary.content
                    st.caption('Página 1: CV pendiente de tu revisión. La extracción no aprueba datos ni acredita títulos o experiencia. Registra solo los hechos que confirmes en la ficha profesional.')
                    st.text(review.primary.text)
                    if review.annexes:
                        st.warning(f'{len(review.annexes)} páginas adicionales separadas. No forman parte del CV ni están autorizadas para adjuntarse.')
                        for annex in review.annexes:
                            st.download_button(f'Revisar anexo independiente: página {annex.number}',annex.content,
                                               file_name=f'Anexo-pagina-{annex.number}.pdf',key=f'aa_annex_{annex.number}')
                else:
                    from .documents import validate_document
                    st.text(validate_document(content,suffix))
                prepared=(content,suffix,candidate_snapshot(db)['_facts_hash'])
            except Exception:st.error('No se pudo separar y revisar el documento. No se ha aprobado ni guardado ningún dato.')
        if prepared and st.button('Conservar importación como CV pendiente de revisión'):
            try:st.session_state['aa_review_id']=create_cv_review(db,prepared[0],prepared[1])
            except Exception:st.error('El archivo no contiene todas las afirmaciones aprobadas o no es válido. No se ha aprobado el CV.')
        reviews=db.rows("SELECT id,file_hash,approved_at,created_at FROM candidate_documents WHERE kind='CV' AND facts_hash=? AND revoked_at IS NULL ORDER BY id DESC",(candidate_snapshot(db)['_cv_facts_hash'],))
        if reviews:
            ids=[r['id'] for r in reviews]
            chosen=st.selectbox('Versión del CV para revisar',ids,index=ids.index(st.session_state['aa_review_id']) if st.session_state.get('aa_review_id') in ids else 0,
                                format_func=lambda key:'Versión '+str(key)+(' · aprobada' if next(r for r in reviews if r['id']==key)['approved_at'] else ' · pendiente'))
            try:
                content,ext,sha,text=cv_review_bytes(db,chosen)
                st.caption('Revisión íntegra del documento. La aprobación solo afecta a esta versión y a la ficha actual; no activa AutoApply.')
                st.text(text)
                st.download_button('Descargar CV para revisión',content,file_name='CV.'+ext)
                prepared=(content,ext,candidate_snapshot(db)['_facts_hash'])
            except Exception:
                prepared=None;st.error('No se puede abrir esta versión: cambió la ficha o falló la integridad.')
            reviewed=st.checkbox('He revisado el CV completo: todas sus afirmaciones son veraces y están respaldadas por mi ficha',key='aa_review_consent_'+str(chosen))
            if prepared and st.button('Guardar esta versión validada del CV',disabled=not reviewed):
                try:
                    did=approve_cv_review(db,chosen,sha,prepared[2],reviewed);st.success(f'CV cifrado aprobado: versión {did}')
                except Exception:st.error('CV inválido, contiene elementos activos, cambió la ficha o faltan afirmaciones respaldadas.')
        if role and st.button('Preparar carta inglesa local con mis hechos aprobados'):
            try:
                st.session_state['aa_letter']=(render_letter(candidate_snapshot(db),role,extension),extension)
                st.success('Carta preparada para revisión; no se envía ni adjunta automáticamente.')
            except Exception:st.error('Completa primero la ficha y las afirmaciones verificadas.')
        if st.session_state.get('aa_letter'):
            content,ext=st.session_state['aa_letter']
            st.download_button('Descargar carta para revisar',content,file_name='CoverLetter.'+ext)
    with st.expander('Configurar y autorizar una política de simulación'):
        from .policy_ui import render_policy_editor
        render_policy_editor(db,policy)
    from .operations_ui import render_operations
    render_operations(db,roles)
    with st.expander('Comprobación documental de requisitos y condiciones'):
        st.caption('Registra hechos contrastados, no aprobación individual de envío. Sin evidencia se conserva HOLD. Se requieren citas literales y IDs de afirmaciones aprobadas para cada comprobación.')
        jobs=roles
        if jobs:
            jid=st.selectbox('Oferta para contraste documental',[j['id'] for j in jobs],format_func=lambda k:next(j['title']+' · '+j['company'] for j in jobs if j['id']==k),key='aa_clearance_job')
            with st.form('aa_clearance_form'):
                raw=st.text_area('Hechos y evidencias de la oferta (JSON)',value='{}')
                expiry=st.text_input('Vigencia de estas evidencias (ISO con zona)',value=(datetime.now(ZoneInfo('Europe/Dublin'))+timedelta(days=7)).isoformat(timespec='seconds'))
                checked=st.checkbox('He contrastado todos estos hechos con el texto y mi ficha validada')
                if st.form_submit_button('Guardar contraste factual'):
                    try:save_clearance(db,jid,json.loads(raw),expiry,checked);st.success('Contraste guardado; la política sigue siendo quien decide elegibilidad.')
                    except Exception:st.error('Faltan citas literales, IDs de hechos aprobados, campos o caducidad válida.')
            with st.form('aa_route_form'):
                mode=st.selectbox('Medio de ruta verificada',['bicycle','bus'])
                evidence=st.text_input('URL pública de evidencia del trayecto y horario')
                route_json=st.text_area('Evidencia exacta de ida, vuelta y turno (JSON)',value='{}')
                checked=st.checkbox('He contrastado la ida y la vuelta reales para esos días y horas desde Ballinlough')
                if st.form_submit_button('Guardar ruta para AutoApply'):
                    try:approve_route(db,jid,mode,evidence,json.loads(route_json),0,checked);st.success('Ruta manual con evidencia guardada para esta versión del anuncio')
                    except Exception:st.error('Revisa evidencia, destino, turno exacto, vigencia, ida/vuelta y ausencia de transbordos.')
    if st.button('Vista previa AutoApply (25 ofertas)'):
        st.session_state['aa_preview']=preview(db,25,it_only=not include_other)
    if st.session_state.get('aa_preview'):
        st.dataframe([p for p in st.session_state['aa_preview'] if include_other or p.get('it_classification',{}).get('status')=='CONFIRMED_IT'],hide_index=True)
    if st.button('Ejecutar simulación completa sin envíos'):
        try:st.success(f'Trabajador de simulación iniciado: {launch_simulation()}')
        except Exception:st.error('No se pudo iniciar el trabajador; revisa logs del proyecto.')
    st.caption('La simulación completa conserva una decisión por oferta, sin detenerse al cubrir cupos. No escribe datos personales en webs reales.')
    st.json(report(db))
    history=db.rows('''SELECT a.id,p.job_id,j.title,j.company,p.decision,a.state,a.target_url,a.document_id,a.updated_at,a.error_code,a.confirmation_reference,
                       s.status AS intervention_state,s.form_state AS browser_form_state
                       FROM application_attempts a JOIN application_plans p ON p.id=a.plan_id JOIN jobs j ON j.id=p.job_id
                       LEFT JOIN autoapply_interventions s ON s.attempt_id=a.id ORDER BY a.id DESC''')
    classifications={j['id']:classify_it_functions(j).status for j in db.rows('SELECT id,title,description,category,detail_complete FROM jobs')}
    visible_history=[a for a in history if include_other or classifications.get(a['job_id'])=='CONFIRMED_IT']
    st.dataframe(visible_history,hide_index=True)
    if visible_history:
        with st.expander('Resolver un intento o revisar sus preguntas'):
            st.caption('Resolver manualmente no acredita confirmación externa. No repetir conserva identidad y cupos. El reintento solo vuelve a preparar documentos de simulación; nunca rellena ni envía formularios públicos.')
            chosen=st.selectbox('Intento para resolver',[a['id'] for a in visible_history],format_func=lambda key:next(str(a['id'])+' · '+a['title']+' · '+a['state'] for a in visible_history if a['id']==key))
            selected=next(a for a in visible_history if a['id']==chosen)
            st.dataframe(db.rows('SELECT question_hash,fact_id,answer_hash,created_at FROM application_answers WHERE attempt_id=?',(chosen,)),hide_index=True)
            st.dataframe(db.rows('SELECT occurred_at,kind,before_state,after_state,details FROM application_events WHERE attempt_id=? ORDER BY id',(chosen,)),hide_index=True)
            with st.form('aa_resolution'):
                action=st.selectbox('Acción manual',['NO_REPETIR','MARCAR_RESUELTA','REINTENTAR_PREPARACION_SIMULADA'])
                acknowledged=st.checkbox('He revisado el historial; esta acción no certifica un envío ni libera una candidatura incierta')
                if st.form_submit_button('Guardar resolución manual'):
                    try:
                        from .resolution import manual_resolution,retry_simulation_preparation
                        result=(retry_simulation_preparation(db,chosen,acknowledged,selected['updated_at']) if action=='REINTENTAR_PREPARACION_SIMULADA'
                                else manual_resolution(db,chosen,action,acknowledged,selected['updated_at']))
                        st.json(result)
                    except Exception:
                        st.error('Acción retenida: comprueba aceptación, estado actualizado, trabajador ocupado, evidencia previa al envío y política vigente. No se han liberado identidades ni enviado datos.')
    plans=db.rows('SELECT id,job_id,decision,state,reasons,created_at FROM application_plans ORDER BY id DESC')
    st.dataframe([p for p in plans if include_other or classifications.get(p['job_id'])=='CONFIRMED_IT'],hide_index=True)
    st.caption(f'{len(plans)} planes históricos conservados. El filtro IT solo cambia la vista; la exportación conserva todos.')
    st.download_button('Exportar auditoría AutoApply JSON',json.dumps({'status':report(db),'plans':plans,'attempts':history},ensure_ascii=False,indent=2),file_name='autoapply-audit.json',mime='application/json')
    with st.expander('Privacidad y borrado de ficha profesional'):
        st.caption('Borra el contenido de hechos y CV locales y revoca el permiso. Conserva IDs/hashes de auditoría para evitar duplicados. Las copias de seguridad anteriores no se modifican y siguen cifradas con DPAPI.')
        st.download_button('Exportar mi ficha profesional legible',json.dumps(candidate_snapshot(db),ensure_ascii=False,indent=2),file_name='candidate-private.json',mime='application/json')
        erase=st.checkbox('Confirmo el borrado del contenido de mi ficha y documentos actuales')
        if st.button('Borrar ficha y documentos cifrados',disabled=not erase):
            try:
                forget_professional_data(db,True)
                for key in ('aa_cv_preview','aa_letter'):st.session_state.pop(key,None)
                st.success('Contenido borrado y autorización revocada.')
            except Exception:st.error('No se pudo completar el borrado. No se han borrado rutas externas.')


def render_profile_editor(db):
    from .it_scope import classify_it_functions
    candidate=candidate_snapshot(db)
    roles=[j for j in db.rows('SELECT * FROM jobs') if classify_it_functions(j).status=='CONFIRMED_IT']
    st.caption('Vacío significa desconocido. No se deducen permisos, títulos ni experiencia del perfil de búsqueda.')
    st.write({k:v for k,v in candidate.items() if not k.startswith('_')})
    st.dataframe(candidate['_claims'],hide_index=True)
    with st.form('aa_fact_form',clear_on_submit=True):
        field=st.selectbox('Dato profesional',['full_name','first_name','last_name','email','phone','location','linkedin_url','work_authorization','availability'])
        value=st.text_input('Valor confirmado (permiso laboral: IRELAND_AUTHORIZED / SPONSORSHIP_REQUIRED / UNKNOWN)')
        origin=st.text_input('Origen de verificación del dato')
        confirmed=st.checkbox('Confirmo la veracidad de este dato y autorizo guardarlo localmente cifrado')
        if st.form_submit_button('Guardar dato validado'):
            try:approve_fact(db,field,value,origin,confirmed);st.success('Dato cifrado guardado. Los CV anteriores se invalidan.')
            except Exception:st.error('No se pudo guardar: comprueba formato, origen y confirmación explícita.')
    with st.form('aa_claim_form',clear_on_submit=True):
        section=st.selectbox('Sección del CV',['Profile','Skills','Experience','Projects','Education','Additional Experience','Languages','Availability'])
        text=st.text_area('Afirmación exacta en inglés para el CV')
        origin=st.text_input('Evidencia de esta afirmación')
        approved=st.checkbox('He comprobado esta afirmación; no contiene experiencia ni títulos inventados')
        if st.form_submit_button('Aprobar afirmación para el CV'):
            try:approve_fact(db,'claim:'+uuid4().hex,{'section':section,'text_en':text},origin,approved);st.success('Afirmación aprobada y versionada')
            except Exception:st.error('Falta texto, evidencia o aprobación explícita.')
    with st.form('aa_answer_form',clear_on_submit=True):
        question=st.text_input('Pregunta exacta autorizada del formulario')
        host=st.text_input('Dominio exacto para esa respuesta')
        answer=st.text_area('Respuesta veraz preaprobada')
        sensitive=st.checkbox('Autorizo expresamente esta respuesta sensible o aceptación legal exacta')
        approved=st.checkbox('He revisado pregunta, dominio y respuesta; autorizo esta plantilla')
        if st.form_submit_button('Guardar respuesta preaprobada'):
            try:approve_fact(db,'answer:'+uuid4().hex,{'question':question,'host':host,'answer':answer,'explicit_sensitive':sensitive},'USER_EXACT_ANSWER_TEMPLATE',approved);st.success('Respuesta cifrada guardada')
            except Exception:st.error('Revisa la pregunta, dominio, respuesta y autorización.')


def render_cv_editor(db):
    from .it_scope import classify_it_functions
    candidate=candidate_snapshot(db)
    roles=[j for j in db.rows('SELECT * FROM jobs') if classify_it_functions(j).status=='CONFIRMED_IT']
    st.caption('Plantilla ATS fiel a las afirmaciones aprobadas. No se inventa adaptación semántica. Los archivos guardados se cifran; las descargas explícitas son legibles.')
    extension=st.selectbox('Formato CV',['pdf','docx'])
    roles=[j for j in db.rows('SELECT id,title,company,url,apply_url,description,category,detail_complete FROM jobs ORDER BY id')
           if classify_it_functions(j).status=='CONFIRMED_IT']
    role_id=st.selectbox('Ordenar CV para una oferta (opcional)',['Sin adaptación']+[j['id'] for j in roles],
                        format_func=lambda key:key if key=='Sin adaptación' else next(j['title']+' · '+j['company'] for j in roles if j['id']==key))
    role=next((j for j in roles if j['id']==role_id),None)
    if st.button('Preparar CV inglés para revisar'):
        try:
            st.session_state['aa_review_id']=create_cv_review(db,render_cv(candidate_snapshot(db),extension,role),extension)
        except ValueError as exc:
            if str(exc)=='CV_CONTENT_EXCEEDS_ONE_PAGE_REVIEW_REQUIRED':
                st.error('El CV completo no cabe en una página legible. Revisa la extensión; no se ha recortado contenido ni aprobado el CV.')
            else:st.error('Completa nombre, contacto y afirmaciones aprobadas; revisa el contenido del CV.')
        except Exception:st.error('Completa nombre, contacto y al menos una afirmación aprobada; verifica las dependencias opcionales.')
    upload=st.file_uploader('CV propio para revisión local',type=['pdf','docx'],key='aa_upload')
    prepared=None
    if upload:
        prepared=None
        try:
            suffix=Path(upload.name).suffix.lower().lstrip('.')
            content=upload.getvalue()
            if suffix=='pdf':
                from .cv_import import review_cv_pdf
                review=review_cv_pdf(content)
                content=review.primary.content
                st.caption('Página 1: CV pendiente de tu revisión. La extracción no aprueba datos ni acredita títulos o experiencia. Registra solo los hechos que confirmes en la ficha profesional.')
                st.text(review.primary.text)
                if review.annexes:
                    st.warning(f'{len(review.annexes)} páginas adicionales separadas. No forman parte del CV ni están autorizadas para adjuntarse.')
                    for annex in review.annexes:
                        st.download_button(f'Revisar anexo independiente: página {annex.number}',annex.content,
                                           file_name=f'Anexo-pagina-{annex.number}.pdf',key=f'aa_annex_{annex.number}')
            else:
                from .documents import validate_document
                st.text(validate_document(content,suffix))
            prepared=(content,suffix,candidate_snapshot(db)['_facts_hash'])
        except Exception:st.error('No se pudo separar y revisar el documento. No se ha aprobado ni guardado ningún dato.')
    if prepared and st.button('Conservar importación como CV pendiente de revisión'):
        try:st.session_state['aa_review_id']=create_cv_review(db,prepared[0],prepared[1])
        except Exception:st.error('El archivo no contiene todas las afirmaciones aprobadas o no es válido. No se ha aprobado el CV.')
    reviews=db.rows("SELECT id,file_hash,approved_at,created_at FROM candidate_documents WHERE kind='CV' AND facts_hash=? AND revoked_at IS NULL ORDER BY id DESC",(candidate_snapshot(db)['_cv_facts_hash'],))
    if reviews:
        ids=[r['id'] for r in reviews]
        chosen=st.selectbox('Versión del CV para revisar',ids,index=ids.index(st.session_state['aa_review_id']) if st.session_state.get('aa_review_id') in ids else 0,
                            format_func=lambda key:'Versión '+str(key)+(' · aprobada' if next(r for r in reviews if r['id']==key)['approved_at'] else ' · pendiente'))
        try:
            content,ext,sha,text=cv_review_bytes(db,chosen)
            st.caption('Revisión íntegra del documento. La aprobación solo afecta a esta versión y a la ficha actual; no activa AutoApply.')
            from .cv_preview import show_pdf_preview
            show_pdf_preview(content,ext)
            st.text(text)
            st.download_button('Descargar CV para revisión',content,file_name='CV.'+ext)
            prepared=(content,ext,candidate_snapshot(db)['_facts_hash'])
        except Exception:
            prepared=None;st.error('No se puede abrir esta versión: cambió la ficha o falló la integridad.')
        reviewed=st.checkbox('He revisado el CV completo: todas sus afirmaciones son veraces y están respaldadas por mi ficha',key='aa_review_consent_'+str(chosen))
        if prepared and st.button('Guardar esta versión validada del CV',disabled=not reviewed):
            try:
                did=approve_cv_review(db,chosen,sha,prepared[2],reviewed);st.success(f'CV cifrado aprobado: versión {did}')
            except Exception:st.error('CV inválido, contiene elementos activos, cambió la ficha o faltan afirmaciones respaldadas.')
    if role and st.button('Preparar carta inglesa local con mis hechos aprobados'):
        try:
            st.session_state['aa_letter']=(render_letter(candidate_snapshot(db),role,extension),extension)
            st.success('Carta preparada para revisión; no se envía ni adjunta automáticamente.')
        except Exception:st.error('Completa primero la ficha y las afirmaciones verificadas.')
    if st.session_state.get('aa_letter'):
        content,ext=st.session_state['aa_letter']
        st.download_button('Descargar carta para revisar',content,file_name='CoverLetter.'+ext)


def render_factual_tools(db):
    from .it_scope import classify_it_functions
    candidate=candidate_snapshot(db)
    roles=[j for j in db.rows('SELECT * FROM jobs') if classify_it_functions(j).status=='CONFIRMED_IT']
    st.caption('Registra hechos contrastados, no aprobación individual de envío. Sin evidencia se conserva HOLD. Se requieren citas literales y IDs de afirmaciones aprobadas para cada comprobación.')
    jobs=roles
    if jobs:
        jid=st.selectbox('Oferta para contraste documental',[j['id'] for j in jobs],format_func=lambda k:next(j['title']+' · '+j['company'] for j in jobs if j['id']==k),key='aa_clearance_job')
        with st.form('aa_clearance_form'):
            raw=st.text_area('Hechos y evidencias de la oferta (JSON)',value='{}')
            expiry=st.text_input('Vigencia de estas evidencias (ISO con zona)',value=(datetime.now(ZoneInfo('Europe/Dublin'))+timedelta(days=7)).isoformat(timespec='seconds'))
            checked=st.checkbox('He contrastado todos estos hechos con el texto y mi ficha validada')
            if st.form_submit_button('Guardar contraste factual'):
                try:save_clearance(db,jid,json.loads(raw),expiry,checked);st.success('Contraste guardado; la política sigue siendo quien decide elegibilidad.')
                except Exception:st.error('Faltan citas literales, IDs de hechos aprobados, campos o caducidad válida.')
        with st.form('aa_route_form'):
            mode=st.selectbox('Medio de ruta verificada',['bicycle','bus'])
            evidence=st.text_input('URL pública de evidencia del trayecto y horario')
            route_json=st.text_area('Evidencia exacta de ida, vuelta y turno (JSON)',value='{}')
            checked=st.checkbox('He contrastado la ida y la vuelta reales para esos días y horas desde Ballinlough')
            if st.form_submit_button('Guardar ruta para AutoApply'):
                try:approve_route(db,jid,mode,evidence,json.loads(route_json),0,checked);st.success('Ruta manual con evidencia guardada para esta versión del anuncio')
                except Exception:st.error('Revisa evidencia, destino, turno exacto, vigencia, ida/vuelta y ausencia de transbordos.')


def render_privacy(db):
    from .it_scope import classify_it_functions
    candidate=candidate_snapshot(db)
    roles=[j for j in db.rows('SELECT * FROM jobs') if classify_it_functions(j).status=='CONFIRMED_IT']
    st.caption('Borra el contenido de hechos y CV locales y revoca el permiso. Conserva IDs/hashes de auditoría para evitar duplicados. Las copias de seguridad anteriores no se modifican y siguen cifradas con DPAPI.')
    st.download_button('Exportar mi ficha profesional legible',json.dumps(candidate_snapshot(db),ensure_ascii=False,indent=2),file_name='candidate-private.json',mime='application/json')
    erase=st.checkbox('Confirmo el borrado del contenido de mi ficha y documentos actuales')
    if st.button('Borrar ficha y documentos cifrados',disabled=not erase):
        try:
            forget_professional_data(db,True)
            for key in ('aa_cv_preview','aa_letter'):st.session_state.pop(key,None)
            st.success('Contenido borrado y autorización revocada.')
        except Exception:st.error('No se pudo completar el borrado. No se han borrado rutas externas.')


def render_simulation_tools(db):
    st.subheader('Candidaturas automáticas — modo A')
    state=report(db)
    st.write('Estado actual: '+state['mode'])
    st.info('Simulación únicamente. El modo real futuro enviará sin aprobación individual dentro de tu política. Falta un ensayo real específico autorizado; el envío real está bloqueado.')
    from .it_scope import classify_it_functions
    st.warning('AutoApply exclusivamente IT: las funciones informáticas deben estar confirmadas. Empleos generales excluidos; casos ambiguos retenidos. La búsqueda general conserva todas las ofertas.')
    st.write('Clasificación por funciones reales:',state['it_classification_counts'])
    include_other=st.checkbox('Consultar también candidaturas ambiguas y ofertas generales excluidas',value=False)
    buttons=st.columns(3)
    if buttons[0].button('PAUSAR TODO AUTOAPPLY',type='primary'):
        pause(db);st.success('Pausa guardada; se consulta de nuevo antes del paso final.')
    if buttons[1].button('Revocar permiso de envío'):
        pause(db,revoke=True);st.success('Permiso revocado. No se borró el historial.')
    deliberate=st.checkbox('Entiendo que reanudar solo continúa la simulación con mi política vigente')
    if buttons[2].button('Reanudar simulación',disabled=not deliberate):
        try:resume(db,'RESUME_SIMULATION');st.success('Simulación reanudada')
        except ValueError:st.error('Política caducada, revocada o modificada. Revisa y acepta una versión nueva.')
    control,row,policy=current_policy(db);candidate=candidate_snapshot(db)
    control,row,policy=current_policy(db);candidate=candidate_snapshot(db)
    from .operations_ui import render_operations
    if st.button('Vista previa AutoApply (25 ofertas)'):
        st.session_state['aa_preview']=preview(db,25,it_only=not include_other)
    if st.session_state.get('aa_preview'):
        st.dataframe([p for p in st.session_state['aa_preview'] if include_other or p.get('it_classification',{}).get('status')=='CONFIRMED_IT'],hide_index=True)
    if st.button('Ejecutar simulación completa sin envíos'):
        try:st.success(f'Trabajador de simulación iniciado: {launch_simulation()}')
        except Exception:st.error('No se pudo iniciar el trabajador; revisa logs del proyecto.')
    st.caption('La simulación completa conserva una decisión por oferta, sin detenerse al cubrir cupos. No escribe datos personales en webs reales.')
    st.json(report(db))
    history=db.rows('''SELECT a.id,p.job_id,j.title,j.company,p.decision,a.state,a.target_url,a.document_id,a.updated_at,a.error_code,a.confirmation_reference,
                       s.status AS intervention_state,s.form_state AS browser_form_state
                       FROM application_attempts a JOIN application_plans p ON p.id=a.plan_id JOIN jobs j ON j.id=p.job_id
                       LEFT JOIN autoapply_interventions s ON s.attempt_id=a.id ORDER BY a.id DESC''')
    classifications={j['id']:classify_it_functions(j).status for j in db.rows('SELECT id,title,description,category,detail_complete FROM jobs')}
    visible_history=[a for a in history if include_other or classifications.get(a['job_id'])=='CONFIRMED_IT']
    st.dataframe(visible_history,hide_index=True)
    if visible_history:
        with st.expander('Resolver un intento o revisar sus preguntas'):
            st.caption('Resolver manualmente no acredita confirmación externa. No repetir conserva identidad y cupos. El reintento solo vuelve a preparar documentos de simulación; nunca rellena ni envía formularios públicos.')
            chosen=st.selectbox('Intento para resolver',[a['id'] for a in visible_history],format_func=lambda key:next(str(a['id'])+' · '+a['title']+' · '+a['state'] for a in visible_history if a['id']==key))
            selected=next(a for a in visible_history if a['id']==chosen)
            st.dataframe(db.rows('SELECT question_hash,fact_id,answer_hash,created_at FROM application_answers WHERE attempt_id=?',(chosen,)),hide_index=True)
            st.dataframe(db.rows('SELECT occurred_at,kind,before_state,after_state,details FROM application_events WHERE attempt_id=? ORDER BY id',(chosen,)),hide_index=True)
            with st.form('aa_resolution'):
                action=st.selectbox('Acción manual',['NO_REPETIR','MARCAR_RESUELTA','REINTENTAR_PREPARACION_SIMULADA'])
                acknowledged=st.checkbox('He revisado el historial; esta acción no certifica un envío ni libera una candidatura incierta')
                if st.form_submit_button('Guardar resolución manual'):
                    try:
                        from .resolution import manual_resolution,retry_simulation_preparation
                        result=(retry_simulation_preparation(db,chosen,acknowledged,selected['updated_at']) if action=='REINTENTAR_PREPARACION_SIMULADA'
                                else manual_resolution(db,chosen,action,acknowledged,selected['updated_at']))
                        st.json(result)
                    except Exception:
                        st.error('Acción retenida: comprueba aceptación, estado actualizado, trabajador ocupado, evidencia previa al envío y política vigente. No se han liberado identidades ni enviado datos.')
    plans=db.rows('SELECT id,job_id,decision,state,reasons,created_at FROM application_plans ORDER BY id DESC')
    st.dataframe([p for p in plans if include_other or classifications.get(p['job_id'])=='CONFIRMED_IT'],hide_index=True)
    st.caption(f'{len(plans)} planes históricos conservados. El filtro IT solo cambia la vista; la exportación conserva todos.')
    st.download_button('Exportar auditoría AutoApply JSON',json.dumps({'status':report(db),'plans':plans,'attempts':history},ensure_ascii=False,indent=2),file_name='autoapply-audit.json',mime='application/json')
