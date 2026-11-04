"""Download a bounded personal reference collection and build offline readers.

No executable source content is run. Publisher files are kept unmodified.
HTML readers are derived copies with local styles/images and source attribution.
"""
import sys,json,hashlib,re,io,copy,time,logging,threading,os
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urljoin,urlparse,unquote
from concurrent.futures import ThreadPoolExecutor,as_completed
sys.path.insert(0,str(Path(__file__).parent/'vendor'))
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
logging.getLogger('pypdf').setLevel(logging.ERROR)
ROOT=Path(os.environ["MARS_CACHE_COLLECTION"]).resolve()
LIMIT=80*1024*1024
TOTAL_LIMIT=1024*1024*1024
budget_lock=threading.Lock()
downloaded=0
UA={'User-Agent':requests.utils.default_user_agent()}
CSS='''body{max-width:960px;margin:0 auto;padding:24px;font:18px/1.65 system-ui,sans-serif;color:#20251f;background:#faf9f4}a{color:#205a3a}img{max-width:100%;height:auto}table{border-collapse:collapse;max-width:100%;display:block;overflow:auto}th,td{border:1px solid #a6aaa0;padding:.5em}header{border-bottom:2px solid #52664a;padding-bottom:1em;margin-bottom:2em}header p{font-size:14px;line-height:1.5}.notice{background:#eeeede;padding:1em}pre{white-space:pre-wrap}h1,h2,h3{line-height:1.25}@media print{body{padding:0;font-size:12pt}header p{font-size:9pt}a{color:inherit}}'''

def now():return datetime.now(timezone.utc).isoformat()
def sha(b):return hashlib.sha256(b).hexdigest()
def slug(t):return re.sub(r'[^a-z0-9]+','-',t.lower()).strip('-')[:100] or 'document'
def request_bytes(url,limit=LIMIT):
 global downloaded
 if urlparse(url).scheme not in ('https','http'):raise ValueError('Unsupported URL scheme')
 for attempt in range(2):
  try:
   with requests.get(url,headers=UA,timeout=(15,60),stream=True) as r:
    r.raise_for_status()
    if int(r.headers.get('Content-Length','0') or 0)>limit:raise ValueError('File exceeds collection limit')
    chunks=[];n=0
    for c in r.iter_content(128*1024):
     n+=len(c)
     if n>limit:raise ValueError('File exceeds collection limit')
     with budget_lock:
      if downloaded+len(c)>TOTAL_LIMIT:raise ValueError('Collection download budget exhausted')
      downloaded+=len(c)
     chunks.append(c)
    return b''.join(chunks),r.url,dict(r.headers)
  except (requests.Timeout,requests.ConnectionError):
   if attempt:raise
   time.sleep(1)

def reader_html(item,raw,base):
 soup=BeautifulSoup(raw,'html.parser')
 # Site-specific extraction retains source warnings, tables and article structure.
 if 'weather.gov' in base:
  main=soup.select_one('#cms-content') or soup.select_one('.content-area') or soup.body
 elif 'purdue.edu' in base:
  main=soup.select_one('main') or soup.select_one('article') or soup.body
 else:
  main=soup.select_one('main') or soup.select_one('article') or soup.select_one('#content') or soup.body
 if main is None:raise ValueError('No document body')
 main=copy.deepcopy(main)
 for x in main.select('script,style,iframe,frame,frameset,object,embed,form,nav,header,footer,aside,link,meta,button,input,video,audio,source'):
  x.decompose()
 for x in main.find_all(True):
  for k in list(x.attrs):
   if k.lower().startswith('on') or k.lower() in ['style','srcset','background','action','ping','integrity','crossorigin','loading']:del x[k]
  for attr in ['href','src','xlink:href']:
   v=x.get(attr)
   if v and v.strip().lower().startswith(('javascript:','vbscript:','data:text/html')):del x[attr]
  if x.name=='a' and x.get('href') and not x['href'].startswith('#'):
   x['href']=urljoin(base,x['href']);x['data-online']='true';x['title']='Original source link; internet required unless archived locally'
 # Local image copies keep diagrams useful without an internet connection.
 assets=[];missing=[];count=0
 for img in main.find_all('img'):
  src=img.get('src') or img.get('data-src')
  if not src:
   img.decompose();continue
  u=urljoin(base,src)
  if u.startswith('data:image/'):
   continue
  if count>=60:
   missing.append(u);img.replace_with('[Image not included in this snapshot]');continue
  count+=1
  try:
   b,res,h=request_bytes(u,8*1024*1024)
   mime=h.get('Content-Type','').split(';')[0]
   if not mime.startswith('image/'):raise ValueError('Not an image')
   ext={'image/png':'.png','image/jpeg':'.jpg','image/gif':'.gif','image/svg+xml':'.svg','image/webp':'.webp'}.get(mime,'.img')
   # SVG may contain active/remote content; retain an inert missing-image note instead.
   if mime=='image/svg+xml':raise ValueError('SVG not embedded in offline reader')
   path=ROOT/'library/assets'/(sha(b)+ext);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b)
   img['src']='../assets/'+path.name
   assets.append({'url':u,'resolved_url':res,'local_path':path.relative_to(ROOT).as_posix(),'bytes':len(b),'sha256':sha(b)})
  except Exception as e:
   missing.append(u)
   label=img.get('alt') or 'Source image'
   img.replace_with(f'[{label}: image unavailable in offline snapshot]')
 # Embedded background media is intentionally absent; original HTML is retained separately.
 for e in main.find_all(True):
  if e.name not in ['img','a']:
   for k in ['src','href','xlink:href']:
    if e.get(k):del e[k]
 text=main.get_text(' ',strip=True)
 if len(text)<250:raise ValueError('Article content too short; manual extraction needed')
 from html import escape as esc
 notice=f"<header><a href='../../index.html'>MARS CACHE / Library</a><h1>{esc(item['title'])}</h1><p>{esc(item['publisher'])} · {esc(item['audience'])}<br>Saved {esc(item['retrieved_utc'])}<br><a href='{esc(item['url'],quote=True)}'>Original source (online)</a> · <a href='../../{esc(item['original_path'],quote=True)}'>Unmodified HTML source</a></p><p>{esc(item['notes'])}</p></header>"
 out=f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; img-src 'self' file: data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'\"><title>{esc(item['title'])} | MARS CACHE</title><style>{CSS}</style></head><body>{notice}<main>{str(main)}</main></body></html>"
 dates={}
 for key in ['article:published_time','article:modified_time','dcterms.date','date','DC.date.issued','DC.date.modified']:
  node=soup.find('meta',attrs={'name':key}) or soup.find('meta',attrs={'property':key})
  if node and node.get('content'):dates[key]=node['content']
 return out,assets,missing,dates,len(text),soup.title.get_text(' ',strip=True) if soup.title else ''

def collect(item):
 item=dict(item);item['attempted_utc']=now()
 old_path=ROOT/'catalog.json'
 if old_path.exists():
  old=next((x for x in json.loads(old_path.read_text(encoding='utf-8')) if x['id']==item['id']),None)
  if old and old.get('status')=='unavailable' and '--retry-unavailable' not in sys.argv:return old
  if old and old.get('status')=='collected':
   p=ROOT/old['local_path'];o=ROOT/old['original_path']
   if p.exists() and o.exists() and sha(o.read_bytes())==old['sha256'] and sha(p.read_bytes())==old.get('reader_sha256',old['sha256']):return old
 try:
  b,res,h=request_bytes(item['url']);item['retrieved_utc']=now()
  item.update(resolved_url=res,content_type=h.get('Content-Type',''),bytes=len(b),sha256=sha(b),last_modified=h.get('Last-Modified'),etag=h.get('ETag'))
  ispdf=b[:1024].lstrip().startswith(b'%PDF-')
  expectedpdf='.pdf' in urlparse(item['url']).path.lower()
  if expectedpdf and not ispdf:raise ValueError('Expected a PDF but server returned another format')
  category=slug(item['category'])
  folder=ROOT/'library'/category;folder.mkdir(parents=True,exist_ok=True)
  name=slug(item['title'])+'--'+item['id']
  if ispdf:
   reader=PdfReader(io.BytesIO(b),strict=False)
   if reader.is_encrypted:raise ValueError('Encrypted PDF requires manual review')
   item['pages']=len(reader.pages)
   if item['pages']<1:raise ValueError('Empty PDF')
   meta=reader.metadata or {}
   item['pdf_metadata']={str(k):str(v) for k,v in meta.items()}
   # Extractability is recorded separately; scanned PDFs can still be valid.
   if item['category']=='Maps and navigation' or len(b)>8*1024*1024:
    item['first_page_text_characters']=None
    item['text_extraction_note']='Text extraction skipped for large/graphical PDF; PDF structure and page count validated.'
   else:
    item['first_page_text_characters']=len(reader.pages[0].extract_text() or '')
   p=folder/(name+'.pdf');p.write_bytes(b)
   item.update(format='PDF',local_path=p.relative_to(ROOT).as_posix(),original_path=p.relative_to(ROOT).as_posix(),status='collected',validation='PDF parsed; page count and SHA-256 recorded. Content not independently reviewed.')
  else:
   if 'html' not in item['content_type'].lower() and b'<html' not in b[:2048].lower():raise ValueError('Unsupported document format')
   raw=ROOT/'sources/original-html'/(name+'.html');raw.parent.mkdir(parents=True,exist_ok=True);raw.write_bytes(b)
   item['original_path']=raw.relative_to(ROOT).as_posix()
   out,assets,missing,dates,n,st=reader_html(item,b,res)
   p=folder/(name+'.html');p.write_text(out,encoding='utf-8')
   item.update(format='HTML reader',local_path=p.relative_to(ROOT).as_posix(),status='collected',assets=assets,missing_images=missing,source_dates=dates,article_text_characters=n,source_title=st,validation='Readable HTML extracted, active content removed, available images saved locally. Original HTML retained. Content not independently reviewed.')
   item['reader_sha256']=sha(p.read_bytes())
 except Exception as e:
  item.update(status='unavailable',error=f'{type(e).__name__}: {e}')
 return item

def run():
 plan=json.loads((ROOT/'collection-plan.json').read_text(encoding='utf-8'))
 results=[]
 with ThreadPoolExecutor(max_workers=4) as ex:
  futures=[ex.submit(collect,item) for item in plan]
  for f in as_completed(futures):
   x=f.result();results.append(x)
   if x['status']!='collected':print('UNAVAILABLE',x['title'],x.get('error',''),flush=True)
   if len(results)%10==0:print('PROGRESS',len(results),'/',len(plan),flush=True)
   (ROOT/'catalog.partial.json').write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding='utf-8')
 results.sort(key=lambda x:(x['category'],x['group'],x['title']))
 (ROOT/'catalog.json').write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding='utf-8')
 from collections import Counter
 good=[x for x in results if x['status']=='collected']
 print('COMPLETE',len(good),'collected;',len(results)-len(good),'unavailable;',round(sum(x['bytes'] for x in good)/1024/1024,1),'MiB originals')
 print(json.dumps(dict(Counter(x['category'] for x in good))))
if __name__=='__main__':run()
