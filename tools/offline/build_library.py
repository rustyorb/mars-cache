"""Build the portable offline catalog, documentation, and integrity inventory."""
import json,csv,hashlib,re,os
from pathlib import Path
from html import escape as e
from urllib.parse import urljoin
from collections import Counter,defaultdict
import sys
sys.path.insert(0,str(Path(__file__).parent/'vendor'))
from bs4 import BeautifulSoup

ROOT=Path(os.environ["MARS_CACHE_COLLECTION"]).resolve()
DATE='2026-11-04'
ORDER=['Water and immediate preparedness','Nuclear and radiation','Health and sanitation','Maps and navigation','Growing food','Preserving food','Tools and power','Communications','Cache operation']

def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
 return h.hexdigest()
def size(n):return f'{n/1024/1024:.1f} MB' if n>=1024*1024 else f'{n/1024:.0f} KB'
def natural(t):return [int(x) if x.isdigit() else x.lower() for x in re.split('(\\d+)',t)]
def run():
 records=json.loads((ROOT/'catalog.json').read_text(encoding='utf-8'))
 good=[x for x in records if x['status']=='collected'];bad=[x for x in records if x['status']!='collected']
 lookup={}
 for x in good:
  lookup[x['url']]=x['local_path'];lookup[x.get('resolved_url',x['url'])]=x['local_path']
 # Prefer local copies of links when the linked resource is in this collection.
 for x in good:
  if x['format']!='HTML reader':continue
  p=ROOT/x['local_path'];s=BeautifulSoup(p.read_text(encoding='utf-8'),'html.parser')
  for a in s.select('a[href]'):
   href=a['href'];base=href.split('#')[0]
   if base in lookup and a.get('data-online'):
    rel=os.path.relpath(ROOT/lookup[base],p.parent).replace('\\','/')
    a['href']=rel+('#'+href.split('#',1)[1] if '#' in href else '')
    a.attrs.pop('data-online',None);a['title']='Open saved local copy'
  p.write_text(str(s),encoding='utf-8');x['reader_sha256']=digest(p)
 (ROOT/'catalog.json').write_text(json.dumps(records,indent=2,ensure_ascii=False),encoding='utf-8')
 total=sum(x['bytes'] for x in good);counts=Counter(x['category'] for x in good)
 pdfs=sum(x['format']=='PDF' for x in good);pages=sum(x.get('pages',0) for x in good)
 groups=defaultdict(list)
 for x in good:groups[(x['category'],x['group'])].append(x)
 content=[]
 for cat in ORDER:
  if not counts[cat]:continue
  blocks=[]
  for (c,g),items in groups.items():
   if c!=cat:continue
   rows=[]
   for x in sorted(items,key=lambda x:natural(x['title'])):
    keywords=' '.join(str(x.get(k,'')) for k in ['title','group','category','publisher','audience','notes']).lower()
    info=' · '.join([x['format'],f"{x['pages']} pages" if x.get('pages') else '',size(x['bytes'])]).replace(' ·  · ',' · ')
    if x.get('audience') and x['audience']!='General reference':info+=' · '+x['audience']
    rows.append(f"<li class='entry' data-search='{e(keywords,quote=True)}'><div><a class='resource' href='{e(x['local_path'],quote=True)}'>{e(x['title'])}</a><p>{e(info)}</p></div><details><summary>Source</summary><p>{e(x['publisher'])}<br>{e(x['edition'])}<br><a href='{e(x['source_page'],quote=True)}'>Publisher page (online)</a></p></details></li>")
   blocks.append(f"<section class='group'><h3>{e(g)} <span>{len(items)}</span></h3><ul>{''.join(rows)}</ul></section>")
  content.append(f"<section class='category' data-category='{e(cat,quote=True)}' id='{re.sub('[^a-z]+','-',cat.lower()).strip('-')}'><div class='category-title'><h2>{e(cat)}</h2><span>{counts[cat]} saved items</span></div>{''.join(blocks)}</section>")
 chips="<button class='chip active' type='button' data-filter='all' aria-pressed='true'>Everything</button>"+''.join(f"<button class='chip' type='button' data-filter='{e(c,quote=True)}' aria-pressed='false'>{e(c)}</button>" for c in ORDER if counts[c])
 quick=[]
 for term,label in [('First Aid','First aid reference'),('Where to Go in a Radiation Emergency','Radiation: where to shelter'),('Decontamination for Yourself','Radiation: decontamination'),('Make Water Safe During','Emergency drinking water'),('Indiana Roadway Map 2026','Indiana road map'),('Kentucky - Official Highway Map','Kentucky road map')]:
  item=next((x for x in good if x['title'].startswith(term)),None)
  if item:quick.append(f"<a href='{e(item['local_path'],quote=True)}'>{e(label)} <span>↗</span></a>")
 html='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src 'self' file: data:; base-uri 'none'; form-action 'none'"><title>MARS CACHE — Kentuckiana Field Library</title><style>
 :root{--paper:#f4f1e8;--ink:#222a23;--muted:#5e685e;--line:#c7cbbd;--green:#344b35;--accent:#e7b866}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:system-ui,-apple-system,sans-serif}a{color:var(--green);text-underline-offset:3px}a:hover{color:#111}.shell{max-width:1120px;margin:auto;padding:0 32px}.top{border-bottom:1px solid var(--line);padding:19px 0;font:12px/1.4 monospace;letter-spacing:.13em;display:flex;justify-content:space-between;gap:20px}.hero{padding:48px 0 38px;border-bottom:2px solid var(--ink)}.eyebrow{font:12px/1.4 monospace;letter-spacing:.15em;color:var(--muted)}h1{font-size:clamp(48px,9vw,100px);letter-spacing:-.065em;line-height:.97;margin:14px 0 20px;font-weight:850}.intro{font-size:22px;max-width:650px;line-height:1.45;margin:0 0 16px}.tagline{font:13px/1.6 monospace;color:var(--muted)}.stats{display:flex;gap:30px;flex-wrap:wrap;margin-top:30px}.stats strong{display:block;font-size:25px}.stats span{font-size:12px;color:var(--muted)}.quick{padding:27px 0;border-bottom:1px solid var(--line)}.quick h2{font:12px/1.4 monospace;letter-spacing:.1em;margin:0 0 14px}.quick-links{display:flex;flex-wrap:wrap;gap:9px}.quick a{border:1px solid var(--line);padding:12px 14px;text-decoration:none;font-size:14px;background:#fffdf6}.quick a span{padding-left:15px}.controls{padding:30px 0 20px}label{display:block;font-weight:650;margin-bottom:9px}input{width:100%;font:17px system-ui;padding:14px 16px;background:#fffdf8;border:1px solid #919b8c;border-radius:2px;color:var(--ink)}input:focus{outline:3px solid #e7b866;outline-offset:2px}.chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:15px}.chip{border:1px solid var(--line);padding:8px 11px;background:transparent;color:var(--green);font:13px system-ui;cursor:pointer;border-radius:3px}.chip.active{background:var(--green);color:#fff;border-color:var(--green)}.result{font:12px/1.6 monospace;color:var(--muted)}.category{margin:15px 0 38px}.category-title{border-bottom:2px solid var(--green);display:flex;align-items:baseline;justify-content:space-between;gap:16px;padding-bottom:10px}.category-title h2{font-size:25px;margin:0;letter-spacing:-.03em}.category-title>span{font:12px monospace;color:var(--muted)}.group{margin-top:23px}.group h3{font-size:15px;margin:0;padding:10px 0;color:var(--muted)}.group h3 span{font:11px monospace;padding:3px 6px;background:#e1e5d8;margin-left:6px}ul{list-style:none;padding:0;margin:0}.entry{border-top:1px solid var(--line);padding:15px 0;display:flex;justify-content:space-between;gap:20px}.entry .resource{font-size:16px;font-weight:600;text-decoration:none}.entry .resource:hover{text-decoration:underline}.entry p{font-size:12px;color:var(--muted);line-height:1.6;margin:5px 0 0}.entry details{font-size:12px;min-width:52px;max-width:260px}.entry summary{cursor:pointer;color:var(--muted)}[hidden]{display:none!important}.foot{border-top:2px solid var(--ink);padding:25px 0 40px;display:flex;justify-content:space-between;gap:24px;font-size:12px;line-height:1.6;color:var(--muted)}.foot p{max-width:620px;margin:0}.empty{padding:30px 0;color:var(--muted)}@media(max-width:600px){.shell{padding:0 18px}.top{font-size:10px}.hero{padding:34px 0 26px}.intro{font-size:18px}.entry{gap:12px}.category-title h2{font-size:22px}.stats{gap:24px}.foot{flex-direction:column}.entry details{max-width:160px}}@media print{.controls,.quick,.foot,details{display:none}.hero{padding:10px 0}h1{font-size:40px}.entry{padding:6px 0}.category{break-inside:avoid}}
 </style></head><body><div class="shell"><div class="top"><span>MARS BROTHERS / FIELD LIBRARY</span><span>KENTUCKIANA · COLLECTION 01</span></div><header class="hero"><div class="eyebrow">MOBILE ARCHIVE FOR RESILIENCE &amp; SURVIVAL</div><h1>MARS CACHE<span style="color:#87916f">.</span></h1><p class="intro">A library for survival, repair, and rebuilding.</p><p class="tagline">Two brothers. One cache. No internet required.</p><div class="stats">__STATS__</div></header><section class="quick"><h2>QUICK REFERENCES</h2><div class="quick-links">__QUICK__</div></section><div class="controls"><label for="search">Find a reference</label><input id="search" type="search" placeholder="Search titles, subjects, or publishers…" autocomplete="off"><div class="chips" aria-label="Filter by subject">__CHIPS__</div><p class="result" id="results" aria-live="polite">__COUNT__ saved items · search covers catalog descriptions</p></div><main>__CONTENT__<p class="empty" id="empty" hidden>No matches. Try a broader word or choose Everything.</p></main><footer class="foot"><p>Saved originals and readable page snapshots. Sources retain their publication dates and intended audiences. This collection includes older references and has not undergone independent medical or engineering review. Maps show static information; this library has no live weather, road, or fallout data.</p><p><a href="ABOUT.html">About this collection &amp; remaining gaps</a><br><a href="catalog.csv">Source catalog</a> · <a href="SHA256SUMS.txt">File fingerprints</a></p></footer></div><script>
 const entries=[...document.querySelectorAll('.entry')],cats=[...document.querySelectorAll('.category')],groups=[...document.querySelectorAll('.group')],search=document.querySelector('#search');let filter='all';function update(){const terms=search.value.toLowerCase().trim().split(/\\s+/).filter(Boolean);let shown=0;for(const item of entries){const category=item.closest('.category').dataset.category;const show=(filter==='all'||category===filter)&&terms.every(t=>item.dataset.search.includes(t));item.hidden=!show;if(show)shown++;}for(const g of groups)g.hidden=![...g.querySelectorAll('.entry')].some(x=>!x.hidden);for(const c of cats)c.hidden=![...c.querySelectorAll('.entry')].some(x=>!x.hidden);document.querySelector('#results').textContent=`${shown} of ${entries.length} saved items · search covers catalog descriptions`;document.querySelector('#empty').hidden=shown!==0;}search.addEventListener('input',update);for(const b of document.querySelectorAll('.chip'))b.addEventListener('click',()=>{filter=b.dataset.filter;for(const x of document.querySelectorAll('.chip')){x.classList.toggle('active',x===b);x.setAttribute('aria-pressed',String(x===b));}update();});
 </script></body></html>'''
 stats=f"<div><strong>{len(good)}</strong><span>saved references &amp; chapters</span></div><div><strong>{pdfs}</strong><span>original PDFs</span></div><div><strong>{size(total)}</strong><span>source documents</span></div><div><strong>{DATE}</strong><span>collection date</span></div>"
 html=html.replace('__STATS__',stats).replace('__QUICK__',''.join(quick)).replace('__CHIPS__',chips).replace('__CONTENT__',''.join(content)).replace('__COUNT__',str(len(good)))
 (ROOT/'index.html').write_text(html,encoding='utf-8')
 with (ROOT/'catalog.csv').open('w',newline='',encoding='utf-8-sig') as f:
  keys=['title','group','category','publisher','edition','audience','status','format','pages','bytes','local_path','source_page','url','resolved_url','retrieved_utc','sha256','error','notes']
  writer=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');writer.writeheader();writer.writerows(records)
 lines=['# MARS CACHE — Collection status','',f'Collection date: {DATE}.','',f'{len(good)} saved documents/chapter files: {pdfs} PDFs and {len(good)-pdfs} readable HTML snapshots. {pages:,} PDF pages. {size(total)} in original documents, excluding local images and metadata.','', '## Saved by subject','']
 lines.extend(f'- {cat}: {counts[cat]}' for cat in ORDER if counts[cat])
 lines+=['','## Coverage and limits','','- Hesperian works are counted as chapter files, not separate books. Four works are included: Where There Is No Doctor; Where There Is No Dentist; New Where There Is No Doctor; A Community Guide to Environmental Health.','- The USDA canning set contains its introduction and all seven guides, publisher-linked 2015 revision.','- Road maps cover Kentucky and Indiana. City insets have their own source editions. The eight USGS topo sheets cover selected parts of the Louisville area only; this is not complete Kentuckiana coverage.','- Static map editions are recorded where supplied. No live bridge, road, weather, fallout or water-quality conditions are available in this archive.','- Original PDFs remain unmodified. Readable HTML snapshots have active content and site navigation removed; available article images are local. Saved source links may still require the internet.','- File integrity and PDF readability checks are not an independent clinical, food-safety or engineering review. Source material includes historical publications.','- Collection is for personal offline use. Hesperian provides chapter downloads but retains copyright; consult included copyright pages and publisher terms before redistributing the bundle.','- A Raspberry Pi operating-system image, hotspot configuration, full-text index, and large ZIM archives are not included yet.','','## Not downloaded / needs follow-up','']
 for x in bad:lines+=[f"- **{x['title']}** — {x.get('error','Unavailable')}. Source: {x['url']}"]
 lines+=['','## Next collection priorities','','1. County-level maps and broader topo coverage once preferred counties or travel corridors are known.','2. Regional seed saving, orchards, small livestock, soil, pest management, wells, septic and sanitation references.','3. Carpentry, plumbing, electrical fundamentals, small engines, bicycle repair, textiles and practical textbooks.','4. Exact manuals for the equipment the two households own.','5. Kiwix archives: Wikipedia, Appropedia and selected repair/reference collections; resolve current availability, size and terms before large downloads.','6. Civilian nuclear monitoring and instrument manuals once the instruments are selected.','','Blocked URLs are recorded as unavailable and are not silently substituted with unverified copies.']
 health_included=any(x['publisher']=='Hesperian Health Guides' for x in good)
 if not health_included:
  lines=[line for line in lines if not line.startswith('- Hesperian works are counted')]
  lines+=['','## Health guides for your own collection','','Hesperian chapter PDFs are omitted from this transfer copy. Obtain your own copies from https://languages.hesperian.org/pages/en/pdf.html . Their digital redistribution policy requests written permission: https://hesperian.org/open-copyright-policy/ . See HEALTH-DOWNLOADS.html.']
 status='\n'.join(lines)+'\n';(ROOT/'COLLECTION-STATUS.md').write_text(status,encoding='utf-8')
 about=f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>About MARS CACHE</title><style>body{{max-width:850px;margin:auto;padding:24px;background:#f4f1e8;color:#222a23;font:17px/1.7 system-ui}}a{{color:#344b35}}pre{{white-space:pre-wrap;font:15px/1.8 system-ui;overflow-wrap:anywhere}}</style></head><body><a href='index.html'>← MARS CACHE</a><pre>{e(status)}</pre></body></html>"
 (ROOT/'ABOUT.html').write_text(about,encoding='utf-8')
 readme=f'''# MARS CACHE

Mobile Archive for Resilience & Survival — Kentuckiana starter collection

Two brothers. One cache. No internet required.

Open `index.html` in a browser. The catalog and saved documents work from this folder without internet access. Search filters document titles, subjects, publisher names and catalog notes; it does not search the full text of every PDF.

This first collection contains {len(good)} saved references/chapter files ({pdfs} original PDFs and {len(good)-pdfs} readable HTML snapshots). Four Hesperian works are stored as separate publisher-provided chapters. See `ABOUT.html` or `COLLECTION-STATUS.md` for coverage and gaps.

To move it, copy the complete folder, including `library`, `sources/original-html`, and the catalogs. Keep relative paths intact. Sources and publication dates are in `catalog.csv` / `catalog.json`; some dates remain undetermined. Reader snapshots have source links that may need the internet. PDFs can also be opened directly in any compatible reader.

The collection is for personal offline use. Preserve all publisher/copyright pages. Review publisher terms before redistributing any complete bundle. Clinical and technical references have not undergone independent content review. This is a content collection; no Raspberry Pi OS has been flashed or deployed.

To refresh your personal cache, run the preparation launcher again from the original downloaded package. Collection tool source lives with that package under `tools`. Run them with Python 3 and the documented dependencies. `collect.py` reuses checksum-matching local originals and skips recorded unavailable sources unless `--retry-unavailable` is given. `build_library.py` rebuilds the browsing catalog; `verify.py` checks local integrity. Avoid running collection and catalog builds concurrently.
'''
 if not health_included:
  readme=readme.replace('Four Hesperian works are stored as separate publisher-provided chapters.','Hesperian chapter PDFs are omitted from this transfer copy; HEALTH-DOWNLOADS.html links to publisher downloads for your own collection.')
  readme=readme.split('Collection tools live under')[0]+'This is a portable browsing copy. The source collection on the owner\'s computer also contains the collection tools.\n'
 (ROOT/'README.md').write_text(readme,encoding='utf-8')
 if (ROOT/'tools').exists():
  (ROOT/'tools/requirements.txt').write_text('requests\nbeautifulsoup4\npypdf\n',encoding='utf-8')
 inventory=[]
 for x in good:
  for key in ['local_path','original_path']:
   p=ROOT/x[key];inventory.append(p)
  for a in x.get('assets',[]):inventory.append(ROOT/a['local_path'])
 inventory+= [ROOT/n for n in ['index.html','ABOUT.html','README.md','COLLECTION-STATUS.md','catalog.json','catalog.csv','collection-plan.json']]
 inventory=sorted(set(inventory))
 (ROOT/'SHA256SUMS.txt').write_text(''.join(f'{digest(p)}  {p.relative_to(ROOT).as_posix()}\n' for p in inventory),encoding='utf-8')
 report={'date':DATE,'collected':len(good),'unavailable':len(bad),'pdfs':pdfs,'html_readers':len(good)-pdfs,'pdf_pages':pages,'original_bytes':total,'integrity_files':len(inventory),'categories':dict(counts)}
 (ROOT/'collection-summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
if __name__=='__main__':run()
