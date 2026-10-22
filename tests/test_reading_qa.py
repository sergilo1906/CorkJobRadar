import json
import pytest
from corkjobradar.config import ROOT
from corkjobradar.reading_qa import reviewed_reading,reviewed_analysis
from corkjobradar.translation import validate_translations


def reading(quote,spanish):
    return {'method':'TRADUCCION_INTEGRA_POR_PASAJES','items':[{'id':0,'quote':quote,'field':'duties','explanation_es':spanish}],
            'errors':[],'passages_total':1,'passages_translated':1}


def test_real_reviewed_sources_preserve_values_and_declare_correction_provenance():
    config=json.loads((ROOT/'config/reviewed_translation_spans.json').read_text(encoding='utf-8'))
    for correction in config['corrections']:
        quote=correction['source']
        original=reading(quote,'SYNTHETIC BAD ORIGINAL')
        reviewed=reviewed_reading(original)
        item=reviewed['items'][0]
        assert original['items'][0]['explanation_es']=='SYNTHETIC BAD ORIGINAL'
        assert item['translation_method']=='CORRECCION_LITERAL_REVISADA'
        assert item['original_model_translation']=='SYNTHETIC BAD ORIGINAL'
        assert item['explanation_es']==correction['spanish'] and '?' not in item['explanation_es']
        assert reviewed['passages_from_reviewed_corrections']==1
        validate_translations(json.dumps({'0':item['explanation_es']},ensure_ascii=False),[{'id':0,'text':quote}])
        assert reviewed_reading(reviewed)==reviewed


def test_unreviewed_variant_is_withheld_instead_of_inventing_a_correction():
    original=reading('Support AV deployments at another site.','Gestionar depósitos en otra sede.')
    reviewed=reviewed_reading(original)
    assert not reviewed['items'] and reviewed['passages_translated']==0
    assert reviewed['errors'][0]['reason_codes']==['DEPLOYMENT_IS_NOT_DEPOSIT']
    assert reviewed['rejected_items'][0]['quote']==original['items'][0]['quote']


def test_casual_contract_information_cannot_silently_disappear():
    original=reading('Casual Toll Operators provide cover at a different toll station.','Operadores a tiempo completo cubren otra estación.')
    reviewed=reviewed_reading(original)
    assert reviewed['errors'][0]['reason_codes']==['CASUAL_EMPLOYMENT_TYPE_LOST']


def test_primary_summary_is_corrected_and_missing_translation_stays_explicit():
    correction=json.loads((ROOT/'config/reviewed_translation_spans.json').read_text(encoding='utf-8'))['corrections'][0]
    original={'summary_es':'SYNTHETIC WRONG DEPLOYMENT','semantic':reading(correction['source'],'SYNTHETIC WRONG DEPLOYMENT')}
    fixed=reviewed_analysis(original)
    assert fixed['summary_es']==correction['spanish']
    unknown={'summary_es':'Hay depósitos.','semantic':reading('Plan AV deployments.','Hay depósitos.')}
    held=reviewed_analysis(unknown)
    assert 'depósitos' not in held['summary_es'] and held['depth']=='LECTURA_LOCAL_ES_PARCIAL'


def test_persisted_correction_appends_and_backend_refuses_unresolved_review(db,profile):
    from test_reviews import draft
    from corkjobradar.reviews import approve_analysis
    from scripts.apply_reading_corrections import apply_corrections
    jid,aid=draft(db,profile)
    row=db.rows('SELECT * FROM job_analyses WHERE id=?',(aid,))[0]
    value=json.loads(row['result']);value.update(summary_es='Hay depósitos.',depth='LECTURA_LOCAL_ES_REVISAR')
    value['semantic']=reading('Plan AV deployments.','Hay depósitos.')
    db.execute('UPDATE job_analyses SET result=? WHERE id=?',(json.dumps(value),aid))
    with pytest.raises(ValueError,match='borrador'):approve_analysis(db,jid,aid,'SYNTHETIC REVIEW')
    before=db.rows('SELECT * FROM job_analyses WHERE id=?',(aid,))[0]
    result=apply_corrections(db)
    assert len(result['changed_readings'])==1
    assert db.rows('SELECT * FROM job_analyses WHERE id=?',(aid,))[0]==before
    assert db.rows('SELECT analysis_status FROM jobs')[0]['analysis_status']=='PENDIENTE_PROFUNDO'
    assert apply_corrections(db)['changed_readings']==[]
    assert db.rows('PRAGMA foreign_key_check')==[]
