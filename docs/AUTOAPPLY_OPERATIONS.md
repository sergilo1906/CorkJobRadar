# AutoApply: revisión y preparación operativas, envío real bloqueado

Continuación vigente: [flujo verificable, paquete manual, transporte y prueba HTTP propia](AUTOAPPLY_VERIFIED_FLOW.md); [revisión oficial ATS](AUTOAPPLY_ATS_REVIEW_2026-10-20.md). SQLite v7 aditiva. Los resultados finales actuales están en `PROGRESO.md` y `TEST_REPORT.md`; las cifras v6/295 siguientes corresponden a la fase anterior. LIVE continúa OFF y no existe recepción ATS externa comprobada.

Estado del desarrollo 20/10/2026. Se reutilizan las reglas IT, cuotas, identidades, hechos aprobados y registros anteriores. Este documento distingue capacidades implementadas de pruebas con formularios alojados o envíos reales aún pendientes.

## CV definitivo y política

La pestaña **Candidaturas automáticas → CV fundamentado en inglés** muestra versiones persistentes. El borrador PDF preparado con los 22 hechos aprobados está cifrado y pendiente; se puede leer el texto íntegro y descargar. Tras revisar la versión, la casilla de confirmación habilita **Guardar esta versión validada del CV**. La aprobación liga archivo/hash, afirmaciones y ficha; un cambio del contenido profesional invalida el documento. Reiniciar Streamlit conserva el borrador y nunca lo aprueba. Los anexos permanecen fuera del CV y sin autorización.

El editor de política es guiado: IT obligatorio, modalidades, plataformas, dominios exactos, Cork City/área de Cork, límite de trayecto, turnos, contratos, jornada, salario duro opcional, encaje/confianza, cupos diarios/semanales/empresa, espera por empresa, ventana Dublin, caducidad y permisos de preparación. Los requisitos obligatorios, descripción íntegra, vigencia, duplicados y transporte verificado no se pueden desactivar. Seleccionar plataforma no autoriza implícitamente sus dominios ni concede permiso contractual.

Guardar una política exige CV aprobado, campos explícitos y consentimiento de **simulación**; no arranca trabajadores. La política guarda las versiones de ficha/CV/adaptador. Leer correo y enviar permanecen desactivados. Las respuestas a preguntas se vinculan a texto exacto y dominio: se pueden guardar desde el panel de preguntas pendientes. Añadir respuestas pausa la política sin obligar a volver a aprobar un CV cuyo contenido no cambió. La huella de autorización abarca también respuestas; la huella documental solo los hechos que respaldan el CV.

## Formularios reales: alcance comprobado

- Greenhouse: GET real de la vacante **IT Support Specialist de Keeper**, Cork, posting `4418202009`, esquema de 16 campos. [Vacante](https://job-boards.greenhouse.io/keepersecurity/jobs/4418202009). El esquema público se transforma en campos versionados y la preparación se comprueba en Playwright **sin conexión al ATS**. No equivale a completar el DOM React alojado.
- Preparación real desconectada con la ficha aprobada y CV de revisión: nombre, apellidos, email, teléfono, CV, LinkedIn, localización y autorización laboral. Sigue **HOLD**: faltan respuestas verificadas sobre patrocinio futuro, residencia permanente, disponibilidad híbrida, 2+ años de experiencia, caso técnico y expectativas salariales. No se redondean 1 año y 10 meses a dos años ni se inventan historias.
- Una pregunta exacta sobre autorización laboral en Irlanda puede reutilizar el dato ya aprobado cuando la opción «Yes» es inequívoca. No se deducen patrocinio futuro, residencia permanente, experiencia total ni aceptaciones legales. Las demás preguntas conservan HOLD hasta contar con respuesta verificada.
- HTML real de Greenhouse/GlobeTech leído solo por GET: contiene controles dinámicos y un formulario GET intermediario; no se declara validado por tener inputs en HTML. No se automatizan endpoints ocultos.
- Lectura Playwright real del DOM de Keeper con transporte GET restringido: declara reCAPTCHA, sin elementos de reto visibles en ese corte. Se registra `HOSTED_CAPTCHA_DECLARED_OR_DETECTED` en la inspección 2 y se detiene la carga de subrecursos. No se intenta resolverlo ni se introduce información personal. `interactive_completion_verified=false`; el esquema público no sustituye la validación del formulario alojado.
- Lever: GET real de [Integration Engineer de Bright Machines](https://jobs.lever.co/brightmachines/92b0e3d3-00e1-43d6-abde-a7efc492416d/apply), usado exclusivamente para comprobar el lector público. Se observaron 13 campos y **CAPTCHA**; se conserva el bloqueo. No se rellenó ni se usó esa vacante como objetivo autorizado. Se guarda captura pública con procedencia para regresión sin Internet.

La [API oficial de Greenhouse](https://docs.greenhouse.io/job-board) requiere credenciales de empresa para POST; la [API oficial de Lever](https://github.com/lever/postings-api#apply-to-a-job-posting) también exige API key de una cuenta de empresa. La disponibilidad de GET no acredita permiso de automatizar envío. No hay credenciales/permiso de envío ni adaptador alojado liberado. No se eluden CAPTCHA o restricciones, ni se pide al usuario conseguir credenciales de otra empresa.

Las inspecciones caducan en 24 horas, quedan ligadas al anuncio y versión del adaptador y se conservan cifradas. Una preparación puede usar un CV pendiente **solo en la revisión local desconectada**, con marca explícita; no lo convierte en documento autorizado, no crea intentos/reservas y nunca concede elegibilidad. La inspección o el formulario remoto no reciben datos personales.

## Ensayo controlado y recepción

La interfaz/CLI permiten crear un plan de ensayo sin autorizarlo. Congela vacante, CV, ficha, política, formulario, versión del adaptador y caducidad de 24 horas. Una autorización futura exige hash exacto, consentimiento específico `AUTHORIZE_ONE_CONTROLLED_APPLICATION` y máximo de un envío. Cambiar el paquete exige una revisión nueva. La autorización no activa el modo autónomo. Hoy los requisitos y el transporte real están pendientes: el botón de autorización permanece bloqueado y el ejecutor falla cerrado.

El verificador de recibos de Lever exige respuesta documentada `ok: true` y `applicationId`, endpoint/posting coincidentes y diario de despacho correlacionado. HTTP 200 sin recibo, error, redirección o falta de correlación no confirman. La evidencia se cifra y es inmutable; no se almacenan API keys en las URLs del diario de recibos. En simulación nunca se escriben candidaturas reales. El registro futuro LIVE exige además permiso/versión del adaptador y barrera de release; un recibo validado será necesario para `ENVIADA_CONFIRMADA` y seguimiento idempotente en `user_actions`. Respuestas inciertas conservan identidad y no autorizan reenvío. Esta rama solo se ha probado con despachos sintéticos aislados; **ninguna recepción real se ha verificado todavía**.

El modo A conserva la decisión por política, sin aprobación individual posterior. El diagnóstico de activación enumera CV, política, adaptador/permiso y ensayo real pendientes. El envío autónomo y el ensayo real siguen bloqueados tanto en el código como en SQLite (`live_enabled=0`). No hay nueva tarea programada ni servicio de Windows.

## Persistencia, pruebas y comandos

SQLite v6 añade inspecciones, planes/consentimientos de ensayo y evidencias de recibos sin alterar las tablas anteriores. Copia previa: `data/backups/before-autoapply-operational-2026-10-20T110150+0100/`; la migración también genera copia v5 antes de abrir v6. Datos y afirmaciones aprobados se conservan.

Evidencias separadas:

- Suites de código: `logs/operational-*.xml`; no sumar suites solapadas. Resultado completo vigente en `TEST_REPORT.md`.
- Regresión final de esta fase: **295 pruebas superadas**, cero fallos/errores/omitidas, 20 avisos de deprecación, 238,75 s (`logs/operational-final.xml`). La suite completa intermedia de 282 casos y las 120 pruebas AutoApply quedan conservadas y no se suman.
- Comprobación posterior de todo AutoApply: **136 superadas**, 10 avisos, 62,94 s (`logs/operational-scope-final.xml`), tras exigir clasificación IT actual también al reabrir una inspección aunque el hash siga igual. No sumar con la suite completa.
- GET y HTML reales: `logs/operational-public-form-probes.json`, `logs/operational-real-greenhouse.log`, `logs/operational-real-lever.json`.
- Preparación desconectada con ficha real: `logs/operational-real-preparation-verified.log`; sin valores personales, cero POST. El CV pendiente no está aprobado.
- Regresión de capturas públicas, sin Internet ni PII: `scripts/check_public_form_snapshots.py`, `logs/operational-source-regressions.json`.
- Chromium contra la UI real: `logs/operational-ui-browser.json`; borrador persistente visible, guardar deshabilitado hasta revisión, editor guiado e inspección real con bloqueo de CAPTCHA visibles, sin aprobar documento/política ni enviar formularios.
- Auditoría final: `logs/operational-production-state.json`; 459 ofertas, 22 hechos intactos, un CV pendiente y dos inspecciones públicas. Historial original conservado, integridad/FK correctas, cero contactos en texto plano, cero intentos/candidaturas y LIVE OFF. La copia principal y ZIP coinciden con sus hashes; los sidecars transitorios del manifiesto inicial no son necesarios para restaurar (`validation-after-close.json`).

Incidencias conservadas y corregidas: el primer sondeo de DOM omitía permitir `robots.txt` en su lista local; la primera prueba visual no encontraba una opción fuera de la porción virtualizada del desplegable y se corrigió filtrándola por texto. El primer auditor necesitaba abrir la conexión con URI habilitada para adjuntar la copia como inmutable. Sus logs fallidos permanecen junto a los resultados corregidos; no se cambiaron ni restauraron datos para forzar un resultado positivo.

Copia del estado probado, con conexiones cerradas antes de calcular hashes, SQLite íntegra, código/resultados y los PDF/inspecciones todavía cifrados: `logs/operational-checkpoint-backup.json`. La restauración de esos datos permanece local y requiere conservar el mismo usuario Windows para DPAPI; no se restaura sobre producción durante estas comprobaciones.

```powershell
.\.venv\Scripts\python.exe -m corkjobradar autoapply cv prepare --format pdf
.\.venv\Scripts\python.exe -m corkjobradar autoapply form-inspect --job ID_REAL
.\.venv\Scripts\python.exe -m corkjobradar autoapply form-prepare --inspection ID --review-document ID_CV
.\.venv\Scripts\python.exe -m corkjobradar autoapply trial status --job ID_REAL --inspection ID
.\.venv\Scripts\python.exe -m corkjobradar autoapply trial plan --job ID_REAL --inspection ID
.\.venv\Scripts\python.exe -m corkjobradar autoapply readiness
```

Los comandos son concretos pero los IDs deben proceder de la propia base. Aprobar documento o política exige consentimiento expreso y nunca se ejecuta como parte de una prueba contra producción. Para continuar: aprobar el CV desde UI, configurar la política, resolver preguntas/requisitos reales y permisos del primer adaptador; después probar el formulario alojado y diseñar el transporte autorizado antes de solicitar el ensayo real. No declarar AutoApply terminado.
