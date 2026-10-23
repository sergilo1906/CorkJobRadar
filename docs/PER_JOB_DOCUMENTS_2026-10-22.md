# Documentos por oferta — implementación y validación Windows

**Flujo documental local implementado y probado; documentos pendientes del usuario. LIVE OFF.** Se continúa la rama validada PR1/2/3 y se incorpora íntegra la PR5 (`0785bf8`) mediante avance directo en una rama nueva, `work/per-job-documents-20261022`. No se modifica `main` ni se mezclan las bases del worktree aislado. No se declara terminado AutoApply externo.

## Cambios implementados

- SQLite v13 aditiva con copia previa automática, integridad y FK comprobadas. Expediente profesional estructurado derivado exclusivamente de hechos vigentes, con campos y posiciones literales, responsabilidades asociadas a empleo, fechas, formación, nivel básico/end-user y campos desconocidos explícitos. No se importan proyectos o tareas adicionales de los originales como hechos aprobados.
- Selección por capacidades y necesidades de cada anuncio, además de identidad exacta de tecnologías. Se conservan el expediente completo, los IDs seleccionados y omitidos, citas y niveles obligatorio/deseable/ambiguo. La evidencia relacionada no concede cumplimiento ni equivalencia académica. Un conflicto cronológico impide aprobar el paquete.
- Tres familias: soporte IT, desarrollo junior y QA. Distintas selecciones y prioridades, resúmenes nuevos pendientes de revisión, bullets originales ordenados dentro de su empleo, capacidades clasificadas, formación y fechas conservadas. No se atribuye experiencia QA, idiomas nativos, certificaciones, logros o proyectos sin evidencia.
- PDF/DOCX comparten presentación y contenido. Letra fija legible, cabecera, subtítulo objetivo, contacto/LinkedIn, perfil, capacidades, empleo/periodo y formación. Una página por defecto; dos solo mediante configuración explícita. No se reduce la fuente para forzar el ajuste.
- Carta de presentación independiente: puesto/empresa exactos, hasta tres evidencias seleccionadas y relaciones con funciones publicadas. Revisión de redacción antes de autorizar su exportación. No equivale a una recomendación firmada por un empleador.
- Biblioteca cifrada de referencias: bytes íntegros del PDF original, hash, página fuente, tipo, fecha publicada, importación, revisión y permiso de uso. Admite escaneados sin texto y campos de firma, sin afirmar validación criptográfica. Carriage es confirmación de empleo; SIE y Gas Reusense son recomendaciones de distinto alcance.
- Versiones por vacante y paquete elegido por el usuario. CV solo por defecto; carta y cada referencia requieren selección/consentimiento y aceptación comprobada por el usuario en el destino. Revisión de contenido y diseño/formato, caducidad, vínculos a perfil/oferta/formulario y revocación. Aprobar un CV por oferta no aprueba el CV general ni una política automática.
- Cambiar versión, formato, carta, referencias/permisos o esquema reinicia las casillas de revisión. El backend también rechaza cambios concurrentes de formulario y permisos. La descarga en memoria desaparece al cambiar la selección, y se muestra qué archivos contiene cada paquete autorizado.
- Integración con el ZIP manual existente: documentos exactos, contacto/LinkedIn, respuestas verificadas, preguntas pendientes, instrucciones y permisos. Revalida versiones, hashes, hechos, esquema, duplicados y selección inmediatamente antes de exportar. No incorpora transporte externo.
- Interfaz existente ampliada en **Mis candidaturas → oferta → CV**. Biblioteca en **Perfil y configuración → CV definitivo → Biblioteca de referencias y originales**. No se reconstruyen las seis pantallas.

## Originales: límite importante

El PDF autorizado contiene el CV antiguo y tres anexos. Se conserva completo y sin alterar, compartido por las tres fichas de referencia. La imagen de cada página es una vista derivada, nunca un nuevo «original firmado».

**No se exporta ese paquete completo al seleccionar una sola referencia.** Para adjuntar una referencia individual, aportar su PDF original independiente, revisarlo y autorizarlo. Así se evita incluir un CV antiguo y otras cartas no seleccionadas. No se recortan ni reconstruyen firmas para esconder esta limitación. Las tres fichas importadas permanecen pendientes, sin permiso de compartir.

La inspección privada identifica diferencias de redacción entre cartas y perfil, además de información adicional no aprobada. Se registran para revisión, sin cambiar los22 hechos. Las fechas antiguas de DAM del PDF fuente no sustituyen el estado académico confirmado por el usuario.

## Evidencias y situación actual

- Respaldo inicial completo: `logs/per-job-start-backup.json`; hashes, ZIP, ambas SQLite/FK y60 activos cifrados comprobados. No restaurado sobre producción.
- **Suite completa final:712 PASS**,0 fallos/errores/omitidas,26 avisos de deprecación,526,66s (`logs/per-job-release.xml`). Previa completa710 PASS, posterior dirigida53 PASS y dirigida124 PASS conservadas; se solapan y no se suman. La inicial completa704 PASS/1 fallo detectó un test que esperaba la navegación antigua; se actualizó manteniendo las barreras de consentimiento. Los demás fallos iniciales y sus correcciones permanecen registrados, incluidos un selector de AppTest y un fichero de prueba inexistente que ejecutó cero casos.
- Generación con perfil real: `scripts/validate_per_job_real_profile.py`, documentos para tres ofertas almacenadas y pruebas reales de PDF/DOCX con LibreOffice. **Borradores actuales10/11/12 por oferta; CV4 general intacto y sin aprobar.** Capturas100%/150% privadas dentro de la bóveda local; ninguna captura/CV se publica. Las variantes no certifican elegibilidad: QA conserva requisitos lingüísticos y el puesto graduate conserva dudas académicas. Tres CV y sus Word: una página, todos los hechos elegidos/contactos conservados; cartas202/176/194 palabras, tres bloques de evidencia y redacción nueva pendiente de revisión.
- Primer intento de comprobación Office retenido por su PDF derivado con `OpenAction`. Se corrigió el verificador: lee el texto del render de visualización y mantiene la validación estricta del PDF que se exportaría. No se relajó el validador de candidaturas. Log fallido conservado.
- CV4 permanece pendiente y tiene una retención explícita de calidad. Los borradores por oferta y sus textos nuevos no se aprueban por el agente. Aprobaciones históricas y versiones cifradas intactas. Los proyectos, empleos adicionales y tareas del PDF fuente sin aprobación previa no se incorporan por suposición; el expediente permite identificar esos campos pendientes.

Navegador sobre la instalación real: `logs/per-job-production-ready.json`,1440/390, sin desbordamiento, consentimientos desmarcados, referencias pendientes y tablas críticas intactas. Prueba aislada con Chromium: selección→contenido→diseño→cambio de carta que reinicia consentimiento→aprobación ficticia→ZIP exacto→revocación. Registro manual accesible con CV por oferta aunque no haya CV general aprobado. No se utiliza identidad real en esos ensayos de aprobación.

Se corrigió que un requisito bajo un encabezado preferible quedara ambiguo: conserva DESEABLE, y si la frase contradice ese encabezado se retiene POR_ACLARAR. Los encabezados adicionales para composición conservan citas/offsets y no convierten formación ofrecida en requisito. Relacionar capacidades no sustituye una comprobación semántica/humana completa.

Conservación final: `logs/per-job-final-preservation.json`,15 tablas históricas y60 activos anteriores intactos,7 tablas de transporte idénticas,22 hechos vigentes,4 CV generales sin cambios,3 referencias pendientes,12 versiones por oferta y0 paquetes nuevos aprobados. SQLite/FK correctas; cero contactos en58 archivos/SQLite revisados. Copia final `logs/per-job-final-backup.json`; verificación `logs/per-job-final-verification.json`. Evidencia visual adicional47 archivos protegidos con DPAPI, con descifrado/ZIP comprobados; solo metadatos en `logs/per-job-visual-review.json`.

Streamlit necesitó reinicio controlado para cargar la migración y, posteriormente, todos los módulos actualizados. El supervisor anterior salió antes de arrancar el nuevo; misma base y próxima búsqueda22:25:41, intervalo6h. `logs/per-job-final-runtime-recovery.json`. Comprobar PID+stamp actual; no reutilizar números de sesiones anteriores. Un primer verificador arrancó antes del supervisor y falló correctamente; repetido tras comprobar salud/propietario. Sin servicios, inicio de Windows ni reinicio físico.

## Uso en la aplicación

1. **Ofertas de empleo → elegir vacante IT → Preparar candidatura → CV**. En Mis candidaturas también puede aparecer en **Requieren intervención** mientras haya datos pendientes.
2. Comparar selección y expediente; revisar requisitos, ubicación/horario y preguntas. Generar documentos si la versión anterior quedó retenida.
3. Descargar/revisar PDF o DOCX, incluido todo el contenido y las nuevas redacciones. Elegir carta y originales opcionales únicamente si el destino los admite.
4. El usuario marca sus revisiones y aprueba el paquete exacto. Preparar ZIP y descargarlo no envía nada. Completar personalmente el formulario oficial.
5. Tras una solicitud efectuada realmente, **Solicitud → Registrar candidatura presentada por mí**, y conservar el justificante. El sistema bloquea duplicados y no confunde esa declaración con recepción externa autenticada.

## Dependencias humanas y externas

El usuario revisa el contenido, diseño, formato, documentos opcionales y permiso de cada paquete. Los campos profesionales o anexos nuevos necesitan revisión; los22 hechos vigentes no requieren reaprobarse. Una descarga explícita es una copia privada legible bajo control del usuario; revocar en la aplicación no borra copias ya descargadas.

Para el modo automático siguen pendientes un canal permitido, ensayo externo autorizado con recepción comprobada y activación separada de política. LinkedIn/Indeed continúan manuales. No se envían candidaturas, no se resuelven CAPTCHA reales ni se piden permisos API para utilizar los paquetes manuales.

## Continuidad y publicación verificadas

El commit funcional `b683a28` se publicó en `work/per-job-documents-20261022`, conservando main. La auditoría del índice comprobó336 archivos sin contactos reales ni patrones de secretos detectados. Bases, originales, CV, capturas y evidencias privadas permanecen fuera de Git.

El ciclo automático21 terminó el22/10 a las22:25:55, con122 observaciones de las tres fuentes habilitadas y67 tareas completadas. Añadió dos anuncios de marketing en Austin: son616 registros/3.028 análisis, no dos oportunidades IT compatibles nuevas. La comprobación posterior conserva los614 IDs anteriores, todo su contenido y análisis históricos,17 tablas estáticas idénticas,76 activos cifrados y las7 tablas de transporte. Fechas de observación y cinco metadatos de origen se actualizaron como parte de la búsqueda real. Evidencia: `logs/per-job-scheduled-cycle-verification.json`.

El supervisor existente permanece RUNNING/WAITING, cada6 horas, próxima búsqueda23/10 a las04:26:29 Europe/Dublin. Copia adicional posterior al ciclo: `logs/per-job-post-cycle-backup.json`. No se repiten pruebas funcionales tras cambios exclusivamente documentales. Los712 PASS acreditan el código publicado, sin atribuirlos a GitHub CI ni a un envío externo.
