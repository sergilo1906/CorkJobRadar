"""Deterministic hard gates; neither scores nor model prose can override them."""
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import math
import re
from ..config import digest
from ..normalization import normalized
from ..geography import valid_commute, effective_checks
from .policy import authorized_host
from .it_scope import classify_it_functions,AUTHORIZATION_SCOPE


@dataclass
class Reason:
    code: str
    severity: str
    evidence: str
    message: str = ''


@dataclass
class Decision:
    outcome: str
    reasons: list[Reason]
    policy_version: str | None
    confidence: float | None
    def to_dict(self):return asdict(self)


def evaluate_autoapply(job, analysis, profile, policy, transport=(), employer=None, platform=None,
                       *, control=None, candidate=None, clearance=None, policy_version=None,
                       clock=None, duplicate=False, quota_reason=None, db=None):
    clock=clock or datetime.now(ZoneInfo('Europe/Dublin'))
    reasons=[]
    def add(code, severity='HOLD', evidence=''):
        messages={
            'POLICY_OFF_OR_PAUSED':'Activa expresamente una política de simulación vigente o resuelve la pausa.',
            'POLICY_EXPIRED':'El permiso ha caducado: revisa y acepta una política nueva.',
            'DESTINATION_NOT_AUTHORIZED':'El dominio exacto de destino no está autorizado.',
            'ADAPTER_NOT_VERIFIED':'El adaptador no tiene una versión verificada para esta operación.',
            'AUTOMATION_PERMISSION_MISSING':'Falta acreditar permiso de automatización de esta plataforma.',
            'ALREADY_APPLIED_OR_RESERVED':'Existe una candidatura o reserva equivalente. No repetir sin conciliación fiable.',
            'APPLICATION_ACCEPTANCE_UNVERIFIED':'No hay evidencia suficiente de que esta vacante acepte candidaturas.',
            'NO_VERIFIED_ROUND_TRIP_WITHOUT_CAR':'Falta una ruta efectiva de ida y vuelta sin coche para los días y horas exactos.',
            'VERIFIED_REQUIREMENTS_AND_TERMS_MISSING':'Falta contraste vigente de requisitos y condiciones con citas y hechos aprobados.',
            'REQUIREMENTS_ANALYSIS_INCOMPLETE':'El análisis no acredita haber resuelto todos los requisitos obligatorios.',
            'CANDIDATE_OR_CV_VERSION_NOT_AUTHORIZED':'La versión de ficha o CV no figura en el permiso aceptado.',
            'VERIFIED_CV_MISSING':'Prepara, revisa y guarda un CV respaldado por afirmaciones aprobadas.',
            'SCHEDULE_UNKNOWN_OR_REJECTED':'Horario desconocido o fuera de las franjas autorizadas.',
            'CONTRACT_UNKNOWN_OR_REJECTED':'Contrato desconocido o no autorizado.',
            'HARD_SALARY_MINIMUM_UNVERIFIED':'No se acredita el mínimo duro en la moneda y unidad autorizadas.',
            'CAPTCHA_MFA_OR_ACCESS_BLOCK':'Acceso bloqueado o CAPTCHA/MFA: revisión manual, sin evasión.',
            'UNRESOLVED_FORM_QUESTIONS':'Quedan preguntas sin una respuesta veraz y preaprobada.',
            'NON_IT_EXCLUDED':'AutoApply solo admite IT. Esta oferta no tiene funciones informáticas elegibles.',
            'IT_CLASSIFICATION_UNCONFIRMED':'Las funciones reales no confirman IT; revisar la descripción, sin preparar ni enviar.',
            'IT_ONLY_POLICY_REQUIRED':'La política antigua debe sustituirse por una autorización exclusivamente IT.',
        }
        reasons.append(Reason(code,severity,evidence,messages.get(code,'Revisar la condición '+code+'; no se presume cumplida.')))
    control=control or {};candidate=candidate or {};platform=platform or {};clearance=clearance or {}
    it_scope=classify_it_functions(job)
    if it_scope.status!='CONFIRMED_IT':
        add('NON_IT_EXCLUDED' if it_scope.status=='NON_IT' else 'IT_CLASSIFICATION_UNCONFIRMED',
            'BLOCK' if it_scope.status=='NON_IT' else 'HOLD',it_scope.reason)
    if not policy or not control.get('enabled') or control.get('paused') or control.get('alert'):
        add('POLICY_OFF_OR_PAUSED','BLOCK')
    if not policy:return Decision('BLOCK',reasons,policy_version,analysis.get('data_confidence'))
    broad=policy.selection_mode=='IT_50KM_MAX3'
    if broad:
        if db is None:add('RADIUS_ASSESSMENT_REQUIRED')
        else:
            from .broad_selection import assess_selection
            selected=assess_selection(db,job,candidate,profile)
            if selected['origin_hash']!=policy.selection_origin_hash or selected['rules_version']!=policy.selection_rules_version:
                add('RADIUS_POLICY_BINDING_CHANGED','BLOCK')
            for code in selected['exclusions']:add(code,'BLOCK')
            for code in selected['essential_pending']:add(code)
    if policy.categories!=['IT'] or policy.authorization_scope!=AUTHORIZATION_SCOPE:add('IT_ONLY_POLICY_REQUIRED','BLOCK')
    if datetime.fromisoformat(policy.expires_at)<=clock:add('POLICY_EXPIRED','BLOCK')
    if not policy.window_start<=clock.strftime('%H:%M')<policy.window_end:add('OUTSIDE_TIME_WINDOW')
    if job.get('mode') not in policy.modes:add('MODE_NOT_AUTHORIZED','BLOCK')
    if not authorized_host(job.get('apply_url') or job['url'],policy):add('DESTINATION_NOT_AUTHORIZED','BLOCK')
    if not platform.get('verified') or policy.adapter_versions.get(platform.get('id'))!=platform.get('version'):
        add('ADAPTER_NOT_VERIFIED')
    if not platform.get('automation_permitted'):add('AUTOMATION_PERMISSION_MISSING')
    if platform.get('changed'):add('ADAPTER_CHANGED','BLOCK')
    if platform.get('blocked'):add('CAPTCHA_MFA_OR_ACCESS_BLOCK','BLOCK')
    company=normalized(employer or job['company']);title=normalized(job['title'])
    if company in [normalized(c) for c in policy.excluded_companies]:add('EMPLOYER_EXCLUDED','BLOCK')
    if policy.allowed_companies and company not in [normalized(c) for c in policy.allowed_companies]:add('EMPLOYER_NOT_ALLOWED','BLOCK')
    if any(normalized(w) in title for w in policy.forbidden_words):add('FORBIDDEN_TITLE','BLOCK')
    if policy.allowed_title_words and not any(normalized(w) in title for w in policy.allowed_title_words):add('TITLE_NOT_ALLOWED','BLOCK')
    if duplicate:add('ALREADY_APPLIED_OR_RESERVED','BLOCK')
    if quota_reason:add(quota_reason)
    if not broad and job.get('scope')=='FUERA_DE_ALCANCE':add('OUTSIDE_SEARCH_SCOPE','BLOCK')
    if job.get('possible_duplicate'):add('POSSIBLE_DUPLICATE')
    if job.get('open_status') in {'CLOSED_CONFIRMED','UNLISTED'}:add('JOB_CLOSED_OR_UNLISTED','BLOCK')
    elif job.get('open_status')!='OPEN_CONFIRMED':add('APPLICATION_ACCEPTANCE_UNVERIFIED')
    try:
        verified=datetime.fromisoformat(job.get('last_verified_at') or '')
        if verified.tzinfo is None or not timedelta(0)<=clock-verified<=timedelta(hours=policy.max_verification_hours):
            add('VERIFICATION_STALE')
    except (ValueError,TypeError):add('VERIFICATION_MISSING')
    raw=job.get('raw',{})
    if isinstance(raw,str):
        import json
        raw=json.loads(raw)
    from ..verification import evidence_status,deadline_state
    if evidence_status({**job,'raw':raw,'description':job.get('description','')},clock)[0]=='CLOSED_CONFIRMED':add('SOURCE_REPORTS_CLOSED','BLOCK')
    if deadline_state(raw,clock)[0] in {'UNKNOWN_TIMEZONE','AMBIGUOUS_LOCAL_TIME','UNPARSEABLE'}:add('DEADLINE_NOT_VERIFIABLE')
    if raw.get('_listing_type')=='BOLSA_DE_TALENTO_SIN_VACANTE_CONCRETA' and not policy.allow_talent_pools:
        add('TALENT_POOL','BLOCK')
    if not job.get('detail_complete'):add('INCOMPLETE_DESCRIPTION')
    if not broad and analysis.get('_content_hash')!=job.get('content_hash'):add('ANALYSIS_STALE_OR_UNBOUND')
    if not broad and analysis.get('analysis_completeness')!='COMPLETO':add('REQUIREMENTS_ANALYSIS_INCOMPLETE')
    score=analysis.get('fit_score');confidence=analysis.get('data_confidence')
    if not broad and (not isinstance(score,(int,float)) or isinstance(score,bool) or not math.isfinite(score) or score<policy.min_score):add('SCORE_BELOW_POLICY')
    if not broad and (not isinstance(confidence,(int,float)) or isinstance(confidence,bool) or not math.isfinite(confidence) or confidence<policy.min_confidence):add('CONFIDENCE_BELOW_POLICY')
    for key in ('full_name','email','work_authorization'):
        if not candidate.get(key):add('VERIFIED_'+key.upper()+'_MISSING')
    if candidate.get('work_authorization')!='IRELAND_AUTHORIZED':add('IRELAND_WORK_AUTHORIZATION_UNCONFIRMED')
    if not candidate.get('cv_document_id'):add('VERIFIED_CV_MISSING')
    if policy.candidate_facts_hash!=candidate.get('_facts_hash') or candidate.get('cv_document_id') not in policy.authorized_document_ids:
        add('CANDIDATE_OR_CV_VERSION_NOT_AUTHORIZED')
    bound=clearance.get('content_hash')==job.get('content_hash') and clearance.get('facts_hash')==candidate.get('_facts_hash')
    try:bound=bound and datetime.fromisoformat(clearance['expires_at'])>clock
    except (KeyError,ValueError,TypeError):bound=False
    if not bound and not broad:add('VERIFIED_REQUIREMENTS_AND_TERMS_MISSING')
    else:
        if not broad and clearance.get('requirements_met') is not True:add('MANDATORY_REQUIREMENTS_UNRESOLVED')
        if not broad and clearance.get('legal_eligibility') is not True:add('LEGAL_ELIGIBILITY_UNRESOLVED')
        if not broad and clearance.get('experience_met') is not True:add('EXPERIENCE_INCOMPATIBLE_OR_UNKNOWN')
        rule=policy.it
        if rule.schedules and clearance.get('schedule') not in rule.schedules:add('SCHEDULE_UNKNOWN_OR_REJECTED')
        if rule.contracts and clearance.get('contract') not in rule.contracts:add('CONTRACT_UNKNOWN_OR_REJECTED')
        if rule.full_time_required and clearance.get('full_time') is not True:add('FULL_TIME_UNVERIFIED')
        if rule.minimum_salary is not None:
            salary=clearance.get('salary')
            if not isinstance(salary,(int,float)) or isinstance(salary,bool) or not math.isfinite(salary) or clearance.get('salary_unit')!=rule.salary_unit or clearance.get('currency')!='EUR':add('HARD_SALARY_MINIMUM_UNVERIFIED')
            elif salary<rule.minimum_salary:add('SALARY_BELOW_HARD_MINIMUM','BLOCK')
    if broad:
        # Unknown commute/shift is a warning in this expressly selected policy.
        # Any additional hard terms still require factual evidence.
        if not bound and (policy.it.full_time_required or policy.it.schedules or policy.it.contracts or policy.it.minimum_salary is not None):add('EXPLICIT_HARD_TERMS_UNVERIFIED')
    elif job.get('mode')=='REMOTE':
        if not bound or clearance.get('remote_from_ireland') is not True:add('REMOTE_IRELAND_UNVERIFIED')
    else:
        if policy.location_scope=='CORK_CITY' and not re.search(r'\bcork city\b|\bballinlough\b|\bdouglas\b|\bblackrock,? cork\b',job.get('location',''),re.I):add('CORK_CITY_LOCATION_UNVERIFIED')
        valid=[]
        for check in effective_checks(transport):
            details=check.get('details',{})
            if isinstance(details,str):
                import json
                try:details=json.loads(details)
                except (ValueError,TypeError):continue
            if not isinstance(details,dict):continue
            exact_shift=all(clearance.get(k) and details.get(k)==clearance[k] for k in ('shift_start','shift_end','days'))
            duration=details.get('duration_minutes')
            within_limit=policy.max_commute_minutes is None or isinstance(duration,(int,float)) and not isinstance(duration,bool) and math.isfinite(duration) and 0<duration<=policy.max_commute_minutes
            if valid_commute(check,profile) and within_limit and details.get('job_content_hash')==job.get('content_hash') and details.get('schedule')==clearance.get('schedule') and details.get('valid_until') and exact_shift:
                valid.append(check)
        if not valid:add('NO_VERIFIED_ROUND_TRIP_WITHOUT_CAR')
    if not all((policy.permissions.generate_cv,policy.permissions.attach_cv,policy.permissions.fill_forms)):
        add('PREPARATION_PERMISSIONS_MISSING')
    if platform.get('unresolved_questions'):add('UNRESOLVED_FORM_QUESTIONS')
    outcome='BLOCK' if any(r.severity=='BLOCK' for r in reasons) else 'HOLD' if reasons else 'ALLOW'
    return Decision(outcome,reasons,policy_version,confidence)
