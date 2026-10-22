# Política y uso de AutoApply

Flujo actual: [manual operativo](AUTOAPPLY_OPERATIONS.md). El CV pendiente y su revisión sobreviven a reinicios. La política se configura con controles guiados, sin necesidad de YAML, y solo se acepta para simulación tras aprobar el CV. Guardar respuestas exactas nuevas pausa la política sin invalidar un CV cuyo contenido no cambió. Ninguna acción de configuración inicia un trabajador ni habilita envío real.

**Alcance vigente exclusivamente IT.** Leer `AUTOAPPLY_IT_ONLY.md`. Ningún empleo general se autoriza para AutoApply. Las funciones reales del anuncio deben confirmar IT; los casos ambiguos se retienen. Las políticas anteriores requieren sustitución por autorización IT. LIVE OFF.

## Uso seguro actual

1. Inicia la aplicación con `iniciar.ps1` y abre **Candidaturas automáticas**.
2. Completa hechos profesionales y afirmaciones en inglés. Confirma únicamente lo que sea cierto. `IRELAND_AUTHORIZED` solo si has verificado ese permiso; no significa que lo hayamos supuesto. Nombre, apellidos, idiomas y experiencia no se deducen.
3. Prepara o importa un CV PDF/DOCX, descárgalo, revísalo completo y guarda expresamente su versión. La generación conserva todas las afirmaciones; puede reordenarlas para una oferta. La carta es opcional y local.
4. El único sector autorizable es IT. Configura modalidades, dominios exactos, score/confianza y cupos. El editor avanzado contiene permisos, contratos, turnos, salario duro, exclusiones, versiones de adaptador, franja y caducidad. Guarda con aceptación explícita **solo de simulación**. La UI vincula las versiones de ficha/CV actuales; CLI exige que estén indicadas en el archivo.
5. Ejecuta la simulación completa. Consulta los planes y los códigos concretos. Una política apagada bloquea todas; un dato desconocido retiene la candidatura. Las ofertas continúan en la búsqueda habitual.
6. Resuelve hechos o evidencias faltantes; cualquier cambio de ficha invalida CV anteriores y pausa la política. Acepta una versión nueva si cambió el alcance o los datos.
7. El ensayo real todavía **no está habilitado**. Cuando se implemente y exista permiso por plataforma, el usuario deberá elegir y autorizar expresamente una oferta para F5. Solo tras verificarlo podrá desarrollarse/liberarse la activación real por política. No se solicita esa autorización ahora.

El ejemplo `config/autoapply.example.yaml` está desactivado, sin dominios ni permisos. 3/día y 15/semana son sugerencias, no preferencias atribuidas al usuario. Validar YAML no concede consentimiento. `final_submit=true` por sí solo jamás habilita live.

## Preferencias y evidencias

IT no exige L–V; los turnos/fines de semana aceptados deben aparecer expresamente en `it.schedules`. Las antiguas reglas NO IT ya no autorizan candidaturas. Valores de contratos y horarios son códigos exactos de evidencia, no inferencias extraídas por coincidencia libre. Salario orientativo no se convierte en mínimo duro. Un mínimo duro exige importe, moneda y unidad conocidos.

Todo presencial/híbrido requiere ruta efectiva desde Ballinlough; ya no se admiten excepciones que omitan comprobar transporte. La referencia de 60 minutos en coche nunca basta. La ruta debe tener ida y vuelta, acceso a origen, destino, vigencia y coincidencia de horas/días exactos con las condiciones contrastadas. El verificador actual admite bicicleta o autobús directo sin transbordos; rutas con transbordos todavía requieren desarrollo adicional. El planificador GTFS solo no acredita una ruta efectiva.

La comprobación documental de una oferta **no autoriza su envío individual**: aporta hechos que la política evalúa. Se conserva ligada al hash del anuncio y de la ficha. Por ejemplo, el JSON de la UI admite:

```json
{
  "requirements_met": true,
  "legal_eligibility": true,
  "experience_met": true,
  "schedule": "WEEKDAYS_DAY",
  "contract": "PERMANENT",
  "full_time": true,
  "shift_start": "09:00",
  "shift_end": "17:00",
  "days": ["MON", "TUE", "WED", "THU", "FRI"],
  "evidence": {
    "requirements_met": {"quote": "CITA LITERAL DEL ANUNCIO", "fact_ids": [123]}
  }
}
```

**Ejemplo de formato, no hechos del usuario ni de una vacante.** Cada campo obligatorio y cada condición opcional declarada necesitan su propia entrada `evidence`, cita literal y IDs de hechos aprobados. No copiar números/horarios de este ejemplo a ofertas reales. Salario usa `salary`, `salary_unit` (`hour`/`year`) y `currency`; remoto desde Irlanda necesita `remote_from_ireland` con evidencia. La ruta JSON añade `destination`, `outbound`, `return`, `shift_compatible`, `origin_access`, `valid_until`, `schedule`, `shift_start`, `shift_end`, `days` y opcionalmente `duration_minutes`; sus valores deben proceder de comprobaciones reales.

## CLI implementada

```powershell
.\.venv\Scripts\python.exe -m corkjobradar autoapply doctor
.\.venv\Scripts\python.exe -m corkjobradar autoapply policy show
.\.venv\Scripts\python.exe -m corkjobradar autoapply policy validate --file config\autoapply.example.yaml
.\.venv\Scripts\python.exe -m corkjobradar autoapply preview --limit 25
.\.venv\Scripts\python.exe -m corkjobradar autoapply run --dry-run
.\.venv\Scripts\python.exe -m corkjobradar autoapply pause
.\.venv\Scripts\python.exe -m corkjobradar autoapply revoke
.\.venv\Scripts\python.exe -m corkjobradar autoapply reconcile
.\.venv\Scripts\python.exe -m corkjobradar autoapply report
.\.venv\Scripts\python.exe -m corkjobradar autoapply inspect --job ID_REAL
```

`policy accept --file RUTA --consent AUTHORIZE_SIMULATION` crea una versión aceptada explícitamente para simulación; `resume --consent RESUME_SIMULATION` reanuda solo una política vigente y no revocada. `run --live` devuelve código 2 y `LIVE_LOCKED`. No figura en instaladores ni tareas. Los informes Excel habituales incluyen planes, intentos, eventos y cupos AutoApply; la exportación privada de ficha es una acción separada y explícita.

En el historial puedes elegir **No repetir**, **Marcar resuelta** o **Reintentar preparación simulada**. Las dos primeras conservan identidades/cupos y no certifican recepción externa; una resolución manual impide reintentos posteriores. La tercera exige diario completo anterior a cualquier envío, política/ficha/evidencias vigentes y cuotas disponibles, y únicamente vuelve a validar documentos locales. Nunca reintenta un envío incierto o LIVE. Si otro trabajador tiene el lock, espera a que termine antes de resolver.

CLI equivalente, sustituyendo ID y fecha exacta por los que muestra el historial:

```powershell
.\.venv\Scripts\python.exe -m corkjobradar autoapply resolve --attempt ID --action NO_REPETIR --expected-updated-at FECHA_ISO_DEL_HISTORIAL --acknowledge
```

La fecha evita actuar sobre una vista obsoleta. Los otros códigos de acción son `MARCAR_RESUELTA` y `REINTENTAR_PREPARACION_SIMULADA`. No se liberan reservas ni se consulta correo con estas acciones. Justo antes del paso final se vuelven a comprobar duplicados, caducidad de la oferta y cuotas; una reserva de un día anterior se contabiliza en el día efectivo tras comprobar capacidad.
