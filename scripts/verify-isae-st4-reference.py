"""Refine an independent energy beam for every successfully imported ST-4 model."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import time
import numpy as np
from isae_st4_reference import modes,LENGTH,EA_X,CG_X,EI,GJ,MASS,T0

ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--kernel',type=Path,required=True);p.add_argument('--native',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();sys.path.insert(0,str(a.kernel.resolve()))
    from openswing.asw import parse_asw
    data=json.loads(a.native.read_text());groups={}
    base=ROOT/'.reference/isae-validation'/data['revision']
    for row in data['inputs']:
        if row['status']=='parsed_and_constructed':groups.setdefault(row['sha256'],row['path'])
    out=dict(status='RUNNING',native_input_revision=data['revision'],native_modules=data['modules'],
             script_sha256=sha(__file__),reference_sha256=sha(ROOT/'scripts/isae_st4_reference.py'),runs=[],requested=3*len(groups),
             scope='Independent linear Rayleigh bending/torsion energy integrals. Literal stiffness, mass, rotary inertia and complete point-pylon offsets. No OpenSwing solver, mesh, residual or eigenpencil is used.',
             full_physical_validation=False)
    dest=ROOT/'.reference/isae-st4-independent';dest.mkdir(exist_ok=True)
    for digest,name in groups.items():
        path=base/name;assert sha(path)==digest;model=parse_asw(path.read_text());assert len(model.beams)==1
        beam=model.beams[0];grid=np.linspace(T0,LENGTH,5);g=model.constants[0];assert g==9.81
        for field,value in [('EIcc',EI),('GJ',GJ),('Cea',EA_X),('Cta',EA_X),('Ccg',CG_X),('mg',MASS*g),('x',0.),('y',0.),('mgnn',0.),('Nea',0.),('Nta',0.),('Ncg',0.)]:
            np.testing.assert_allclose(beam.value(field,grid),value,rtol=1e-14,atol=1e-15)
        for field in ['EInn','EA','GKc','GKn']:assert np.all(np.isinf(beam.value(field,grid)))
        np.testing.assert_allclose(beam.value('z',grid),(grid-T0)*LENGTH/(LENGTH-T0),atol=3e-16)
        rotary=float(beam.value('mgcc',.6)/g);assert abs(rotary-.0078)<1e-15 or abs(rotary-.0035)<1e-15
        points=[]
        for row in model.records.get('weight',[]):
            assert row[0]==1 and not np.any(row[6:])
            points.append([float(row[5]/g),*map(float,[row[1],*row[2:5]])])
        for elements in [64,128,256]:
            identity=dict(source_sha256=digest,points=points,rotary=rotary,elements=elements,reference_sha256=out['reference_sha256'])
            key=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest();cache=dest/(key+'.json')
            if cache.exists():r=json.loads(cache.read_text());assert r['identity']==identity
            else:
                start=time.perf_counter();r=dict(identity=identity,result=modes(points,rotary,elements),seconds=time.perf_counter()-start)
                cache.write_text(json.dumps(r,indent=2)+'\n')
            out['runs'].append(dict(source=name,source_sha256=digest,elements=elements,cache=cache.relative_to(ROOT).as_posix(),sha256=sha(cache)))
            a.output.write_text(json.dumps(out,indent=2)+'\n')
            print(len(out['runs']),out['requested'],Path(name).name,elements,flush=True)
    out['status']='INDEPENDENT_REFERENCE_COMPUTED_NOT_PHYSICALLY_VALIDATED';a.output.write_text(json.dumps(out,indent=2)+'\n')


if __name__=='__main__':main()
