# Integración comprobada de PR, CV y Windows — 22/10/2026

**Aplicación local actualizada; AutoApply externo todavía no operativo. LIVE OFF.** Se conserva la arquitectura y la interfaz existentes. No se han aprobado CV, políticas ni candidaturas en nombre del usuario.

## PR revisadas e integración

| PR | Commit examinado | Resultado local |
|---|---|---|
| #2 — fechas DAM | `9a72ee22b7b49bea7cd76c1961fe4adaa027c723` | 7 pruebas Windows iniciales PASS; se añadió exclusión mutua con el trabajador, comprobación FK del respaldo y regresiones de conservación/paquetes obsoletos |
| #3 — pausa e informe | `defda70f7d6cf7d6d9c3238f44e5bb630f1cd599` | 22 pruebas iniciales PASS; se extendió la protección al backend transaccional y al panel avanzado |
| #1 — plantilla previa aprovechada | `702ea61d70bbb5813790819b66996bcedd511706` | 14 pruebas iniciales PASS; se reutilizó y corrigió el módulo, sin reconstruir el generador desde cero |

Las PR #2/#3 combinan sin conflictos. Al incorporar #1 hubo conflictos solo en `PROGRESO.md`, `NEXT_STEPS.md` y el checkpoint: se conservaron las notas de ambos lados y la ascendencia Git completa. La rama local activa es `work/validated-pr23-cv-20261022`. Las PR originales continúan abiertas; no se ha fusionado ni sobrescrito `main` remoto. Integrar la rama verificada completa para incluir las correcciones posteriores a esas PR.

Registro: `logs/pr23-github-review.json`. No hay checks de GitHub Actions ejecutados por estas PR; la evidencia es Windows local.

## CV y datos profesionales

- Se inspeccionó visualmente la primera página del PDF de referencia. Las tres páginas adicionales no se incorporan al CV.
- PDF y DOCX comparten geometría A4, márgenes, Arial, cabecera azul, separadores, jerarquía, viñetas y énfasis. El contenido procede exclusivamente de las afirmaciones vigentes. Las secciones del original sin hechos aprobados no se rellenan por suposición.
- Se conservan las afirmaciones completas; la adaptación no copia instrucciones del anuncio ni desordena la cronología laboral. La titulación precede a los cursos complementarios. Desbordar una página legible produce un error explícito, también al generar Word.
- DAM figura como finalizado y examen aprobado, **Institut Baix Camp, 2022–2024**. No se afirma una fecha de expedición, Bachelor, Honours ni NFQ8.
- El cambio sustituye solo la versión vigente del dato académico: **22 hechos activos, 24 versiones históricas**. Las otras afirmaciones permanecen intactas.
- **CV versión 4: PDF cifrado, pendiente de revisión.** Los CV2/CV3 conservan sus fechas de aprobación históricas y quedan revocados por el cambio académico. Nadie ha aprobado el nuevo documento.
- La interfaz muestra la imagen del PDF seleccionado y permite descargar sus bytes exactos. La vista previa usa PNG explícito para evitar la recompresión JPEG de Streamlit. El consentimiento continúa desmarcado y el botón de aprobación deshabilitado hasta una acción del usuario.
- DOCX accesible en **Perfil y configuración → CV definitivo → Opciones de documento: DOCX, importar CV o carta**. Generarlo crea una revisión independiente; no convierte automáticamente una aprobación PDF en aprobación Word.
- PDF y Word con el contenido real se renderizaron y revisaron: una página en ambos, todos los hechos conservados y fechas correctas. Se utilizó LibreOffice 25.2.4.3 con perfil temporal dentro del proyecto, sin instalar Office ni modificar su perfil habitual. No se ha comprobado Microsoft Word.

Se detectó y corrigió que Word partía `2022-2024` por el guion: un salto de línea de presentación antes del rango mantiene la fecha íntegra sin alterar la afirmación. Los documentos son deterministas para evitar borradores distintos por timestamps de generación.

Evidencias privadas con metadatos: `logs/pr23-current-cv-render-proof.json`, `logs/pr23-academic-change.json`. Los archivos legibles de inspección son temporales; el CV persistente se conserva mediante DPAPI.

El control automático rechazó la limpieza temporal tanto recursiva como por archivos explícitos, indicando únicamente `blocked by policy`. Por ello `data/pr23-cv-private` se conserva con permisos restringidos al usuario actual y SYSTEM, además de una copia DPAPI independiente en `data/backups/`. No se publicó en GitHub. Evidencia: `logs/pr23-render-evidence-preservation.json`. Su retirada queda pendiente; no se eludió el bloqueo utilizando otro mecanismo de borrado.

## Búsqueda, selección, preparación y conservación

**614/614 ofertas reevaluadas**, 614 análisis añadidos y **3.026 análisis totales** al cierre de esta operación. No se borraron análisis anteriores. Quedan 56 ofertas con funciones IT confirmadas y 15 oportunidades locales razonables para revisar; no equivalen a 15 candidaturas plenamente elegibles ni a 15 centros verificados dentro de 50 km.

La selección mantiene Ballinlough, radio de 50 km, mínimo obligatorio solicitado hasta tres años, diferencias menores de experiencia y deseables como advertencias. Centro, transporte sin coche, turno y dudas esenciales permanecen pendientes cuando falta evidencia. No se atribuyen rutas, equivalencias académicas o disponibilidad a partir de una localidad.

La búsqueda real más reciente, ejecución20, terminó el22/10 a16:24:26 Dublin: SolarWinds80, Version1 37 y Evo-soft4 registros observados, paginación completa y tareas de detalle/análisis terminadas. Es cobertura de esas fuentes, no de todo Cork. La nueva reevaluación local no se presenta como una nueva consulta web.

Los **52 paquetes manuales históricos** siguen almacenados y cifrados. Todos rechazan su apertura por `HANDOFF_PROFILE_OR_CV_CHANGED`, como corresponde. La cola se ha refrescado sin crear paquetes con un CV no aprobado. No hay intentos de candidatura, declaraciones de envío ni recibos externos.

Lista actual: [oportunidades](OPORTUNIDADES_IT_DAM_FECHAS_2026-10-22.md). Excel local: `exports/Oportunidades-IT-DAM-fechas-2026-10-22.xlsx`. Las dos pantallas de ofertas/candidaturas conservan el acceso a las oportunidades; tras invalidar un CV, las retenidas están en **Requieren intervención**.

Se guardaron respaldos consistentes antes del código y antes del cambio académico, con SHA-256, SQLite/FK y ZIP comprobados. Se verificó que no faltan filas históricas ni cambian los otros hechos; las siete tablas de transporte se compararon en ambos sentidos, sin diferencias. El respaldo final incluye las nuevas pruebas y los archivos cifrados referenciados. No se restauró ninguna copia sobre producción.

Registros: `logs/pr23-cv-start-backup.json`, `logs/pr23-backup-verification.json`, `logs/pr23-before-academic-backup.json`, `logs/pr23-data-preservation.json`, `logs/pr23-transport-preservation.json`.

## Pruebas y navegador

| Ejecución | Resultado | Evidencia local |
|---|---|---|
| Suite completa de integración, antes de los últimos ajustes | 645 PASS | `logs/pr23-reference-full-tests.xml` |
| Regresión final de pausa/backend, UI, procesos Windows, navegador y cambio académico | 65 PASS | `logs/pr23-final-runtime-tests.xml` |
| CV, rango académico Word, render Office e importación | 39 PASS | `logs/pr23-word-final-regression.xml` |
| Respaldo: nueva evidencia, DPAPI, ausencia de carpeta opcional y no sobrescritura | 1 PASS | `logs/pr23-backup-regression-corrected.xml` |
| Aplicación real, Chromium 1440/390, imagen/descarga exactas, consentimiento y supervisor | PASS | `logs/pr23-delivery-browser.json` |

Las suites se solapan: **no se suman** y no se presenta la suite645 como ejecutada después de los últimos cambios. Los avisos de NumPy/Streamlit son deprecaciones. Se conservan los fallos iniciales y sus correcciones, incluidos preparación del banco aislado, inicialización de Office, salto del rango, recompresión de imagen y selectores del verificador.

El ensayo Chromium sobre la aplicación real verifica píxeles del PDF, hash de la descarga, controles sin desbordamiento, opción DOCX y ausencia de consentimiento. Los contactos/CV no se guardan en capturas ni logs. Las tablas de perfil, documentos, políticas e intentos permanecen iguales durante esa revisión.

## Windows continuo

Se observó que el proceso de Streamlit anterior había terminado a17:30 y el supervisor dejó `EXITED_CHECKPOINT_RETAINED`, sin errores registrados. Se volvió a abrir mediante el lanzador existente y recuperó la misma base, estado solicitado RUNNING, cola y programación de seis horas. Cerrar la pestaña deja continuar los latidos; ejecutar un segundo lanzador reutiliza el mismo supervisor.

La protección de pausa ahora se comprueba dentro de la transacción de `runtime.command`: callbacks atrasados de UI/CLI no pueden reactivar búsqueda en PAUSING/STOPPING ni programar SEARCH_NOW mientras hay trabajo activo. El panel avanzado aplica las mismas restricciones.

No se instalaron servicios ni inicio automático de Windows. Los ensayos de procesos propios cubren muerte/reinicio de la aplicación, bloqueo único y recuperación. **No se suspendió, apagó ni reinició físicamente el equipo**: ese ensayo sigue pendiente. La búsqueda siguiente conservada es22/10 a22:25:41 Dublin; consultar el panel para fechas posteriores.

## Primer envío externo: vía viable y límites reales

Se revisaron otra vez los mecanismos oficiales. Ninguno tiene una concesión de envío para esta instalación:

| Canal | Estado actual |
|---|---|
| Greenhouse | GET público y preparador existentes; POST exige Basic Auth con clave del tablero. Primera opción técnica condicionada por el adaptador y una vacante local, no por un permiso supuesto. [Documentación](https://docs.greenhouse.io/job-board.html) |
| Lever | POST requiere clave del cliente creada por Super Admin. Autorización/ensayo/recepción pendientes. [API oficial](https://github.com/lever/postings-api#apply-to-a-job-posting) |
| SmartRecruiters | API de clientes/partners, OAuth `candidate_applications_manage`, consulta de estado documentada; sin adaptador autorizado de envío aquí. [API](https://developers.smartrecruiters.com/docs/application-api) |
| Ashby | `candidatesWrite`, autenticación y control de publicación; sin concesión ni transporte verificado. [Envio](https://developers.ashbyhq.com/reference/applicationformsubmit) |
| Recruitee | Preparación multipart existente; permiso del destino y prueba pendientes. Token de Careers Site anunciado obligatorio desde10/02/2027. No se utilizó su demo como receptor autorizado. [Autenticación](https://docs.recruitee.com/reference/authentication-1) |
| LinkedIn / Indeed | Solo manual asistido. [LinkedIn](https://www.linkedin.com/help/linkedin/answer/a1341543), [Indeed](https://www.indeed.com/legal?hl=en_US) |

La consulta GET actual de [Keeper IT Support Specialist](https://job-boards.greenhouse.io/keepersecurity/jobs/4418202009) recuperó15 preguntas, normalizadas a16 campos. Se conservó una inspección nueva y se prepararon ocho campos reconocidos en un **formulario local desconectado**, con CV4 únicamente para revisión local. Cero POST; no demuestra un formulario externo rellenado, permiso ni recepción.

Siguen pendientes seis respuestas obligatorias: patrocinio presente/futuro, residencia permanente, presencialidad híbrida tres días, experiencia2+ años con el alcance indicado, un incidente concreto resuelto y expectativas salariales. El perfil sigue acreditando1 año10 meses, sin redondeo. El esquema publica dirección en Lower Glanmire Road; coordenadas, recorrido sin coche y horario necesitan comprobación independiente. CV4 y política tampoco están autorizados para enviar.

El camino práctico inmediato es aprobar el CV si procede, resolver esas preguntas, contrastar requisitos/transporte y usar la candidatura manual asistida por el enlace oficial. **No requiere negociar una API empresarial.**

Para automatizar: obtener una concesión concreta para organización/endpoints y entorno de prueba; implementar y validar transporte y confirmación correlacionada; preparar la candidatura completa; pedir autorización expresa para un solo ensayo; comprobar respuesta ATS y recepción externa; después pedir activación separada de política. `execute_trial` y LIVE siguen bloqueados: no basta cambiar un interruptor ni interpretar un clic/recibo local como recepción empresarial.

Diagnóstico por siete causas y todas las ofertas: `logs/pr23-current-blockers.json`. Preparación real desconectada: `logs/pr23-real-profile-preparation.json`. Consulta externa GET: `logs/pr23-keeper-readonly.json`. No se enviaron mensajes a empleadores, datos personales a ATS ni candidaturas.
