"""Permanent AutoApply restriction. Employer identity and model scores confer no authority."""
import re
from dataclasses import dataclass,asdict
from ..passages import source_passages

AUTHORIZATION_SCOPE='IT_ONLY_CONFIRMED_FUNCTIONS_V1'
CLASSIFIER_VERSION='it-functions-1.3'

EXCLUDED_TITLES=re.compile(r'\b(?:warehouse (?:operative|assistant|worker|manager|supervisor)|picker|packer|retail|supermarket|shop assistant|cashier|stockroom|'
    r'(?:production|manufacturing|assembly|cleanroom)\s+(?:operative|operator|technician|worker|associate)|'
    r'logistics (?:operative|coordinator|assistant)|delivery driver|truck driver|courier|'
    r'chef|waiter|waitress|catering|housekeep\w*|cleaner|cleaning operative|plumber|electrician|HVAC)\b',re.I)
ACTION=re.compile(r'^(?:[•*\-]\s*|\d+[.)]\s*)*(?:(?:you will|you.ll|the successful candidate will|responsible for)\s+)?'
    r'(?:provide|deliver|troubleshoot|resolve|diagnose|support|maintain|install|configure|administer|manage|'
    r'develop|implement|code|build|debug|design|test|validate|automate|execute|write|perform|report|'
    r'building|writing|maintaining|debugging|integrating|automating|monitor|investigate|triage|respond|analyse|analyze|prepare|repair|handle|pick|pack|load|unload|drive|clean|serve|process|stock|operate)\b',re.I)
IT_DUTIES={
 'IT_SUPPORT':r'\b(?:support|troubleshoot|resolve|diagnose|install|configure|maintain|provide|deliver|administer)\b.{0,160}\b(?:Windows|Microsoft 365|Office 365|M365|Active Directory|IT incidents?|IT support|computer(?:s| hardware)?|laptops?|desktop systems?|software (?:issues?|incidents?|applications?))\b',
 'APPLICATION_SUPPORT':r'\bserve\b.{0,130}\b(?:internal|software) development\b.{0,160}\b(?:bug resolution|software issues)\b|\b(?:support|troubleshoot|resolve|diagnose|investigate)\b.{0,160}\b(?:software applications?|application incidents?|database errors?|software tickets?)\b',
 'SOFTWARE_DEVELOPMENT':r'\b(?:develop|implement|code|build|building|debug|debugging|integrating|design|maintain)\b.{0,160}\b(?:software|web applications?|websites?|native Android|iOS|Java|Python|SQL|JavaScript|HTML|CSS|React|Astro|C#|\.NET|APIs?)\b',
 'SOFTWARE_QA':r'\b(?:test|validate|automate|execute|design|write|perform|report)\b.{0,160}\b(?:software|web applications?|software bugs?|software testing|automated software tests?)\b',
 'SYSTEMS_NETWORK_CLOUD':r'\b(?:monitor|maintain|configure|support|administer|manage|troubleshoot)\b.{0,160}\b(?:IT infrastructure|servers?|computer networks?|network infrastructure|cloud infrastructure|Azure|AWS|Linux|network connectivity)\b',
 'CYBERSECURITY':r'\b(?:monitor|investigate|triage|respond|analyse|analyze)\b.{0,160}\b(?:security alerts?|cybersecurity|cyber security threats?|SIEM|SOC alerts?|endpoint security)\b',
}
NON_IT_DUTIES=re.compile(r'\b(?:pick|pack|load|unload|stock)\b.{0,90}\b(?:goods|orders|pallets|shelves|stock|boxes)\b|'
    r'\b(?:serve|prepare)\b.{0,60}\b(?:food|meals|drinks)\b|\b(?:process|resolve|handle)\b.{0,80}\b(?:billing|refunds|delivery complaints)\b|'
    r'\b(?:install|repair|maintain)\b.{0,80}\b(?:HVAC|heating|plumbing)\b|\boperate\b.{0,60}\b(?:production|manufacturing) machinery\b',re.I)


@dataclass
class ITScope:
    status:str
    reason:str
    evidence:list
    families:list
    version:str=CLASSIFIER_VERSION
    def to_dict(self):return asdict(self)


def classify_it_functions(job):
    title=job.get('title','');text=job.get('description') or ''
    if EXCLUDED_TITLES.search(title):return ITScope('NON_IT','EXCLUDED_NON_IT_ROLE',[],[])
    passages,_=source_passages(text);positive=[];negative=[];families=set()
    for passage in passages:
        if passage['section'] not in {'duties','unknown'}:continue
        for clause in re.split(r'\n+|(?<=[.!?])\s+',passage['text']):
            clause=clause.strip()
            if not clause or not ACTION.search(clause):continue
            if re.search(r'\b(?:not required to|will not|do not|never)\b',clause,re.I):continue
            hits=[name for name,pattern in IT_DUTIES.items() if re.search(pattern,clause,re.I)]
            if hits:
                positive.append({'quote':clause,'offset':text.find(clause),'families':hits});families.update(hits)
            if NON_IT_DUTIES.search(clause):negative.append({'quote':clause,'offset':text.find(clause)})
    if positive and negative:return ITScope('AMBIGUOUS','MIXED_IT_AND_NON_IT_FUNCTIONS',positive+negative,sorted(families))
    if positive:
        if not job.get('detail_complete'):return ITScope('AMBIGUOUS','INCOMPLETE_IT_DESCRIPTION',positive,sorted(families))
        if job.get('category') in {'Almacen','Produccion','Tecnicos'}:return ITScope('AMBIGUOUS','IT_CATEGORY_REVIEW_REQUIRED',positive,sorted(families))
        return ITScope('CONFIRMED_IT','TECHNOLOGICAL_FUNCTIONS_CONFIRMED',positive,sorted(families))
    if negative or job.get('category') in {'Almacen','Produccion'} or re.search(r'\bcustomer (?:service|care)\b',title,re.I):
        return ITScope('NON_IT','NON_TECHNOLOGICAL_FUNCTIONS',negative,[])
    return ITScope('AMBIGUOUS','TECHNOLOGICAL_FUNCTIONS_NOT_CONFIRMED',[],[])


def require_it_job(job):
    result=classify_it_functions(job)
    if result.status!='CONFIRMED_IT':
        raise PermissionError('NON_IT_EXCLUDED' if result.status=='NON_IT' else 'IT_CLASSIFICATION_UNCONFIRMED')
    return result
