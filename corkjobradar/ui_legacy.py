import json
import math
from datetime import datetime
from pathlib import Path
import streamlit as st
import yaml
from corkjobradar.config import ROOT,now,load_profile,save_profile
from corkjobradar.db import Database
from corkjobradar.cli import doctor
from corkjobradar.repository import all_jobs,latest_analysis,latest_analyses,run_observations
from corkjobradar.audit import coverage,coverage_markdown
from corkjobradar.worker import create_run,spawn_worker,prepare_resume,enqueue
from corkjobradar.sources import load_catalog,export_sources,import_sources
from corkjobradar.exporting import export_all,LABELS
from corkjobradar.imports import import_csv,cv_skills
from corkjobradar.analysis import analyze_job
from corkjobradar.runtime_ui import bootstrap as runtime_bootstrap,render as render_runtime


def render_legacy(db,section,selected=None):
    from corkjobradar.worker import create_run,spawn_worker,prepare_resume,enqueue
    from corkjobradar.exporting import export_all
    profile=load_profile()
    results=latest_analyses(db)
    jobs=all_jobs(db,results)
    results={j['id']:results.get(j['id'],{}) for j in jobs}
    ids={j['id']:j for j in jobs}
    report=coverage(db)
    def launch(kind='scan',payload=None):
        try:
            override={**profile,'analyzer':'llama'} if kind=='deep' else None
            run_id=create_run(db,kind=kind,profile_override=override)
            if kind in {'health','discover','import_url','transit_refresh'}:
                enqueue(db,run_id,None,None,kind,payload)
            elif kind=='deep':
                enqueue(db,run_id,None,payload['job_id'],'analyze')
            spawn_worker(run_id)
            st.success(f'Ejecución {run_id} iniciada en proceso independiente')
        except Exception as exc:
            st.error(str(exc))
    personal_marks={};application_states={}
    workflow={'solicitada','respuesta recibida','entrevista','rechazada','oferta recibida','seguimiento'}
    for record in db.rows('SELECT * FROM user_actions ORDER BY id DESC'):
        target=application_states if record['action'] in workflow else personal_marks
        target.setdefault(record['job_id'],record['action'])
    if section=='list':
        st.subheader('Todas las ofertas conservadas')
        st.caption('Por defecto: absolutamente todas, incluidas cerradas, pendientes y archivadas. La paginación solo cambia la vista.')
        observed_runs=db.rows('SELECT DISTINCT r.id,r.started_at FROM scan_runs r JOIN source_runs s ON s.run_id=r.id ORDER BY r.id DESC')
        observed_run=st.selectbox('Búsqueda para comparar novedades',[r['id'] for r in observed_runs],index=0) if observed_runs else None
        observations=run_observations(db,observed_run) if observed_run else {}
        for job in jobs:
            job['change_status']=observations.get(job['id'],'NO_OBSERVADA')
            job['application_status']=application_states.get(job['id'],'sin candidatura registrada')
        change_filter=st.multiselect('Novedad en la búsqueda',['NEW','CHANGED','REPEATED','NO_OBSERVADA','LEGACY_UNKNOWN'])
        query=st.text_input('Palabras clave en título, empresa, localidad o descripción')
        filters={}
        labels={'category':'Sector','scope':'Alcance','open_status':'Vigencia','analysis_status':'Estado del análisis',
                'company':'Empresa','location':'Ubicación publicada','mode':'Modalidad','contract':'Contrato publicado'}
        for index,(key,label) in enumerate(labels.items()):
            if index%4==0: columns=st.columns(4)
            filters[key]=columns[index%4].multiselect(label,sorted({j[key] for j in jobs}))
        with st.expander('Filtros adicionales'):
            sources=st.multiselect('Fuente',sorted({s for j in jobs for s in (j['sources'] or '').split('; ')}))
            minimum=st.slider('Encaje mínimo provisional',0,100,0)
            schedule=st.multiselect('Horario publicado',['lunes_viernes','fines_semana','noches','rotacion','guardias','diurno'])
            mark=st.selectbox('Marca personal',['Todas','favorita','pendiente','quiero solicitar','solicitada','descartada'])
            application_filter=st.multiselect('Seguimiento de candidaturas',sorted(workflow))
            route=st.selectbox('Transporte documentado',['Todos','bus directo','bicicleta','radio IT referencia'])
            salary_unit=st.selectbox('Unidad salarial',['Cualquiera','hora','año'])
            salary_min=st.number_input('Salario mínimo publicado (sin conversiones)',min_value=0.,value=0.)
            if salary_min and salary_unit=='Cualquiera':
                st.warning('Selecciona hora o año para aplicar un mínimo comparable. Mientras tanto no se aplica el mínimo.')
                salary_min=0.
            unknown_salary=st.checkbox('Conservar salario desconocido al filtrar',value=True)
            max_experience=st.number_input('Máximo de años de experiencia publicados (0 = sin filtro)',min_value=0,value=0,step=1)
            unknown_experience=st.checkbox('Conservar experiencia desconocida al filtrar',value=True)
            tech_type=st.selectbox('Tipo de puesto',['Todos','IT','NO_IT'])
            new_only=st.checkbox('Primera observación hoy (Europe/Dublin)')
        filtered=[]
        for j in jobs:
            if change_filter and j['change_status'] not in change_filter: continue
            if application_filter and j['application_status'] not in application_filter: continue
            if query and query.casefold() not in ' '.join(str(j[k]) for k in ('title','company','location','description')).casefold(): continue
            if any(values and j[key] not in values for key,values in filters.items()): continue
            if tech_type=='IT' and j['category']!='IT': continue
            if tech_type=='NO_IT' and j['category']=='IT': continue
            if sources and not any(s in (j['sources'] or '').split('; ') for s in sources): continue
            if (j['fit_score'] or 0)<minimum: continue
            result=results[j['id']]
            facts=result.get('facts',{})
            shift=facts.get('schedule',{}).get('value') or {}
            if schedule and not all(s in shift for s in schedule): continue
            sal=facts.get('salary',{}).get('value')
            exp=facts.get('experience',{}).get('value')
            if max_experience and ((exp is None and not unknown_experience) or (exp is not None and exp>max_experience)): continue
            if salary_unit!='Cualquiera' or salary_min:
                if not sal and not unknown_salary: continue
                if sal and ((salary_unit!='Cualquiera' and sal['unit']!=salary_unit) or sal['min']<salary_min): continue
            if mark!='Todas' and mark not in {personal_marks.get(j['id']),application_states.get(j['id'])}: continue
            if new_only and not j['first_seen_at'].startswith(now()[:10]): continue
            if route!='Todos':
                target={'bus directo':'bus','bicicleta':'bicycle','radio IT referencia':'car_reference'}[route]
                from corkjobradar.geography import valid_commute
                if not any(ch['mode']==target and (valid_commute(ch,profile) if target!='car_reference' else ch['viability']=='VERIFICADA') for ch in result.get('transport',{}).get('checks',[])): continue
            filtered.append(j)
        order=st.selectbox('Ordenar por',['Primera observación','Última observación','Encaje provisional','Empresa','Fecha publicada','Confianza','Última verificación','Salario EUR/hora','Salario EUR/año'])
        if order.startswith('Salario EUR/'):
            unit=order.split('/')[-1]
            def pay_key(j):
                pay=results[j['id']].get('facts',{}).get('salary',{}).get('value')
                return pay['min'] if pay and pay['unit']==unit else -1
            filtered.sort(key=pay_key,reverse=True)
            st.caption('Se ordenan únicamente salarios publicados en la unidad elegida; los demás aparecen después.')
        else:
            key={'Primera observación':'first_seen_at','Última observación':'last_seen_at','Encaje provisional':'fit_score','Empresa':'company','Fecha publicada':'posted_at','Confianza':'data_confidence','Última verificación':'last_verified_at'}[order]
            filtered.sort(key=lambda j:j[key] if j[key] is not None else 0 if key in {'fit_score','data_confidence'} else '',reverse=order!='Empresa')
        page_size=st.selectbox('Ofertas por página',[25,50,100],index=1)
        pages=max(1,math.ceil(len(filtered)/page_size))
        page=st.number_input('Página',min_value=1,max_value=pages,value=1,step=1)
        st.write(f'{len(filtered)} resultados · {len(jobs)} registros totales · {pages} páginas')
        columns=['id','title','company','location','category','scope','change_status','application_status','schedule','contract','salary','posted_at','first_seen_at','last_seen_at','fit_score','data_confidence','open_status','last_verified_at','analysis_status','depth','sources','url']
        st.dataframe([{k:j.get(k) for k in columns} for j in filtered[(page-1)*page_size:page*page_size]],hide_index=True,width='stretch',column_config={**{k:LABELS.get(k,k) for k in columns},'url':st.column_config.LinkColumn('Anuncio original')})
        return
    if section=='detail':
        st.subheader('Ficha individual y evidencias')
        if jobs:
            ids={j['id']:j for j in jobs}
            selected=st.selectbox('Oferta',list(ids),index=list(ids).index(selected) if selected in ids else 0,format_func=lambda i:f"{ids[i]['title']} · {ids[i]['company']}")
            from corkjobradar.reading_qa import reviewed_analysis
            j=ids[selected]; result=reviewed_analysis(results[selected])
            st.write(f"**{j['title']}** · {j['company']} · {j['location']}")
            st.write(f"Vigencia: {j['open_status']} · Análisis: {j['analysis_status']} · {result.get('depth','PENDIENTE')}")
            st.warning(j['scope_reason'])
            st.link_button('Abrir anuncio original',j['url'])
            if j['apply_url'] and j['apply_url'].startswith(('https://','http://')) and 'linkedin.com' not in j['apply_url']:
                st.link_button('Abrir candidatura para revisión manual',j['apply_url'])
            st.text(result.get('summary_es','Análisis pendiente'))
            if j.get('analysis_stale'):
                st.warning('El contenido cambió después del análisis mostrado. Reanalizar antes de usar su puntuación.')
            st.write(result.get('verdict_es',''))
            if result.get('fit_range'):
                st.caption(f"Intervalo por datos desconocidos: {result['fit_range']['minimum']}–{result['fit_range']['maximum']}/100. No expresa probabilidad de contratación.")
            from corkjobradar.local_model import is_validated_model
            if st.button('Leer esta oferta en español con el modelo local',disabled=not is_validated_model()):
                launch('deep',{'job_id':selected})
            if not is_validated_model():
                st.caption('El modelo local sigue pendiente de validar. Se conserva el análisis documental con citas y las incidencias.')
            from corkjobradar.reading_qa import reviewed_reading
            semantic=reviewed_reading(result.get('semantic',{}))
            if semantic.get('items'):
                st.warning('Interpretación del modelo local: las citas se han validado; la traducción y las conclusiones requieren revisión humana.')
                st.caption(f"Pasajes traducidos con cita: {semantic.get('passages_translated','?')}/{semantic.get('passages_total','?')}. Los fallos permanecen pendientes.")
                field_labels={'duties':'Funciones','mandatory':'Requisitos imprescindibles','desirable':'Requisitos deseables','benefits':'Condiciones y beneficios','context':'Contexto publicado'}
                for item in semantic['items']:
                    st.caption(field_labels.get(item.get('field'),item.get('field','Pasaje'))+' · '+str(item.get('requirement_level','sin clasificar')))
                    if item.get('translation_method')=='CORRECCION_LITERAL_REVISADA':st.caption('Traducción literal corregida y revisada; la salida anterior se conserva en el historial.')
                    st.text(item['explanation_es'])
                    st.text('Fuente literal: '+item['quote'])
                if result.get('model_validation')=='VALIDADO_MUESTRA_LIMITADA' and not semantic.get('errors') and not j.get('analysis_stale'):
                    with st.form('review_analysis'):
                        reviewed=st.checkbox('He contrastado todas las interpretaciones, los requisitos y los datos desconocidos con el texto original')
                        review_notes=st.text_area('Notas de la revisión del análisis')
                        if st.form_submit_button('Guardar revisión y completar este análisis'):
                            if not reviewed:
                                st.error('Confirma la revisión del texto y sus citas; el borrador sigue pendiente.')
                            else:
                                try:
                                    from corkjobradar.reviews import approve_analysis
                                    candidates=db.rows('SELECT id FROM job_analyses WHERE job_id=? AND analyzer_version=? ORDER BY id DESC LIMIT 1',(selected,result['analyzer_version']))
                                    approve_analysis(db,selected,candidates[0]['id'],review_notes)
                                    st.success('Revisión guardada como nueva versión. Los datos no publicados y el transporte pendiente siguen indicados.')
                                except Exception as exc:st.error(str(exc))
            documentary=result.get('documentary',{})
            for key,label in [('duties_original','Funciones publicadas'),('mandatory_original','Requisitos imprescindibles publicados'),('desirable_original','Requisitos deseables publicados')]:
                with st.expander(label):
                    for quote in documentary.get(key,[]):
                        st.text(quote)
                    if not documentary.get(key): st.write('No se han podido separar con fiabilidad; revisar el texto original.')
            with st.expander('Análisis detallado, encaje, evidencias e incertidumbre'): st.json(result)
            with st.expander('Versiones conservadas del análisis'):
                versions=db.rows('SELECT id,analyzer_version,status,created_at,result FROM job_analyses WHERE job_id=? ORDER BY id DESC',(selected,))
                if versions:
                    chosen=st.selectbox('Versión para revisar',[r['id'] for r in versions],
                        format_func=lambda i:next(f"{v['created_at']} · {v['analyzer_version']} · {v['status']}" for v in versions if v['id']==i))
                    st.json(json.loads(next(v['result'] for v in versions if v['id']==chosen)))
            with st.expander('Texto original íntegro recuperado'): st.text(j['description'] or 'Descripción pendiente')
            with st.expander('Procedencias, snapshots y verificaciones'):
                st.dataframe(db.rows('SELECT * FROM job_sources WHERE job_id=?',(selected,)),width='stretch')
                st.dataframe(db.rows('SELECT id,content_hash,captured_at FROM job_snapshots WHERE job_id=?',(selected,)),width='stretch')
                st.dataframe(db.rows('SELECT * FROM verification_events WHERE job_id=? ORDER BY id DESC',(selected,)),width='stretch')
            with st.form('user_action'):
                action=st.selectbox('Marcar oferta',['favorita','pendiente','quiero solicitar','solicitada','descartada','respuesta recibida','entrevista','rechazada','oferta recibida','seguimiento'])
                notes=st.text_area('Notas personales')
                application_date=st.text_input('Fecha de candidatura opcional (AAAA-MM-DD)')
                if st.form_submit_button('Guardar marca y notas'):
                    try:
                        if application_date: datetime.strptime(application_date,'%Y-%m-%d')
                        db.execute('INSERT INTO user_actions(job_id,action,notes,application_date,created_at) VALUES(?,?,?,?,?)',(selected,action,notes,application_date or None,now()))
                        st.success('Guardado en SQLite')
                    except ValueError: st.error('Fecha inválida; usar AAAA-MM-DD')
            st.dataframe(db.rows('SELECT * FROM user_actions WHERE job_id=? ORDER BY id DESC',(selected,)),width='stretch')
        else: st.write('Sin ofertas todavía. Carga el catálogo y ejecuta una búsqueda.')
    elif section=='coverage':
        st.subheader('Cobertura y reconciliación')
        st.write(report['scope'])
        st.json({k:v for k,v in report.items() if k not in {'sources','source_runs'}},expanded=False)
        st.dataframe(report['source_runs'],width='stretch',hide_index=True)
        st.download_button('Descargar informe de cobertura',coverage_markdown(report),file_name='cobertura.md')
    elif section=='sources':
        st.subheader('Catálogo ampliable y fuentes no cubiertas')
        if not db.rows('SELECT id FROM sources') and st.button('Cargar catálogo de fuentes comprobadas'):
            load_catalog(db); st.rerun()
        st.dataframe(db.rows('SELECT id,name,kind,url,enabled,permission,status,checked_at,last_success,notes FROM sources'),width='stretch',hide_index=True)
        with st.expander('Editar/importar catálogo YAML o CSV'):
            catalog=st.text_area('Catálogo YAML completo',export_sources(db),height=260)
            if st.button('Guardar catálogo YAML'):
                try:
                    count=import_sources(db,catalog)
                    (ROOT/'config/sources.yaml').write_text(export_sources(db),encoding='utf-8')
                    st.success(f'{count} fuentes guardadas; las ausentes no se eliminan')
                except Exception as exc: st.error(str(exc))
            upload=st.file_uploader('Importar catálogo de fuentes',type=['yaml','csv'],key='sources_upload')
            if upload and st.button('Importar fuentes del archivo'):
                try: st.success(f"{import_sources(db,upload.getvalue().decode('utf-8-sig'),'csv' if upload.name.endswith('.csv') else 'yaml')} fuentes importadas")
                except Exception as exc: st.error(str(exc))
            st.download_button('Exportar fuentes YAML',export_sources(db),file_name='sources.yaml')
            st.download_button('Exportar fuentes CSV',export_sources(db,'csv').encode('utf-8-sig'),file_name='sources.csv')
        st.subheader('Importar oferta omitida')
        url=st.text_input('URL pública del anuncio')
        if st.button('Importar URL e investigar omisión') and url: launch('import_url',{'url':url})
        csv_upload=st.file_uploader('Ofertas CSV: title,url; opcionales company,location,description,detail_complete',type=['csv'])
        if csv_upload and st.button('Importar ofertas CSV'):
            try: st.success(f"{len(import_csv(db,csv_upload.getvalue().decode('utf-8-sig'),profile))} publicaciones procesadas")
            except Exception as exc: st.error(str(exc))
        career_url=st.text_input('Página pública de carreras para descubrir ATS enlazados')
        if st.button('Examinar enlaces y ampliar cola de fuentes') and career_url: launch('discover',{'url':career_url})
        discoveries=db.rows('SELECT * FROM discovery_runs ORDER BY id DESC')
        if discoveries:
            st.dataframe(discoveries,width='stretch',hide_index=True)
            discovery_id=st.selectbox('Descubrimiento para continuar',[r['id'] for r in discoveries])
            if st.button('Continuar recursos pendientes de descubrimiento'):
                launch('discover',{'discovery_id':discovery_id})
            with st.expander('Enlaces candidatos y recursos pendientes; todavía no son ofertas verificadas'):
                st.dataframe(db.rows('SELECT * FROM discovery_resources WHERE discovery_id=?',(discovery_id,)),width='stretch')
                st.dataframe(db.rows('SELECT * FROM discovery_candidates WHERE discovery_id=?',(discovery_id,)),width='stretch')
        omission_url=st.text_input('Diagnosticar una omisión sin importar la oferta')
        if st.button('Consultar historial de la omisión') and omission_url:
            from corkjobradar.discovery import diagnose_omission
            diagnosis=diagnose_omission(db,omission_url)
            db.event('INVESTIGAR_OMISION',diagnosis)
            st.json(diagnosis)
    elif section=='profile':
        st.subheader('Perfil local editable')
        st.caption('Pesos: suma 100. accepted_time_windows admite noches,rotacion,guardias,fines_semana; vacío no limita. '
                   'Ollama es opcional y requiere modelo local ya instalado. No se envían datos a servicios de IA externos.')
        profile_text=st.text_area('Configuración YAML',yaml.safe_dump(profile,allow_unicode=True,sort_keys=False),height=360)
        if st.button('Guardar perfil'):
            try: save_profile(yaml.safe_load(profile_text)); st.success('Guardado. Usa Reanalizar pendientes para actualizar el encaje.')
            except Exception as exc: st.error(str(exc))
        cv=st.file_uploader('CV voluntario local PDF/DOCX; solo propone competencias',type=['pdf','docx'])
        if cv and st.button('Extraer propuestas del CV sin guardarlo'):
            try: st.session_state['cv_candidates']=cv_skills(cv.getvalue(),cv.name)
            except Exception as exc: st.error(str(exc))
        if 'cv_candidates' in st.session_state:
            confirmed=st.multiselect('Confirma qué competencias persistir',st.session_state['cv_candidates'])
            if st.button('Confirmar y guardar competencias seleccionadas'):
                updated=load_profile(); updated['skills']=sorted(set(updated['skills']+confirmed)); save_profile(updated)
                st.success('Guardadas únicamente las competencias confirmadas')
        st.subheader('Transporte: comprobación manual con evidencia')
        if selected:
            from corkjobradar.ui_transport import assisted_transport
            assisted_transport(db,selected,profile,launch)
            st.write('Oferta seleccionada: '+ids[selected]['title'])
            with st.form('route_evidence'):
                mode=st.selectbox('Medio',['bus','bicycle','car_reference'])
                transfers=st.number_input('Transbordos de autobús',min_value=0,value=0,step=1)
                viability=st.selectbox('Resultado de la comprobación',['NO_VERIFICADA','VERIFICADA','NO_VIABLE'])
                evidence_url=st.text_input('Fuente verificable de la ruta')
                destination=st.text_input('Centro de trabajo/destino publicado')
                origin_access=st.text_input('Acceso desde Ballinlough a la parada o inicio')
                outbound=st.text_input('Ida: línea, paradas, horario y caminata/bici')
                return_trip=st.text_input('Vuelta: línea, paradas, horario y caminata/bici')
                duration=st.number_input('Duración comprobada en minutos (0 = desconocida)',min_value=0,value=0)
                compatible=st.checkbox('He contrastado ida y vuelta con el turno y los días de trabajo')
                valid_until=st.date_input('Evidencia de transporte válida hasta (revisar al cambiar horario)',key='route_valid_until')
                route_notes=st.text_area('Notas y evidencia literal; causa si NO_VIABLE')
                if st.form_submit_button('Guardar comprobación manual'):
                    if viability=='VERIFICADA' and (not evidence_url.startswith(('https://','http://')) or not destination or (mode!='car_reference' and not all([origin_access,outbound,return_trip,compatible])) or (mode=='car_reference' and not duration)):
                        st.error('Faltan pruebas; usar NO_VERIFICADA hasta contrastar la ruta.')
                    else:
                        details={'destination':destination,'origin_access':origin_access,'outbound':outbound,'return':return_trip,'shift_compatible':compatible,
                                 'duration_minutes':duration or None,'notes':route_notes,'method':'Comprobación manual declarada por usuario','valid_until':valid_until.isoformat()}
                        db.execute('INSERT INTO commute_checks(job_id,origin,mode,transfers,viability,evidence_url,checked_at,details) VALUES(?,?,?,?,?,?,?,?)',
                                   (selected,profile['origin_neighborhood'],mode,transfers,viability,evidence_url,now(),json.dumps(details,ensure_ascii=False)))
                        analyze_job(db,selected,profile); st.success('Comprobación y nuevo análisis guardados')
        else: st.write('Selecciona una oferta cuando existan resultados.')
    elif section=='history':
        runs=db.rows('SELECT id,status,started_at,finished_at,heartbeat,message FROM scan_runs ORDER BY id DESC')
        st.dataframe(runs,width='stretch',hide_index=True)
        if runs:
            resume_id=st.selectbox('Ejecución para continuar',[r['id'] for r in runs])
            if st.button('Continuar búsqueda interrumpida'):
                try: prepare_resume(db,resume_id); spawn_worker(resume_id); st.success(f'Ejecución {resume_id} reanudada')
                except Exception as exc: st.error(f'No se puede reanudar con un trabajador activo: {exc}')
        with st.expander('Errores, omisiones y tareas pendientes'):
            st.dataframe(db.rows('SELECT * FROM source_errors ORDER BY id DESC'),width='stretch')
            st.dataframe(db.rows("SELECT * FROM audit_events WHERE kind='INVESTIGAR_OMISION' ORDER BY id DESC"),width='stretch')
            st.dataframe(db.rows("SELECT * FROM task_queue WHERE status<>'done' ORDER BY id"),width='stretch')
        if st.button('Exportar todo'):
            try:
                st.session_state['exported']=export_all(db)
                st.success(f"Exportación con {st.session_state['exported']['count']} ofertas y auditoría")
            except Exception as exc: st.error(str(exc))
        if 'exported' in st.session_state:
            for label in ('xlsx','csv','json','coverage'):
                path=Path(st.session_state['exported'][label])
                st.download_button('Descargar '+label.upper(),path.read_bytes(),file_name=path.name,key='download_'+label)
        st.caption('Archivos locales: '+str(ROOT/'exports'))
