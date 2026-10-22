# AutoApply exclusivamente IT

Decisión vigente: `CorkJobRadar_AutoApply_IT_Only.md`. Sustituye cualquier autorización general previa de AutoApply; la búsqueda general y el historial SQLite se conservan. Motor `autoapply-2.0-it-only-simulation`. LIVE OFF.

## Barreras implementadas

- La política acepta exactamente `categories: [IT]` y `authorization_scope: IT_ONLY_CONFIRMED_FUNCTIONS_V1`. Las políticas antiguas sin este alcance, generales o de motor anterior no pueden reanudarse; se conserva su registro y se exige nueva autorización.
- `autoapply/it_scope.py` examina funciones literales de la descripción íntegra. Registra versión, familia tecnológica, cita y posición. Empresa, puntuación, etiquetas del modelo y habilidades deseables no confirman una función IT. Se excluyen tareas de empresa, beneficios y requisitos como prueba de funciones.
- Funciones informáticas reconocidas: soporte de equipos/Windows/Microsoft 365, desarrollo, pruebas de software, sistemas/redes/cloud y ciberseguridad. Puestos no tecnológicos reconocidos: BLOCK. Texto insuficiente, Technical Support sin funciones identificadas o funciones mixtas: HOLD. La clasificación es conservadora por reglas, no comprensión semántica exhaustiva; las formas de redacción no reconocidas requieren revisión y no obtienen permiso.
- Se comprueba IT al evaluar, reservar desde la oferta persistida, generar CV/carta adaptados, preparar/reintentar y efectuar el control prefinal. Un ALLOW falsificado o una copia del anuncio proporcionada por el llamador no anulan la oferta real de SQLite.
- Se mantienen las barreras de requisitos obligatorios, experiencia, autorización laboral, vigencia, duplicados, ficha/CV aprobados, cuotas, dominios y versión del adaptador. Los requisitos deseables no pasan a ser obligatorios. Los horarios IT se autorizan expresamente y pueden incluir turnos y fines de semana.
- Presencial e híbrido exigen ruta vigente de ida/vuelta sin coche desde Ballinlough, ligada al anuncio y al turno exacto. No se admiten excepciones de política que omitan esta evidencia. La referencia de 60 minutos en coche no demuestra accesibilidad real. El verificador actual de bus exige servicio directo: no hay evaluación completa de transbordos.
- El panel de candidaturas muestra IT por defecto. La casilla de consulta general permite ver otros registros; no modifica permisos ni elimina ofertas. CLI: `autoapply preview --include-other` para consulta; la simulación completa recorre todas las ofertas, sin detenerse por cupos o buenos resultados.

## CV y datos aprobados

El usuario ha identificado `Downloads/CV_Sergi_Lopez_IT_Support_.pdf` como versión actual. Lectura real de cuatro páginas: CV en la primera y tres anexos separados. SHA256 del original: `3f69b4609aa04ababf3a0bc06a0f31d57eb591a1c8b3144aaa24b9faca7bfbe1`. El archivo original no se modifica. No se copian datos personales a este documento ni a logs.

El usuario aprobó expresamente los hechos presentados y confirmó contactos, derecho a trabajar y disponibilidad. Importación del 20/10/2026 10:52: 22 datos/afirmaciones activos (9 datos y 13 afirmaciones), cifrados con DPAPI y procedencia/consentimiento cifrados; evidencia `logs/approved-cv-facts-import.json`. No se aprueban otros contenidos del CV por su mera presencia. DAM consta en curso, pendiente MP13; conocimiento básico no se convierte en experiencia profesional ni formación en certificación. El permiso B no acredita disponer de coche. Los hechos de vigencia personal necesitarán actualización si cambian.

Comprobados descifrado exacto, procedencia, ausencia de contactos en texto plano en SQLite/WAL, CV preparado en memoria con todas las afirmaciones, control de aprobación documental y conservación de los controles/política. No se ha registrado aún una versión final del CV como revisada; cero anexos autorizados y cero intentos/envíos. Copia previa de importación: `data/backups/before-approved-cv-facts-2026-10-20T105040+0100/`. Ningún archivo de Downloads modificado.

Regresión de bóveda e importación tras guardar los datos: `logs/it-only-approved-facts.xml`, **13 superadas** (5,42 s). El CV generado con esos hechos produce una página PDF; el documento no adquiere aprobación por generarse. La auditoría de historial conserva todos los IDs y registros originales también después de añadir la ficha.

La importación PDF de la interfaz reconstruye la primera página sin anotaciones activas, muestra su texto y ofrece los anexos como descargas independientes. No aprueba hechos ni guarda documentos al leer. El backend rechaza CV PDF de varias páginas incluso tras una aprobación de documento. Los anexos nunca se seleccionan automáticamente como CV. La ficha/cada afirmación y la versión final del CV necesitan revisión explícita; los documentos aprobados se cifran con DPAPI. LinkedIn admite únicamente una URL de perfil confirmada por el usuario; no se accede automáticamente a LinkedIn.

## Evidencias

- Copia previa consistente: `data/backups/before-it-only-2026-10-19T213521+0100/`, manifiesto `logs/it-only-backup.json`; no restaurada sobre producción.
- Reglas/política/pipeline/seguridad/resoluciones/prefinal: `logs/it-only-core.xml`, **72 pruebas superadas**.
- Separación de CV, rechazo de PDF activo/malformado, aprobaciones, LinkedIn y bloqueo de preparación general: `logs/it-only-cv-fixed.xml`, **9 pruebas superadas**. El primer ensayo conserva dos errores de infraestructura de pytest por un identificador de caso de más de 10 MB que excedía el límite de variables de Windows; corregido usando IDs breves. No eran envíos ni un ensayo con datos personales.
- Regresión completa: `logs/it-only-full.xml`, **254 superadas**, cero fallos/errores/omitidas, 14 avisos, 262,03 s. Chromium real comprueba IT por defecto y DESACTIVADO sin enviar formularios (`logs/autoapply-ui-browser.json`). Las suites se solapan; no sumar sus recuentos.
- Simulación completa de datos persistentes: 459 procesadas, 459 BLOCK por falta de política, cero preparaciones/envíos/errores (`logs/it-only-production-simulation.log`). Estado: 39 ofertas con funciones IT reconocidas, 25 no IT y 395 ambiguas/no confirmadas, incluidas las fuera de alcance. Estos recuentos no acreditan elegibilidad ni cobertura total.
- Integridad/FK e historial inmutable correctos; todos los IDs de ofertas/planes originales conservados, 383 planes reevaluados con motivos nuevos (`logs/it-only-production-state.json`). La primera comparación trataba los planes como inmutables y se corrigió el auditor para distinguir actualización de borrado; no se restauraron ni retocaron datos para forzar el resultado. `pip check` y doctor AutoApply correctos.

## Límites pendientes

No hay adaptador de envío real liberado, permiso para enviar a ATS ni ensayo real autorizado. El modo A sigue siendo el objetivo: una futura política válida permitirá envíos sin aprobación individual; esta fase solo prepara y prueba simulación. No se declara cobertura total de Cork ni análisis semántico perfecto. Resolver hechos profesionales, evidencias de cada oferta, rutas y permisos de plataforma antes de considerar un ensayo real separado.
