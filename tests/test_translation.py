import json
import pytest
from corkjobradar.passages import source_passages
from corkjobradar.translation import validate_translations,batches,translation_schema


def test_all_characters_preserved_with_headings_and_offer_boundary():
    text='Qualifications\n:\nNative speaker of the language required.\nOffer:\nIntensive training and familiarisation phase.\nFully paid return travel to your home country\nDiversity and Inclusion\nWe encourage candidates to apply.\n'
    passages,retained=source_passages(text)
    spans=sorted([*passages,*retained],key=lambda p:p['offset'])
    assert ''.join(p['text'] for p in spans)==text
    native=next(p for p in passages if 'Native speaker' in p['text'])
    training=next(p for p in passages if 'Intensive training' in p['text'])
    travel=next(p for p in passages if 'Fully paid' in p['text'])
    assert native['requirement_level']=='mandatory'
    assert training['field']=='training' and training['requirement_level']=='not_requirement'
    assert travel['field']=='benefits' and travel['requirement_level']=='not_requirement'
    assert any(p['kind']=='SEPARATOR' and p['text']==':\n' for p in retained)


def test_training_records_are_duties_not_training_offered():
    text='Responsibilities\nSetting up and maintaining a Training Record Matrix for Production personnel.\n'
    passages,_=source_passages(text)
    assert passages[0]['field']=='duties' and 'training' not in passages[0]['facets']


@pytest.mark.parametrize('bad',[
 {'0':'Tareas de trabajo'},
 {'0':'Funciones'},
 {},
 {'0':'Mantener los registros.','1':'Inventado'},
 {'0':'Maintain records of staff training and keep them up to date.'},
])
def test_generic_incomplete_missing_or_untranslated_outputs_rejected(bad):
    p=[{'id':0,'text':'Maintain records of staff training and keep them up to date.'}]
    with pytest.raises(ValueError):validate_translations(json.dumps(bad),p)


@pytest.mark.parametrize('source,translation',[
 ('No experience required.','Se requiere experiencia.'),
 ('Salary €42,000 per annum.','Salario de 45,000 dólares anuales.'),
 ('No weekends required.','Se trabaja los fines de semana.'),
])
def test_negations_and_numbers_are_not_discarded(source,translation):
    with pytest.raises(ValueError):validate_translations(json.dumps({'0':translation}),[{'id':0,'text':source}])


def test_number_format_can_be_restored_but_value_count_and_order_never_change():
    from corkjobradar.translation import restore_number_format
    assert restore_number_format('Salario 42.000 EUR anuales.','Salary 42,000 EUR per annum.')=='Salario 42,000 EUR anuales.'
    assert restore_number_format('Experiencia: 0,5 años.','Experience: 0.5 years.')=='Experiencia: 0.5 años.'
    assert restore_number_format('Proceso P2P preciso.','Accurate purchase to pay process.')=='Proceso P2P preciso.'
    for target,original in [('15 hours','1.5 hours'),('2 years, 12 months','12 years, 2 months'),('2 years','2 years and 2 months')]:
        with pytest.raises(ValueError):restore_number_format(target,original)


def test_irish_qualification_is_never_renamed_as_another_certificate():
    p=[{'id':0,'text':'A Leaving Certificate or equivalent is required.'}]
    with pytest.raises(ValueError,match='CREDENTIAL'):
        validate_translations(json.dumps({'0':'Se requiere un certificado de abandono o equivalente.'}),p)


def test_software_name_cannot_be_translated_as_a_warehouse():
    source='Responsible for ensuring Day to Day Running of Systems ie (One Vault).'
    with pytest.raises(ValueError,match='SYSTEM_NAME'):
        validate_translations(json.dumps({'0':'Responsable del funcionamiento diario de los sistemas, es decir, un almacén.'}),[{'id':0,'text':source}])


def test_schema_requires_every_id_and_batches_never_truncate():
    passages,_=source_passages('Responsibilities\n'+('Maintain equipment and document incidents.\n'*37))
    grouped=list(batches(passages,max_characters=130,max_units=3))
    assert [p['id'] for b in grouped for p in b]==list(range(37))
    assert translation_schema(grouped[0])['required']==[str(p['id']) for p in grouped[0]]
    good={'0':'Mantener los registros de formación del personal y mantenerlos actualizados.'}
    result=validate_translations(json.dumps(good),[{'id':0,'text':'Maintain records of staff training and keep them up to date.'}])
    assert result[0]['quote']=='Maintain records of staff training and keep them up to date.'


def test_all_passages_persist_and_cache_without_inference_on_retry(db,profile):
    import httpx
    from conftest import source
    from corkjobradar.models import Job
    from corkjobradar.repository import save_job
    from corkjobradar.translation import translate_job
    source(db,'html')
    jid=save_job(db,'fixture',Job(external_id='translate',title='Synthetic only',url='https://fixture.test/trans',
        description='Responsibilities\n'+('Clean equipment and document every production step.\n'*13),detail_complete=True),profile=profile)
    job=db.rows('SELECT * FROM jobs WHERE id=?',(jid,))[0];calls=[]
    def handler(request):
        payload=json.loads(request.content);passages=json.loads(payload['messages'][1]['content'])['passages'];calls.append(passages)
        content={key:'Limpiar los equipos y documentar cada paso de producción.' for key in passages}
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(content)}}]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result=translate_job(db,job,client)
        assert result['passages_translated']==result['passages_total']==13 and result['errors']==[]
        assert [p['id'] for p in result['items']]==list(range(13))
        before=len(calls);again=translate_job(db,job,client)
        assert len(calls)==before and again['batches_cached']==3


def test_failed_batch_does_not_discard_other_passages(db,profile):
    import httpx
    from conftest import source
    from corkjobradar.models import Job
    from corkjobradar.repository import save_job
    from corkjobradar.translation import translate_job
    source(db,'html')
    jid=save_job(db,'fixture',Job(external_id='partial-trans',title='Synthetic only',url='https://fixture.test/partial-trans',
        description='Responsibilities\n'+('Clean equipment and document every production step.\n'*13)),profile=profile)
    job=db.rows('SELECT * FROM jobs WHERE id=?',(jid,))[0]
    def handler(request):
        passages=json.loads(json.loads(request.content)['messages'][1]['content'])['passages']
        content={key:'Limpiar los equipos y documentar cada paso de producción.' for key in passages} if '0' not in passages else {}
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(content)}}]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:result=translate_job(db,job,client)
    assert result['passages_translated']==8 and result['passages_total']==13
    assert result['errors'][0]['passage_ids']==[0,1,2,3,4] and result['status']=='PROFUNDO_PARCIAL'
