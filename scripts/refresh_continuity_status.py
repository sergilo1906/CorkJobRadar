"""Refresh source/coverage documents from persisted evidence, preserving earlier reports."""
import json
from pathlib import Path
import shutil
import sys
from xml.etree import ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now
from corkjobradar.db import Database
from corkjobradar.audit import coverage,coverage_markdown


def main():
    db=Database();generated=now();archive=ROOT/'docs/history/before-continuity';archive.mkdir(parents=True,exist_ok=True)
    for name in ('SOURCES.md','COVERAGE.md','TEST_REPORT.md'):
        src=ROOT/'docs'/name
        if src.exists() and not (archive/name).exists():shutil.copyfile(src,archive/name)
    sources=db.rows('SELECT * FROM sources ORDER BY name');runs=db.rows('SELECT * FROM source_runs ORDER BY id DESC')
    last={}
    for run in runs:last.setdefault(run['source_id'],run)
    def safe(value):return str(value if value is not None else 'desconocido').replace('|','/').replace('\n',' ')
    table=['| Fuente | Conector | Activa | Permiso | Último recorrido | Páginas/publicaciones | Última comprobación | URL |',
           '|---|---|---|---|---|---|---|---|']
    for s in sources:
        r=last.get(s['id'],{})
        table.append('| '+' | '.join(map(safe,[s['name'],s['kind'],'Sí' if s['enabled'] else 'No',s['permission'],
            (str(r.get('run_id'))+': '+str(r.get('status'))) if r else s['status'],
            str(r.get('pages_visited','?'))+'/'+str(r.get('observed','?')),s.get('checked_at'),'[Abrir]('+s['url']+')']))+' |')
    text='# Fuentes y capacidades actuales — EN DESARROLLO\n\nGenerado desde SQLite: '+generated+'. '+str(len(sources))+' fuentes registradas; '+str(sum(s['enabled'] for s in sources))+' activas.\n\n'
    text+='Cada fecha/recorrido procede de su fuente y ejecución. No son una única búsqueda simultánea ni cobertura de todo Cork. Un GET de salud no acredita paginación completa.\n\n'+'\n'.join(table)+'\n\n## Límites y procedencias\n\n'
    for s in sources:text+='- **'+s['name']+'**: '+s['notes']+'\n'
    text+='\nConectores con pruebas offline y uso real: Greenhouse, Lever, Ashby, SmartRecruiters, HSE (listado; documentos pendientes) y HTML de anuncios individuales. Los portales manuales/desactivados no se consideran compatibles. My Greenhouse/AutoApply no se deduce del soporte GET de búsqueda. No se eluden robots, CAPTCHA ni restricciones.\n'
    text+='\nNuevas JYSK/Securitas: registro de descubrimiento y GET en `logs/continuity-source-probes.json`; ejecución 11 (18+21 publicaciones), con fichas dentro de alcance y pendientes descargadas. Los enlaces indexados que ya expiraron no se inventan como ofertas actuales.\n'
    text+='\nDescubrimiento ATS: [Job Board API de Greenhouse](https://docs.greenhouse.io/job-board) y [Postings API oficial de Lever, incluidas instancias EU](https://github.com/lever/postings-api). Reconocer un enlace solo registra una fuente pendiente; no autoriza formularios ni envíos.\n'
    (ROOT/'docs/SOURCES.md').write_text(text,encoding='utf-8')
    report=coverage(db)
    extra='\n## Alcance técnico actual\n\nEl informe anterior corresponde solo a las fuentes seleccionadas en esa ejecución. Las demás figuran como no cubiertas por esa ejecución aunque tengan comprobaciones anteriores. HSE y sus documentos se auditan por separado; no se declara descripción íntegra por tener una ficha HTML.\n\nHay descubrimiento reanudable de sitemaps y feeds y diagnóstico local de omisiones. GTFS Bus Éireann ofrece calendario y servicios directos; no demuestra acceso a pie/bici ni compatibilidad con un turno desconocido. DNS se fija al conectar. El análisis profundo se mantiene separado de la traducción y de la revisión humana. AutoApply real permanece bloqueado.\n'
    (ROOT/'docs/COVERAGE.md').write_text(coverage_markdown(report)+extra,encoding='utf-8')
    tests={}
    for path in sorted((ROOT/'logs').glob('*.xml')):
        if not (path.name.startswith(('continuity-','translation-','it-only-','operational-','verified-flow-','external-adapter-','human-intervention-','assisted-delivery-','usable-it-','it-50km-','local-runtime-','ui-redesign-','academic-reevaluation-'))):continue
        node=ET.parse(path).getroot();suites=list(node) if node.tag=='testsuites' else [node]
        tests[path.name]={k:sum(float(s.get(k,0)) for s in suites) for k in ('tests','failures','errors','skipped','time')}
    testtext='# Pruebas actuales — EN DESARROLLO\n\nGenerado: '+generated+'. Windows/Python y SQLite comprobados; envíos reales OFF. Las suites se solapan y no deben sumarse.\n\n| Evidencia | Casos | Fallos | Errores | Omitidas | Segundos |\n|---|---:|---:|---:|---:|---:|\n'
    for name,t in tests.items():testtext+='| '+name+' | '+' | '.join(str(round(t[k],3)) for k in ('tests','failures','errors','skipped','time'))+' |\n'
    latest_name=next((name for name in ('academic-reevaluation-full.xml','ui-redesign-full.xml','local-runtime-full.xml','it-50km-final-full.xml','usable-it-final-full.xml','human-intervention-final.xml','external-adapter-final.xml','verified-flow-final.xml','verified-flow-full.xml','operational-final.xml','operational-full.xml','it-only-full.xml','continuity-reading-final.xml') if name in tests and not any(tests[name][k] for k in ('failures','errors','skipped'))),'continuity-reading-final.xml')
    latest=tests.get(latest_name)
    if latest:
        testtext+='\nÚltima suite completa histórica documentada: **'+str(int(latest['tests']))+' casos**, '+str(int(latest['failures']))+' fallos, '+str(int(latest['errors']))+' errores y '+str(int(latest['skipped']))+' omitidos (`'+latest_name+'`). Las suites anteriores no se suman.\n'
    if latest_name=='academic-reevaluation-full.xml':
        testtext+='\nReevaluación académica22/10: completa590 PASS, anterior a los últimos casos de redacción/modalidad/plazo, cubiertos por las regresiones posteriores listadas arriba (166/63/106/38 y comprobación final de interfaz). No sumar suites solapadas.613 ofertas reevaluadas y todas las1185 evaluaciones iniciales retenidas;2411 análisis al cierre tras versionar las reglas.56 IT confirmadas;15 locales para revisión (2 prioritarias/13 condicionadas),2 adicionales con funciones IT pendientes.36 normalizaciones Ashby documentadas con snapshots. CV2 pendiente,22 hechos intactos, LIVE OFF. Chromium real escritorio/móvil y Excel56 filas; ninguna solicitud externa. [Uso, resultados y límites](ACADEMIC_REEVALUATION_2026-10-22.md).\n'
    if latest_name=='usable-it-final-full.xml':
        testtext+='\nVía asistida y descubrimiento: nueva regresión completa por cambios de identidad/lectura de requisitos; los fallos previos y correcciones se conservan. Pruebas posteriores dirigidas, si existen, figuran por separado y no se suman. Chromium verifica consentimiento de CV, portapapeles real, ZIP y justificante con identidad ficticia en base aislada; no hay envíos externos. Búsqueda real 15: 120 anuncios conservados y 59 dentro de alcance/pendientes analizados; total 579, 22 hechos intactos. SQLite v10 aditiva; LIVE OFF. [Uso y límites](CANDIDATURAS_IT_ASISTIDAS.md).\n'
    if 'assisted-delivery-regression.xml' in tests:
        targeted=tests['assisted-delivery-regression.xml']
        testtext+='\nContinuación 21/10: regresión dirigida de módulos modificados, **'+str(int(targeted['tests']))+' casos**, '+str(int(targeted['failures']))+' fallos, '+str(int(targeted['errors']))+' errores, '+str(int(targeted['skipped']))+' omitidos (`assisted-delivery-regression.xml`). No es una repetición completa ni se suma a 399. SQLite v9 aditiva; diagnóstico de siete ejes, paquete manual legible y justificantes EML/PDF cifrados con revisión por hash. Su revisión personal no acredita recepción externa. [Canales y alcance](AUTOAPPLY_CHANNELS_2026-10-21.md).\n'
    if latest_name=='external-adapter-final.xml':
        testtext+='\nIntegración externa: inventario de todas las ofertas y adaptador Recruitee GET/preparación multipart comprobados con esquema público real e identidad ficticia aislada. POST/recibo del servidor propio no acreditan ATS. No se ha ejecutado envío externo ni hay candidatura compatible lista; LIVE OFF. Chromium de la UI real y conservación en ambas bases verificados en `logs/external-adapter-browser.json` y `logs/external-adapter-production-audit.json`. El primer fallo de selector del script de navegador se conserva junto a la ejecución corregida. [Alcance y pendientes](AUTOAPPLY_EXTERNAL_ADAPTER.md), [revisión de vacantes](FIRST_APPLICATION_REVIEW.md).\n'
    if latest_name=='human-intervention-final.xml':
        testtext+='\nIntervención humana: CAPTCHA/MFA simulados en servidor propio, campos conservados en la misma sesión, continuación revalidada, caducidad/reconstrucción y recibo local diferenciado. Pruebas con navegador visible y proceso independiente; no se ejecutó desafío ni candidatura externos. Modos LinkedIn/Indeed manuales y redirecciones con permiso separado. SQLite v8 aditiva y LIVE OFF. Primeros fallos y correcciones conservados. [Alcance y procedimiento](AUTOAPPLY_HUMAN_INTERVENTION.md).\n'
    if latest_name=='it-50km-final-full.xml':
        testtext+='\nPolítica amplia IT 50 km / mínimo solicitado hasta 3 años: distancias 49/50/51, rangos/preferibles/máximos/meses, dudas menores como advertencias sin inventar experiencia, incompatibilidades acreditadas, origen DPAPI/centro/versiones, selección independiente de permisos, cola completa/idempotencia/concurrencia/leases/reinicio, CV aprobado/paquete real local/LinkedIn y no repetición de incertidumbre. SQLite v11 aditiva; 579 ofertas/22 hechos preservados y LIVE OFF. Chromium local de paquete y producción real comprobados, ninguna recepción ATS externa acreditada. Fallos iniciales corregidos y resultados conservados. [Reglas, uso y límites](IT_50KM_POLICY.md). Auditoría `logs/it-50km-production-audit.json` y UI `logs/it-50km-production-browser.json`.\n'
    if latest_name=='local-runtime-full.xml':
        testtext+='\nSupervisor Windows local: horario persistente, bloqueo físico único, PID/creación, cierre de pestaña, muerte/reinicio de procesos propios y botones Streamlit comprobados. Saltos de reloj/suspensión simulados; no se suspendió ni reinició Windows. GET real mediante supervisor en copia aislada: tres fuentes completas y análisis/detalle, sin candidaturas ni cambios en la base principal durante ese ensayo. Inicio al entrar en Windows solo ofrecido para instalación manual, no activado. LIVE OFF. [Funcionamiento y protocolo de ensayo del equipo](LOCAL_RUNTIME_WINDOWS.md).\n'
        if 'local-runtime-final-check.xml' in tests:
            targeted=tests['local-runtime-final-check.xml']
            testtext+='\nRegresión final posterior: **'+str(int(targeted['tests']))+' casos**, '+str(int(targeted['failures']))+' fallos, '+str(int(targeted['errors']))+' errores, '+str(int(targeted['skipped']))+' omitidos (`local-runtime-final-check.xml`). Cubre runtime/navegador/selección IT/formularios y remotos masivos sujetos a autorización adicional. No se suma a la completa ni acredita envíos externos. Ciclo real principal posterior completado: 581 ofertas/22 hechos, LIVE OFF; consultar `logs/local-runtime-production-cycle.json` y auditoría de conservación.\n'
    if latest_name=='ui-redesign-full.xml':
        testtext+='\nInterfaz de seis áreas, navegación móvil, consultas en lote/caché, CV por versión, formularios por pasos y controles persistentes. Completa568; posteriores52 y24 solapadas cubren los ajustes finales, sin sumar. Chromium30 vistas/cinco resoluciones y16 subpantallas; flujo asistido y CAPTCHA propio solo con identidades sintéticas, cero recepción empresarial. CV pendiente y LIVE OFF; cantidades actuales en el checkpoint/panel. Actualización22/10: DAM terminado/examen aprobado por confirmación del usuario, CV2 pendiente, historial cifrado conservado; diez pruebas dirigidas y Chromium de producción. Incidencia de aislamiento y conservación auditadas, sin ocultar actualización de metadatos históricos. [Mapa, uso, pruebas y límites](UI_REDESIGN.md).\n'
    testtext+='\nAutoApply exige funciones IT confirmadas en el backend antes de evaluar, preparar y realizar la comprobación final; las políticas generales anteriores requieren sustitución y nueva autorización IT. CV PDF: primera página separada; anexos fuera del CV y sin autorización automática. Los datos profesionales requieren aprobación expresa; su estado vigente consta en el checkpoint. La aprobación de hechos no aprueba por sí sola el documento final ni una política de envío. LIVE permanece OFF. Evidencias y límites: `docs/AUTOAPPLY_IT_ONLY.md`.\n'
    testtext+='\nLa referencia al recuperar era 151 casos (continuity-baseline). Ensayos GPU: bases separadas y reportes `translation-evaluation-*.json`, incluidos los fallos; ausencia de errores mecánicos no acredita exactitud semántica. La primera carga fue rechazada por RAM insuficiente, sin eludir el control. Revisar checkpoint para la versión del modelo/proveedor efectivamente aprobada.\n\nRegresiones: Offer/beneficios no se convierten en requisitos; separadores no son citas; cada pasaje queda trazado; números, negaciones y nombres protegidos; fecha/hora límite con zona y ambigüedad DST; HSE conserva fecha original y normalización. Las pruebas históricas previas permanecen en `docs/history/before-continuity/` y el informe AutoApply separado.\n'
    testtext+='\nComando reproducible: `.\\.venv\\Scripts\\python.exe -m pytest -q --basetemp=data\\pytest-next --junitxml=logs\\continuity-next.xml`. No ejecutar pruebas destructivas en producción ni anunciar live compatible sin ensayo autorizado.\n'
    testtext+='\n`continuity-experience-before.xml` reproduce intencionadamente dos defectos anteriores a la corrección (historia de empresa atribuida al candidato); `continuity-experience-after.xml` comprueba la corrección. No son fallos pendientes. Nuevas barreras prefinal: fecha límite, duplicado manual y cuota se revisan de nuevo. Resoluciones manuales no confirman recepción externa; el reintento solo prepara documentos de simulación.\n'
    testtext+='\n`continuity-current.xml` conserva un fallo Windows WinError 5 al reemplazar un checkpoint. Se corrigió con temporal único y reintentos limitados conservando el archivo previo; `continuity-fixed.xml` y la prueba de bloqueo transitorio verifican la corrección. Consultar `continuity-verified.xml` para la suite completa posterior. La conservación del historial se comprueba por EXCEPT contra la copia de recuperación en `logs/continuity-data-preservation.json`; no se restauró sobre producción.\n'
    testtext+='\nRevisión semántica adicional: dos errores reales de traducción corregidos mediante correspondencias literales revisadas con fuente/hash, conservando las salidas originales (deployments y personal ocasional). Regresión e integración: `continuity-reading-qa.xml`. El modelo continúa como lector asistido limitado y no acredita análisis semántico completo. UI real Chromium: `logs/autoapply-ui-browser.json`; IDs de exportación XLSX/CSV/JSON: `logs/continuity-export-check.json`; doctors y bloqueo LIVE con código 2: `logs/continuity-cli-check.json`. No hubo envíos reales.\n'
    (ROOT/'docs/TEST_REPORT.md').write_text(testtext,encoding='utf-8')
    state={'generated_at':generated,'project_status':'EN DESARROLLO','counts':{t:db.rows('SELECT COUNT(*) n FROM '+t)[0]['n'] for t in ('jobs','job_analyses','sources','scan_runs','application_attempts','user_actions')},
           'integrity':db.rows('PRAGMA integrity_check'),'foreign_keys':db.rows('PRAGMA foreign_key_check'),'coverage':report,'tests':tests}
    (ROOT/'logs/continuity-current-state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'generated_at':generated,'counts':state['counts'],'integrity':state['integrity']}))


if __name__=='__main__':main()
