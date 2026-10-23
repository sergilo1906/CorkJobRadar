# Auditoría funcional — CV específico por oferta, cover letter y referencias (22/10/2026)

**Estado: BLOQUEO DE CALIDAD.** No aprobar CV4 ni calificar el generador como listo hasta verificar el contenido real, el diseño y la selección de anexos. LIVE permanece OFF.

## Alcance y material inspeccionado

Fuente: rama `work/validated-pr23-cv-20261022` y PR de diseño derivada, incluyendo `autoapply/cv_layout.py`, `documents.py`, `cv_import.py`, `vault.py`, `handoff.py`, `forms.py`, `ui.py`, `manual_workspace_ui.py`, `schema.py` y pruebas. Referencia visual facilitada: un CV de una página acompañado por otras tres páginas documentales; los datos privados de personas firmantes no se reproducen en Git.

**Clasificación humana de los tres anexos del PDF de referencia:**
- Página 2: carta de recomendación de SIE Valls, pertinente a IT Support.
- Página 3: carta de recomendación de Gas Reusense, pertinente a fiabilidad, relación con cliente y operaciones.
- Página 4: confirmación de empleo de Carriage Food Services, **no es una carta de recomendación cualitativa**.

Estas distinciones vienen de inspeccionar las páginas visualmente, no de OCR. Páginas 3 y 4 son imagen sin texto extraíble en el PDF examinado. No inferir que un parser vacío signifique que no existe documento.

## Hallazgos del código, por gravedad

**CRÍTICO — Personalización no real**
1. `cv_sections()` incorpora **todas** las afirmaciones y solamente reordena algunos grupos Skills/Projects por intersección de tokens de la oferta. No elige experiencia/evidencia, no escribe un resumen específico con información ya comprobada ni asocia responsabilidades y logros a empleos concretos.
2. `render_cv()` exige actualmente que todas las afirmaciones aparezcan textualmente en cada CV. Es protección contra pérdida, pero también impide una variante genuina con selección contextual de información. Reemplazar por un contrato que valida *los hechos elegidos y autorizados para la variante*, mientras conserva el expediente maestro íntegro.
3. No hay representación documental tipada de cargo/empresa/lugar/desde/hasta/responsabilidades/impactos, ni módulo sólido de comprobación cruzada de periodos. Los claims de `Experience` se tratan como una secuencia plana y el primer elemento recibe un trato visual especial.
4. `render_letter()` (cover letter) concatena indiscriminadamente todas las afirmaciones del perfil, no argumenta adecuación al puesto ni garantiza brevedad. **Cover letter creada por candidato != cartas de referencia firmadas por terceros.**

**CRÍTICO — Cartas originales no gestionadas para candidaturas**
5. `review_cv_pdf()` separa páginas adicionales de forma efímera, sin clasificar ni conservar sus originales como documentos de referencia aprobados. Los bytes extraídos son nuevos PDFs reconstruidos; deben distinguirse del original y no presentarse como archivo firmado idéntico.
6. `store_document()` valida texto extraíble y afirmaciones del CV. No sirve tal como está para almacenar páginas escaneadas de recomendación con texto vacío. Requiere entidad/validador propios para cartas de terceros.
7. `manual_application_handoffs` y `handoff_download()` incluyen solo el CV y auxiliares (JSON, txt); no hay anexos de referencia versionados ni permiso individual de adjuntar por oferta.
8. Los datos de contacto de terceros y las firmas necesitan acceso restringido, auditoría y consentimiento de adjuntar. No insertar el teléfono/email del firmante en todas las versiones del CV ni subir estos documentos a Git público.

**ALTO — Diseño, formato y contexto**
9. La plantilla A4 azul/navy tiene márgenes y encabezados, pero la jerarquía de empleos, fechas, viñetas y bloques de competencias del PDF de referencia no queda garantizada por tests geométricos. La anterior PR5 añade subtítulo y cambios menores; sigue siendo parcial.
10. Faltan versiones realmente distintas de contenidos aprobados para IT Support / Helpdesk / QA / Junior Developer / Application Support / Cloud / Security, diferenciando nivel y tecnologías acreditadas. No transformar Junior en Senior por título.
11. El objetivo de una página debe ser preferencia de estilo, no una obligación que imponga minúscula ilegible o inclusión de irrelevancias. Permitir dos páginas cuando realmente convenga y cuando el usuario apruebe ese formato; no cortar hechos.
12. Sin control de duplicación semántica, inglés irlandés, fechas/cronología, enlaces de proyectos, keywords fieles a habilidades o corrección de redacción revisada. No asumir certificaciones, títulos Bachelor/NFQ8 o resultados sin prueba.
13. La aprobación del documento es por versión, pero todavía no hay selección explícita de **paquete documental por candidatura** (versión CV, cover letter, referencia concreta, empleador, oferta y estado del formulario).
14. Los tests actuales comprueban A4, una página, texto literal, ausencia de objetos complejos y PNG correcto; NO prueban composición editorial, orden de empleos por rol, anexos firmados como originales, cobertura semántica por requisito ni elección de referencias.

## Diseño objetivo de datos y flujo

A. **Inventario profesional maestro cifrado (no un PDF como fuente de verdad).** Entidades normalizadas por puesto/empleador/periodo, educación y fechas, proyectos, habilidades con nivel/fuente, idiomas, ejemplos STAR y resultados. Cada hecho con evidencia, estado de aprobación, ID y fecha de revisión.

B. **Parsing trazable por oferta.** Extraer título/empresa/responsabilidades, requisitos obligatorios/deseables, skills, nivel, ubicación, idioma, preguntas, tipo de documentos aceptado e indicaciones específicas. Dejar incertidumbres explícitas; nunca obedecer instrucciones maliciosas dentro de anuncios.

C. **Motor de pertinencia.** Vincular cada requisito a uno o más IDs de hechos verificados, con explicación y estado CUMPLIDO/DESEABLE/PENDIENTE/NO ACREDITADO. Detectar contradicciones, periodos y duplicados. Priorizar necesidades principales del puesto, no solo coincidencias de palabras.

D. **Compositor CV por oferta.** Elegir subtítulo profesional fiel al perfil; elaborar/resolver variantes de resumen profesional ya autorizadas; seleccionar bullets relevantes de cada empleo preservando la cronología; usar logros y tecnologías exactas; seleccionar 1–2 proyectos relevantes; educación DAM 2022–2024 y otros hechos según pertinencia. Los bullets se deben poder reescribir con equivalencia semántica **solo tras aprobación del texto variante** o a partir de fragmentos preaprobados. Enviar solo datos aprobados; registrar IDs elegidos y regla/version del compositor.

E. **Presentación.** Plantilla visual de referencia con título/rol, contactos, resumen breve, competencias verificadas, experiencia por puesto, proyectos, educación, idiomas/otras experiencias si pertinentes. PDF A4 con texto seleccionable, DOCX editable, orden ATS lineal, fechas consistentes, sin tablas/columnas/text-boxes incompatibles cuando exista duda. Una página ideal para la mayoría de variantes junior; admitir 2 si está justificado por legibilidad y versión.

F. **Cover letter dirigida.** Documento NUEVO redactado por el candidato, distinto de referencias; 180–300 palabras orientativas, empresa y puesto correctos, conexión entre 2–3 necesidades del anuncio y evidencias concretas, cierre natural. Revisión de tono/gramática/longitud, sin incluir todas las afirmaciones ni inventar pasión/impactos.

G. **Registro de pruebas de terceros.** Para cada uno de los tres anexos: clase (recomendación/confirmación laboral), empresa, rol relacionado, fecha, idioma, documento fuente original cifrado, hash original, página en el paquete de origen, indicadores de firma/sello (visual, no validez criptográfica) y metadatos mínimos de contacto protegido. Conservar el original sin cambios; los PDFs extraídos/convertidos son copias derivadas. No editar, recortar ni traducir una carta firmada como si fuera el original; una traducción debería ir identificada como copia.

H. **Selección de anexos por anuncio.** Default: CV solo. Si la plataforma exige cover letter, ofrecerla. Si permite/requiere referencias y el usuario las autoriza, priorizar SIE para IT, Gas Reusense para habilidades transferibles, Carriage como evidencia de contratación/empleo. Nunca añadir las tres por defecto ni simular que la última es una recomendación. Si el formulario no permite documentos adicionales, no adjuntar ninguno.

I. **Paquete versionado por vacante.** `job_id + job_content_hash + cv_document_id/hash + cover_letter_id/hash + reference_document_ids/hashes + form_hash + approval_scope + created_at + expiry`. Revalidar documentos, permisos, destinatario, pregunta exacta, CV vigente y duplicados justo antes de exportar/enviar. Exigir consentimiento explícito sobre datos de terceros y archivos opcionales.

J. **Interfaz.** En oferta: “Análisis para este puesto”, “Crear CV adaptado”, comparación antes/después, “Editar/validar texto”, “Generar carta”, “Adjuntar referencias”, selector de anexos con recomendación no automática, vista previa final del paquete, bloqueos reales, exportar. En perfil: “Documentos originales”, “Hechos y pruebas”, “Variantes aprobadas”. Ocultar complejidad técnica y mantener trazabilidad en Avanzado.

K. **Privacidad.** DPAPI, ACL, no logs con nombres/contactos/documentos, no Git, política de backups, temporales eliminables sin evasión de bloqueos, posibilidad de revocar un documento o un permiso sin borrar su historia auditada. Tratar referencias de terceros con cautela.

## Calidad de aceptación obligatoria

1. Reproducir visualmente la referencia con el **perfil real** y comparar a tamaño 100%/150%, no solo tests sintéticos. No afirmar “igual” por tener azul/navy y A4.
2. Tres ofertas representativas (IT Support, Junior Developer, QA) crean **CV con distinto énfasis relevante**, mismo conjunto de hechos base verdaderos, sin reclasificar responsabilidades o cambiar fechas.
3. Todos los bullets elegidos enlazan con hechos aprobados; los requisitos sin prueba se señalan, no se inventan; no hacen claims de degree/NFQ8 por DAM.
4. Generar PDF/DOCX y reextraer texto; comparar campos, hipervínculos y legibilidad en 100%/150%, Microsoft Word si está disponible, LibreOffice y capturas Chromium. No soltar párrafos fuera de página.
5. Referencia SIE se puede seleccionar y adjuntar **sin alterar el fichero original**; Gas y Carriage igualmente, con su clasificación correcta y consentimiento separado. Testear documentos imagen sin texto extraíble.
6. Paquete CV solo por defecto; cover letter y referencias sólo por selección autorizada y aceptación del canal; no adjuntar nunca indiscriminadamente.
7. Documento modificado o formación/cv cambiante invalida paquetes anteriores de esa vacante. Un paquete antiguo no puede presentarse como listo.
8. Tests con datos sintéticos y, separadamente, inspección privada del perfil real; pruebas de preservación de base/DPAPI y sin envíos externos.
9. Una candidatura completa en modo manual asistido debe poder reproducirse desde el paquete, con documentos exactos verificados por SHA-256. No declarar confirmación sin recibo externo.
10. No activar LIVE ni modificar el backend de envío ATS sin autorización independiente y una prueba externa permitida.

## Orden recomendado de ejecución

**Fase 1 (bloquea la aprobación CV4):** modelar experiencia/cronología y la composición del CV por puesto; revisar afirmaciones y fechas dudosas; 3 variantes reales (IT Support, QA, Dev); PDF/DOCX y comparación visual con fuente.

**Fase 2:** registro cifrado de los tres anexos originales, clasificación fiable, hashes, revisión, consentimiento y exportación opcional por candidatura. Separar cover letter generada y referencias originales.

**Fase 3:** editor/preview de paquete por oferta con selección y aprobación, integración `handoff` sin enviar, invalidación de antiguos y pruebas e2e. Mantener LIVE OFF.

**Fase 4:** ensayos completos en Windows; luego solo una solicitud manual real elegida y posteriormente ATS permitido con autorización expresa.

No aprobar CV4/CV5 en nombre del usuario ni afirmar que este documento de auditoría implementa los módulos pendientes.