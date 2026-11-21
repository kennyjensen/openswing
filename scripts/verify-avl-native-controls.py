"""Small serial native-AVL force controls, independent of OpenSwing.

Each case retains the original binary output, input geometry and command stream.
These are diagnostic references, never additions to ISAE pass denominators.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'artifacts/isae/avl-native-build-20261108'


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def utc(): return datetime.now(timezone.utc).isoformat()
def write(p, value): p.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def prepare(out):
    assert not out.exists(), out
    v = json.loads((BUILD/'verification.json').read_text())
    assert sha(BUILD/'avl') == v['binary_sha256']
    out.mkdir(parents=True)
    cases = []
    for geometry in ['rectangle', 'swept', 'winglets']:
        for nc, ns in [(1,16), (2,16), (4,16), (8,16), (8,32)]:
            cases.append(dict(id=f'{geometry}-c{nc}-s{ns}', geometry=geometry,
                              nchord=nc, nspan=ns, alpha=5., sweep=30. if geometry=='swept' else 0., legs=False))
    cases += [dict(id='rectangle-zero',geometry='rectangle',nchord=8,nspan=32,alpha=0.,sweep=0.,legs=False),
              dict(id='winglets-negative',geometry='winglets',nchord=8,nspan=32,alpha=-5.,sweep=0.,legs=False),
              dict(id='swept-reflected',geometry='swept',nchord=8,nspan=32,alpha=5.,sweep=-30.,legs=False),
              dict(id='swept-leg-forces',geometry='swept',nchord=8,nspan=32,alpha=5.,sweep=30.,legs=True)]
    plan = dict(observed_utc=utc(), previous_turn='progress: eight authoritative PDFs verified; source policy made persistent',
                binary=str((BUILD/'avl').relative_to(ROOT)), binary_sha256=sha(BUILD/'avl'),
                build_verification_sha256=sha(BUILD/'verification.json'), cases=cases,
                geometry='10 m projected horizontal span, 1 m streamwise chord; winglets extend 1 m upwards at both ends. One continuous surface and component; sectionwise cosine span spacing. Swept case is a straight oblique parallelogram, not a mirrored V planform.',
                flow='Mach=0, beta=0, no rotation, flat sections; alpha acts on freestream, wake remains body-x aligned as native AVL specifies.',
                forces='Native default bound-vortex force plus a separate native trailing-leg option control. Geometric axes. No viscous input.',
                exclusions='Not the previous local-chord Gaunaa geometry, not an ASWING replacement, not SA-11 validation.',
                unchanged_pins=json.loads((BUILD/'plan.json').read_text())['unchanged_pins'])
    write(out/'plan.json',plan)
    shutil.copyfile(__file__,out/'driver-used.py')
    print(json.dumps(dict(status='prepared',cases=len(cases))))


def model(c):
    slope=math.tan(math.radians(c['sweep']));ns=c['nspan']
    sections=[(-5.,0.,ns),(5.,0.,0)]
    if c['geometry']=='winglets':sections=[(-5.,1.,ns//4),(-5.,0.,ns),(5.,0.,ns//4),(5.,1.,0)]
    lines=[c['id'],'0.0','0 0 0.0','10.0 1.0 10.0','0.25 0.0 0.0','0.0',
           'SURFACE','Continuous test surface',f"{c['nchord']} 1.0",'COMPONENT','1']
    for y,z,n in sections:
        lines += ['SECTION',f'{slope*y:.17g} {y:.17g} {z:.17g} 1.0 0.0'+(f' {n} 1.0' if n else '')]
    return '\n'.join(lines)+'\n'


def labeled(path):
    result={}
    for line in path.read_text().splitlines():
        if '|' not in line:continue
        left,right=line.split('|',1)
        try:values=[float(x) for x in left.split()]
        except ValueError:continue
        result[right.strip()]=values
    return result


def parse(directory,c):
    total=labeled(directory/'total.txt')
    result={}
    for key in ['CXtot, Cltot, Cl\'tot','CYtot, Cmtot','CZtot, Cntot, Cn\'tot',
                'CLtot','CDtot','CDvis, CDind','Trefftz Plane: CLff, CDff, CYff, e']:
        names=key.removeprefix('Trefftz Plane: ').split(', ')
        for name,value in zip(names,total[key],strict=True):result[name]=value
    assert total['Alpha, pb/2V, p\'b/2V'][0]==c['alpha']
    nstrips=c['nspan']*(1.5 if c['geometry']=='winglets' else 1)
    assert total['# strips']==[nstrips]
    assert total['# vortices']==[nstrips*c['nchord']]
    assert 'Geometric' in (directory/'total.txt').read_text()
    # Native body-strip output carries five-digit geometry/forces. Its original
    # rounding is retained; use a separate full-precision total export above.
    strips=[]
    for line in (directory/'body-strips.txt').read_text().splitlines():
        fields=line.split()
        if len(fields)!=16 or not fields[0].isdigit():continue
        strips.append([float(x) for x in fields])
    a=np.asarray(strips);assert a.shape==(int(nstrips),16),a.shape
    r=a[:,1:4]-[.25,0,0];chord=a[:,4];area=a[:,5]
    force=a[:,8:11]*area[:,None]/10
    torque=(a[:,11:14]*chord[:,None]*area[:,None]/10+np.cross(r,force))
    cf=force.sum(axis=0);cm=torque.sum(axis=0)/[10,1,10]
    expected_f=np.array([result[k] for k in ['CXtot','CYtot','CZtot']])
    expected_m=np.array([result[k] for k in ['Cltot','Cmtot','Cntot']])
    # This checks exported accounting, not independent physical correctness.
    error=max(float(np.max(abs(cf-expected_f))),float(np.max(abs(cm-expected_m))))
    assert error<2e-5,error
    assert result['CDvis']==0.
    assert all(math.isfinite(x) for x in result.values())
    near_far=(result['CDind']/result['CDff']-1)*100 if result['CDff']>1e-15 else None
    return dict(coefficients=result, near_far_drag_difference_percent=near_far,
                body_strips=strip_names(), strip_data=strips,
                rounded_strip_reconstruction_max_error=error,
                max_abs_strip_normal_coefficient=float(np.max(abs(a[:,14]))),
                max_abs_strip_pitch_coefficient=float(np.max(abs(a[:,12]))),
                strips=int(nstrips), vortices=int(nstrips*c['nchord']))


def strip_names():return ['j','x_c4','y','z','chord','area','dihedral','incidence','cfx','cfy','cfz','cmx','cmy','cmz','cn','ca']


def supplement(out,parent):
    assert not out.exists(),out
    base=json.loads((parent/'plan.json').read_text())
    selected=[c for c in base['cases'] if c['id'] in [f'{g}-c8-s32' for g in ['rectangle','swept','winglets']]]
    assert len(selected)==3
    cases=[]
    for c in selected:
        for nc,ns in [(8,64),(16,32)]:
            cases.append(dict(c,id=f"{c['geometry']}-c{nc}-s{ns}",nchord=nc,nspan=ns))
        cases.append(dict(c,id=c['geometry']+'-alpha1',alpha=1.))
    c=next(c for c in selected if c['geometry']=='winglets')
    cases.append(dict(c,id='winglets-alpha-minus1',alpha=-1.))
    plan=dict(base,cases=cases,observed_utc=utc(),parent_plan=str((parent/'plan.json').relative_to(ROOT)),
              parent_plan_sha256=sha(parent/'plan.json'),
              reason='Initial grids leave sweep moment and near/far drag differences; refine each mesh direction separately and check angle scaling. All native cases remain at or below 768 vortices.')
    out.mkdir(parents=True);write(out/'plan.json',plan);shutil.copyfile(__file__,out/'driver-used.py')
    print(json.dumps(dict(status='prepared-supplement',cases=len(cases))))


def run(out,index):
    plan=json.loads((out/'plan.json').read_text());c=plan['cases'][index]
    binary=ROOT/plan['binary'];assert sha(binary)==plan['binary_sha256']
    directory=out/c['id'];assert not directory.exists();directory.mkdir()
    (directory/'model.avl').write_text(model(c))
    commands='LOAD model.avl\nOPER\nO\nA\n'+('T\n' if c['legs'] else '')+'\n'
    commands+=f"A A {c['alpha']}\nX\nMRF\nFT total.txt\nFS strips.txt\nFSB body-strips.txt\nFE elements.txt\n\nQUIT\n"
    (directory/'commands.txt').write_text(commands)
    t=time.monotonic()
    process=subprocess.run([str(binary)],input=commands,text=True,capture_output=True,cwd=directory,timeout=40)
    seconds=time.monotonic()-t
    (directory/'stdout.txt').write_text(process.stdout);(directory/'stderr.txt').write_text(process.stderr)
    write(directory/'process.json',dict(observed_utc=utc(),returncode=process.returncode,seconds=seconds,binary_sha256=plan['binary_sha256']))
    assert process.returncode==0,process.stderr
    parsed=parse(directory,c)
    write(directory/'result.json',dict(case=c,observed_utc=utc(),seconds=seconds,**parsed,
        artifacts={str(p.name):sha(p) for p in sorted(directory.iterdir()) if p.is_file()}))
    print(json.dumps(dict(id=c['id'],seconds=seconds,CL=parsed['coefficients']['CLtot'],
                        CD=parsed['coefficients']['CDind'],CDff=parsed['coefficients']['CDff'],
                        Cm=parsed['coefficients']['Cmtot'],near_far_percent=parsed['near_far_drag_difference_percent'])))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    g=p.add_mutually_exclusive_group(required=True);g.add_argument('--prepare',action='store_true');g.add_argument('--case',type=int)
    g.add_argument('--refinement-of',type=Path)
    a=p.parse_args();out=a.output.resolve()
    if a.prepare:prepare(out)
    elif a.refinement_of:supplement(out,a.refinement_of.resolve())
    else:run(out,a.case)


if __name__=='__main__':main()
