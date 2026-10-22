"""Focused screens. Existing backend services retain every authorization gate."""
from html import escape
import math
import streamlit as st
from ..config import now
from .. import runtime as rt
from .model import date_label,filter_jobs
from .visibility import APPLICATION_STATES,runtime_actions,safe_controls,actions_for


def go(page,job=None,step=None,section=None):
    st.session_state.ui_area=page
    st.session_state.ui_job=job
    if step is not None:st.session_state.ui_job_step=step
    if section is not None:st.session_state.ui_profile_section=section


def nav_button(label,page,*,job=None,step=None,section=None,key=None,primary=False):
    st.button(label,key=key,on_click=go,args=(page,job,step,section),type='primary' if primary else 'secondary')


def empty(text):st.markdown('<div class="cjr-empty">'+escape(text)+'</div>',unsafe_allow_html=True)
def title(name,description):st.title(name);st.caption(description)
def clear_job():st.session_state.ui_job=None


def runtime_label(data):
    r=data['control']
    if r['state']=='STOPPING':return 'Terminando la tarea actual'
    if r['desired']=='PAUSED':return 'Actividad pausada'
    if r['desired']=='STOPPED':return 'Actividad detenida'
    if not data['supervisor_alive']:return 'Recuperando trabajador local'
    return 'Buscando ofertas' if r.get('active_kind')=='SCAN' else 'Preparando candidaturas' if r.get('active_kind') else 'Activa · esperando próximo ciclo'


@st.fragment(run_every='5s')
def home_runtime(db):
    data=rt.snapshot(db);row=data['control']
    st.markdown('<span class="cjr-status">'+escape(runtime_label(data))+'</span>',unsafe_allow_html=True)
    st.write('Última búsqueda: '+date_label(row['last_search_finished'],'Sin búsqueda finalizada'))
    st.write('Próxima: '+(date_label(row['next_search_at'],'Al iniciar') if row['desired']=='RUNNING' else 'Programación pausada o detenida'))
    if row['last_error_code']:st.error('La actividad necesita revisión. Consulta Actividad y notificaciones.')


def home(db,view):
    title('Tu próxima oportunidad IT','Ballinlough, Cork · 50 km · Bicicleta y transporte público')
    home_runtime(db)
    notices=rt.snapshot(db)['notifications']
    groups=[[('Ofertas guardadas',len(view['jobs'])),('Oportunidades IT por revisar',view['potential']),('Candidaturas preparadas',view['prepared'])],
            [('Recepciones externas confirmadas',view['confirmed']),('Envíos declarados manualmente',view['manual']),('Intervenciones pendientes',db.rows("SELECT COUNT(*) n FROM autoapply_interventions WHERE status NOT IN ('PRUEBA_LOCAL_CONFIRMADA','ENVIO_INCIERTO')")[0]['n'])]]
    st.caption(('CV aprobado' if view['cv_approved'] else 'CV pendiente de tu aprobación')+' · AutoApply LIVE OFF')
    html='<dl class="cjr-metrics">'
    for group in groups:
        for label,value in group:html+='<div class="cjr-metric"><dt>'+escape(label)+'</dt><dd>'+str(value)+'</dd></div>'
    st.markdown(html+'</dl>',unsafe_allow_html=True)
    st.caption('Guardada no significa compatible. Hay que contrastar vigencia, requisitos, centro y accesibilidad.')
    st.subheader('Qué necesitas hacer ahora')
    if not view['cv_approved']:
        with st.container(border=True):
            held=bool(db.rows("SELECT id FROM job_document_events WHERE kind='GENERAL_CV_QUALITY_HOLD' LIMIT 1"))
            if held:
                st.markdown('**Preparar tu CV para una oferta**')
                st.write('Tus hechos aprobados se conservan. Elige una oportunidad y revisa sus documentos en el paso CV; el CV general anterior está retenido por calidad.')
                nav_button('Elegir oferta y preparar documentos','Ofertas de empleo',key='home_cv',primary=True)
            else:
                st.markdown('**Revisar tu CV definitivo**')
                st.write('Tus datos aprobados se conservan. Falta aprobar una versión del documento para preparar paquetes.')
                nav_button('Revisar y aprobar CV','Perfil y configuración',section='CV definitivo',key='home_cv',primary=True)
    with st.container(border=True):
        st.markdown('**Consultar oportunidades informáticas**')
        st.write('Compara requisitos obligatorios y deseables antes de preparar tu candidatura.')
        nav_button('Ver ofertas IT','Ofertas de empleo',key='home_offers')
    if any(n['kind']!='APPROVED_CV_REQUIRED' for n in notices):nav_button('Resolver avisos pendientes','Actividad y notificaciones',key='home_notices')
    st.caption(('CV definitivo aprobado' if view['cv_approved'] else 'CV pendiente de aprobación')+' · AutoApply LIVE OFF · No se realizan envíos externos.')
    st.button('Actualizar resumen',key='home_refresh')


def _persist_filters():
    for name in ('search','scope','mode','status','family','size','page'):
        key='offer_'+name
        if key in st.session_state:st.session_state.setdefault('offer_saved',{})[name]=st.session_state[key]


def _restore_filters():
    for name,value in st.session_state.get('offer_saved',{}).items():st.session_state.setdefault('offer_'+name,value)


def open_label(value):
    return {'OPEN_CONFIRMED':'Abierta verificada','OPEN_LIKELY':'Posiblemente abierta','CLOSED_CONFIRMED':'Cerrada'}.get(value,'Vigencia pendiente')


def academic_summary(db,view):
    if not view.get('academic_reviewed'):return
    st.caption(f"Reevaluación académica vigente: {view['academic_reviewed']}/{len(view['jobs'])} ofertas. {view['potential']} oportunidades IT locales por revisar. Las dudas menores no excluyen; la distancia y la recepción no se presumen.")
    st.caption(f"{view.get('priority_local',0)} para revisar primero · {view.get('conditional_local',0)} condicionadas a requisitos académicos o lingüísticos esenciales.")
    with st.expander('Lista completa tras actualizar mi formación'):
        from ..reevaluation import opportunity_report,report_markdown,report_excel
        from ..autoapply.academic import SOURCES
        report=opportunity_report(db)
        st.write('Se muestran todas las oportunidades, incluidas las condicionadas por idiomas o matrícula. No todas son plenamente elegibles.')
        st.download_button('Descargar lista IT actualizada',report_markdown(report).encode('utf-8'),file_name='Oportunidades-IT-DAM.md',mime='text/markdown',key='academic_list_download')
        st.download_button('Descargar lista IT en Excel',report_excel(report),file_name='Oportunidades-IT-DAM.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',key='academic_excel_download')
        st.caption('CFGS DAM no se equipara automáticamente a Bachelor, Honours Degree o NFQ8. Referencias genéricas; aceptación del empleador por confirmar.')
        if report.get('pending_it_reviews'):st.write(f"{len(report['pending_it_reviews'])} anuncios adicionales en IT por confirmar. Se conservan como HOLD; no se preparan hasta acreditar sus funciones y ubicación.")
        st.link_button('Referencia oficial QQI/NARIC sobre Técnico Superior',SOURCES[1])


def offer_card(job,application=False):
    with st.container(border=True):
        company=job['company'] or 'Empresa pendiente'
        st.markdown('<p class="cjr-company" title="'+escape(company)+'">'+escape(company)+'</p>',unsafe_allow_html=True)
        st.markdown('<h3 class="cjr-job-title" title="'+escape(job['title'])+'">'+escape(job['title'])+'</h3>',unsafe_allow_html=True)
        st.write(job['location_label']+' · '+job['distance_label'])
        mode={'REMOTE':'Remoto','HYBRID':'Híbrido','ONSITE':'Presencial'}.get(job['mode'],'Modalidad por aclarar')
        st.caption(job['experience_label']+' · '+mode+' · '+job['salary_label'])
        st.write('**'+job['application']+'**' if application else job['compatibility']+' · '+open_label(job['open_status']))
        if job.get('academic_label'):st.caption(job['academic_label'])
        if job.get('deadline_status') not in {None,'ABSENT'}:st.caption('Plazo publicado: '+(date_label(job.get('deadline_at')) if job['deadline_status'] in {'NOT_EXPIRED','EXPIRED'} else 'Pendiente de aclarar'))
        if job.get('review_priority')==2:st.caption(job['priority_note'])
        if application and job['application_at']:st.caption(date_label(job['application_at']))
        nav_button('Abrir candidatura' if application else 'Ver oferta','Mis candidaturas' if application else 'Ofertas de empleo',job=job['id'],key=('application_' if application else 'offer_open_')+job['id'])


def offers(db,view):
    if st.session_state.get('ui_job'):
        job=next((j for j in view['jobs'] if j['id']==st.session_state.ui_job),None)
        if job:return detail(db,view,job)
        clear_job()
    title('Ofertas de empleo','Informática y DAM · Hasta 3 años de mínimo obligatorio · Los requisitos deseables no excluyen')
    if not view['jobs']:
        empty('No hay resultados guardados todavía. Inicia una búsqueda o importa un anuncio desde Actividad y notificaciones.')
        nav_button('Iniciar o revisar búsqueda','Actividad y notificaciones',key='empty_offers_activity',primary=True)
        return
    academic_summary(db,view)
    if st.toggle('Vista de tabla y filtros avanzados',key='offers_advanced_table'):
        from ..ui_legacy import render_legacy
        render_legacy(db,'list')
        return
    _restore_filters()
    st.text_input('Buscar puesto, empresa o ubicación',key='offer_search',on_change=_persist_filters)
    cols=st.columns(2)
    scope=cols[0].selectbox('Mostrar',['Oportunidades IT','IT por confirmar','Todas las IT','Todas las ofertas'],key='offer_scope',on_change=_persist_filters)
    families=['Todas']+sorted({f for j in view['jobs'] for f in j['families']})
    family=cols[1].selectbox('Categoría IT',families,key='offer_family',on_change=_persist_filters)
    with st.expander('Más filtros'):
        cols=st.columns(2)
        mode=cols[0].selectbox('Modalidad',['Todas','ONSITE','HYBRID','REMOTE','DESCONOCIDO'],format_func=lambda v:{'ONSITE':'Presencial','HYBRID':'Híbrida','REMOTE':'Remota','DESCONOCIDO':'Por aclarar'}.get(v,v),key='offer_mode',on_change=_persist_filters)
        status=cols[1].selectbox('Vigencia',['Todas','OPEN_CONFIRMED','OPEN_LIKELY','CLOSED_CONFIRMED','UNKNOWN'],format_func=lambda v:'Todas' if v=='Todas' else open_label(v),key='offer_status',on_change=_persist_filters)
        st.caption('Ubicación o experiencia desconocidas permanecen pendientes. Remotos separados, sin autorización automática.')
    filtered=filter_jobs(view['jobs'],st.session_state.get('offer_search',''),scope,mode,status,family)
    st.write(f'**{len(filtered)} resultados** · {len(view["jobs"])} ofertas conservadas')
    cols=st.columns(2);size=cols[0].selectbox('Resultados por página',[8,16,32],key='offer_size',on_change=_persist_filters)
    pages=max(1,math.ceil(len(filtered)/size))
    if st.session_state.get('offer_page',1)>pages:st.session_state.offer_page=1
    page=cols[1].number_input('Página',min_value=1,max_value=pages,key='offer_page',on_change=_persist_filters)
    if not filtered:empty('No hay resultados con estos filtros. Prueba Todas las IT o amplía la búsqueda. No se han eliminado ofertas.')
    for job in filtered[(page-1)*size:page*size]:offer_card(job)
    st.caption(f'Página {page} de {pages}. Solo se pagina la vista; el trabajador procesa toda su cola.')
    with st.expander('Buscar en canales oficiales e importar ofertas'):
        from ..junior_discovery import ROLE_QUERIES,manual_channels
        from urllib.parse import urlencode
        role=st.selectbox('Puesto para buscar en los canales oficiales',ROLE_QUERIES,key='official_role')
        st.link_button('Buscar en LinkedIn manualmente','https://www.linkedin.com/jobs/search/?'+urlencode({'keywords':role,'location':'Cork, Ireland'}))
        st.link_button('Buscar en Indeed manualmente','https://ie.indeed.com/jobs?'+urlencode({'q':role,'l':'Cork'}))
        st.caption('Se usan sus funciones oficiales. No se automatizan sus interfaces.')
        for channel in manual_channels():
            st.link_button('Abrir canal manual: '+channel['name'],channel['url'])
            st.caption(channel['status']+' · '+channel['note'])
        nav_button('Fuentes e importación','Actividad y notificaciones',key='offers_sources')


def detail(db,view,job):
    st.button('Volver a resultados',on_click=clear_job,key='back_offers')
    title(job['title'],job['company']+' · '+job['location_label'])
    st.write(open_label(job['open_status'])+' · '+job['distance_label']+' · '+job['compatibility'])
    cols=st.columns(2)
    cols[0].write('**Salario publicado**');cols[0].write(job['salary_label'])
    cols[1].write('**Experiencia solicitada**');cols[1].write(job['experience_label'])
    st.caption('Publicación: '+date_label(job.get('posted_at'),'No publicada')+' · Verificación: '+date_label(job.get('last_verified_at'),'Pendiente'))
    from ..autoapply.manual_workspace import assess_manual_job
    from ..autoapply.broad_selection import assess_selection
    from ..autoapply.selection_ui import reason_text
    assessment=assess_manual_job(db,job);selection=assess_selection(db,job)
    if selection['exclusions']:st.warning(' '.join(reason_text(x) for x in selection['exclusions']))
    elif selection['essential_pending']:st.info('Por resolver: '+' '.join(reason_text(x) for x in selection['essential_pending']))
    if selection['warnings']:st.caption('Advertencias: '+' '.join(reason_text(x) for x in selection['warnings']))
    st.subheader('Formación y titulación')
    st.write(job['academic_label'])
    for item in selection['academic_review']['items']:
        st.write('• '+item['quote']);st.caption(item['status']+' · '+item['reason'])
    st.caption('DAM terminado no implica Bachelor, Honours Degree ni NFQ8. Una duda académica mantiene la oportunidad para revisión y no autoriza el envío.')
    st.subheader('Responsabilidades')
    duties=view['analyses'].get(job['id'],{}).get('documentary',{}).get('duties_original',[])
    if duties:
        for line in duties[:8]:st.write('• '+line)
        if len(duties)>8:
            with st.expander('Más responsabilidades'):
                for line in duties[8:]:st.write('• '+line)
    else:st.info('Funciones sin separar con fiabilidad. Consulta el anuncio original antes de decidir.')
    for level,label in [('OBLIGATORIO','Requisitos obligatorios'),('DESEABLE','Requisitos deseables'),('POR_ACLARAR','Pendientes de aclarar')]:
        st.subheader(label);rows=[r for r in assessment['requirements'] if r['level']==level]
        if rows:
            for r in rows:st.write('• '+r['quote']);st.caption(r['status']+' · '+r['reason'])
        else:st.caption('No se han extraído requisitos de este tipo con fiabilidad; no significa que no existan.')
    st.subheader('Transporte y horario')
    st.write('Ballinlough · Sin coche propio · '+('Comprobación vigente registrada' if assessment['transport_verified'] else 'Accesibilidad pendiente de comprobar'))
    st.caption('Horario: '+str(assessment['schedule'] or 'No publicado o por aclarar')+'. La distancia no acredita un trayecto viable.')
    st.link_button('Abrir anuncio original',job['url'])
    if job['application'] in APPLICATION_STATES[3:]:
        st.info('Candidatura: '+job['application']+'. Consulta su historial antes de cualquier otra actuación.')
        nav_button('Ver candidatura','Mis candidaturas',job=job['id'],key='detail_existing')
    else:
        controls=actions_for(cv_approved=view['cv_approved'],preparation_allowed=selection['preparation_allowed'],application=job['application'])
        if controls['prepare'] or (controls['review_cv'] and selection['preparation_allowed']):nav_button('Preparar candidatura','Mis candidaturas',job=job['id'],step='Solicitud' if view['cv_approved'] else 'CV',key='detail_prepare',primary=True)
        else:st.info('Preparación retenida por los criterios del puesto. Revisa requisitos y evidencias antes de continuar.')
    with st.expander('Texto publicado completo'):st.text(job['description'] or 'Texto pendiente de recuperar')
    if st.checkbox('Mostrar análisis y herramientas avanzadas de esta oferta',key='detail_advanced'):
        from ..ui_legacy import render_legacy
        render_legacy(db,'detail',job['id'])


def applications(db,view):
    jid=st.session_state.get('ui_job');job=next((j for j in view['jobs'] if j['id']==jid),None)
    if job:
        st.button('Volver a mis candidaturas',on_click=clear_job,key='back_applications')
        title(job['title'],job['company']+' · '+job['application'])
        st.caption('Preparar no equivale a enviar. Una declaración manual no acredita recepción externa.')
        if actions_for(cv_approved=view['cv_approved'],preparation_allowed=True,application=job['application'])['open_application']:
            from ..autoapply.interaction_modes import manual_target_url
            try:st.link_button('Abrir formulario oficial para solicitud manual',manual_target_url(job.get('apply_url') or job['url']))
            except ValueError:st.info('El enlace de solicitud necesita revisión antes de abrirse.')
        options=['Resumen','CV','Requisitos','Transporte','Respuestas','Solicitud','Seguimiento','Justificantes']
        if st.session_state.get('ui_job_step') not in options:st.session_state.ui_job_step='Resumen'
        step=st.selectbox('Paso de la candidatura',options,key='ui_job_step')
        if step=='Resumen':
            st.write(job['location_label']+' · '+job['distance_label']+' · '+open_label(job['open_status']))
            st.write('CV: '+('Aprobado' if view['cv_approved'] else 'Pendiente de tu revisión'))
            st.write('Estado: '+job['application'])
            st.write(job['academic_label']);st.caption(job['priority_note'])
            nav_button('Revisar requisitos','Mis candidaturas',job=jid,step='Requisitos',key='application_requirements')
            if job['application'] not in APPLICATION_STATES[3:]:nav_button('Preparar candidatura','Mis candidaturas',job=jid,step='Solicitud' if view['cv_approved'] else 'CV',key='application_prepare',primary=True)
            st.link_button('Abrir oferta original',job['url'])
        elif step=='Seguimiento':
            st.caption('Seguimiento declarado por ti. No autentica al remitente ni acredita recepción externa por sí solo.')
            if not job['has_application']:
                st.info('Registra primero una solicitud real desde Solicitud. Preparar un paquete no significa haberlo presentado.')
            else:
                with st.form('application_followup_'+jid):
                    action=st.selectbox('Resultado que has contrastado',['seguimiento','respuesta recibida','entrevista','rechazada','oferta recibida'])
                    notes=st.text_area('Referencia del mensaje o resumen contrastado, sin datos sensibles')
                    if st.form_submit_button('Guardar seguimiento'):
                        if not notes.strip():st.error('Añade la referencia o el resumen del hecho que has contrastado.')
                        else:
                            db.execute('INSERT INTO user_actions(job_id,action,notes,created_at) VALUES(?,?,?,?)',(jid,action,notes.strip(),now()))
                            st.success('Seguimiento registrado; se conserva el historial de envío.');st.rerun()
                history=db.rows('SELECT action,created_at FROM user_actions WHERE job_id=? ORDER BY id DESC',(jid,))
                if history:st.dataframe(history,hide_index=True,width='stretch',column_config={'action':'Estado declarado','created_at':'Registrado'})
        elif step=='Justificantes':
            from ..autoapply.assisted_ui import render_manual_evidence
            render_manual_evidence(db,job_id=jid)
        elif job['application'] in APPLICATION_STATES[3:] and step in {'Solicitud','CV'}:
            st.info('La candidatura ya está registrada, cerrada o tiene un envío incierto. Se conserva el historial y no se ofrece repetirla.')
            if job['application']==APPLICATION_STATES[3]:nav_button('Adjuntar justificante','Mis candidaturas',job=jid,step='Justificantes',key='application_evidence')
        elif step=='Solicitud' and not view['cv_approved']:
            from ..autoapply.handoff import load_handoff
            valid_package=False
            for existing in db.rows('SELECT id FROM manual_application_handoffs WHERE job_id=? ORDER BY id DESC',(jid,)):
                try:load_handoff(db,existing['id']);valid_package=True;break
                except (ValueError,PermissionError):continue
            if valid_package:
                from ..autoapply.manual_workspace_ui import render_job_workspace
                render_job_workspace(db,jid,step)
            else:
                st.warning('Revisa y aprueba los documentos de esta oferta para preparar el paquete. La aprobación no autoriza envíos.')
                nav_button('Revisar documentos de esta oferta','Mis candidaturas',job=jid,step='CV',key='application_cv_needed',primary=True)
        else:
            from ..autoapply.manual_workspace_ui import render_job_workspace
            render_job_workspace(db,jid,step)
        return
    title('Mis candidaturas','Preparación, seguimiento y justificantes en un solo lugar. Cada paquete se revalida al abrirlo; preparado no significa enviado ni plenamente elegible.')
    academic_summary(db,view)
    selected=st.selectbox('Estado de candidatura',APPLICATION_STATES,key='applications_state')
    rows=[j for j in view['jobs'] if j['application']==selected and (j['has_application'] or j['potential'])]
    st.write(f'**{len(rows)} candidaturas u oportunidades** · {selected}')
    search=st.text_input('Buscar candidatura por empresa o puesto',key='applications_search').casefold()
    rows=[j for j in rows if not search or search in (j['title']+' '+j['company']).casefold()]
    rows.sort(key=lambda j:(j.get('review_priority',0),j.get('deadline_at') or '9999',j['company'],j['title']))
    pages=max(1,math.ceil(len(rows)/8))
    if st.session_state.get('applications_page',1)>pages:st.session_state.applications_page=1
    page=st.number_input('Página de candidaturas',1,pages,key='applications_page')
    if not rows:
        empty('No hay candidaturas en este estado. Selecciona otro estado o elige una oportunidad IT para empezar.')
        nav_button('Consultar ofertas IT','Ofertas de empleo',key='applications_offers')
    for row in rows[(page-1)*8:page*8]:offer_card(row,application=True)


def autoapply(db,view):
    title('AutoApply','Automatización separada del descubrimiento y la preparación local')
    st.warning('LIVE OFF · Los envíos externos están desactivados.')
    st.write('Puedes preparar solicitudes y presentarlas manualmente. La automatización externa requiere un canal permitido y probado, un ensayo real autorizado y una activación de política independiente.')
    for name,description in [('Manual','Tú utilizas la plataforma oficial y registras el resultado.'),('Asistida','Cork Job Radar prepara CV y respuestas verificadas para copiar.'),('Automatización externa','Sin canal operativo acreditado para enviar desde esta instalación.'),('LinkedIn e Indeed','Solo candidatura manual asistida. Sus interfaces no se automatizan.')]:
        with st.container(border=True):st.markdown('**'+name+'**');st.write(description)
    nav_button('Ir a mis candidaturas','Mis candidaturas',key='aa_applications',primary=True)
    nav_button('Revisar política de candidaturas','Perfil y configuración',section='Política de candidaturas',key='aa_policy')
    if db.rows("SELECT id FROM autoapply_interventions WHERE status NOT IN ('PRUEBA_LOCAL_CONFIRMADA','ENVIO_INCIERTO') LIMIT 1"):
        from ..autoapply.interventions_ui import render_interventions
        render_interventions(db)
    if st.checkbox('Mostrar herramientas avanzadas de AutoApply',key='aa_tools'):
        tool=st.selectbox('Herramienta avanzada',['Formularios y ensayo controlado','Compatibilidad de plataformas','Diagnóstico de bloqueos','Contraste documental','Simulación y auditoría histórica'],key='aa_tool')
        if tool=='Formularios y ensayo controlado':
            from ..autoapply.operations_ui import render_operations
            render_operations(db,[j for j in view['jobs'] if j['it_status']=='CONFIRMED_IT'])
        elif tool=='Compatibilidad de plataformas':
            from ..autoapply.manual_ui import render_manual_operations
            render_manual_operations(db,[j for j in view['jobs'] if j['it_status']=='CONFIRMED_IT'])
        elif tool=='Diagnóstico de bloqueos':
            from ..autoapply.assisted_ui import render_assisted_diagnostics
            render_assisted_diagnostics(db)
        elif tool=='Contraste documental':
            from ..autoapply.ui import render_factual_tools
            render_factual_tools(db)
        else:
            from ..autoapply.ui import render_simulation_tools
            render_simulation_tools(db)


def _runtime_command(db,action):
    try:safe_controls(rt.state(db),action);rt.command(db,action)
    except ValueError:st.session_state.ui_runtime_error='El estado cambió o ya hay trabajo activo. Actualiza antes de volver a intentarlo.'


def cancel_search(db,run_id):
    db.execute("UPDATE scan_runs SET cancel_requested=1 WHERE id=? AND status='running' AND cancel_requested=0",(run_id,))


@st.fragment(run_every='5s')
def activity_status(db):
    data=rt.snapshot(db);row=data['control']
    st.markdown('<span class="cjr-status">'+escape(runtime_label(data))+'</span>',unsafe_allow_html=True)
    available=runtime_actions(row,data['supervisor_alive'])
    labels={'START':'Iniciar actividad local','PAUSE':'Pausar actividad','RESUME':'Reanudar actividad','STOP':'Detener actividad'}
    cols=st.columns(max(1,len(available)+1))
    for col,action in zip(cols,available):col.button(labels[action],key='ui_runtime_'+action,on_click=_runtime_command,args=(db,action))
    if row['state'] not in {'STOPPING','PAUSING'}:
        cols[-1].button('Buscar IT ahora',key='ui_runtime_SEARCH_NOW',disabled=bool(row.get('active_kind')),on_click=_runtime_command,args=(db,'SEARCH_NOW'))
    else:
        st.info('Pausa o detención en curso. Se conserva la página o tarea actual antes de terminar.')
    st.write('Última búsqueda: '+date_label(row['last_search_finished'],'Sin búsqueda finalizada'))
    st.write('Próxima búsqueda: '+(date_label(row['next_search_at'],'Al iniciar') if row['desired']=='RUNNING' else 'Programación pausada o detenida'))
    st.caption('Cerrar la pestaña no detiene la actividad. El ordenador no trabaja durante suspensión o apagado.')
    if row['last_error_code']:st.error('La última operación falló. Revisa el diagnóstico en Avanzado; no se han enviado candidaturas.')
    if st.session_state.get('ui_runtime_error'):st.warning(st.session_state.pop('ui_runtime_error'))
    active=db.rows("SELECT id,started_at,cancel_requested FROM scan_runs WHERE status='running' ORDER BY id DESC LIMIT 1")
    if active:
        run=active[0]
        st.info('Búsqueda en curso · Inicio '+date_label(run['started_at']))
        tasks=db.rows('SELECT status,COUNT(*) n FROM task_queue WHERE run_id=? GROUP BY status',(run['id'],))
        total=sum(t['n'] for t in tasks);done=sum(t['n'] for t in tasks if t['status']=='done')
        if total:st.progress(done/total,text=f'{done} de {total} tareas completadas; las pendientes se conservan')
        if run['cancel_requested']:st.caption('Cancelación solicitada: terminando la petición o tarea actual.')
        else:st.button('Cancelar búsqueda en curso',key='cancel_search_'+str(run['id']),on_click=cancel_search,args=(db,run['id']))
    cols=st.columns(2);cols[0].metric('Tareas pendientes de otras búsquedas',sum(r['n'] for r in data['pending_tasks']));cols[1].metric('Recepciones externas confirmadas',data['confirmed_external'])


def activity(db,view):
    title('Actividad y notificaciones','Control de los procesos locales, búsquedas y avisos')
    activity_status(db)
    section=st.selectbox('Ver actividad',['Avisos y próximas acciones','Historial de búsquedas','Fuentes e importación','Cobertura del descubrimiento','Exportar informes','Avanzado'],key='activity_section')
    if section=='Avisos y próximas acciones':
        from ..runtime_ui import NOTICES
        notices=rt.snapshot(db)['notifications']
        if not notices:empty('No hay avisos pendientes. La búsqueda conserva su programación.')
        for n in notices:
            with st.container(border=True):
                st.write(NOTICES.get(n['kind'],'Revisión necesaria en la actividad local.'))
                if n['kind']=='APPROVED_CV_REQUIRED':nav_button('Revisar CV','Perfil y configuración',section='CV definitivo',key='notice_cv_'+str(n['id']))
                elif n['kind']=='HUMAN_VERIFICATION':nav_button('Abrir intervención','AutoApply',key='notice_human_'+str(n['id']))
                elif n.get('job_id'):nav_button('Revisar candidatura','Mis candidaturas',job=n['job_id'],step='Respuestas',key='notice_job_'+str(n['id']))
                if not n.get('acknowledged_at') and st.button('Marcar aviso como leído',key='notice_read_'+str(n['id'])):
                    db.execute('UPDATE local_runtime_notifications SET acknowledged_at=? WHERE id=?',(now(),n['id']));st.rerun()
                elif n.get('acknowledged_at'):st.caption('Leído · La causa sigue pendiente de resolución.')
        if db.rows("SELECT id FROM autoapply_interventions WHERE status NOT IN ('PRUEBA_LOCAL_CONFIRMADA','ENVIO_INCIERTO') LIMIT 1"):
            from ..autoapply.interventions_ui import render_interventions
            render_interventions(db)
    elif section=='Historial de búsquedas':
        rows=db.rows('SELECT started_at,finished_at,status,message FROM scan_runs ORDER BY id DESC LIMIT 100')
        if rows:st.dataframe(rows,column_config={'started_at':'Inicio','finished_at':'Fin','status':'Estado','message':'Resultado'},hide_index=True,width='stretch')
        else:empty('Todavía no se ha realizado ninguna búsqueda.')
        interrupted=db.rows("SELECT id,started_at,status FROM scan_runs WHERE status IN ('partial','cancelled','failed','interrupted') ORDER BY id DESC")
        if interrupted:
            chosen=st.selectbox('Búsqueda interrumpida para reanudar',[r['id'] for r in interrupted],format_func=lambda k:next(date_label(r['started_at'])+' · '+r['status'] for r in interrupted if r['id']==k))
            busy=bool(db.rows("SELECT id FROM scan_runs WHERE status='running' LIMIT 1")) or bool(rt.state(db).get('active_kind'))
            if st.button('Reanudar búsqueda interrumpida',disabled=busy):
                try:
                    from ..worker import prepare_resume,spawn_worker
                    prepare_resume(db,chosen);spawn_worker(chosen);st.success('Búsqueda reanudada; se conservan los resultados anteriores.')
                except Exception:st.error('No se reanudó: comprueba el trabajador activo, sus recursos y el estado guardado.')
    elif section in {'Fuentes e importación','Cobertura del descubrimiento','Exportar informes'}:
        from ..ui_legacy import render_legacy
        render_legacy(db,{'Fuentes e importación':'sources','Cobertura del descubrimiento':'coverage','Exportar informes':'history'}[section])
    else:
        tool=st.selectbox('Diagnóstico local',['Supervisor y tareas','Operaciones de mantenimiento','Instalación y dependencias'],key='activity_tool')
        if tool=='Supervisor y tareas':
            data=rt.snapshot(db);st.json(data['control'])
            for label,rows in [('Eventos del supervisor',data['events']),('Tareas pendientes',data['pending_tasks']),('Cola de preparación',data['queue'])]:
                st.subheader(label)
                if rows:st.dataframe(rows,hide_index=True,width='stretch')
                else:st.caption('Sin registros.')
        elif tool=='Instalación y dependencias':
            if st.button('Comprobar instalación'):
                from ..cli import doctor
                st.json(doctor(db))
        else:
            from ..worker import create_run,spawn_worker
            kind=st.selectbox('Operación',['Reanalizar pendientes','Reverificar vigencia','Actualizar fuentes','Buscar catálogo completo'])
            busy=bool(db.rows("SELECT id FROM scan_runs WHERE status='running' LIMIT 1")) or bool(rt.state(db).get('active_kind'))
            if st.button('Ejecutar operación seleccionada',disabled=busy):
                try:
                    r=create_run(db,kind={'Reanalizar pendientes':'analyze','Reverificar vigencia':'verify','Actualizar fuentes':'health','Buscar catálogo completo':'scan'}[kind])
                    if kind=='Actualizar fuentes':
                        from ..worker import enqueue
                        enqueue(db,r,None,None,'health')
                    spawn_worker(r);st.success('Operación iniciada; puedes seguir utilizando la aplicación.')
                except Exception:st.error('No se pudo iniciar la operación. Comprueba el trabajador activo y las fuentes.')


def profile(db,view):
    title('Perfil y configuración','Tus datos y autorizaciones se conservan localmente y cifrados')
    options=['CV definitivo','Datos y experiencia aprobados','Preferencias IT y ubicación','Frecuencia y notificaciones','Política de candidaturas','Privacidad','Sistema avanzado']
    if st.session_state.get('ui_profile_section') not in options:st.session_state.ui_profile_section='CV definitivo'
    section=st.selectbox('Sección de configuración',options,key='ui_profile_section')
    if section=='CV definitivo':
        st.info('Aprobar el CV confirma únicamente esta versión del documento. No activa AutoApply ni autoriza envíos.')
        from ..autoapply.manual_workspace_ui import _cv
        from ..autoapply.vault import candidate_snapshot
        _cv(db,None,candidate_snapshot(db),expanded=True)
        if st.checkbox('Opciones de documento: DOCX, importar CV o carta',key='profile_cv_import'):
            from ..autoapply.ui import render_cv_editor
            render_cv_editor(db)
        st.info('Para adaptar documentos a una vacante: Mis candidaturas → selecciona oferta → CV. La revisión por oferta no aprueba el CV general.')
        with st.expander('Biblioteca de referencias y originales'):
            from ..autoapply.job_documents_ui import render_references
            render_references(db)
    elif section=='Datos y experiencia aprobados':
        st.write(f"{view['approved_facts']} datos y afirmaciones aprobados se conservan. Solo añade o corrige información que haya cambiado.")
        with st.expander('Expediente estructurado y campos pendientes'):
            from ..autoapply.professional_dossier import build_dossier
            from ..autoapply.vault import candidate_snapshot
            dossier=build_dossier(candidate_snapshot(db))
            st.caption('Representación derivada de tus hechos vigentes. No importa proyectos, tareas ni fechas nuevas por suposición.')
            st.dataframe([{'Tipo':e['kind'],'Hecho aprobado':e['approved_text'],
                           'Campos pendientes':', '.join(e['review_pending'])} for e in dossier['entries']],hide_index=True)
        if st.checkbox('Mostrar mis datos privados y editar la ficha',key='profile_private'):
            from ..autoapply.ui import render_profile_editor
            render_profile_editor(db)
        else:st.caption('Contacto, LinkedIn, experiencia, estudios e idiomas permanecen ocultos hasta que los abras aquí o prepares una candidatura.')
    elif section=='Preferencias IT y ubicación':
        st.write('Funciones IT o relacionadas con DAM · Ballinlough · 50 km · Mínimo obligatorio solicitado de hasta 3 años.')
        st.write('No se descarta por requisitos deseables. Sin coche propio; bicicleta y transporte público. Remotos separados.')
        from ..autoapply.selection_ui import render_selection_controls
        render_selection_controls(db)
        st.caption('Los trayectos y horarios se comprueban en la ficha de cada candidatura, paso Transporte.')
    elif section=='Frecuencia y notificaciones':
        row=rt.state(db)
        with st.form('ui_frequency'):
            hours=st.number_input('Horas entre búsquedas IT',.25,168.,float(row['interval_hours']),step=.25)
            prepare=st.checkbox('Preparar candidaturas razonables con CV aprobado',value=bool(row['auto_prepare']))
            sound=st.checkbox('Aviso sonoro local',value=bool(row['sound']))
            if st.form_submit_button('Guardar frecuencia y avisos'):
                try:rt.configure(db,hours,prepare,sound);st.success('Configuración guardada. LIVE sigue OFF.')
                except ValueError:st.error('Indica un intervalo entre 0,25 y 168 horas.')
        with st.expander('Inicio opcional al entrar en Windows'):
            from ..runtime_ui import startup_script
            st.write('No instalado por la aplicación. Descargar el archivo no lo activa. Solo si tú lo decides, cópialo a Inicio con Win+R → shell:startup. No se instala ningún servicio ni tarea.')
            st.download_button('Descargar lanzador opcional de inicio',startup_script(),file_name='CorkJobRadar-inicio-opcional.vbs')
    elif section=='Política de candidaturas':
        from ..autoapply.policy import current_policy
        from ..autoapply.policy_ui import render_policy_editor
        st.warning('Solo simulación. Autorizar esta política no activa LIVE ni sustituye el ensayo externo autorizado.')
        render_policy_editor(db,current_policy(db)[2])
    elif section=='Privacidad':
        from ..autoapply.ui import render_privacy
        render_privacy(db)
    else:
        from ..ui_legacy import render_legacy
        jobs={j['id']:j for j in view['jobs']}
        chosen=st.selectbox('Oferta para herramientas de transporte',list(jobs),format_func=lambda k:jobs[k]['title']+' · '+jobs[k]['company']) if jobs else None
        render_legacy(db,'profile',chosen)
