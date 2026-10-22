"""Reproducible public metadata probe: fixed endpoint, robots checked, GET only."""
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.http import WebClient
from corkjobradar.config import ROOT,load_profile,now,digest


def main():
    url='https://distilled.recruitee.com/api/offers'
    profile=load_profile();profile.update(http_retries=0,domain_interval_seconds=0)
    stamp=now().replace(':','')
    report={'checked_at':now(),'url':url,'method':'GET','submitted':False,'personal_data_used':False,
            'adapter_implemented':False,'live_enabled':False}
    try:
        with WebClient(profile) as web:
            response=web.get(url,check_robots=True);response.raise_for_status();data=response.json()
        report.update(status=response.status_code,sha256=hashlib.sha256(response.content).hexdigest(),
                      top_level_keys=list(data) if isinstance(data,dict) else [])
        if isinstance(data,dict) and isinstance(data.get('offers'),list):
            folder=ROOT/'data/public-probes';folder.mkdir(exist_ok=True)
            raw_file=folder/('recruitee-'+stamp+'.json')
            raw_file.write_bytes(response.content)
            index_file=folder/('recruitee-'+stamp+'-states.json')
            index_file.write_text(json.dumps({'source_url':url,'checked_at':now(),'sha256':report['sha256'],
                'search_run':False,'offers':[{'id':offer.get('id'),'url':offer.get('careers_url'),
                    'content_hash':digest(offer),'state':'PENDIENTE_VALIDAR_DIAGNOSTICO',
                    'reason':'Captura de API para evaluar un adaptador; sin analizar elegibilidad ni autorizar candidatura.'}
                    for offer in data['offers']]},ensure_ascii=False,indent=2),encoding='utf-8')
            report.update(published_offer_count=len(data['offers']),offer_schema_keys=sorted(data['offers'][0]) if data['offers'] else [],
                          questions_exposed=any('open_questions' in o for o in data['offers']),eligibility_evaluated=False,
                          public_snapshot=str(raw_file.relative_to(ROOT)),offer_states_file=str(index_file.relative_to(ROOT)))
        report['limitation']='GET publico solamente; permiso, adaptador y recepcion pendientes. No se guardan ofertas en produccion.'
    except Exception as exc:report.update(blocked=True,error_type=type(exc).__name__)
    (ROOT/'logs'/('verified-flow-recruitee-recheck-'+stamp+'.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__':main()
