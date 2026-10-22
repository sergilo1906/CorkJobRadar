"""Enable ONLY the limited local reading capability after the documented five-advert review."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now
from corkjobradar.semantic import PROMPT_VERSION,VALIDATION_VERSION
from corkjobradar.translation import TRANSLATION_PROMPT,validate_translations
from corkjobradar.local_model import verify_model_artifact


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--reviewed-report',required=True);args=parser.parse_args()
    path=Path(args.reviewed_report).resolve()
    if not path.is_relative_to(ROOT/'logs'):raise ValueError('Report must be a local recorded evaluation')
    report=json.loads(path.read_text(encoding='utf-8'))
    if not report.get('finished_at') or len(report['jobs'])!=5:raise ValueError('Completed five-advert review required')
    total=0;memory=0
    for job in report['jobs']:
        semantic=job['semantic']
        if semantic['prompt_version']!=TRANSLATION_PROMPT or semantic['errors'] or semantic['passages_translated']!=semantic['passages_total']:
            raise ValueError('A reviewed advert is incomplete or belongs to a different prompt')
        for item in semantic['items']:
            validate_translations(json.dumps({str(item['id']):item['explanation_es']},ensure_ascii=False),[{'id':item['id'],'text':item['quote']}])
        total+=semantic['passages_translated'];memory+=semantic.get('passages_from_verified_glossary',0)
    if total<100:raise ValueError('Insufficient actual source coverage for this declared review')
    config=json.loads((ROOT/'data/local-model-gpu/runtime_config.json').read_text(encoding='utf-8'))
    model=ROOT/config['model'];sha=verify_model_artifact(model,model.parent)
    review={'status':'VALIDADO_MUESTRA_LIMITADA','checked_at':now(),'prompt_version':PROMPT_VERSION,'validation_version':VALIDATION_VERSION,
            'capability':'ASSISTED_SPANISH_READING_WITH_SOURCE_CITATIONS','sample_jobs':len(report['jobs']),'sample_passages':total,
            'verified_glossary_passages':memory,'reviewed_by':'Development agent; not candidate consent or per-job user approval',
            'evidence':[str(path.relative_to(ROOT)),'docs/LOCAL_READER_VALIDATION.md'],
            'model_sha256':sha,'not_approved':['Unreviewed complete analysis','Autonomous candidate eligibility','Any real submission'],
            'limitations':'Limited developer-reviewed sample, terminology safeguards and complete source spans. Every production reading remains a human-review draft.'}
    destination=ROOT/'data/model-quality.json';quality=json.loads(destination.read_text(encoding='utf-8'))
    quality[model.name]=review;destination.write_text(json.dumps(quality,ensure_ascii=False,indent=2),encoding='utf-8')
    config.update(diagnostic=False,status='LIMITED_READING_VALIDATION')
    (ROOT/'config/local_model.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
    (ROOT/'logs/local-reader-validation.json').write_text(json.dumps(review,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(review,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
