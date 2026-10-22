import json
import httpx
import pytest
from corkjobradar.semantic import validate_interpretation,chunks,local_analysis
from corkjobradar.models import Job
from corkjobradar.repository import save_job,unpack_job
from conftest import source


def test_rejects_invented_quote_and_numbers():
    text='At least 2 years experience required.'
    payload={'items':[{'field':'mandatory','explanation_es':'Exige 5 años.','quote':text}],'unknown_fields':[]}
    with pytest.raises(ValueError,match='cifras'):
        validate_interpretation(json.dumps(payload),text)


def test_generic_label_cannot_pass_as_translation_of_real_work():
    text='Setting up and maintaining a Training Record Matrix for Production personnel.'
    payload={'items':[{'field':'duties','explanation_es':'Tareas de trabajo','quote':text}],'unknown_fields':[]}
    with pytest.raises(ValueError,match='genérica'):
        validate_interpretation(json.dumps(payload),text)
    payload['items'][0].update(explanation_es='Exige experiencia.',quote='Invented job facts')
    with pytest.raises(ValueError,match='literal'):
        validate_interpretation(json.dumps(payload),text)

def test_rejects_desirable_as_mandatory_and_skills_as_employer_training():
    payload={'items':[{'field':'training','explanation_es':'Debe conocer SAP.','quote':'SAP experience is desirable.'}],'unknown_fields':[]}
    with pytest.raises(ValueError,match='deseable'):
        validate_interpretation(json.dumps(payload),'SAP experience is desirable.')
    payload['items'][0]['field']='desirable'
    with pytest.raises(ValueError,match='deseable'):
        validate_interpretation(json.dumps(payload),'SAP experience is desirable.')

def test_category_repaired_from_explicit_preference_or_qualification():
    text='Qualifications\nAdvanced MS Word and Excel skills.\nSAP experience is desirable.'
    payload={'items':[{'field':'training','explanation_es':'Habilidades avanzadas de Word y Excel.','quote':'Advanced MS Word and Excel skills.'},
                      {'field':'mandatory','explanation_es':'Se valora experiencia en SAP.','quote':'SAP experience is desirable.'}],'unknown_fields':[]}
    out=validate_interpretation(json.dumps(payload),text)
    assert [i['field'] for i in out['items']]==['tools','desirable']

def test_corporate_legal_footer_is_retained_without_becoming_job_requirement():
    from corkjobradar.semantic import model_text
    before='SYNTHETIC ONLY. Job in Cork.\n'
    footer='AbbVie is an equal opportunity employer. US & Puerto Rico only https://www.abbvie.com/join-us/equal-employment-opportunity-employer.html'
    core,retained=model_text({'company':'AbbVie','url':'https://jobs.smartrecruiters.com/AbbVie/test','description':before+footer})
    assert core==before and core+retained[0]['text']==before+footer
    assert retained[0]['classification']=='AVISO_LEGAL_CORPORATIVO_CONSERVADO'


def test_chunks_cover_every_character():
    text=('SYNTHETIC only ' * 2003)+'FINAL'
    assert ''.join(t for _,t in chunks(text))==text

def test_citations_use_actual_passage_text_and_reject_nonexistent_id():
    from corkjobradar.semantic import materialize_citations
    passages=[{'id':0,'text':'SYNTHETIC ONLY. Full training provided.'}]
    data={'items':[{'field':'training','explanation_es':'Se proporciona formación completa.','passage_id':0}],'unknown_fields':[]}
    result=json.loads(materialize_citations(json.dumps(data),passages))
    assert result['items'][0]['quote']==passages[0]['text']
    data['items'][0]['passage_id']=999
    with pytest.raises(ValueError,match='inexistente'):
        materialize_citations(json.dumps(data),passages)


def test_each_chunk_is_processed_and_cached(db,profile):
    source(db,'html')
    text=('Maintain computers. '*200)+('Support users. '*260)+('Document incidents. '*40)
    jid=save_job(db,'fixture',Job(external_id='model',title='IT Support',location='Cork City',url='https://fixture.test/a',description=text,detail_complete=True),profile=profile)
    job=unpack_job(db.rows('SELECT * FROM jobs WHERE id=?',(jid,))[0]);calls=[]
    def handler(r):
        calls.append(r)
        quote=json.loads(json.loads(r.content)['messages'][1]['content'])['advert_fragment'][:40]
        payload={'explanation_es':'Mantener los ordenadores.','quote':quote}
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(payload)}}]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result=local_analysis(db,job,client)
        assert result['chunks_total']==result['chunks_validated'] and result['characters_total']==len(text)
        assert 1<=len(calls)<=result['chunks_total']
        previous_calls=len(calls)
        cached=local_analysis(db,job,client)
        assert cached['chunks_cached']==result['chunks_total'] and len(calls)==previous_calls

def test_sse_reassembled_and_cancel_closes_response(db):
    from corkjobradar.semantic import generate
    from corkjobradar.worker import create_run
    events=[{'choices':[{'delta':{'content':'{"ok":'},'finish_reason':None}]},
            {'choices':[{'delta':{'content':'true}'},'finish_reason':'stop'}]}]
    data=''.join('data: '+json.dumps(e)+'\n\n' for e in events)+'data: [DONE]\n\n'
    class Stream(httpx.SyncByteStream):
        closed=False
        def __iter__(self):
            yield data.encode()
        def close(self):self.closed=True
    streams=[]
    def handler(r):
        s=Stream();streams.append(s)
        return httpx.Response(200,headers={'Content-Type':'text/event-stream'},stream=s)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result=generate(client,{})
        assert result['choices'][0]['message']['content']=='{"ok":true}' and streams[-1].closed
        rid=create_run(db,kind='deep');db.execute('UPDATE scan_runs SET cancel_requested=1 WHERE id=?',(rid,))
        with pytest.raises(InterruptedError,match='Cancelación'):
            generate(client,{},db,rid)
        assert streams[-1].closed
