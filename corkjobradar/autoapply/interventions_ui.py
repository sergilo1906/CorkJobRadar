"""Interventions show metadata only; no browser secrets or personal-field snapshots."""
import streamlit as st
from .human_sessions import (pending_interventions,worker_alive,request_command,launch_session,
                             create_intervention,PAUSED,EXPIRED,TERMINAL)
from .interaction_modes import interaction_route


@st.fragment(run_every=3)
def render_interventions(db):
    st.subheader('Intervenciones pendientes')
    st.caption('LIVE OFF. Resolver una verificación humana no autoriza el envío ni confirma recepción. LinkedIn e Indeed se utilizan manualmente; cada web empresarial requiere permiso independiente.')
    rows=pending_interventions(db)
    pending=[r for r in rows if r['status'] not in TERMINAL]
    if not pending:st.info('No hay intervenciones pendientes. Ningún formulario externo con datos personales se ha abierto automáticamente.')
    for row in pending:
        sid=row['id']
        with st.expander(row['company']+' · '+row['title']+' · '+row['status'],expanded=True):
            st.write('Modo:', 'HUMAN_VERIFICATION' if row['status']==PAUSED else 'HOLD')
            st.write('Motivo:',row['reason_code'])
            st.write('Estado del formulario:',row['form_state'])
            st.write('Última verificación:',row['last_verified_at'] or 'Sin verificar')
            st.write('Campos preparados:',row['filled_count'])
            st.code(row.get('apply_url') or row['url'],language=None)
            if row['status']==EXPIRED:
                st.warning('El navegador está cerrado o la sesión no está disponible. Será necesario reconstruir los campos, comprobar de nuevo el CV y repetir la verificación humana. No se conserva un CAPTCHA resuelto.')
            if row['fixture_url']:st.caption('Prueba local aislada; no es una candidatura externa.')
            if st.button('Abrir o recuperar sesión autorizada',key='hi_open_'+sid,disabled=bool(row['submission_started'])):
                try:
                    if row['worker_available']:request_command(db,sid,'FOCUS' if row['status']!=EXPIRED else 'RECOVER')
                    else:launch_session(db,sid,'RECOVER' if row['form_state']!='SIN_ABRIR' else 'OPEN')
                    st.success('Acción solicitada; actualiza el estado para comprobar su resultado.')
                except Exception:st.error('Sesión retenida: faltan permisos o cambiaron sus condiciones. No se han abierto formularios externos.')
            if st.button('CONTINUAR CANDIDATURA',key='hi_continue_'+sid,disabled=not(row['worker_available'] and row['status']==PAUSED) or bool(row['submission_started'])):
                try:
                    request_command(db,sid,'CONTINUE')
                    st.success('Revalidación solicitada. El botón por sí solo no confirma la verificación ni envía.')
                except Exception:st.error('No se puede continuar: revisa sesión, CV, respuestas, política, requisitos, ruta y vigencia.')
            if st.button('Cerrar sesión de navegador',key='hi_close_'+sid,disabled=not row['worker_available']):
                try:request_command(db,sid,'CLOSE');st.success('Cierre solicitado.')
                except Exception:st.error('No se pudo solicitar el cierre; comprueba el estado del proceso.')
    if rows:
        st.dataframe([{k:r[k] for k in ('company','title','status','reason_code','form_state','last_verified_at','filled_count')} for r in rows],hide_index=True)
    st.button('Actualizar intervenciones',key='hi_refresh')
    with st.expander('Sesión interactiva para un intento preparado'):
        attempts=db.rows("""SELECT a.id,a.state,j.url,j.apply_url,j.title,j.company FROM application_attempts a
                             JOIN application_plans p ON p.id=a.plan_id JOIN jobs j ON j.id=p.job_id
                             WHERE a.state='LISTA_PARA_ENVIO' ORDER BY a.id DESC""")
        if not attempts:st.caption('No hay intentos con formulario preparado y autorización apta para sesión interactiva.')
        for attempt in attempts:
            route=interaction_route(attempt.get('apply_url') or attempt['url'],source_url=attempt['url'])
            st.write(attempt['company']+' · '+attempt['title']+' · '+route['mode'])
            st.caption(route['reason'])
            if st.button('Preparar intervención autorizada',key='hi_prepare_'+str(attempt['id']),disabled=not route['automation_allowed']):
                inspections=db.rows('''SELECT i.id FROM autoapply_form_inspections i JOIN application_plans p ON p.job_id=i.job_id
                                      JOIN application_attempts a ON a.plan_id=p.id WHERE a.id=? ORDER BY i.id DESC''',(attempt['id'],))
                try:
                    if not inspections:raise ValueError('INSPECTION_REQUIRED')
                    sid=create_intervention(db,attempt['id'],inspections[0]['id']);launch_session(db,sid)
                    st.success('Sesión autorizada solicitada.')
                except Exception:st.error('Preparación retenida por las comprobaciones actuales; no se han enviado datos.')
