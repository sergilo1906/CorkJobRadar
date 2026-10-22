from dataclasses import dataclass, field
from pydantic import BaseModel, Field, field_validator
from urllib.parse import urlsplit
import ipaddress

class Job(BaseModel):
    external_id: str
    title: str
    company: str = 'No indicado por la empresa'
    location: str = 'No indicado por la empresa'
    url: str
    apply_url: str | None = None
    description: str = ''
    detail_complete: bool = False
    posted_at: str | None = None
    mode: str = 'DESCONOCIDO'
    raw: dict = Field(default_factory=dict)

    @field_validator('url','apply_url')
    @classmethod
    def public_link(cls,value):
        if value is None:
            return value
        p=urlsplit(value)
        if p.scheme not in {'http','https'} or not p.hostname or p.username or p.password or p.port not in {None,80,443}:
            raise ValueError('Enlace de oferta HTTP(S) inválido')
        if p.hostname=='linkedin.com' or p.hostname.endswith('.linkedin.com') or p.hostname in {'localhost','localhost.localdomain'}:
            raise ValueError('Enlace excluido')
        try:
            ip=ipaddress.ip_address(p.hostname)
        except ValueError:
            ip=None
        if ip is not None and not ip.is_global:
            raise ValueError('No se permiten enlaces de redes privadas')
        return value

@dataclass
class Page:
    jobs: list[Job]
    cursor: str | None
    expected_total: int | None = None
    complete: bool | None = None
    evidence: dict = field(default_factory=dict)

class DeepAnalysis(BaseModel):
    model_config = {'extra': 'forbid'}
    summary_es: str
    duties_es: list[str]
    mandatory_es: list[str]
    desirable_es: list[str]
    evidence_quotes: list[str]
    unknown_fields: list[str]
