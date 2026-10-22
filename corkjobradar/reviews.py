"""An explicit human review may complete a draft, without filling unknown facts."""
import json
from uuid import uuid4
from .config import now


def approve_analysis(db,job_id,analysis_id,notes):
    if not notes.strip():
        raise ValueError('Anota qué has contrastado con el anuncio antes de aprobar')
    with db.transaction():
        rows=db.rows('SELECT * FROM job_analyses WHERE id=? AND job_id=?',(analysis_id,job_id))
        if not rows:
            raise ValueError('Análisis inexistente')
        row=rows[0];result=json.loads(row['result'])
        from .reading_qa import reviewed_analysis
        result=reviewed_analysis(result)
        job=db.rows('SELECT * FROM jobs WHERE id=?',(job_id,))[0]
        if row['content_hash']!=job['content_hash'] or not job['detail_complete']:
            raise ValueError('El contenido cambió o la descripción está incompleta; recuperar y reanalizar')
        if result.get('model_validation')!='VALIDADO_MUESTRA_LIMITADA' or result.get('semantic',{}).get('errors') or not result.get('semantic',{}).get('items'):
            raise ValueError('Solo se puede aprobar un borrador local validado, con citas y sin errores pendientes')
        review={'reviewed_at':now(),'notes':notes.strip(),'method':'Revisión declarada por el usuario',
                'previous_analysis_id':analysis_id,'unknown_fields_preserved':True}
        result['manual_review']=review
        result['analysis_completeness']='COMPLETO'
        version=row['analyzer_version']+':manual-review:'+uuid4().hex[:12]
        result['analyzer_version']=version
        new_id=db.execute('''INSERT INTO job_analyses(job_id,content_hash,profile_hash,analyzer_version,status,result,created_at)
            VALUES(?,?,?,?,?,?,?)''',(job_id,row['content_hash'],row['profile_hash'],version,'COMPLETO',json.dumps(result,ensure_ascii=False),now()))
        db.execute("UPDATE jobs SET analysis_status='COMPLETO' WHERE id=?",(job_id,))
        db.event('ANALYSIS_REVIEWED',{**review,'analysis_id':new_id},job_id=job_id)
    return new_id
