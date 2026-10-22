"""Real public GET only. No candidate vault imported, no authentication or POST."""
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now,load_profile,digest
from corkjobradar.http import WebClient
from corkjobradar.autoapply.platforms import inspect_greenhouse
from corkjobradar.autoapply.recruitee import inspect_recruitee


def main():
    folder=ROOT/'data/public-probes';folder.mkdir(exist_ok=True)
    stamp=now().replace(':','');calls=[];captures=[];results={}
    class Recorder:
        def __init__(self,web):self.web=web
        def get(self,url,**kwargs):
            response=self.web.get(url,**kwargs)
            sha=hashlib.sha256(response.content).hexdigest();path=folder/('external-adapter-'+sha+'.json')
            if not path.exists():path.write_bytes(response.content)
            calls.append({'url':url,'method':'GET','status':response.status_code,'sha256':sha,'file':str(path.relative_to(ROOT))})
            captures.append(response)
            return response
    profile=load_profile();profile.update(http_retries=0)
    with WebClient(profile) as web:
        recorder=Recorder(web)
        probes={
            'keeper':lambda:inspect_greenhouse('https://job-boards.greenhouse.io/keepersecurity/jobs/4418202009',recorder),
            'globetech':lambda:inspect_greenhouse('https://job-boards.eu.greenhouse.io/globetech/jobs/4960319101',recorder),
            'recruitee':lambda:inspect_recruitee('https://distilled.recruitee.com/o/snr-fe/c/new',recorder),
        }
        for name,probe in probes.items():
            try:
                result=probe();results[name]=result
                if name=='recruitee':
                    (folder/('external-adapter-recruitee-normalized-'+stamp+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            except Exception as exc:results[name]={'held':True,'error_type':type(exc).__name__,'submitted':False}
        try:
            response=recorder.get('https://api.ashbyhq.com/posting-api/job-board/netgear',check_robots=True);response.raise_for_status()
            data=response.json();posting='415ee500-8f36-4766-a9e9-a565827e52c2'
            matches=[j for j in data['jobs'] if posting in j.get('jobUrl','')]
            results['netgear_graduate']={'published_matches':len(matches),'html_form_completed':False,'submitted':False,
                'mandatory_degree_review':bool(matches and 'Level 8 honours degree' in matches[0].get('descriptionPlain',''))}
        except Exception as exc:results['netgear_graduate']={'held':True,'error_type':type(exc).__name__,'submitted':False}
    states=[]
    for response in captures:
        try:data=response.json()
        except ValueError:continue
        listings=data.get('offers') or data.get('jobs') or [] if isinstance(data,dict) else []
        for job in listings:
            states.append({'source':str(response.url),'id':job.get('id') or job.get('jobUrl'),'title':job.get('title'),
                           'content_hash':digest(job),'state':'PENDIENTE_VALIDAR_DIAGNOSTICO',
                           'reason':'Sondeo de integración documentada. No es análisis de elegibilidad ni candidatura.'})
    state_path=folder/('external-adapter-states-'+stamp+'.json')
    state_path.write_text(json.dumps(states,ensure_ascii=False,indent=2),encoding='utf-8')
    report={'checked_at':now(),'mode':'REAL_PUBLIC_GET_ONLY','calls':calls,'preserved_listing_states':len(states),
            'states_file':str(state_path.relative_to(ROOT)),'personal_data_used':False,'external_posts':0,'live_enabled':False,
            'recruitee':{k:v for k,v in results.get('recruitee',{}).items() if k not in {'fields','source_it_classification'}},
            'greenhouse_postings_observed':{k:v.get('posting_id') for k,v in results.items() if k in {'keeper','globetech'}},
            'netgear_graduate':results.get('netgear_graduate'),
            'hosted_fill_verified':False,'external_receipt_verified':False,'trial_ready':False}
    (ROOT/'logs'/('external-adapter-real-get-'+stamp+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True))


if __name__=='__main__':main()
