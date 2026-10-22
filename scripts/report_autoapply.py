"""Generate the AutoApply evidence report from completed test/audit files."""
from pathlib import Path
import json
import sys
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from corkjobradar.config import now


def suite(name):
    path=ROOT/'logs'/name
    root=ET.parse(path).getroot()
    suites=list(root) if root.tag=='testsuites' else [root]
    return {k:sum(float(s.get(k,0)) for s in suites) for k in ('tests','failures','errors','skipped','time')}


def main():
    final=suite('autoapply-delivery.xml')
    assert final['failures']==final['errors']==final['skipped']==0
    baseline=suite('autoapply-baseline.xml')
    audit=json.loads((ROOT/'logs/autoapply-final-audit.json').read_text(encoding='utf-8'))
    ui=json.loads((ROOT/'logs/autoapply-ui-browser.json').read_text(encoding='utf-8'))
    counts=audit['reopened_excel_rows']
    text=f'''# AutoApply: informe de pruebas y límites

Generado: {now()}. Windows 11 / Python 3.12.4, `.venv` del proyecto. **Simulación únicamente; ningún envío real.**

## Resultado medido

- Baseline antes de AutoApply: **{int(baseline['tests'])} pruebas superadas**, {baseline['time']:.2f} s, 10 avisos existentes (`logs/autoapply-baseline.xml`).
- Suite final: **{int(final['tests'])} pruebas superadas**, {int(final['failures'])} fallos, {int(final['errors'])} errores, {int(final['skipped'])} omitidas, {final['time']:.2f} s (`logs/autoapply-delivery.xml` / `.log`). 14 avisos de deprecación Streamlit/NumPy, no fallos.
- F1 dirigida: 26 superadas. F2: un primer fallo al normalizar errores de PDF inválido, corregido; 4 casos específicos superados después. Primeras pruebas Chromium: 10 superadas. Integración F3/UI: 30 superadas. Seguridad combinada: 40 superadas. Casos adicionales: 8 superados. Las suites se solapan: no sumar sus recuentos como casos distintos.
- Dos suites completas intermedias de 148 casos también pasaron; se preservan sus XML y logs. Tres casos posteriores prueban números no finitos para no permitir salario/score/confianza desconocidos.
- `pip check` sin dependencias rotas, `compileall` sin errores. Instalación opcional real desde ausencia de Playwright/ReportLab y repetición de `instalar-autoapply.ps1` correctas. Chromium se ha lanzado en este Windows; no solo instalado.

## Prueba sobre datos reales sin envío

`autoapply run --dry-run`: **415 ofertas procesadas, 415 decisiones BLOCK por política OFF, cero errores, cero intentos y cero candidaturas enviadas**. La segunda ejecución no duplicó planes. Los motivos están persistidos; no son una afirmación de que esas ofertas nunca puedan ser elegibles tras configurar datos y permisos.

`autoapply run --live`: código de salida **2**, `LIVE_LOCKED`; comprobado sin crear intentos. `policy validate` del ejemplo y `reconcile` sin correo ni clics también ejecutados. No se ha aceptado una política activa en producción ni añadido datos personales ficticios.

Inspección pública real Greenhouse de GlobeTech Cork (19/10/2026): GET con preguntas, idioma nativo y GDPR; evidencia en `logs/autoapply-greenhouse-inspection-d23d74f13d944cc3a670bb1f0ab6e75a.json`. Ningún dato del candidato se envió a esa web. Las condiciones de automatización y el DOM alojado no se han validado para enviar.

Streamlit real iniciado en `127.0.0.1:8501`, no solo AppTest. Chromium abrió la pestaña nueva y encontró el estado `{ui['state']}` y el botón de pausa; cero formularios enviados (`logs/autoapply-ui-browser.json`). Los controles de datos/política/trabajador se prueban además con AppTest sobre SQLite aislada.

## Conservación y exportación

La copia inicial contiene código/config/tests/docs, SQLite principal v4 y SQLite de transporte, con SHA-256 en `data/backups/before-autoapply-20261019-185937/manifest.json`. Integridad/FK verificadas. La primera comprobación del ZIP se ejecutó antes de cerrar el escritor y falló; se reabrió y verificó después correctamente, registrado en el manifiesto.

Restauración a `data/autoapply-restoration-test.sqlite3` y migración v4→v5: **todas las filas históricas iguales**, integridad OK, cero errores FK (`logs/autoapply-restoration-test.json`). Auditoría final: todas las tablas de negocio anteriores conservan exactamente sus filas. Solo la caché HTTP incorpora la lectura pública deliberada del formulario. No se han borrado ofertas, notas ni candidaturas; no hay fixtures ni hechos profesionales sintéticos en producción.

Excel reabierto: **{counts['Todas_las_ofertas']} ofertas, {counts['AutoApply_planes']} planes, {counts['AutoApply_intentos']} intentos y {counts['Candidaturas']} candidaturas**, con eventos/cupos. JSON reabierto y CSV BOM comprobados. Archivos exactos en `logs/autoapply-final-audit.json`, bajo `exports/autoapply-verified/`. La exportación no incluye el contenido descifrado de la bóveda.

## Escenarios reproducibles cubiertos

| Grupo | Comprobación |
|---|---|
| Política | OFF, caducada, perfil cambiado, revocación, pausa antes del paso final, inmutabilidad y auditoría append-only |
| Preferencias | IT sin ruta aunque esté en radio de coche; IT fin de semana con ruta; NO IT bici o bus directo; transbordos rechazados |
| Datos | Requisitos/permiso laboral/CV ausentes, vigencia dudosa, bolsa de talento, salario/horario desconocidos, análisis desactualizado |
| Duplicados | Indeed/web oficial, dos reservas concurrentes, cuota diaria, cancelación/incertidumbre conservan identidad |
| Formularios | Greenhouse/Lever sintéticos, regresión de esquema Cork, campos/etiquetas, uploads PDF/DOCX, selects, HTML inválido, campos añadidos |
| Bloqueos | CAPTCHA/login/MFA representado por campos, firma/consentimiento/preguntas obligatorias sin respuesta, bloqueo de red y redirects privados |
| Confirmación | HTTP 200 sin recibo no confirma; recibo con ID de oferta y referencia; acción no iniciada no confirma; correo ausente no se inventa |
| Recuperación | Navegador cerrado, cambio de CV/ficha durante relleno, caída tras acción de fixture, ENVIO_INCIERTO sin reintento |
| Privacidad | DPAPI real, ACL Windows, sin contacto en eventos, PDF inválido rechazado, hashes, borrado y revocación |
| Inyección | Texto del anuncio no modifica destino/afirmaciones; exfiltración a loopback abortada por sandbox offline |

## Reproducir

```powershell
.\\.venv\\Scripts\\python.exe -m pytest -q --basetemp=data\\pytest-autoapply-recheck --junitxml=logs\\autoapply-recheck.xml
.\\.venv\\Scripts\\python.exe -m corkjobradar autoapply doctor
.\\.venv\\Scripts\\python.exe -m corkjobradar autoapply run --dry-run
.\\.venv\\Scripts\\python.exe scripts\\check_autoapply_ui.py
```

Las pruebas son secuenciales y usan bases temporales del proyecto. La comprobación de navegador UI requiere Streamlit local iniciado; no pulsa botones que envíen ni rellena datos reales. El auditor `scripts/audit_autoapply.py` compara con el estado inicial de esta intervención, por lo que detectará también cambios legítimos que haga el usuario posteriormente: no deben borrarse para forzar igualdad.

## No probado / pendiente

F4 parcial: adaptar y validar formularios alojados de un ATS con permiso de automatización. F5: ensayo real concreto todavía no autorizado. F6: backend de envío y confirmación real, conciliación fiable/seguimiento y activación live por política pendientes; no basta retirar una bandera. F7: plataformas adicionales. No hay lector de correo, compatibilidad universal ni análisis semántico exhaustivo validado. Cancelados/inciertos no tienen reintento automático ni botón para liberar reservas sin prueba.

La incidencia de TEMP del controlador en las primeras pruebas se explica en `AUTOAPPLY_SAFETY.md`; está corregida y cubierta por regresión. Los resultados offline no acreditan permiso contractual ni funcionamiento de un envío real.
'''
    (ROOT/'docs/AUTOAPPLY_TEST_REPORT.md').write_text(text,encoding='utf-8')
    print(json.dumps({'report':str(ROOT/'docs/AUTOAPPLY_TEST_REPORT.md'),'final_suite':final}))


if __name__=='__main__':main()
