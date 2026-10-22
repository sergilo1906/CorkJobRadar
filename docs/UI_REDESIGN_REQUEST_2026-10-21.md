# CORK JOB RADAR — REDISEÑO INTEGRAL UI/UX Y REORGANIZACIÓN DE LA INTERFAZ

Actúa como desarrollador senior de interfaces, diseñador UX/UI, arquitecto de aplicaciones Streamlit e ingeniero QA.

Proyecto: `C:\Proyectos\CorkJobRadar`

## OBJETIVO PRINCIPAL

Quiero que rediseñes y corrijas TODA la interfaz de Cork Job Radar.

Actualmente considero que la experiencia de usuario, la distribución de los elementos, el formato, la organización de las secciones y la lógica de qué se muestra y qué se oculta están mal resueltas.

No quiero un cambio superficial de colores.

Quiero una aplicación profesional, intuitiva, moderna, coherente, fácil de utilizar y visualmente bien organizada.

**DEBES IMPLEMENTAR LOS CAMBIOS REALES EN EL CÓDIGO. NO TE LIMITES A PROPONER UN DISEÑO O A CREAR DOCUMENTACIÓN.**

## FASE 1 — AUDITORÍA COMPLETA DE LA INTERFAZ

Antes de modificar nada:

1. Lee PROGRESO.md, NEXT_STEPS.md y el checkpoint vigente.
2. Identifica todos los componentes, páginas, pestañas y formularios de Streamlit.
3. Comprueba qué procesos están activos antes de iniciar otros.
4. Abre la aplicación existente con Chromium.
5. Recorre todas las pantallas y subpantallas.
6. Inspecciona los estados visibles, desplegables, formularios, tablas y acciones.
7. Realiza capturas de la interfaz actual como referencia.
8. Comprueba si existe información duplicada, contradictoria, mal posicionada o innecesaria.
9. Identifica elementos que aparecen cuando deberían permanecer ocultos.
10. Identifica funciones importantes que están escondidas en secciones poco intuitivas.

No elimines funcionalidades antes de identificar dónde deben quedar accesibles.

## FASE 2 — NUEVA ARQUITECTURA DE NAVEGACIÓN

Quiero reorganizar el programa en seis áreas principales:

### 1. INICIO

Debe ser el panel principal al abrir la aplicación.

Mostrar solamente lo más importante:

- Estado de la búsqueda continua.
- Última búsqueda y próxima ejecución.
- Número de ofertas totales.
- Ofertas IT potencialmente interesantes.
- Candidaturas preparadas.
- Candidaturas enviadas y confirmadas.
- Intervenciones pendientes.
- Estado del CV.
- Estado de AutoApply.
- Errores importantes que requieren actuación.

Incorporar una sección llamada "Qué necesitas hacer ahora".

Debe mostrar acciones reales pendientes y permitir acceder directamente a ellas.

No mostrar logs técnicos, identificadores internos, hashes, información de depuración ni configuraciones avanzadas en el inicio.

No confundir ofertas guardadas con ofertas compatibles.

### 2. OFERTAS DE EMPLEO

Debe convertirse en el centro principal de consulta de vacantes.

Incluir:

- Búsqueda por empresa y puesto.
- Filtros claros.
- Ubicación y distancia.
- Categoría IT.
- Experiencia mínima solicitada.
- Salario publicado.
- Modalidad presencial, híbrida o remota.
- Vigencia.
- Compatibilidad.
- Estado de candidatura.

Mis criterios principales son:

- Empleos IT o relacionados con DAM.
- Radio de 50 km desde Ballinlough.
- Hasta 3 años de experiencia mínima requerida.
- No excluir por requisitos meramente deseables.
- Permitir oportunidades razonables con pequeñas diferencias de experiencia o conocimientos.
- No inventar distancias ni requisitos.

La lista debe ser fácil de leer.

Cada oferta debe presentar como máximo la información necesaria para decidir si merece abrirla.

Al seleccionar una oferta, mostrar una ficha detallada con:

- Empresa y puesto.
- Ubicación.
- Fecha de publicación o verificación, si existe.
- Salario, si está publicado.
- Responsabilidades.
- Requisitos obligatorios.
- Requisitos deseables.
- Requisitos pendientes de aclarar.
- Comparación con mi experiencia.
- Transporte.
- Enlace original.
- Acciones para preparar candidatura.

No mostrar párrafos enormes sin estructura.

No mostrar el mismo contenido repetido en diferentes bloques.

Los resultados deben cargarse eficientemente mediante paginación o virtualización cuando corresponda.

### 3. MIS CANDIDATURAS

Separar claramente:

- Pendientes de preparar.
- Preparadas.
- Requieren intervención.
- Enviadas declaradas manualmente.
- Enviadas con confirmación externa.
- Estado incierto.
- Rechazadas o cerradas, cuando exista evidencia.

No mostrar herramientas técnicas de integración como si fueran candidaturas normales.

Cada candidatura debe tener una ficha clara con estado, empresa, puesto, fecha y acciones disponibles.

Quiero botones intuitivos:

- Preparar candidatura.
- Descargar CV.
- Copiar respuestas.
- Abrir oferta.
- Registrar solicitud.
- Adjuntar justificante.
- Continuar intervención, cuando proceda.

Ocultar botones que no correspondan al estado actual.

Cuando una acción esté bloqueada por un requisito, mostrar una explicación breve y la forma de resolverlo.

### 4. AUTOAPPLY

Crear una sección diferenciada para las candidaturas automáticas.

Mostrar claramente si LIVE está OFF o activado.

Separar visualmente:

- Candidaturas manuales.
- Candidaturas asistidas.
- Automatización externa permitida.
- Plataformas sin automatización autorizada.

La pantalla principal de AutoApply debe ser fácil de entender para alguien que no conoce conceptos técnicos.

Ocultar los controles avanzados de ATS, tokens, hashes, migraciones y diagnósticos detrás de una sección de herramientas avanzadas.

No mostrar botones de enviar si no existe un canal autorizado y realmente operativo.

No sugerir que una candidatura se ha enviado cuando solamente se ha preparado.

No permitir que cambios visuales anulen bloqueos del backend.

### 5. ACTIVIDAD Y NOTIFICACIONES

Agrupar:

- Estado del supervisor.
- Búsquedas en curso.
- Próxima ejecución.
- Historial de búsquedas.
- Fuentes con errores.
- Tareas pendientes.
- CAPTCHA/MFA pendientes.
- Alertas importantes.

Permitir iniciar, pausar, reanudar, detener y solicitar búsqueda inmediata.

Los controles disponibles deben depender del estado real del proceso.

No mostrar simultáneamente botones contradictorios.

Por ejemplo:

RUNNING:
- Mostrar PAUSAR y DETENER.
- Ocultar INICIAR y REANUDAR.

PAUSED:
- Mostrar REANUDAR y DETENER.
- Ocultar PAUSAR.

STOPPED:
- Mostrar INICIAR.
- Ocultar PAUSAR y REANUDAR.

STOPPING:
- Mostrar estado de detención en curso.
- Deshabilitar acciones incompatibles.
- Evitar órdenes duplicadas.

Usar el estado real del backend, no una variable visual desconectada.

Mantener los logs técnicos en una zona avanzada.

### 6. PERFIL Y CONFIGURACIÓN

Agrupar toda la configuración del usuario:

- Datos personales.
- Experiencia.
- Formación.
- Idiomas.
- LinkedIn.
- CV aprobados.
- Preferencias IT.
- Radio de búsqueda.
- Transporte.
- Frecuencia de búsqueda.
- Política de candidaturas.
- Privacidad y eliminación de datos.

Mostrar datos personales sensibles solamente cuando sea necesario y de forma protegida.

No mostrar información privada en todas las pantallas.

No repetir formularios de perfil repartidos por múltiples pestañas.

La configuración avanzada del sistema debe estar separada de las preferencias personales.

## FASE 3 — CORREGIR QUÉ SE MUESTRA Y QUÉ SE OCULTA

Esta fase es fundamental.

Construye una matriz de visibilidad basada en:

- Pantalla.
- Estado real del sistema.
- Estado del CV.
- Estado de la política.
- Disponibilidad del canal.
- Existencia de candidaturas.
- Intervenciones pendientes.
- Permisos.
- Datos disponibles.
- Errores.

Implementa las reglas de forma centralizada, evitando múltiples condiciones contradictorias entre páginas.

Ejemplos:

- Si no hay intervenciones pendientes, no mostrar tablas vacías enormes.
- Si el CV no está aprobado, mostrar una acción clara para aprobarlo; no mostrar controles de envío como disponibles.
- Si AutoApply está OFF, mostrar su estado y únicamente acciones realmente permitidas.
- Si no hay salario publicado, mostrar "No publicado", no una cifra inventada.
- Si no hay ubicación confirmada, mostrar "Ubicación pendiente", no una distancia falsa.
- Si el puesto no tiene requisitos extraídos, indicar que faltan datos; no mostrar una lista vacía como si no exigiera requisitos.
- Si un usuario no necesita ver un ajuste técnico, ocultarlo tras "Avanzado".
- Si una candidatura ya fue registrada, no presentar otra vez el botón de solicitar como si fuera nueva.
- Si hay errores, mostrarlos cerca de la acción afectada.
- Si una sección no tiene datos útiles, mostrar un estado vacío comprensible con una acción adecuada.
- Si una operación está trabajando, mostrar progreso y evitar dobles clics.

NO ocultes advertencias críticas ni bloqueos de seguridad.

## FASE 4 — REDISEÑO VISUAL COMPLETO

Quiero una apariencia de aplicación profesional, moderna y coherente.

Estilo:

- Diseño limpio.
- Espaciados consistentes.
- Tipografía legible.
- Jerarquía visual clara.
- Tarjetas de información bien proporcionadas.
- Tablas legibles.
- Botones consistentes.
- Iconografía discreta.
- Paleta de colores limitada.
- Bordes y radios consistentes.
- Buen contraste.
- Estados visuales diferenciados.
- Diseño adaptable a diferentes tamaños de pantalla.

Evitar:

- Demasiadas cajas dentro de otras cajas.
- Decenas de elementos desplegables innecesarios.
- Títulos enormes.
- Texto técnico sin explicación.
- Botones desalineados.
- Columnas demasiado estrechas.
- Espacios vacíos excesivos.
- Tablas que desbordan.
- Información repetida.
- Colores que no representan un estado real.
- Páginas excesivamente largas sin organización.
- Scroll horizontal innecesario.
- Elementos que cambian de sitio entre recargas.

Diseña un sistema visual compartido:

- Componentes de navegación.
- Botones.
- Formularios.
- Tarjetas.
- Indicadores de estado.
- Mensajes de error.
- Mensajes de éxito.
- Estados vacíos.
- Tablas y filtros.
- Diálogos de confirmación.

Utiliza componentes nativos de Streamlit cuando sean adecuados.

Centraliza el CSS que sea imprescindible y evita selectores frágiles dependientes de clases internas de Streamlit.

No introduzcas librerías de interfaz pesadas sin justificación.

## FASE 5 — EXPERIENCIA DE USUARIO REAL

Piensa en el programa desde la perspectiva de una persona que solamente quiere conseguir empleo IT.

El flujo principal debe ser:

ABRIR PROGRAMA
→ VER ESTADO
→ CONSULTAR OFERTAS
→ ELEGIR UNA
→ REVISAR REQUISITOS
→ PREPARAR CANDIDATURA
→ PRESENTARLA POR EL CANAL PERMITIDO
→ REGISTRAR RESULTADO.

No obligues a entrar en cuatro pestañas distintas para completar una operación sencilla.

Evita confirmaciones innecesarias, pero conserva las autorizaciones obligatorias.

Prioriza la información práctica frente a los detalles de implementación.

Implementa navegación consistente y regreso sencillo desde una ficha al listado manteniendo filtros y posición cuando sea posible.

## FASE 6 — RENDIMIENTO Y ESTABILIDAD

La interfaz ya trabaja con cientos de ofertas y seguirá creciendo.

- Evita consultas SQLite individuales por cada fila.
- Reutiliza consultas en lote.
- No recalcules análisis pesados por cada rerun.
- No hagas consultas externas solo por abrir una pantalla.
- Utiliza correctamente el estado de sesión de Streamlit.
- Evita reruns globales innecesarios.
- Comprueba que la actualización del supervisor no reinicia formularios en edición.
- Mantén separados los trabajadores y la interfaz.
- Evita crear procesos duplicados.
- No pongas en riesgo la integridad de SQLite.

## FASE 7 — PRUEBAS VISUALES OBLIGATORIAS

No consideres terminado el rediseño solamente porque pytest pase.

Abre la interfaz mediante Chromium y comprueba visualmente TODAS las secciones.

Prueba diferentes resoluciones:

- 1920 × 1080.
- 1440 × 900.
- 1280 × 720.
- 768 × 1024.
- 390 × 844.

Verifica:

- Navegación.
- Espaciados.
- Tablas.
- Formularios.
- Botones.
- Filtros.
- Datos vacíos.
- Datos extensos.
- Textos largos.
- Estados de error.
- Estados RUNNING, PAUSED y STOPPED.
- CV pendiente y aprobado en bases de prueba.
- AutoApply OFF.
- CAPTCHA/intervención simulada.
- Candidaturas preparadas y registradas en datos de prueba.

Revisa las capturas reales, detecta defectos visuales y corrígelos.

No te limites a guardar capturas automáticamente sin analizarlas.

Incluye comprobaciones de accesibilidad: contraste, navegación por teclado, etiquetas y controles identificables.

Prueba que no aparecen datos personales indebidamente.

## FASE 8 — CONSERVACIÓN Y SEGURIDAD

No reconstruyas todo el proyecto desde cero.

Mantén:

- SQLite.
- Los datos existentes.
- Los 22 hechos profesionales aprobados.
- Los CV y su cifrado.
- El supervisor local.
- Los conectores existentes.
- Las funcionalidades de AutoApply.
- La protección contra duplicados.
- Los permisos y autorizaciones.
- LIVE OFF.
- Los checkpoints.

No modifiques otros proyectos ni instales servicios.

Realiza una copia verificable antes de cambios estructurales.

Si hay migraciones, deben ser incrementales y probadas.

No apruebes mi CV, no actives políticas y no envíes candidaturas en mi nombre.

## FASE 9 — CRITERIOS DE FINALIZACIÓN

Solamente considera completo el rediseño cuando:

1. Todas las funciones existentes estén accesibles desde una estructura coherente.
2. No existan bloques duplicados innecesarios.
3. Los componentes se muestren u oculten según el estado real.
4. Los botones ejecuten la acción que anuncian.
5. No haya contradicciones entre información, estados y contadores.
6. Las pantallas funcionen con datos reales.
7. La interfaz sea legible y adaptable.
8. Las pruebas funcionales pasen.
9. La revisión visual en Chromium no detecte defectos importantes.
10. La base de datos y las autorizaciones se conserven.
11. LIVE continúe OFF.
12. Los cambios queden documentados.

Si descubres funcionalidades que no pueden conservarse o errores que dependen de acciones externas, documéntalos explícitamente.

## EJECUCIÓN

No quiero solamente un plan de diseño.

Quiero que:

1. Audites la interfaz actual.
2. Diseñes la nueva estructura.
3. Modifiques los archivos reales.
4. Reorganices componentes y navegación.
5. Corrijas la visibilidad de todos los estados.
6. Mejores el formato completo.
7. Pruebes con Chromium.
8. Inspecciones las capturas.
9. Corrijas problemas visuales.
10. Ejecutes pruebas de regresión.
11. Actualices PROGRESO.md, NEXT_STEPS.md y SESSION_CHECKPOINT.md.

Trabaja de forma autónoma y continúa hasta completar todo lo que sea posible en esta sesión.

Mantén checkpoints frecuentes para recuperar el trabajo si se agotan los créditos.

**PRIORIDAD ABSOLUTA: conseguir que Cork Job Radar parezca y se comporte como una aplicación profesional y sea sencilla de usar, sin perder ninguna funcionalidad existente.**