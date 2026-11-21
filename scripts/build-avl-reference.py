"""Serial local AVL 3.52 reference build; no system installation.

The original numerical routines and plotting library are retained. Only the
two declared vortex-capacity constants are reduced to 1024 for bounded RAM.
Run prepare, then numbered four-file batches, then link.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
UPSTREAM=ROOT/'.reference/avl-native-20261108/source/AVL3.52rel09032025'
HEADERS=ROOT/'.reference/avl-native-20261108/dependencies/headers-python/usr/include'
XLIB=Path('/usr/lib/aarch64-linux-gnu/libX11.so.6')


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def utc():return datetime.now(timezone.utc).isoformat()
def write(p,x):p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')


def prepare(out):
    if out.exists():raise ValueError('Prepare needs a fresh output directory.')
    assert (HEADERS/'X11/Xlib.h').is_file() and XLIB.is_file()
    upstream_meta=json.loads((ROOT/'.reference/avl-native-20261108/SOURCE.json').read_text())
    assert upstream_meta['archive_sha256']==sha(ROOT/'.reference/avl-native-20261108/avl3.52.tgz')
    out.mkdir(parents=True);(out/'objects').mkdir();(out/'logs').mkdir()
    source=out/'source';source.mkdir()
    original={}
    for folder in ('src','plotlib','eispack'):
        for p in sorted((UPSTREAM/folder).rglob('*')):
            if p.is_file():
                name=p.relative_to(UPSTREAM);target=source/name
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(p.read_bytes());original[str(name)]=sha(p)
    changes=[]
    for name,old,new in [('src/ADIMEN.INC','NVMAX=5000','NVMAX=1024'),
                         ('src/avl_heap_inc.f90','NVX=5000','NVX=1024')]:
        p=source/name;text=p.read_text();assert text.count(old)==1
        p.write_text(text.replace(old,new))
        changes.append(dict(path=name,old=old,new=new,original_sha256=original[name],build_sha256=sha(p)))
    make=(UPSTREAM/'bin/Makefile.gfortranDP').read_text().replace('\\\n',' ')
    objects=re.search(r'^AOBJS\s*=\s*(.*)$',make,re.M).group(1).split()
    units=[]
    for obj in objects:
        stem=Path(obj).stem
        name=('second_g77.f' if stem=='second' else stem+('.f90' if stem.startswith('avl_heap') else '.f'))
        units.append(dict(source='src/'+name,object=obj,kind='double'))
    units += [dict(source='src/matrix-lapackdp.f',object='matrix-lapackdp.o',kind='double'),
              dict(source='src/matrix-lapacksubs.f',object='matrix-lapacksubs.o',kind='default'),
              dict(source='eispack/eispack.f',object='eispack.o',kind='default')]
    for stem in ('plt_base','plt_font','plt_util','plt_color','set_subs','gw_subs','ps_subs',
                 'pdf_subs','plt_old','plt_3D'):
        units.append(dict(source='plotlib/'+stem+'.f',object=stem+'.o',kind='double'))
    units += [dict(source='plotlib/pdf/hpdf-stubs.f',object='hpdf-stubs.o',kind='double'),
              dict(source='plotlib/xwin11/Xwin2.c',object='Xwin2.o',kind='c')]
    for u in units:assert (source/u['source']).is_file(),u
    plan=dict(observed_utc=utc(),previous_turn='progress: continuous attached-force audit isolated sampling error and verified a global drag identity',
        upstream=upstream_meta,source_original_pins=original,
        source_build_pins={str(p.relative_to(source)):sha(p) for p in sorted(source.rglob('*')) if p.is_file()},
        changes=changes,units=units,batch_size=4,batches=(len(units)+3)//4,
        fortran_flags=['-O1','-std=legacy','-fallow-argument-mismatch','-fcheck=bounds'],
        double_flags=['-fdefault-real-8'],c_flags=['-O1','-std=gnu89','-DUNDERSCORE','-DDBL_ARGS'],
        compiler=subprocess.run(['gfortran','--version'],check=True,text=True,capture_output=True).stdout.splitlines()[0],
        x11_library=str(XLIB),x11_sha256=sha(XLIB),
        dependency_manifest_sha256=sha(ROOT/'.reference/avl-native-20261108/dependencies/SOURCE.json'),
        unchanged_pins={str(p.relative_to(ROOT)):sha(p) for p in sorted(ROOT.glob('openswing/**/*.py'))+
                       [ROOT/'docs/validation/ISAE_STATUS.md',ROOT/'docs/validation/isae-progress-scopes.json']},
        scope='Native complete console AVL with upstream X11 plotting library; capacity change only. Not ASWING and not a production runtime dependency.')
    write(out/'plan.json',plan);shutil.copyfile(__file__,out/'build-driver-used.py')
    print(json.dumps(dict(status='prepared',units=len(units),batches=plan['batches'],capacity=1024)))


def check(plan,out):
    for name,pin in plan['source_build_pins'].items():assert sha(out/'source'/name)==pin,name
    for name,pin in plan['unchanged_pins'].items():assert sha(ROOT/name)==pin,name
    assert sha(XLIB)==plan['x11_sha256']


def build(out,batch):
    plan=json.loads((out/'plan.json').read_text());check(plan,out)
    log=out/'logs'/f'batch-{batch:02d}.json'
    if log.exists():raise ValueError('Batch record already exists; do not overwrite a prior attempt.')
    start=batch*plan['batch_size'];units=plan['units'][start:start+plan['batch_size']]
    assert units
    for u in plan['units'][:start]:assert (out/'objects'/u['object']).is_file(),u
    results=[]
    for u in units:
        src=out/'source'/u['source'];obj=out/'objects'/u['object']
        assert not obj.exists(),obj
        if u['kind']=='c':
            cmd=['gcc',*plan['c_flags'],'-I'+str(HEADERS),'-c',str(src),'-o',str(obj)]
        else:
            cmd=['gfortran',*plan['fortran_flags']]
            if u['kind']=='double':cmd += plan['double_flags']
            cmd += ['-I'+str(src.parent),'-I'+str(out/'source/src'),'-I'+str(out/'source/plotlib'),
                    '-I'+str(out/'objects'),'-J'+str(out/'objects'),'-c',str(src),'-o',str(obj)]
        started=time.monotonic()
        result=subprocess.run(cmd,cwd=out/'objects',capture_output=True,text=True,timeout=45)
        record=dict(unit=u,command=cmd,returncode=result.returncode,seconds=time.monotonic()-started,
                    stdout=result.stdout,stderr=result.stderr,observed_utc=utc())
        if obj.exists():record['object_sha256']=sha(obj)
        results.append(record)
        write(log,dict(status='running' if result.returncode==0 else 'failed',records=results))
        print(json.dumps({k:record[k] for k in ('unit','returncode','seconds')}),flush=True)
        if result.returncode:raise RuntimeError(result.stderr[-4000:])
    write(log,dict(status='complete',records=results));check(plan,out)


def link(out):
    plan=json.loads((out/'plan.json').read_text());check(plan,out)
    binary=out/'avl';assert not binary.exists()
    objects=[]
    for batch in range(plan['batches']):
        record=json.loads((out/'logs'/f'batch-{batch:02d}.json').read_text());assert record['status']=='complete'
        for r in record['records']:
            p=out/'objects'/r['unit']['object'];assert sha(p)==r['object_sha256'];objects.append(str(p))
    cmd=['gfortran','-o',str(binary),*objects,str(XLIB)]
    result=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
    write(out/'link.json',dict(observed_utc=utc(),command=cmd,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr))
    assert result.returncode==0,result.stderr
    smoke=subprocess.run([str(binary)],input='QUIT\n',capture_output=True,text=True,timeout=15,cwd=out)
    (out/'smoke.stdout').write_text(smoke.stdout);(out/'smoke.stderr').write_text(smoke.stderr)
    assert smoke.returncode==0,(smoke.returncode,smoke.stderr)
    write(out/'verification.json',dict(observed_utc=utc(),status='built-and-smoke-tested',binary_sha256=sha(binary),
        plan_sha256=sha(out/'plan.json'),smoke_returncode=smoke.returncode,unchanged_pin_count=len(plan['unchanged_pins']),
        artifacts={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()}))
    print(json.dumps(dict(status='built-and-smoke-tested',binary=str(binary),sha256=sha(binary))))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--prepare',action='store_true');group.add_argument('--batch',type=int);group.add_argument('--link',action='store_true')
    args=parser.parse_args();out=args.output.resolve()
    if args.prepare:prepare(out)
    elif args.link:link(out)
    else:build(out,args.batch)


if __name__=='__main__':main()
