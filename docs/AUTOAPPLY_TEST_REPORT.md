# AutoApply: informe de pruebas y límites

## Intervención humana — 20/10/2026

**Suite completa final: 399 PASS**, cero fallos/errores/omitidas, 23 avisos de deprecación y **496,96 s** (`human-intervention-final.xml`/`.log`). LIVE OFF. Pausa/recuperación y modo manual implementados sobre la arquitectura previa, sin formularios ni candidaturas externos. Pruebas dirigidas: 29 PASS y después **34 PASS** (`human-intervention-fixed.xml`, `human-intervention-actor-fixed.xml`), solapadas. Cierre seleccionado **5 PASS / 31 deseleccionadas**, 36,21 s (`human-intervention-visible-ready.xml`): dos casos CAPTCHA/MFA con Chromium **visible**, desafío reaparecido en Submit bloqueado, proceso independiente con ventana conservada entre lecturas y cierre por borrado profesional. Las deselecciones no son casos superados adicionales. No repetir toda la suite sin cambios/fallos/dudas nuevos.

Los fallos iniciales y correcciones se conservan: 14 FAIL/15 PASS por tipo del campo email del fixture y ciclo de Playwright; 74 PASS/2 FAIL por redirección y PID del lanzador Windows; una ejecución visible interrumpida por guard DOM durante navegación y falta de Chromium con ventana; siguiente 3 PASS/2 FAIL por ejecutable ausente. Se instaló Chromium completo en el proyecto y se ejecutó con ventana. El instalador reproducible deja de usar solo headless. No se ocultan los XML/logs fallidos ni se presentan como defectos externos del ATS.

Guardas: detectar antes/después de cada campo, cancelar submit ante verificación reaparecida, revalidación completa de datos/CV/política/IT/requisitos/ruta/fecha/cupos/duplicados y comprobación de hash del archivo adjunto. Los 3xx se inspeccionan sin seguirlos; no se hereda permiso de un portal. Campos/archivo alterados y preguntas desconocidas retienen; esconder el widget no acredita verificación. El receptor local vincula sesión activa/verificación, multipart y recibo persistido; un 200 incompleto produce incertidumbre sin reintento. **Ningún recibo local marca ENVIADA_CONFIRMADA ni crea seguimiento empresarial.**

Chromium contra el Streamlit real correcto: `logs/human-intervention-browser.json`, sección pendiente/modos manuales/refresco visibles, sin alterar tablas ni aprobaciones. CLI/pip/compilación/doctors correctos, nuevo comando de intervenciones vacío y LIVE exit 2 (`human-intervention-cli-check.json`). Auditoría `human-intervention-production-audit.json`: SQLite v8 y transporte íntegros/FK correctas, todas las filas previas iguales, nuevas tablas vacías, 459 ofertas/22 hechos, CV 1 pendiente, cero políticas/ensayos/intentos/recibos, cero contactos en texto plano en bases y 30 logs examinados.

Alcance y comandos: [intervención humana](AUTOAPPLY_HUMAN_INTERVENTION.md). Falta plataforma/permiso/DOM y comprobación de verificación externos, entorno autorizado, ensayo expresamente aprobado y confirmación empresarial. No declarar completada esa funcionalidad ni liberar LIVE. Los resultados de integración externos y cifras siguientes son historial previo.

Auditoría posterior de cierre: `human-intervention-delivery-audit.json`, sin cambios de filas previas ni contactos en bases/34 logs; tablas nuevas vacías. El instalador actualizado se ejecutó con exit 0 y doctor confirma Chromium visible/barreras externas OFF (`human-intervention-installer-script.log`). Copia final y hashes: `human-intervention-final-backup.json`. No hay pruebas/trabajadores interactivos activos.

## Resultado vigente — integración externa, 20/10/2026

**Suite completa: 363 PASS**, cero fallos, cero errores, cero omitidas; 23 avisos Streamlit/NumPy, 301,67 s. JUnit/log `logs/external-adapter-final.xml` y `.log`. La referencia de entrada era 333; no se suman las suites dirigidas de 44/43/30/5 casos porque se solapan. No hay nueva dependencia ni esquema SQLite.

Nuevas pruebas: normalización del esquema Recruitee real capturado con procedencia/hash; todos los campos/preguntas conservados; URL/tenant/slug/origen y fecha de token; respuestas legales sin alias automático; tipos y documentos aprobados; codificador multipart con IDs/booleanos/fechas/números; LinkedIn del CV y pregunta específica sin campo nativo inventado. Chromium desconectado y receptor HTTP propio comprueban el formato con identidad ficticia y archivo real, recepción local y rechazo de duplicado 409. La prueba separa preguntas sintéticas añadidas del esquema que el proveedor publicó. Pausa antes de preparar la petición final bloquea sin despachar.

GET externos comprobados: Keeper/GlobeTech/Recruitee 200; Ashby/NETGEAR `AccessBlocked`, sin alternativa que eluda la restricción (`logs/external-adapter-real-get-2026-10-20T144759+0100.json`). **No se hizo POST a ningún ATS ni se probó recepción de una empresa.** No hay sandbox externo autorizado disponible. Las pruebas del servidor propio no completan esa fase.

UI real Chromium: inventario de las 459 ofertas visible, sin aprobar documento/política ni alterar tablas (`logs/external-adapter-browser.json`). Primera ejecución del script falló por selector exacto de etiqueta; fallo conservado en `external-adapter-browser.log`, ejecución corregida en `external-adapter-browser-fixed.log`. No se ha probado un formulario alojado Recruitee ni se declara que funciona.

`logs/external-adapter-production-audit.json`: SQLite v7 y transporte íntegros/FK correctas, comparación EXCEPT de todas las tablas en ambos sentidos contra copia inicial sin diferencias, 459 ofertas/22 hechos, cero intentos/recibos/acciones/consentimientos, CV 1 pendiente y cero políticas. Cero contactos en texto plano en SQLite/WAL/SHM y 17 logs nuevos examinados. Compilación, dependencias y doctors correctos; LIVE exit 2 (`logs/external-adapter-cli-check.json`). Informe/copia anterior conservados.

Reproducir sin envíos: `scripts/audit_stored_ats.py`, `scripts/probe_external_adapters.py` (GET público), `scripts/check_external_adapter_ui.py` (Streamlit existente), `scripts/verify_current_delivery.py --baseline-manifest logs/external-adapter-baseline-backup.json --report logs/external-adapter-production-recheck.json --check-log-prefix external-adapter-`. El auditor exige nombre nuevo para no sobrescribir evidencia. Pruebas aisladas: `python -m pytest -q tests/test_recruitee_preparation.py tests/test_stored_ats_inventory.py --basetemp=data/pytest-next-external --junitxml=logs/external-adapter-next.xml`. No ejecutarlas sobre la base productiva.

Limitaciones/orden pendiente: [integración externa](AUTOAPPLY_EXTERNAL_ADAPTER.md) y [primera candidatura aún retenida](FIRST_APPLICATION_REVIEW.md). LIVE OFF. Los bloques siguientes son históricos y sus cifras no describen la suite vigente.

## Historial de comprobaciones previas

Estado comprobado de continuidad 20:42: suite completa actual **223 superadas**, cero fallos/errores/omitidas, 14 avisos de deprecación, 226,69 s (`logs/continuity-reading-final.xml`). Nuevas barreras de cierre, duplicado manual, reserva/cuota al cambiar de día y resolución/reintento de preparación simulada incluidas. Chromium real sigue mostrando DESACTIVADO y cero formularios enviados. Doctors exit 0 y LIVE exit 2 verificados; historial conservado contra copia y nueva copia consistente guardada. Los 415 planes históricos siguientes no significan que ya se haya ejecutado la simulación de las 458 ofertas actuales: el continuador espera a la cola 12 antes de hacerlo. Envío real y conciliación externa siguen pendientes.

## Continuidad 19/10/2026 — comprobaciones posteriores

Se añadió resolución manual auditada y reintento exclusivo de preparación simulada, sin migrar ni reemplazar SQLite. **36 pruebas superadas**, cuatro avisos de deprecación (`logs/continuity-resolution.xml`, 19,82 s). Incluyen diario posterior a envío rechazado, incertidumbre conservada, No repetir idempotente, vista obsoleta, exclusión de trabajador concurrente, rollback por CV inválido, duplicado manual y mismo intento/reserva reutilizados. La rama ALLOW del reintento usa una decisión sintética explícita en el test, con documentos, transacciones y prefinal reales; no demuestra elegibilidad de ofertas de producción ni permiso de un ATS.

Suite UI y regresión documental posterior: **19 superadas**, diez avisos (`logs/continuity-experience-after.xml`). La suite completa actual está en `logs/continuity-full.log`/`.xml`; solo dar por válida su cifra cuando termine. El envío LIVE sigue bloqueado. Las cifras de 415 siguientes corresponden al informe histórico, no al estado actual de 458 ofertas.

Generado: 2026-10-19T19:29:11+01:00. Windows 11 / Python 3.12.4, `.venv` del proyecto. **Simulación únicamente; ningún envío real.**

## Resultado medido

- Baseline antes de AutoApply: **100 pruebas superadas**, 143.50 s, 10 avisos existentes (`logs/autoapply-baseline.xml`).
- Suite final: **151 pruebas superadas**, 0 fallos, 0 errores, 0 omitidas, 182.34 s (`logs/autoapply-delivery.xml` / `.log`). 14 avisos de deprecación Streamlit/NumPy, no fallos.
- F1 dirigida: 26 superadas. F2: un primer fallo al normalizar errores de PDF inválido, corregido; 4 casos específicos superados después. Primeras pruebas Chromium: 10 superadas. Integración F3/UI: 30 superadas. Seguridad combinada: 40 superadas. Casos adicionales: 8 superados. Las suites se solapan: no sumar sus recuentos como casos distintos.
- Dos suites completas intermedias de 148 casos también pasaron; se preservan sus XML y logs. Tres casos posteriores prueban números no finitos para no permitir salario/score/confianza desconocidos.
- `pip check` sin dependencias rotas, `compileall` sin errores. Instalación opcional real desde ausencia de Playwright/ReportLab y repetición de `instalar-autoapply.ps1` correctas. Chromium se ha lanzado en este Windows; no solo instalado.

## Prueba sobre datos reales sin envío

`autoapply run --dry-run`: **415 ofertas procesadas, 415 decisiones BLOCK por política OFF, cero errores, cero intentos y cero candidaturas enviadas**. La segunda ejecución no duplicó planes. Los motivos están persistidos; no son una afirmación de que esas ofertas nunca puedan ser elegibles tras configurar datos y permisos.

`autoapply run --live`: código de salida **2**, `LIVE_LOCKED`; comprobado sin crear intentos. `policy validate` del ejemplo y `reconcile` sin correo ni clics también ejecutados. No se ha aceptado una política activa en producción ni añadido datos personales ficticios.

Inspección pública real Greenhouse de GlobeTech Cork (19/10/2026): GET con preguntas, idioma nativo y GDPR; evidencia en `logs/autoapply-greenhouse-inspection-d23d74f13d944cc3a670bb1f0ab6e75a.json`. Ningún dato del candidato se envió a esa web. Las condiciones de automatización y el DOM alojado no se han validado para enviar.

Streamlit real iniciado en `127.0.0.1:8501`, no solo AppTest. Chromium abrió la pestaña nueva y encontró el estado `DESACTIVADO` y el botón de pausa; cero formularios enviados (`logs/autoapply-ui-browser.json`). Los controles de datos/política/trabajador se prueban además con AppTest sobre SQLite aislada.

## Conservación y exportación

La copia inicial contiene código/config/tests/docs, SQLite principal v4 y SQLite de transporte, con SHA-256 en `data/backups/before-autoapply-20261019-185937/manifest.json`. Integridad/FK verificadas. La primera comprobación del ZIP se ejecutó antes de cerrar el escritor y falló; se reabrió y verificó después correctamente, registrado en el manifiesto.

Restauración a `data/autoapply-restoration-test.sqlite3` y migración v4→v5: **todas las filas históricas iguales**, integridad OK, cero errores FK (`logs/autoapply-restoration-test.json`). Auditoría final: todas las tablas de negocio anteriores conservan exactamente sus filas. Solo la caché HTTP incorpora la lectura pública deliberada del formulario. No se han borrado ofertas, notas ni candidaturas; no hay fixtures ni hechos profesionales sintéticos en producción.

Excel reabierto: **415 ofertas, 415 planes, 0 intentos y 0 candidaturas**, con eventos/cupos. JSON reabierto y CSV BOM comprobados. Archivos exactos en `logs/autoapply-final-audit.json`, bajo `exports/autoapply-verified/`. La exportación no incluye el contenido descifrado de la bóveda.

## Escenarios reproducibles cubiertos

| Grupo | Comprobación |
|---|---|
| Política | OFF, caducada, perfil cambiado, revocación, pausa antes del paso final, inmutabilidad y auditoría append-only |
| Preferencias | IT sin ruta aunque esté en radio de coche; IT fin de semana con ruta; NO IT bici o bus directo; transbordos rechazados |
| Datos | Requisitos/permiso laboral/CV ausentes, vigencia dudosa, bolsa de talento, salario/horario desconocidos, análisis desactualizado |
| Duplicados | Indeed/web oficial, dos reservas concurrentes, cuota diaria, cancelación/incertidumbre conservan identidad |
| Formularios | Greenhouse/Lever sintéticos, regresión de esquema Cork, campos/etiquetas, uploads PDF/DOCX, selects, HTML inválido, campos añadidos |
| Bloqueos | CAPTCHA/login/MFA representado por campos, firma/consentimiento/preguntas obligatorias sin respuesta, bloqueo de red y redirects privados |
| Confirmación | HTTP 200 sin recibo no confirma; recibo con ID de oferta y referencia; acción no iniciada no confirma; correo ausente no se inventa |
| Recuperación | Navegador cerrado, cambio de CV/ficha durante relleno, caída tras acción de fixture, ENVIO_INCIERTO sin reintento |
| Privacidad | DPAPI real, ACL Windows, sin contacto en eventos, PDF inválido rechazado, hashes, borrado y revocación |
| Inyección | Texto del anuncio no modifica destino/afirmaciones; exfiltración a loopback abortada por sandbox offline |

## Reproducir

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=data\pytest-autoapply-recheck --junitxml=logs\autoapply-recheck.xml
.\.venv\Scripts\python.exe -m corkjobradar autoapply doctor
.\.venv\Scripts\python.exe -m corkjobradar autoapply run --dry-run
.\.venv\Scripts\python.exe scripts\check_autoapply_ui.py
```

Las pruebas son secuenciales y usan bases temporales del proyecto. La comprobación de navegador UI requiere Streamlit local iniciado; no pulsa botones que envíen ni rellena datos reales. El auditor `scripts/audit_autoapply.py` compara con el estado inicial de esta intervención, por lo que detectará también cambios legítimos que haga el usuario posteriormente: no deben borrarse para forzar igualdad.

## No probado / pendiente

F4 parcial: adaptar y validar formularios alojados de un ATS con permiso de automatización. F5: ensayo real concreto todavía no autorizado. F6: backend de envío y confirmación real, conciliación fiable/seguimiento y activación live por política pendientes; no basta retirar una bandera. F7: plataformas adicionales. No hay lector de correo, compatibilidad universal ni análisis semántico exhaustivo validado. Cancelados/inciertos no tienen reintento automático ni botón para liberar reservas sin prueba.

La incidencia de TEMP del controlador en las primeras pruebas se explica en `AUTOAPPLY_SAFETY.md`; está corregida y cubierta por regresión. Los resultados offline no acreditan permiso contractual ni funcionamiento de un envío real.
> Actualización vigente 20/10/2026: AutoApply exclusivamente IT. Las pruebas históricas NO IT de este informe describen el comportamiento anterior; ya no autorizan candidaturas. Consultar `AUTOAPPLY_IT_ONLY.md`, `TEST_REPORT.md` y `logs/it-only-*.xml` para la regresión actual. LIVE OFF.

> Continuación 20/10/2026: resultado final **295 pruebas superadas** (`logs/operational-final.xml`, cero fallos/errores/omitidas, 20 avisos). UI real, capturas públicas y preparación desconectada comprobadas por separado. El formulario remoto declara CAPTCHA y no se ha rellenado ni enviado. Recibos solo probados con despachos sintéticos, LIVE OFF. Estado vigente en `AUTOAPPLY_OPERATIONS.md`; los números siguientes son históricos.

# Continuación de flujo verificable (20/10/2026)

Evidencias nuevas: `logs/verified-flow-*.xml` y `docs/AUTOAPPLY_VERIFIED_FLOW.md`. **Suite completa final: 333 PASS, cero fallos/errores/omitidas, 21 avisos de deprecación y 280,86 s** (`logs/verified-flow-final.xml`). Dirigidas 68/36 PASS, solapadas; primera completa 332 PASS/1 FAIL corregido en UI de transporte; dirigida posterior UI/transporte 20 PASS. No sumar suites. Se conservan informes fallidos de fixture/red y el primer full; no son evidencia de recepción ATS.

Chromium real sobre Streamlit pasa la matriz de permisos y la retención del paquete manual hasta aprobar CV. Auditoría compara todas las tablas previas con la copia de inicio: intactas, ambas SQLite íntegras, cero contactos en claro, cero envíos/consentimientos reales. `pip check`, compilación, doctor y barrera `--live` (exit 2) comprobados. Receptor HTTP local propio con datos ficticios: cuerpo multipart/PDF/recibo persistido contrastados; 200 sin recibo no confirma. No se ha rellenado ni enviado ningún formulario ATS externo con datos personales.

SQLite v7 aditiva y sus migraciones v1/v5/v6 se prueban en copias temporales; no se restaura producción. F4/F5/F6 siguen pendientes. Los bloques inferiores describen fases previas.

