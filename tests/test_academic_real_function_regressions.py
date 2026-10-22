"""Minimal literal excerpts from public jobs already stored, read 22/10/2026.

NETGEAR: https://jobs.ashbyhq.com/netgear/415ee500-8f36-4766-a9e9-a565827e52c2
WatchGuard: https://jobs.lever.co/watchguard/5217e4e4-2cdc-425c-8003-b56a445f1cd9
Synthetic counterexamples test safety, not job availability or receipt.
"""
import pytest
from corkjobradar.autoapply.it_scope import classify_it_functions
from corkjobradar.autoapply.broad_selection import experience_requirements
from corkjobradar.ui.model import filter_jobs


@pytest.mark.parametrize('title,quote,family',[
    ('Graduate Mobile Software Engineer','Building features in our native Android (Kotlin) and iOS (Swift) applications, from ticket to release.','SOFTWARE_DEVELOPMENT'),
    ('CyberSecurity Technician (SOC)','Investigate and contain cyber security threats','CYBERSECURITY'),
])
def test_real_function_phrasing_has_literal_evidence_not_just_employer_or_title(title,quote,family):
    job={'title':title,'description':'Responsibilities\n'+quote,'category':'IT','detail_complete':True}
    result=classify_it_functions(job)
    assert result.status=='CONFIRMED_IT' and family in result.families
    assert result.evidence[0]['quote']==quote
    job['description']='Responsibilities\nSYNTHETIC: Work as a team and communicate well.'
    assert classify_it_functions(job).status!='CONFIRMED_IT'


@pytest.mark.parametrize('title,quote,category',[
    ('Warehouse Operative','Building features in native Android applications.','Almacen'),
    ('Support Assistant','Investigate physical security threats.','Otros'),
    ('Production Technician','Writing production reports and building workbenches.','Produccion'),
    ('Junior Support Technician','Excellent IT skills and computer literacy are required.','IT'),
])
def test_new_phrasing_does_not_make_non_it_or_unproven_roles_eligible(title,quote,category):
    assert classify_it_functions({'title':title,'description':quote,'category':category,'detail_complete':True}).status!='CONFIRMED_IT'


def test_required_network_engineering_years_are_work_experience_not_degree_duration():
    job={'description':'Required Qualifications\n4+ years in enterprise network engineering.'}
    assert experience_requirements(job)[0]['excludes']
    job['description']='Required Qualifications\n4 year degree in network engineering.'
    assert not experience_requirements(job)


def test_pending_it_filter_never_mixes_unconfirmed_with_confirmed_opportunities():
    base={'company':'SYNTHETIC','title':'Junior Support Technician','location_label':'Ubicación pendiente','families':[],'mode':'DESCONOCIDO','open_status':'UNKNOWN','potential':False,'it_status':'AMBIGUOUS','pending_it_review':True}
    assert not filter_jobs([base],scope='Oportunidades IT')
    assert filter_jobs([base],scope='IT por confirmar')==[base]
    assert not filter_jobs([base],query='missing',scope='IT por confirmar')
