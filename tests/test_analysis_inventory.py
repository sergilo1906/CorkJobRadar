import json
from corkjobradar.audit import analysis_inventory
from corkjobradar.config import now
from corkjobradar.models import Job
from corkjobradar.repository import save_job
from conftest import source


def test_inventory_counts_current_version_once_and_distinguishes_archives_and_missing_text(db,profile):
    source(db,'html')
    def job(external,complete=True,location='Cork City'):
        return save_job(db,'fixture',Job(external_id=external,title='IT Support',location=location,url='https://fixture.test/'+external,
            description='SYNTHETIC ONLY. '*50,detail_complete=complete),profile=profile)
    reader=job('reader');missing=job('missing',False);outside=job('outside',location='Dublin');pending=job('pending')
    content=db.rows('SELECT content_hash FROM jobs WHERE id=?',(reader,))[0]['content_hash']
    for version,validation,translated in [('old','VALIDADO_MUESTRA_LIMITADA',5),('current','VALIDADO_MUESTRA_LIMITADA',10),('rejected','RECHAZADO',99)]:
        result={'depth':'LECTURA_LOCAL_ES_REVISAR','model_validation':validation,'semantic':{'passages_total':10,'passages_translated':translated}}
        db.execute('INSERT INTO job_analyses(job_id,content_hash,profile_hash,analyzer_version,status,result,created_at) VALUES(?,?,?,?,?,?,?)',
            (reader,content,'profile',version,'REVISIÓN_MANUAL',json.dumps(result),now()))
    result=analysis_inventory(db)
    assert result['all_stored_jobs']==4 and result['reconciled']
    assert result['exclusive_states']=={'LECTURA_POR_REVISAR':1,'TEXTO_INCOMPLETO':1,'ARCHIVADA_FUERA_DE_ALCANCE':1,'SIN_ANALISIS':1}
    assert result['current_reading_passages_translated']==10
    db.execute("UPDATE jobs SET content_hash='changed' WHERE id=?",(reader,))
    changed=analysis_inventory(db)
    assert changed['exclusive_states']['ANALISIS_DESACTUALIZADO']==1
    assert changed['current_reading_passages_translated']==0
