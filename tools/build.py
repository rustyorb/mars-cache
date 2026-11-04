"""Build MARS CACHE's public site from an existing private/local collection.

Usage: python tools/build.py --collection /path/to/MARS-CACHE
No credentials or private source snapshots are copied into the public repository.
"""
import argparse,hashlib,json,re,shutil,csv,io,zipfile
from collections import defaultdict,Counter
from pathlib import Path
from html import escape as esc
from urllib.parse import urlparse,unquote
import sys

ROOT=Path(__file__).resolve().parents[1]
ORDER=['Water and immediate preparedness','Nuclear and radiation','Health and sanitation','Maps and navigation','Growing food','Preserving food','Tools and power','Communications']
PDF_PUBLISHERS={'CDC','US Geological Survey','USDA / National Center for Home Food Preservation','USDA Forest Service','FEMA','FEMA / HHS REMM'}
HTML_PUBLISHERS={'National Weather Service','US EPA'}
SITE_URL='https://rustyorb.github.io/mars-cache/'
REPO_URL='https://github.com/rustyorb/mars-cache'
VERSION='v0.1.0'
ARCHIVE='MARS-CACHE-Public-Offline-Core-v0.1.0.zip'
DOWNLOAD=f'{REPO_URL}/releases/download/{VERSION}/{ARCHIVE}'

def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def natural(s):return [int(x) if x.isdigit() else x.lower() for x in re.split('(\\d+)',s)]
def size(n):return f'{n/1024/1024:.1f} MiB' if n>=1024*1024 else f'{n/1024:.0f} KiB'
def slug(s):return re.sub('[^a-z]+','-',s.lower()).strip('-')

def run(collection):
 sys.path.insert(0,str(collection/'tools/vendor'))
 from bs4 import BeautifulSoup
 original=json.loads((collection/'catalog.json').read_text(encoding='utf-8'))
 records=[];sources={}
 for x in original:
  if x['status']!='collected' or x['publisher']=='Hesperian Health Guides':continue
  hosted=(x['format']=='PDF' and x['publisher'] in PDF_PUBLISHERS) or (x['format']=='HTML reader' and x['publisher'] in HTML_PUBLISHERS)
  item={k:x[k] for k in ['id','title','group','category','publisher','edition','audience','source_page','url','retrieved_utc']}
  item.update(availability='hosted' if hosted else 'publisher',format=x['format'],pages=x.get('pages'),bytes=x.get('bytes'),description=x.get('notes',''))
  item['href']=x['local_path'] if hosted else x['url']
  if hosted:item['source_sha256']=x['sha256']
  sources[x['id']]=x;records.append(item)
 for title in ['Where There Is No Doctor','New Where There Is No Doctor','Where There Is No Dentist','A Community Guide to Environmental Health']:
  sample=next(x for x in original if x.get('group')==title and x['status']=='collected')
  records.append(dict(id=hashlib.sha256(title.encode()).hexdigest()[:12],title=title,group='Hesperian health guides',category='Health and sanitation',publisher='Hesperian Health Guides',edition=sample['edition'],audience='Health reference',source_page='https://languages.hesperian.org/pages/en/pdf.html',url='https://languages.hesperian.org/pages/en/pdf.html',href='https://languages.hesperian.org/pages/en/pdf.html',availability='publisher',format='Publisher chapter downloads',pages=None,bytes=None,description='Obtain chapter PDFs directly from the publisher for your personal offline collection. Digital redistribution requires publisher permission.'))
 site=ROOT/'site';site.mkdir(exist_ok=True)
 private_lookup={(collection/x['local_path']).resolve():x for x in original if x.get('local_path')}
 public_lookup={x['id']:x for x in records}
 for item in records:
  if item['availability']!='hosted':continue
  x=sources[item['id']];src=collection/x['local_path'];dst=site/x['local_path']
  dst.parent.mkdir(parents=True,exist_ok=True)
  if x['format']=='PDF':shutil.copy2(src,dst)
  else:
   soup=BeautifulSoup(src.read_text(encoding='utf-8'),'html.parser')
   for a in soup.select('a[href]'):
    href=a['href'];parsed=urlparse(href)
    if parsed.scheme or not parsed.path:continue
    target=(src.parent/unquote(parsed.path)).resolve()
    if target.is_relative_to(collection/'sources'):
     a.decompose();continue
    if target in private_lookup:
     source_item=private_lookup[target];public=public_lookup.get(source_item['id'])
     if public and public['availability']=='hosted':
      import os
      a['href']=os.path.relpath(site/public['href'],dst.parent).replace('\\','/')
     else:a['href']=source_item['url']
   for img in soup.select('img[src]'):
    u=img['src']
    if urlparse(u).scheme:raise ValueError('Unexpected remote embedded image')
    source=(src.parent/unquote(u)).resolve()
    if not source.is_relative_to(collection/'library/assets'):raise ValueError('Unexpected asset path')
    dest=site/source.relative_to(collection);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
   for a in soup.select('a[href]'):
    if a['href'].startswith(('http://','https://')):a['target']='_blank';a['rel']='noopener noreferrer'
   dst.write_text(str(soup),encoding='utf-8',newline='\n')
  item['hosted_sha256']=digest(dst)
 records.sort(key=lambda x:(ORDER.index(x['category']),x['group'],natural(x['title'])))
 (ROOT/'data/catalog.json').write_text(json.dumps(records,indent=2,ensure_ascii=False),encoding='utf-8',newline='\n')
 (site/'catalog.json').write_text(json.dumps(records,indent=2,ensure_ascii=False),encoding='utf-8',newline='\n')
 with (site/'catalog.csv').open('w',encoding='utf-8-sig',newline='') as f:
  fields=['title','category','publisher','edition','availability','href','source_page','retrieved_utc','hosted_sha256']
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore',lineterminator='\n');w.writeheader();w.writerows(records)
 groups=defaultdict(list)
 for x in records:groups[(x['category'],x['group'])].append(x)
 blocks=[]
 for cat in ORDER:
  sections=[]
  for (c,g),items in groups.items():
   if c!=cat:continue
   rows=[]
   for x in items:
    local=x['availability']=='hosted'
    info=('Saved in this library' if local else 'Publisher download · internet needed')+' · '+x['publisher']
    if local and x.get('pages'):info+=f" · {x['pages']} pages"
    if local and x.get('bytes'):info+=' · '+size(x['bytes'])
    keywords=' '.join(str(x.get(k,'')) for k in ['title','group','category','publisher','audience','description']).lower()
    attrs='' if local else ' target="_blank" rel="noopener noreferrer"'
    rows.append(f"<li class='entry' data-search='{esc(keywords,quote=True)}'><div><a class='resource' href='{esc(x['href'],quote=True)}'{attrs}>{esc(x['title'])}</a><p>{esc(info)}</p></div><details><summary>Source</summary><p>{esc(x['publisher'])}<br>{esc(x['edition'])}<br>{esc(x['audience'])}<br><a href='{esc(x['source_page'],quote=True)}' target='_blank' rel='noopener noreferrer'>Original publisher</a></p></details></li>")
   sections.append(f"<section class='group'><h3>{esc(g)} <span>{len(items)}</span></h3><ul>{''.join(rows)}</ul></section>")
  count=sum(x['category']==cat for x in records)
  blocks.append(f"<section class='category' data-category='{esc(cat,quote=True)}' id='{slug(cat)}'><div class='category-title'><h2>{esc(cat)}</h2><span>{count} resources</span></div>{''.join(sections)}</section>")
 chips="<button class='chip active' type='button' data-filter='all' aria-pressed='true'>Everything</button>"+''.join(f"<button class='chip' type='button' data-filter='{esc(c,quote=True)}' aria-pressed='false'>{esc(c)}</button>" for c in ORDER)
 quick=[]
 for title,label in [('Where to Go in a Radiation Emergency','Radiation: where to shelter'),('Decontamination for Yourself','Radiation: decontamination'),('Make Water Safe During','Emergency drinking water'),('Indiana Roadway Map 2026','Indiana road map'),('Kentucky - Official Highway Map','Kentucky road map')]:
  x=next(x for x in records if x['title'].startswith(title));attrs='' if x['availability']=='hosted' else ' target="_blank" rel="noopener noreferrer"'
  quick.append(f"<a href='{esc(x['href'],quote=True)}'{attrs}>{esc(label)} <span>↗</span></a>")
 hosted=sum(x['availability']=='hosted' for x in records);linked=len(records)-hosted
 template=(ROOT/'templates/index.html').read_text(encoding='utf-8')
 stats=f"<div><strong>{hosted}</strong><span>references saved here</span></div><div><strong>{linked}</strong><span>publisher resources</span></div><div><strong>8</strong><span>local topo sheets</span></div><div><strong>Kentuckiana</strong><span>collection 01</span></div>"
 page=template.replace('@@STATS@@',stats).replace('@@QUICK@@',''.join(quick)).replace('@@CHIPS@@',chips).replace('@@CONTENT@@',''.join(blocks)).replace('@@COUNT@@',str(len(records))).replace('@@DOWNLOAD@@',DOWNLOAD).replace('@@REPO@@',REPO_URL)
 (site/'index.html').write_text(page,encoding='utf-8',newline='\n')
 (site/'.nojekyll').write_text('',encoding='utf-8',newline='\n')
 (site/'404.html').write_text("<!doctype html><html lang='en'><meta charset='utf-8'><title>Page not found | MARS CACHE</title><h1>This reference has moved.</h1><p><a href='/mars-cache/'>Return to MARS CACHE</a></p></html>",encoding='utf-8',newline='\n')
 about='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>About | MARS CACHE</title><style>body{max-width:800px;padding:30px;margin:auto;background:#f4f1e8;color:#222a23;font:17px/1.7 system-ui}a{color:#344b35}</style></head><body><a href="index.html">← MARS CACHE</a><h1>Knowledge worth keeping.</h1><p>MARS CACHE is the Mars brothers' collection of survival, repair and rebuilding references for Kentuckiana. MARS stands for Mobile Archive for Resilience &amp; Survival.</p><h2>Reading and downloading</h2><p>The catalog contains 32 locally hosted references and 23 publisher resources. Hosted files can be read here or saved in the offline core download. Publisher resources open on their original websites and need internet access until you obtain your own copies. Search covers catalog descriptions, titles and publishers, not every word inside every PDF.</p><p>Unzip the offline download completely and open index.html. The bundled references work locally; publisher links still require the internet.</p><h2>Sources and dates</h2><p>Collection date: November 4, 2026. The regional topo selection covers parts of the Louisville area, not all of Kentuckiana. Publication dates vary and some references are historical. Static maps do not show current road, bridge, weather or fallout conditions. The collection has not undergone independent medical or engineering review.</p><h2>Attribution</h2><p>Source: CDC, HHS, FEMA, USDA, USGS, EPA and National Weather Service, as credited in each catalog entry. CDC/HHS materials are also available free on agency websites. MARS CACHE is an independent project; references and links do not imply endorsement by CDC, HHS, any other agency, publisher, or the United States Government. Original source documents retain their contents and credits.</p><p>Hesperian books and regional university and state publications are linked to their publishers. Hesperian's <a href="https://hesperian.org/open-copyright-policy/" target="_blank" rel="noopener noreferrer">digital distribution policy</a> requires written permission for redistribution.</p><p><a href="catalog.csv">Download the source catalog</a> · <a href="https://github.com/rustyorb/mars-cache">Project repository</a></p></body></html>'''
 (site/'about.html').write_text(about,encoding='utf-8',newline='\n')
 (site/'README-OFFLINE.txt').write_text('MARS CACHE — Public Offline Core\n\nUnzip the entire archive before opening index.html.\n32 hosted references are included. The catalog also links to 23 publisher resources that require internet access until you download your own copies.\n\nWHILE ONLINE: run Prepare-Personal-Cache.cmd on Windows, or python3 tools/prepare_personal.py on macOS/Linux. Python 3 is required. This downloads your own publisher files and health chapters directly into MARS-CACHE-Personal in your home folder. Check OFFLINE-READINESS.html there for missing files, then practice with Wi-Fi off.\n\nSources, audiences, dates and file hashes are recorded in catalog.json and catalog.csv. This archive contains no live weather, road or radiation data.\n\nhttps://rustyorb.github.io/mars-cache/\n',encoding='utf-8',newline='\n')
 prepare='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Prepare your offline cache | MARS CACHE</title><style>body{max-width:800px;margin:auto;padding:30px;background:#f4f1e8;color:#222a23;font:18px/1.7 system-ui}a{color:#344b35}code{font-size:15px;overflow-wrap:anywhere}</style></head><body><a href="index.html">← MARS CACHE</a><h1>Prepare now. Read offline later.</h1><p>The website is the distribution point. The survival copy is the set of files stored on your own devices.</p><ol><li>Download the offline core and unzip the entire archive. Its 32 hosted references work locally immediately.</li><li>While still online, run <strong>Prepare-Personal-Cache.cmd</strong> on Windows. <a href="https://www.python.org/downloads/" target="_blank" rel="noopener noreferrer">Python 3</a> must be installed. On macOS/Linux, run <code>python3 tools/prepare_personal.py</code> from the unzipped folder.</li><li>The tool reuses the core PDFs and downloads the remaining files directly from publishers. Your personal library goes in <strong>MARS-CACHE-Personal</strong> in your home folder.</li><li>Open <strong>OFFLINE-READINESS.html</strong> there. It checks the 143 planned reference/chapter files and reports any missing downloads. Preparation is incomplete if files are missing.</li><li>Disconnect Wi-Fi and mobile data. Practice finding maps and instructions. Keep another complete copy on a backup drive.</li></ol><p>A publisher link or website bookmark is not an offline copy. The preparation tool needs internet access; it is meant to run before an outage. Publisher materials retain their terms and attribution.</p><p>The Raspberry Pi stage will serve these local files over its own Wi-Fi. This release does not yet install a Pi operating system.</p></body></html>'''
 (site/'prepare.html').write_text(prepare,encoding='utf-8',newline='\n')
 files=sorted(p for p in site.rglob('*') if p.is_file() and p.name!='SHA256SUMS.txt')
 (site/'SHA256SUMS.txt').write_text(''.join(f'{digest(p)}  {p.relative_to(site).as_posix()}\n' for p in files),encoding='utf-8',newline='\n')
 dist=ROOT/'dist';dist.mkdir(exist_ok=True)
 archive=dist/ARCHIVE
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as z:
  for p in sorted(site.rglob('*')):
   if p.is_file():z.write(p,'MARS-CACHE/'+p.relative_to(site).as_posix())
  extras=[ROOT/'Prepare-Personal-Cache.cmd',ROOT/'PREPARE-YOUR-CACHE.md',ROOT/'tools/prepare_personal.py',ROOT/'tools/personal-requirements.txt',ROOT/'data/personal-download-plan.json']+list((ROOT/'tools/offline').glob('*.py'))
  for p in extras:z.write(p,'MARS-CACHE/'+p.relative_to(ROOT).as_posix())
 with zipfile.ZipFile(archive) as z:
  if z.testzip():raise ValueError('Offline archive integrity check failed')
 (dist/(ARCHIVE+'.sha256')).write_text(digest(archive)+'  '+ARCHIVE+'\n',encoding='utf-8',newline='\n')
 report={'resources':len(records),'hosted':hosted,'publisher_links':linked,'site_bytes':sum(p.stat().st_size for p in site.rglob('*') if p.is_file()),'archive_bytes':archive.stat().st_size,'archive_sha256':digest(archive)}
 (dist/'build-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8',newline='\n')
 print(json.dumps(report,indent=2))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--collection',type=Path,required=True)
 run(p.parse_args().collection.resolve())
