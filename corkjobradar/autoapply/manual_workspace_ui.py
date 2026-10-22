"""One assisted desk using the existing CV, handoff and manual receipt services."""
from urllib.parse import urlsplit
from urllib.parse import urlencode
import streamlit as st
from ..config import load_profile
from .documents import render_cv,create_cv_review,cv_review_bytes,approve_cv_review,document_bytes
from .handoff import prepare_handoff,load_handoff,handoff_download,declare_manual_submission
from .interaction_modes import manual_target_url
from .manual_workspace import manual_inventory,assess_manual_job,factual_introduction,save_manual_transport
from .manual_requirements import review_requirement
from .vault import candidate_snapshot


def _copy(label,value):
    st.text(label+' · botón de copiar a la derecha')
    st.code(str(value),language=None,wrap_lines=True)


def _cv(db,job,candidate,expanded=None):
    if candidate.get('cv_document_id'):st.success('CV definitivo aprobado · La aprobación no autoriza envíos.')
    with st.expander('1. Revisar y aprobar mi CV definitivo',expanded=not candidate.get('cv_document_id') if expanded is None else expanded):
        st.caption('Se reutilizan los hechos aprobados y el control de versiones. Aprobar el documento no autoriza envíos. La adaptación solo ordena afirmaciones existentes.')
        specific=bool(job and job['it_status']=='CONFIRMED_IT')
        if st.button('Preparar CV para este puesto y revisar' if specific else 'Preparar CV general con mis hechos para revisar',key='mw_prepare_cv'):
            try:
                selected=db.rows('SELECT * FROM jobs WHERE id=?',(job['job_id'],))[0] if specific else None
                st.session_state['mw_cv_id']=create_cv_review(db,render_cv(candidate_snapshot(db),'pdf',selected),'pdf')
            except Exception:st.error('No se pudo preparar el CV. Revisa hechos aprobados, funciones IT y formato.')
        versions=db.rows("SELECT id,approved_at FROM candidate_documents WHERE kind='CV' AND facts_hash=? AND revoked_at IS NULL ORDER BY id DESC",(candidate['_cv_facts_hash'],))
        if not versions:st.info('Prepara una versión para poder revisarla.');return
        ids=[r['id'] for r in versions];preferred=st.session_state.get('mw_cv_id')
        did=st.selectbox('CV definitivo para esta candidatura',ids,index=ids.index(preferred) if preferred in ids else 0,
                         format_func=lambda i:'Versión '+str(i)+(' · aprobada' if next(r['approved_at'] for r in versions if r['id']==i) else ' · pendiente'),key='mw_cv_version')
        try:
            content,ext,sha,text=cv_review_bytes(db,did)
            st.text(text)
            with st.expander('Avanzado: integridad del documento'):st.caption('SHA-256: '+sha)
            st.download_button('Descargar esta versión para revisar',content,file_name='CV-para-revisar.'+ext,key='mw_review_download')
            if next(r['approved_at'] for r in versions if r['id']==did):
                approved,approved_ext,_=document_bytes(db,did)
                st.download_button('Descargar CV definitivo aprobado',approved,file_name='CV.'+approved_ext,key='mw_approved_cv_download')
                st.caption('La aprobación de este CV no certifica los requisitos ni la accesibilidad de la oferta seleccionada.')
                return
            consent=st.checkbox('He revisado íntegramente esta versión y apruebo este CV definitivo',key='mw_cv_consent_'+str(did)+'_'+sha)
            if st.button('Aprobar esta versión del CV',disabled=not consent,key='mw_approve_cv'):
                approve_cv_review(db,did,sha,candidate['_facts_hash'],confirmed=consent);st.success('CV aprobado por ti. LIVE sigue OFF.');st.rerun()
        except Exception:st.info('Versión retenida por cambio de datos o integridad; genera y revisa una nueva.')


def render_manual_workspace(db):
    st.subheader('Candidaturas IT asistidas')
    st.caption('Selecciona una vacante y prepara su solicitud manual. No requiere permisos API empresariales ni política automática. LIVE OFF.')
    with st.expander('Descubrir más ofertas IT junior y canales oficiales'):
        from ..junior_discovery import ROLE_QUERIES,start_junior_search,manual_channels
        role=st.selectbox('Familia IT para búsqueda manual oficial',ROLE_QUERIES,key='mw_role_query')
        st.link_button('Buscar en LinkedIn con sus funciones oficiales','https://www.linkedin.com/jobs/search/?'+urlencode({'keywords':role,'location':'Cork, County Cork, Ireland'}))
        st.link_button('Buscar en Indeed con sus funciones oficiales','https://ie.indeed.com/jobs?'+urlencode({'q':role,'l':'Cork, County Cork'}))
        st.caption('Los enlaces los abres tú; Cork Job Radar no automatiza esas interfaces. Actualizar las fuentes consulta sus listados públicos completos, sin detenerse al encontrar buenos puestos.')
        for channel in manual_channels():
            st.link_button('Abrir canal manual: '+channel['name'],channel['url'])
            st.caption(channel['status']+' · '+channel['note'])
        active=db.rows("SELECT id FROM scan_runs WHERE status='running'")
        if active:st.info('Búsqueda existente en ejecución: '+str(active[0]['id']))
        if st.button('Buscar nuevas ofertas en fuentes IT revisadas',disabled=bool(active),key='mw_discover'):
            try:st.session_state['mw_discovery']=start_junior_search(db);st.success('Búsqueda persistente iniciada; las ofertas conservarán su análisis o estado pendiente.')
            except Exception:st.error('No se inició otra búsqueda. Comprueba la ejecución activa o la configuración de fuentes.')
        runs=db.rows('''SELECT DISTINCT r.id,r.status,r.started_at,r.finished_at FROM scan_runs r JOIN source_runs s ON s.run_id=r.id
                        WHERE s.source_id LIKE 'junior_%' ORDER BY r.id DESC''')
        if runs:st.dataframe(runs,hide_index=True)
    from .selection_ui import render_selection_controls,assisted_inventory,render_worksite,reason_text
    from .broad_selection import assess_selection,STATES
    render_selection_controls(db)
    candidate=candidate_snapshot(db);inventory=assisted_inventory(db)
    st.write('Registros examinados:',inventory['jobs_processed'],'· IT o relacionados para revisar:',inventory['it_or_related_reviewed'])
    st.write('Todos los estados de candidatura asistida:',inventory['states'])
    import json
    st.download_button('Descargar evaluación completa IT 50 km (JSON)',json.dumps(inventory['selection_report'],ensure_ascii=False,indent=2).encode('utf-8'),
                       file_name='Cork-IT-50km-evaluacion.json',mime='application/json',key='it50_download_inventory')
    st.caption('La selección profesional es independiente de permisos y adaptadores. La experiencia real no cambia. Transporte pendiente y dudas menores advierten; centro geográfico, preguntas esenciales y CV pendientes requieren intervención.')
    offers=inventory['offers'];states=STATES
    if 'mw_states' in st.session_state and any(s not in states for s in st.session_state['mw_states']):del st.session_state['mw_states']
    chosen_states=st.multiselect('Estado para candidatura asistida',states,default=['ENVIABLE','ENVIABLE_CON_ADVERTENCIAS','INTERVENCION_REQUERIDA'],key='mw_states')
    remotes=st.checkbox('Mostrar también remotos separados (no autoriza incluirlos)',key='it50_show_remotes')
    needle=st.text_input('Buscar puesto o empresa IT',key='mw_search').casefold().strip()
    visible=[r for r in offers if r['state'] in chosen_states and (remotes or r['selection']['geography']['state']!='REMOTE_SEPARATE') and (not needle or needle in (r['title']+' '+r['company']).casefold())]
    st.dataframe([{k:r[k] for k in ('title','company','location','state','open_confirmed','fulfilled','unmet_mandatory','pending_mandatory','transport_verified','cv_approved')} for r in visible],hide_index=True)
    if not visible:
        st.info('No hay ofertas con esos filtros. Consulta otros estados o amplía el descubrimiento.')
        _cv(db,None,candidate)
        return
    jid=st.selectbox('Elegir candidatura IT asistida',[r['job_id'] for r in visible],format_func=lambda key:next(r['title']+' · '+r['company'] for r in visible if r['job_id']==key),key='mw_job')
    row=db.rows('SELECT * FROM jobs WHERE id=?',(jid,))[0];job=assess_manual_job(db,row,candidate);selected=assess_selection(db,row,candidate)
    job['state']=selected['state'];job['reasons']=[reason_text(code) for code in selected['exclusions']+selected['essential_pending']+selected['operational_pending']]
    job['manual_package_possible']=selected['preparation_allowed'] and selected['cv_approved']
    st.text(job['company']+' · '+job['title']);st.write('Estado:',job['state'])
    st.write('Selección profesional:',selected['professional_state'],'· Canal:',selected['interaction_mode'])
    if selected['warnings']:st.warning('Advertencias; no equivalen a rechazo: '+' '.join(reason_text(code) for code in selected['warnings']))
    if selected['experience']:st.dataframe(selected['experience'],hide_index=True)
    render_worksite(db,row,selected)
    try:st.link_button('Abrir anuncio oficial y solicitar manualmente',manual_target_url(row.get('apply_url') or row['url']))
    except ValueError:st.info('Enlace pendiente de revisión; no abrir automáticamente.')
    if st.button('Comprobar vigencia del anuncio sin enviar',key='mw_verify'):
        from ..http import WebClient
        from ..verification import verify_job
        with WebClient(load_profile(),db) as client:verify_job(db,jid,client)
        st.rerun()
    st.caption('Última verificación: '+str(job['last_verified_at'])+' · '+job['source_open_status']+' · Fecha límite: '+job['deadline'])
    with st.expander('Anuncio original y funciones IT',expanded=False):
        st.text(row['description']);st.write('Clasificación de funciones:',job['it_status'])
    _cv(db,job,candidate)
    with st.expander('2. Requisitos cumplidos, no cumplidos y pendientes',expanded=True):
        requirements=job['requirements']
        st.dataframe([{k:r[k] for k in ('quote','level','status','reason','fact_ids')} for r in requirements],hide_index=True)
        if requirements and job['it_status']=='CONFIRMED_IT':
            rid=st.selectbox('Requisito que has contrastado',[r['id'] for r in requirements],format_func=lambda i:next(r['quote'] for r in requirements if r['id']==i),key='mw_requirement_'+jid)
            facts={**{v:k for k,v in candidate['_fact_ids'].items()},**{c['id']:c['section']+': '+c['text_en'] for c in candidate['_claims']}}
            status=st.selectbox('Resultado del contraste',['PENDIENTE','CUMPLIDO','NO_CUMPLIDO'],key='mw_result_'+rid)
            ids=st.multiselect('Hechos ya aprobados que respaldan el resultado',list(facts),format_func=lambda k:str(k)+' · '+facts[k],key='mw_fact_ids_'+rid)
            acknowledged=st.checkbox('He contrastado esta frase del anuncio con esos hechos; no autorizo ningún envío',key='mw_check_'+jid+'_'+rid)
            if st.button('Guardar contraste de este requisito',disabled=not acknowledged,key='mw_save_requirement'):
                try:review_requirement(db,jid,rid,status,ids,row['content_hash'],candidate['_facts_hash'],confirmed=acknowledged);st.rerun()
                except (ValueError,PermissionError):st.error('Se necesitan hechos aprobados para CUMPLIDO y versiones vigentes del anuncio y perfil.')
    with st.expander('3. Accesibilidad y horario',expanded=not job['transport_verified']):
        st.write('Origen: Ballinlough · Sin coche propio · Bicicleta y transporte público')
        st.write('Trayecto/horario:', 'VERIFICADOS' if job['transport_verified'] else 'ADVERTENCIA: PENDIENTES; no descarta por sí sola la candidatura')
        st.write('Horario documentado:',job['schedule'] or 'No verificado','· Inicio:',job['shift_start'] or 'desconocido','· Fin:',job['shift_end'] or 'desconocido')
        if job['route_details']:st.dataframe(job['route_details'],hide_index=True)
        st.link_button('Consultar trayecto, accesos y avisos en TFI','https://www.transportforireland.ie/plan-a-journey/')
        st.caption('Esta vía manual permite registrar una comprobación sin política ni autorizaciones API. Los horarios o trayectos no se adivinan. Remoto exige comprobar por separado permiso desde Irlanda y presencialidad.')
        if job['it_status']=='CONFIRMED_IT' and row['mode']!='REMOTE':
            with st.form('mw_transport_'+jid):
                mode=st.selectbox('Medio sin coche',['bicycle','bus'])
                destination=st.text_input('Centro exacto de trabajo que has confirmado')
                days=st.multiselect('Días de trabajo confirmados',['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'])
                start=st.time_input('Hora de entrada confirmada',value=None)
                end=st.time_input('Hora de salida confirmada',value=None)
                overnight=st.checkbox('La salida corresponde al día siguiente')
                evidence=st.text_input('URL pública de evidencia del trayecto')
                access=st.text_input('Acceso comprobado desde Ballinlough; no incluyas domicilio privado')
                outbound=st.text_input('Ida comprobada: bicicleta o línea directa, paradas y horarios')
                back=st.text_input('Vuelta comprobada: bicicleta o línea directa, paradas y horarios')
                duration=st.number_input('Máximo de minutos comprobado por trayecto completo',min_value=1,value=None,step=1)
                valid=st.date_input('Comprobación válida hasta',value=None)
                verified=st.checkbox('He comprobado centro, turno, todos los días, accesos e ida/vuelta sin coche; autobús sin transbordos')
                if st.form_submit_button('Guardar mi comprobación para candidatura manual'):
                    try:
                        if start is None or end is None or valid is None:raise ValueError('MISSING_SHIFT')
                        save_manual_transport(db,jid,mode,evidence,{'destination':destination,'days':days,'shift_start':start.isoformat(timespec='minutes'),
                            'shift_end':end.isoformat(timespec='minutes'),'overnight':overnight,'origin_access':access,'outbound':outbound,'return':back,
                            'duration_minutes':duration,'valid_until':valid.isoformat(),'shift_compatible':verified},row['content_hash'],confirmed=verified)
                        st.success('Comprobación factual conservada; no autoriza envíos.');st.rerun()
                    except Exception:st.error('Faltan datos contrastados, vigencia o compatibilidad del trayecto. Se conserva HOLD.')
    with st.expander('4. Contactos y respuestas para copiar',expanded=True):
        from .forms import load_inspection,answer_plan,inspect_job_form,inspection_route
        from .platforms import platform_for
        inspection=None;inspection_id=None
        for existing in db.rows('SELECT id FROM autoapply_form_inspections WHERE job_id=? ORDER BY id DESC',(jid,)):
            try:inspection=load_inspection(db,existing['id']);inspection_id=existing['id'];break
            except (ValueError,PermissionError):continue
        try:can_inspect=inspection_route(db,row)['cap'].get('inspection_supported')
        except ValueError:can_inspect=False
        if can_inspect and job['it_status']=='CONFIRMED_IT':
            if st.button('Actualizar preguntas públicas para esta solicitud',key='mw_inspect'):
                try:
                    from ..http import WebClient
                    with WebClient(load_profile(),db) as client:inspect_job_form(db,jid,client)
                    st.rerun()
                except Exception:st.info('No se pudieron comprobar las preguntas públicas; revisarlas manualmente en el destino.')
        if inspection:
            plan=answer_plan(inspection,candidate)
            for field in inspection['fields']:
                answer=plan['mapping'].get(field['id'])
                if answer and 'value' in answer:_copy(field['label'],answer['value'])
            unanswered=[{'pregunta':f['label'],'obligatoria':f['required'],'estado':'PENDIENTE' if f['required'] else 'OPCIONAL_SIN_RESPUESTA_APROBADA'} for f in inspection['fields'] if f['id'] not in plan['mapping']]
            if unanswered:
                st.caption('Preguntas del formulario por resolver (incluye opcionales)')
                st.dataframe(unanswered,hide_index=True)
        else:st.info('Preguntas del formulario pendientes de comprobar en el sitio oficial. No se marca la solicitud como completa por tener contactos y CV.')
        for key,label in [('full_name','Nombre'),('email','Email'),('phone','Teléfono'),('linkedin_url','LinkedIn'),('location','Ubicación')]:
            if candidate.get(key):_copy(label,candidate[key])
        host=urlsplit(row.get('apply_url') or row['url']).hostname
        exact=[a for a in candidate['_answers'] if a['host']==host]
        for answer in exact:_copy('Respuesta aprobada para la pregunta exacta: '+answer['question'],answer['answer'])
        for claim in candidate['_claims']:
            _copy('Hecho profesional aprobado · '+claim['section'],claim['text_en'])
        if job['it_status']=='CONFIRMED_IT' and candidate.get('_claims') and candidate.get('full_name'):
            _copy('Presentación factual para tu revisión; no responde a preguntas técnicas o de motivación específicas',factual_introduction(candidate,row))
        st.caption('Los hechos de arriba son material verificado, no respuestas universales. No transformar formación en título/certificación ni responder patrocinio futuro o preguntas nuevas por suposición.')
        if not exact:st.info('No hay plantillas de preguntas exactas para este dominio. El paquete incluirá los datos reconocidos por una inspección vigente; las demás preguntas seguirán pendientes.')
    with st.expander('5. Paquete, declaración manual y justificante',expanded=True):
        if job['reasons']:st.write('Pendientes de candidatura:',job['reasons'])
        if st.button('Preparar solicitud manual con mi CV aprobado',disabled=not job['manual_package_possible'],key='mw_prepare_package'):
            try:
                result=prepare_handoff(db,jid,inspection_id);st.session_state['mw_package_'+jid]=result['handoff_id']
                st.success('Paquete preparado. Abre el enlace oficial, completa y revisa el formulario por ti mismo.')
            except Exception:st.error('Preparación retenida. Revisa CV aprobado, funciones IT, cambios o solicitud previa.')
        packages=db.rows('SELECT id FROM manual_application_handoffs WHERE job_id=? ORDER BY id DESC',(jid,))
        if packages:
            hid=st.selectbox('Solicitud manual preparada',[p['id'] for p in packages],key='mw_package_id_'+jid)
            try:
                packet=load_handoff(db,hid)
                st.download_button('Descargar CV y solicitud manual',handoff_download(db,hid),file_name='Candidatura-IT.zip',mime='application/zip',key='mw_package_download')
                cv,ext,_=document_bytes(db,packet['document_id']);st.download_button('Descargar solo CV aprobado',cv,file_name='CV.'+ext,key='mw_cv_download')
            except Exception:st.info('Paquete caducado/cambiado o candidatura ya registrada. No reutilizar para un segundo envío.')
            declared=st.checkbox('Confirmo que ya presenté esta solicitud manualmente; registrar para evitar duplicados',key='mw_declared_'+jid+'_'+str(hid))
            if st.button('Registrar candidatura presentada por mí',disabled=not declared,key='mw_declare'):
                try:declare_manual_submission(db,hid,declared);st.success('Declaración registrada. Adjunta el justificante en la sección existente.');st.rerun()
                except Exception:st.error('No se puede registrar: duplicado, historial incierto o paquete inválido.')
        st.caption('Los justificantes EML/PDF se conservan cifrados en «Justificantes de candidaturas manuales». Declarar o aportar un archivo no autentica una recepción externa.')


def render_job_workspace(db,jid,step):
    from .selection_ui import render_worksite,reason_text
    from .broad_selection import assess_selection
    candidate=candidate_snapshot(db)
    row=db.rows('SELECT * FROM jobs WHERE id=?',(jid,))[0];job=assess_manual_job(db,row,candidate);selected=assess_selection(db,row,candidate)
    job['state']=selected['state'];job['reasons']=[reason_text(code) for code in selected['exclusions']+selected['essential_pending']+selected['operational_pending']]
    job['manual_package_possible']=selected['preparation_allowed'] and selected['cv_approved']
    if step=='CV':
        _cv(db,job,candidate,expanded=True)
        return
    inspection_id=None
    if step=='Requisitos':
        requirements=job['requirements']
        if requirements:
            st.dataframe([{k:r[k] for k in ('quote','level','status','reason')} for r in requirements],hide_index=True,width='stretch',column_config={'quote':'Requisito publicado','level':'Obligatorio o deseable','status':'Comparación con tu perfil','reason':'Motivo'})
        else:st.info('Faltan requisitos por extraer. Revisa el texto original; no significa que el puesto carezca de requisitos.')
        if requirements and job['it_status']=='CONFIRMED_IT':
            rid=st.selectbox('Requisito que has contrastado',[r['id'] for r in requirements],format_func=lambda i:next(r['quote'] for r in requirements if r['id']==i),key='mw_requirement_'+jid)
            facts={**{v:k for k,v in candidate['_fact_ids'].items()},**{c['id']:c['section']+': '+c['text_en'] for c in candidate['_claims']}}
            status=st.selectbox('Resultado del contraste',['PENDIENTE','CUMPLIDO','NO_CUMPLIDO'],key='mw_result_'+rid)
            ids=st.multiselect('Hechos ya aprobados que respaldan el resultado',list(facts),format_func=lambda k:str(k)+' · '+facts[k],key='mw_fact_ids_'+rid)
            acknowledged=st.checkbox('He contrastado esta frase del anuncio con esos hechos; no autorizo ningún envío',key='mw_check_'+jid+'_'+rid)
            if st.button('Guardar contraste de este requisito',disabled=not acknowledged,key='mw_save_requirement'):
                try:review_requirement(db,jid,rid,status,ids,row['content_hash'],candidate['_facts_hash'],confirmed=acknowledged);st.rerun()
                except (ValueError,PermissionError):st.error('Se necesitan hechos aprobados para CUMPLIDO y versiones vigentes del anuncio y perfil.')
    if step=='Transporte':
        render_worksite(db,row,selected)
        st.write('Origen: Ballinlough · Sin coche propio · Bicicleta y transporte público')
        st.write('Trayecto/horario:', 'VERIFICADOS' if job['transport_verified'] else 'ADVERTENCIA: PENDIENTES; no descarta por sí sola la candidatura')
        st.write('Horario documentado:',job['schedule'] or 'No verificado','· Inicio:',job['shift_start'] or 'desconocido','· Fin:',job['shift_end'] or 'desconocido')
        if job['route_details']:st.dataframe(job['route_details'],hide_index=True)
        st.link_button('Consultar trayecto, accesos y avisos en TFI','https://www.transportforireland.ie/plan-a-journey/')
        st.caption('Esta vía manual permite registrar una comprobación sin política ni autorizaciones API. Los horarios o trayectos no se adivinan. Remoto exige comprobar por separado permiso desde Irlanda y presencialidad.')
        if job['it_status']=='CONFIRMED_IT' and row['mode']!='REMOTE':
            with st.form('mw_transport_'+jid):
                mode=st.selectbox('Medio sin coche',['bicycle','bus'])
                destination=st.text_input('Centro exacto de trabajo que has confirmado')
                days=st.multiselect('Días de trabajo confirmados',['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'])
                start=st.time_input('Hora de entrada confirmada',value=None)
                end=st.time_input('Hora de salida confirmada',value=None)
                overnight=st.checkbox('La salida corresponde al día siguiente')
                evidence=st.text_input('URL pública de evidencia del trayecto')
                access=st.text_input('Acceso comprobado desde Ballinlough; no incluyas domicilio privado')
                outbound=st.text_input('Ida comprobada: bicicleta o línea directa, paradas y horarios')
                back=st.text_input('Vuelta comprobada: bicicleta o línea directa, paradas y horarios')
                duration=st.number_input('Máximo de minutos comprobado por trayecto completo',min_value=1,value=None,step=1)
                valid=st.date_input('Comprobación válida hasta',value=None)
                verified=st.checkbox('He comprobado centro, turno, todos los días, accesos e ida/vuelta sin coche; autobús sin transbordos')
                if st.form_submit_button('Guardar mi comprobación para candidatura manual'):
                    try:
                        if start is None or end is None or valid is None:raise ValueError('MISSING_SHIFT')
                        save_manual_transport(db,jid,mode,evidence,{'destination':destination,'days':days,'shift_start':start.isoformat(timespec='minutes'),
                            'shift_end':end.isoformat(timespec='minutes'),'overnight':overnight,'origin_access':access,'outbound':outbound,'return':back,
                            'duration_minutes':duration,'valid_until':valid.isoformat(),'shift_compatible':verified},row['content_hash'],confirmed=verified)
                        st.success('Comprobación factual conservada; no autoriza envíos.');st.rerun()
                    except Exception:st.error('Faltan datos contrastados, vigencia o compatibilidad del trayecto. Se conserva HOLD.')
    if step=='Respuestas':
        from .forms import load_inspection,answer_plan,inspect_job_form,inspection_route
        from .platforms import platform_for
        inspection=None;inspection_id=None
        for existing in db.rows('SELECT id FROM autoapply_form_inspections WHERE job_id=? ORDER BY id DESC',(jid,)):
            try:inspection=load_inspection(db,existing['id']);inspection_id=existing['id'];break
            except (ValueError,PermissionError):continue
        try:can_inspect=inspection_route(db,row)['cap'].get('inspection_supported')
        except ValueError:can_inspect=False
        if can_inspect and job['it_status']=='CONFIRMED_IT':
            if st.button('Actualizar preguntas públicas para esta solicitud',key='mw_inspect'):
                try:
                    from ..http import WebClient
                    with WebClient(load_profile(),db) as client:inspect_job_form(db,jid,client)
                    st.rerun()
                except Exception:st.info('No se pudieron comprobar las preguntas públicas; revisarlas manualmente en el destino.')
        if inspection:
            plan=answer_plan(inspection,candidate)
            for field in inspection['fields']:
                answer=plan['mapping'].get(field['id'])
                if answer and 'value' in answer:_copy(field['label'],answer['value'])
            unanswered=[{'pregunta':f['label'],'obligatoria':f['required'],'estado':'PENDIENTE' if f['required'] else 'OPCIONAL_SIN_RESPUESTA_APROBADA'} for f in inspection['fields'] if f['id'] not in plan['mapping']]
            if unanswered:
                st.caption('Preguntas del formulario por resolver (incluye opcionales)')
                st.dataframe(unanswered,hide_index=True)
        else:st.info('Preguntas del formulario pendientes de comprobar en el sitio oficial. No se marca la solicitud como completa por tener contactos y CV.')
        for key,label in [('full_name','Nombre'),('email','Email'),('phone','Teléfono'),('linkedin_url','LinkedIn'),('location','Ubicación')]:
            if candidate.get(key):_copy(label,candidate[key])
        host=urlsplit(row.get('apply_url') or row['url']).hostname
        exact=[a for a in candidate['_answers'] if a['host']==host]
        for answer in exact:_copy('Respuesta aprobada para la pregunta exacta: '+answer['question'],answer['answer'])
        if candidate['_claims']:
            with st.expander('Otros hechos profesionales aprobados para copiar'):
                claims={str(c['id']):c for c in candidate['_claims']}
                cid=st.selectbox('Hecho profesional',list(claims),format_func=lambda k:claims[k]['section']+' - '+claims[k]['text_en'][:85],key='new_claim_copy_'+jid)
                _copy(claims[cid]['section'],claims[cid]['text_en'])
        if job['it_status']=='CONFIRMED_IT' and candidate.get('_claims') and candidate.get('full_name'):
            _copy('Presentación factual para tu revisión; no responde a preguntas técnicas o de motivación específicas',factual_introduction(candidate,row))
        st.caption('Los hechos de arriba son material verificado, no respuestas universales. No transformar formación en título/certificación ni responder patrocinio futuro o preguntas nuevas por suposición.')
        if not exact:st.info('No hay plantillas de preguntas exactas para este dominio. El paquete incluirá los datos reconocidos por una inspección vigente; las demás preguntas seguirán pendientes.')
    if step=='Solicitud':
        if not selected['preparation_allowed']:
            st.warning('Preparación retenida: '+' '.join(job['reasons']))
            return
        from .forms import load_inspection
        for entry in db.rows('SELECT id FROM autoapply_form_inspections WHERE job_id=? ORDER BY id DESC',(jid,)):
            try:load_inspection(db,entry['id']);inspection_id=entry['id'];break
            except (ValueError,PermissionError):continue
        if job['reasons']:st.write('Pendientes de candidatura:',job['reasons'])
        current_packages=db.rows('SELECT id FROM manual_application_handoffs WHERE job_id=? ORDER BY id DESC',(jid,))
        reusable=False
        for package in current_packages:
            try:load_handoff(db,package['id']);reusable=True;break
            except (ValueError,PermissionError):continue
        if not reusable and st.button('Preparar solicitud manual con mi CV aprobado',disabled=not job['manual_package_possible'],key='mw_prepare_package'):
            try:
                result=prepare_handoff(db,jid,inspection_id);st.session_state['mw_package_'+jid]=result['handoff_id']
                st.success('Paquete preparado. Abre el enlace oficial, completa y revisa el formulario por ti mismo.')
            except Exception:st.error('Preparación retenida. Revisa CV aprobado, funciones IT, cambios o solicitud previa.')
        packages=db.rows('SELECT id FROM manual_application_handoffs WHERE job_id=? ORDER BY id DESC',(jid,))
        if packages:
            hid=st.selectbox('Solicitud manual preparada',[p['id'] for p in packages],key='mw_package_id_'+jid)
            try:
                packet=load_handoff(db,hid)
                st.download_button('Descargar CV y solicitud manual',handoff_download(db,hid),file_name='Candidatura-IT.zip',mime='application/zip',key='mw_package_download')
                cv,ext,_=document_bytes(db,packet['document_id']);st.download_button('Descargar solo CV aprobado',cv,file_name='CV.'+ext,key='mw_cv_download')
            except Exception:st.info('Paquete caducado/cambiado o candidatura ya registrada. No reutilizar para un segundo envío.')
            declared=st.checkbox('Confirmo que ya presenté esta solicitud manualmente; registrar para evitar duplicados',key='mw_declared_'+jid+'_'+str(hid))
            if st.button('Registrar candidatura presentada por mí',disabled=not declared,key='mw_declare'):
                try:declare_manual_submission(db,hid,declared);st.success('Declaración registrada. Adjunta el justificante en la sección existente.');st.rerun()
                except Exception:st.error('No se puede registrar: duplicado, historial incierto o paquete inválido.')
        st.caption('Los justificantes EML/PDF se conservan cifrados en «Justificantes de candidaturas manuales». Declarar o aportar un archivo no autentica una recepción externa.')
