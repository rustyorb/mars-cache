"""Prepare a personal offline cache while the internet is still available.

Publisher-restricted chapters are downloaded by the owner directly from their
publishers. They are not included in the public repository or release archive.
"""
import argparse,hashlib,json,os,re,shutil,subprocess,sys,venv
from datetime import datetime,timezone
from pathlib import Path
from html import escape

KIT=Path(__file__).resolve().parents[1]
def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()

def main():
 parser=argparse.ArgumentParser(description='Download and verify your own offline MARS CACHE.')
 parser.add_argument('--destination',type=Path,default=Path.home()/'MARS-CACHE-Personal')
 parser.add_argument('--check-only',action='store_true',help='Check the download plan without creating files or downloading.')
 args=parser.parse_args();dest=args.destination.expanduser().resolve()
 if dest.is_relative_to(KIT):raise SystemExit('Choose a personal cache folder outside the public project/download folder.')
 plan=json.loads((KIT/'data/personal-download-plan.json').read_text(encoding='utf-8'))
 from urllib.parse import urlparse
 for x in plan:
  if not re.fullmatch('[a-f0-9]{12}',x['id']):raise SystemExit('Invalid resource identifier in plan.')
  host=urlparse(x['url']).hostname or ''
  if urlparse(x['url']).scheme!='https' or not (host.endswith(('.gov','.edu','.amazonaws.com','.hesperian.org')) or host=='hesperian.org'):raise SystemExit('Unexpected source in download plan: '+host)
 ids={x['id'] for x in plan}
 if len(ids)!=len(plan):raise SystemExit('Duplicate resource identifiers in plan.')
 core=KIT/'site' if (KIT/'site/catalog.json').exists() else KIT
 core_records=json.loads((core/'catalog.json').read_text(encoding='utf-8'))
 core_by_id={x['id']:x for x in core_records if x['availability']=='hosted' and x['format']=='PDF'}
 if args.check_only:
  print(json.dumps({'planned_resources':len(plan),'local_PDF_seeds':len(core_by_id),'destination':str(dest),'writes_or_downloads':False},indent=2));return 0
 print('MARS CACHE — preparing your personal offline library',flush=True)
 print(f'{len(plan)} references and chapter files. Keep the internet connected until the final report.',flush=True)
 dest.mkdir(parents=True,exist_ok=True)
 existing=json.loads((dest/'catalog.json').read_text(encoding='utf-8')) if (dest/'catalog.json').exists() else []
 current={x['id']:x for x in existing}
 seeded=0
 for item in plan:
  x=core_by_id.get(item['id'])
  if not x or item['id'] in current:continue
  source=(core/x['href']).resolve()
  if not source.is_relative_to(core) or not source.exists() or digest(source)!=item.get('expected_source_sha256'):continue
  target=(dest/x['href']).resolve()
  if not target.is_relative_to(dest):raise SystemExit('Invalid local destination in catalog.')
  target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
  record=dict(item)
  record.update(status='collected',format='PDF',local_path=x['href'],original_path=x['href'],bytes=source.stat().st_size,sha256=digest(source),pages=x['pages'],retrieved_utc=x['retrieved_utc'],validation='Seeded from the public offline core; original document SHA-256 matched.')
  current[item['id']]=record;seeded+=1
 (dest/'catalog.json').write_text(json.dumps(list(current.values()),indent=2,ensure_ascii=False),encoding='utf-8')
 (dest/'collection-plan.json').write_text(json.dumps(plan,indent=2,ensure_ascii=False),encoding='utf-8')
 print(f'Reused {seeded} reference PDFs from the downloaded core.',flush=True)
 env_dir=dest/'.preparation-tools/venv'
 python=env_dir/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
 if not python.exists():
  print('Setting up the isolated preparation tools…',flush=True)
  venv.EnvBuilder(with_pip=True).create(env_dir)
 requirements=KIT/'tools/personal-requirements.txt'
 subprocess.run([str(python),'-m','pip','install','--disable-pip-version-check','--quiet','-r',str(requirements)],check=True)
 env=os.environ.copy();env['MARS_CACHE_COLLECTION']=str(dest)
 for name,extra in [('collect.py',['--retry-unavailable']),('build_library.py',[]),('verify.py',[str(dest)])]:
  subprocess.run([str(python),str(KIT/'tools/offline'/name),*extra],cwd=dest,env=env,check=True)
 results=json.loads((dest/'catalog.json').read_text(encoding='utf-8'))
 saved={x['id']:x for x in results if x.get('status')=='collected'}
 missing=[dict(id=x['id'],title=x['title'],source=x['url'],error=next((r.get('error','Not collected') for r in results if r['id']==x['id']),'Not collected')) for x in plan if x['id'] not in saved]
 report={'checked_utc':datetime.now(timezone.utc).isoformat(),'expected':len(plan),'saved':len(ids & set(saved)),'missing':missing,'ready_for_offline_use':not missing}
 (dest/'OFFLINE-READINESS.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
 heading='Offline collection complete' if not missing else 'Preparation incomplete — some files are missing'
 details=''.join(f"<li>{escape(x['title'])}: {escape(x['error'])}</li>" for x in missing)
 html=f"<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>MARS CACHE — Offline readiness</title><style>body{{max-width:850px;padding:30px;margin:auto;font:18px/1.7 system-ui;background:#f4f1e8;color:#222a23}}</style><h1>{heading}</h1><p>{report['saved']} of {report['expected']} reference/chapter files are saved locally and passed file-integrity checks.</p><p>Open the library with Wi-Fi and mobile data off to practice using it. Store another copy on your backup drive. Current weather, fallout and road conditions still require external observations.</p><ul>{details}</ul><p><a href='index.html'>Open your personal offline library</a></p></html>"
 (dest/'OFFLINE-READINESS.html').write_text(html,encoding='utf-8')
 print('\n'+heading,flush=True)
 print(f"{report['saved']} of {report['expected']} saved. Open: {dest/'OFFLINE-READINESS.html'}",flush=True)
 if missing:
  print('Keep the missing-file report. Run preparation again while online to retry missing items.',flush=True)
  return 2
 return 0

if __name__=='__main__':
 try:sys.exit(main())
 except subprocess.CalledProcessError as e:raise SystemExit(f'Preparation stopped during a tool step (exit {e.returncode}). Existing downloaded files were retained; run preparation again while online.')
