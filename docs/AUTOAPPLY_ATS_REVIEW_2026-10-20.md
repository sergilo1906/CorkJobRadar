# Revisión de canales de candidatura — 20/10/2026

Prioridad práctica actual: [vía asistida, nuevas fuentes IT y uso manual sin autorizaciones API empresariales](CANDIDATURAS_IT_ASISTIDAS.md). La investigación de envío externo continúa separada y no bloquea esa preparación manual.

Continuación focalizada 21/10: [canales actuales, bloqueos y gestiones concretas](AUTOAPPLY_CHANNELS_2026-10-21.md). Esta matriz histórica no concede permisos nuevos.

**Resultado para esta instalación: cero ATS con automatización de envío permitida y técnicamente comprobada. LIVE OFF.** El catálogo aparece también en la interfaz y en `autoapply platforms`. Es independiente de la lista de dominios de la política: esa lista no concede permisos del proveedor.

Continuación con inventario de las empresas reales de SQLite y adaptador de preparación Recruitee: [integración externa y pruebas](AUTOAPPLY_EXTERNAL_ADAPTER.md). Recruitee ya tiene consulta/normalización/preparación multipart; sigue sin transporte POST ni recibo externo comprobados. No leer «sin implementar» en el cuadro histórico como ausencia de esas nuevas funciones de preparación.

| Canal | Clasificación | Evidencia y alcance | Próximo requisito |
|---|---|---|---|
| Greenhouse Job Board API | Pendiente de validar | GET público de vacantes/esquema comprobado; POST con clave del tablero del empleador | Permiso del titular, entorno de prueba y credencial de integración; envío/recibo sin probar |
| Greenhouse alojado, Keeper inspeccionado | Intervención manual | El HTML declara reCAPTCHA; no se rellena ni se resuelve | Paquete local y revisión manual |
| My Greenhouse | No permite esta automatización | Acuerdo §3(z), referido al servicio My Greenhouse | Uso manual |
| Lever Postings API | Pendiente de validar | API para formularios del cliente, requiere clave generada por Super Admin | Integración autorizada y comprobación de recepción |
| Lever alojado observado | Intervención manual | HTML real con CAPTCHA conservado | Paquete local y revisión manual |
| SmartRecruiters Application API | Pendiente de validar | API protegida para clientes/partners; candidatura y consulta de estado documentadas | Autorización de integración y autenticación con ámbito adecuado; adaptador no implementado |
| Ashby applicationForm.submit | Pendiente de validar | Basic Auth y permiso candidatesWrite; no es API anónima de candidatos | Autorización del titular y prueba de formulario/archivos/recibo; adaptador no implementado |
| Recruitee Careers Site API | Pendiente de validar | GET real y adaptador de esquema/preparación multipart comprobados; ocho publicaciones conservadas; cero POST externos | Permiso específico, privacidad/controles, transporte y recepción externa pendientes; sin vacante compatible acreditada |
| Indeed Apply | No permite esta automatización | Bots externos de Indeed Apply prohibidos fuera de sus herramientas oficiales; acceso automatizado requiere permiso escrito | Uso manual |
| LinkedIn / Easy Apply | No permite esta automatización | Automatización externa de actividad prohibida según ayuda oficial | Uso manual; conservar el enlace LinkedIn aprobado no automatiza LinkedIn |
| Workday, iCIMS, Workable, Taleo, HSE y restantes | Pendiente de validar | Sin revisión suficiente de cada destino ni adaptador de envío comprobado | Intervención manual hasta revisar cada servicio |

No se atribuye a todos los formularios de Greenhouse/Lever el CAPTCHA de un empleador observado. Tampoco se extrapola el acuerdo My Greenhouse a los tableros de todas las empresas. Una API documentada para clientes constituye una vía técnica condicionada, no permiso universal para una aplicación personal. La ausencia de una prohibición localizada tampoco concede autorización.

Fuentes oficiales consultadas en esta continuación:

- [Greenhouse Job Board API](https://docs.greenhouse.io/job-board.html): GET sin autenticación; POST autenticado. El cliente debe validar los campos obligatorios; una respuesta del servidor no acredita que se enviaran todos.
- [Lever Postings API](https://github.com/lever/postings-api#apply-to-a-job-posting): clave del cliente, campos configurables, archivos multipart, límites y recibo con identificador. No se han usado claves ni envíos de otra organización.
- [My Greenhouse: acuerdo](https://my.greenhouse.io/users/agreement): restricción de medios automatizados en su ámbito específico.
- [SmartRecruiters Application API](https://developers.smartrecruiters.com/docs/application-api) y [autenticación](https://developers.smartrecruiters.com/docs/authentication): configuración de preguntas/privacidad, creación y consulta de estado; OAuth con `candidate_applications_manage`. Exige presentar avisos y tratar preguntas de diversidad por separado. API key sin restricciones de ámbito no es una credencial apropiada para conceder permisos generales al candidato.
- [Ashby: envío](https://developers.ashbyhq.com/reference/applicationformsubmit), [autenticación](https://developers.ashbyhq.com/reference/authentication), [página de carreras propia](https://developers.ashbyhq.com/docs/creating-a-custom-careers-page) y [condiciones de cliente](https://www.ashbyhq.com/resources/terms). Es una integración de organización; no se presume autorización para automatizar todos sus formularios alojados. En una futura implementación deberá rechazarse explícitamente el envío a vacantes no publicadas.
- [Indeed: condiciones](https://www.indeed.com/legal?hl=en_US).
- Recruitee: [introducción de API de candidato](https://docs.recruitee.com/reference/intro-to-careers-site-api), [creación de candidatura](https://docs.recruitee.com/reference/offersoffer_idcandidates), [autenticación](https://docs.recruitee.com/reference/authentication-1) y [condiciones Tellent](https://tellent.com/terms). No debe confundirse con su Company API privada. La documentación anuncia `X-Careers-Sites-Token` obligatorio desde el 10/02/2027; un GET sin token actual no garantiza disponibilidad futura. El POST desencadena candidatura y correo de confirmación: no se ha probado. Son necesarias la revisión de condiciones del empleador, preguntas/consentimiento y prueba autorizada antes de liberar un adaptador. GET real registrado en `logs/verified-flow-recruitee-probe.json`: ocho publicaciones/preguntas; no se incorporan a producción ni se declaran compatibles con el perfil.
- [LinkedIn: actividad automatizada](https://www.linkedin.com/help/linkedin/answer/a1341543) y [acuerdo](https://www.linkedin.com/legal/user-agreement).

No se ha encontrado ni utilizado un sandbox público con permiso de presentar candidaturas. Se ha solicitado la identificación de un entorno propio/autorizado si el usuario dispone de él, sin solicitar secretos. No se crea una cuenta, se contrata un servicio ni se contacta con empleadores.

Sondeo Recruitee reproducible: `scripts/probe_recruitee_readonly.py`. Conserva respuesta pública íntegra y un estado pendiente por publicación en `data/public-probes/`, con hash/procedencia en `logs/verified-flow-recruitee-recheck-*.json`. No es una ejecución de búsqueda ni añade ofertas sintéticas o elegibilidad al historial principal. Las publicaciones observadas no se pierden ni se confunden con solicitudes autorizadas.

El receptor HTTP de las pruebas pertenece al banco local del proyecto, escucha únicamente en loopback durante la prueba y usa identidad ficticia. Su recibo prueba solo ese servidor. No es evidencia de recepción externa, no supera F4/F5, no autoriza un ensayo real y no libera LIVE.
