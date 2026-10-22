"""Chromium proof of final card spacing, empty action and manual links; local fixtures only."""
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now
from corkjobradar.db import Database
from scripts.check_ui_redesign_states import owned_dashboard
from scripts.check_ui_redesign import navigate,layout,idle


def main():
    from playwright.sync_api import sync_playwright,expect
    output=ROOT/'logs/ui-redesign-final-adjustments.json'
    if output.exists():raise ValueError('PRESERVE_EXISTING_PROOF')
    folder=ROOT/'data/ui-redesign/final-adjustments-verified-v2'
    folder.mkdir(parents=True,exist_ok=False)
    os.environ['PLAYWRIGHT_BROWSERS_PATH']=str(ROOT/'data/playwright-browsers')
    os.environ['TEMP']=os.environ['TMP']=str(ROOT/'data/browser-temp')
    result={'checked_at':now(),'status':'PASS','synthetic_fixtures_only':True,'external_requests':0}
    with sync_playwright() as pw:
        browser=pw.chromium.launch(args=['--disable-background-networking'])
        for kind,path in [('long',ROOT/'data/ui-redesign/additional-states-delivery/human/test.sqlite3'),('empty',ROOT/'data/ui-redesign/additional-states-final/empty.sqlite3')]:
            assert path.exists()
            with owned_dashboard(Database(path)) as origin:
                context=browser.new_context(viewport={'width':390,'height':844},service_workers='block')
                def allowed(url):
                    a=urlsplit(origin);b=urlsplit(url)
                    return a.hostname==b.hostname and a.port==b.port
                def guard(route):
                    if allowed(route.request.url):route.continue_()
                    else:result['external_requests']+=1;route.abort()
                context.route('**/*',guard)
                context.route_web_socket('**/*',lambda ws:ws.connect_to_server() if allowed(ws.url) else ws.close())
                page=context.new_page();page.goto(origin)
                page.get_by_role('heading',name='Tu próxima oportunidad IT',exact=True).wait_for(timeout=60000);idle(page)
                navigate(page,'Ofertas de empleo')
                assert not page.get_by_test_id('stException').count()
                dims=layout(page)
                assert dims['document_width']<=390 and dims['overflow_controls']==0
                if kind=='long':
                    title=page.locator('.cjr-job-title').first
                    measure=title.evaluate('(e)=>{const s=getComputedStyle(e);return {height:e.getBoundingClientRect().height,line:parseFloat(s.lineHeight),top:s.paddingTop,bottom:s.paddingBottom,clamp:s.webkitLineClamp,text_length:e.textContent.length}}')
                    assert measure['height']<=2*measure['line']+1,measure
                    assert measure['top']==measure['bottom']=='0px' and measure['clamp']=='2'
                    assert measure['text_length']>100
                    assert page.get_by_role('link',name='Abrir canal manual:',include_hidden=True).count()>0
                    result['long_title']=measure
                else:
                    expect(page.get_by_role('button',name='Iniciar o revisar búsqueda',exact=True)).to_be_visible()
                    assert page.get_by_role('textbox',name='Buscar puesto o empresa',exact=True).count()==0
                    result['empty_action_visible']=True
                page.screenshot(path=str(folder/(kind+'.png')),full_page=True)
                context.close()
        browser.close()
    assert result['external_requests']==0
    output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
