"""Local preparation and honest platform status; no automatic remote navigation."""
import streamlit as st
from .compatibility import compatibility_report
from .handoff import prepare_handoff,load_handoff,handoff_download,declare_manual_submission
from .vault import candidate_snapshot
from .it_scope import classify_it_functions


def render_manual_operations(db,jobs):
    from .assisted_ui import render_assisted_diagnostics
    render_assisted_diagnostics(db)
    with st.expander('Compatibilidad ATS y permiso de automatización'):
        assessment=compatibility_report()
        st.caption('Revisado: '+assessment['reviewed_on']+'. Plataformas con permiso y envío comprobados en esta instalación: '+str(assessment['allowed_and_verified_count'])+'. LIVE OFF.')
        for review in assessment['routes']:
            st.write(review['platform']+' · '+review['classification'])
            st.caption(review['scope']+' '+review['technical_evidence']+' '+review['next_step'])
            for source in review['sources']:st.markdown('[Documentación oficial]('+source+')')
        if st.button('Auditar plataformas y retenciones de todas las ofertas guardadas'):
            from .opportunities import persist_inventory
            report,_=persist_inventory(db)
            st.session_state['aa_ats_inventory']=report
        report=st.session_state.get('aa_ats_inventory')
        if report:
            st.write('Ofertas examinadas:',report['jobs_processed'])
            st.dataframe(report['companies'],hide_index=True)
            st.caption(report['limitation'])
            st.download_button('Descargar inventario ATS y retenciones',__import__('json').dumps(report,ensure_ascii=False,indent=2),
                               file_name='Inventario-ATS.json',mime='application/json')
    with st.expander('Preparar paquete para intervención manual'):
        st.caption('LINKEDIN_MANUAL: CV, respuestas y enlace para Easy Apply manual. INDEED_MANUAL: documentos y funciones oficiales utilizadas por ti. Un enlace externo requiere revisión independiente; no se automatizan estos portales.')
        st.caption('CV aprobado, contactos, LinkedIn y respuestas verificadas, sin rellenar sitios externos. Los requisitos y rutas pendientes siguen en HOLD. Descargar no significa enviar.')
        jobs=[j for j in jobs if classify_it_functions(j).status=='CONFIRMED_IT']
        if jobs:
            jid=st.selectbox('Vacante IT para preparación manual',[j['id'] for j in jobs],
                            format_func=lambda key:next(j['title']+' · '+j['company'] for j in jobs if j['id']==key))
            from .interaction_modes import interaction_route
            chosen=next(j for j in jobs if j['id']==jid)
            route=interaction_route(chosen.get('apply_url') or chosen['url'],source_url=chosen['url'])
            st.write('Modo de plataforma:',route['mode'])
            st.caption(route['reason'])
            inspections=db.rows('SELECT id FROM autoapply_form_inspections WHERE job_id=? ORDER BY id DESC',(jid,))
            iid=st.selectbox('Preguntas inspeccionadas para el paquete',[None]+[r['id'] for r in inspections],
                             format_func=lambda key:'Sin inspección: revisar todas las preguntas manualmente' if key is None else 'Inspección '+str(key))
            approved=bool(candidate_snapshot(db).get('cv_document_id'))
            if st.button('Preparar paquete manual cifrado',disabled=not approved):
                try:
                    prepare_handoff(db,jid,iid)
                    st.success('Paquete cifrado conservado para revisión manual, sin enviar.')
                except Exception:st.error('Revisa CV aprobado, duplicados, URL oficial e inspección vigente.')
            if not approved:st.info('Aprueba primero la versión definitiva del CV. Los hechos ya aprobados se conservan.')
            packages=db.rows('SELECT id,created_at,package_hash FROM manual_application_handoffs WHERE job_id=? ORDER BY id DESC',(jid,))
            hid=st.selectbox('Paquete manual conservado',[r['id'] for r in packages],
                             format_func=lambda key:next('Versión '+str(key)+' · '+r['created_at'] for r in packages if r['id']==key)) if packages else None
            if hid:
                try:
                    package=load_handoff(db,hid)
                    if package['job_id']==jid:
                        st.warning('REVISIÓN MANUAL · No enviado · Recepción externa sin verificar')
                        st.write('Bloqueos vigentes:',package['blockers'])
                        st.write('Respuestas verificadas:',len(package['verified_answers']))
                        if package.get('question_checklist'):st.dataframe(package['question_checklist'],hide_index=True)
                        if package['unresolved_questions']:st.dataframe(package['unresolved_questions'],hide_index=True)
                        st.caption('El ZIP descargado contiene datos personales en claro. La copia persistente está cifrada.')
                        st.download_button('Descargar paquete para revisión manual',handoff_download(db,hid),file_name='Candidatura-manual.zip',mime='application/zip')
                        st.link_button('Abrir formulario oficial para uso manual',package['target_url'])
                except Exception:st.info('Paquete retenido: caducó, cambió la oferta/ficha/CV o ya consta una solicitud.')
                declared=st.checkbox('Ya he presentado esta candidatura manualmente; evitar duplicados sin afirmar recepción externa')
                if st.button('Registrar mi declaración de envío manual',disabled=not declared):
                    try:
                        declare_manual_submission(db,hid,declared)
                        st.success('Declaración registrada; no se repetirá. Recepción externa todavía sin verificar.')
                    except Exception:st.error('No se puede registrar: ya existe candidatura equivalente o no se puede verificar el paquete conservado.')
        declarations=db.rows('''SELECT d.declared_at,d.status,h.job_id FROM manual_application_declarations d
                                JOIN manual_application_handoffs h ON h.id=d.handoff_id ORDER BY d.id DESC''')
        if declarations:st.dataframe(declarations,hide_index=True)
