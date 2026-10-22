"""Una revisión pública conservadora del inventario, sin extraer vacantes ni activar fuentes.
Ejecutar desde la raíz: .venv/Scripts/python.exe -m docs.probe_inventory
"""
import json
from corkjobradar.config import ROOT,load_profile,now
from corkjobradar.db import Database
from corkjobradar.http import WebClient,AccessBlocked
from corkjobradar.sources import upsert_source,export_sources
from bs4 import BeautifulSoup

def main():
    db=Database()
    inventory=json.loads((ROOT/'docs/research_inventory.json').read_text(encoding='utf-8'))
    evidence=[]
    profile=load_profile()
    profile['http_timeout']=15
    profile['http_retries']=0
    with WebClient(profile,db) as client:
        for item in inventory:
            status='REVISION_PENDIENTE'
            record={**item,'checked_at':now()}
            try:
                response=client.get(item['url'],check_robots=True,accept='text/html')
                soup=BeautifulSoup(response.text,'lxml')
                record.update(http_status=response.status_code,final_url=str(response.url),
                              title=soup.title.get_text(' ',strip=True) if soup.title else None)
                reason='Página accesible; conector específico/paginación y condiciones pendientes de implementar/revisar'
            except AccessBlocked as exc:
                status='BLOQUEADA_RESTRINGIDA';reason=str(exc)
                record['error']=reason
            except Exception as exc:
                status='ERROR_DE_ACCESO';reason=str(exc)[:700]
                record['error']=reason
            record['status']=status
            evidence.append(record)
            upsert_source(db,{'id':item['id'],'name':item['name'],'kind':'manual','url':item['url'],'enabled':False,
                              'permission':'PENDIENTE','status':status,'checked_at':record['checked_at'],
                              'notes':reason+'; importación manual disponible',
                              'config':{'source_class':item['type'],'discovery_url':item['url']}})
            db.execute('UPDATE sources SET status=?,checked_at=? WHERE id=?',(status,record['checked_at'],item['id']))
            print(item['id'],status,flush=True)
            (ROOT/'logs/inventory_probe.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'config/sources.yaml').write_text(export_sources(db),encoding='utf-8')

if __name__=='__main__': main()
