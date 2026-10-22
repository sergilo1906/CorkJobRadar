"""Registro JSON local sin datos de CV ni contenido completo de los anuncios."""
import json
import re
from .config import now

def log_event(db_path, event, **fields):
    path=db_path.with_suffix('.jsonl')
    item={'at':now(),'event':event,**fields}
    for key,value in item.items():
        if isinstance(value,str):
            item[key]=re.sub(r'(?i)(api[_-]?key|token|password|authorization)([=: ]+)[^\s&]+',r'\1\2[REDACTED]',value)
    with path.open('a',encoding='utf-8') as stream:
        stream.write(json.dumps(item,ensure_ascii=False)+'\n')
