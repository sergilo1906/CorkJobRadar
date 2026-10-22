# AutoApply: arquitectura y alcance real

Actualización de intervención humana: SQLite **v8** añade sesiones y cola de comandos sin secretos, unidas de forma única a intentos ya reservados. `human_sessions.py` gestiona preparación/metadatos/exclusión; `interactive_worker.py` conserva el actor Playwright fuera de Streamlit; `interactive_browser.py` detiene campos ante CAPTCHA/MFA y revalida datos/CV/formulario/política/IT/ruta/cupos antes de continuar; `interventions_ui.py` muestra estado/recuperación y `interaction_modes.py` separa portales manuales de destinos empresariales. El actor ejecutable solo permite el receptor propio sintético; **ningún transporte interactivo externo está liberado**. [Pruebas, ventana visible y límites](AUTOAPPLY_HUMAN_INTERVENTION.md). Los apartados v5/v6/v7 son historial de diseño.

Implementación local añadida al proyecto existente; **simulación únicamente**. El modo A previsto usa consentimiento por política y no aprobación individual posterior. F5 y F6 no se han ejecutado ni declarado operativos.

Ampliación vigente 20/10: `opportunities.py` inventaría todas las ofertas/ATS con estados explícitos sin cambiar elegibilidad ni datos. `recruitee.py` integra GET público y preparación en memoria del multipart documentado; reutiliza almacén de inspecciones cifrado, respuestas exactas/CV aprobado y barrera prefinal. No hay transporte POST externo ni parser de recepción Recruitee presentado como validado. `forms.py` conserva HOLD del proveedor incluso después de rellenar HTML desconectado. El registro de capacidades no concede permiso ni envío live a este adaptador. Detalles: [integración externa](AUTOAPPLY_EXTERNAL_ADAPTER.md). Los apartados v5/v6 siguientes conservan el diseño histórico; esquema actual v7.

## Integración

- `autoapply/policy.py`: configuración estricta, consentimiento explícito de simulación, versiones inmutables, huella SHA-256, usuario local, caducidad, pausa/revocación y vínculo con perfil/motor.
- `autoapply/eligibility.py`: única decisión determinista ALLOW/HOLD/BLOCK. La puntuación no anula un bloqueo; confianza independiente. La falta de hechos nunca se convierte en autorización por timeout.
- `autoapply/store.py`: planes persistentes, reservas atómicas `BEGIN IMMEDIATE`, identidades entre fuentes, cuotas, estados y conciliación conservadora.
- `autoapply/vault.py`: hechos y plantillas de respuesta cifrados con DPAPI del usuario Windows. `candidate_facts` con campos `claim:*` forma el ledger de afirmaciones: texto, origen cifrado, fecha, usuario y revocación. No se importan como hechos los datos incompletos del perfil de búsqueda.
- `autoapply/documents.py`: PDF/DOCX reales con afirmaciones inglesas aprobadas. Adaptación por orden de coincidencias literales, sin añadir competencias. Carta inglesa mediante plantilla fiel. Importaciones requieren revisión humana completa; presencia de citas no prueba automáticamente la veracidad de un documento ajeno.
- `autoapply/browser.py`: Playwright/Chromium **offline**, sin credenciales, capturas ni acceso a la red. Solo recursos locales suministrados en memoria bajo un origen `.invalid`; rutas desconocidas se abortan, WebSocket y service workers bloqueados. Familias de formularios de prueba: Greenhouse, Lever y Recruitee.
- `autoapply/platforms.py`: registro de capacidades controlado por código, GET público Greenhouse y generador de regresión local a partir del esquema. Ningún adaptador de envío real verificado.
- `autoapply/workbench.py`: recorrido de estados con navegador y documentos reales en bases sintéticas aisladas. Rechaza explícitamente `data/radar.sqlite3` y ofertas sin marcador de fixture.
- `autoapply/engine.py`: procesa todas las ofertas locales. Una vista previa limitada no limita el trabajador completo. Cada oferta obtiene plan y motivos; las cuotas afectan preparación, no conservación ni búsqueda.
- `autoapply/ui.py`, `cli.py`: séptima pestaña, ficha, CV/carta, política, revisión factual, rutas, vista previa, proceso independiente, pausa y exportación. Reiniciar Streamlit no inicia trabajadores.

## SQLite v5 y conservación

La migración añade `autoapply_policies`, `autoapply_control`, `candidate_facts`, `candidate_documents`, `job_clearances`, `application_plans`, `application_attempts`, `application_answers`, `application_events`, `application_reservations`, `application_identities`. No elimina ni reescribe tablas históricas. Auditoría append-only; políticas inmutables. Las respuestas de formularios se trazan por ID de hecho y hash, sin texto personal en los eventos.

Antes de migrar se guarda copia SQLite consistente. Se ha restaurado una copia v4 y migrado a v5 comparando todas las filas históricas. La reversión admitida es restaurar **en una ruta nueva**, comprobarla y usar el código archivado correspondiente; no hay botón destructivo para sustituir la base en uso. Copia inicial y manifiesto: `data/backups/before-autoapply-20261019-185937/`.

La deduplicación antigua conserva por separado registros ya referenciados por AutoApply para no alterar pruebas de candidaturas; los marca como posibles duplicados. Las identidades de solicitud siguen bloqueando intentos repetidos.

## Estados y recuperación

Planes: `NO_ELEGIBLE`, `PENDIENTE_VERIFICACION`, `LISTA_PARA_PREPARAR`. Intentos: `APROBADA_POR_POLITICA → PREPARADA → RELLENANDO → LISTA_PARA_ENVIO → SIMULADA_SIN_ENVIO` en el banco de pruebas. Retenciones, cancelaciones y fallos conservan registro. No se marca una candidatura solicitada en `user_actions` por una simulación.

Las transiciones futuras `ENVIANDO → ENVIADA_CONFIRMADA / ENVIO_INCIERTO` están preparadas, pero entrar en envío o confirmar una candidatura real exige una liberación que actualmente siempre se deniega. Un registro interrumpido en ENVIANDO pasa a ENVIO_INCIERTO; no se reintenta. Los intentos previos al envío interrumpidos se cancelan conservando reservas e identidades.

`resolution.py` añade acciones manuales auditadas desde CLI/UI: No repetir y Marcar resuelta conservan identidad y cupos y jamás fabrican confirmación externa ni `user_actions`. Una resolución manual bloquea nuevos reintentos. El reintento disponible solo revalida y prepara documentos de **SIMULATION** con diario completo previo al envío, reserva original, política/ficha/anuncio/evidencias vigentes y elegibilidad recalculada. Nunca entra en formularios públicos. Si algún evento alcanzó ENVIANDO/INCIERTO/CONFIRMADA, o falta diario, se rechaza. Se reutiliza el mismo intento y se fecha su reserva de nuevo tras comprobar cuotas sin contar dos veces ese intento. Error de CV revierte la transacción completa. La conciliación/reintento de un envío LIVE sigue pendiente y bloqueada.

Un único lock por base serializa búsquedas y simulaciones. La UI permanece separada. No se instalan servicios, tareas programadas ni arranque automático. La simulación se vuelve a lanzar deliberadamente; sus planes son idempotentes. No hay reintento automático del clic final.

## Límite de la simulación real

El trabajador de ofertas reales evalúa y persiste planes; con un futuro ALLOW podría preparar el documento aprobado. **No rellena formularios públicos**, porque un upload o autosave ya transmitiría datos. El recorrido completo de formulario ocurre únicamente con fixtures sintéticos offline. F4 necesita además autorización contractual y validar el DOM alojado, no solo el esquema JSON; F5 necesita autorización específica de una oferta elegida por el usuario; F6 sigue bloqueada.
# Continuación v6 — 20/10/2026

Además del diseño histórico siguiente: borradores en `candidate_documents` con `approved_at=NULL`, revisión por hash de fichero y ficha, huella documental independiente de las respuestas de formularios y aprobación explícita persistente. La huella completa de autorización sí incluye las respuestas, y cambiarlas pausa la política. La migración v6 añade inspecciones cifradas, planes/consentimientos inmutables de ensayo único y evidencias inmutables de recibos. Los recibos LIVE solo pueden confirmar un intento si tienen evidencia validada ligada al despacho POST y al posting; el simulador no escribe `user_actions`. La barrera LIVE y `CHECK(live_enabled=0)` siguen activas. Manual y evidencia actual: `AUTOAPPLY_OPERATIONS.md`.

# Ampliación de continuidad: esquema v7

El flujo actual añade `compatibility.py` (catálogo documental sin conceder capacidades), `handoff.py`/`manual_ui.py` (paquete DPAPI y declaración manual diferenciada), `final_gate.py` (reevaluación completa antes de ENVIANDO, detrás del bloqueo LIVE) y comprobación multifecha con accesos separados en `transit.py`. `manual_application_handoffs` y `manual_application_declarations` son aditivos; una declaración crea seguimiento idempotente y bloquea duplicados sin afirmar recepción externa. La deduplicación general conserva sus referencias. El borrado profesional y los backups incluyen paquetes cifrados. Detalles y límites: [flujo verificable](AUTOAPPLY_VERIFIED_FLOW.md).

El receptor loopback existe exclusivamente en `tests/`; no es un adaptador externo, no usa datos del usuario ni altera capacidades de producción. F4/F5/F6 continúan sin completar; LIVE bloqueado. La arquitectura anterior se conserva abajo como historial.

