"""Local controls; never authorizes CV, Windows startup, policy or live sending."""
from pathlib import Path
import streamlit as st
from .runtime import Watchdog,state,command,configure,snapshot,update,process_stamp
from .config import ROOT,now

NOTICES={'APPROVED_CV_REQUIRED':'Revisa y aprueba tu CV definitivo para preparar paquetes.',
         'HUMAN_VERIFICATION':'CAPTCHA, MFA o verificación humana pendiente. Abre las intervenciones de AutoApply.',
         'ESSENTIAL_ANSWER':'Falta una respuesta legal o habilitación imprescindible. Revisa la oferta y sus preguntas.',
         'SOURCE_ACCESS_REVIEW':'Fuente bloqueada: necesita revisión manual de acceso; no se elude ni se reintenta continuamente.',
         'REPEATED_FAILURE':'Actividad pausada tras fallos repetidos. Revisa los errores antes de reanudar.'}
NOTICES['PREPARATION_REVIEW']='No se pudo preparar un paquete. Revisa CV, documentos, preguntas y cambios de esta oferta; no se ha enviado nada.'


@st.cache_resource
def attach_watchdog(database):
    return Watchdog(database)


def bootstrap(db):
    import os
    update(db,owner_pid=os.getpid(),owner_stamp=process_stamp(os.getpid()))
    return attach_watchdog(str(db.path.resolve()))


def startup_script():
    # Download only. The app never installs this in the Windows Startup folder.
    python=str(ROOT/'.venv/Scripts/pythonw.exe').replace('"','""')
    script=str(ROOT/'scripts/iniciar_local.py').replace('"','""')
    return ('Set shell = CreateObject("WScript.Shell")\r\n'
            'shell.Run Chr(34) & "'+python+'" & Chr(34) & " " & Chr(34) & "'+script+'" & Chr(34), 0, False\r\n').encode('utf-16')


@st.fragment(run_every='5s')
def render(db):
    st.subheader('Actividad local continua · Windows · LIVE OFF')
    data=snapshot(db);row=data['control']
    st.write('Actividad solicitada:',row['desired'],'· Estado:',row['state'],'· Supervisor:', 'activo' if data['supervisor_alive'] else 'detenido')
    from .ui.visibility import runtime_actions
    labels={'START':'Iniciar actividad local','PAUSE':'Pausar actividad','RESUME':'Reanudar actividad','STOP':'Detener actividad','SEARCH_NOW':'Buscar IT ahora'}
    actions=list(runtime_actions(row))
    if row['state']!='STOPPING' and not row.get('active_kind'):actions.append('SEARCH_NOW')
    cols=st.columns(max(1,len(actions)))
    for col,action in zip(cols,actions):
        label=labels[action]
        col.button(label,key='local_'+action,on_click=command,args=(db,action))
    st.caption('Cerrar la pestaña no detiene el proceso local. Pausar o detener deja terminar la petición/tarea en curso y conserva los puntos de reanudación. Apagar o suspender el PC detiene su ejecución; al volver se conserva la cola. No se envían candidaturas.')
    with st.expander('Configurar frecuencia y preparación local'):
        with st.form('local_runtime_config'):
            hours=st.number_input('Horas entre búsquedas IT',.25,168.0,float(row['interval_hours']),step=.25)
            prepare=st.checkbox('Preparar todas las candidaturas razonables con CV previamente aprobado',value=bool(row['auto_prepare']))
            sound=st.checkbox('Aviso sonoro local al aparecer nuevas intervenciones',value=bool(row['sound']))
            if st.form_submit_button('Guardar configuración local'):
                configure(db,hours,prepare,sound);st.success('Configuración guardada. No activa envío ni inicio con Windows.');st.rerun(scope='fragment')
        st.write('Ballinlough · 50 km en línea recta · funciones IT/DAM confirmadas · mínimo solicitado hasta 3 años. Transporte pendiente y deseables advierten. Origen preciso y CV se revisan en el panel de candidaturas. LinkedIn/Indeed permanecen manuales.')
    last=row['last_search_finished']
    if not last:
        old=db.rows('SELECT r.finished_at FROM scan_runs r WHERE r.finished_at IS NOT NULL AND EXISTS(SELECT 1 FROM source_runs s WHERE s.run_id=r.id) ORDER BY r.id DESC LIMIT 1')
        last=old[0]['finished_at'] if old else None
    st.write('Última búsqueda finalizada:',last or 'Sin búsqueda acreditada','· Próxima programada:',row['next_search_at'] or 'Al iniciar')
    if row['desired']!='RUNNING':st.caption('Programación inactiva o pausada: la fecha pendiente se retomará al reanudar; no se ejecutará mientras esté detenido.')
    st.write('Última preparación local:',row['last_prepare_at'] or 'Pendiente','· Último latido:',row['heartbeat'] or 'Sin supervisor')
    cols=st.columns(3);cols[0].metric('Paquetes preparados',data['prepared']);cols[1].metric('Enviadas con confirmación externa',data['confirmed_external']);cols[2].metric('Declaradas manualmente',data['manual_declarations'])
    with st.expander('Tareas pendientes, cola y errores'):
        st.dataframe(data['pending_tasks'],hide_index=True);st.dataframe(data['queue'],hide_index=True)
        if row['last_error_code']:st.warning('Último error: '+row['last_error_code'])
        st.dataframe(data['events'],hide_index=True)
    pending=[n for n in data['notifications'] if n['acknowledged_at'] is None]
    with st.expander('Intervenciones y avisos pendientes ('+str(len(pending))+')',expanded=bool(pending)):
        for item in pending:
            st.warning(NOTICES.get(item['kind'],item['kind']))
            if item['job_id']:
                jobs=db.rows('SELECT company,title FROM jobs WHERE id=?',(item['job_id'],))
                if jobs:st.text(jobs[0]['company']+' · '+jobs[0]['title'])
            st.caption(item['created_at'])
            if st.button('Marcar aviso como leído',key='local_notice_'+str(item['id'])):
                db.execute('UPDATE local_runtime_notifications SET acknowledged_at=? WHERE id=?',(now(),item['id']));st.rerun(scope='fragment')
        if not pending:st.caption('No hay avisos nuevos. Marcar leído no resuelve CAPTCHA, preguntas ni requisitos.')
    with st.expander('Inicio opcional al entrar en Windows · desactivado'):
        st.write('No se ha instalado ningún servicio ni inicio automático. Si quieres activarlo, descarga este lanzador y cópialo tú a tu carpeta de Inicio: Win+R → shell:startup. Para desactivarlo, elimina únicamente ese lanzador de esa carpeta.')
        st.download_button('Descargar lanzador opcional de inicio',startup_script(),file_name='CorkJobRadar-inicio-opcional.vbs',mime='application/octet-stream',key='local_startup_download')
        st.caption('Descargarlo no lo activa. Reutiliza el servidor del proyecto si ya está abierto y respeta el estado pausado/detenido guardado. Durante el apagado no trabaja; vuelve a ejecutarse al iniciar sesión solo si tú has instalado el lanzador.')
