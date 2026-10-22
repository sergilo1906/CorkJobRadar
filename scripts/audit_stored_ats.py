"""Audit every stored job; no network, profile edits or candidate submissions."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.db import Database
from corkjobradar.config import ROOT
from corkjobradar.autoapply.opportunities import persist_inventory


def main():
    report,path=persist_inventory(Database())
    result={k:v for k,v in report.items() if k!='offers'}
    result['inventory_path']=str(path.relative_to(ROOT))
    (ROOT/'logs/external-adapter-stored-ats.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='companies'}))


if __name__=='__main__':main()
