"""Validate site files and public-export boundaries without third-party packages."""
import hashlib,json,re,sys
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlparse,unquote
ROOT=Path(__file__).resolve().parents[1];SITE=ROOT/'site'
errors=[]
catalog=json.loads((SITE/'catalog.json').read_text(encoding='utf-8'))
class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[]
 def handle_starttag(self,tag,attrs):
  attrs=dict(attrs)
  for k in ['src','href']:
   if attrs.get(k):self.links.append((tag,k,attrs[k]))
checked=0
for x in catalog:
 if x['availability']=='hosted':
  p=(SITE/x['href']).resolve()
  if not p.is_relative_to(SITE) or not p.exists():errors.append('Missing/outside hosted reference: '+x['title']);continue
  if hashlib.sha256(p.read_bytes()).hexdigest()!=x['hosted_sha256']:errors.append('Reference hash mismatch: '+x['title'])
  if p.suffix=='.pdf' and not p.read_bytes()[:1024].lstrip().startswith(b'%PDF-'):errors.append('Invalid PDF header: '+p.name)
  checked+=1
 else:
  if urlparse(x['href']).scheme not in ['http','https']:errors.append('Invalid publisher URL')
  if x['publisher']=='Hesperian Health Guides' and x['href']!='https://languages.hesperian.org/pages/en/pdf.html':errors.append('Hesperian must link to publisher landing page')
for line in (SITE/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
 expected,rel=line.split('  ',1);p=(SITE/rel).resolve()
 if not p.is_relative_to(SITE) or not p.exists():errors.append('Missing/outside inventory file: '+rel);continue
 if hashlib.sha256(p.read_bytes()).hexdigest()!=expected:errors.append('Inventory mismatch: '+rel)
local_links=0
for p in SITE.rglob('*.html'):
 parser=Links();parser.feed(p.read_text(encoding='utf-8'))
 for tag,attr,u in parser.links:
  parsed=urlparse(u)
  if attr=='src' and parsed.scheme in ['http','https']:errors.append('External embedded dependency: '+u)
  if parsed.scheme or not parsed.path:continue
  if parsed.path.startswith('/'):
   # Project-root path in the standalone 404 page.
   if parsed.path=='/mars-cache/':continue
   errors.append('Unexpected absolute web path: '+u);continue
  target=(p.parent/unquote(parsed.path)).resolve()
  if not target.is_relative_to(SITE) or not target.exists():errors.append('Broken local link: '+str(p.relative_to(SITE))+' -> '+u)
  local_links+=1
for p in ROOT.rglob('*'):
 if not p.is_file() or any(x in p.parts for x in ['.git','dist','previews','__pycache__']):continue
 if p.stat().st_size>100*1024*1024:errors.append('File exceeds regular Git limit: '+str(p.relative_to(ROOT)))
 if p.suffix.lower() in ['.html','.json','.csv','.md','.py','.yml','.txt']:
  text=p.read_text(encoding='utf-8-sig')
  for pattern in [r'gh[pousr]_[A-Za-z0-9]{20,}',r'sk-(?:proj-)?[A-Za-z0-9_-]{30,}',r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----',r'(?i)[A-Z]:[\\/](?:Users|_AI_PROJECTS)[\\/]']:
   if re.search(pattern,text):errors.append('Potential private export in '+str(p.relative_to(ROOT)));break
 if p.is_relative_to(SITE) and ('health-and-sanitation' in p.parts or 'original-html' in p.parts):errors.append('Private/publisher-restricted folder exported: '+str(p))
size=sum(p.stat().st_size for p in SITE.rglob('*') if p.is_file())
if size>=1024**3:errors.append('Published site exceeds GitHub Pages size limit')
report={'resources':len(catalog),'hosted_files_checked':checked,'publisher_links':sum(x['availability']=='publisher' for x in catalog),'local_links_checked':local_links,'site_bytes':size,'errors':errors}
print(json.dumps(report,indent=2))
if errors:sys.exit(1)
