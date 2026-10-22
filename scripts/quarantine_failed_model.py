"""Keep rejected experiments auditable while excluding them from normal results."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.db import Database
from corkjobradar.config import ROOT,now
from corkjobradar.repository import latest_analysis

db=Database();rejected=[];jobs=set()
reason='Modelo 1.5B: truncamientos y error semántico comprobado al convertir un aviso legal US/Puerto Rico en restricción de candidatura. Citas/JSON no garantizan comprensión.'
for row in db.rows("SELECT * FROM job_analyses WHERE json_extract(result,'$.model') LIKE '%1.5%'"):
    result=json.loads(row['result'])
    if result.get('model_validation')=='RECHAZADO':continue
    result['model_validation']='RECHAZADO'
    result['quality_rejection']={'reason':reason,'checked_at':now(),'evidence':'logs/ultimate-local-model-evaluation-v3-rejected.json'}
    semantic=result.get('semantic',{})
    semantic['rejected_items']=semantic.pop('items',[])
    semantic['items']=[]
    db.execute("UPDATE job_analyses SET status='REVISIÓN_MANUAL',result=? WHERE id=?",(json.dumps(result,ensure_ascii=False),row['id']))
    rejected.append(row['id']);jobs.add(row['job_id'])
for jid in jobs:
    accepted=latest_analysis(db,jid)
    db.execute('UPDATE jobs SET analysis_status=? WHERE id=?',(accepted.get('analysis_completeness','PENDIENTE'),jid))
quality={'qwen2.5-1.5b-instruct-q4_k_m.gguf':{'status':'RECHAZADO','reason':reason,'checked_at':now(),
         'evidence':['logs/ultimate-local-model-evaluation-v1-rejected.json','logs/ultimate-local-model-evaluation-v2-rejected.json','logs/ultimate-local-model-evaluation-v3-rejected.json']}}
(ROOT/'data/model-quality.json').write_text(json.dumps(quality,ensure_ascii=False,indent=2),encoding='utf-8')
db.event('MODEL_QUALITY_REJECTION',{'analysis_ids':rejected,'reason':reason,'retained':True})
print('Rejected experiments retained, hidden from normal result selection:',len(rejected))
