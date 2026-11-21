"""Foreground owner for one fresh current-kernel unloaded study."""
import hashlib,json,os,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
MAIN=Path('/home/userland/aswing')
PINS=json.loads((ROOT/'source-pins.json').read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def identity(pid):
 p=Path(f'/proc/{pid}/stat')
 if not p.exists():return None
 f=p.read_text().rsplit(')',1)[1].split()
 return dict(pid=pid,state=f[0],start_ticks=int(f[19]),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
def pins():
 for p,h in PINS.items():
  if sha(p)!=h:raise RuntimeError('Pinned dependency changed: '+p)
def save(record):
 p=ROOT/'state.json';temp=p.with_suffix('.json.part');temp.write_text(json.dumps(record,indent=2)+'\n');temp.replace(p)
command=[str(MAIN/'.venv/bin/python'),str(MAIN/'scripts/verify-durrant-unloaded.py'),'--plan',str(ROOT/'plan.json'),'--output',str(ROOT/'results'),'--native','compute','--kernel-root',str(MAIN)]
record=dict(status='running',started=time.time(),command=command,working_directory=str(MAIN),wrapper=identity(os.getpid()),source_pins_sha256=sha(ROOT/'source-pins.json'),plan_sha256=sha(ROOT/'plan.json'),environment={'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'},native_cache_policy='compute three fresh cases; no saved input records in plan')
child=None;code=1
try:
 if (ROOT/'results').exists():raise RuntimeError('Fresh results directory required')
 pins();save(record)
 env=os.environ.copy();env.update(record['environment'])
 with (ROOT/'study.log').open('w') as log:
  child=subprocess.Popen(command,cwd=MAIN,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
  record['child']=identity(child.pid);save(record)
  print(json.dumps({'status':'launched','wrapper':record['wrapper'],'child':record['child'],'state':str(ROOT/'state.json')}),flush=True)
  while True:
   try:code=child.wait(timeout=30);break
   except subprocess.TimeoutExpired:
    record['updated']=time.time();p=ROOT/'results/run.json'
    if p.exists():
     run=json.loads(p.read_text());record.update(phase=run.get('phase'),completed_cases=len(run['cases']),native_cases=list(run['native_cases']))
    save(record)
 record['child_exit_code']=code;pins()
 if sha(ROOT/'plan.json')!=record['plan_sha256']:raise RuntimeError('Plan changed during run')
 if code:raise RuntimeError('Study exited '+str(code))
 run=json.loads((ROOT/'results/run.json').read_text())
 if run['status']!='computed' or len(run['cases'])!=12 or len(run['native_cases'])!=3:raise RuntimeError('Expected all12 reference and3 fresh native cases')
 for e in run['cases']+list(run['native_cases'].values()):
  if sha(ROOT/'results'/e['file'])!=e['sha256']:raise RuntimeError('Artifact hash mismatch')
 record.update(status='completed',completed_cases=12,native_cases=list(run['native_cases']),run_sha256=sha(ROOT/'results/run.json'),log_sha256=sha(ROOT/'study.log'),pinned_dependencies_unchanged=True)
except BaseException as error:
 record.update(status='incomplete' if isinstance(error,KeyboardInterrupt) else 'failed',error=repr(error))
 if child is not None and child.poll() is None:
  child.terminate()
  try:child.wait(timeout=10)
  except subprocess.TimeoutExpired:child.kill();child.wait()
 code=1
finally:
 record.update(ended=time.time(),wrapper_exit_code=code,child_exit_code=None if child is None else child.returncode);save(record)
 print(json.dumps({'status':record['status'],'exit_code':code,'state':str(ROOT/'state.json')}),flush=True)
sys.exit(code)
