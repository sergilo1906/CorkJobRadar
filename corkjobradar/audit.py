from collections import Counter
import json
from .config import now

SCOPE_TEXT = ('IT dentro del radio de referencia de ~60 minutos en coche desde Ballinlough, Cork (sin asumir coche propio); '
              'NO IT Cork City o ruta directa en un solo autobús / bicicleta; remoto elegible; accesibilidad no verificada separada.')


def analysis_inventory(db):
    """Disjoint current states across ALL local jobs, independent of the selected scan."""
    rows=db.rows('''SELECT j.id,j.scope,j.detail_complete,j.content_hash,a.content_hash analyzed_hash,
        a.status,json_extract(a.result,'$.depth') depth,
        json_extract(a.result,'$.semantic.passages_total') passages_total,
        json_extract(a.result,'$.semantic.passages_translated') passages_translated
        FROM jobs j LEFT JOIN job_analyses a ON a.id=(SELECT id FROM job_analyses
        WHERE job_id=j.id AND COALESCE(json_extract(result,'$.model_validation'),'') NOT IN ('RECHAZADO','EN_EVALUACION')
        ORDER BY id DESC LIMIT 1)''')
    states=Counter();translated=0;passages=0
    for row in rows:
        if row['scope']=='FUERA_DE_ALCANCE':state='ARCHIVADA_FUERA_DE_ALCANCE'
        elif not row['detail_complete']:state='TEXTO_INCOMPLETO'
        elif row['analyzed_hash'] and row['analyzed_hash']!=row['content_hash']:state='ANALISIS_DESACTUALIZADO'
        elif row['status']=='COMPLETO':state='ANALISIS_REVISADO_COMPLETO'
        elif str(row['depth']).startswith('LECTURA_LOCAL_ES'):
            state='LECTURA_PARCIAL' if row['depth'].endswith('PARCIAL') else 'LECTURA_POR_REVISAR'
        elif row['status'] is None:state='SIN_ANALISIS'
        else:state='ANALISIS_BASICO_O_PROFUNDO_PENDIENTE'
        states[state]+=1
        if state in {'LECTURA_PARCIAL','LECTURA_POR_REVISAR','ANALISIS_REVISADO_COMPLETO'}:
            passages+=row['passages_total'] or 0;translated+=row['passages_translated'] or 0
    return {'all_stored_jobs':len(rows),'exclusive_states':dict(states),'reconciled':sum(states.values())==len(rows),
            'current_reading_passages_total':passages,'current_reading_passages_translated':translated,
            'note':'Inventario global actual; una lectura traducida no equivale a análisis completo. Versiones antiguas y experimentales no se suman.'}

def coverage(db,run_id=None):
    if run_id is None:
        runs = db.rows('SELECT r.* FROM scan_runs r WHERE EXISTS(SELECT 1 FROM source_runs s WHERE s.run_id=r.id) ORDER BY r.id DESC LIMIT 1')
        if not runs:
            runs=db.rows('SELECT * FROM scan_runs ORDER BY id DESC LIMIT 1')
        run_id = runs[0]['id'] if runs else None
    run = db.rows('SELECT * FROM scan_runs WHERE id=?',(run_id,)) if run_id else []
    sources = db.rows('SELECT * FROM sources ORDER BY id')
    sr = db.rows('SELECT * FROM source_runs WHERE run_id=? ORDER BY id',(run_id,)) if run_id else []
    jobs = db.rows('SELECT DISTINCT j.* FROM jobs j JOIN run_jobs r ON r.job_id=j.id WHERE r.run_id=?',(run_id,)) if run_id else db.rows('SELECT * FROM jobs')
    target = [j for j in jobs if j['scope'] != 'FUERA_DE_ALCANCE']
    analyzed={r['job_id'] for r in db.rows('SELECT DISTINCT job_id FROM job_analyses')}
    groups = Counter()
    for job in target:
        status = job['analysis_status']
        group = 'completo' if status=='COMPLETO' else 'basico_o_parcial' if status in {'PARCIAL_POR_DATOS','REVISIÓN_MANUAL'} and job['id'] in analyzed else 'error' if status=='ERROR' else 'pendiente'
        groups[group] += 1
    observed = db.rows('SELECT count(*) AS n FROM run_jobs WHERE run_id=?',(run_id,))[0]['n'] if run_id else db.rows('SELECT count(*) AS n FROM job_sources')[0]['n']
    complete = sum(s['status']=='completed' and s['pagination_complete']==1 for s in sr)
    partial = sum(s['status'] in {'partial','error','running','pending'} for s in sr)
    blocked = sum(s['status']=='blocked' for s in sr)
    visited = {s['source_id'] for s in sr if s['status']=='completed' and s['pagination_complete']==1}
    selected = {s['source_id'] for s in sr}
    enabled = {s['id'] for s in sources if s['enabled']}
    uncovered = []
    for source in sources:
        if source['id'] in visited:continue
        current=next((r for r in sr if r['source_id']==source['id']),None)
        reason=(current['message'] or current['status']) if current else (
            'NO_SELECCIONADA_EN_ESTA_EJECUCION' if source['enabled'] else 'DESACTIVADA_NO_SELECCIONADA')
        uncovered.append({'source':source['id'],'name':source['name'],'reason':reason,
                          'selected_in_run':current is not None,'catalog_status':source['status'],
                          'catalog_note':source['notes']})
    listing_complete=bool(run and run[0]['status']=='completed' and complete==len(sr) and len(sr)>0)
    descriptions_complete=all(j['detail_complete'] for j in target)
    analyses_complete=bool(target) and groups.get('completo',0)==len(target)
    result = {'generated_at':now(),'run_id':run_id,'scope':SCOPE_TEXT,'registered_sources':len(sources),
              'enabled_sources_current_catalog':len(enabled),'selected_sources':len(selected),
              'selected_source_ids':sorted(selected),'enabled_unselected_source_ids':sorted(enabled-selected),
              'selection_note':'Completitud del listado referida solo a fuentes seleccionadas; catálogo activo medido al generar el informe, no al iniciar la búsqueda.',
              'inaccessible_sources_catalog':sum(s['status'] in {'BLOQUEADA','BLOQUEADA_RESTRINGIDA','ERROR_DE_ACCESO','ERROR'} for s in sources),
              'fully_examined_sources':complete,'partial_sources':partial,'blocked_sources_in_run':blocked,
              'uncovered_sources':uncovered,'observed_postings':observed,'unique_jobs':len(jobs),
              'duplicate_publications':observed-len(jobs),'target_or_pending_jobs':len(target),
              'archived_out_of_scope':len(jobs)-len(target),
              'full_descriptions_in_scope':sum(j['detail_complete'] for j in target),
              'full_descriptions_all':sum(j['detail_complete'] for j in jobs),
              'talent_pool_posts':sum(json.loads(j['raw']).get('_listing_type')=='BOLSA_DE_TALENTO_SIN_VACANTE_CONCRETA' for j in jobs),
              'analysis_groups':dict(groups),'reconciled':sum(groups.values())==len(target),
              'geography':dict(Counter(j['scope']+':'+j['category'] for j in jobs)),
              'changes':dict(Counter(r['change_status'] for r in db.rows('''SELECT job_id,CASE
                WHEN MAX(change_status='NEW') THEN 'NEW' WHEN MAX(change_status='CHANGED') THEN 'CHANGED'
                WHEN MAX(change_status='REPEATED') THEN 'REPEATED' ELSE 'LEGACY_UNKNOWN' END change_status
                FROM run_jobs WHERE run_id=? GROUP BY job_id''',(run_id,)))) if run_id else {},
              'listing_coverage_status':'COMPLETA_PARA_FUENTES_ACCESIBLES' if listing_complete else 'PARCIAL',
              'description_coverage_status':'INTEGRAS' if descriptions_complete else 'DESCRIPCIONES_PENDIENTES',
              'analysis_coverage_status':'COMPLETA_REVISADA' if analyses_complete else 'BASICA_PARCIAL_O_PENDIENTE',
              'status':'COMPLETA_PARA_FUENTES_ACCESIBLES' if listing_complete and descriptions_complete and analyses_complete else 'LISTADOS_COMPLETOS_ANALISIS_PARCIAL' if listing_complete else 'PARCIAL',
              'market_coverage':'DESCONOCIDO: no existe denominador del mercado total',
              'state_note':'Estados actuales de las ofertas observadas en la ejecución; snapshots originales conservados',
              'source_runs':sr,'sources':sources}
    result['global_analysis_inventory']=analysis_inventory(db)
    assert result['reconciled'], 'Fallo de reconciliación: oferta perdida entre estados'
    return result

def coverage_markdown(report):
    return ('# Cobertura Cork Job Radar\n\n'
            f"Generado: {report['generated_at']} · Ejecución: {report['run_id']} · Estado: {report['status']}\n\n"
            f"Listado: {report.get('listing_coverage_status')}; descripciones: {report.get('description_coverage_status')}; análisis: {report.get('analysis_coverage_status')}.\n\n"
            f"Alcance vigente: {report['scope']}\n\n"
            f"Fuentes registradas: {report['registered_sources']}; examinadas completamente: {report['fully_examined_sources']}; "
            f"parciales: {report['partial_sources']}; bloqueadas en ejecución: {report['blocked_sources_in_run']}.\n\n"
            f"Seleccionadas en esta ejecución: {report['selected_sources']}; activas actualmente: {report['enabled_sources_current_catalog']}; "
            f"activas no seleccionadas: {len(report['enabled_unselected_source_ids'])}. {report['selection_note']}\n\n"
            f"Anuncios observados: {report['observed_postings']}; ofertas únicas: {report['unique_jobs']}; "
            f"objetivo o accesibilidad pendiente: {report['target_or_pending_jobs']}; archivadas fuera de alcance: {report['archived_out_of_scope']}; "
            f"texto íntegro en alcance: {report['full_descriptions_in_scope']}.\n\n"
            f"Estados exclusivos del análisis en alcance: {report['analysis_groups']}. Reconciliación: {report['reconciled']}.\n\n"
            f"{report['state_note']}. {report['market_coverage']}.\n\n"
            f"Inventario global actual de {report['global_analysis_inventory']['all_stored_jobs']} ofertas: "
            f"{report['global_analysis_inventory']['exclusive_states']}. "
            f"{report['global_analysis_inventory']['note']}\n\n"
            '## Fuentes pendientes o no cubiertas\n\n'+
            '\n'.join(f"- {s['name']} ({s['source']}): {s['reason']}" for s in report['uncovered_sources'])+'\n')
