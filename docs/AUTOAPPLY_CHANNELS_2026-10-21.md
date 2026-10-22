# Canales externos y candidatura asistida — 21/10/2026

**EN DESARROLLO, LIVE OFF. Cero plataformas con envío permitido y técnicamente comprobado en esta instalación.** Se continúa sobre las 399 pruebas completas históricas; no se rehacen CAPTCHA/MFA, navegador interactivo ni la restricción IT. No se han enviado candidaturas, contactado proveedores o creado cuentas.

## Diagnóstico independiente

El panel «Diagnóstico independiente y gestiones de cada canal» y `python -m corkjobradar autoapply blockers` recorren **las 459 ofertas** sin detenerse en el primer bloqueo. Permiso, adaptador, acceso humano, respuestas, transporte, CV/política y compatibilidad son siete ejes distintos. El JSON versionado en `data/ats-reviews/blockers-*.json` contiene cada ID. No crea candidaturas ni autoriza envíos; `ready_to_submit` sigue siendo falso.

| Causa | Estado actual | Responsable de resolverla |
|---|---|---|
| Permiso | Sin concesión específica del destino ni credenciales de integración | Empleador/proveedor; una política personal no lo sustituye |
| Adaptador | Greenhouse/Lever: inspección/preparación. Recruitee: GET/esquema/multipart en memoria. Sin envío/recibo externos comprobados; Ashby/SmartRecruiters sin adaptador de candidatura | Desarrollo sobre un canal autorizado |
| CAPTCHA/autenticación | Observaciones anteriores en Keeper/Lever; no acreditan sesión vigente. Ashby NETGEAR bloquea el sondeo actual | Usuario en sesión permitida; nunca eludir restricciones |
| Preguntas | Esquemas almacenados pueden caducar; se muestran también opcionales desconocidas | Reinspección y respuesta exacta aprobada o dejar opcional en blanco |
| Transporte | Sin trayecto acreditado para los puestos presenciales/híbridos considerados | Verificar centro, días, turno, ida/vuelta desde Ballinlough sin coche; remoto exige permiso desde Irlanda |
| CV/política | 22 hechos aprobados intactos; borrador PDF 1 sin aprobación final, cero políticas | Usuario en la interfaz existente; no repetir la aprobación de hechos |
| Oferta compatible | Ninguna candidatura reúne funciones IT, requisitos, vigencia y accesibilidad acreditados | Evidencia del anuncio y aclaraciones verificables; no inventar cualificaciones |

La lectura diagnóstica de inspecciones antiguas se etiqueta como histórica, sin saltarse caducidad en el preparador ni afirmar que una sesión sigue abierta. HTTP 200 no demuestra aceptación actual de solicitudes ni permiso de presentación.

## Prioridad según los puestos guardados

Se conserva el inventario completo: siete empresas, 85 anuncios por título/funciones para investigar, 39 con funciones IT confirmadas y 22 de ese conjunto dentro del alcance almacenado. No son 22 candidaturas elegibles.

1. **Greenhouse, Keeper/GlobeTech:** primera vía técnica condicionada por los preparadores existentes y puestos Cork. Keeper IT Support `4418202009` exige 2+ años; el perfil acredita 1 año y 10 meses, además de otras respuestas y trayecto híbrido pendientes. No redondear experiencia. Los 11 QA GlobeTech dentro del alcance piden lenguas/variedades nativas no acreditadas.
2. **Ashby, NETGEAR/Qumulo:** Graduate NETGEAR `415ee500-8f36-4766-a9e9-a565827e52c2` pide Level 8 honours completado en el plazo indicado; DAM sigue en curso. Hay contradicción entre modo remoto almacenado y presencialidad del texto; la lectura pública actual está bloqueada. Otras vacantes son senior o geografía/derecho laboral no acreditados. No se fuerza acceso.
3. **Lever, WatchGuard:** renovaciones comerciales por idiomas no tienen funciones IT confirmadas por pertenecer a una empresa tecnológica.
4. **SmartRecruiters, AbbVie/Egis:** las candidatas del inventario están fuera del alcance guardado.
5. **Recruitee, Distilled:** alternativa técnica secundaria, no candidatura elegible de producción. El GET conserva ocho publicaciones diagnósticas fuera del catálogo. Frontend Engineer `2777657` es Belfast, 3–5 años y tiene preguntas externas/privacidad por revisar. Derecho a trabajar en Irlanda no acredita Reino Unido.

## Mecanismos oficiales y permisos

Fuentes revisadas el 21/10. Documentar una API de cliente no concede acceso a candidatos o bots.

| Canal | Mecanismo documentado | Estado y gestión necesaria |
|---|---|---|
| Greenhouse Job Board | GET público; POST Basic Auth con Job Board API Key | Pendiente: titular debe autorizar integración y trabajo/entorno de prueba. [API](https://docs.greenhouse.io/job-board.html) |
| Lever Postings | POST con clave creada por Super Admin del cliente; campos configurados por cuenta | Pendiente: permiso del titular, clave adecuada, preguntas completas y comprobación de recibo. [API](https://github.com/lever/postings-api#apply-to-a-job-posting) |
| Ashby | `applicationForm.submit`, permiso `candidatesWrite`, v2026-01-01 | Pendiente y sin adaptador: autorización de organización y pruebas. Futura implementación fijará `allowSubmissionForUnpublishedJobPosting=false`; el valor por defecto permite no publicadas. [Envío](https://developers.ashbyhq.com/reference/applicationformsubmit), [autenticación](https://developers.ashbyhq.com/reference/authentication) |
| SmartRecruiters | Application API protegida, OAuth `candidate_applications_manage`: configuración, envío y consulta de estado | Pendiente y sin adaptador: integración cliente/partner, avisos y preguntas. [API](https://developers.smartrecruiters.com/docs/application-api) |
| Recruitee Careers Site | Multipart candidato/preguntas; `X-Careers-Sites-Token` obligatorio desde 10/02/2027 | Pendiente: permiso del destino, acceso adecuado, privacidad y confirmación. No confundir con Company API. [Envío](https://docs.recruitee.com/reference/offersoffer_idcandidates), [autenticación](https://docs.recruitee.com/reference/authentication-1) |
| Recruitee RC | El quickstart de partners requiere obtener acceso RC | No disponible aquí. Trata integraciones de evaluación/referencias; no acredita sandbox abierto de Careers Site API. Proveedor debe conceder acceso y aclarar alcance. [Quickstart](https://docs.recruitee.com/reference/quickstart) |
| LinkedIn/Easy Apply | Ayuda prohíbe software externo que automatiza actividad en su web | No permite esta automatización: LINKEDIN_MANUAL. [Ayuda](https://www.linkedin.com/help/linkedin/answer/a1341543), [acuerdo](https://www.linkedin.com/legal/user-agreement) |
| Indeed Apply | Condiciones consultadas, actualizadas 29/09/2026: prohíben automatizar Apply fuera de proveedores/herramientas oficiales | No permite esta automatización: INDEED_MANUAL. Sin autorización escrita ni integración oficial de este programa. [Condiciones](https://www.indeed.com/legal?hl=en_US) |

Una redirección requiere permiso independiente del sitio empresarial. My Greenhouse y demás destinos conservan la [revisión histórica del 20/10](AUTOAPPLY_ATS_REVIEW_2026-10-20.md); no se les atribuye una nueva comprobación ni una prohibición general del proveedor.

### Gestión personal concreta

Puedes utilizar este texto con un titular/proveedor dispuesto a ofrecer integración. **No se ha enviado**. No hace falta negociar acceso ATS para una presentación completamente manual.

> Estoy evaluando una integración personal de candidaturas con Cork Job Radar. ¿Autorizan expresamente utilizar el mecanismo oficial en su organización? Necesito dominios/endpoints permitidos, condiciones aplicables, campos/consentimientos, límites, vigencia/revocación y método de comprobar recepción. Antes de datos reales necesito un entorno o vacante de prueba expresamente autorizado, datos admitidos y procedimiento para retirar los de prueba. No necesito acceso administrativo general. ¿Quién puede documentar la concesión y facilitar una credencial adecuada?

Guardar respuesta y alcance para su revisión. No pegar claves, contraseñas, cookies o tokens en chat, perfil o logs. Aún no existe editor seguro/liberado de credenciales de envío: revisar la concesión antes de implementar almacenamiento. Poseer una clave no acredita por sí solo autorización. Si no se concede integración, continuar manualmente.

## Flujo manual mejorado

1. Revisar y aprobar una versión de CV en el control existente. Los 22 hechos no se vuelven a aprobar. Sin CV aprobado no se exporta paquete.
2. Elegir oferta con funciones IT confirmadas y preparar paquete local. No exige aprobar política automática para uso manual.
3. Descargar ZIP: CV aprobado, JSON con contactos/LinkedIn/respuestas, dudas, LEEME y nuevo **CANDIDATURA.txt** legible. Incluye versión/hash de CV, enlace oficial, preguntas opcionales pendientes y procedimiento. No se envía a páginas externas.
4. Abrir enlace en tu navegador, revisar requisitos, turno/transporte, vigencia y formulario. Copiar respuestas verificadas solo para la pregunta exacta. Bloqueos técnicos de AutoApply no sustituyen incompatibilidad con el puesto.
5. Tras presentar manualmente, registrar la declaración existente para evitar duplicados; no equivale a recepción.
6. En «Justificantes de candidaturas manuales», adjuntar EML original o PDF pasivo (máximo 5 MB), consentir conservación cifrada y revisar archivo exacto. Original, texto y cabeceras quedan DPAPI. Vista privada optativa y revisión ligada al hash por archivo.

El parser no ejecuta adjuntos/HTML ni consulta imágenes; rechaza PDFs activos y correo reenviado encapsulado. Coincidencias de destinatario/empresa/puesto/frase son orientativas: no validan DKIM, identidad del remitente ni recepción ATS. Estados `USER_SUPPLIED_NOT_AUTHENTICATED` y `USER_REVIEWED_NOT_EXTERNALLY_AUTHENTICATED`; nunca ENVIADA ni recibo ATS autenticado. Admite archivar evidencia histórica tras caducar el paquete sin volver a autorizar su uso. El borrado profesional elimina el nuevo contenido cifrado; copias anteriores tienen retención propia.

## Evidencias y límites

- Copia previa: `logs/assisted-delivery-baseline-backup.json`, ambas bases, código y tres activos DPAPI; no se restaura sobre producción.
- Diagnóstico inicial: `logs/assisted-delivery-diagnosis-baseline.json`. Informes por 459 ofertas: `data/ats-reviews/blockers-*.json`.
- GET reales: `logs/external-adapter-real-get-2026-10-21T151340+0100.json`: Keeper/GlobeTech/Recruitee 200, NETGEAR AccessBlocked; cero POST/datos personales. Ocho estados Recruitee conservados sin insertar candidaturas.
- Inicial nueva: 18 PASS (`assisted-delivery-first.xml`). Regresión afectada: **67 PASS**, cero fallos/errores/omitidas, 13 avisos, 37,77 s (`assisted-delivery-regression.xml`): migraciones, cifrado, EML/PDF de identidad ficticia, rechazos, duplicados concurrentes, conservación y UI. No sumar suites solapadas. La última completa histórica sigue siendo 399; no se ha repetido.
- Chromium real del panel, auditoría de ambas bases, CLI/doctors y copia final: `logs/assisted-delivery-*`; resultado terminado en checkpoint. El primer fallo del script Chromium se conserva, sin atribuirle éxito.

Regresión reproducible sobre bases aisladas (elegir nombres nuevos para conservar informes anteriores):

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_assisted_delivery.py tests/test_autoapply_manual_handoff.py tests/test_autoapply_vault.py tests/test_autoapply_trials_receipts.py tests/test_stored_ats_inventory.py tests/test_ultimate_stabilization.py tests/test_ui.py tests/test_human_interventions.py::test_v7_additive_migration_preserves_all_old_rows_and_live_check --basetemp=data/pytest-assisted-next --junitxml=logs/assisted-delivery-next.xml
```

Antes del primer ensayo faltan permiso y entorno, adaptador/recepción externos, vacante compatible, CV/política, respuestas y transporte. Solo entonces preparar candidatura completa y solicitar autorización expresa para **un** envío. La activación del modo A será posterior y separada, con recepción externa acreditada y política vigente. LIVE permanece bloqueado.
