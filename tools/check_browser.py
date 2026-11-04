"""Exercise local or deployed browsing. Requires Playwright and Chromium."""
import argparse,json
from pathlib import Path
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
args=argparse.ArgumentParser();args.add_argument('--url');opts=args.parse_args()
records=json.loads((ROOT/'site/catalog.json').read_text(encoding='utf-8'))
base=opts.url or (ROOT/'site/index.html').as_uri()
out=ROOT/'previews';out.mkdir(exist_ok=True)
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True)
 context=browser.new_context(offline=not bool(opts.url),viewport={'width':1200,'height':1100})
 page=context.new_page();errors=[];bad_responses=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.on('response',lambda r:bad_responses.append((r.status,r.url)) if r.status>=400 else None)
 page.goto(base,wait_until='load')
 assert page.locator('.entry:visible').count()==len(records)
 page.screenshot(path=str(out/('live-library.png' if opts.url else 'public-library.png')))
 page.locator('[data-filter="Nuclear and radiation"]').click()
 assert page.locator('.entry:visible').count()==sum(x['category']=='Nuclear and radiation' for x in records)
 page.locator('[data-filter="Health and sanitation"]').click()
 assert page.locator('.entry:visible').count()==4
 assert page.locator('.entry:visible a.resource[target="_blank"]').count()==4
 page.locator('[data-filter="all"]').click();page.locator('#search').fill('USDA Principles')
 assert page.locator('.entry:visible').count()==1
 page.locator('#search').fill('not-a-reference-xyz');assert page.locator('#empty').is_visible()
 page.locator('#search').fill('');page.set_viewport_size({'width':390,'height':844})
 assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
 page.screenshot(path=str(out/('live-mobile.png' if opts.url else 'public-mobile.png')))
 opened=0
 for x in records:
  if x['availability']=='hosted' and x['format']=='HTML reader':
   page.goto(urljoin(base,x['href']),wait_until='load')
   assert len(page.locator('main').first.inner_text())>250
   assert not page.locator('img').evaluate_all('(imgs)=>imgs.filter(i=>!i.complete||i.naturalWidth===0).map(i=>i.src)')
   opened+=1
 assert not errors,errors
 assert not bad_responses,bad_responses
 report={'base':base,'resources':len(records),'offline_mode':not bool(opts.url),'filtering':True,'health_publisher_links':4,'mobile_layout':True,'hosted_html_readers_opened':opened,'javascript_errors':errors,'failed_responses':bad_responses}
 (out/('live-verification.json' if opts.url else 'local-verification.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps(report,indent=2))
 context.close();browser.close()
