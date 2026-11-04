"""Verify collected originals, reader copies, assets and relative document links."""
import sys,json,hashlib
from pathlib import Path
from urllib.parse import urlparse,unquote
sys.path.insert(0,str(Path(__file__).parent/'vendor'))
from bs4 import BeautifulSoup
ROOT=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
errors=[];checked=0;links=0
for line in (ROOT/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
 expected,rel=line.split('  ',1);p=(ROOT/rel).resolve()
 if not p.is_relative_to(ROOT):errors.append('Outside collection: '+rel);continue
 if not p.exists():errors.append('Missing: '+rel);continue
 h=hashlib.sha256()
 with p.open('rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
 if h.hexdigest()!=expected:errors.append('Checksum mismatch: '+rel)
 checked+=1
data=json.loads((ROOT/'catalog.json').read_text(encoding='utf-8'))
good=[x for x in data if x['status']=='collected']
for x in good:
 for key,hashkey in [('original_path','sha256'),('local_path','reader_sha256' if x['format']=='HTML reader' else 'sha256')]:
  p=ROOT/x[key]
  if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest()!=x[hashkey]:errors.append('Catalog mismatch: '+x[key])
 for a in x.get('assets',[]):
  p=ROOT/a['local_path']
  if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest()!=a['sha256']:errors.append('Asset mismatch: '+a['local_path'])
htmlpaths=[ROOT/'index.html',ROOT/'ABOUT.html']+[ROOT/x['local_path'] for x in good if x['format']=='HTML reader']
for p in htmlpaths:
 soup=BeautifulSoup(p.read_text(encoding='utf-8'),'html.parser')
 for node in soup.select('[src],[href]'):
  for attr in ['src','href']:
   u=node.get(attr)
   if not u:continue
   parsed=urlparse(u)
   if attr=='src' and parsed.scheme in ('http','https'):errors.append('External embedded dependency: '+str(p)+' '+u)
   if parsed.scheme or not parsed.path:continue
   target=(p.parent/unquote(parsed.path)).resolve()
   if not target.is_relative_to(ROOT):errors.append('Link leaves collection: '+u)
   elif not target.exists():errors.append('Broken local link: '+str(p)+' -> '+u)
   links+=1
report={'checksummed_files':checked,'saved_documents':len(good),'html_files_checked':len(htmlpaths),'relative_links_checked':links,'errors':errors}
(ROOT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
if errors:sys.exit(1)
