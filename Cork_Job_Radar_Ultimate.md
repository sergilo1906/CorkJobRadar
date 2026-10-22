# PROMPT MAESTRO — CORK JOB RADAR ULTIMATE

## TU MISIÓN

Actúa como un equipo completo de desarrollo formado por un arquitecto de software senior, desarrollador Python, ingeniero de datos, especialista en búsqueda de empleo, ingeniero QA y diseñador de aplicaciones.

Tu objetivo es convertir **Cork Job Radar** en la mejor aplicación de búsqueda y análisis de empleo que razonablemente podamos construir con los recursos disponibles.

No quiero un prototipo, una interfaz decorativa ni un programa que solamente encuentre unas pocas ofertas. Quiero una herramienta verdaderamente útil para buscar trabajo en Cork, que descubra sistemáticamente las vacantes accesibles, las examine individualmente, compruebe su vigencia y me ayude a decidir dónde presentar mi candidatura.

**La prioridad absoluta es la exhaustividad comprobable, la calidad de los análisis y el funcionamiento real.**

No tienes un límite artificial de tiempo de desarrollo. Trabaja por fases, conserva el progreso y continúa mientras dispongas de los recursos y permisos necesarios.

---

## 1. PRIMERO: EXAMINA EL PROYECTO EXISTENTE

La aplicación ya existe en:

`C:\Proyectos\CorkJobRadar`

Antes de modificar nada:

1. Lee `PROGRESO.md`, `PROGRESS.md`, `NEXT_STEPS.md`, `README.md` y el prompt maestro original.
2. Revisa todo el código Python, configuración, conectores, estructura SQLite, pruebas y documentación.
3. Comprueba si está instalada la última actualización del analizador documental (`rules-1.2-documentary`).
4. Ejecuta el diagnóstico y la suite de pruebas existente.
5. Examina las fuentes configuradas, las ejecuciones anteriores, las tareas pendientes y los informes de cobertura.
6. Comprueba la integridad de la base de datos y realiza una copia de seguridad antes de cualquier migración.
7. Identifica funcionalidades reales, incompletas, duplicadas, incorrectas y pendientes de probar.

Como referencia, la última versión documentada tenía 29 fuentes registradas, 7 activas, 272 ofertas únicas y 61 ofertas prioritarias o pendientes de accesibilidad. Estos números son históricos: compruébalos en el proyecto y no los presentes como resultados actuales.

**PROHIBIDO:** borrar la base de datos, reiniciar el proyecto, destruir el historial, sustituir resultados reales por ejemplos o rehacer módulos que ya funcionan correctamente.

Realiza mejoras incrementales sobre la arquitectura existente.

---

## 2. MI PERFIL Y CONDICIONES LABORALES

Vivo en **Ballinlough, Cork City, Irlanda**.

No tengo coche propio. Dispongo de bicicleta y puedo utilizar transporte público.

### Trabajos de informática (IT)

Busca todas las oportunidades razonables relacionadas con:

- IT Support, Helpdesk, Service Desk y Desktop Support.
- Junior IT Technician, Technical Support y Application Support.
- Junior Software Developer, Java Developer y QA Tester.
- IT Operations, Infrastructure Support y Systems Support.
- Graduate Programmes, Internships, Apprenticeships y Trainee.
- Otros puestos tecnológicos de entrada compatibles con mi formación de DAM.

Condiciones:

- Radio geográfico equivalente a unos 60 minutos en coche desde Ballinlough.
- La distancia en coche es solamente un criterio de búsqueda: **no significa que tenga coche**.
- Comprobar posteriormente si el trayecto en transporte público o bicicleta es factible.
- No exigir lunes a viernes.
- Admitir fines de semana, diferentes turnos y horarios, indicando claramente sus condiciones.
- Priorizar puestos junior, sin experiencia o con requisitos realmente asumibles.
- No excluir automáticamente vacantes que soliciten experiencia.
- Incluir trabajos remotos desde Irlanda e híbridos compatibles.
- Salario orientativo de 30.000–40.000 € anuales, sin utilizarlo como filtro obligatorio.

### Todos los demás trabajos

Buscar especialmente:

- Production Operative y Manufacturing Operative.
- Assembly, Packaging, Cleanroom y Product Builder.
- Warehouse Operative, Picker/Packer e Inventory.
- Stock Controller, Goods In y Goods Out.
- General Operative, General Assistant y Factory Worker.
- Instalaciones, HVAC, aislamiento y mantenimiento.
- Retail, supermercados, reposición y otros trabajos generales.
- Cualquier otro empleo realista que pudiera interesarme.

Condiciones geográficas:

- Priorizar Cork City.
- Admitir localidades exteriores solamente cuando exista un desplazamiento practicable en bicicleta o **un único autobús directo sin transbordos** desde Ballinlough.
- No asumir que Little Island, Ringaskiddy o Carrigtwohill son accesibles únicamente por encontrarse cerca de Cork.
- Si no puedes verificar el transporte, marcarlo como pendiente de comprobación y conservar la oferta.

Condiciones laborales:

- Priorizar contratos permanentes.
- Preferiblemente jornada completa.
- Preferiblemente lunes a viernes.
- Horarios diurnos, fijos y estables.
- Evitar especialmente rotaciones constantes de turnos.
- Salario orientativo de 15 €/hora o superior, sin excluir automáticamente ofertas que paguen menos.

**Todas estas condiciones son criterios para evaluar y clasificar empleos, no excusas para dejar de buscar.**

---

## 3. MOTOR DE BÚSQUEDA MASIVA

Este es uno de los módulos más importantes.

Quiero que el sistema descubra la mayor cantidad posible de ofertas relevantes de fuentes públicas y accesibles.

### Fuentes que debes investigar

- Webs oficiales de contratación de empresas.
- Greenhouse.
- Lever.
- Ashby.
- SmartRecruiters.
- Otros sistemas ATS utilizados por empresas de Cork.
- JobsIreland.
- IrishJobs.
- Jobs.ie.
- Indeed, cuando el acceso automatizado esté permitido.
- Agencias de contratación.
- Empresas industriales, tecnológicas, logísticas y comerciales.
- Administraciones y empresas públicas.
- Universidades, centros de investigación y hospitales.
- Pequeñas y medianas empresas con ofertas publicadas directamente.
- Otras fuentes públicas que descubras durante la investigación.

No utilices LinkedIn como fuente principal.

### Descubrimiento automático de nuevas fuentes

No quiero depender exclusivamente de una lista fija de empresas.

Implementa un mecanismo que permita descubrir nuevas empresas, páginas de contratación y sistemas ATS relevantes.

Utiliza métodos públicos y permitidos, como:

- Directorios y páginas corporativas.
- Enlaces a páginas de empleo.
- Sitemaps.
- Feeds RSS/Atom.
- JSON-LD `JobPosting`.
- APIs públicas documentadas.
- Búsquedas web y directorios accesibles.

Una fuente descubierta debe quedar registrada y pasar por un proceso de validación antes de activarse.

### Paginación exhaustiva

No quiero que el programa se detenga tras encontrar 10, 20, 50 o 100 ofertas.

Para cada fuente accesible:

1. Identifica su sistema real de paginación.
2. Recorre todas las páginas correspondientes al alcance configurado.
3. Recupera las vacantes y sus enlaces.
4. Detecta errores, páginas repetidas y truncamientos.
5. Comprueba que no quedan páginas accesibles sin procesar.
6. Registra recuentos y evidencia de cobertura.

Nunca marques una fuente como completamente revisada si no puedes demostrarlo.

Respeta los términos de servicio, restricciones técnicas, límites de peticiones y condiciones de acceso. No eludas CAPTCHA, autenticación ni sistemas antibots.

Cuando una fuente no permita automatización, registra el problema y proporciona una alternativa permitida.

---

## 4. ANÁLISIS INDIVIDUAL EXHAUSTIVO

**Este es el segundo componente más importante.**

No quiero análisis superficiales basados en el título de una oferta.

Cada oferta recuperada dentro del alcance debe tener un análisis individual basado en su descripción completa, o una incidencia documentada si no puede recuperarse.

### Información obligatoria de cada oferta

Recupera y analiza:

1. Empresa y título original.
2. Ubicación exacta o ubicación insuficiente.
3. Dirección o modalidad presencial, híbrida o remota.
4. Fecha de publicación, cuando esté disponible.
5. Estado de vigencia comprobado.
6. Salario y complementos publicados.
7. Jornada semanal.
8. Turnos y horarios.
9. Tipo de contrato.
10. Funciones y responsabilidades.
11. Formación exigida.
12. Experiencia imprescindible.
13. Experiencia deseable.
14. Habilidades y herramientas necesarias.
15. Formación proporcionada por la empresa.
16. Idiomas exigidos.
17. Requisitos físicos cuando consten.
18. Posibilidades de crecimiento respaldadas por el anuncio.
19. Accesibilidad desde Ballinlough.
20. Compatibilidad con mi perfil.
21. Dificultades para mi candidatura.
22. Recomendación argumentada.
23. Enlace oficial de candidatura.
24. Fuente y fecha de la última comprobación.

### Explicaciones en español

La aplicación debe explicarme claramente:

- Qué trabajo haría durante una jornada normal.
- Qué responsabilidades tendría.
- Qué requisitos cumplo.
- Qué requisitos me faltan.
- Si parecen enseñarme desde cero.
- Si la empresa solicita experiencia obligatoria.
- Qué dificultades podría encontrar.
- Por qué me recomendarías presentarme o no.

No quiero textos genéricos que se repitan en todas las ofertas.

Distingue rigurosamente entre información comprobada, interpretación razonable y datos desconocidos.

**Nunca inventes salarios, turnos, responsabilidades o beneficios.**

### Análisis con inteligencia artificial

Revisa el adaptador Ollama existente.

Si hay un modelo local apropiado instalado, comprueba su funcionamiento real, precisión, velocidad y capacidad para analizar descripciones completas.

Si no hay ninguno, investiga una opción local razonable compatible con el hardware existente, pero no instales modelos enormes ni consumas recursos excesivos sin evaluar previamente la capacidad del equipo.

Puedes proponer una API externa opcional, pero nunca hacer obligatoria una suscripción de pago.

Implementa respuestas estructuradas, validación de campos, trazabilidad de evidencias y reintentos controlados.

Si la IA falla, la oferta debe conservarse y quedar marcada como pendiente de análisis profundo.

No presentes el análisis por reglas como si fuera una interpretación semántica completa.

---

## 5. GARANTÍA DE ANÁLISIS COMPLETO

La búsqueda y el análisis deben funcionar como procesos separados.

Estados mínimos:

- Descubierta.
- Descripción recuperada.
- Pendiente de análisis.
- Análisis básico completado.
- Análisis profundo completado.
- Pendiente de verificación.
- Error recuperable.
- Fuente inaccesible.
- Fuera de alcance.
- Cerrada o retirada.

Cuando la búsqueda finalice, el sistema debe continuar analizando las ofertas pendientes.

Si se recuperan 800 descripciones completas dentro del alcance, deben existir 800 análisis individualizados o incidencias explícitas.

No se permite eliminar ofertas del procesamiento porque tengan baja puntuación.

Implementa análisis reanudable y persistente. Si cierro la aplicación o Windows se reinicia, debe poder continuar sin repetir innecesariamente trabajo.

---

## 6. TRANSPORTE DESDE BALLINLOUGH

Quiero que el programa compruebe los desplazamientos reales, no solamente la distancia geográfica.

Investiga fuentes autorizadas y fiables para:

- Rutas de autobuses.
- Transbordos.
- Horarios de ida y vuelta.
- Desplazamientos en bicicleta.
- Tiempo a pie hasta las paradas.
- Compatibilidad con el horario del empleo.

Para trabajos generales, una localidad exterior a Cork City solamente se considerará accesible cuando exista un trayecto en bicicleta practicable o un autobús directo sin transbordos.

Para IT, conservar las ofertas dentro del radio geográfico establecido, pero indicar si puedo llegar realmente sin coche.

**Comprobar la vuelta del trabajo es tan importante como comprobar la ida**, especialmente por las noches o fines de semana.

Si no hay una API o fuente adecuada, desarrolla una comprobación manual asistida y muestra claramente que el trayecto no está verificado.

No inventes líneas ni tiempos.

---

## 7. INTERFAZ DE USUARIO PROFESIONAL

Aprovecha la aplicación Streamlit existente. No la sustituyas sin una razón técnica demostrable.

Quiero una interfaz moderna, rápida y sencilla en español.

Debe permitir:

- Iniciar, detener y reanudar búsquedas.
- Consultar fuentes y su estado.
- Ver progreso real por fuente y por fase.
- Mostrar todas las ofertas descubiertas.
- Filtrar por sector, ubicación, salario, contrato y horario.
- Filtrar por accesibilidad en bicicleta o autobús.
- Ordenar por compatibilidad.
- Diferenciar ofertas nuevas, repetidas, cerradas y modificadas.
- Abrir fichas detalladas.
- Consultar la descripción original y el análisis en español.
- Abrir el enlace oficial para solicitar empleo.
- Guardar favoritos.
- Marcar ofertas descartadas.
- Registrar candidaturas y respuestas recibidas.
- Añadir ofertas manualmente mediante URL.
- Exportar resultados.
- Revisar errores y limitaciones.

### Panel principal

Quiero ver métricas reales:

- Fuentes registradas.
- Fuentes accesibles revisadas.
- Fuentes pendientes.
- Vacantes encontradas.
- Ofertas únicas.
- Ofertas abiertas confirmadas.
- Ofertas con vigencia desconocida.
- Ofertas completamente analizadas.
- Ofertas pendientes de análisis.
- Ofertas nuevas desde la última búsqueda.
- Ofertas recomendadas.
- Cobertura real de las fuentes configuradas.

No uses porcentajes engañosos. El 100 % de las fuentes comprobadas no equivale al 100 % de los trabajos existentes en Cork.

---

## 8. DETECCIÓN DE OFERTAS OMITIDAS

Quiero una función específica para encontrar y corregir errores de cobertura.

Cuando introduzca manualmente una oferta que el programa no haya encontrado:

1. Identifica la empresa y la web.
2. Comprueba si la fuente estaba registrada.
3. Comprueba si la vacante estaba publicada durante la búsqueda anterior.
4. Analiza si falló la paginación, extracción, clasificación, deduplicación o descubrimiento.
5. Registra el motivo conocido o deja explícito que no pudo determinarse.
6. Crea una prueba de regresión cuando se identifique un fallo reproducible.
7. Corrige el conector correspondiente si es posible.
8. Comprueba que la corrección no rompe otras fuentes.

El objetivo es mejorar progresivamente la cobertura y no repetir siempre los mismos errores.

---

## 9. BASE DE DATOS Y ACTUALIZACIONES

Mantén SQLite y los datos actuales.

Asegura:

- Deduplicación entre portales y webs oficiales.
- Conservación de todos los enlaces de procedencia.
- Fechas de primera y última detección.
- Historial de cambios.
- Comparación entre búsquedas.
- Versionado de análisis.
- Detección de nuevas ofertas.
- Detección prudente de vacantes retiradas.
- Reintentos de errores.
- Procesos reanudables.
- Migraciones seguras.
- Copias de seguridad.
- Recuperación tras interrupciones.

No consideres cerrada una oferta simplemente porque falle una petición o desaparezca temporalmente de los resultados.

Evita duplicaciones de empresas y publicaciones, sin fusionar vacantes distintas por compartir título.

---

## 10. EXPORTACIONES COMPLETAS

Perfecciona la exportación Excel existente.

Quiero un archivo con:

- Todas las ofertas.
- Recomendadas.
- IT.
- Producción.
- Almacenes.
- Técnicos.
- Otros sectores.
- Ofertas nuevas.
- Análisis pendientes.
- Transporte pendiente.
- Candidaturas.
- Fuentes revisadas.
- Errores y limitaciones.
- Historial de búsquedas.

Cada fila debe conservar enlace, empresa, descripción, salario conocido, horario, estado, compatibilidad y datos del análisis.

Los filtros del Excel tienen que funcionar y el archivo debe abrirse correctamente en Microsoft Excel.

Comprueba que las columnas no contienen información inventada ni fórmulas inseguras procedentes de anuncios.

---

## 11. PUNTUACIÓN PERSONALIZADA

Mejora el sistema actual para dar una puntuación de 0 a 100 a cada oferta relevante.

Valora:

- Compatibilidad con experiencia.
- Requisitos reales.
- Posibilidad de aprender.
- Salario publicado.
- Estabilidad.
- Horario.
- Transporte.
- Probabilidades razonadas de encajar en el perfil.
- Progresión profesional.

Utiliza ponderaciones distintas para IT y trabajos generales.

En IT no penalices automáticamente los fines de semana.

En trabajos generales da más importancia a horarios estables de lunes a viernes y desplazamientos sencillos.

La puntuación debe mostrar sus razones y tener un indicador independiente de confianza.

Si faltan datos importantes, no fabriques una puntuación aparentemente precisa.

Conserva todas las ofertas aunque obtengan baja puntuación.

---

## 12. CALIDAD, SEGURIDAD Y RENDIMIENTO

Utiliza una arquitectura sencilla y mantenible compatible con Windows.

Mantén preferentemente:

- Python.
- SQLite.
- Streamlit.
- Playwright únicamente donde sea apropiado y esté permitido.
- APIs públicas documentadas.
- pytest.
- openpyxl.
- Análisis local opcional mediante Ollama.

No introduzcas Docker, Kubernetes ni servicios cloud innecesarios.

Implementa:

- Reintentos con backoff.
- Límites de consultas por dominio.
- Control de concurrencia.
- Gestión de bloqueos.
- Logs útiles.
- Control de errores de red.
- Validación de URLs y protección SSRF, incluida la resolución DNS.
- Gestión segura de secretos.
- Pruebas de integridad de datos.
- Comprobación de uso de recursos.
- Ejecución sin congelar la interfaz.
- Reanudación después de fallos.

No automatices candidaturas, envío de CV ni contacto con empresas sin autorización explícita.

---

## 13. PRUEBAS REALES OBLIGATORIAS

No consideres implementada una característica solo porque hayas escrito su código.

Para cada mejora:

1. Revisa las pruebas existentes.
2. Añade pruebas específicas.
3. Ejecuta pruebas unitarias.
4. Ejecuta pruebas de integración.
5. Prueba casos límite.
6. Realiza pruebas reales cuando las fuentes permitan consultas.
7. Corrige los errores.
8. Repite las pruebas hasta obtener un resultado verificable.
9. Documenta lo que no has podido probar.

Prueba especialmente:

- Paginación hasta el final.
- Conectores bloqueados.
- Fuentes sin vacantes.
- Descripciones incompletas.
- Salarios ausentes.
- Duplicados.
- Fechas desconocidas.
- Pérdida de conexión.
- Reinicios.
- Cambios de estructura HTML.
- IT fuera de Cork City.
- IT con horarios de fin de semana.
- Trabajos generales con autobús directo.
- Trabajos generales que exigen transbordo.
- Rutas sin datos verificables.
- Miles de ofertas.
- Análisis interrumpidos.
- Exportaciones extensas.

No ejecutes tests destructivos sobre la base de producción.

---

## 14. PLAN DE DESARROLLO OBLIGATORIO

Trabaja siguiendo este orden:

**FASE 1 — Diagnóstico y estabilización**

Verificar la instalación actual, integrar correctamente las mejoras existentes, arreglar errores reales y asegurar la integridad de los datos.

**FASE 2 — Ampliación de fuentes**

Investigar y activar nuevas fuentes permitidas, priorizando las de mayor cobertura para Cork. Implementar conectores y paginación verificables.

**FASE 3 — Descubrimiento automático**

Añadir detección de nuevas empresas y páginas de empleo. Mejorar la investigación de vacantes omitidas.

**FASE 4 — Análisis individual profundo**

Validar el motor semántico y procesar todas las ofertas pendientes con evidencia textual.

**FASE 5 — Transporte**

Implementar comprobaciones de ida/vuelta desde Ballinlough mediante datos fiables.

**FASE 6 — Experiencia de usuario**

Mejorar interfaz, filtros, búsqueda, fichas, favoritos, candidaturas y exportaciones.

**FASE 7 — Optimización**

Reducir consultas innecesarias, mejorar velocidad, persistencia y eficiencia sin sacrificar cobertura.

**FASE 8 — Auditoría completa**

Ejecutar las pruebas finales, revisar la cobertura, documentar las limitaciones y preparar una versión estable para Windows.

Completa primero una funcionalidad útil y verificable antes de pasar a funciones decorativas.

---

## 15. CRITERIOS DE ACEPTACIÓN

No declares la aplicación terminada si no puedes demostrar que:

1. Arranca en mi ordenador Windows.
2. Conserva mis datos anteriores.
3. Los conectores declarados como operativos han sido probados.
4. La paginación de las fuentes soportadas funciona.
5. Cada oferta recuperada tiene una descripción o una incidencia.
6. Cada oferta dentro de alcance tiene análisis o un pendiente explícito.
7. El análisis diferencia hechos de interpretaciones.
8. Los enlaces son reales y tienen estado de verificación.
9. La accesibilidad no presupone disponer de coche.
10. Las búsquedas pueden interrumpirse y reanudarse.
11. Los resultados se mantienen entre sesiones.
12. Los Excel exportados son válidos.
13. El historial permite detectar nuevas vacantes.
14. Los fallos de cobertura quedan documentados.
15. La suite de pruebas pertinente se ejecuta y sus resultados quedan registrados.

La aplicación puede alcanzar una versión estable aunque existan restricciones externas pendientes, pero esas restricciones deben mostrarse claramente y no ocultarse.

---

## 16. AUTONOMÍA Y CONTINUIDAD

Tienes permiso para examinar y modificar los archivos del proyecto, ejecutar pruebas y utilizar herramientas de desarrollo dentro de la carpeta de Cork Job Radar.

No modifiques proyectos ajenos.

Antes de acciones destructivas, gastos, instalaciones a nivel del sistema o cambios externos sensibles, pide autorización.

No te detengas simplemente después de escribir un plan.

No termines una sesión con una lista de recomendaciones si puedes implementar y probar una mejora real.

Actualiza constantemente:

- `PROGRESO.md`
- `NEXT_STEPS.md`
- `docs/TEST_REPORT.md`
- `docs/SOURCES.md`
- `docs/COVERAGE.md`

Cuando finalice una sesión, registra exactamente qué funciona, qué has probado y qué falta.

Si necesitas continuar en una nueva sesión, deja suficiente información para retomar el trabajo sin repetir tareas.

## INSTRUCCIÓN FINAL

**COMIENZA AHORA.**

Inspecciona completamente el proyecto actual, ejecuta las pruebas de referencia, detecta la primera mejora pendiente de mayor impacto e impleméntala.

Después continúa con las siguientes fases, comprobando siempre los resultados reales.

No quiero una aplicación que parezca completa. Quiero una aplicación cuya funcionalidad, cobertura y análisis puedan demostrarse con evidencia.

El objetivo final es encontrar sistemáticamente la mayor cantidad posible de oportunidades laborales accesibles para mí, analizar profundamente todas las vacantes recuperadas que correspondan a mi búsqueda y ayudarme a conseguir el mejor trabajo posible en Cork.