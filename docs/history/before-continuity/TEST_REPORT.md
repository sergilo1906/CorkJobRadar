# Informe de pruebas y comprobaciones

Actualización AutoApply 19/10/2026: baseline nuevo de 100 pruebas; integración en simulación y nueva suite/auditoría en [AUTOAPPLY_TEST_REPORT.md](AUTOAPPLY_TEST_REPORT.md). El informe de 63 casos siguiente es histórico y conserva su fecha. No acredita envíos automáticos reales.

Generado: 2026-10-19T12:16:14+01:00. Windows 11 10.0.26200, Python 3.12.4, entorno .venv del proyecto.

## Pruebas automatizadas

Última suite completa: `63` casos; fallos `0`; errores `0`; omitidos `0`; duración `74.671` segundos. Evidencia: logs/pytest-delivery.xml y logs/pytest-delivery.log. Tras traducir encabezados de Excel, las tres pruebas específicas de UI y XLSX también pasaron (logs/pytest-export-spanish.log).

Comandos ejecutados:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=data\pytest-delivery --junitxml=logs\pytest-delivery.xml
.\.venv\Scripts\python.exe -m pytest tests\test_ui.py tests\test_safety_and_states.py::test_excel_long_text_and_formula_injection -q --basetemp=data\pytest-export-spanish
powershell -NoProfile -ExecutionPolicy Bypass -File .\instalar.ps1
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m corkjobradar doctor
.\.venv\Scripts\python.exe -m corkjobradar sources --load
.\.venv\Scripts\python.exe -m corkjobradar sources --refresh
.\.venv\Scripts\python.exe -m corkjobradar scan --all
.\.venv\Scripts\python.exe -m corkjobradar verify --all
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

El instalador terminó con código 0 (logs/installer-final.log); pip check: sin dependencias rotas. doctor: SQLite integrity_check=ok. Los scripts de PowerShell se probaron en este proyecto, sin WSL ni modificación de políticas globales. La creación inicial de .venv y la instalación desde entorno vacío se ejecutaron; la repetición del instalador también fue correcta. Se reinició el servidor de este proyecto y se ejecutó iniciar.ps1: arranque correcto y /_stcore/health devolvió HTTP 200, cuerpo ok. Los .cmd son alternativas escritas, pendientes de una prueba interactiva de doble clic.

## Cobertura de la suite

- Fixtures por Greenhouse, Lever, Ashby, SmartRecruiters y HTML JSON-LD/microdatos.
- Fechas, salarios por unidad, turnos, deduplicación conservadora, alcance IT/NO IT, rutas sintéticas de cero/un transbordo, bicicleta y referencia IT sin coche.
- HTTP 403/404/429/503, Retry-After, timeout, gzip, límites de tamaño, robots, redirección a red privada, caché por Accept, cambios de estructura, páginas repetidas y tarjetas malformadas.
- 137 puestos en 7 páginas + 12 duplicados = 149 procedencias; 8 sin salario, 5 detalles fallidos y 3 cierres explícitos. Resultado exacto: 132 análisis básicos + 5 pendientes; al reanudar, solo cinco descargas y 137 análisis básicos. Sin datos sintéticos en producción.
- Interrupción tras 60 puestos: cursor persistido y recuperación hasta 137 sin perder registros.
- DB limpia, reinicio, candidaturas persistidas, importación de omisión incluso en 403, XLSX reabierto, CSV BOM, JSON y conservación de texto mayor de 32.767 caracteres.
- AppTest: seis pestañas, filtros, detalle, exportación y lanzamiento del trabajador sin bloquear UI. CV PDF vacío y DOCX sintético se procesan sin inventar competencias.
- Advertencias: cinco DeprecationWarning de Streamlit/NumPy en la suite UI; no son fallos. Ollama no fue encontrado en PATH; no se atribuye una prueba en vivo del proveedor profundo.

## Humo real de conectores

```json
{
  "generated_at": "2026-10-19T12:16:11+01:00",
  "run_id": 5,
  "scope": "IT dentro del radio de referencia de ~60 minutos en coche desde Ballinlough, Cork (sin asumir coche propio); NO IT Cork City o ruta directa en un solo autobús / bicicleta; remoto elegible; accesibilidad no verificada separada.",
  "registered_sources": 29,
  "inaccessible_sources_catalog": 2,
  "fully_examined_sources": 7,
  "partial_sources": 0,
  "blocked_sources_in_run": 0,
  "observed_postings": 273,
  "unique_jobs": 272,
  "duplicate_publications": 1,
  "target_or_pending_jobs": 61,
  "archived_out_of_scope": 211,
  "full_descriptions_in_scope": 61,
  "full_descriptions_all": 258,
  "talent_pool_posts": 2,
  "analysis_groups": {
    "basico_o_parcial": 61
  },
  "reconciled": true,
  "geography": {
    "FUERA_DE_ALCANCE:Otras": 144,
    "FUERA_DE_ALCANCE:Produccion": 7,
    "EN_ALCANCE:Otras": 12,
    "EN_ALCANCE:Produccion": 2,
    "FUERA_DE_ALCANCE:Tecnicos": 8,
    "FUERA_DE_ALCANCE:Almacen": 1,
    "ACCESIBILIDAD_PENDIENTE:Otras": 29,
    "ACCESIBILIDAD_PENDIENTE:IT": 17,
    "FUERA_DE_ALCANCE:IT": 51,
    "EN_ALCANCE:IT": 1
  },
  "status": "COMPLETA_PARA_FUENTES_ACCESIBLES",
  "market_coverage": "DESCONOCIDO: no existe denominador del mercado total",
  "state_note": "Estados actuales de las ofertas observadas en la ejecución; snapshots originales conservados"
}
```

Todos los conectores activos cuentan con ejecución real de extracción, persistencia y análisis básico. Los textos completos se muestran en la ficha local. El navegador real abrió http://127.0.0.1:8501 y su DOM mostró Cork Job Radar, seis pestañas y cero componentes de excepción. La herramienta de captura no permitía guardar bajo C:\Proyectos; se usó lectura del DOM y AppTest, sin afirmar una captura inexistente en el proyecto.

Validación XLSX real: 272 filas maestras y 23 hojas reabiertas con openpyxl. Archivo: C:\Proyectos\CorkJobRadar\exports\cork_job_radar_2026-10-19T121612_0100.xlsx. Manifiesto: logs/verified-export.json. La exportación corresponde a la ejecución de descubrimiento 5 y a estados actuales de datos.

Verificaciones actuales: [{"open_status": "ACCESS_BLOCKED", "n": 2}, {"open_status": "OPEN_CONFIRMED", "n": 122}, {"open_status": "OPEN_LIKELY", "n": 87}, {"open_status": "UNKNOWN", "n": 61}]. Las bloqueadas o reintentables permanecen visibles; no se consideran cerradas. El recorrido completo de los listados no garantiza que todos los formularios de solicitud sean accesibles.

La ejecución adicional de verificación 6 terminó parcial: 205 tareas procesadas y 67 reintentables tras suspender el dominio que devolvió un bloqueo. En el navegador se registraron ocho ERR_CONNECTION_REFUSED durante el reinicio intencionado del servidor; la conexión se recuperó y el DOM posterior mostró seis pestañas, datos reales y cero excepciones de componentes. Evidencia de comprobaciones finales: logs/final-checks.json.

## Fallos encontrados y corregidos

Instalación todavía en curso en la primera prueba de doctor; expresión salarial con espacios; fixture HTML mal construido; tratamiento de redirecciones; JSON frente a HTML por Accept; microdatos sin JSON-LD; página genérica vacía marcada incorrectamente completa; doble descompresión HTTP; separación de identidad canónica frente a URL publicada; caché independiente por Accept. Se preservaron los errores y se corrigió el estado histórico de la primera fuente HTML. Una ejecución de tests concurrente reutilizó basetemp y falló por bloqueo de Windows; se repitieron secuencialmente en directorios separados y pasaron.

La ejecución 4 de verificación fue cancelada para corregir los enlaces; el estado se conserva. Historial real:

```json
[
  {
    "id": 1,
    "status": "partial",
    "started_at": "2026-10-19T11:51:10+01:00",
    "finished_at": "2026-10-19T11:52:53+01:00",
    "message": ""
  },
  {
    "id": 2,
    "status": "completed",
    "started_at": "2026-10-19T11:54:37+01:00",
    "finished_at": "2026-10-19T11:54:39+01:00",
    "message": ""
  },
  {
    "id": 3,
    "status": "completed",
    "started_at": "2026-10-19T11:56:17+01:00",
    "finished_at": "2026-10-19T11:56:43+01:00",
    "message": ""
  },
  {
    "id": 4,
    "status": "cancelled",
    "started_at": "2026-10-19T12:00:23+01:00",
    "finished_at": "2026-10-19T12:01:53+01:00",
    "message": ""
  },
  {
    "id": 5,
    "status": "completed",
    "started_at": "2026-10-19T12:03:29+01:00",
    "finished_at": "2026-10-19T12:04:10+01:00",
    "message": ""
  },
  {
    "id": 6,
    "status": "partial",
    "started_at": "2026-10-19T12:07:53+01:00",
    "finished_at": "2026-10-19T12:10:55+01:00",
    "message": ""
  },
  {
    "id": 7,
    "status": "completed",
    "started_at": "2026-10-19T12:12:46+01:00",
    "finished_at": "2026-10-19T12:13:14+01:00",
    "message": ""
  }
]
```

## Lo no validado/no implementado

No se ha validado análisis semántico profundo en vivo, rutas automáticas, navegadores dinámicos de conectores, RSS/Atom/sitemaps ni parsers específicos de los portales/agencias desactivados. No se afirma cobertura total de Cork. Los análisis de reglas son PARCIAL_POR_DATOS, no COMPLETO.
