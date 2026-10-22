"""Read-only browser smoke against this project's locally running Streamlit server."""
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from corkjobradar.config import now


def main():
    from playwright.sync_api import sync_playwright
    temp=ROOT/'data/browser-temp';temp.mkdir(exist_ok=True)
    os.environ.update(PLAYWRIGHT_BROWSERS_PATH=str(ROOT/'data/playwright-browsers'),TEMP=str(temp),TMP=str(temp))
    blocked=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=['--disable-background-networking','--disable-breakpad'])
        context=browser.new_context(service_workers='block',accept_downloads=False)
        def guard(route):
            parsed=urlsplit(route.request.url)
            if parsed.hostname=='127.0.0.1' and parsed.port==8501 and parsed.scheme=='http':route.continue_()
            else:blocked.append(parsed.hostname);route.abort()
        context.route('**/*',guard)
        def socket_guard(ws):
            parsed=urlsplit(ws.url)
            if parsed.hostname=='127.0.0.1' and parsed.port==8501:ws.connect_to_server()
            else:ws.close()
        context.route_web_socket('**/*',socket_guard)
        page=context.new_page()
        try:
            page.goto('http://127.0.0.1:8501',wait_until='domcontentloaded')
            page.get_by_role('heading',name='Cork Job Radar',exact=True).wait_for(timeout=30000)
            page.get_by_role('tab',name='Candidaturas automáticas',exact=True).click()
            page.get_by_role('heading',name='Candidaturas automáticas — modo A',exact=True).wait_for(timeout=30000)
            page.get_by_role('button',name='PAUSAR TODO AUTOAPPLY',exact=True).wait_for()
            assert page.get_by_text('Estado actual: DESACTIVADO',exact=True).is_visible()
            assert page.get_by_text('AutoApply exclusivamente IT:',exact=False).is_visible()
            general=page.get_by_role('checkbox',name='Consultar también candidaturas ambiguas y ofertas generales excluidas',exact=True)
            assert not general.is_checked()
            result={'checked_at':now(),'url':page.url,'tab_visible':True,'pause_visible':True,'state':'DESACTIVADO',
                    'it_only_warning_visible':True,'general_jobs_default_visible':False,
                    'external_requests_blocked':len(blocked),'live_submission_enabled':False,'forms_submitted':0}
            (ROOT/'logs/autoapply-ui-browser.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
            print(json.dumps(result))
        finally:context.close();browser.close()


if __name__=='__main__':main()
