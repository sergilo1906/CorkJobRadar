"""Radius evidence, private origin and resumable local queue controls."""
import json
import streamlit as st
from ..config import now
from .radius import origin,save_origin,save_worksite
from .broad_selection import selection_inventory,assess_selection,RULES_VERSION
from .selection_queue import refresh_queue,prepare_all_local,queue_summary

REASON_LABELS={
    'ACADEMIC_ACCEPTANCE_PENDING':'DAM terminado no acredita automáticamente la titulación solicitada: comprobar equivalencia, alternativa o matrícula actual. La duda no descarta la preparación.',
    'NON_IT':'Las funciones del puesto no son informáticas.',
    'IT_FUNCTIONS_PENDING':'Faltan funciones concretas que acrediten un puesto IT.',
    'OUTSIDE_50_KM':'Ubicación acreditada fuera del radio de 50 km.',
    'WORKSITE_RADIUS_PENDING':'Falta comprobar el centro real de trabajo y su distancia.',
    'REMOTE_ADDITIONAL_AUTHORIZATION_REQUIRED':'Remoto separado: comprobar permiso desde Irlanda y autorización adicional.',
    'MANDATORY_MINIMUM_EXPERIENCE_OVER_3':'Pide más de 3 años como mínimo obligatorio.',
    'EXPERIENCE_ALTERNATIVE_OR_PREFERENCE_TO_CLARIFY':'Experiencia con alternativas o preferencia por aclarar; no se descarta automáticamente.',
    'EXPERIENCE_SHORTFALL_DISCLOSED':'Tu experiencia real es inferior a la solicitada, dentro del mínimo de hasta 3 años que quieres considerar.',
    'NONESSENTIAL_REQUIREMENT_NOT_PROVEN':'Requisito técnico, académico o deseable sin acreditar; revisar el contraste sin atribuir competencias.',
    'PROVEN_MANDATORY_INCOMPATIBILITY':'Existe un incumplimiento obligatorio acreditado.',
    'OWN_CAR_REQUIRED':'Exige expresamente coche propio y tu perfil declara que no dispones de él.',
    'ESSENTIAL_LEGAL_OR_LICENSE_ANSWER_PENDING':'Falta una respuesta o acreditación legal/habilitación imprescindible.',
    'IRELAND_WORK_AUTHORIZATION_PENDING':'Derecho a trabajar en Irlanda pendiente de acreditar.',
    'PROVEN_COMMUTE_INCOMPATIBILITY':'Desplazamiento incompatible acreditado para los medios disponibles.',
    'COMMUTE_AND_SHIFT_PENDING':'Desplazamiento y turno pendientes de verificar; esta incertidumbre no descarta la candidatura.',
    'VACANCY_CLOSED':'La oferta figura cerrada o su plazo ha vencido.',
    'CURRENT_OPEN_STATUS_PENDING':'Es necesario comprobar que la oferta sigue abierta.',
    'DEADLINE_PENDING':'Fecha límite pendiente de aclarar.',
    'APPROVED_CV_PENDING':'CV definitivo pendiente de tu revisión y aprobación por versión.',
    'POSSIBLE_DUPLICATE_REVIEW':'Posible duplicado pendiente de contrastar.',
    'ALREADY_APPLIED_OR_RESERVED':'Ya existe una solicitud o reserva equivalente: no repetir.',
}


def reason_text(code):
    return REASON_LABELS.get(code,code)


def render_selection_controls(db):
    st.subheader('Política de selección IT · 50 km · mínimo solicitado hasta 3 años')
    st.caption('Preferencias de selección implementadas; todavía no autorizan envíos. LIVE OFF. Sin corte por puntuación o número de ofertas. Los hechos y la duración real de tu experiencia se conservan.')
    with st.expander('Origen local y reglas de selección'):
        o=origin(db)
        st.write('Origen aproximado Ballinlough' if o.get('approximate') else 'Origen preciso guardado cifrado localmente')
        st.caption('Radio de 50 km en línea recta, inclusive. Las coordenadas privadas no se envían a mapas, geocodificadores ni logs. La distancia no es un tiempo de transporte.')
        with st.form('it50_origin'):
            lat=st.number_input('Latitud privada del origen',-90.0,90.0,float(o['latitude']),format='%.6f')
            lon=st.number_input('Longitud privada del origen',-180.0,180.0,float(o['longitude']),format='%.6f')
            consent=st.checkbox('Confirmo este origen local para calcular distancias; no autorizo envíos')
            if st.form_submit_button('Guardar origen cifrado localmente',disabled=not consent):
                save_origin(db,lat,lon,confirmed=consent);st.rerun()
        st.write('0–3 años de mínimo obligatorio: se considera, aunque tu experiencia real sea inferior. Más de 3 de mínimo obligatorio: excluida. Los deseables y dudas técnicas/académicas se conservan como advertencias.')
        st.write('Remotos en categoría separada, sin inclusión automática. Transporte pendiente advierte; coche propio obligatorio o incompatibilidad acreditada bloquean. LinkedIn/Indeed se completan manualmente.')
    with st.expander('Cola completa y reanudable de preparación local'):
        st.write(queue_summary(db))
        st.caption('Incluye todas las ofertas, también excluidas y pendientes con motivo. Preparar no envía, no aprueba CV, no resuelve preguntas nuevas ni necesita permisos API empresariales. Las sesiones de envío incierto no se reintentan.')
        if st.button('Reclasificar todas las ofertas y actualizar cola',key='it50_refresh_queue'):
            refresh_queue(db);st.success('Todas las ofertas examinadas y conservadas en la cola.');st.rerun()
        from .vault import candidate_snapshot
        approved=bool(candidate_snapshot(db).get('cv_document_id'))
        if not approved:st.info('Revisa y aprueba tu CV definitivo para poder preparar los paquetes. La cola ya conserva las ofertas y sus motivos.')
        if st.button('Preparar todas las candidaturas manuales posibles',disabled=not approved,key='it50_prepare_all'):
            try:st.write(prepare_all_local(db))
            except RuntimeError:st.info('Hay otro trabajador activo. Se conserva la cola; no se inicia otro.')
        history=db.rows('SELECT occurred_at,workflow_state,code FROM it_application_queue_events ORDER BY id DESC LIMIT 30')
        if history:st.dataframe(history,hide_index=True)


def render_worksite(db,job,selection):
    with st.expander('Centro de trabajo y distancia geográfica',expanded=selection['geography']['state']=='LOCATION_PENDING'):
        geo=selection['geography'];st.write('Radio:',geo['state'])
        st.write('Distancia en línea recta:',(str(round(geo['distance_km'],3))+' km') if geo['distance_km'] is not None else 'Pendiente; no se inventa una distancia')
        st.caption(geo['reason'])
        st.caption('Comprueba que las coordenadas corresponden al centro del puesto, no solo a una sede social o al centro de la ciudad.')
        if job['mode']=='REMOTE':return
        with st.form('it50_site_'+job['id']):
            lat=st.number_input('Latitud publicada del centro de trabajo',-90.0,90.0,value=None,format='%.6f')
            lon=st.number_input('Longitud publicada del centro de trabajo',-180.0,180.0,value=None,format='%.6f')
            evidence=st.text_input('URL oficial que acredita este centro para la vacante')
            consent=st.checkbox('He comprobado el centro real de esta vacante y sus coordenadas')
            if st.form_submit_button('Guardar centro verificado',disabled=not consent):
                try:save_worksite(db,job['id'],lat,lon,evidence,job['content_hash'],confirmed=consent);st.rerun()
                except (ValueError,PermissionError):st.error('No se guardó: revisa coordenadas, URL pública y versión del anuncio.')


def assisted_inventory(db):
    """Keep the old factual checklist while presenting the new independent selection."""
    from .manual_workspace import manual_inventory
    old=manual_inventory(db);new=selection_inventory(db);by_id={r['job_id']:r for r in new['offers']}
    for r in old['offers']:
        selected=by_id[r['job_id']];r['factual_review_state']=r['state'];r['selection']=selected;r['state']=selected['state']
        r['reasons']=selected['exclusions']+selected['essential_pending']+selected['operational_pending']
        r['manual_package_possible']=selected['preparation_allowed'] and selected['cv_approved']
    old['selection_report']=new
    old['states']=new['states']
    return old
