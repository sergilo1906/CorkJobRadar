# Metodología de cobertura

El denominador del mercado total de Cork es desconocido. Nunca se calcula un porcentaje de «todas las ofertas de Cork». Se auditan únicamente las consultas explícitas de las fuentes activadas.

El registro de fuentes distingue vías API públicas documentadas, HTML público revisado, importación manual y revisión pendiente. Una URL localizada, HTTP 200 o primera página correcta no acreditan un rastreo completo.

## Recorrido y conservación

Greenhouse y Ashby documentan una respuesta con todos los puestos del tablero. Greenhouse se contrasta con `meta.total` si está presente. Lever recorre skip/limit hasta página vacía, sin asumir que una página corta es el final. SmartRecruiters conserva la consulta `country=ie`, pagina offset/limit, contrasta `totalFound` y descarga las descripciones separadas de los listados. HTML requiere evidencia explícita de paginación, enlaces configurados y ofertas reconocibles; una página vacía desconocida es un error. El anuncio HTML individual de AbbVie cubre únicamente ese anuncio.

Se guardan primero las publicaciones, identidades, snapshots y tareas. Luego se clasifica el alcance. Los anuncios fuera de alcance siguen visibles y no se cuentan como analizados exhaustivamente. Las tarjetas malformadas se preservan como ERROR con su contenido original; no invalidan el guardado de las demás, pero impiden declarar completo el parser de esa fuente.

Los cursores y tareas se persisten incrementalmente. Reanudar reutiliza las páginas/tareas ya guardadas siempre que el protocolo permita continuar por cursor. Los endpoints de respuesta única pueden requerir releer el listado; el guardado es idempotente. Los fallos transitorios quedan reintentables; un bloqueo suspende las siguientes descargas del mismo origen. No existe límite de ofertas buenas, salario, antigüedad, sector ni puntuación en el descubrimiento.

La deduplicación exige identidad de origen o URL oficial canónica y mismo empleador. Dos títulos iguales no se fusionan. Los slugs de SmartRecruiters solo se normalizan para comparar identidades: el enlace original publicado se conserva para navegación. Las fusiones registran alias e historial completo en `DEDUP_MERGE`; las procedencias no se pierden.

## Alcance personal

IT: Cork y radio geográfico de unos 60 minutos en coche desde Ballinlough, pendiente de evidencia donde no se conoce. No presupone coche ni transporte accesible. NO IT: Cork City o evidencia de bicicleta/autobús directo con cero transbordos. Remoto elegible en Irlanda se incluye; remoto restringido a otros países se archiva. Ubicaciones ambiguas quedan pendientes, sin presentarlas como comprobadas. La clasificación de ubicación es una regla conservadora, no un geocodificador completo ni un cálculo real del radio.

Los registros de transporte son comprobaciones manuales con evidencia, origen, destino, fecha, ida y vuelta. No se afirman líneas ni tiempos reales calculados por el sistema. Falta integración con un proveedor autorizado de transporte/rutas.

## Reconciliación y estados

Por ejecución: publicaciones observadas = procedencias únicas observadas; puestos únicos = IDs maestros distintos; duplicados = publicaciones menos puestos únicos. Los puestos objetivo o pendientes se reparten de forma exclusiva en completos, básicos/parciales, pendientes o errores. Los archivados quedan aparte. La auditoría falla si no cuadran esas categorías.

Los recuentos de `audit` describen el **estado actual de los registros observados en esa ejecución**. No son una reconstrucción inmutable del análisis en el momento histórico; los snapshots originales y eventos sí se conservan. La exportación identifica fecha de generación y ejecución de auditoría y contiene todos los registros locales.

`COMPLETA_PARA_FUENTES_ACCESIBLES` significa únicamente que se completaron las consultas activadas de esa ejecución y sus tareas recuperables. No significa mercado completo ni análisis profundo completo. Los análisis de reglas permanecen `ANALISIS_BASICO/PARCIAL_POR_DATOS`, aunque se hayan procesado todos los textos íntegros. Las fuentes desactivadas/no implementadas aparecen en el informe de no cubiertas.

`OPEN_CONFIRMED` requiere formulario visible con campos de candidatura; nunca se envía. `OPEN_LIKELY` indica anuncio visible sin confirmar solicitud. `CLOSED_CONFIRMED` exige cierre explícito o plazo publicado vencido. `UNLISTED` exige dos listados completos satisfactorios consecutivos sin esa publicación y ninguna procedencia todavía visible. Errores, CAPTCHA y 403/404 no acreditan cierre. Bolsas de talento se conservan con señal explícita de que no demuestran una vacante concreta.

## Límites técnicos conocidos

- HTML genérico cubre JSON-LD y microdatos schema.org, enlaces/siguiente configurables. No interpreta cualquier portal ni implementa Playwright, RSS/Atom, sitemaps o cursores JavaScript.
- No hay motor geográfico/rutas autorizado conectado. Una comprobación de barrio no acredita acceso a una parada.
- Sin motor semántico profundo validado en vivo: resumen básico, requisitos complejos e inferencias requieren revisión humana.
- La investigación de omisiones abre una incidencia y conserva el anuncio; el diagnóstico causal definitivo y la incorporación de un nuevo parser requieren revisión técnica.
- Se detectan totales discordantes, páginas repetidas y límites. Una variación de recuento superior al 50% frente al último listado completo genera `SOURCE_COUNT_ANOMALY`; requiere revisar si cambió la consulta antes de interpretar la diferencia.
- La validación SSRF comprueba DNS y redirecciones; el transporte de httpx vuelve a resolver el host. No se ha implementado fijación de DNS contra rebinding, por lo que la importación debe limitarse a sitios públicos de confianza.
- Migraciones iniciales sencillas; no hay actualización automática del programa ni instalador binario firmado.
