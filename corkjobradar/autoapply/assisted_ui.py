"""Independent blockers and encrypted historical manual proof, without sending."""
import streamlit as st
from .blocker_report import persist_blocker_report
from .manual_evidence import retain_manual_evidence,read_manual_evidence,evidence_download,review_manual_evidence


def render_assisted_diagnostics(db):
    with st.expander('Diagnóstico independiente y gestiones de cada canal'):
        st.caption('Permisos, adaptador, acceso, respuestas, transporte, CV/política y compatibilidad son causas separadas. El diagnóstico no autoriza envíos ni modifica ofertas.')
        if st.button('Diagnosticar todos los bloqueos por separado'):
            report,_=persist_blocker_report(db);st.session_state['aa_independent_blockers']=report
        report=st.session_state.get('aa_independent_blockers')
        if report:
            st.write('Ofertas diagnosticadas:',report['jobs_processed'])
            st.dataframe(report['companies'],hide_index=True)
            relevant=[r for r in report['offers'] if r['it_relevant_for_research'] and r['stored_scope']!='FUERA_DE_ALCANCE']
            if relevant:
                jid=st.selectbox('Desglose de una vacante para investigación',[r['job_id'] for r in relevant],format_func=lambda key:next(r['company']+' · '+r['title'] for r in relevant if r['job_id']==key))
                selected=next(r for r in relevant if r['job_id']==jid)
                st.dataframe([{'causa':axis,**{k:v for k,v in value.items() if k!='unresolved_questions'}} for axis,value in selected['axes'].items()],hide_index=True)
                if selected['axes']['answers']['unresolved_questions']:st.dataframe(selected['axes']['answers']['unresolved_questions'],hide_index=True)
            st.caption(report['limit'])
            st.download_button('Descargar diagnóstico separado',__import__('json').dumps(report,ensure_ascii=False,indent=2),file_name='Bloqueos-AutoApply.json',mime='application/json')


def render_manual_evidence(db,job_id=None):
    declarations=db.rows('''SELECT d.id,d.declared_at,j.company,j.title FROM manual_application_declarations d
                                JOIN manual_application_handoffs h ON h.id=d.handoff_id JOIN jobs j ON j.id=h.job_id
                                WHERE (? IS NULL OR h.job_id=?) ORDER BY d.id DESC''',(job_id,job_id))
    with st.expander('Justificantes de candidaturas manuales',expanded=bool(declarations)):
        st.caption('Registra primero tu declaración de presentación manual. Aquí puedes conservar un EML original o PDF pasivo, cifrado. Ningún archivo ni revisión personal se convierte por sí solo en recepción externa autenticada.')
        if not declarations:
            st.info('No hay candidaturas manuales declaradas. No se crearán declaraciones ni justificantes de ejemplo.')
            return
        declaration_id=st.selectbox('Candidatura manual cuyo justificante quieres conservar',[r['id'] for r in declarations],
                                   format_func=lambda key:next(r['company']+' · '+r['title']+' · '+r['declared_at'] for r in declarations if r['id']==key))
        uploaded=st.file_uploader('Justificante original EML o PDF pasivo (máximo 5 MB)',type=['eml','pdf'],key='aa_manual_evidence_upload')
        consent=st.checkbox('Autorizo conservar este justificante cifrado; entiendo que no autentica al remitente ni activa AutoApply',key='aa_manual_evidence_consent')
        if st.button('Guardar justificante cifrado',disabled=uploaded is None or not consent):
            try:
                result=retain_manual_evidence(db,declaration_id,uploaded.getvalue(),uploaded.name.rsplit('.',1)[-1].lower(),consent=consent)
                st.success('Justificante conservado con hash y vínculo a la candidatura. Recepción externa sin autenticar.')
            except Exception:st.error('No se pudo guardar: comprueba tamaño/formato, correo original sin reenvío o PDF sin contenido activo.')
        evidence=db.rows('''SELECT e.id,e.uploaded_at,e.extension,e.status,r.status AS review_status FROM manual_application_evidence e
                           LEFT JOIN manual_application_evidence_reviews r ON r.evidence_id=e.id WHERE e.declaration_id=? ORDER BY e.id DESC''',(declaration_id,))
        if evidence:
            st.dataframe(evidence,hide_index=True)
            eid=st.selectbox('Justificante para revisar o descargar',[r['id'] for r in evidence])
            try:
                packet=read_manual_evidence(db,eid)
                st.json(packet['signals'])
                evidence_key=str(eid)+'_'+packet['content_hash']
                if st.checkbox('Mostrar el texto privado del justificante',key='aa_manual_evidence_private_'+evidence_key):
                    extracted=packet['extracted'];st.text((extracted.get('subject') or '')+'\n'+extracted['text'])
                content,ext=evidence_download(db,eid)
                st.download_button('Descargar justificante original',content,file_name='Justificante.'+ext,mime='message/rfc822' if ext=='eml' else 'application/pdf')
                acknowledged=st.checkbox('He contrastado personalmente el justificante con esta candidatura; no solicito autenticar su origen',key='aa_manual_evidence_review_'+evidence_key)
                if st.button('Registrar mi revisión del justificante',disabled=not acknowledged):
                    review_manual_evidence(db,eid,packet['content_hash'],acknowledged=acknowledged)
                    st.success('Revisión personal conservada. La confirmación externa autenticada continúa pendiente.')
            except Exception:st.info('Justificante no disponible o retenido: puede haberse borrado el contenido profesional o cambiado su integridad.')
