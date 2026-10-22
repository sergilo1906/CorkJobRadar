# Lectura local en español — validación limitada

Estado: **EN DESARROLLO**. Se valida una capacidad de lectura/traducción asistida con citas, **no** el análisis semántico completo sin revisión ni la elegibilidad de candidaturas. La interfaz conserva REVISIÓN_MANUAL y AutoApply sigue OFF.

## Modelo y alcance

Qwen3-4B-Q4_K_M.gguf existente, runtime portátil llama.cpp Vulkan, NVIDIA RTX 3050 4 GB, dos hilos CPU y contexto 4096. No se ha instalado otro modelo ni software del sistema. La carga se bloquea por RAM/VRAM insuficientes. Antes de activar el lector se comprueba SHA-256 contra el manifest de procedencia; no basta que exista un archivo GGUF.

Prompt `translate-es-4-memory-terms`, comprobación `translation-spans-1`. Se exige una traducción por cada pasaje, se conserva toda la estructura/fuente, se controlan cifras/negaciones y se protegen nombres académicos y de sistemas. El glosario local declara expresamente los pasajes que resuelve por correspondencia literal revisada; no se atribuyen al modelo. Las cifras se normalizan solo cuando el valor, orden y número de apariciones coinciden. Los fallos se conservan como pendientes y los lotes correctos permiten reanudación.

## Ensayos reales y correcciones

Se utilizaron **copias separadas** de SQLite y cinco descripciones reales guardadas: Purchase To Pay Administrator, Production Administrator, Production Operator, Localisation QA Australian Market y Localisation QA Danish. No se enviaron datos profesionales privados ni se crearon candidaturas.

- El ensayo inicial no arrancó por RAM insuficiente; se mantuvo la salvaguarda. Después hubo recursos suficientes.
- Versión 1: mejoró tareas concretas, pero falló formatos numéricos e interpretó Leaving Certificate de forma incorrecta. No aprobada.
- Versión 2: 133 pasajes cubiertos sin fallos mecánicos; revisión de fuente/traducción detectó One Vault convertido en almacén. No aprobada.
- Versión 3: términos protegidos y fallos retenidos; se detectaron falsos positivos numéricos en identificadores y ambigüedad de self driven. No aprobada.
- Versión 4: **133/133 pasajes** en los cinco anuncios, sin errores de validación. Se revisaron los fallos anteriores contra citas: One Vault conserva su nombre; Leaving Certificate no se renombra; Treasury se interpreta como Tesorería; accrual como devengo; los molinos son equipos; formación ofrecida se separa de registros de formación; self driven y viaje de regreso usan correspondencias exactas revisadas. Evidencia: `logs/translation-evaluation-2026-10-19T195447+0100.json`, bases de evaluación dentro de `data/`.

Hay 8 pasajes de los dos anuncios QA resueltos por glosario; la cifra de 133 no significa 133 traducciones generadas por IA. El contador de caracteres enviados al modelo se corrigió para excluir esos pasajes; los reportes anteriores se conservan como históricos. Cada traducción puede revisarse junto a su fuente original.

Esta muestra reducida de dos empleadores no demuestra exactitud universal. Hay expresiones poco naturales y las categorías documentales se apoyan en secciones, no en decisiones legales del modelo. No se estima porcentaje de precisión ni probabilidad de contratación. Las ofertas nuevas, los datos no publicados y cualquier fallo siguen con estado explícito. Los resultados anteriores v6 no se convierten retroactivamente en validados.

## Revisión ampliada posterior — incidencias reales

La lectura de más ofertas confirmó límites semánticos que las comprobaciones mecánicas no detectan: en NETGEAR, `AV-over-IP deployments` se convirtió en «depósitos»; en Egis, una frase de Casual Toll Operator perdió el carácter ocasional del puesto. Se conservan las salidas incorrectas originales en sus versiones y se añadieron **correcciones literales revisadas**, con cita completa, hash, URL de evidencia y procedencia en `config/reviewed_translation_spans.json`. No se atribuyen a la IA ni equivalen a una validación de datos profesionales del candidato.

`reading_qa.py` aplica `literal-review-1` después de la lectura y en la ficha; corrige únicamente correspondencias exactas revisadas. Una variante no revisada que contenga esos errores queda retenida, con fuente y salida previa conservadas. El backend de revisión también lo comprueba. `scripts/apply_reading_corrections.py` añade versiones, sin reescribir los originales; aplicación real inicial: análisis 697→708 y 699→709, ambos todavía para revisión humana (`logs/continuity-reading-corrections.json`). El proceso 12 cargó código anterior al arrancar; la ficha aplica la protección al leerlo y la continuación local reanalizará con doc-5/literal-review-1 y caché.

Pruebas de regresión e integración posteriores: **41 superadas** (`logs/continuity-reading-qa.xml`). La cobertura de pasajes y una muestra limitada no permiten afirmar traducción infalible ni análisis exhaustivo automatizado. Persisten revisiones y pasajes retenidos por formato/unidad numérica.
