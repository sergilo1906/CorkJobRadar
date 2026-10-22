# Candidatura verificable: alcance de esta continuación

La automatización externa permanece **sin liberar**. Se amplían las verificaciones y la vía manual sobre el código anterior; no se sustituyen los 22 hechos, su aprobación, el CV ni las políticas. El estado final de pruebas consta en `TEST_REPORT.md` y `PROGRESO.md`.

## Preparación manual persistente

En **Candidaturas automáticas → Preparar paquete para intervención manual** se elige una vacante IT confirmada y opcionalmente una inspección vigente de sus preguntas. Hace falta aprobar la versión definitiva del CV; la aprobación anterior de los hechos no se repite ni sustituye esa revisión documental.

El paquete guarda cifrados CV, contactos, LinkedIn, respuestas exactas/dominio con su dato de procedencia y preguntas pendientes. Conserva huellas de oferta/ficha/documento/formulario, caducidad de 24 horas y bloqueos. No inventa respuestas, no adjunta anexos y no prepara puestos no IT. Una pregunta sin resolver permanece visible. Sin inspección, todas las preguntas del sitio requieren revisión manual.

Las versiones se recuperan desde SQLite tras reiniciar la interfaz. La descarga ZIP se genera en memoria, lleva el PDF/DOCX aprobado, datos/respuestas y advertencias. **El ZIP descargado contiene datos personales en claro**; la copia persistente permanece DPAPI. Ni preparar, descargar ni abrir el enlace oficial crean una candidatura enviada o reservan un envío automático. Antes de descargar se vuelven a contrastar vigencia de la inspección, IT actual, ficha, CV, URL y duplicados. Cambiar estas condiciones bloquea la reutilización del paquete.

La casilla **Ya he presentado esta candidatura manualmente** registra exclusivamente una declaración del usuario. Se muestra `DECLARED_NO_EXTERNAL_RECEIPT`, se conserva seguimiento `solicitada` y se bloquean duplicados entre fuentes, incluso después de reiniciar. No se crea `ENVIADA_CONFIRMADA` ni evidencia externa. El registro es idempotente y transaccional. Puede registrar una presentación pasada aunque haya cambiado el perfil; eso no vuelve a habilitar el CV antiguo para descargar/enviar. Los paquetes cifrados se incluyen en borrado profesional y copias de seguridad. La deduplicación general conserva las ofertas que ya tienen estos registros.

## Validación inmediatamente anterior al envío

`final_submission_gate` amplía la comprobación anterior: vuelve a consultar la oferta IT actual, política/pausa/epoch, CV y ficha, requisitos y análisis más reciente, transporte vigente, duplicados, cupos, destino, preguntas y huella de formulario. Exige evidencia de haber validado el formulario alojado o una API de envío; un esquema público reconstruido no basta. Devuelve únicamente metadatos de validación y no envía.

La transición a `ENVIANDO` exige esta barrera adicional, detrás del bloqueo LIVE independiente. Las pruebas positivas emplean una capacidad hipotética aislada; **ningún adaptador público obtiene esa capacidad**. La comprobación no sustituye el permiso del ATS, el consentimiento del ensayo, la prueba real ni la activación separada de la política autónoma.

## Transporte desde Ballinlough

El planificador sigue sin asumir coche. Ahora acepta cuatro accesos declarados separados (origen→parada, parada→trabajo, trabajo→parada de vuelta y parada→origen). Calcula tiempos completos e incluye espera de regreso. Comprueba todos los turnos y fechas explícitos, sin detenerse en el primer día bueno: calendario GTFS, excepciones, regreso tras medianoche, caducidad y cambio de hora. El límite opcional se aplica a ambos trayectos completos. Datos no finitos, negativos, ambiguos o fuera de vigencia quedan retenidos. La UI permite comprobar más fechas con el mismo turno.

Esto no obtiene el turno real de un anuncio que no lo publica ni demuestra una ruta a pie/bici. No se deducen accesos desde distancias en línea recta. El resultado de horarios **no se convierte automáticamente en una ruta aprobada**. Presencial/híbrido sin comprobación real conserva HOLD. El calendario de un operador y unas paradas no demuestra ausencia de otras rutas.

`logs/verified-flow-real-transit.json` conserva una lectura del GTFS oficial importado, con paradas reales de Ballinlough y South Mall y ventana diaria de diagnóstico. No es un turno publicado, no acredita acceso a un trabajo y no guarda una ruta aprobada. Los horarios y excepciones sintéticos de regresión están en bases temporales separadas.

## Ensayo HTTP propio y recepción

`tests/test_autoapply_network_e2e.py` levanta un receptor propio en `127.0.0.1`, puerto efímero y ruta aleatoria, durante la prueba. Usa exclusivamente perfil, hechos y CV ficticios identificados como prueba en una base temporal. Chromium envía multipart real mediante TCP/HTTP; no hay respuesta de red simulada por Playwright en este ensayo. La producción y las restricciones de red de `WebClient` permanecen separadas.

El receptor compara todos los valores esperados y los bytes/hash del CV, rechaza campos o archivos distintos y guarda una sola recepción por vacante en su SQLite temporal. La comprobación cliente contrasta respuesta con POST concreto, hash del cuerpo multipart, PDF, vacante e identificador. El cuerpo de evidencia se cifra; los informes públicos contienen campos/hashes, nunca valores personales.

Los escenarios cubren recibo válido del servidor propio, HTTP 200 sin recibo, pausa antes del POST, cambio a empleo no IT y pregunta obligatoria desconocida. Los tres últimos envían cero POST. No se crea ningún `user_actions` ni `ENVIADA_CONFIRMADA` real; las reservas de simulación se conservan y no se reintenta una recepción incierta. Evidencias por escenario: `logs/verified-flow-network-*.json` y JUnit de integración.

**Este servidor no es un ATS externo ni un sandbox de proveedor. No demuestra recepción externa ni completa F4/F5.** Los parsers de recibo ATS anteriores siguen probados solo con respuestas aisladas. El adaptador externo, permiso y formulario/API completos siguen pendientes.

## Continuación hacia modo A

1. Revisar CV definitivo y configurar límites desde UI; no volver a aprobar los hechos ya guardados.
2. Identificar un canal/entorno ATS propio o expresamente autorizado, o validar una API de candidato documentada para el destino concreto (Recruitee es una vía pendiente). Revisar alcance y autenticación; no obtener credenciales ajenas ni eludir CAPTCHA. [Matriz y fuentes oficiales](AUTOAPPLY_ATS_REVIEW_2026-10-20.md).
3. Completar su adaptador y recepción en ese entorno; conservar peticiones, respuestas y estados sin PII en logs.
4. Resolver requisitos, respuestas y transporte de una vacante IT real compatible. Keeper mantiene pendientes que no se pueden inventar; 1 año y 10 meses no son 2+ años.
5. Obtener autorización expresa para un único ensayo real concreto con paquete ligado a versiones/caducidad; enviar una vez y verificar recepción externa. Ante duda, `ENVIO_INCIERTO` sin reenvío.
6. Solo tras esa evidencia, liberar el transporte y la activación separada de la política autónoma delimitada. Después de activarla, las candidaturas que cumplan sus condiciones no necesitan aprobación individual. Actualmente LIVE OFF, sin envío real ni activación autorizados.
