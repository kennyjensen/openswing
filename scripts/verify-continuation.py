"""Physical equilibrium continuation and adaptive mode tracking evidence.

Run with OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/verify-continuation.py.
The earlier stability artifact is a pinned regression baseline, not an
independent physical oracle. Circular-arc geometry is derived independently.
"""
import hashlib,json,platform,runpy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import scipy
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.network import solve_static
from openswing.stability import solve_stability

baseline_path=Path('docs/validation/stability.json')
files=[Path(__file__),Path('scripts/modal-benchmark.py'),baseline_path,*sorted(Path('openswing').glob('*.py'))]
provenance=dict(versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),
    source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
checkpoint=Path('.reference/continuation-verification-checkpoint.json')
saved=json.loads(checkpoint.read_text()) if checkpoint.exists() else {}
cache=saved.get('cases',{}) if saved.get('provenance')==provenance else {}


def record(key,compute):
    if key in cache:print('Resumed '+key,flush=True);return cache[key]
    result=compute();cache[key]=result
    temp=checkpoint.with_suffix('.tmp');temp.write_text(json.dumps(dict(provenance=provenance,cases=cache),allow_nan=False));temp.replace(checkpoint)
    print(key+': '+json.dumps(result.get('comparison',{})),flush=True);return result


def circular_arc():
    source='''Name
Independent circular-arc continuation
End
Unit
L 1 m
T 1 s
F 1 N
End
Constant
9.80665 1.225 340.294
End
Reference
2 1 2
End
Ground
1 0 0
End
Beam 1
Inextensible cantilever
 t x y z EIcc EInn GJ EA GKc GKn
0 0 0 0 100 0 0 0 0 0
2 0 2 0 100 0 0 0 0 0
End
'''
    model=parse_asw(source);meshes=[]
    for panels in (12,24):
        seed=None;points=[]
        for angle in (1.,1.5,2.):
            # Uniform end moment EI*angle/L gives a circular arc with R=L/angle.
            result=solve_static(model,panels=panels,gravity=[0,0,0],loads=[dict(beam=1,t=2,moment=[50*angle,0,0])],initial_state=seed)
            exact=np.array([0,2*np.sin(angle)/angle,2*(1-np.cos(angle))/angle]);tip=np.array(result['nodes'][-1]['position'])
            error=float(np.linalg.norm(tip-exact));assert error<.004
            assert result['residual']<1e-8
            np.testing.assert_allclose(result['support_moment'],[-50*angle,0,0],atol=1e-6)
            points.append(dict(angle=angle,exact_tip=exact.tolist(),tip_error=error,result=result));seed=result['equilibrium_state']
        meshes.append(dict(panels=panels,points=points))
    ratios=[b['tip_error']/a['tip_error'] for a,b in zip(meshes[0]['points'],meshes[1]['points'])]
    assert max(ratios)<.26
    return dict(source=source,meshes=meshes,comparison=dict(maximum_error_12=max(p['tip_error'] for p in meshes[0]['points']),
        maximum_error_24=max(p['tip_error'] for p in meshes[1]['points']),error_ratios=ratios))


def adaptive_flutter():
    baseline=json.loads(baseline_path.read_text())['cases']['span80']
    benchmark=runpy.run_path('scripts/modal-benchmark.py');model=benchmark['configuration'](80)
    result=solve_stability(model,FlightCondition(speed=40,alpha=0,mach=0,stall=False),4,gravity=[0,0,0],
        values=[40,45,50],modes=dict(count=8,step=1e-6,rank_tolerance=1e-10),warm_start=True,adaptive=True,
        max_subdivisions=4,max_extra_points=12,
        progress=lambda stage,i,n:print(f'adaptive span80 attempt {i}',flush=True) if stage=='point' else None)
    assert result['converged'] and result['spectrum_complete']
    assert result['tracking_complete'],result['gaps']
    assert result['subdivisions'] and len(result['boundaries'])==1
    boundary=result['boundaries'][0];assert boundary['status']=='resolved'
    assert abs(boundary['value']-baseline['comparison']['computed_critical_speed'])<.005
    errors=[]
    for old in baseline['result']['points']:
        if old['kind']!='grid':continue
        current=next(p for p in result['points'] if p['value']==old['value'] and 'superseded_by' not in p)
        a=np.array([complex(*m['eigenvalue']) for m in old['result']['modes']]);b=np.array([complex(*m['eigenvalue']) for m in current['result']['modes']])
        errors.append(float(max(min(abs(b-r)) for r in a)))
    assert max(errors)<1e-4
    return dict(source=model.dumps(),result=result,comparison=dict(baseline_role='Previously computed cold-solve regression, not independent validation.',
        previous_gaps=len(baseline['result']['gaps']),current_gaps=len(result['gaps']),inserted_points=len(result['subdivisions']),
        superseded_attempts=sum('superseded_by' in p for p in result['points']),maximum_grid_root_change=max(errors),
        previous_critical_speed=baseline['comparison']['computed_critical_speed'],current_critical_speed=boundary['value'],
        independent_2d_reference_speed=baseline['comparison']['independent_2d_critical_speed']))


if __name__=='__main__':
    cases=dict(circular_arc=record('circular_arc',circular_arc),adaptive_span80=record('adaptive_span80',adaptive_flutter))
    Path('docs/validation/continuation.json').write_text(json.dumps(dict(description='Physical steady-state continuation with circular-arc mesh refinement and adaptive finite-span mode tracking.',
        **provenance,cases=cases,limitations=['Local Newton correction is not pseudo-arclength continuation, branch-uniqueness proof or a fold tracker.',
            'Exact source and mesh matching is required; changing conditions, loads, controller parameters and operating targets still requires solving every equation.',
            'Adaptive tracking cannot resolve defective/repeated mode identity, certify unreturned modes, or exclude multiple crossings between samples.',
            'The prior stability artifact is a historical regression reference. ASWING executable and experimental agreement remain unverified.']),indent=2,allow_nan=False)+'\n')
    print('Completed continuation study with '+str(len(provenance['source_sha256']))+' generating hashes.',flush=True)
