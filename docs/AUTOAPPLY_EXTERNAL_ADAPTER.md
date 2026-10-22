# Integración externa: inventario real y preparación documentada

Actualizado el 20/10/2026. **LIVE OFF. No hay todavía candidatura real compatible y autorizada lista para enviar, ni recepción externa comprobada.** Se continúa sobre la base y los controles existentes; no se cambia la aprobación de los 22 hechos, del CV o de la política.

## Qué usan las empresas de nuestra base

El inventario examina las **459 ofertas**, sin detenerse al encontrar candidatas. Conserva resultado, motivos, plataforma, clasificación IT y señales literales de requisitos para cada ID. No modifica el estado de las ofertas ni las convierte en elegibles. La detección por título sirve para investigación; una empresa tecnológica o un título no sustituyen funciones IT confirmadas.

| Empresa en SQLite | ATS observado | Ofertas IT confirmadas o títulos para investigar | Permiso/mecanismo de envío |
|---|---|---:|---|
| GlobeTech | Greenhouse EU | 11 | Job Board API POST con credencial del tablero; formularios alojados pendientes/restringidos por CAPTCHA observado |
| Keeper Security | Greenhouse | 28 (17 IT confirmadas) | Mismo mecanismo autenticado; no existe permiso/clave del empleador para esta aplicación |
| NETGEAR | Ashby | 33 (11 IT confirmadas) | applicationForm.submit con autenticación/permiso candidatesWrite; no hay integración autorizada |
| Qumulo | Ashby | 7 pendientes de funciones | Mismo requisito; no se presume compatibilidad por el sector de la empresa |
| WatchGuard | Lever | 4 para investigar | API de cliente con clave; incluye un puesto comercial que NO se convierte en IT por mencionar idiomas FR/IT/ES |
| AbbVie | SmartRecruiters | 1 pendiente | Application API protegida, con ámbito de acceso del cliente/partner |
| Egis Group | SmartRecruiters | 1 pendiente | Mismo requisito; no se declara informática por el título de ingeniería |

Este corte produce 39 clasificaciones IT confirmadas y 22 registros de investigación en HOLD dentro del alcance almacenado; no son 22 solicitudes elegibles. Otros 309 quedan conservados fuera del alcance y 128 como generales/no confirmados. No hay desapariciones del inventario. Faltan permiso, validación completa y activación; el listado no acredita que las ofertas sigan aceptando candidaturas.

Informe reproducible: `python -m corkjobradar autoapply ats-inventory` o `scripts/audit_stored_ats.py`. El panel de compatibilidad tiene un botón para ejecutar/descargar el inventario. Resultado completo versionado en `data/ats-reviews/`; resumen en `logs/external-adapter-stored-ats.json`. Solo contiene información de ofertas y huellas de versiones, sin contactos del candidato.

## Canal adicional documentado: Recruitee

La [Careers Site API](https://docs.recruitee.com/reference/intro-to-careers-site-api) documenta consulta y presentación desde la perspectiva del candidato y permite construir una página/formulario propio. El [endpoint de candidatura](https://docs.recruitee.com/reference/offersoffer_idcandidates) describe campos y archivos multipart. Es una vía técnica más directa que las APIs privadas de empresa anteriores, pero la documentación no resuelve por sí sola las condiciones y controles de cada destino.

`recruitee.py` implementa GET público con robots/DNS/HTTPS validados, identificación exacta de tenant/slug/URLs publicadas, normalización de los campos y preparación **en memoria** de sus nombres multipart documentados. Usa el CV aprobado mediante el cargador de documentos existente, y contactos/LinkedIn/respuestas verificados. No usa enlaces remotos de CV, anexos, tokens extraídos de páginas ni endpoints internos. Los tipos desconocidos, preguntas legales, cuestionarios externos, opciones sin codificador y campos obligatorios sin respuesta mantienen HOLD. LinkedIn se conserva en el CV y se completa en preguntas exactas que lo pidan; no se inventa un campo nativo que el API no documente.

La inspección se integra en el registro cifrado/versionado existente y caduca en 24 horas. La preparación desconectada comprueba campos con Chromium sin conectar el formulario al proveedor; los bloqueos del destino se conservan. El resumen público del paquete expone cuentas/huellas y bloqueos, nunca valores personales ni archivos. `repr` de la petición privada está redactado. La entrada `final_prepared_request` reutiliza la barrera completa prefinal; un borrador preparado no puede convertir una política pausada o un destino pendiente en autorización de envío.

La [autenticación oficial](https://docs.recruitee.com/reference/authentication-1) anuncia token obligatorio desde el **10/02/2027**. El adaptador rechaza consultas sin configurar a partir de esa fecha; no supone acceso anónimo perpetuo. Las [condiciones Tellent](https://tellent.com/terms) y las del empleador requieren revisión del uso concreto. No se interpreta la ausencia de una prohibición localizada como autorización universal.

**Estado del canal: preparación/GET reales comprobados; permiso específico, llenado alojado, transporte POST y recepción externa pendientes.** `automation_permitted=false`, `api_submission_verified=false`, `live_supported=false`. No se añade un emisor real ni se habilita la transición LIVE. No se afirma F4/F5/F6 completadas.

## Evidencia externa y límites

`scripts/probe_external_adapters.py` hace solo GET, sin importar la bóveda del candidato:

- Keeper `4418202009` y GlobeTech `4960319101`: API pública 200 y preguntas reales, con hash/captura conservados. Esto acredita consulta, no recepción.
- Recruitee/Distilled: API pública 200, ocho publicaciones y esquema Frontend Engineer `2777657` normalizado. Las ocho publicaciones quedan capturadas y con estado diagnóstico pendiente; no se añaden como candidaturas ni se califican automáticamente para el perfil.
- Ashby/NETGEAR: `AccessBlocked` en el endpoint público durante este sondeo. No se intenta eludir la restricción. La página nativa requiere JavaScript; no se presenta como formulario rellenado ni como vigencia nuevamente confirmada.

Evidencias en `logs/external-adapter-real-get-*.json` y `data/public-probes/external-adapter-*`. El sondeo es diagnóstico, no una búsqueda completa ni un cambio de estado de vigencia en producción.

La oferta Recruitee capturada está en **Belfast**, exige experiencia y derechos laborales de Irlanda del Norte que no constan; no es una propuesta de candidatura para el usuario. El derecho a trabajar en Irlanda no acredita el de Reino Unido. Se conserva también un enlace a un cuestionario externo para revisión manual, sin visitarlo ni completarlo.

## Qué se prueba y qué falta

Las pruebas reutilizan el esquema público capturado con su procedencia/hash y una identidad ficticia aislada. Comprueban todos los campos conservados, CV PDF con LinkedIn, contactos, respuestas por texto/dominio, tipos legales, IDs de preguntas y codificación multipart. Se rechazan documentos no aprobados, destinos alterados, URL de redes privadas, cambios de esquema y números/fechas no válidos. Los controles existentes vuelven a verificar funciones IT, política, requisitos, transporte, vigencia y duplicados.

El ensayo del codificador sobre servidor propio usa TCP/HTTP real y datos ficticios: el servidor compara campos y PDF, guarda una recepción y rechaza la repetición con 409. **Sigue siendo recepción de un servidor local, no de Recruitee ni de una empresa.** No se usa como condición para activar LIVE. No se ejecuta POST de candidato a ningún proveedor.

Recruitee documenta un [entorno RC para integraciones](https://docs.recruitee.com/reference/quickstart) que requiere acceso concedido y token. Ese quickstart trata integraciones de partner; no acredita acceso actual ni que incluya la Careers API requerida. No disponemos de ese entorno/credenciales y no se contacta con el proveedor, crea cuenta o presenta datos sin autorización. Las pruebas de POST externo autorizado siguen **sin ejecutar**. Un dominio llamado demo o un ejemplo de documentación no concede permiso para crear candidatos.

## Revisión de primera candidatura

Ver [contraste de ofertas reales y bloqueos](FIRST_APPLICATION_REVIEW.md). Ninguna reúne todavía todos los requisitos y autorizaciones. No se solicita permiso de envío sobre una propuesta incompleta. Hay CV 1 pendiente de revisión documental, cero políticas y cero ensayos autorizados. Los 22 hechos aprobados se mantienen.

Para continuar: conseguir un entorno de pruebas autorizado o acreditar un canal concreto permitido, completar su transporte/recepción sin datos inventados, resolver requisitos/ruta y CV/política de una vacante compatible. Entonces se podrá presentar el paquete completo al usuario y esperar consentimiento para **un único ensayo real**. Solo tras su recepción externa y auditoría se podrá liberar la activación separada del modo A, con cupos y sin aprobación individual dentro de la política.
