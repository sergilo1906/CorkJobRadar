import re
from .normalization import normalized

def effective_checks(checks):
    latest={}
    for check in checks:
        latest.setdefault((check.get('origin'),check.get('mode')),check)
    return list(latest.values())

def valid_commute(check, profile):
    details = check.get('details', {})
    if isinstance(details, str):
        import json
        try:details = json.loads(details)
        except (ValueError,TypeError):return False
    if not isinstance(details,dict):return False
    if details.get('valid_until'):
        from .config import now
        from datetime import date
        try:
            if date.fromisoformat(details['valid_until'])<date.fromisoformat(now()[:10]):return False
        except (ValueError,TypeError):return False
    if check.get('origin') != profile['origin_neighborhood']:
        return False
    if check.get('viability') != 'VERIFICADA' or not check.get('evidence_url'):
        return False
    if not all(details.get(k) for k in ('destination', 'outbound', 'return', 'shift_compatible', 'origin_access')):
        return False
    if details.get('shift_compatible') is not True:return False
    duration=details.get('duration_minutes')
    if duration is not None:
        import math
        if isinstance(duration,bool) or not isinstance(duration,(int,float)) or not math.isfinite(duration) or duration<=0:return False
    if check['mode'] == 'bus':
        if type(check.get('transfers')) is not int or check['transfers'] != 0 or not profile['public_transport']:
            return False
        maximum = profile.get('max_bus_minutes')
    elif check['mode'] == 'bicycle':
        if not profile['has_bicycle']:
            return False
        maximum = profile.get('max_bicycle_minutes')
    else:
        return False
    return maximum is None or (details.get('duration_minutes') is not None and details['duration_minutes'] <= maximum)

def scope_for(job, cat, profile, checks=()):
    checks=effective_checks(checks)
    loc = normalized(job['location'])
    raw = job.get('raw', {})
    # Un remoto sin país no demuestra elegibilidad para residir en Irlanda.
    remote = job.get('mode') == 'REMOTE'
    if remote and re.search(r'\bireland\b', loc + ' ' + str(raw.get('applicantLocationRequirements','')).lower()):
        return 'EN_ALCANCE', 'Remoto publicado para Irlanda; confirmar condiciones contractuales', 'REMOTO_IRLANDA'
    structured_location = raw.get('location',{})
    city_field = structured_location.get('city','') if isinstance(structured_location,dict) else ''
    city = normalized(city_field)=='cork city' or bool(re.search(r'\bcork city\b|\bballinlough\b|\bdouglas\b|\bblackrock,? cork\b', loc))
    # Cork a secas se conserva pendiente: ciudad y condado son ambiguos.
    if city and not remote:
        return 'EN_ALCANCE', 'Localidad identificada como Cork City; trayecto del turno pendiente', 'CORK_CITY'
    if any(valid_commute(c, profile) for c in checks):
        return 'EN_ALCANCE', 'Trayecto sin coche documentado de ida y vuelta para el turno', 'RUTA_VERIFICADA'
    if cat == 'IT':
        if city or re.search(r'\bcork\b', loc):
            return 'ACCESIBILIDAD_PENDIENTE', 'TRAYECTO_REAL_SIN_VERIFICAR; radio IT y ubicación exacta pendientes', 'IT_REFERENCIA_PENDIENTE'
        # La referencia de 60 minutos se registra manualmente con evidencia.
        if any(c.get('mode') == 'car_reference' and c.get('viability') == 'VERIFICADA'
               and c.get('origin') == profile['origin_neighborhood'] and c.get('evidence_url')
               and __import__('json').loads(c['details']).get('duration_minutes', 999) <= profile['it_car_radius_minutes_reference']
               for c in checks):
            return 'EN_ALCANCE', 'Radio IT de referencia documentado; TRAYECTO_REAL_SIN_VERIFICAR', 'IT_RADIO_REFERENCIA'
    distant = re.search(r'\b(dublin|london|galway|limerick|belfast|sligo|westport|mayo|new york|san francisco|seattle|germany|poland|france|united states|usa|us|australia|india|spain|mexico|guadalajara|kentucky|california|taipei|taiwan|san jose|burlingame|richmond|vancouver|los angeles|washington dc|united kingdom|uk|virginia|chicago|new zealand|canada)\b', loc)
    if distant and not re.search(r'\bcork\b|\bireland\b', loc):
        return 'FUERA_DE_ALCANCE', 'Ubicación o región remota publicada fuera de Irlanda/Cork; sin elegibilidad Irlanda documentada', 'OTRA_ZONA'
    if distant and not re.search(r'\bcork\b', loc) and not remote:
        return 'FUERA_DE_ALCANCE', 'Ubicación publicada fuera del área objetivo; conservar archivada', 'OTRA_ZONA'
    if checks and all(c.get('viability') == 'NO_VIABLE' for c in checks) and cat != 'IT':
        return 'FUERA_DE_ALCANCE', 'Comprobaciones documentadas no viables sin coche', 'SIN_RUTA_VIABLE'
    return 'ACCESIBILIDAD_PENDIENTE', 'Ubicación, radio o ruta sin coche no verificados; no se elimina', 'SIN_VERIFICAR'
