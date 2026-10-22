"""The existing vacancy workspace's document step. User actions alone approve."""
import io
import streamlit as st
from .vault import candidate_snapshot
from .job_documents import (create_job_version, load_job_version, review_file,
                            approve_job_bundle, export_job_bundle, revoke_job_version)
from .job_composition import FAMILIES, family_for
from .reference_library import (reference_record, reference_bytes, reference_preview,
                                import_reference, review_reference, revoke_reference, ISSUERS)

ISSUER_LABELS = {'SIE':'SIE · recomendación IT', 'GAS_REUSENSE':'Gas Reusense · recomendación laboral',
                 'CARRIAGE_FOOD_SERVICES':'Carriage · confirmación de empleo'}


def render_references(db):
    st.subheader('Documentos originales y referencias')
    st.caption('Originales cifrados e intactos. Importar no autoriza adjuntar. Una cover letter es tu carta de presentación, no una recomendación de otra empresa.')
    with st.expander('Importar una referencia original'):
        file = st.file_uploader('PDF original, también escaneado', type=['pdf'], key='ref_original_upload')
        issuer = st.selectbox('Emisor y clasificación', list(ISSUERS), format_func=lambda v: ISSUER_LABELS[v], key='ref_issuer')
        page = st.number_input('Página de la referencia dentro del original', min_value=1, max_value=20, value=1, key='ref_page')
        issued = st.date_input('Fecha publicada (vacía si no consta)', value=None, key='ref_issued')
        role = st.text_input('Puesto relacionado tal como figura en la referencia', key='ref_role')
        standalone = st.checkbox('Este PDF contiene únicamente esta referencia completa; no incluye un CV ni otros documentos', key='ref_standalone')
        consent = st.checkbox('Autorizo conservar localmente este original cifrado; no autorizo adjuntarlo', key='ref_store_consent')
        if st.button('Conservar original para revisar', disabled=not file or not consent, key='ref_import'):
            try:
                import_reference(db, file.getvalue(), issuer=issuer, document_type=ISSUERS[issuer], source_page=page,
                                 issued_on=issued.isoformat() if issued else None, related_role=role, standalone_document=standalone or None, consent_to_store=consent)
                st.success('Original conservado sin permiso de adjuntar.'); st.rerun()
            except Exception: st.error('No se pudo importar: revisa PDF pasivo, clasificación, fecha y página. No se modificó el original.')
    rows = db.rows('SELECT id,revoked_at FROM reference_originals ORDER BY id')
    if not rows:
        st.info('Todavía no hay referencias importadas. No se adjunta ninguna por defecto.'); return
    for record in rows:
        rid = record['id']; row = reference_record(db, rid, include_revoked=True); meta = row['metadata']
        if row['revoked_at']:
            st.caption(ISSUER_LABELS.get(meta.get('issuer'), 'Referencia') + ' · revocada'); continue
        with st.expander(ISSUER_LABELS[meta['issuer']] + (' · revisada' if row['reviewed_at'] else ' · pendiente de revisión')):
            st.write('Fecha publicada:', meta['issued_on'] or 'No verificada')
            st.write('Puesto relacionado:', meta['related_role'] or 'Pendiente')
            if meta.get('notes'): st.info(meta['notes'])
            if not meta.get('source_contains_only_this_reference'):
                st.warning('El original contiene varios documentos. Esta página es solo una vista derivada. Para adjuntar únicamente esta referencia necesitas su PDF original independiente; no exportaremos el CV antiguo ni las otras cartas por selección implícita.')
            st.caption('No se acredita la validez criptográfica de firmas. No se editan, traducen ni reconstruyen los originales.')
            if st.checkbox('Ver página de referencia', key=f'ref_view_{rid}'):
                try:
                    number = st.selectbox('Página del original independiente',list(range(1,row['page_count']+1)),key=f'ref_preview_page_{rid}')-1 if meta.get('source_contains_only_this_reference') else None
                    st.image(reference_preview(db, rid, number), output_format='PNG', caption='Vista derivada para revisión; el original sigue intacto')
                except Exception: st.info('Vista no disponible; descarga y revisa el original completo.')
            raw, _ = reference_bytes(db, rid)
            st.download_button('Descargar original completo para revisar', raw, file_name=f'Referencia-original-{rid}.pdf', key=f'ref_download_{rid}')
            consistency = st.checkbox('He revisado fechas, puesto y posibles diferencias con mi perfil; no añado hechos nuevos', key=f'ref_consistency_{rid}')
            sharing = st.checkbox('Autorizo proponer este documento para compartir; cada paquete requerirá mi selección expresa', key=f'ref_sharing_{rid}')
            if st.button('Guardar mi revisión de la referencia', disabled=not consistency, key=f'ref_review_{rid}'):
                try:
                    review_reference(db, rid, row['file_hash'], consistency_reviewed=consistency, authorize_sharing=sharing, confirmed=True)
                    st.success('Revisión guardada. No se ha enviado ni adjuntado nada.'); st.rerun()
                except Exception: st.error('La referencia cambió o necesita revisión. No se autorizó.')
            revoke = st.checkbox('Quiero revocar el uso de esta referencia conservando su historial', key=f'ref_revoke_check_{rid}')
            if st.button('Revocar referencia', disabled=not revoke, key=f'ref_revoke_{rid}'):
                revoke_reference(db, rid, confirmed=revoke); st.rerun()


def render_job_documents(db, job):
    st.subheader('Documentos para esta oferta')
    st.caption('Seleccionar hechos no modifica tu expediente maestro. Los textos nuevos y cada documento requieren tu revisión. LIVE OFF: este flujo solo prepara y exporta localmente.')
    candidate = candidate_snapshot(db); jid = job['id']; prefix = 'jd_' + jid
    family = st.selectbox('Enfoque del CV', list(FAMILIES), index=list(FAMILIES).index(family_for(job)),
                          format_func=lambda f: FAMILIES[f], key=prefix+'_family')
    two_pages = st.checkbox('Permitir hasta dos páginas si el contenido relevante lo necesita, manteniendo la letra legible', key=prefix+'_two_pages')
    ready=bool(candidate.get('full_name') and candidate.get('email') and candidate.get('_claims'))
    if not ready:st.info('Completa los datos esenciales y los hechos profesionales en Perfil y configuración antes de generar documentos.')
    if st.button('Crear CV adaptado y carta para revisar', key=prefix+'_generate', type='primary', disabled=not ready):
        try:
            vid = create_job_version(db, jid, family=family, max_pages=2 if two_pages else 1)
            st.session_state[prefix+'_preferred'] = vid
            st.success('Borrador cifrado preparado. Ninguna aprobación ni envío.'); st.rerun()
        except Exception:
            st.error('No se pudo generar sin perder información. Revisa los hechos, la asociación de empleos y el límite de páginas. No se reduce la letra ni se recorta texto para forzarlo.')
    versions = db.rows('SELECT id,created_at,revoked_at FROM job_document_versions WHERE job_id=? ORDER BY id DESC', (jid,))
    if not versions:
        st.info('Crea una versión para comparar contenido, revisar diseño y elegir documentos.'); return
    ids = [v['id'] for v in versions]; preferred = st.session_state.get(prefix+'_preferred')
    vid = st.selectbox('Versión de documentos para esta oferta', ids, index=ids.index(preferred) if preferred in ids else 0,
                       format_func=lambda v: 'Versión ' + str(v) + (' · histórica' if v != ids[0] else ' · más reciente'), key=prefix+'_version')
    try: row, payload = load_job_version(db, vid)
    except Exception:
        st.warning('Versión retenida por cambios de perfil, oferta, integridad o revocación. Su historial se conserva; genera otra versión.'); return
    plan = payload['plan']
    inspection_id=None;inspection=None
    from .forms import load_inspection,answer_plan
    for record in db.rows('SELECT id FROM autoapply_form_inspections WHERE job_id=? ORDER BY id DESC',(jid,)):
        try:
            inspection=load_inspection(db,record['id']);inspection_id=record['id'];break
        except (ValueError,PermissionError):continue
    with st.expander('Comparar expediente general y selección para este puesto', expanded=True):
        chosen = set(plan['selected_fact_ids'])
        st.write('Enfoque:', FAMILIES[plan['family']])
        st.write('Hechos seleccionados:', len(chosen), '· Fuera de esta variante:', len(plan['omitted_fact_ids']), '· Todos se conservan en tu perfil.')
        st.dataframe([{'Contenido aprobado': c['text_en'], 'En este CV': c['id'] in chosen,
                       'Motivo': plan['selection_reasons'].get(str(c['id']), 'Conservado en el expediente maestro.')} for c in candidate['_claims']], hide_index=True)
        if plan['summary']:
            st.warning('Resumen con redacción nueva: debes revisar su fidelidad antes de aprobar este paquete.')
            st.write(plan['summary']['text'])
        if plan['unstructured_content_held']:
            st.info('Hay responsabilidades sin asociación laboral acreditada. Se conservan en el expediente; revisa su estructura antes de incluirlas.')
    with st.expander('Necesidades del anuncio y evidencia relacionada'):
        st.caption('Relacionar capacidades no acredita por sí solo un requisito. Obligatorios, deseables y dudas mantienen su estado original.')
        st.dataframe([{'Requisito': r['quote'], 'Nivel': r['level'], 'Estado': r['status'],
                       'Comparación': r['reason'], 'Herramientas sin acreditar': ', '.join(r['tools_not_accredited'])}
                      for r in plan['requirement_evidence']], hide_index=True)
    with st.expander('Contacto, LinkedIn y preguntas de esta candidatura'):
        for key,label in (('full_name','Nombre'),('email','Email'),('phone','Teléfono'),('linkedin_url','LinkedIn')):
            if candidate.get(key):
                st.caption(label+' · copiar a la derecha');st.code(candidate[key],language=None,wrap_lines=True)
        if inspection:
            answers=answer_plan(inspection,candidate)
            st.caption('Preguntas del esquema conservado. Un CV pendiente o una respuesta ausente no se da por resuelta.')
            for field in inspection['fields']:
                answer=answers['mapping'].get(field['id'])
                if answer and 'value' in answer:
                    st.caption(field['label']);st.code(answer['value'],language=None,wrap_lines=True)
                elif field['type']!='file':
                    st.write(('Obligatoria pendiente: ' if field['required'] else 'Opcional sin respuesta aprobada: ')+field['label'])
        else:st.info('No hay un esquema vigente comprobado. Revisa las preguntas en el formulario oficial; el ZIP no se considera una candidatura completa ni autoriza envíos.')
    ext = st.radio('Formato que vas a revisar y exportar', ['pdf', 'docx'], horizontal=True, key=prefix+f'_format_{vid}')
    cv = review_file(db, vid, 'CV', ext)
    from .cv_preview import pdf_preview
    from pypdf import PdfReader
    preview = review_file(db, vid, 'CV', 'pdf')
    st.caption('Vista PDF del contenido. Para Word descarga y revisa también el DOCX en tu editor: su paginación puede variar.')
    for page in range(len(PdfReader(io.BytesIO(preview)).pages)):
        st.image(pdf_preview(preview, page_number=page, max_pages=payload['max_pages']), output_format='PNG', caption='CV · página '+str(page+1))
    st.download_button('Descargar CV para revisar', cv, file_name='CV-revision.'+ext, key=prefix+f'_cv_download_{vid}_{ext}')
    include_letter = st.checkbox('Incluir mi carta de presentación en este paquete', key=prefix+f'_letter_{vid}')
    if include_letter:
        st.caption('Carta del candidato · redacción pendiente de tu revisión · '+str(payload['letter']['word_count'])+' palabras')
        st.text('\n\n'.join(payload['letter']['lines']))
        st.download_button('Descargar carta para revisar', review_file(db, vid, 'COVER_LETTER', ext), file_name='Carta-revision.'+ext, key=prefix+f'_letter_download_{vid}_{ext}')
    reference_ids = []
    with st.expander('Referencias opcionales: ninguna por defecto'):
        st.caption('SIE puede ser pertinente para IT. Gas aporta una recomendación laboral; Carriage únicamente confirma empleo. Solo se ofrecen originales independientes revisados y autorizados.')
        for ref in db.rows('SELECT id FROM reference_originals WHERE revoked_at IS NULL ORDER BY id'):
            rid = ref['id']; rr = reference_record(db, rid); meta = rr['metadata']
            eligible = bool(rr['reviewed_at'] and meta.get('share_authorized') and meta.get('source_contains_only_this_reference'))
            label = 'Adjuntar '+ISSUER_LABELS[meta['issuer']]+' · referencia '+str(rid)
            if st.checkbox(label, disabled=not eligible, key=prefix+f'_ref_{vid}_{rid}') and eligible:
                reference_ids.append(rid)
            if not eligible: st.caption('Pendiente de revisión/permiso u original independiente. Gestionar en Perfil → CV definitivo → Referencias.')
    from .interaction_modes import manual_target_url
    try: target = manual_target_url(job.get('apply_url') or job['url'])
    except ValueError:
        st.warning('Enlace oficial pendiente de revisión. No se puede aprobar el paquete.'); return
    st.link_button('Abrir enlace oficial para revisar documentos admitidos', target)
    from ..config import digest
    inspection_revision=db.rows('SELECT MAX(id) id FROM autoapply_form_inspections WHERE job_id=?',(jid,))[0]['id']
    from .job_documents import _reference_binding
    try: reference_bindings=[_reference_binding(db,rid)[1] for rid in reference_ids]
    except Exception:
        st.warning('La autorización de una referencia ha cambiado. Revisa la selección antes de continuar.');return
    review_context=digest({'version':row['file_hash'],'extension':ext,'letter':include_letter,
                           'references':reference_bindings,'inspection':inspection_id,'revision':inspection_revision})[:24]
    review_key=prefix+'_'+review_context
    if st.session_state.get(prefix+'_review_context')!=review_context:
        st.session_state[prefix+'_review_context']=review_context
        for suffix in ('_accept','_content','_design','_refs_consent','_approve'):
            st.session_state[review_key+suffix]=False
    accepts = st.checkbox('He comprobado el formulario: admite el formato de CV y todos los documentos opcionales que he seleccionado', key=review_key+'_accept')
    content_ok = st.checkbox('He revisado la selección, el resumen y la carta elegida; todo es veraz y no añade experiencia ni equivalencias', key=review_key+'_content')
    design_ok = st.checkbox('He revisado íntegramente el diseño del archivo elegido, incluidas todas sus páginas', key=review_key+'_design')
    refs_ok = st.checkbox('Autorizo expresamente compartir los documentos de terceros seleccionados en esta candidatura', key=review_key+'_refs_consent') if reference_ids else True
    consent = st.checkbox('Apruebo estos documentos exactos para este puesto y su exportación local; no autorizo un envío automático', key=review_key+'_approve')
    if st.button('Aprobar paquete seleccionado para exportación', disabled=not (accepts and content_ok and design_ok and refs_ok and consent) or vid != ids[0], key=prefix+f'_approve_button_{vid}_{ext}'):
        try:
            bid = approve_job_bundle(db, vid, row['file_hash'], extension=ext, include_letter=include_letter,
                 reference_ids=reference_ids, reference_consents=reference_ids if refs_ok else [],
                 inspection_id=inspection_id,
                 expected_inspection_revision=inspection_revision,
                 expected_reference_bindings=reference_bindings,
                 acceptance={'cv':True, 'cover_letter':include_letter, 'references':bool(reference_ids), 'source_url':target, 'user_verified':accepts},
                 content_reviewed=content_ok, design_reviewed=design_ok, confirmed=consent)
            st.success('Paquete aprobado por ti. LIVE sigue OFF; no se ha enviado.'); st.session_state[prefix+'_bundle']=bid; st.rerun()
        except Exception: st.warning('Paquete retenido. Comprueba versión, selección IT, duplicados, documentos admitidos y permisos de referencias.')
    for bundle in db.rows('SELECT id FROM job_document_bundles WHERE job_id=? AND revoked_at IS NULL ORDER BY id DESC', (jid,)):
        try:
            from .job_documents import load_job_bundle
            approved=load_job_bundle(db,bundle['id'])
        except Exception:
            st.caption('Paquete retenido por cambios o caducidad: '+str(bundle['id']));continue
        st.caption('Paquete autorizado '+str(bundle['id'])+': '+', '.join(d['name'] for d in approved['documents'])+
                   (' · referencias: '+str(len(approved['references'])) if approved['references'] else ' · sin referencias'))
        matches=(approved['version_id']==vid and approved['extension']==ext and approved['include_letter']==include_letter and
                 {r['id'] for r in approved['references']}==set(reference_ids))
        if not matches:
            st.caption('La selección actual difiere de este paquete. Revisa y aprueba la nueva selección para exportarla.');continue
        if st.button('Preparar ZIP autorizado · paquete '+str(bundle['id']), key=prefix+'_zip_prepare_'+str(bundle['id'])):
            try:
                raw, hid = export_job_bundle(db, bundle['id'])
                st.session_state[prefix+'_export'] = (raw, hid, bundle['id'],review_context)
            except Exception: st.warning('No se exportó: un dato, versión, permiso, formulario o plazo ha cambiado; revisa de nuevo.')
    if prefix+'_export' in st.session_state:
        stored=st.session_state[prefix+'_export']
        if len(stored)!=4 or stored[3]!=review_context:
            del st.session_state[prefix+'_export']
        else:
            raw, hid, bid, _ = stored
            # Do not leave a cached download active after revocation or a rerun change.
            try:
                from .job_documents import load_job_bundle
                load_job_bundle(db, bid)
                st.download_button('Descargar candidatura preparada (ZIP privado)', raw, file_name='Candidatura-IT-preparada.zip', mime='application/zip', key=prefix+'_zip_download_'+str(bid))
                st.caption('Paquete manual '+str(hid)+': descargar no presenta una solicitud ni acredita recepción. Los bloqueos y respuestas pendientes figuran dentro.')
            except Exception: st.warning('La descarga anterior ya no está vigente.')
    revoke = st.checkbox('Quiero revocar esta versión de documentos y sus paquetes', key=prefix+f'_revoke_{vid}')
    if st.button('Revocar versión de esta oferta', disabled=not revoke, key=prefix+f'_revoke_button_{vid}'):
        revoke_job_version(db, vid, confirmed=revoke); st.rerun()
