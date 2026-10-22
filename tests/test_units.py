import json
import pytest
from corkjobradar.normalization import canonical_url,normalized,salary,shifts,date_iso,category
from corkjobradar.models import Job
from corkjobradar.repository import save_job
from corkjobradar.analysis import analyze_job,extract
from corkjobradar.geography import scope_for,valid_commute
from corkjobradar.verification import evidence_status,reconcile_absences
from corkjobradar.http import validate_url
from corkjobradar.config import now
from conftest import source

def test_normalization():
    assert canonical_url('https://EXAMPLE.org/job/1/?utm_source=x&job=12#apply')=='https://example.org/job/1?job=12'
    assert normalized(' IT   Support  ')== 'it support'
    assert category('Warehouse Operative')=='Almacen'
    assert category('Localisation QA Engineer')=='IT'
    assert date_iso('2026-10-01T12:00:00Z').endswith('+01:00')
    assert date_iso(None) is None

@pytest.mark.parametrize('text,minimum,unit', [('€15.50 per hour',15.5,'hora'),('EUR 32,000-40,000 per annum',32000,'año'),('€30k / year',30000,'año'),('€15,50/hour',15.5,'hora')])
def test_salary(text,minimum,unit):
    result = salary(text)
    assert result['min']==minimum and result['unit']==unit

def test_no_invented_salary():
    assert salary('Competitive salary, 40 hours') is None
    assert salary('$30 per hour') is None
    assert shifts('Monday to Friday, rotating night shifts and on-call weekends').keys()=={'lunes_viernes','rotacion','noches','guardias','fines_semana'}

def check(profile,mode='bus',transfers=0,**extra):
    return {'origin':profile['origin_neighborhood'],'mode':mode,'transfers':transfers,'viability':'VERIFICADA',
            'evidence_url':'https://fixture.test/route-SYNTHETIC','details':json.dumps({'destination':'Synthetic location','outbound':'Synthetic outward','return':'Synthetic return',
              'shift_compatible':True,'origin_access':'Synthetic approach',**extra})}

def test_transport_rules_synthetic(profile):
    bus = check(profile)
    two = check(profile,transfers=1)
    bicycle = check(profile,mode='bicycle')
    assert valid_commute(bus,profile)
    assert not valid_commute(two,profile)
    assert valid_commute(bicycle,profile)
    job = {'location':'Little Island','mode':'ONSITE','raw':{}}
    assert scope_for(job,'Almacen',profile,[bus])[0]=='EN_ALCANCE'
    assert scope_for(job,'Almacen',profile,[two])[0]=='ACCESIBILIDAD_PENDIENTE'
    assert scope_for({'location':'Cork City'},'Almacen',profile,[bicycle])[0]=='EN_ALCANCE'
    assert scope_for({'location':'County Cork'},'Almacen',profile)[0]=='ACCESIBILIDAD_PENDIENTE'
    assert scope_for({'location':'Dublin'},'Almacen',profile)[0]=='FUERA_DE_ALCANCE'
    it_reference = check(profile,mode='car_reference',duration_minutes=58)
    scope,reason,_ = scope_for(job,'IT',profile,[it_reference])
    assert scope=='EN_ALCANCE' and 'SIN_VERIFICAR' in reason and profile['owns_car'] is False

def test_weekend_it_not_penalized(db,profile):
    source(db,'greenhouse')
    def analyze(title,text):
        job = Job(external_id=title,title=title,company='Fixture',location='Cork City',url='https://fixture.test/'+title.replace(' ','_'),
                  description=(text+' Synthetic duties and responsibilities. ')*12,detail_complete=True)
        return analyze_job(db,save_job(db,'fixture',job,profile=profile),profile)
    weekday = analyze('IT Support Weekday','Monday to Friday')
    weekend = analyze('IT Support Weekend','Weekends')
    a = next(x['points'] for x in weekday['score_explanation'] if x['criterion']=='schedule')
    b = next(x['points'] for x in weekend['score_explanation'] if x['criterion']=='schedule')
    assert a==b
    assert weekday['depth']=='ANALISIS_BASICO' and weekday['analysis_completeness']!='COMPLETO'
    assert analyze('Warehouse Weekday','Monday to Friday')['fit_score']>analyze('Warehouse Weekend','Weekends')['fit_score']

def test_dedup_conservative(db,profile):
    source(db,'greenhouse','one')
    source(db,'lever','two')
    j = Job(external_id='1',title='Warehouse Operative',company='Fixture',location='Cork City',url='https://fixture.test/official/1')
    first = save_job(db,'one',j,profile=profile)
    j.external_id='2'
    assert save_job(db,'two',j,profile=profile)==first
    j.url='https://fixture.test/official/2'
    j.external_id='3'
    assert save_job(db,'two',j,profile=profile)!=first
    assert len(db.rows('SELECT * FROM jobs'))==2
    assert len(db.rows('SELECT * FROM job_sources'))==3

def test_closed_status_signals():
    assert evidence_status({'description':'This job has been closed','raw':{}})[0]=='CLOSED_CONFIRMED'
    assert evidence_status({'description':'Vacancy visible','detail_complete':True,'raw':{}})[0]=='OPEN_LIKELY'
    assert evidence_status({'description':'','raw':{}})[0]=='UNKNOWN'

@pytest.mark.parametrize('url',['file:///C:/secret','http://127.0.0.1','http://[::1]','http://169.254.169.254','http://10.0.0.1','https://user:pass@example.org','https://linkedin.com/jobs','http://example.org:22'])
def test_unsafe_urls(url):
    with pytest.raises(ValueError):
        validate_url(url)
