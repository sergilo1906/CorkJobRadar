# Cork Job Radar — progreso verificable

## AutoApply update — 2026-10-19

Mode A preserved; implementation is **simulation only**, live remains locked pending a separately authorized controlled trial and verified production adapters. Code/data backed up and restored in a separate copy. Baseline: 100 tests passed. SQLite v5 retains historical business rows; 415 production jobs receive persistent blocked plans with policy OFF, zero attempts/sends. Added policies, quotas/idempotency, Windows DPAPI vault, approved claims, real PDF/DOCX CV/letter generation, offline Playwright trials, seventh Streamlit tab, CLI and exports. Exact validation and remaining scope: `docs/AUTOAPPLY_TEST_REPORT.md`, `NEXT_STEPS.md`. Dated progress below is historical.

---

Actualizado: 2026-10-19T12:16:14+01:00. Especificación completa leída (360 líneas) y copiada desde la carpeta inicial. Proyecto: C:\Proyectos\CorkJobRadar.

## Fases

1. **Verificada:** entorno Windows/Python, .venv, dependencias fijadas, scripts, perfil Ballinlough, SQLite v1, CLI doctor y arranque Streamlit con datos locales reales.
2. **Verificada para lo anunciado:** cuatro ATS y HTML JSON-LD/microdatos, fixtures, errores/paginación y conectividad en vivo; URL/CSV manuales. No hay Playwright, RSS/Atom ni sitemaps implementados.
3. **Operativa y ampliable, cobertura parcial del mercado:** 29 fuentes comprobadas/registradas; 7 activadas; demás pendientes/restringidas. Investigación de portales, empresas y agencias documentada. Descubrimiento de ATS enlazados y edición/importación de catálogo disponibles.
4. **Verificada:** cola SQLite, cursor, cancelación, bloqueo de un trabajador, reanudación, snapshots, deduplicación con procedencias, reconciliación y alerta de recuentos. Prueba 137/7/12 exacta. No hay denominador del mercado total.
5. **Básico verificado, profundo pendiente:** textos en alcance procesados individualmente con reglas y estados parciales. Puntuación/certeza separadas. Ollama opcional escrito; no validado en vivo. Interpretación exhaustiva de tareas/requisitos en español pendiente del motor profundo/revisión.
6. **Operativa y probada en sus flujos automatizados:** seis pestañas, filtros, fichas originales, notas/candidaturas, importación, perfil, propuestas CV locales y exportación real XLSX/CSV/JSON/Markdown. Rutas manuales con evidencia; no cálculo de transporte.
7. **Verificada con límites declarados:** 63 pruebas completas sin fallos ni errores y 3 comprobaciones específicas posteriores de UI/Excel. Humo real en cuatro familias ATS y un anuncio genérico. Sin pruebas ficticias declaradas como reales.

## Datos reales actuales

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

Exportación comprobada: C:\Proyectos\CorkJobRadar\exports\cork_job_radar_2026-10-19T121612_0100.xlsx (272 anuncios). Ver docs/TEST_REPORT.md y logs/verified-export.json.

Verificación adicional: ejecución 6 parcial, 205 tareas procesadas y 67 reintentables tras bloqueo; nunca equivalen a 67 cierres. Estados actuales: [{"open_status": "ACCESS_BLOCKED", "n": 2}, {"open_status": "OPEN_CONFIRMED", "n": 122}, {"open_status": "OPEN_LIKELY", "n": 87}, {"open_status": "UNKNOWN", "n": 61}]. Se han distinguido 2 bolsas de talento que no acreditan vacantes concretas.

## Restricciones y siguientes pasos

- Activar un modelo local ya instalado y validar su análisis profundo antes de anunciar completitud semántica.
- Conectar una vía autorizada de rutas/transporte y verificar ida/vuelta según turnos; mantener Ballinlough y ausencia de coche.
- Implementar y probar paginación y fichas de JobsIreland/HSE/agencias accesibles tras revisar condiciones; conservar restricciones de Indeed/J&J y las revisiones pendientes.
- Completar soporte de feeds/sitemaps y parsers dinámicos solo cuando se permita.
- Diagnóstico de omisiones: incidencia automática disponible, investigación causal y regresiones de nuevas fuentes requieren revisión técnica.
- Endurecer fijación DNS contra rebinding y preparar siguientes migraciones con copias previas. No se han enviado CV, correos ni candidaturas a empresas.

## Incidencias de ejecución y aislamiento

La primera ejecución de pytest creó temporales bajo el TEMP predeterminado del usuario, antes de fijar basetemp dentro del proyecto. La navegación automatizada generó su snapshot automático bajo la carpeta de trabajo inicial; al intentar guardarlo en el proyecto, la herramienta denegó esa ruta. No se borraron esos archivos externos sin autorización. Las siguientes pruebas y los informes del proyecto usan rutas internas. Los otros proyectos no se editaron. Estas incidencias se registran para no afirmar aislamiento absoluto que no se cumplió en esas dos herramientas.

No se declara terminado el análisis semántico profundo, el cálculo real de rutas ni los conectores aún no implementados.
# Ultimate upgrade — 2026-10-19 (in progress)

Baseline: 63 tests passed. Consistent database/code backups in `data/backups/`. SQLite v2 migration preserves all pre-existing rows (272 jobs, 273 publications, 482 snapshots, 326 analyses, 7 runs). Per-run change observations and batched latest analyses implemented; 2,000-row query test and connection-time DNS validation pass. HSE connector passes 9 targeted tests; live complete run is being checked. JobsIreland/Manpower terms prevent enabling bulk storage without permission. Further phases and final audit remain open; historical progress follows unchanged.

---

