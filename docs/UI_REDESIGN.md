# Rediseño de la interfaz — cierre local22/10/2026

Última actualización: DAM terminado/examen aprobado por confirmación explícita del usuario;22 hechos vigentes/23 versiones, CV2 pendiente. Revisar en **Perfil y configuración → CV definitivo**. No se aprueba automáticamente ni se envía. La versión previa se conserva revocada. Diez pruebas dirigidas y Chromium de producción en `logs/ui-redesign-dam-completed-delivery.json`. Último ajuste de tarjetas/vacíos en `logs/ui-redesign-final-adjustments.json`; copia final verificada en los informes indicados al final. Las cifras del comienzo del rediseño que siguen son históricas.

Estado: interfaz implementada y verificada localmente. LIVE OFF. El agente no ha aprobado CV, política ni candidatura del usuario; los consentimientos de pruebas se realizaron únicamente con identidades ficticias en bases aisladas.

La copia previa verificable está en `logs/ui-redesign-baseline-backup.json`. Base actual al inicio: 612 ofertas, 22 hechos profesionales y un CV pendiente, sin intentos externos. SQLite v12; este rediseño no requiere migración.

La auditoría Chromium de las siete pantallas antiguas identificó 21 tablas y 36 desplegables. Evidencia: `logs/ui-redesign-baseline-audit-ready.json`, capturas privadas enmascaradas en `data/ui-redesign/before`. La primera captura se tomó antes de completar la carga; la evidencia `ready` es la auditoría completa.

## Dónde está cada función

| Área | Uso normal | Herramientas adicionales |
|---|---|---|
| Inicio | Estado, últimas/próximas búsquedas, contadores diferenciados, acciones pendientes | Sin logs ni datos personales |
| Ofertas de empleo | Búsqueda, filtros, tarjetas paginadas y ficha con requisitos/transporte | Vista de tabla con filtros anteriores; análisis, revisiones, versiones, citas y procedencias por oferta |
| Mis candidaturas | Estados diferenciados; ficha con pasos CV, requisitos, transporte, respuestas, solicitud y justificantes | Evidencias cifradas y declaraciones manuales, sin afirmar recepción |
| AutoApply | LIVE OFF, modos manual/asistido/automatización, intervenciones cuando existen | Formularios, ensayo, matriz ATS, bloqueos, contraste, simulación y auditoría histórica |
| Actividad y notificaciones | Iniciar/pausar/reanudar/detener, próximas búsquedas y avisos | Historial, fuentes/importación/descubrimiento, cobertura, exportación, tareas y diagnósticos |
| Perfil y configuración | CV, datos/experiencia/idiomas/LinkedIn, ubicación, frecuencia, política y privacidad | Perfil YAML, propuestas de competencias y herramientas GTFS/transporte |

Solo se ejecuta la pantalla elegida. Las actualizaciones periódicas se limitan a fragmentos de estado: no se recalcula todo ni se reinician formularios desde el temporizador. La lista usa consultas en lote; la evaluación completa de una vacante se realiza al abrir su ficha. Abrir pantallas no consulta plataformas externas ni inicia envíos.

## Visibilidad

Las reglas principales están en `corkjobradar/ui/visibility.py`. RUNNING muestra Pausar/Detener, PAUSED Reanudar/Detener, STOPPED Iniciar y STOPPING ninguna orden incompatible. Buscar ahora se bloquea con trabajo activo. Los callbacks vuelven a consultar el control persistente. Los bloqueos de CV/permisos/duplicados/recibos siguen en los servicios originales.

Una oferta guardada no es una oferta compatible. El listado prioritario usa funciones IT y pistas de localidad; estas pistas no acreditan kilómetros ni trayectos. Todas las ofertas siguen accesibles. Las distancias solo se muestran si existe centro verificado. Salario desconocido: No publicado. Requisitos no extraídos: datos pendientes, no ausencia de requisitos. Las condiciones deseables se mantienen separadas.

La ficha privada solo se revela mediante una acción explícita en Perfil; contactos/respuestas se muestran cuando el usuario abre ese paso de una candidatura. Los screenshots de pruebas reales enmascaran texto privado. Ningún justificante local se presenta como confirmación externa.

## Matriz central de visibilidad

| Situación | Presentación y acciones |
|---|---|
| RUNNING / PAUSED / STOPPED | Pausar+Detener / Reanudar+Detener / Iniciar; relectura persistente al actuar |
| STOPPING o búsqueda activa | Mensaje de detención; sin órdenes incompatibles; Buscar ahora bloqueado durante trabajo |
| CV pendiente | Acción explícita para revisar versión; preparación retenida, sin controles de envío |
| CV aprobado | Descarga habilitada, sin pedir aprobar de nuevo el mismo documento |
| Sin política/canal externo operativo | LIVE OFF; preparación/manuales y diagnóstico avanzado; ningún botón de envío |
| Sin candidaturas o intervenciones | Estado vacío y acción útil; ninguna tabla de intervenciones vacía |
| Preparada | Paquete local revalidado al abrir, descarga y declaración explícita del usuario |
| Declarada / incierta / confirmada / cerrada | Sin nueva solicitud; seguimiento y justificantes según evidencia; recepción externa solo con prueba LIVE |
| Entrevista/rechazo posteriores | Se actualiza etapa conservando historial y recuento del envío declarado/confirmado |
| Datos privados | Solo en CV, revelado explícito de perfil o paso Respuestas de una candidatura |
| Salario/ubicación/requisitos desconocidos | No publicado / distancia pendiente / datos por extraer; ninguna inferencia de aptitud |
| Errores | Junto a la acción afectada y avisos; detalles internos solo en Avanzado |

## Verificación cerrada

Completa **568 PASS**, 22 avisos/457,19 s. Posteriores **52 PASS**/61,58 s y **24 PASS**/40,90 s, solapadas. No sumar. Compilación/dependencias correctas; LIVE exit2. Informes XML/logs `ui-redesign-*` conservados, incluidos fallos iniciales de mapa de análisis, aislamiento, sincronización, teclado del helper y sesión de fixture sin propietario. Corregidos y comprobados; no son recepciones externas.

`ui-redesign-delivery-visual.json`: seis pantallas × cinco resoluciones (1920×1080,1440×900,1280×720,768×1024,390×844) y16 subpantallas. Sin excepciones/desbordamientos ni fallos de contraste de las muestras visibles. Revisión humana de las capturas para espaciado, jerarquía, tablas, formularios, campos privados enmascarados y vacíos. Se corrigieron navegación móvil, estados de CV y títulos excesivos. El texto completo de los títulos queda en ficha/tooltip. No se afirma certificación integral WCAG: se comprobaron contraste, foco, teclado y etiquetas de los controles funcionales. Referencias oficiales consultadas: [contraste de texto](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) y [elementos gráficos](https://www.w3.org/WAI/WCAG22/understanding/non-text-contrast.html). La primera medición clasificaba erróneamente como texto el icono nativo lateral (18 muestras de3,71:1); se corrigió el umbral gráfico3:1, sin rebajar el texto4,5:1. El selector móvil etiquetado evita depender de ese icono de Streamlit.

`ui-redesign-assisted-browser-proof.json`: en una base sintética se aprobó CV por versión, copió el email exacto al portapapeles, conservó formulario sin guardar, descargó1ZIP, declaró1solicitud y guardó1EML cifrado. El panel muestra1declaración y0recepciones externas. Estados RUNNING/PAUSED/STOPPED/STOPPING controlados mediante backend de prueba, sin supervisor de producción. La recuperación real de procesos se volvió a comprobar en los tests de runtime de la completa.

`ui-redesign-additional-states-final.json`: teclado real, vacíos/error/textos largos, CAPTCHA propio detenido antes dePOST, verificación de prueba y1recibo local,0externos. No desafíos ni formularios de empresas. `ui-redesign-final-adjustments.json` comprueba la tarjeta con título largo en dos líneas y la acción directa de listado vacío; los datos de estas pruebas no se insertaron en principal.

`ui-redesign-delivery-audit.json`:612ofertas/22hechos conservados, CV pendiente,0intentos/paquetes reales, ambas bases íntegras/FK0 y0contactos en los52archivos/bases examinados. Transporte tiene idéntico esquema y filas en7tablas; el hash físico operativo puede diferir del snapshot SQLite. Copia final e integridad/hashes/ZIP en `ui-redesign-final-backup.json` y `ui-redesign-backup-verification.json`.

Incidencia de aislamiento conservada en `logs/ui-redesign-test-isolation-incident.json`: una referencia importada antes de aplicar el mock del lanzador permitió que el test UI reanudara la ejecución histórica 1. No hubo envío ni datos personales: cambió observación/verificación de una oferta, metadatos de una fuente y finalización de aquella búsqueda. Contenido, hechos, CV y controles preservados. Corregidos imports locales y añadido bloqueo de `subprocess.Popen` en pruebas AppTest, que solo deben invocar lanzadores simulados. No se restauró ninguna base ni se ocultaron los valores anteriores; se conservan en la copia previa.
