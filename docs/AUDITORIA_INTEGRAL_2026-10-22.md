# Cork Job Radar — auditoría de preparación integral (22/10/2026)

**Resultado: NO LISTA PARA ENVÍO AUTÓNOMO REAL.** La búsqueda y preparación local tienen implementación, pero las pruebas externas y su autorización faltan. No se ha ejecutado el software ni se ha leído la base cifrada de Windows durante esta revisión: auditoría estática del repositorio público `main` y sus pruebas/documentación. No declarar "100 % verificado".

## Alcance y evidencias examinadas

Inventario GitHub: 323 entradas; 89 archivos del paquete `corkjobradar/`, 63 módulos `tests/test_*`; ninguna configuración `.github/workflows` en el árbol examinado. Código revisado específicamente: arranque (`app.py`, `db.py`), supervisor (`runtime.py`, `runtime_ui.py`), captura (`junior_discovery.py`, `http.py`, fuentes YAML), análisis (`autoapply/it_scope.py`, `academic.py`, `broad_selection.py`, `radius.py`, `selection_queue.py`, `manual_workspace.py`), CV (`documents.py`, `vault.py`, `cv_import.py`), candidaturas (`handoff.py`, `forms.py`, `platforms.py`, `compatibility.py`, `policy.py`, `trials.py`, `final_gate.py`, `interactive_browser.py`), interfaz (`ui/shell.py`, `pages.py`, `model.py`, `visibility.py`), tests seleccionados y checkpoint. Inventario y muestreo de documentación pública sin contactos en claro detectados en los documentos examinados; **no equivale a escaneo forense exhaustivo de cada blob histórico**.

El fichero `docs/VERIFIED_TEST_RESULTS_2026-10-22.json` documenta 590 PASS locales en la última suite completa de reevaluación, con regresiones posteriores solapadas. **No se han reproducido esas ejecuciones en esta auditoría**, y no hay CI que las ejecute por commit. El informe actual del checkpoint indica CV n.º 2 aprobado y paquetes manuales locales preparados, sin solicitudes externas.

## Matriz de subsistemas

| Área | Evidencia concreta | Estado | Criterio de cierre |
|---|---|---|---|
| Instalación y arranque | `app.py`, `iniciar.ps1`, `runtime.py` | Implementado; no ejecutado aquí | Arranque desde un equipo Windows limpio y prueba de actualización no destructiva |
| Base / privacidad | `db.py` migraciones hasta v12, DPAPI `vault.py`, `.gitignore` | Protecciones existentes | Copia/integridad/FK y comprobación de perfil/secretos antes/después |
| Búsqueda continua | Supervisor y cola persistentes `runtime.py` | Implementado | Ensayo físico suspensión/reinicio Windows + un ciclo de 6 h |
| Cobertura del mercado | `junior_it_sources.yaml` incluye solo **tres fuentes automáticas junior** (SolarWinds, Version 1, Evo-soft); otras manuales | Cobertura parcial | Añadir fuentes permitidas relevantes; medir omisiones sin prometer totalidad del mercado |
| Selección de vacantes | `it_scope.py`, `broad_selection.py` | Implementada | Casos reales de no-IT, IT ambiguo, mínimos 3/3–5/4 años y deseables |
| Radio de 50 km | `radius.py` exige coordenadas del centro verificadas | Correctamente conserva pendientes | Revisar centros, fechas, evidencias y accesibilidad; no confundir localidad con dirección exacta |
| Formación / fechas | Confirmación de DAM terminado ya versionada; corrección **2022–2024** está en PR #2, no en `main` | **Pendiente de integrar y probar** | Tras PR #2, ejecutar pruebas Windows y actualizar solo el hecho cifrado; generar nuevo CV revisable |
| CV / plantilla | `documents.py::render_cv` agrupa frases aprobadas en párrafos genéricos | **No reproduce el formato de referencia** | Plantilla A4/ATS profesional, cabeceras y secciones, render PDF/DOCX, inspección visual y control 1 página |
| Paquetes manuales | `handoff.py` cifra CV/answers y los revalida | Implementados, no envío | Revalidar todos los paquetes tras cambio de CV y probar una solicitud manual por canal oficial |
| Panel UI | `ui/pages.py`, `ui/visibility.py` | 6 áreas; hallazgo corregido en esta PR | Verificar pausa real/controles; 5 resoluciones y flujo completo con navegador |
| Aplicación real ATS | `policy.py::require_live` bloquea siempre; `trials.py::execute_trial` también | **BLOQUEO FUNDAMENTAL** | Permiso del destino, adaptador y entorno de ensayo, un envío autorizado con respuesta real correlacionada |
| LinkedIn / Indeed | Modos manuales, no usar automatización externa no autorizada | Decisión deliberada | Presentación manual con herramientas oficiales |
| CAPTCHA / MFA | `interactive_browser.py` limita POST a receptor propio `OWNED_HUMAN_TEST_ONLY` | Simulación local; no ATS real | Primer recorrido humano real solo donde se permita y con permiso expresamente concedido |
| Calidad reproducible | `tests/`, historial de XML locales; sin workflow CI | Evidencia histórica, no CI | Definir runner Windows con control de privacidad, pruebas y build por PR |

## Hallazgo de interfaz corregido en la misma rama

Antes, `ui/visibility.py::runtime_actions` permitía "Reanudar" durante `PAUSING`. `safe_controls` permitía `SEARCH_NOW` durante `PAUSING` si `active_kind` ya estaba vacío. `ui/pages.py::activity_status` también podía mostrar ese botón. Ahora `PAUSING` y `STOPPING` no ofrecen acciones incompatibles. Se añaden casos de regresión a `tests/test_ui_redesign.py`.

**Importante**: cambio revisado estáticamente; pruebas de Windows y Chromium **pendientes**. La mejora afecta visibilidad/UX, no las autorizaciones de backend.

## Orden recomendado, sin reconstrucción innecesaria

**P0 – Antes de cualquier candidatura automática**
1. Probar la rama de corrección de fechas PR #2 en Windows. No fusionarla a ciegas. Confirmar la creación de nuevo borrador, revocación de CV/documentos basados en hechos anteriores y revisión humana; nunca reutilizar paquetes antiguos. No reaprobar los hechos no modificados.
2. Validar una candidatura manual real elegida por el usuario para comprobar CV, formulario y justificante sin interpretar una declaración local como confirmación ATS.
3. Seleccionar una plataforma de aplicación externa con integración explícitamente permitida y entorno/uso concedidos. Implementar el adaptador, validación de preguntas, comprobación final y recepción correlacionada.
4. Autorizar **un** ensayo real específico y verificar su recepción. Solo después, crear activación autónoma separada con política/cupos. Si el permiso no llega, mantener LIVE OFF.

**P1 – Que el producto sea útil diariamente**
5. Rehacer `render_cv` según el diseño A4 indicado por el usuario; conservar el texto de todos los hechos aprobados, diferenciar CV de cartas de recomendación, renderizado PDF/DOCX y revisión visual/ATS. La adaptación por vacante puede reordenar o resaltar hechos, nunca inventarlos.
6. Ampliar fuentes junior compatibles con condiciones de consulta, registrar cobertura real, revalidar cierres y ubicación exacta de puestos dentro de 50 km.
7. Comprobar en un Windows real pausar/reanudar, cerrar pestaña, suspensión, reinicio, bloqueo de duplicados y recuperación de cola. No afirmar que ya se hizo un reinicio físico si solo hubo simulación.

**P2 – Calidad operativa**
8. CI Windows para `pytest` en bases aisladas/DPAPI (nunca contra producción ni con credenciales públicas), pruebas de seguridad, formato, pruebas smoke de CV y controles UI. Conservar comparaciones sin sumar suites solapadas.
9. Verificar que la documentación principal diferencia estado **actual** de estados históricos; documentar la corrección 2022–2024 solo cuando se integre y aplique localmente.
10. Auditoría de historial Git público, dependencias y secretos: no subir datos personales ni CV. Las exclusiones actuales son positivas pero no sustituyen vigilancia continua.

## Definición estricta de “listo”

- **Listo para buscar**: fuente permitida comprobada, supervisor probado y registros idempotentes.
- **Listo para candidatura asistida**: CV actual aprobado, paquete actualizado, revisión de vacante, uso manual del formulario oficial, justificante y seguimiento.
- **Listo para AutoApply real**: destino y automatización permitidos, primer POST real expresamente autorizado, recepción/estado correlacionados, protección ante duplicados/reintentos ambiguos, pruebas y activación independiente. No es equivalente a enviar en *todas* las plataformas.
- **Nunca** prometer que se descubren todas las ofertas del mercado ni que se controlan sistemas externos que no permiten automatización.

### Evidencias que deben producirse en la máquina del usuario

1. `git status`, rama, hashes y copia SQLite/DPAPI verificada; no sobrescribir producción.
2. Ejecución completa de pruebas **en Windows**, prueba dirigida de cambio de formación/visibilidad y comprobación visual PDF + Chromium.
3. Diagnóstico de fuentes y números de ofertas/vacantes IT; fecha y cobertura explícitas.
4. Prueba física de recuperación Windows con logs propios, sin procesos duplicados.
5. Prueba externa únicamente después de permiso y autorización individual; registrar recepción auténtica o estado incierto.

**Esta auditoría no ha enviado candidaturas, aprobado versiones de CV, activado AutoApply, ni tocado la SQLite local.**
