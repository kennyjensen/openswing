"""Serial, resource-capped replay of all six published ST-2 ASWING curves.

The explicit tip-pylon reconstruction is retained as a qualified comparison,
not a literal-file solve. No model coefficient is fitted to a curve.
"""
import argparse
from pathlib import Path
import resource
import time

import verify_sa14_defaults as common

ROOT = common.ROOT
PILOT = ROOT/'artifacts/isae/st2-static-pilot-20261109'
CASES = {
    'torsion-off': dict(kind='torsion',skin=0,nominal=38,x=-.09),
    'torsion-on': dict(kind='torsion',skin=1,nominal=38,x=-.13),
    'bending': dict(kind='bending',skin=0,nominal=39,x=.05),
}


def prepare(out):
    prior=common.read(PILOT/'plan.json');common.authenticate(prior['pins'])
    out.mkdir(parents=True,exist_ok=True);pins=dict(prior['pins'])
    for p in (Path(__file__),PILOT/'plan.json',ROOT/'reference/aswing_doc.txt',
              ROOT/'reference/aswing-authoritative-20261108/drela-aswing-steady.txt'):
        pins[p.relative_to(ROOT).as_posix()]=common.sha(p)
    curves=prior['curves'];cases={};jobs=[]
    for name,config in CASES.items():
        selected={k:c for k,c in curves.items() if c['kind']==config['kind'] and
                  (config['kind']=='bending' or c['skin']==config['skin'])}
        masses=sorted({r['mass_kg'] for c in selected.values() for r in c['targets']})
        assert masses[0]==0.
        cases[name]=dict(**config,masses=masses,curves=list(selected))
        # Start with zero and maximum load in each configuration; neither is
        # selected by predicted error. Interior loads remain required below.
        for mass in (0.,masses[-1]):jobs.append(dict(case=name,mass_kg=mass,nominal=config['nominal'],scope='curve'))
    for name,c in cases.items():
        for mass in (0.,c['masses'][-1]):jobs.append(dict(case=name,mass_kg=mass,nominal=2*c['nominal']+1 if name=='bending' else 2*c['nominal']+2,scope='refinement'))
    for name,c in cases.items():
        for mass in c['masses'][1:-1]:jobs.append(dict(case=name,mass_kg=mass,nominal=c['nominal'],scope='curve'))
    assert len(jobs)==47 and sum(len(c['masses']) for c in cases.values())==41
    common.write(out/'plan.json',dict(observed_utc=common.utc(),pins=pins,cases=cases,curves=curves,jobs=jobs,
        required_ordinates=77,relative_tolerance=.05,mesh_relative_gate=.01,
        limits=prior['limits'],archive_scope_changed=False,
        protocol='All six published ASWING curves, preserving their original points including repeated conditions. '
            '41 unique load states with40 nodes and three paired zero/max refinements with80 nodes. '
            'Cosine spacing; torsion meshes insert the exact .52 property break. '
            'Original properties and MATLAB load coordinates, two equal weights on a rigid pylon at t=.55; '
            'physical y=.558 retained. This does not recover native out-of-domain t=.558 handling. '
            'Displacement is minus loaded-minus-unloaded tip z. Twist is minus local section twist, without subtracting its unloaded value. '
            'No experiment or UM/NAST ordinates used as targets; no mesh-repeat votes.'))
    print('Prepared47 serial states for77 published ordinates; original archive scope unchanged.')


def run(out,index):
    plan=common.read(out/'plan.json');common.authenticate(plan['pins']);job=plan['jobs'][index]
    config=plan['cases'][job['case']];folder=out/f'job-{index:02d}';folder.mkdir()
    from isae_st2 import static_model,observables
    from openswing.bridge import dispatch
    import numpy as np
    mass=job['mass_kg'];_,source,reconstruction=static_model(config['kind'],config['skin'],mass,'archive_pylon')
    request=dict(action='solve',mode='structural',source=source,
        panels=dict(default=job['nominal'],beams={'1':dict(count=job['nominal'],spacing='cosine')}),
        numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator='drela-steady-section-v1'),
        gravity=[0.,0.,-9.81],loads=[],tolerance=1e-8,continuation_steps=4)
    common.write(folder/'request.json',request);started=time.monotonic();result=dispatch(request)
    seconds=time.monotonic()-started;common.write(folder/'result.json',result)
    nodes=sorted(result['nodes'],key=lambda n:n['t']);expected=40 if job['scope']=='curve' else 80
    assert len(nodes)==expected and nodes[0]['t']==.0001 and nodes[-1]['t']==.55
    if config['kind']=='torsion':assert .52 in [n['t'] for n in nodes]
    r=np.asarray([n['position'] for n in nodes]);q=np.asarray(nodes[-1]['rotation'])
    # Straight jig, constant mass/length and zero CG offset in both source files.
    # Integrate endpoint gravity and independently rotate the original tip arm.
    lengths=np.array([e['length'] for e in result['elements']]);assert abs(sum(lengths)-.55)<1e-12
    lumped=np.zeros(len(nodes));lumped[:-1]+=.3745*lengths/2;lumped[1:]+=.3745*lengths/2
    f=lumped[:,None]*np.array([0.,0.,-9.81]);point=r[-1]+q@np.array([config['x'],.008,0.])
    force=f.sum(axis=0)+[0.,0.,-9.81*mass]
    moment=np.cross(r,f).sum(axis=0)+np.cross(point,[0.,0.,-9.81*mass])
    checks=dict(residual=result['residual'],force_balance=float(np.max(abs(np.asarray(result['force_balance'])))),
        moment_balance=float(np.max(abs(np.asarray(result['moment_balance'])))),
        gravity_force=float(np.max(abs(np.asarray(result['applied_force'])-force))),
        gravity_moment=float(np.max(abs(np.asarray(result['applied_moment'])-moment))),
        clamp_position=float(np.max(abs(r[0]))),clamp_rotation=float(np.max(abs(np.asarray(nodes[0]['rotation'])-np.eye(3)))))
    assert result['converged'] and max(checks.values())<1e-7
    common.authenticate(plan['pins'])
    report=dict(observed_utc=common.utc(),job=job,checks=checks,reconstruction=reconstruction,
        observable=observables(r[-1],q),tip_position=r[-1].tolist(),seconds=seconds,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        plan_sha256=common.sha(out/'plan.json'),artifacts={p.name:common.sha(p) for p in folder.iterdir()})
    common.write(folder/'report.json',report)
    print(dict(index=index,**job,observable=report['observable'],seconds=seconds),flush=True)


def summarize(out):
    plan=common.read(out/'plan.json');common.authenticate(plan['pins']);reports=[]
    for i,job in enumerate(plan['jobs']):
        folder=out/f'job-{i:02d}';r=common.read(folder/'report.json')
        assert r['job']==job and r['plan_sha256']==common.sha(out/'plan.json')
        for p,h in r['artifacts'].items():assert common.sha(folder/p)==h
        reports.append(r)
    def state(case,mass,scope):
        selected=[r for r in reports if r['job']['case']==case and r['job']['mass_kg']==mass and r['job']['scope']==scope]
        assert len(selected)==1;return selected[0]['observable']
    rows=[];mesh=[]
    for case,c in plan['cases'].items():
        for scope in ('curve','refinement'):
            zero=state(case,0.,scope);loaded=state(case,c['masses'][-1],scope)
            values=dict(displacement_m=-(loaded['z_m']-zero['z_m']),twist_deg=-loaded['twist_asw_deg'])
            if scope=='curve':coarse=values
            else:
                for quantity in ('displacement_m','twist_deg'):
                    delta=abs(values[quantity]-coarse[quantity])/max(abs(values[quantity]),1e-8)
                    mesh.append(dict(case=case,quantity=quantity,coarse=coarse[quantity],fine=values[quantity],
                        change_percent=100*delta,passed=delta<plan['mesh_relative_gate']))
        zero=state(case,0.,'curve')
        for name in c['curves']:
            curve=plan['curves'][name]
            for target in curve['targets']:
                value=state(case,target['mass_kg'],'curve')
                predicted=-(value['z_m']-zero['z_m']) if curve['quantity']=='displacement_m' else -value['twist_asw_deg']
                error=abs(predicted-target['expected']);gate=max(target['original_absolute_tolerance'],.05*abs(target['expected']))
                rows.append(dict(curve=name,case=case,**target,predicted=predicted,error=error,gate=gate,passed=error<=gate,
                    error_percent=100*error/abs(target['expected']) if abs(target['expected'])>target['original_absolute_tolerance'] else None))
    summary=dict(observed_utc=common.utc(),required=len(rows),passed=sum(r['passed'] for r in rows),rows=rows,mesh_checks=mesh,
        numerical_pass=True,mesh_pass=all(r['passed'] for r in mesh),archive_passes_added=0,
        curves={name:dict(required=sum(r['curve']==name for r in rows),passed=sum(r['curve']==name and r['passed'] for r in rows),
                    max_error_percent=max((r['error_percent'] or 0) for r in rows if r['curve']==name)) for name in plan['curves']},
        solver_seconds=sum(r['seconds'] for r in reports),peak_rss_kib=max(r['peak_rss_kib'] for r in reports),
        qualification='All original ordinates retained; conditional explicit tip-pylon reconstruction, not recovered native anchor handling.')
    common.write(out/'summary.json',summary);print({k:v for k,v in summary.items() if k not in ('rows',)})


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run','summarize']);p.add_argument('--output',type=Path,required=True);p.add_argument('--index',type=int)
    a=p.parse_args()
    if a.action=='prepare':prepare(a.output)
    elif a.action=='summarize':summarize(a.output)
    else:common.bounded();run(a.output,a.index)


if __name__=='__main__':main()
