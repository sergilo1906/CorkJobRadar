"""Guided policy editor. No acceptance and no worker start on rendering/restart."""
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import streamlit as st
from .policy import Policy,save_policy
from .vault import candidate_snapshot
from .platforms import platform_for

SCHEDULES=['WEEKDAYS_DAY','WEEKEND_DAY','ROTATING','NIGHT','SHIFTS']
CONTRACTS=['PERMANENT','FIXED_TERM','TEMPORARY','INTERNSHIP','APPRENTICESHIP']
PLATFORMS={'Greenhouse':['boards.greenhouse.io','job-boards.greenhouse.io','job-boards.eu.greenhouse.io'],
           'Lever':['jobs.lever.co','jobs.eu.lever.co']}


def render_policy_editor(db,policy):
    base=policy or Policy(expires_at=(datetime.now(ZoneInfo('Europe/Dublin'))+timedelta(days=7)).isoformat(timespec='seconds'))
    st.caption('Configura una autorización global para IT. Cuando se libere el modo real no necesitará aprobación individual; ahora solo se autoriza simulación. 3/día y 15/semana son sugerencias editables.')
    st.info('La nueva selección IT incluye centros hasta 50 km y un mínimo solicitado de hasta 3 años. El transporte pendiente advierte; incompatibilidad acreditada o coche propio obligatorio bloquean. Remotos separados. LIVE OFF.')
    st.caption('La política amplia conserva requisitos veraces, CV aprobado, anuncio vigente y prevención de duplicados. No exige dominar todas las tecnologías ni haber completado DAM. La configuración estricta anterior se conserva para políticas antiguas.')
    with st.form('aa_policy_form'):
        broad=st.checkbox('Aplicar política amplia IT: 50 km, mínimo solicitado hasta 3 años, sin filtro de afinidad',value=policy is None or base.selection_mode=='IT_50KM_MAX3')
        st.multiselect('Sectores autorizados para simulación',['IT'],default=['IT'],disabled=True)
        modes=st.multiselect('Modalidades autorizadas',['REMOTE','HYBRID','ONSITE'],default=base.modes)
        selected=st.multiselect('Plataformas autorizadas',list(PLATFORMS),default=[name for name,hosts in PLATFORMS.items() if any(h in base.allowed_hosts for h in hosts)])
        hosts=st.text_area('Dominios exactos autorizados, uno por línea',value='\n'.join(base.allowed_hosts),help='Seleccionar plataforma no autoriza todos sus dominios. Indica solo los dominios exactos que aceptas.')
        city_only=st.checkbox('Limitar los puestos presenciales a Cork City',value=base.location_scope=='CORK_CITY',disabled=broad)
        max_commute=st.number_input('Límite total del trayecto sin coche en minutos (0 = sin límite adicional)',0,240,base.max_commute_minutes or 0)
        schedules=st.multiselect('Horarios y turnos aceptados',list(dict.fromkeys(SCHEDULES+base.it.schedules)),default=base.it.schedules)
        contracts=st.multiselect('Contratos aceptados',list(dict.fromkeys(CONTRACTS+base.it.contracts)),default=base.it.contracts)
        full_time=st.checkbox('Exigir jornada completa',value=base.it.full_time_required if policy else False)
        hard_salary=st.checkbox('Exigir un salario mínimo publicado y verificable',value=base.it.minimum_salary is not None)
        salary=st.number_input('Salario mínimo EUR (solo se aplica si se exige arriba)',min_value=0.0,value=float(base.it.minimum_salary or 0))
        unit=st.selectbox('Unidad del mínimo salarial',['year','hour'],index=0 if base.it.salary_unit=='year' else 1)
        score=st.number_input('Encaje mínimo AutoApply (no se aplica en política amplia)',0,100,base.min_score,disabled=broad)
        confidence=st.number_input('Confianza mínima independiente (no se aplica en política amplia)',0,100,base.min_confidence,disabled=broad)
        daily=st.number_input('Cupo diario AutoApply',1,100,base.max_daily)
        weekly=st.number_input('Cupo semanal AutoApply',1,500,base.max_weekly)
        company=st.number_input('Cupo semanal por empresa',1,100,base.max_company_weekly)
        cooldown=st.number_input('Espera entre candidaturas a una empresa (horas)',1,8760,base.cooldown_hours)
        failures=st.number_input('Errores antes de pausar AutoApply',1,10,base.max_failures)
        excluded=st.text_area('Empresas excluidas, una por línea',value='\n'.join(base.excluded_companies))
        required_titles=st.text_area('Palabras requeridas en el título (opcional, una por línea)',value='\n'.join(base.allowed_title_words))
        forbidden=st.text_area('Palabras prohibidas en el título, una por línea',value='\n'.join(base.forbidden_words))
        start=st.time_input('Hora inicial de automatización (Dublin)',value=datetime.strptime(base.window_start,'%H:%M').time())
        end=st.time_input('Hora final de automatización (Dublin)',value=datetime.strptime(base.window_end,'%H:%M').time())
        expiry=st.text_input('Caducidad de la política (ISO con zona)',value=base.expires_at)
        generate=st.checkbox('Permito generar CV con mis hechos aprobados',value=base.permissions.generate_cv)
        attach=st.checkbox('Permito adjuntar la versión aprobada del CV',value=base.permissions.attach_cv)
        fill=st.checkbox('Permito preparar los campos con respuestas verificadas',value=base.permissions.fill_forms)
        letter=st.checkbox('Permito generar carta con mis hechos aprobados',value=base.permissions.generate_letter)
        st.caption('Envío final y lectura de correo permanecen desactivados. La autorización de una plataforma no acredita permiso contractual ni que su adaptador esté verificado.')
        consent=st.checkbox('Autorizo esta política SOLO para simulación con las versiones actuales de mi ficha y CV; no autoriza envíos reales')
        submitted=st.form_submit_button('Guardar y autorizar simulación')
    if submitted:
        try:
            fresh=candidate_snapshot(db)
            if not fresh.get('cv_document_id'):raise ValueError('APPROVED_CV_REQUIRED')
            allowed=[h.strip() for h in hosts.splitlines() if h.strip()]
            if not selected or not allowed or any(h not in {h for name in selected for h in PLATFORMS[name]} for h in allowed):raise ValueError('EXACT_SELECTED_PLATFORM_HOSTS_REQUIRED')
            if not modes or (not broad and (not schedules or not contracts)) or hard_salary and salary<=0:raise ValueError('EXPLICIT_TERMS_REQUIRED')
            versions={platform_for('https://'+h)['id']:platform_for('https://'+h)['version'] for h in allowed}
            config=base.model_dump()
            from .radius import origin
            from .broad_selection import RULES_VERSION
            config.update(selection_mode='IT_50KM_MAX3' if broad else 'LEGACY_STRICT',selection_origin_hash=origin(db)['binding_hash'] if broad else '',selection_rules_version=RULES_VERSION if broad else '',
                          categories=['IT'],modes=modes,location_scope='CORK_CITY' if city_only and not broad else 'CORK_AND_SURROUNDINGS',max_commute_minutes=None if broad else max_commute or None,
                          allowed_hosts=allowed,adapter_versions=versions,min_score=0 if broad else score,min_confidence=0 if broad else confidence,max_daily=daily,max_weekly=weekly,max_company_weekly=company,
                          cooldown_hours=cooldown,max_failures=failures,excluded_companies=excluded.splitlines(),allowed_title_words=required_titles.splitlines(),forbidden_words=forbidden.splitlines(),
                          window_start=start.strftime('%H:%M'),window_end=end.strftime('%H:%M'),expires_at=expiry,candidate_facts_hash=fresh['_facts_hash'],authorized_document_ids=[fresh['cv_document_id']],
                          permissions={'generate_cv':generate,'attach_cv':attach,'generate_letter':letter,'fill_forms':fill,'final_submit':False,'read_email':False},
                          it={'schedules':schedules,'contracts':contracts,'full_time_required':full_time,'minimum_salary':salary if hard_salary else None,'salary_unit':unit})
            save_policy(db,config,'AUTHORIZE_SIMULATION' if consent else '')
            st.success('Política versionada autorizada para simulación. No se ha iniciado ningún trabajador ni activado el envío real.')
        except Exception:
            st.error('No se guardó la política. Revisa CV aprobado, plataformas/dominios exactos, horarios, contratos, cupos, caducidad y aceptación expresa.')
