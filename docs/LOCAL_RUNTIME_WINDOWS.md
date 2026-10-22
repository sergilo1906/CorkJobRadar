# Funcionamiento continuo local en Windows

La aplicación, supervisor, trabajadores, SQLite y cifrado se ejecutan en este ordenador. La interfaz escucha en **127.0.0.1:8501**. No se instala un servicio, VPS, servidor externo, cuenta de pago ni tarea de Windows. Internet sigue siendo necesario para consultar las fuentes públicas de empleo. **LIVE OFF**: actividad local no equivale a permiso de candidatura ni de envío.

## Uso

El panel superior **Actividad local continua · Windows · LIVE OFF** permite iniciar, pausar, reanudar, detener y pedir una búsqueda inmediata. La frecuencia inicial es **6 horas**, configurable entre 0,25 y 168 horas. El intervalo siguiente se calcula al finalizar el recorrido; no se acumulan decenas de búsquedas después de una noche suspendido.

El supervisor es un proceso independiente. Un vigilante en el proceso de Streamlit lo recupera si termina inesperadamente. Cerrar la pestaña no detiene ninguno. Cerrar el proceso de la aplicación sí hace que el supervisor cierre su actividad guardando la intención y los puntos de reanudación. Pausar/detener solicita terminar la página o tarea actual de forma segura: puede seguir visible STOPPING mientras termina la petición con su tiempo de espera. No se matan procesos ajenos.

El panel muestra estado solicitado/real, supervisor, último recorrido, próxima búsqueda, latido, última preparación, pendientes y errores, paquetes preparados, declaraciones manuales y recepciones externas separadas. Los avisos persistentes incluyen CV pendiente, pregunta imprescindible, CAPTCHA/MFA/intervención existente, preparación fallida y fuente bloqueada. Se puede activar sonido local opcional; no se instala un servicio de notificaciones ni correo automático. Leer un aviso no resuelve el requisito.

## Qué se ejecuta

- Reutiliza `junior_discovery`, los tres conectores de `config/junior_it_sources.yaml`, el análisis básico local y sus colas persistentes. Las publicaciones globales recuperadas se conservan con estado; no se presenta ese listado como cobertura de todo Cork. Las fuentes desactivadas, con permisos cambiados o bloqueadas no se reactivan automáticamente. No se reintenta una fuente/detalle bloqueado continuamente.
- La selección y preparación reutilizan IT/DAM por funciones, Ballinlough y 50 km en línea recta, mínimo solicitado de hasta 3 años, advertencias para deseables/dudas menores/transporte pendiente y bloqueos esenciales. Remotos separados, sin coche supuesto. Una coordenada de localidad no acredita el centro real. Las dudas de ubicación siguen pendientes, no se inventa distancia.
- Prepara todos los paquetes posibles con un CV **ya aprobado**, LinkedIn/contactos y respuestas aprobadas. Reutiliza la inspección de formulario vigente si existe; los campos nuevos obligatorios quedan sin inventar y generan aviso. Se conservan versiones/documentos, cifrado, identificadores y prevenciones de duplicados. Sin aprobación final del CV no genera paquetes como si ya estuviera autorizado.
- Descubrimiento, preparación y envío son vías independientes. No hay transporte de envío en el supervisor. LinkedIn e Indeed permanecen manuales; CAPTCHA/MFA se gestionan mediante el sistema de intervención ya existente, sin evasión ni resolución automática. Ningún recibo local/declaración pasa a ser confirmación empresarial.
- Un bloqueo físico por base impide dos supervisores y otro impide dos trabajadores de búsqueda/preparación. PID más hora de creación evitan confundir un PID reutilizado. El arranque se serializa. Un latido antiguo no autoriza robar una tarea si el proceso o bloqueo siguen vivos. El lanzador de Python puede mostrar un PID adicional que espera al intérprete; no es otro trabajo lógico.
- Reanuda cursores y tareas interrumpidas después de liberar el bloqueo real. Reintentos de procesos usan espera creciente y se pausan tras tres fallos. Trabajos antiguos de análisis avanzado/modelo local requieren reanudación manual para respetar sus recursos y controles; el servicio autónomo no carga un modelo por sorpresa. Un trabajo externo activo se deja terminar.

SQLite **v12 aditiva** contiene control, eventos y avisos locales. La preparación conserva la cola v11 y sus leases. Cambios en ficha, CV, documentos, preguntas, funciones, comprobaciones o fuentes provocan revisión de preparación. No se guardan contraseñas, cookies, tokens CAPTCHA ni respuestas personales en eventos/logs del supervisor.

## Arranque de aplicación e inicio opcional de sesión

```powershell
.\.venv\Scripts\pythonw.exe scripts/iniciar_local.py
```

El lanzador comprueba puerto y propietario de proceso, reutiliza el servidor verificado si existe, o inicia uno local y su vigilante sin consola visible. Conserva RUNNING/PAUSED/STOPPED; no activa una política ni envíos. El vigilante funciona incluso antes de abrir una pestaña.

**Inicio al entrar en Windows no instalado por el agente.** El panel ofrece descargar `CorkJobRadar-inicio-opcional.vbs`. Descargar no activa nada. Solo si lo deseas, puedes abrir **Win+R → shell:startup** y copiar tú ese archivo. Quitar ese archivo de Inicio desactiva ese mecanismo. No se modifican Registro, servicios, tareas programadas ni otros proyectos. Si Windows ha deshabilitado VBScript, puedes crear manualmente un acceso directo a `pythonw.exe scripts/iniciar_local.py` en esa carpeta; no se instala ni habilita un componente del sistema automáticamente.

CLI de diagnóstico/control, siempre con LIVE OFF:

```powershell
.\.venv\Scripts\python.exe -m corkjobradar local-runtime status
.\.venv\Scripts\python.exe -m corkjobradar local-runtime pause
.\.venv\Scripts\python.exe -m corkjobradar local-runtime resume
.\.venv\Scripts\python.exe -m corkjobradar local-runtime stop
```

El CLI guarda intención; el vigilante de la aplicación activa el supervisor. No es un servicio que trabaje después de cerrar todos los procesos locales.

## Evidencia y límites

`logs/local-runtime-real-scan.json`: ciclo externo real de **lectura GET** ejecutado por el supervisor en una copia aislada, 4 Evo-soft +80 SolarWinds +38 Version 1, 61 análisis y 6 detalles terminados. Copia pasó de 579 a 581, hechos22, intentos0; durante ese ensayo no se modificaron tablas críticas principales. Esto prueba descubrimiento/análisis, **no envío ATS**.

`logs/local-runtime-production-cycle.json`: primer ciclo real completado también en la base principal, ahora **581 ofertas y 22 hechos**; CV pendiente, cero paquetes o envíos reales. Queda activo cada **6 horas**, próxima búsqueda **22/10/2026 04:23:26 Europe/Dublin**, configurable desde el panel. Suite completa **552 PASS** y regresión final posterior **105 PASS**, solapadas. Copia final y comprobación en `logs/local-runtime-final-backup.json` y `logs/local-runtime-backup-verification.json`; historial previo y cuatro activos cifrados conservados.

`logs/local-runtime-browser-proof.json` y la prueba `tests/test_local_runtime_browser.py`: Chromium real local, pestaña cerrada mientras siguen latidos, cierre del servidor de prueba, salida del supervisor y reinicio de la aplicación con la misma base, botones pausa/reanudar/detener. Procesos y puertos aislados, ninguna petición externa de navegador, ningún reinicio del ordenador. `tests/test_local_runtime.py` comprueba horarios, salto de reloj/suspensión simulada, cursores, tareas, bloqueo Windows real, muerte/reinicio de supervisor propio, cambios de configuración, bloqueos de fuentes, avisos y ausencia de envíos. Las cifras finales están en PROGRESO/checkpoint y XML, sin sumar suites solapadas.

**No se ha suspendido, apagado ni reiniciado Windows durante el desarrollo.** Las pruebas de muerte/reinicio son de procesos propios y los saltos de reloj son simulados. Microsoft documenta límites de las [notificaciones de apagado de consolas](https://learn.microsoft.com/en-us/windows/console/handlerroutine); por eso la recuperación se apoya en transacciones y puntos persistentes, sin depender de recibir un último callback al apagar. No trabaja durante suspensión/apagado. Falta el ensayo físico siguiente para acreditar este equipo concreto.

## Ensayo manual del equipo, sin envíos

1. Guardar otros trabajos. Mantener LIVE OFF y revisar última búsqueda, próximo horario y pendientes en el panel/CLI. Anotar proceso/latido y estado de cola.
2. Cerrar solo la pestaña, esperar al menos diez segundos y volver a abrir: el latido debe avanzar y la cola conservarse.
3. Pausar, esperar que termine la tarea/petición en curso y comprobar que no se inicia otra búsqueda. Reanudar: una búsqueda vencida se ejecuta una sola vez.
4. Suspender Windows desde su menú y reanudar. Comprobar eventos TIME_GAP, latidos, un solo trabajador y ausencia de acumulación de recorridos. Verificar las ofertas por identificador, no solo por un contador.
5. Apagar Windows normalmente tras guardar los demás programas. Al iniciar sesión, abrir el lanzador manualmente; únicamente si tú instalaste el inicio opcional debe abrirse solo. Si la intención era RUNNING debe retomarla, si era PAUSED/STOPPED debe respetarla.
6. Comprobar integridad, cursores, pendientes, duplicados e incertidumbres, y guardar evidencia del ensayo. La confirmación real de candidatos seguirá necesitando autorización externa separada.

El agente no ejecuta `shutdown`, cambios de energía, reinicios forzados, instalación de inicio de sesión ni servicios sobre tu sesión de trabajo.
