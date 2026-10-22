from corkjobradar.analysis import extract,analyze_job
from corkjobradar.documentary import documentary
from corkjobradar.models import Job
from corkjobradar.repository import save_job
from conftest import source


def parse(text):
    job={'description':text,'url':'https://fixture.test/a','raw':{}}
    return documentary(job,extract(job))


def test_negations_desirable_experience_and_training_evidence():
    facts=parse('No experience required. 2 years experience desirable. Own car not required. Monday to Friday, no weekends. Full training provided. 39 hours per week.')
    assert facts['experience']['value']==0
    assert facts['desirable_experience']['value']==['2 years experience desirable.']
    assert facts['vehicle']['value'] is False
    assert 'fines_semana' not in facts['schedule']['value']
    assert facts['weekly_hours']['value']==['39 hours per week.']


def test_sections_and_every_quote_is_in_the_original():
    text='Responsibilities\nMaintain Windows computers\nResolve user incidents\nEssential requirements\nMust speak English\nPreferred qualifications\nPython is desirable\nBenefits\nPension provided'
    facts=parse(text)
    assert facts['responsibilities']['value']==['Maintain Windows computers','Resolve user incidents']
    assert facts['mandatory_requirements']['value']==['Must speak English']
    assert facts['desirable_requirements']['value']==['Python is desirable']
    for field in facts.values():
        quotes=field['quote'] or []
        if isinstance(quotes,str):quotes=[quotes]
        assert all(q in text for q in quotes)

def test_preferred_section_and_fractional_years_are_not_misclassified():
    facts=parse('Essential requirements\nAt least 0.5 years experience required\nPreferred qualifications\n2 years experience\nContract\nPermanent and fixed-term options')
    assert facts['experience']['value']==0.5
    assert facts['desirable_experience']['value']==['2 years experience']
    assert facts['contract']['value'] is None and facts['contract']['evidence_status']=='AMBIGUO'


def test_offer_and_separators_never_become_mandatory_requirements():
    text='Responsibilities\n:\nTest software.\nQualifications\n:\nNative speaker required.\nOffer:\nFully paid return travel to your home country\nIntensive training and familiarisation phase.\nSalary: €42,000 per annum.\nDiversity and Inclusion\nWe encourage candidates to apply.'
    facts=parse(text)
    assert facts['responsibilities']['value']==['Test software.']
    assert facts['mandatory_requirements']['value']==['Native speaker required.']
    assert ':' not in (facts['desirable_requirements']['value'] or [])


def test_company_description_does_not_become_job_requirement():
    facts=parse('Company Description\nOur corporate policy requires a global review.\nJob Description\nMaintain equipment.\nQualifications\nMS Excel skills.')
    assert facts['mandatory_requirements']['value']==['MS Excel skills.']


def test_company_history_and_training_benefits_are_not_candidate_experience():
    facts=parse('Company Description\nWe have 35 years experience in manufacturing.\nJob Description\nMaintain equipment.\nQualifications\nAt least 0.5 years experience required.\nBenefits\nWork with trainers who have 20 years experience.')
    assert facts['experience']['value']==0.5
    assert facts['experience']['quote']==['At least 0.5 years experience required.']


def test_company_history_cannot_override_no_experience_required():
    facts=parse('About the company\nOur team has 30 years experience.\nRequirements\nNo experience required.')
    assert facts['experience']['value']==0
    assert facts['experience']['evidence_status']=='PUBLICADO'


def test_real_unknowns_remain_partial_with_explained_score_range(db,profile):
    source(db,'html')
    job=Job(external_id='documentary',title='IT Support',url='https://fixture.test/a',location='Cork City',
            description='SYNTHETIC TEST ONLY. Responsibilities\nMaintain computers.\nEssential requirements\nAt least 2 years experience required.',detail_complete=True)
    result=analyze_job(db,save_job(db,'fixture',job,profile=profile),profile)
    from corkjobradar.analysis import VERSION
    assert result['analyzer_version'].startswith(VERSION)
    assert result['academic_review']['degree_equivalence_assumed'] is False
    assert result['depth']=='ANALISIS_BASICO' and result['analysis_completeness']=='PARCIAL_POR_DATOS'
    assert result['fit_range']['minimum']<result['fit_range']['maximum']
    assert all('reason' in row for row in result['score_explanation'])
