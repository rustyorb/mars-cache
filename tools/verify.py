"""Validate site files and public-export boundaries without third-party packages."""
import hashlib,json,re,sys,ipaddress,stat,os
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlparse,unquote
ROOT=Path(__file__).resolve().parents[1];SITE=ROOT/'site'
BANNED_PARTS={'loompanics','private','personal-cache','mars-cache-personal','mars-cache-private'}
RESERVED_SITE_PARTS={'health-and-sanitation','original-html'}
SKIP_PARTS={'.git','dist','previews','__pycache__','tests'}
# First-level site dirs that may exist; library subdirs from the 4c84262 public tree.
ALLOWED_SITE_DIRS={'library'}
ALLOWED_LIBRARY_DIRS={'assets','communications','maps-and-navigation','nuclear-and-radiation','preserving-food','tools-and-power','water-and-immediate-preparedness'}
# Integer-form networks so this file's own text does not contain dotted or IPv6 literals.
_V4_NETS=tuple(ipaddress.ip_network((addr,prefix)) for addr,prefix in ((167772160,8),(2886729728,12),(3232235520,16),(2851995648,16)))
_V6_ULA=ipaddress.IPv6Network((0xfc00<<112,7))
_V6_LL=ipaddress.IPv6Network((0xfe80<<112,10))
HOME_TEXT=[
 r'(?i)[A-Z]:[\\/](?:Users|_AI_PROJECTS)[\\/]',
 r'(?m)(^|[^A-Za-z0-9])/home/[A-Za-z0-9._-]+',
 r'(?m)(^|[^A-Za-z0-9])/Users/[A-Za-z0-9._-]+',
 r'(?m)(^|[^A-Za-z0-9])~/[A-Za-z0-9._-]+',
 r'(?m)(^|[^A-Za-z0-9])~[A-Za-z0-9._-]+/',
 r'\$'+'HOME'+r'(?:/|\\|\b)',
 r'\$\{'+'HOME'+r'\}',
]
SECRET_TEXT=[
 r'gh[pousr]_[A-Za-z0-9]{20,}',
 r'sk-(?:proj-)?[A-Za-z0-9_-]{30,}',
 r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----',
]
_V4_FIND=re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
_V6_FIND=re.compile(r'(?i)(?<![0-9a-f])(?:(?:[0-9a-f]{0,4}:){2,7}[0-9a-f]{0,4}|::ffff:(?:\d{1,3}\.){3}\d{1,3})(?![0-9a-f])')

def _restricted_ip(addr):
 if isinstance(addr,ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
  addr=addr.ipv4_mapped
 if addr.version==4:
  return any(addr in net for net in _V4_NETS)
 return addr in _V6_ULA or addr in _V6_LL

def text_has_restricted_ip(text):
 for rx in (_V4_FIND,_V6_FIND):
  for m in rx.finditer(text):
   try:
    addr=ipaddress.ip_address(m.group(0))
   except ValueError:
    continue
   if _restricted_ip(addr):
    return True
 return False

def private_text_leaks(text):
 for pattern in SECRET_TEXT+HOME_TEXT:
  if re.search(pattern,text):
   return True
 if text_has_restricted_ip(text):
  return True
 return False

def path_has_banned_part(path):
 return any(part.casefold() in BANNED_PARTS for part in Path(path).parts)

def path_has_reserved_site_part(path,site=None):
 site=Path(site or SITE)
 path=Path(path)
 if not path.is_relative_to(site):
  return False
 return any(part.casefold() in RESERVED_SITE_PARTS for part in path.relative_to(site).parts)

def path_has_symlink(path,root):
 # Same walk as tools/build.py: lstat the unresolved path and every parent up to root.
 path=Path(path);root=Path(root)
 cur=path
 while True:
  try:
   mode=cur.lstat().st_mode
  except FileNotFoundError:
   mode=None
  else:
   if stat.S_ISLNK(mode):
    return True
  if cur==root or cur.parent==cur:
   break
  try:
   cur.relative_to(root)
  except ValueError:
   break
  cur=cur.parent
 return False

def iter_site_entries(site):
 site=Path(site)
 for dirpath,dirnames,filenames in os.walk(site,followlinks=False):
  d=Path(dirpath)
  for name in list(dirnames)+list(filenames):
   yield d/name

def site_layout_allowed(path,site=None):
 site=Path(site or SITE)
 path=Path(path)
 if not path.is_relative_to(site):
  return True
 parts=path.relative_to(site).parts
 if len(parts)<=1:
  return True
 if parts[0].casefold() not in {d.casefold() for d in ALLOWED_SITE_DIRS}:
  return False
 if parts[0].casefold()=='library' and len(parts)>=2:
  if parts[1].casefold() not in {d.casefold() for d in ALLOWED_LIBRARY_DIRS}:
   return False
 return True

def main():
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
 for p in iter_site_entries(SITE):
  if path_has_symlink(p,SITE):
   errors.append('Refusing symlink in published site/: '+str(p.relative_to(ROOT)))
 for p in ROOT.rglob('*'):
  if any(x in p.parts for x in SKIP_PARTS):continue
  if p.is_relative_to(SITE) and path_has_symlink(p,SITE):
   errors.append('Refusing symlink in published site/: '+str(p.relative_to(ROOT)));continue
  if not p.is_file():continue
  if path_has_banned_part(p):
   errors.append('Private or personal path in published tree: '+str(p.relative_to(ROOT)));continue
  if p.is_relative_to(SITE) and not site_layout_allowed(p,SITE):
   errors.append('Path is outside the published site layout: '+str(p.relative_to(ROOT)));continue
  if p.stat().st_size>100*1024*1024:errors.append('File exceeds regular Git limit: '+str(p.relative_to(ROOT)))
  if p.suffix.lower() in ['.html','.json','.csv','.md','.py','.yml','.txt']:
   text=p.read_text(encoding='utf-8-sig')
   if private_text_leaks(text):
    errors.append('Potential private export in '+str(p.relative_to(ROOT)))
  if path_has_reserved_site_part(p,SITE):
   errors.append('Private/publisher-restricted folder exported: '+str(p.relative_to(ROOT)))
 size=sum(p.stat().st_size for p in SITE.rglob('*') if p.is_file() and not p.is_symlink())
 if size>=1024**3:errors.append('Published site exceeds GitHub Pages size limit')
 report={'resources':len(catalog),'hosted_files_checked':checked,'publisher_links':sum(x['availability']=='publisher' for x in catalog),'local_links_checked':local_links,'site_bytes':size,'errors':errors}
 print(json.dumps(report,indent=2))
 if errors:return 1
 return 0
if __name__=='__main__':
 raise SystemExit(main())
