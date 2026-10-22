"""Read-only Chromium audit of six screens and every additional menu. No external browsing."""
import argparse
import json
import os
from pathlib import Path
import sys
from time import monotonic
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT,now
from corkjobradar.ui.visibility import PAGES

SIZES=((1920,1080),(1440,900),(1280,720),(768,1024),(390,844))
HEADINGS=dict(zip(PAGES,['Tu próxima oportunidad IT',*PAGES[1:]]))


def idle(page):
    # Allow the browser's widget event to reach Streamlit before inspecting its state.
    page.wait_for_timeout(200)
    page.wait_for_function("() => document.querySelector('[data-test-script-state]')?.getAttribute('data-test-script-state') === 'notRunning'",timeout=60000)
    page.wait_for_timeout(180)


def navigate(page,name):
    sidebar=page.get_by_test_id('stSidebar')
    if page.viewport_size['width']<1000:
        select(page,'Ir a sección',name)
    else:
        bounds=sidebar.bounding_box()
        if not bounds or bounds['x']<0 or bounds['width']==0:page.get_by_test_id('stExpandSidebarButton').click()
        sidebar.get_by_text(name,exact=True).click()
    page.get_by_role('heading',name=HEADINGS[name],exact=True).wait_for(timeout=60000)
    idle(page)


def select(page,label,value):
    page.get_by_test_id('stSelectbox').filter(has=page.get_by_text(label,exact=True)).get_by_role('combobox').click()
    page.get_by_role('option',name=value,exact=True).click()
    idle(page)


def layout(page):
    return page.evaluate('''() => {
      const main=document.querySelector('[data-testid="stMain"]');
      const bad=[...document.querySelectorAll('button,input,select,textarea')].filter(el=>{
        const r=el.getBoundingClientRect(),s=getComputedStyle(el);
        return r.width>0 && r.top<innerHeight && r.bottom>0 && s.visibility!=='hidden' && !el.closest('[data-testid="stSidebar"]') && (r.left< -2 || r.right>innerWidth+2);
      });
      return {viewport:innerWidth,document_width:document.documentElement.scrollWidth,main_width:main.clientWidth,main_scroll:main.scrollWidth,overflow_controls:bad.length};
    }''')


def contrast(page):
    return page.evaluate('''() => {
      const parse=s=>(s.match(/[\\d.]+/g)||[]).map(Number);
      const blend=(c,b)=>c.slice(0,3).map((x,i)=>x*(c[3]??1)+b[i]*(1-(c[3]??1)));
      const lum=c=>c.map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
      const bg=e=>{let chain=[];for(let n=e;n;n=n.parentElement)chain.push(n);return chain.reverse().reduce((b,n)=>blend(parse(getComputedStyle(n).backgroundColor),b),[255,255,255]);};
      let ratios=[];
      for(const el of document.querySelectorAll('h1,h2,h3,p,label,button,a,dt,dd')) {
        const r=el.getBoundingClientRect(),s=getComputedStyle(el);
        if(!r.width || !r.height || r.top>innerHeight || r.bottom<0 || s.visibility==='hidden' || el.closest('[data-testid="stSidebar"]') && innerWidth<1000)continue;
        if(el.matches('button:disabled') || el.closest('button:disabled') || !el.textContent.trim())continue;
        const b=bg(el),f=blend(parse(s.color),b),a=lum(f),c=lum(b),ratio=(Math.max(a,c)+.05)/(Math.min(a,c)+.05);
        const large=parseFloat(s.fontSize)>=24 || parseFloat(s.fontSize)>=18.66 && parseInt(s.fontWeight)>=700;
        const icon=el.matches('button') && el.querySelector('[data-testid="stIconMaterial"]') && el.textContent.trim()===el.querySelector('[data-testid="stIconMaterial"]').textContent.trim();
        ratios.push({tag:el.tagName,ratio:Math.round(ratio*100)/100,minimum:large||icon?3:4.5});
      }
      return {samples:ratios.length,failures:ratios.filter(r=>r.ratio+.02<r.minimum),lowest:Math.min(...ratios.map(r=>r.ratio))};
    }''')


def audit(origin,folder,*,subscreens=True):
    from playwright.sync_api import sync_playwright
    os.environ['PLAYWRIGHT_BROWSERS_PATH']=str(ROOT/'data/playwright-browsers')
    temp=ROOT/'data/browser-temp';temp.mkdir(exist_ok=True)
    os.environ['TEMP']=os.environ['TMP']=str(temp)
    folder=Path(folder).resolve()
    if not folder.is_relative_to(ROOT/'data'):raise ValueError('PROJECT_SCREENSHOT_PATH_REQUIRED')
    folder.mkdir(parents=True,exist_ok=False)
    refused=[];records=[];extra=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=['--disable-background-networking'])
        context=browser.new_context(viewport={'width':1440,'height':900},service_workers='block')
        def allowed(url):
            a=urlsplit(origin);b=urlsplit(url)
            return b.hostname==a.hostname and b.port==a.port
        def guard(route):
            if allowed(route.request.url):route.continue_()
            else:refused.append(True);route.abort()
        context.route('**/*',guard)
        context.route_web_socket('**/*',lambda ws:ws.connect_to_server() if allowed(ws.url) else ws.close())
        page=context.new_page();page.goto(origin,wait_until='domcontentloaded')
        page.get_by_role('heading',name=HEADINGS[PAGES[0]],exact=True).wait_for(timeout=60000);idle(page)
        for width,height in SIZES:
            page.set_viewport_size({'width':width,'height':height})
            page.wait_for_timeout(500)
            for i,name in enumerate(PAGES):
                start=monotonic();navigate(page,name)
                assert not page.get_by_test_id('stException').count(),name
                page.get_by_test_id('stMain').evaluate('(e)=>e.scrollTop=0')
                bounds=layout(page);colors=contrast(page)
                assert bounds['document_width']<=width+2 and bounds['main_scroll']<=bounds['main_width']+2,bounds
                assert not bounds['overflow_controls'],bounds
                # Only selected CV/copy steps ever contain private content; mask before writing.
                filename=f'{width}-{i}.png'
                page.screenshot(path=str(folder/filename),mask=[page.locator('[data-testid="stText"],[data-testid="stCode"],[data-testid="stJson"]')])
                records.append({'page':name,'size':[width,height],'seconds':round(monotonic()-start,2),'layout':bounds,'contrast':colors,'screenshot':filename})
        if subscreens:
            page.set_viewport_size({'width':1440,'height':900})
            page.wait_for_timeout(500)
            for name,label,values in [
                (PAGES[4],'Ver actividad',['Historial de búsquedas','Fuentes e importación','Cobertura del descubrimiento','Exportar informes','Avanzado']),
                (PAGES[5],'Sección de configuración',['Datos y experiencia aprobados','Preferencias IT y ubicación','Frecuencia y notificaciones','Política de candidaturas','Privacidad','Sistema avanzado'])]:
                navigate(page,name)
                for k,value in enumerate(values):
                    select(page,label,value)
                    assert not page.get_by_test_id('stException').count(),value
                    page.get_by_test_id('stMain').evaluate('(e)=>e.scrollTop=0')
                    filename=f'extra-{PAGES.index(name)}-{k}.png'
                    page.screenshot(path=str(folder/filename),mask=[page.locator('[data-testid="stText"],[data-testid="stCode"],[data-testid="stJson"]')])
                    extra.append({'page':name,'section':value,'screenshot':filename})
            navigate(page,PAGES[3]);page.get_by_text('Mostrar herramientas avanzadas de AutoApply',exact=True).click();idle(page)
            for k,value in enumerate(['Formularios y ensayo controlado','Compatibilidad de plataformas','Diagnóstico de bloqueos','Contraste documental','Simulación y auditoría histórica']):
                select(page,'Herramienta avanzada',value)
                assert not page.get_by_test_id('stException').count(),value
                page.get_by_test_id('stMain').evaluate('(e)=>e.scrollTop=0')
                filename=f'extra-3-{k}.png';page.screenshot(path=str(folder/filename),mask=[page.locator('[data-testid="stText"],[data-testid="stCode"],[data-testid="stJson"]')])
                extra.append({'page':PAGES[3],'section':value,'screenshot':filename})
        context.close();browser.close()
    failures=sum(len(r['contrast']['failures']) for r in records)
    return {'checked_at':now(),'status':'PASS' if not failures else 'FAIL','records':records,'subscreens':extra,'external_requests_allowed':False,'blocked_requests':len(refused),'private_content_masked':True,'screenshots':str(folder.relative_to(ROOT)),'live_enabled':False}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--origin',default='http://127.0.0.1:8501');parser.add_argument('--label',required=True);args=parser.parse_args()
    if not args.label.replace('-','').isalnum():raise ValueError('SAFE_LABEL_REQUIRED')
    report=ROOT/'logs'/('ui-redesign-'+args.label+'.json')
    if report.exists():raise ValueError('PRESERVE_PREVIOUS_REPORT')
    result=audit(args.origin,ROOT/'data/ui-redesign'/args.label)
    report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':result['status'],'screens':len(result['records']),'subscreens':len(result['subscreens']),'contrast_failures':sum(len(r['contrast']['failures']) for r in result['records'])}))
    if result['status']!='PASS':raise SystemExit(1)


if __name__=='__main__':main()
