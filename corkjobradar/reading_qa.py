"""Source-bound, versioned corrections; developer review is not candidate consent."""
from copy import deepcopy
import json
import re
from .config import ROOT,digest

QA_VERSION='literal-review-1'


def normalized_span(text):return ' '.join(text.split())


def reviewed_reading(reading,corrections=None):
    if not reading or not str(reading.get('method','')).startswith('TRADUCCION_INTEGRA'):return reading
    if corrections is None:
        path=ROOT/'config/reviewed_translation_spans.json'
        corrections=json.loads(path.read_text(encoding='utf-8'))['corrections'] if path.exists() else []
    by_source={normalized_span(c['source']):c for c in corrections}
    result=deepcopy(reading);items=[];rejected=[]
    for item in result.get('items',[]):
        source=item['quote'];span=normalized_span(source);correction=by_source.get(span)
        if correction:
            if digest(span)!=correction['source_hash']:raise ValueError('REVIEWED_SOURCE_HASH_MISMATCH')
            if item['explanation_es']!=correction['spanish']:
                item.setdefault('original_model_translation',item['explanation_es'])
                item.update(explanation_es=correction['spanish'],translation_method='CORRECCION_LITERAL_REVISADA',
                            correction_version=QA_VERSION,correction_evidence=correction['evidence'])
        codes=[]
        if re.search(r'\bdeployments?\b',source,re.I) and re.search(r'\bdep[oó]sitos?\b',item['explanation_es'],re.I):
            codes.append('DEPLOYMENT_IS_NOT_DEPOSIT')
        if re.search(r'^Casual Toll Operators\b',span,re.I) and not re.search(r'ocasional|eventual|suplenci',item['explanation_es'],re.I):
            codes.append('CASUAL_EMPLOYMENT_TYPE_LOST')
        if codes:
            rejected.append({**item,'reason_codes':codes})
            result.setdefault('errors',[]).append({'passage_ids':[item['id']],'error':'SEMANTIC_REVIEW_REQUIRED',
                                                  'reason_codes':codes,'source_quote':source})
        else:items.append(item)
    result.update(items=items,post_reading_qa_version=QA_VERSION,
                  passages_from_reviewed_corrections=sum(i.get('translation_method')=='CORRECCION_LITERAL_REVISADA' for i in items))
    if 'passages_translated' in result:result['passages_translated']=len(items)
    if rejected:
        result['rejected_items']=result.get('rejected_items',[])+rejected
        result['status']='PROFUNDO_PARCIAL'
    return result


def reviewed_analysis(analysis):
    result=deepcopy(analysis);before=result.get('semantic',{})
    after=reviewed_reading(before)
    if after==before:return result
    result['semantic']=after
    summary=result.get('summary_es','')
    for item in after.get('items',[]):
        if item.get('original_model_translation'):
            summary=summary.replace(item['original_model_translation'],item['explanation_es'])
    for item in after.get('rejected_items',[]):
        summary=summary.replace(item['explanation_es'],'[Pasaje retenido para revisión: consultar la fuente literal]')
    result['summary_es']=summary
    if after.get('errors'):
        result['analysis_completeness']='PENDIENTE_PROFUNDO';result['depth']='LECTURA_LOCAL_ES_PARCIAL'
    return result
