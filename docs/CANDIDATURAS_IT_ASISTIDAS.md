# Candidaturas IT asistidas y descubrimiento — 21/10/2026

La vía manual está al principio de la pestaña **Candidaturas automáticas**, bajo «Candidaturas IT asistidas». Las herramientas de AutoApply quedan en un bloque independiente «Vía B · AutoApply y herramientas avanzadas · LIVE OFF». No hacen falta claves de empresa, autorizar una política de bots ni negociar integración para preparar una candidatura completamente manual.

## Uso práctico

1. Filtrar ofertas y elegir «Elegir candidatura IT asistida». «POR_REVISAR» conserva dudas; no significa compatible ni rechazo. Los títulos junior se priorizan sin detener el análisis en el ranking. También se pueden consultar descartes, cerradas, registradas y fuera de alcance.
2. Abrir «Revisar y aprobar mi CV definitivo». El PDF pendiente existente sigue intacto; puedes leerlo/descargarlo y aprobar **esa versión** expresamente. Preparar otro CV solo reordena hechos aprobados para la oferta y crea un borrador cifrado; no añade cualificaciones. No hay aprobación ni envío por el agente. Los 22 hechos ya aprobados no se vuelven a pedir.
3. Revisar las frases literales del anuncio: OBLIGATORIO, DESEABLE o POR_ACLARAR; CUMPLIDO, NO_CUMPLIDO o PENDIENTE. Los preferibles no excluyen por sí solos. Las cláusulas mixtas/condicionales quedan pendientes. Solo comparaciones muy acotadas se automatizan: duración explícita de soporte general sin redondeo, derecho laboral exacto y coche propio. Una duración de soporte no acredita experiencia con Intune, Azure u otra herramienta. Ausencia de evidencia no equivale a incumplimiento.
4. Si has contrastado un requisito, seleccionar resultado y hechos aprobados que lo respaldan y guardar tu contraste. Queda ligado al texto/hash del puesto y versión de perfil; al cambiar cualquiera caduca. No crea hechos nuevos, respuestas ni autorización de envío, y no sustituye la barrera de AutoApply.
5. Revisar accesibilidad/horario desde Ballinlough sin coche. Hay formulario guiado de comprobación manual de bicicleta/autobús directo: centro exacto, días, entrada/salida, posible turno nocturno, accesos, ida/vuelta, duración, URL de evidencia y caducidad, con confirmación expresa. Reutiliza el validador de rutas, sin requerir la política ni los JSON de AutoApply. Sin datos contrastados conserva HOLD. El cálculo GTFS y sus cuatro accesos siguen en «Perfil y transporte»; no inventa paseos ni horarios. Para remoto, permiso desde Irlanda y presencialidad siguen requiriendo contraste; no hay una nueva aprobación remota simplificada.
6. Copiar cada contacto, LinkedIn, respuesta o hecho con el botón de copiar del bloque, visible al situar el cursor. La presentación breve usa exclusivamente afirmaciones aprobadas y fórmulas de saludo; debe revisarse y no responde por sí sola a una pregunta de motivación o un caso técnico.
7. Cuando haya esquema público compatible, «Actualizar preguntas públicas para esta solicitud» consulta solo GET. Muestra respuestas conocidas y preguntas pendientes, también opcionales. En sitios corporativos con Greenhouse se comprueba procedencia del API y coincidencia exacta con la URL publicada; eso permite leer preguntas, **no** automatizar la interfaz del empleador. Las inspecciones caducan, no se usan esquemas de otro puesto y retirar la fuente invalida esa lectura.
8. Con CV aprobado, preparar y descargar la solicitud manual o solo su CV. El ZIP conserva CV, contactos/LinkedIn, respuestas verificadas, preguntas pendientes, instrucciones y hashes. Puede prepararse para revisar aunque existan dudas: **no certifica aptitud, formulario completo, envío o recepción**. Abrir el enlace oficial en tu navegador, completar/revisar todos los campos y utilizar tú los mecanismos de LinkedIn/Indeed cuando proceda. Los identificadores públicos `gh_jid` se conservan; seguimiento y secretos de sesión no se incluyen en el enlace preparado.
9. Solo después de presentar realmente, registrar la declaración para evitar duplicados. Adjuntar EML original/PDF pasivo en «Justificantes de candidaturas manuales», que se abre al existir declaraciones. Su archivo/revisión personal no autentica al ATS ni crea ENVIADA_CONFIRMADA. No hay declaraciones de ejemplo en producción.

«COMPATIBLE_VERIFICADA» exige funciones IT, ubicación dentro del alcance, vigencia confirmada, derecho laboral, requisitos contrastados y ruta/turno acreditados. El estado del CV se muestra por separado. **Actualmente ninguna candidatura cumple todo ese conjunto.** Los controles funcionan; no se han suplido aprobaciones ni rutas con datos inventados. La lectura de requisitos es determinista y exige revisión humana de frases ambiguas; no se presenta como comprensión semántica universal.

## Descubrimiento ampliado real

«Buscar nuevas ofertas en fuentes IT revisadas» usa el trabajador y cola existentes, comprobando ejecuciones activas. Consulta todas las publicaciones de las fuentes seleccionadas, conserva cada registro antes de analizar y no se detiene al encontrar suficientes anuncios. Familias de consulta manual: IT Support, Helpdesk, Service Desk, Desktop Support, IT Technician, Application/Software Support, Junior Developer, QA Tester, IT Graduate y Trainee. Los botones LinkedIn/Indeed abren búsquedas oficiales; no se rastrean ni automatizan sus cuentas o formularios.

Ejecución **15**, finalizada 21/10 16:21:55: **120 nuevos anuncios**; producción pasa de 459 a **579**, conservando los anteriores. Los **59** dentro del alcance o con accesibilidad pendiente tienen análisis básico documental terminado; hay seis recuperaciones de detalle completadas. Los otros 61 siguen conservados fuera de alcance. No hay datos sintéticos en el catálogo principal. Alcance completo de esos listados/consulta, no del mercado de Cork.

| Fuente nueva | Lectura permitida utilizada | Resultado real | Límite |
|---|---|---|---|
| SolarWinds | Greenhouse Job Board GET público, enlazado con su portal oficial | 78/78 anuncios conservados | Tablero global; muchos fuera de Irlanda/Cork. Publicación no demuestra compatibilidad |
| Version 1 | SmartRecruiters Posting API pública, consulta `country=ie` | 38/38 conservados, detalle de los seis dentro del área pendiente recuperado | La consulta nacional no equivale a 38 ofertas Cork; varias son senior |
| Evo-soft Ireland | HTML público/robots revisados, pestañas de su página de carreras | Cuatro puestos separados con descripción original | Ubicación laboral no publicada en cada ficha, sin inventarla desde la dirección corporativa. No tomar tareas de Developer como funciones del Junior Support Technician |

Los puestos que comparten página tienen identidad interna por sección; el enlace del anuncio sigue siendo el publicado. La deduplicación y el registro de candidaturas distinguen puestos distintos y conservan revisiones/solicitudes anteriores.

Pistas concretas, **sin certificar aptitud ni actualidad completa**:

- [Evo-soft: Junior Support Technician](https://evosoft.ie/about-evo-soft/careers/): publicación visible en página oficial, business logic deseable. Necesita aclarar funciones detalladas, sede, comunicación y desplazamientos a clientes. La descripción corta no se convierte por el título en funciones IT confirmadas.
- [SolarWinds: Support & Operations Internship](https://jobs.solarwinds.com/job-detail/?gh_jid=4739548005): Cork, funciones reales de soporte de aplicaciones confirmadas por cita de interlocución con desarrollo/resolución de bugs. Pide BE/BTech en curso, inglés B2/C1 y conocimientos concretos no acreditados automáticamente por DAM/intermedio. Formación/certificaciones «preferred, not required» se conservan como preferibles. Vigencia OPEN_LIKELY: el formulario dinámico no se ha confirmado ni rellenado.
- Version 1 conserva ofertas Oracle/ERP Cork/Dublín, mayoritariamente senior, para investigación. No se consideran adecuadas por pertenecer al sector IT.

Esquema público real de la internship: **10 campos**, contactos conocidos mapeados localmente y CV pendiente; preguntas opcionales también visibles sin adivinar respuestas. Evidencia `logs/usable-it-real-question-preview.json`, inspección 3 cifrada. Cero datos personales en peticiones, cero POST, sin introducir datos en la página corporativa. No demuestra que un envío externo funcione.

## Canales manuales y límites observados

Se ofrecen enlaces e instrucciones separados para PFH (sin listado extraíble), ICT Services y eir business talent (consulta automatizada suspendida por acceso/robots), Fruition (los enlaces concretos indexados consultados no estaban disponibles), Teamwork.com (página actual observada con ventas/marketing/customer success, sin junior IT acreditado) y DEITG (Newbie Tech, pero descripción/vigencia/sede/horario por verificar; también formulario de talento general). El identificador Greenhouse supuesto de Teamwork no resultó válido; no equivale a una prohibición ni a inexistencia global de puestos. Las pistas se conservan en configuración e informes y pueden abrirse manualmente. No se usa otro endpoint para esquivar un bloqueo.

El formulario de DEITG no se declara una vacante concreta apta solo por tener upload de CV. Los fragmentos de buscador se usaron para localizar páginas oficiales; no para inventar fecha, sueldo, horario o candidatura compatible. Probes originales: `logs/usable-it-channel-probes.json`, `usable-it-official-page-discovery.json`, `usable-it-official-listings.json`, `usable-it-version1-probe.json`. Capturas públicas con hash en `data/public-probes/`.

## Vía B y permisos

Las restricciones y pausa CAPTCHA/MFA existentes siguen activas. Ningún proveedor ha concedido un canal de envío nuevo a esta instalación. Las fuentes de búsqueda GET no conceden ese permiso. No se piden claves empresariales para la vía manual. AutoApply real exige destino/entorno autorizados, formulario/adaptador y recepción externos acreditados, candidatura compatible, ensayo expresamente autorizado y activación posterior separada de política. **LIVE OFF**.

Fuentes primarias: [Greenhouse Job Board](https://docs.greenhouse.io/job-board.html), [SmartRecruiters Posting API](https://developers.smartrecruiters.com/docs/posting-api), [SolarWinds](https://jobs.solarwinds.com/jobs/), [Evo-soft](https://evosoft.ie/about-evo-soft/careers/), [Version 1](https://careers.smartrecruiters.com/Version1). La revisión de envíos y gestiones externas continúa documentada en [canales 21/10](AUTOAPPLY_CHANNELS_2026-10-21.md).

## Pruebas y conservación

Las pruebas usan bases aisladas e identidad ficticia. Chromium comprueba aprobación explícita de una versión, portapapeles real, ZIP/PDF, declaración y carga de EML cifrado; cero peticiones externas. La UI real se comprueba aparte sin aprobar CV, copiar datos privados o crear candidaturas. Los informes terminados, fallos/correcciones, suite final, auditoría de conservación y copias constan en PROGRESO y checkpoint; no sumar suites solapadas.

Resultado terminado: **455 PASS** en la suite completa (`usable-it-final-full.xml`, 338,28 s, 23 avisos) y **39 PASS posteriores** en los módulos nuevos y navegador (`usable-it-delivery-tests.xml`, 22,70 s). La segunda incluye acabados de CV general, descarga aprobada y protección de revisiones; no se suma a la completa. Cero fallos/errores/omitidas en ambas. Los 399 y 67 previos y los intentos fallidos permanecen conservados.

Comandos reproducibles (usar nombres nuevos para no pisar evidencias):

```powershell
.\.venv\Scripts\python.exe -m corkjobradar junior-it
.\.venv\Scripts\python.exe -m pytest -q tests/test_usable_it_workspace.py tests/test_junior_it_discovery.py tests/test_usable_it_browser.py --basetemp=data/pytest-usable-next --junitxml=logs/usable-it-next.xml
```

La primera orden inicia una búsqueda real y añade/refresca datos, nunca candidaturas. Las pruebas no se ejecutan sobre la base principal. No restaurar la copia sobre producción. SQLite v10 añade solo revisiones factuales inmutables, sin valores personales ni permiso de envío. Borrado profesional conserva esos IDs/hashes de auditoría y elimina el contenido cifrado según el mecanismo existente.
