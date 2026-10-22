"""Public form inspection, disconnected preparation and controlled-trial readiness."""
import streamlit as st
from ..config import load_profile
from ..http import WebClient
from .forms import inspect_job_form,load_inspection,disconnected_preparation,answer_plan
from .vault import candidate_snapshot,approve_fact
from ..config import digest
from .trials import trial_readiness,create_trial_plan,authorize_trial,autonomous_readiness,TRIAL_CONSENT
from .platforms import platform_for


def render_operations(db,jobs):
    from .manual_ui import render_manual_operations
    render_manual_operations(db,jobs)
    from .interventions_ui import render_interventions
    render_interventions(db)
    with st.expander('Formularios y preparación de una candidatura sin envío'):
        st.caption('La inspección solo usa GET públicos. La comprobación de campos se ejecuta desconectada de Internet: no introduce datos ni sube el CV al ATS. No acredita envío ni funcionamiento completo del formulario alojado.')
        supported=[j for j in jobs if platform_for(j.get('apply_url') or j['url']).get('inspection_supported')]
        if supported:
            jid=st.selectbox('Vacante IT para inspeccionar',[j['id'] for j in supported],format_func=lambda key:next(j['title']+' · '+j['company'] for j in supported if j['id']==key))
            hosted=st.checkbox('Comprobar también el DOM público Greenhouse sin rellenar ni enviar',value=False)
            if st.button('Inspeccionar formulario público (solo lectura)'):
                try:
                    with WebClient(load_profile(),db) as client:result=inspect_job_form(db,jid,client,hosted)
                    st.success('Inspección guardada sin datos personales enviados. Permiso de envío aún no verificado.')
                except Exception:st.error('Inspección retenida: fuente no disponible, acceso restringido, esquema cambiado u oferta pendiente. No se eluden restricciones.')
            inspections=db.rows('SELECT id,inspected_at,status FROM autoapply_form_inspections WHERE job_id=? ORDER BY id DESC',(jid,))
            iid=None
            if inspections:
                iid=st.selectbox('Inspección conservada',[r['id'] for r in inspections],format_func=lambda key:next(str(r['id'])+' · '+r['inspected_at']+' · '+r['status'] for r in inspections if r['id']==key))
                try:
                    result=load_inspection(db,iid)
                    st.dataframe([{'Pregunta':f['label'],'Tipo':f['type'],'Obligatoria':f['required']} for f in result['fields']],hide_index=True)
                    if result['blockers']:st.warning('Hay restricciones o campos sin validar: '+', '.join(result['blockers']))
                    cv_options=db.rows("SELECT id,approved_at FROM candidate_documents WHERE kind='CV' AND facts_hash=? AND revoked_at IS NULL ORDER BY id DESC",(candidate_snapshot(db)['_cv_facts_hash'],))
                    review_cv=st.selectbox('CV para la preparación desconectada',[None]+[r['id'] for r in cv_options],
                                          format_func=lambda key:'Usar mi CV aprobado' if key is None else 'Versión '+str(key)+(' · pendiente, solo revisión local' if not next(r for r in cv_options if r['id']==key)['approved_at'] else ' · aprobada'))
                    if st.button('Comprobar preparación desconectada con mi CV y datos aprobados'):
                        prepared=disconnected_preparation(db,iid,review_cv)
                        st.session_state['aa_disconnected_result']=prepared
                    cached=st.session_state.get('aa_disconnected_result')
                    if cached and cached['inspection_id']==iid and cached['facts_hash']==candidate_snapshot(db)['_facts_hash']:
                        st.write('Resultado: '+cached['state'])
                        st.write('Campos con datos aprobados:',cached['resolved_fields'])
                        if cached['unresolved_questions']:st.dataframe(cached['unresolved_questions'],hide_index=True)
                        if cached.get('using_unapproved_cv_for_local_review_only'):st.warning('Este CV sigue pendiente de aprobación. Se ha usado únicamente en una revisión local sin conexión al ATS.')
                        st.caption('Cero envíos. Las preguntas pendientes requieren respuestas verificadas y preaprobadas; no se rellenan por intuición.')
                    pending=answer_plan(result,candidate_snapshot(db))['unresolved']
                    if pending:
                        with st.expander('Guardar una respuesta verificada a una pregunta pendiente'):
                            from urllib.parse import urlsplit
                            selected=st.selectbox('Pregunta pendiente',[q['field'] for q in pending],format_func=lambda key:next(q['label'] for q in pending if q['field']==key))
                            field=next(f for f in result['fields'] if f['id']==selected)
                            st.write(field['label']);host=urlsplit(result['public_url']).hostname
                            st.caption('Respuesta autorizada únicamente para esta pregunta exacta y '+host+'. Cambiar respuestas pausa la política; no modifica ni vuelve a pedir aprobación de los hechos del CV.')
                            with st.form('aa_form_answer_'+str(iid)+'_'+digest(selected)[:12]):
                                if field['type']=='select-one':
                                    values=[None]+[o['value'] for o in field['options']]
                                    value=st.selectbox('Respuesta',values,format_func=lambda key:'Sin respuesta' if key is None else next(o['text'] for o in field['options'] if o['value']==key))
                                elif field['type']=='checkbox':value=st.selectbox('Respuesta',['','true','false'])
                                else:value=st.text_area('Respuesta veraz, sin inventar experiencia ni condiciones')
                                sensitive=st.checkbox('Autorizo expresamente esta respuesta si contiene una aceptación legal o datos sensibles')
                                confirmed=st.checkbox('He contrastado la respuesta y autorizo guardarla cifrada para esta pregunta y dominio')
                                if st.form_submit_button('Guardar respuesta verificada'):
                                    if not value or not confirmed:st.error('Falta una respuesta y su confirmación expresa.')
                                    else:
                                        approve_fact(db,'answer:'+digest([host,field['label']])[:40],{'question':field['label'],'host':host,'answer':value,'explicit_sensitive':sensitive},'USER_REVIEWED_EXACT_FORM_QUESTION',True)
                                        st.success('Respuesta cifrada guardada. Revisa la política pausada antes de reanudar; no se ha enviado nada.')
                except Exception:st.error('La inspección o el CV necesitan una nueva revisión; no se ha enviado nada.')
            with st.expander('Preparar un único ensayo real futuro'):
                st.caption('Crear el plan no autoriza enviar. La autorización se limita a una vacante, CV, ficha, formulario y política concretos durante 24 horas. El envío autónomo necesitará una activación separada tras comprobar el ensayo.')
                try:
                    readiness=trial_readiness(db,jid,iid)
                    st.write('Requisitos pendientes:',readiness['blockers'])
                    for step in readiness['procedure']:st.write('• '+step)
                    if st.button('Crear plan de ensayo para revisar (sin autorizar envío)'):
                        st.session_state['aa_trial_plan']=create_trial_plan(db,jid,iid)
                    trial=st.session_state.get('aa_trial_plan')
                    if trial and trial['readiness']['snapshot']['job_id']==jid:
                        st.write({'Plan':trial['trial_id'],'Caducidad':trial['expires_at'],'Huella revisada':trial['snapshot_hash']})
                        consent=st.checkbox('Autorizo expresamente UN envío real de este plan y ninguna otra candidatura',disabled=not readiness['ready'])
                        if st.button('Autorizar este ensayo único',disabled=not readiness['ready'] or not consent):
                            authorize_trial(db,trial['trial_id'],trial['snapshot_hash'],TRIAL_CONSENT)
                            st.success('Autorización del ensayo registrada; no se ha ejecutado ningún envío.')
                    if not readiness['ready']:st.info('El ensayo no puede autorizarse ni ejecutarse todavía: hay requisitos pendientes y el transporte real no está liberado.')
                except Exception:st.error('El paquete del ensayo ha cambiado o no puede verificarse. Crea un nuevo plan tras resolver las evidencias.')
        else:st.info('No hay vacantes IT confirmadas de una plataforma compatible con inspección.')
    with st.expander('Requisitos para activar el modo autónomo IT'):
        ready=autonomous_readiness(db)
        st.write('Envío real: DESACTIVADO')
        st.write('Pendiente:',ready['blockers'])
        st.caption('El modo A aplicará dentro de la política activa, sin aprobación individual de cada candidatura. No se ofrece activación mientras falten el ensayo real y las validaciones del adaptador y de recepción.')
