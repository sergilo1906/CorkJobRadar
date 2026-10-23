# Borradores periódicos por oferta — validación local23/10/2026

El trabajador local ahora genera los CV y cartas por oferta sin exigir la aprobación del CV general retenido. La generación crea borradores cifrados; la aprobación de contenido, diseño, formato y documentos opcionales sigue correspondiendo al usuario. LIVE OFF.

## Funcionamiento implementado

- `autoapply/document_preparation.py` conecta la selección existente con la composición de documentos. Examina el inventario entero, sin cortes por ranking, y prepara ofertas IT locales razonables. Excluidas, remotas con autorización separada, candidaturas ya registradas y requisitos obligatorios incompatibles no generan borradores automáticos. Las pistas geográficas permiten revisar; no acreditan radio, centro ni transporte.
- Los requisitos deseables no excluyen. Horarios, transporte sin coche, dudas académicas/idiomas y preguntas pendientes siguen visibles y no se convierten en requisitos cumplidos. No se infiere equivalencia de DAM a Bachelor/NFQ8.
- Reutiliza versiones vigentes, incluidas las familias y el límite de páginas elegidos por el usuario. Los hechos modificados crean versiones pendientes conservando las anteriores. Una revocación para los mismos datos impide recrearla automáticamente, con segunda comprobación dentro de la transacción de escritura tras renderizar.
- Si falla una oferta, conserva un HOLD y continúa con las demás. Un activo cifrado corrupto se conserva para revisión; no se sustituye silenciosamente. Una pausa deja versiones persistentes reutilizables. No hay transporte HTTP, exportación, aprobación ni envío en este preparador.
- El supervisor reutiliza sus bloqueos y procesos existentes; el identificador de versión de la composición forma parte de la huella de trabajo. La preparación desactivada sigue desactivada. No se crean servicios ni inicio automático de Windows.
- Inicio muestra borradores separados de candidaturas preparadas. **Revisar borradores de CV y carta → Borradores por revisar** reúne versiones pendientes de distintos estados de la cola. Los avisos abren directamente el paso CV.
- Corregida la reactivación de avisos: una causa pendiente puede reabrir su fila resuelta sin duplicados; conserva el aviso leído mientras siga activo y solo repite el sonido opcional cuando la causa reaparece.

## Evidencias y alcance exacto

Suite completa: **734 PASS**,0 fallos/errores/omitidas,26 avisos (`logs/document-runtime-final-release.xml`). Esta ejecución precede al último arreglo de reapertura de avisos; después, **75 PASS** de regresión del código actual en documentos, avisos, supervisor, transiciones y navegador (`logs/document-runtime-final-notifications.xml`,7 avisos). Se solapan y no se suman. La completa previa733 y los ensayos dirigidos188/21 siguen conservados. No se atribuyen estos resultados a GitHub CI.

Instalación real Chromium1440/390 PASS: Inicio → filtro de borradores → aviso → CV de la oferta, vista previa, aprobación deshabilitada, opcionales desmarcados, calidad retenida del CV4 y referencias pendientes. Cero peticiones externas, capturas privadas o cambios en las diez tablas críticas del comprobador. `logs/per-job-document-runtime-production-final.json`.

La primera prueba de navegador sintético falló por el selector del comprobador, corregido sin relajar controles. La primera comprobación de producción descubrió los avisos ya resueltos que no se reabrían; se corrigió el servicio, se añadieron regresiones y se repitió con éxito. Los fallos y sus logs se conservan.

Con el perfil cifrado: **15 borradores actuales,24 versiones históricas por oferta y60 archivos PDF/DOCX validados**. Los tres ejemplos anteriores se reutilizaron y se añadieron12 borradores. Son documentos para revisar, no15 candidaturas plenamente elegibles; varias ofertas conservan condiciones académicas, lingüísticas o de transporte pendientes. La validación y renderización LibreOffice de las tres familias del22/10 permanece documentada en `PER_JOB_DOCUMENTS_2026-10-22.md`; este ciclo no acredita Microsoft Word ni revisión humana del contenido.

Conservación: `logs/document-runtime-final-preservation.json`:616 ofertas/3.028 análisis,22 hechos vigentes/24 históricos,4 CV generales,3 referencias pendientes,52 paquetes históricos y0 bundles aprobados nuevos/0 intentos. Catorce tablas estáticas idénticas a la copia inicial, historia anterior retenida,76 activos cifrados anteriores idénticos,7 tablas de transporte sin cambios, SQLite/FK correctas y0 contactos en logs/bases revisados.

Se recuperó la aplicación cuyos procesos habían cesado después de las08:03. Dos recargas controladas posteriores cargaron módulos coherentes, sin dos supervisores simultáneos. Repetición por el supervisor existente:0 versiones duplicadas, horario conservado (`logs/document-runtime-recovery.json`). No se ensayó un apagado, suspensión o reinicio físico de Windows.

## Búsqueda y uso

El ciclo22 nocturno fue parcial: Evo-soft no permitió verificar robots.txt y quedó bloqueado, sin eludirlo ni reintentarlo continuamente. El ciclo23 completó118 observaciones de SolarWinds81 y Version1 37; no son118 ofertas nuevas ni cobertura completa de Cork. El supervisor queda RUNNING/WAITING cada6h, próxima búsqueda **23/10 a las16:30:12 Europe/Dublin** al comprobar.

Abrir **Inicio → Revisar borradores de CV y carta**, elegir candidatura y paso CV; también **Actividad y notificaciones → Revisar CV y carta**. Comparar hechos, requisitos y diseño; solo el usuario aprueba el paquete exacto. Las referencias necesitan originales independientes revisados y autorización expresa; permanecen opcionales y desmarcadas. No aprobar CV4 ni volver a pedir los22 hechos.

Copias: `logs/document-runtime-start-backup.json` y `logs/document-runtime-final-backup.json`; verificación final `logs/document-runtime-backup-verification.json`. Se conservan las anteriores, sin restaurar sobre producción. Código en la rama `work/per-job-documents-20261022`, PR6 en borrador; main no se fusiona ni sobrescribe. Bases, CV y pruebas privadas siguen fuera de Git.

AutoApply externo continúa pendiente de mecanismo permitido, ensayo autorizado con recepción real y activación separada de política. LinkedIn/Indeed manuales. Esta fase no acredita ni autoriza un envío externo.
