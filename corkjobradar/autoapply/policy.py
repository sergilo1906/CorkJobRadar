from datetime import datetime, time
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit
import getpass
import json
import re
from uuid import uuid4
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from ..config import digest, now, load_profile
from . import ENGINE_VERSION, LIVE_RELEASED
from .it_scope import AUTHORIZATION_SCOPE


class Permissions(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    generate_cv: bool = False
    attach_cv: bool = False
    generate_letter: bool = False
    fill_forms: bool = False
    final_submit: bool = False
    read_email: bool = False


class SectorRule(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    schedules: list[str] = Field(default_factory=list)
    contracts: list[str] = Field(default_factory=list)
    full_time_required: bool = True
    minimum_salary: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    salary_unit: str = 'hour'
    @field_validator('salary_unit')
    @classmethod
    def unit(cls, value):
        if value not in {'hour','year'}: raise ValueError('Unidad salarial: hour o year')
        return value


class Policy(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    categories: list[str] = Field(default_factory=lambda:['IT'])
    authorization_scope: Literal['IT_ONLY_CONFIRMED_FUNCTIONS_V1'] = AUTHORIZATION_SCOPE
    selection_mode: Literal['LEGACY_STRICT','IT_50KM_MAX3'] = 'LEGACY_STRICT'
    selection_origin_hash: str = ''
    selection_rules_version: str = ''
    modes: list[str] = Field(default_factory=list)
    location_scope: Literal['CORK_AND_SURROUNDINGS','CORK_CITY'] = 'CORK_AND_SURROUNDINGS'
    max_commute_minutes: int | None = Field(default=None,ge=1,le=240)
    allowed_hosts: list[str] = Field(default_factory=list)
    adapter_versions: dict[str,str] = Field(default_factory=dict)
    candidate_facts_hash: str = ''
    authorized_document_ids: list[int] = Field(default_factory=list)
    engine_version: str = ENGINE_VERSION
    excluded_companies: list[str] = Field(default_factory=list)
    allowed_companies: list[str] = Field(default_factory=list)
    allowed_title_words: list[str] = Field(default_factory=list)
    forbidden_words: list[str] = Field(default_factory=list)
    min_score: int = Field(default=70, ge=0, le=100)
    min_confidence: int = Field(default=80, ge=0, le=100)
    max_daily: int = Field(default=3, ge=1, le=100)
    max_weekly: int = Field(default=15, ge=1, le=500)
    max_company_weekly: int = Field(default=1, ge=1, le=100)
    cooldown_hours: int = Field(default=168, ge=1)
    max_failures: int = Field(default=1, ge=1, le=10)
    window_start: str = '09:00'
    window_end: str = '18:00'
    expires_at: str
    max_verification_hours: int = Field(default=24, ge=1, le=168)
    allow_talent_pools: bool = False
    geographic_exceptions: dict[str,str] = Field(default_factory=dict)
    permissions: Permissions = Field(default_factory=Permissions)
    it: SectorRule = Field(default_factory=SectorRule)
    non_it: SectorRule = Field(default_factory=lambda:SectorRule(schedules=['WEEKDAYS_DAY'],contracts=['PERMANENT']))
    @field_validator('categories')
    @classmethod
    def it_only(cls,value):
        if value!=['IT']:raise ValueError('AUTOAPPLY_IT_ONLY: categorías debe contener exclusivamente IT')
        return value
    @field_validator('allowed_hosts')
    @classmethod
    def hosts(cls, values):
        for v in values:
            if v!=v.lower() or not re.fullmatch(r'[a-z0-9]+(?:[.-][a-z0-9]+)*\.[a-z]{2,}',v):
                raise ValueError('Dominio exacto en minúsculas, sin comodines, puertos ni URLs')
            if v.endswith(('.local','.localhost','.test')) or v=='localhost':
                raise ValueError('Los dominios de test solo se permiten en el banco de pruebas aislado')
        return values
    @model_validator(mode='after')
    def valid_dates(self):
        if self.engine_version!=ENGINE_VERSION:raise ValueError('IT_ONLY_ENGINE_REAUTHORIZATION_REQUIRED')
        if self.geographic_exceptions:raise ValueError('IT_ONLY_REQUIRES_VERIFIED_TRANSPORT_NO_EXCEPTIONS')
        if self.selection_mode=='IT_50KM_MAX3':
            from .broad_selection import RULES_VERSION
            if self.selection_rules_version!=RULES_VERSION or not re.fullmatch('[a-f0-9]{64}',self.selection_origin_hash):
                raise ValueError('EXPLICIT_RADIUS_RULES_AND_ORIGIN_BINDING_REQUIRED')
            if self.location_scope=='CORK_CITY':raise ValueError('RADIUS_POLICY_REQUIRES_50KM_SCOPE')
        expiry=datetime.fromisoformat(self.expires_at)
        if expiry.tzinfo is None: raise ValueError('Caducidad con zona horaria obligatoria')
        if time.fromisoformat(self.window_start)>=time.fromisoformat(self.window_end):
            raise ValueError('Franja diurna: inicio debe preceder al fin')
        if self.max_weekly<self.max_daily: raise ValueError('Cupo semanal menor que diario')
        return self


def profile_hash(profile=None):
    return digest({k:v for k,v in (profile or load_profile()).items() if not k.startswith('_')})


def event(db, kind, details=None, plan_id=None, attempt_id=None, before=None, after=None):
    # Only caller supplied codes/hashes/IDs. Never pass page text, answers or exceptions.
    db.execute('''INSERT INTO application_events(plan_id,attempt_id,occurred_at,kind,before_state,after_state,details)
                  VALUES(?,?,?,?,?,?,?)''',(plan_id,attempt_id,now(),kind,before,after,json.dumps(details or {},sort_keys=True)))


def save_policy(db, config, consent, profile=None):
    policy=Policy.model_validate(config)
    if consent!='AUTHORIZE_SIMULATION':
        raise ValueError('Aceptación expresa de simulación requerida; no autoriza envío real')
    if datetime.fromisoformat(policy.expires_at)<=datetime.now(ZoneInfo('Europe/Dublin')):
        raise ValueError('La política ya ha caducado')
    payload=policy.model_dump()
    with db.transaction() as con:
        con.execute('BEGIN IMMEDIATE')
        pid=db.execute('''INSERT INTO autoapply_policies(version,created_at,local_user,consent,config,integrity_hash,profile_hash)
                          VALUES(?,?,?,?,?,?,?)''',(uuid4().hex,now(),getpass.getuser(),consent,json.dumps(payload,sort_keys=True),digest(payload),profile_hash(profile)))
        db.execute('''UPDATE autoapply_control SET enabled=1,live_enabled=0,paused=0,alert=0,
                      epoch=epoch+1,policy_id=?,updated_at=?,reason='SIMULATION_CONSENT' WHERE id=1''',(pid,now()))
        event(db,'POLICY_SIMULATION_ACCEPTED',{'policy_id':pid,'hash':digest(payload),'engine':ENGINE_VERSION})
    return pid


def pause(db, reason='USER_PAUSE', revoke=False, alert=False):
    with db.transaction():
        db.execute('''UPDATE autoapply_control SET paused=1,enabled=CASE WHEN ? THEN 0 ELSE enabled END,
                      live_enabled=0,alert=?,epoch=epoch+1,updated_at=?,reason=? WHERE id=1''',(int(revoke),int(alert),now(),reason))
        event(db,'PERMISSION_REVOKED' if revoke else 'PAUSED',{'reason':reason})


def current_policy(db, profile=None):
    control=db.rows('SELECT * FROM autoapply_control WHERE id=1')[0]
    rows=db.rows('SELECT * FROM autoapply_policies WHERE id=?',(control['policy_id'],))
    if not rows: return control,None,None
    row=rows[0];payload=json.loads(row['config'])
    if payload.get('authorization_scope')!=AUTHORIZATION_SCOPE or payload.get('categories')!=['IT']:
        if control['enabled'] or not control['paused']:
            pause(db,'IT_ONLY_POLICY_REAUTHORIZATION_REQUIRED',revoke=True)
        return {**control,'enabled':0,'paused':1,'live_enabled':0,'reason':'IT_ONLY_POLICY_REAUTHORIZATION_REQUIRED'},row,None
    if digest(payload)!=row['integrity_hash'] or row['profile_hash']!=profile_hash(profile) or payload.get('engine_version')!=ENGINE_VERSION:
        if not control['paused']: pause(db,'POLICY_OR_PROFILE_CHANGED',alert=True)
        control={**control,'paused':1,'reason':'POLICY_OR_PROFILE_CHANGED'}
    try: policy=Policy.model_validate(payload)
    except ValueError:
        if not control['paused']:pause(db,'INVALID_POLICY',alert=True)
        return {**control,'paused':1},row,None
    return control,row,policy


def resume(db, consent, profile=None):
    control,row,policy=current_policy(db,profile)
    if consent!='RESUME_SIMULATION' or not policy or not control['enabled'] or control['alert'] or datetime.fromisoformat(policy.expires_at)<=datetime.now(ZoneInfo('Europe/Dublin')):
        raise ValueError('Revisar política, vigencia y alertas; aceptar otra versión si cambió el perfil')
    with db.transaction():
        db.execute("UPDATE autoapply_control SET paused=0,epoch=epoch+1,updated_at=?,reason='RESUMED_SIMULATION' WHERE id=1",(now(),))
        event(db,'RESUMED_SIMULATION')


def require_live(db):
    # Deliberate release barrier. No CLI/UI/config switch can bypass the missing F5 trial.
    if not LIVE_RELEASED:
        raise PermissionError('LIVE_LOCKED: falta ensayo controlado autorizado y validación del adaptador; cero envíos')
    raise PermissionError('LIVE_LOCKED: activación futura requiere consentimiento y límites expresos')


def authorized_host(url, policy):
    try:
        p=urlsplit(url)
        return p.scheme=='https' and not p.username and not p.password and p.port in {None,443} and p.hostname in policy.allowed_hosts
    except ValueError:return False
