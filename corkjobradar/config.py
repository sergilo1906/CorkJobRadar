from pathlib import Path
import hashlib
import json
from datetime import datetime
from zoneinfo import ZoneInfo
import yaml

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "radar.sqlite3"

def now():
    return datetime.now(ZoneInfo("Europe/Dublin")).isoformat(timespec="seconds")

def load_profile():
    return yaml.safe_load((ROOT / "config/profile.yaml").read_text(encoding="utf-8"))

def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

def save_profile(profile):
    original = load_profile()
    if not isinstance(profile,dict) or not set(original).issubset(profile):
        raise ValueError('Faltan campos obligatorios del perfil')
    if profile.get('analyzer') not in {'basic','ollama','llama'}:
        raise ValueError('Analizador disponible: basic, ollama o llama local; no hay IA externa activada')
    if profile['non_it_max_bus_transfers'] != 0:
        raise ValueError('El alcance NO IT requiere un único autobús sin transbordos')
    for key in ('owns_car','has_bicycle','public_transport','it_weekdays_required'):
        if not isinstance(profile[key],bool):
            raise ValueError(f'{key} debe ser true o false')
    if not isinstance(profile['weights'],dict) or set(profile['weights'])!=set(original['weights']) or any(not isinstance(x,(int,float)) or x<0 for x in profile['weights'].values()):
        raise ValueError('Pesos de criterios inválidos')
    if sum(profile["weights"].values()) != 100:
        raise ValueError("Los pesos deben sumar 100")
    for sector,weights in profile.get('weights_by_sector',{}).items():
        if sector not in {'IT','NO_IT'} or not isinstance(weights,dict) or set(weights)!=set(original['weights']) or any(not isinstance(x,(int,float)) or x<0 for x in weights.values()) or sum(weights.values())!=100:
            raise ValueError('Pesos IT/NO_IT deben tener los mismos criterios y sumar 100')
    for key in ('http_timeout','max_response_bytes','safety_max_pages','it_car_radius_minutes_reference'):
        if not isinstance(profile[key],(int,float)) or profile[key]<=0:
            raise ValueError(f'{key} debe ser positivo')
    if profile['safety_max_pages'] != int(profile['safety_max_pages']):
        raise ValueError('safety_max_pages debe ser entero')
    for key in ('max_bicycle_minutes','max_bus_minutes'):
        if profile[key] is not None and (not isinstance(profile[key],(int,float)) or profile[key]<=0):
            raise ValueError(f'{key}: null o minutos positivos')
    path = ROOT / "config/profile.yaml"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(yaml.safe_dump(profile, allow_unicode=True, sort_keys=False), encoding="utf-8")
    tmp.replace(path)
