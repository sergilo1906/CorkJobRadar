# Diagnóstico de partida — Ultimate

Revisión del 19/10/2026, después de leer íntegramente el nuevo encargo, el original, documentación, configuración, módulos y pruebas existentes.

- La suite de referencia ha pasado **63 pruebas**, sin fallos ni errores, en 103,08 s. Evidencia: `logs/ultimate-baseline.xml`.
- SQLite v1 íntegro y sin errores de claves externas. Se conservan 272 anuncios, 273 procedencias, 482 snapshots, 326 versiones de análisis y 7 ejecuciones. Son datos almacenados, no un rastreo nuevo.
- Copia consistente de SQLite y archivo de código/configuración previos en `data/backups/`, con integridad de la copia comprobada.
- No está instalado `rules-1.2-documentary`: el código usa `rules-1.1`. Tampoco hay Ollama en PATH. No se atribuye una instalación inexistente.
- 29 fuentes registradas, 7 activas; quedaron 179 tareas de una verificación cancelada y 67 reintentables de otra. Se preservan sus estados.
- Hardware: i5-11400H, 16 GB RAM, RTX 3050 4 GB. En la revisión solo había unos 2,5 GB de RAM libre y 21,8 GB de disco libre. No se instalarán modelos grandes ni componentes del sistema.

## Hallazgos que justifican cambios incrementales

1. La interfaz abre una conexión/consulta por oferta para recuperar análisis, y repite ese recorrido. La auditoría también consulta por fila. Esto penaliza búsquedas de miles de ofertas.
2. Falta una observación inmutable del hash y la novedad de cada oferta por ejecución; el historial no permite comparar con precisión las búsquedas nuevas.
3. La validación DNS se repite al conectar sin fijar el resultado: queda una ventana de rebinding.
4. El analizador no extrae responsabilidades y repite texto genérico. No distingue requisitos obligatorios/deseables ni negaciones como «no experience required».
5. La investigación de omisiones solo abre una incidencia genérica, sin diagnóstico basado en el historial.
6. Los conectores oficiales existentes funcionan; se ampliarán sin sustituirlos. JobsIreland y HSE son candidatos de mayor cobertura pendientes de revisar condiciones, estructura y paginación.
7. `docs/finalize_report.py` contiene cifras y descripciones históricas fijas: no se utilizará para atribuir pruebas o capacidades nuevas sin actualizarlo.

Primera mejora: observaciones de búsqueda y consultas en lote, con migración respaldada y pruebas de conservación; después ampliación de fuentes.
