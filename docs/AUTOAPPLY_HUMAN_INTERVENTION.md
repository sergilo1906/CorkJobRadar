# Intervención humana y sesiones de navegador

20/10/2026. **EN DESARROLLO · LIVE OFF · sin formularios, desafíos o candidaturas externos ejecutados en esta fase.** La infraestructura funciona sobre un servidor local propio con identidad ficticia aislada. No acredita soporte interactivo en un ATS externo. Los 22 hechos aprobados, el CV pendiente y la política sin configurar no cambian.

## Modos y condiciones oficiales

La revisión vigente de [LinkedIn, acuerdo de usuario](https://www.linkedin.com/legal/user-agreement) y [ayuda sobre software prohibido](https://www.linkedin.com/help/linkedin/answer/a1341387) mantiene bloqueada la automatización de su interfaz. `LINKEDIN_MANUAL` prepara CV/respuestas/enlace para que el usuario utilice Easy Apply manualmente. No hay extensión, cookies importadas ni navegador controlado en LinkedIn.

Las [condiciones Indeed Irlanda](https://ie.indeed.com/legal?hl=en), sección de Indeed Apply, prohíben automatizar ese proceso mediante herramientas ajenas a sus proveedores y herramientas oficiales. `INDEED_MANUAL` ofrece documentos/enlace para el uso manual de las funciones oficiales. No ejecuta Indeed Apply ni presume acceso autorizado a APIs de partners.

`EMPLOYER_SITE_ALLOWED` exige permiso y formulario empresarial comprobados. `HUMAN_VERIFICATION` es una pausa dentro de ese canal permitido; no convierte un sitio restringido en compatible. `HOLD` conserva datos incompletos, permiso desconocido y restricciones pendientes. Actualmente **ningún canal empresarial interactivo externo cumple las condiciones de liberación**. Las capacidades siguen cerradas, aunque exista un formulario JSON consultable.

Un enlace externo desde un portal se revisa por sus propias condiciones/adaptador/política. No se hereda permiso. La navegación inesperada o los dominios no autorizados se bloquean; no se persiguen redirecciones del portal con un navegador automatizado. Los enlaces manuales Indeed solo conservan su identificador de oferta; los de LinkedIn eliminan seguimiento. No se exportan tokens de login en URLs.

## Estado y proceso propietario

SQLite v8 añade `autoapply_interventions` y `autoapply_intervention_commands`; conserva las tablas previas. La sesión se liga de forma única al intento reservado y a versiones/huellas de formulario, ficha, CV y política. No contiene valores cumplimentados, contraseñas, cookies, tokens CAPTCHA, HTML del usuario o capturas de pantalla.

El trabajador `interactive_worker.py` es dueño único del objeto Playwright; una exclusión del sistema operativo por sesión impide dos navegadores propietarios concurrentes. Tiene ventana de navegador **visible por defecto**, con helper sin consola adicional en Windows. Las pruebas pueden usar headless únicamente con una base sintética aislada y marcada; ese ajuste no habilita sitios públicos. El proceso espera comandos guardados en SQLite, independiente de los reruns de Streamlit. No se inicia ningún trabajador por abrir la pestaña.

Estados de sesión: `PREPARADA`, `INTERVENCION_HUMANA_REQUERIDA`, `HOLD`, `SESION_CADUCADA`, `CERRADA`, y estados exclusivos del ensayo propio `PRUEBA_LOCAL_CONFIRMADA` / `ENVIO_INCIERTO`. El estado de sesión se muestra junto al de preparación del intento; una preparación nunca es un envío.

La sección **Intervenciones pendientes** muestra empresa, puesto, URL, motivo, campos preparados, estado del formulario y última comprobación. Se actualiza cada tres segundos y ofrece recuperación/foco, **CONTINUAR CANDIDATURA** y cierre. El botón solo solicita una revalidación; no declara resuelto el desafío. No hay filas de prueba en producción. CLI de solo lectura: `python -m corkjobradar autoapply interventions`.

## Pausa, continuación y recuperación

Antes y después de cada campo se examinan indicadores visibles de CAPTCHA/autenticación/MFA. Al detectarlos no se escriben más campos ni se intenta presentar la solicitud: se conserva abierta la misma página con lo ya introducido. El controlador no pulsa verificaciones, lee tokens CAPTCHA, rellena contraseñas o contrata servicios de resolución. La intervención en el ensayo se hace sobre un control **simulado propio**, nunca un desafío de proveedor.

Al continuar se exige sesión abierta y válida, ausencia de bloqueo y confirmación específica de verificación del entorno autorizado. Ocultar un widget no basta. En el protocolo local esa confirmación procede del servidor de prueba para la sesión actual del navegador. **No es un verificador genérico de reCAPTCHA/hCaptcha**: un ATS real necesitará su comprobación permitida y probada; hoy queda bloqueado.

Se repite la barrera completa existente: funciones IT, requisito/experiencia/derecho laboral/análisis vigente, política y permisos, versión de datos/CV, bytes del adjunto, respuestas verificadas, estructura de formulario, destinos, fechas, ruta sin coche desde Ballinlough, cupos y duplicados. Campos modificados manualmente no se convierten automáticamente en hechos aprobados; se retienen. Un archivo distinto del CV aprobado no se sustituye silenciosamente ni se presenta. La última comprobación se repite al autorizar la única petición del receptor propio.

Si el servidor declara caducada la sesión, la ventana se cierra o falta heartbeat, se indica `SESION_CADUCADA`. Se conserva la preparación en la base y puede reconstruirse desde las versiones aprobadas **si siguen vigentes**; la nueva página necesita nueva verificación humana. No se exporta ni promete restaurar un CAPTCHA resuelto. Si caduca el esquema o cambia la ficha/política se conserva HOLD y hace falta nueva preparación válida. Un intento que pudo enviarse nunca se recupera para repetirlo automáticamente.

La espera del trabajador tiene un límite de 30 minutos; al terminar cierra el navegador y exige recuperación. No hay arranque automático con Windows. La pausa conserva solo la sesión abierta: reiniciar Windows no conserva cookies/autenticación. El borrado profesional solicita además cierre de las ventanas propietarias. Los temporales de Chromium y su controlador permanecen bajo el proyecto; no hay perfil persistente, exportación de estado, trazas ni logs de cuerpos HTTP.

## Confirmación y límites de prueba

El receptor propio usa HTTP multipart real, compara campos y hash del PDF, guarda un recibo en SQLite y vincula respuesta, hash de petición, oferta y referencia. Un 200 sin esos datos produce `ENVIO_INCIERTO`, bloqueando reintentos. La exclusión por intento y las identidades reservadas impiden duplicados.

`PRUEBA_LOCAL_CONFIRMADA` **no escribe `user_actions`, `application_receipt_evidence` ni `ENVIADA_CONFIRMADA`**. La confirmación empresarial permanece detrás del control de recibo externo correlacionado y del bloqueo LIVE existentes. No hay transporte interactivo ni lector de confirmación externa liberados; no se atribuye a una empresa un recibo de localhost.

Pruebas reproducibles (secuenciales, solo bases aisladas del proyecto):

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_human_interventions.py --basetemp=data\pytest-human-next --junitxml=logs\human-intervention-next.xml
.\.venv\Scripts\python.exe scripts\check_human_intervention_ui.py
.\.venv\Scripts\python.exe -m corkjobradar autoapply interventions
```

La comprobación UI utiliza el Streamlit ya abierto en localhost y no aprueba datos/documentos/política. Sus resultados y los fallos corregidos se conservan bajo `logs/human-intervention-*`; las suites se solapan y no se suman. Ver el checkpoint para el resultado final efectivamente ejecutado y la prueba con navegador visible.

Resultado final: **399 PASS**, cero fallos/errores/omitidas, 23 avisos, 496,96 s (`human-intervention-final.xml`). Selección de cierre con ventana visible: **5 PASS**, 31 deseleccionadas, 36,21 s (`human-intervention-visible-ready.xml`), incluidos dos casos visibles CAPTCHA/MFA. Los recibos verificados son exclusivamente del receptor propio; confirmaciones externas cero. UI real, instalador, CLI y conservación de ambas bases comprobados; detalles en `AUTOAPPLY_TEST_REPORT.md`.

El instalador `instalar-autoapply.ps1` instala ahora Chromium completo y headless dentro del proyecto, con temporales/caché locales y sin retirar otros navegadores. La instalación anterior solo incluía headless y no acreditaba ventanas visibles. La versión visible descargada se ha ejecutado en las pruebas corregidas; no se usa el Chrome personal del usuario.

## Requisitos externos pendientes

Hace falta una plataforma empresarial compatible, condiciones/permiso acreditados, un adaptador específico del DOM y de la verificación, entorno autorizado y prueba externa expresamente aprobada. Después, vacante IT compatible, CV definitivo y límites de política autorizados, ensayo real único y confirmación externa. Activar modo A será un acto separado; resolver un CAPTCHA nunca lo activa. No declarar esta función terminada ni operativo el envío por haber pasado pruebas locales.
