# Selección IT amplia en 50 km — 21/10/2026

Especificación íntegra conservada en `IT_50KM_REQUEST_2026-10-21.md`. Se sustituye la selección conservadora para esta nueva vía; no se alteran los hechos profesionales ni se concede autorización de envío. **LIVE OFF. CV definitivo pendiente del usuario. Ningún envío externo realizado.**

La clasificación profesional es independiente de permisos, adaptador y capacidad de envío. El checklist factual anterior conserva `CUMPLIDO/NO_CUMPLIDO/PENDIENTE`: una experiencia real de 1 año y 10 meses no pasa a ser 2 o 3 años. Pedir hasta 3 años mínimos admite considerar la candidatura con advertencia aunque exista esa diferencia. No se promete satisfacer todos los requisitos del anunciante.

## Reglas implementadas

- IT por funciones concretas: soporte, aplicaciones, software/web/Java, QA software, sistemas/redes/cloud y otros perfiles tecnológicos. Título, empresa o afinidad por sí solos no autorizan puestos generales. Se amplían literales de desarrollo web y soporte de aplicaciones conservando el control IT existente.
- Distancia geodésica Haversine, radio terrestre medio 6371,0088 km. Compara sin redondear con 50 km inclusive; pequeña tolerancia numérica de 1e-9 km. No estima minutos, salario, autobuses ni horarios. Centro aproximado Ballinlough **51.88944, -8.44639**, [referencia pública](https://en.wikipedia.org/wiki/Ballinlough%2C_Cork); no es un domicilio particular.
- Origen preciso opcional introducido localmente: BLOB DPAPI ligado al usuario Windows, sin enviar a geocodificadores, mapas o logs. Cambiarlo altera la huella que deberá aceptar una futura política amplia. Los informes contienen solo la huella del origen, nunca sus coordenadas privadas.
- Centro de trabajo: evidencia por oferta/hash/fecha/caducidad y confirmación humana, o `jobLocation.geo` con dirección de centro publicada. Coordenadas municipales publicadas se muestran como punto provisional, sin acreditarlas como oficina exacta. No se deduce el puesto desde el domicilio social. Sin precisión suficiente queda pendiente; no se inventa inclusión/exclusión a partir de un nombre ambiguo. Remotos separados sin autorización adicional automática.
- Experiencia: números y números escritos en inglés, rangos, `3+`, `at least`, `minimum`, `more than`, años/meses y abreviaturas. Compara el mínimo solicitado, no el máximo del intervalo: 3–5 permite, mínimo 4 excluye. Preferibles no excluyen; alternativas académicas ambiguas conservan advertencia. Duraciones de estudios/contexto y máximos `up to` no constituyen mínimos.
- Dudas técnicas/académicas, deseables, salario no publicado y transporte pendiente advierten; no se exige un porcentaje de afinidad. Incumplimiento obligatorio acreditado, coche propio imprescindible y falta legal/habilitación esencial bloquean o requieren intervención. Una ruta de bus fallida aislada no demuestra imposibilidad de todos los medios disponibles.
- `professional_state` presenta selección; `state` añade vigencia/CV/duplicados/intervención/recepción. `ENVIABLE[_CON_ADVERTENCIAS]` describe aptitud según las reglas, **no concede permiso externo**. `authorization` y `live_enabled=false` permanecen explícitos. Declaración manual/recibo local no generan `ENVIADA_CONFIRMADA`. Incertidumbre tras despacho conserva `ENVIO_INCIERTO` e impide repetición.

## Uso

En **Candidaturas automáticas → Candidaturas IT asistidas** aparece la nueva selección y sus filtros. El panel permite precisar origen local, registrar centro verificado, revisar experiencia solicitada y advertencias, preparar/aprobar una versión de CV explícitamente y reutilizar el paquete/copia de respuestas/registro/justificante existentes. El botón de preparación masiva permanece deshabilitado mientras no exista CV aprobado. No solicita permisos API para utilizar las candidaturas manuales.

En las herramientas avanzadas se puede configurar **política amplia IT** para simulación, con dominios, adaptadores, cuotas y caducidad explícitos. Ligada a versión de reglas, origen, ficha y documentos. No se crea ni aprueba automáticamente ninguna política. Se conserva la semántica de políticas históricas `LEGACY_STRICT`, sin ampliar silenciosamente un consentimiento anterior. En modalidad amplia no se utilizan puntuación/confianza para cortar la selección y el trayecto desconocido no impone HOLD; los límites duros adicionales que el usuario configure necesitan evidencia. La barrera final vuelve a consultar la selección y los demás controles vigentes.

```powershell
.\.venv\Scripts\python.exe -m corkjobradar autoapply selection
.\.venv\Scripts\python.exe -m corkjobradar autoapply selection --refresh-queue
.\.venv\Scripts\python.exe -m corkjobradar autoapply selection --prepare-local
```

El último comando prepara **solo archivos locales**, sin HTTP ni formularios externos. Cola SQLite aditiva v11: una fila por cada oferta, historial de cambios, huellas de vigencia/perfil/CV/origen/centro/requisitos/transportes, leases transaccionales y recuperación tras caducidad. Se reutiliza exclusión de trabajadores. No descarta después de 10/20 ofertas ni corta por puntuación; excluidas, ambiguas y duplicadas conservan motivo. Un paquete usa los bytes exactos de un CV aprobado; una nueva versión adaptada se revisa antes de aprobarla, sin aprobación automática ni competencias nuevas.

## Evaluación real y límites

`logs/it-50km-delivery-inventory.json` y `it-50km-delivery-inventory-summary.json`: **579 registros examinados y en cola; 22 hechos conservados; 45 IT confirmadas; 26 permiten preparación documental y 19 IT exceden el mínimo de 3 años**. Los 26 no equivalen a candidaturas listas: geografía precisa, vigencia, legalidad/preguntas según puesto y CV siguen pendientes. Total final de todos los sectores: **171 EXCLUIDA, 408 INTERVENCION_REQUERIDA**. El contexto de encabezados de experiencia reconoce nueve mínimos >3 adicionales frente al inventario inicial, conservado aparte. Cero candidaturas con todos los controles acreditados, cero envíos y cero recepción empresarial. La cola conserva PENDING/EXCLUDED; no se ejecutó preparación sobre datos reales sin CV aprobado.

No hay nuevas fuentes ni recepción externa validadas en esta fase. [LinkedIn](https://www.linkedin.com/help/linkedin/answer/a1341387/prohibition-of-scraping-software) y [Indeed](https://www.indeed.com/legal?hl=en_US) mantienen restricciones de automatización consultadas de nuevo el 21/10/2026; enlaces y paquetes manuales conservados. Redirección empresarial exige revisión independiente. GET público, permiso del usuario o CAPTCHA resuelto no conceden por sí solos permiso de envío.

Activación pendiente de mecanismo permitido y probado, ensayo real autorizado con confirmación externa y consentimiento posterior de política. Las pruebas locales de esta fase no satisfacen esos requisitos.

## Verificación

Última completa **517 PASS** (383,27 s, 23 avisos), posterior **125 PASS** (72,55 s) solapada con contexto de encabezados y lote local de 27 paquetes. No sumar. Chromium final en producción, exportación JSON y controles sin aprobación comprobados en `logs/it-50km-delivery-browser.json`; cero peticiones externas/POST. Auditoría final `logs/it-50km-delivery-audit.json`: ambas bases íntegras y filas anteriores intactas, 37 logs sin contactos; LIVE OFF. Se conservan fallos y correcciones en los informes. Copia previa `logs/it-50km-baseline-backup.json` y final `logs/it-50km-final-backup.json`; hashes/activos/integridad en `logs/it-50km-backup-verification.json`. Nunca restaurar sobre producción. Consultar el checkpoint para los siguientes pasos.
