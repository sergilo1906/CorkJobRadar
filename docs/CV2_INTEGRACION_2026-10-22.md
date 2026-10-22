# Generador profesional de CV — entrega parcial para revisión

Fecha: 22 de octubre de 2026, Europe/Dublin. Base auditada: `main`, commit `2acde61e7e17f3cf971696f8ca159a4a7f216e41`.

## Estado comprobado y alcance

Se revisaron el código del repositorio, su checkpoint más reciente y el paquete documental anterior. El README y el prompt de migración están desactualizados respecto del checkpoint: este registra CV id2 aprobado desde las 11:35:37, 26 paquetes locales, 22 hechos vigentes, 613 ofertas y cero envíos. Son observaciones documentadas del equipo Windows; no se ha consultado su base de producción en esta sesión. No se debe pedir otra aprobación del mismo documento ni revocarlo por este cambio.

Esta entrega mejora el generador compartido. No acredita haber importado el PDF elegido en el equipo Windows ni que el generador reproduzca exactamente su diseño. El clon contiene código, no los hechos cifrados ni el supervisor local. El CV aprobado existente se conserva; solo las generaciones posteriores utilizan la nueva plantilla.

| Requisito | Implementación o evidencia | Estado |
| --- | --- | --- |
| Plantilla profesional PDF/Word | `autoapply/cv_layout.py`, título destacado, contacto, márgenes A4 y encabezados semánticos | Implementado |
| Fuente única de hechos | `render_cv` consume el mismo snapshot, conserva literalmente cada afirmación y verifica su presencia en el resultado | 12 regresiones PASS |
| Perfil, proyectos y experiencia adicional | Secciones admitidas por el validador y ambos editores; proyectos antiguos reconocibles se agrupan como afirmaciones completas | Implementado, sin migración de hechos |
| Adaptación por oferta | Reordena afirmaciones por vocabulario; no incorpora texto de la web; conserva bloqueo de ofertas no IT | PASS sintético |
| PDF de una página | Prueba tamaños de 10, 9.5 y 9 puntos; rechaza desbordamiento sin truncar | PASS sintético |
| Word editable | Encabezados reales, texto en orden de lectura, sin tablas ni cajas de texto | PASS estructural y revisión visual de una página sintética |
| Consentimiento separado | Revisión idempotente pendiente; no aparece como documento aprobado | PASS con doble de almacenamiento solo en el test |
| LIVE y envíos | El test comprueba LIVE 0, sin políticas ni intentos; código de envío y control sin cambios | PASS sintético; Windows no verificado |
| Documentos fuente | Validador del paquete: PDF principal 1 página; conjunto con tres cartas 4 páginas; Word consistente | PASS documental |
| Referencias originales | No se editaron ni publicaron; conjunto original SHA256 `5fef8620ce220fd4fbadfb0e62ed7679337f0017b7a03aa16935548f4cc13a14` | Conservadas en la fuente; importación cifrada pendiente |
| Integridad de producción, 22 hechos, ofertas y supervisor | Sin acceso al almacenamiento Windows; no se ejecutaron migraciones ni comandos de búsqueda sobre producción | No verificado |
| SQLite de prueba | `integrity_check=ok`, `foreign_key_check` vacío, sin hechos/políticas/intentos creados | PASS |

## Pruebas ejecutadas

- `python -m pytest -q tests/test_professional_cv.py --basetemp=data/pytest-cv-only`: **12 PASS**.
- Suite completa iniciada antes del último test adicional: **369 PASS, 255 FAIL**, 624 casos, 205.64 s. 251 fallos reportan `VAULT_REQUIRES_WINDOWS_DPAPI`, tres carecen del ejecutable Chromium configurado y uno falla en comprobaciones de proceso del runtime Windows. No se considera una suite aprobada ni se suman sus casos a los anteriores. No se desactivó DPAPI ni se modificaron pruebas existentes para hacerlas pasar.
- Ampliación dirigida (`test_professional_cv`, `test_units`, `test_autoapply_cv_import`): **36 PASS, 3 FAIL**; los tres fallos requieren DPAPI Windows. Solapa con los grupos anteriores.
- `compileall` y `git diff --check`: PASS.
- PDF sintético renderizado con Poppler; Word sintético renderizado con `render_docx.py`; inspección visual realizada. No son el CV real ni acreditan el resultado de los 22 hechos de producción.
- El primer intento de suite falló por ausencia del directorio temporal `data/`; se creó el directorio y se repitió la suite. Las dependencias disponibles aquí no son el entorno fijado de Windows. El fixture grande de Lever se recuperó íntegro del remoto tras fallar su primera descarga; no se modificó en la propuesta.

## Límites y continuación en Windows

1. Aplicar esta rama sobre el checkout existente, preservando cambios locales y creando las copias consistentes habituales antes de cualquier escritura privada. No sustituirlo por este clon ni restaurar bases de prueba.
2. Ejecutar la suite con el entorno Windows fijado y Chromium ya configurado. Revisar escritorio y móvil en Perfil y configuración, generación por oferta y descargas. Esta propuesta sigue en borrador hasta esa validación.
3. Comprobar el CV id2 aprobado sin revocarlo. Para una nueva revisión profesional, usar el flujo existente de importación o generación. La autorización de desarrollo no aprueba ese documento nuevo. No cambiar ni reaprobar en bloque los hechos existentes.
4. Contrastar los 22 textos vigentes con el PDF elegido. Los apartados nuevos no se rellenan inventando un perfil ni duplicando hechos. La compatibilidad literal conservadora del importador puede rechazar textos parafraseados: resolver ese caso con revisión explícita, no relajando comprobaciones.
5. La igualdad de contenido PDF/Word se comprueba; Word puede paginar de forma diferente según fuentes y motor. Revisar la página real antes de usarlo. La réplica exacta del diseño de referencia, el subtítulo profesional, la comparación visual de versiones y el acceso cifrado opcional a cartas quedan pendientes.
6. Verificar conteos, hashes privados, estado del supervisor y LIVE OFF sobre el equipo real. No se ha enviado ninguna candidatura desde esta sesión.

Rollback: revertir el commit de esta propuesta. No hay migración SQL ni sustitución de documentos/hechos. Las revisiones que se creen después deben conservarse en su historial; nunca borrar ni restaurar bases de producción para revertir la plantilla.
