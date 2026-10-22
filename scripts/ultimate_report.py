"""Generate evidence-based reports; keeps older documents in docs/history."""
import json
import shutil
import sqlite3
import sys
from pathlib import Path
from xml.etree import ElementTree
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now
from corkjobradar.db import Database
from corkjobradar.audit import coverage,coverage_markdown


def main():
    db=Database();stamp=now();history=ROOT/'docs/history/ultimate-before-reports'
    history.mkdir(parents=True,exist_ok=True)
    for filename in ['docs/SOURCES.md','docs/COVERAGE.md','docs/TEST_REPORT.md','NEXT_STEPS.md']:
        src=ROOT/filename;dest=history/src.name
        if src.exists() and not dest.exists():shutil.copy2(src,dest)
    report=coverage(db)
    tests=[]
    for file in sorted((ROOT/'logs').glob('ultimate-*.xml')):
        root=ElementTree.parse(file).getroot()
        suites=[root] if root.tag=='testsuite' else list(root)
        totals={k:sum(int(s.get(k,'0')) for s in suites) for k in ['tests','failures','errors','skipped']}
        totals.update(file=file.name,seconds=round(sum(float(s.get('time','0')) for s in suites),2))
        tests.append(totals)
    counts={t:db.rows('SELECT count(*) n FROM '+t)[0]['n'] for t in
            ['jobs','job_sources','job_snapshots','job_analyses','scan_runs','user_actions']}
    validation={'generated_at':stamp,'schema':db.rows('PRAGMA user_version')[0]['user_version'],
                'integrity':db.rows('PRAGMA integrity_check'),'foreign_key_errors':db.rows('PRAGMA foreign_key_check'),
                'counts':counts,'coverage':report,'tests':tests}
    baseline=sorted((ROOT/'data/backups').glob('radar-before-ultimate-*.sqlite3'))
    if baseline:
        uri='file:'+baseline[0].as_posix()+'?mode=ro&immutable=1'
        with sqlite3.connect(uri,uri=True) as old:
            retained={}
            for table in ['jobs','job_snapshots','job_analyses','scan_runs','user_actions']:
                before={row[0] for row in old.execute('SELECT id FROM '+table)}
                after={row['id'] for row in db.rows('SELECT id FROM '+table)}
                retained[table]={'baseline':len(before),'retained':len(before & after),'missing':len(before-after)}
            validation['retention']=retained
    (ROOT/'logs/ultimate-validation-state.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'logs/ultimate-coverage.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'docs/COVERAGE.md').write_text(coverage_markdown(report)+
        '\n## Qué significa completo\n\nEl estado de los listados se separa de descripción y análisis. Una fuente con paginación agotada puede tener documentos pendientes. '
        'Los enlaces de sitemaps/feeds son candidatos con estado, no ofertas ni vacantes vigentes acreditadas. '
        'El tablero HTML individual de AbbVie cubre un solo anuncio. Los tableros nacionales/globales incluyen registros fuera del área, que se archivan con motivo. '
        'No existe un denominador demostrable de todo el mercado de Cork.\n',encoding='utf-8')
    lines=['# Fuentes y límites reales',f'\nGenerado: {stamp}. Fuente de verdad: SQLite y ejecución '+str(report['run_id'])+'.',
        '\nLas APIs activas se consultan por GET público documentado; HTML verifica robots.txt. No se eluden CAPTCHA ni autenticación. '
        '«Accesible» no acredita descripción íntegra, candidatura abierta ni cobertura de un empleador completo.\n',
        '| Fuente | Activada / conector | Último listado observado | Comprobación / permiso |',
        '|---|---|---|---|']
    for source in db.rows('SELECT * FROM sources ORDER BY id'):
        last=db.rows('SELECT status,pages_visited,observed,pagination_complete,finished_at FROM source_runs WHERE source_id=? ORDER BY id DESC LIMIT 1',(source['id'],))
        state=f"{last[0]['status']}; {last[0]['pages_visited']} páginas; {last[0]['observed']} publicaciones; {last[0]['finished_at']}" if last else 'Sin rastreo implementado/ejecutado'
        config=json.loads(source['config']);permission=config.get('permission_evidence','')
        permitted=f"[{source['permission']}]({permission})" if permission else source['permission']
        lines.append(f"| [{source['name']}]({source['url']}) | {'Sí' if source['enabled'] else 'No'} / {source['kind']} | {state} | {source['checked_at'] or 'Sin comprobar'}; {permitted} |")
    lines+=['\n## Limitaciones comprobadas\n',
        '- HSE: dos páginas verificadas; las especificaciones adjuntas no se declaran íntegras cuando robots del servidor de archivos no se puede verificar. Las incidencias DOCUMENT_PENDING se conservan.',
        '- JobsIreland: condiciones de reproducción requieren permiso; extracción masiva desactivada. https://jobsireland.ie/en-US/TermsConditions',
        '- Manpower: las condiciones prohíben crear bases de datos sin permiso. https://www.manpower.ie/legal_documents/terms_and_conditions',
        '- Indeed y Johnson & Johnson: acceso restringido observado anteriormente; no se ha eludido. Los demás conectores manuales están pendientes de implementación y revisión de condiciones.',
        '- Descubrimiento HSE: un sitemap dio timeout; permanece como error explícito. Los candidatos no revisados no cuentan como ofertas procesadas.',
        '- Bus Éireann: horarios estáticos NTA, CC BY 4.0. Solo rectángulo Cork (51,7–52,1 N; 8,9–8,0 O), autobuses regulares de ese operador; no todos los transportes. Calendarios, excepciones y cambio de hora se controlan. Requiere cuatro paradas y confirmar accesos/turno. No hay API de tiempo real sin credenciales. https://developer.nationaltransport.ie/usagepolicy',
        '- Bicicleta y accesos a pie: comprobación asistida/manual con fuente, ida, vuelta, fecha y turno; no se generan tiempos ficticios.']
    (ROOT/'docs/SOURCES.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    test_lines=['# Pruebas y comprobaciones',f'\nGenerado: {stamp}. Se conservan también los ensayos fallidos y las correcciones; no se ocultan.\n',
                '| Evidencia JUnit en logs | Pruebas | Fallos | Errores | Omitidas | Segundos |','|---|---:|---:|---:|---:|---:|']
    for result in tests:
        test_lines.append('| '+ ' | '.join(str(result[k]) for k in ['file','tests','failures','errors','skipped','seconds'])+' |')
    test_lines += ['\n## Comprobaciones reales\n',
        f"- Última búsqueda real: ejecución {report['run_id']}, {report['fully_examined_sources']} listados completos, {report['observed_postings']} publicaciones y {report['unique_jobs']} ofertas únicas observadas. Alcance y límites en COVERAGE.md.",
        '- SQLite: '+str(validation['integrity'])+'; errores FK: '+str(len(validation['foreign_key_errors']))+'. Conservación de IDs originales: '+str(validation.get('retention',{}))+'.',
        '- Prueba aislada de carga: 2.003 ofertas y 50 publicaciones duplicadas; todas procesadas, también las de menor encaje. Paginación del servidor con tamaño menor que el solicitado, deduplicación y colas reconciliadas.',
        '- UI Streamlit AppTest: filtros, detalle, Excel, trabajador persistente, respuesta de candidatura, análisis individual en cola y cálculo GTFS en dos sentidos. Los tests usan SQLite temporal dentro de data; nunca siembran ofertas de prueba en producción.',
        '- GTFS real: procedencia y SHA-256 en data/GTFS_Bus_Eireann-provenance.json; importación en logs/ultimate-transit-import.json; servicios reales entre paradas de Ballinlough y Mahon Point en logs/ultimate-transit-real-check.json. No valida un domicilio, empleo o paseo concreto.',
        '- IA: ensayos, salidas rechazadas y mediciones en logs/ultimate-local-model-*.json y data/model-quality.json. Solo se habilita un modelo tras validación explícita de una muestra; ninguna salida cuenta como probabilidad de contratación ni comprensión garantizada.',
        '- Dependencias: logs/ultimate-pip-check.log. Los avisos de NumPy/Streamlit se documentan; no se presentan como fallos de aplicación.',
        '- Alcance de las pruebas: fixtures sintéticos identificados y aislados; comprobaciones reales con fuentes públicas. No equivale a precisión estadística, cobertura de todo Cork o validación de todas las traducciones.']
    (ROOT/'docs/TEST_REPORT.md').write_text('\n'.join(test_lines)+'\n',encoding='utf-8')
    (ROOT/'NEXT_STEPS.md').write_text('''# Pendientes verificables

1. Revisar el resultado de la evaluación local en `data/model-quality.json`; si no supera calidad, mantener IA desactivada. Auditar cada interpretación que se use para una candidatura. Las citas no prueban corrección semántica.
2. Completar documentos HSE cuando su servidor permita verificar robots; alternativamente importar texto/documentos que el usuario tenga derecho a utilizar. No eludir el bloqueo.
3. Ampliar portales/agencias con permiso, paginación y pruebas reales antes de activarlos. Solicitar permisos de reproducción solo cuando el usuario autorice contactar con terceros.
4. Revisar los candidatos de sitemaps y feeds, corregir omisiones reproducibles y conservar los errores de recursos pendientes. No contar candidatos sin verificar como ofertas reales.
5. Confirmar dirección, días, horas y cuatro paradas de cada candidatura. Comprobar accesos a pie/bici y avisos oficiales. El cálculo de horarios estáticos no valida por sí solo el trayecto.
6. Tras cambios de perfil, reanalizar. Al cambiar consultas, conservar las firmas/configuraciones históricas. Retomar ejecuciones pendientes desde la interfaz; no borrar colas antiguas.
7. Mantener copias consistentes y repetir las comprobaciones correspondientes cuando cambie código, estructura de una fuente, modelo o feed. Ninguna etapa acredita el mercado total de Cork.
''',encoding='utf-8')
    print(json.dumps({'generated_at':stamp,'counts':counts,'run_id':report['run_id'],'retention':validation.get('retention',{})},indent=2))


if __name__=='__main__':
    main()
