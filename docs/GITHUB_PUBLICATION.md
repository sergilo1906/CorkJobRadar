# Repositorio de código y datos locales

**Visibilidad actual: público**, por instrucción expresa del usuario el22/10/2026. Repositorio: https://github.com/sergilo1906/CorkJobRadar. Antes del cambio se revisaron los311 blobs del historial de3 commits, sin coincidencias de contactos reales o patrones de secretos; acceso anónimo confirmado con HTTP200. Evidencia local: `logs/github-public-history-audit.json` y `logs/github-public-visibility.json`.

El repositorio GitHub contiene el código, las pruebas, las configuraciones de ejemplo y la documentación del proyecto. Su visibilidad inicial es **privada**.

Las carpetas `data/`, `logs/`, `exports/`, `.venv/`, los CV y anexos, las bases SQLite, los activos DPAPI, las copias de seguridad y los secretos permanecen en Windows y están excluidos de Git. Los ficheros de fixtures incluidos contienen ejemplos de prueba o publicaciones públicas, no el perfil personal real. La documentación de continuidad conserva el contexto funcional del proyecto; no contiene el CV ni los contactos de la ficha cifrada.

`docs/VERIFIED_TEST_RESULTS_2026-10-22.json` resume resultados reales de JUnit con los nombres de los informes. Los XML/logs completos y las capturas siguen en las carpetas locales; no se atribuye a GitHub una ejecución de esas pruebas ni una confirmación de candidatura.

Un clon no recupera las ofertas, documentos, aprobaciones ni datos cifrados del ordenador. Para continuar en este equipo se utiliza la carpeta actual, conservando sus bases y copias. DPAPI está ligado al usuario Windows; subir el código no convierte los activos cifrados en datos portables ni activa LIVE.

Antes de futuros commits, ejecutar `git add` sobre los archivos de código deseados y `python scripts/audit_github_publish.py`. La comprobación inspecciona los blobs preparados, bloquea rutas privadas, patrones de secretos y contactos reales disponibles localmente, y no imprime sus valores. No utiliza red ni envía datos.
