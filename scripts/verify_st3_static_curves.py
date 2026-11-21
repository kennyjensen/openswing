"""Fresh serial ST-3 replay of the source scripts' nonnegative plotted branch.

Read ASWING's red EPS markers, not experimental ordinates or clipped line
vertices. Preserve both unavailable source points in the 86-target scope.
Only the two source Weight rows vary, exactly as in change_mass.m.
"""
import argparse
from pathlib import Path
import re
import resource
import runpy
import time

import verify_sa14_defaults as common
import isae_st3_curve_markers as markers

ROOT = common.ROOT
REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
CACHE = ROOT/'reference/isae-validation'/REVISION
CASE = CACHE/'3 - Structure/CASE - ST3 Low aspect ratio'
STATIC = CASE/'Static_Deflection_analysis'
LAYUPS = {
    '0_3_90': ('[0_3_90]_S', '[03_90]_S'),
    'p15_0': ('[+15_2_0_2]_S', '[+15_2_0_2]_S'),
    'm15_0': ('[-15_2_0_2]_S', '[-15_2_0_2]_S'),
}


def load_masses(kind, load):
    raw=[load/9.81/2]*2 if kind=='F' else [load,-load]
    return [0. if x==0 else float(format(x,'.5g')) for x in raw]


def loaded_source(text, masses):
    """Keep the original 9.81 multiplier and use the reviewed scalar format."""
    for i, mass in enumerate(masses, 1):
        row=f'  1  0.558  {-.07 if i==1 else .07:.2f}  0.558  0.0  {mass:.5g}'
        text,n=re.subn(rf'(?m)(^#  MASS{i}[^\n]*\n)[^\n]*',lambda m:m[1]+row,text)
        assert n==1
    return text


def plotted(observable, kind, quantity, name):
    if quantity=='Z':
        return observable['h_m']*(-1 if kind=='M' and name!='0_3_90' else 1)
    return observable['twist_asw_deg']*(-1 if kind=='M' else 1)


def prepare(out):
    import numpy as np
    from openswing.asw import parse_asw
    old=runpy.run_path(str(ROOT/'scripts/extract-isae-st3-static.py'))
    manifest=common.read(ROOT/'reference/isae-validation/manifest.json')
    assert manifest['revision']==REVISION
    paths=[*sorted((ROOT/'openswing').glob('*.py')),Path(__file__),
        ROOT/'scripts/isae_st3_curve_markers.py',ROOT/'scripts/extract-isae-st3-static.py',
        ROOT/'scripts/verify-isae-st3-static.py',ROOT/'scripts/isae_st3_static_reference.py',
        ROOT/'scripts/verify_sa14_defaults.py',ROOT/'scripts/isae_suite_extra_polars.py',
        ROOT/'scripts/isae_suite_polars.py',ROOT/'tests/test_isae_st3_curve_markers.py',
        ROOT/'tests/test_isae_st3_static_curves.py',
        ROOT/'docs/validation/aswing-authoritative-references.md',
        ROOT/'docs/validation/aswing-authoritative-sources.json']
    sources=[p for p in STATIC.iterdir() if p.suffix in ('.asw','.m','.sh','.eps','.txt')]
    loads={};final_row_audit={}
    for name,(folder,stem) in LAYUPS.items():
        p=CASE/folder/(stem+'_M_VS_THETA.csv');sources.append(p)
        raw=np.loadtxt(p,delimiter=',',skiprows=2)
        assert raw.shape==(17,2) and np.isfinite(raw).all()
        moments=raw[:,1]*(1 if name=='0_3_90' else -1);moments[len(moments)//2]=0.
        loads[name]=dict(F=[i*.1*9.81 for i in range(6 if name=='0_3_90' else 5)],
            M=sorted(float(x) for x in moments if x>=0))
        assert len(loads[name]['M'])==9
        source=(STATIC/f'[{name}].asw').read_text();model=old['ns']['inspect'](source,name)
        final=float(format(moments[-1],'.5g'))
        expected=np.array([final,-final])*9.81
        actual=np.array([r[5] for r in model.records['weight']])
        np.testing.assert_allclose(actual,expected,atol=1e-14,rtol=0)
        final_row_audit[name]=dict(last_script_value=float(moments[-1]),rounded_mass_kg=final,
            actual_original_weights_N=actual.tolist())
    for p in sources:
        assert common.sha(p)==manifest['files'][p.relative_to(CACHE).as_posix()]['sha256']
    paths+=sources
    catalog=common.read(ROOT/'docs/validation/aswing-authoritative-sources.json')
    for entry in catalog['files']:
        if entry['id'] in ('isae-part-3','drela-steady'):
            for field,key in [('local_pdf','sha256'),('local_text','text_sha256')]:
                p=ROOT/entry[field];assert common.sha(p)==entry[key];paths.append(p)
    figures={};targets=[];stroke_checks=[]
    for p in sorted(STATIC.glob('*.eps')):
        # The unchanged legacy axis reader expects its historical symlink path.
        legacy_path=old['ns']['CACHE']/p.relative_to(CACHE)
        figure=markers.extract(p.read_text(),old['extract'](legacy_path));figures[p.name]=figure
        for curve in figure['curves']:
            name=curve['name'];original=loads[name][figure['kind']];found={}
            vertices=np.asarray(curve['stroke_vertices']);a=vertices[:-1];d=vertices[1:]-a
            for r in curve['samples']:
                i=int(np.argmin(abs(np.asarray(original)-r['plotted_load'])))
                assert abs(original[i]-r['plotted_load'])<=r['x_tolerance'] and i not in found
                found[i]=r
                point=np.array([r['x'],r['y']]);t=np.clip(np.sum((point-a)*d,axis=1)/np.sum(d*d,axis=1),0,1)
                distance=float(np.min(np.linalg.norm(point-(a+t[:,None]*d),axis=1)))
                assert distance<=markers.PIXEL_ENVELOPE
                stroke_checks.append(dict(figure=p.name,name=name,load_index=i,distance=distance))
            for i,load in enumerate(original):
                row=dict(figure=p.name,name=name,kind=figure['kind'],quantity=figure['quantity'],
                    script_load=load,load_index=i,source_available=i in found)
                if i in found:
                    row.update({key:value for key,value in found[i].items() if key!='kind'},
                        marker_kind=found[i]['kind'])
                else:
                    assert load>figure['x_range'][1]
                    row.update(expected=None,original_absolute_tolerance=None,unavailable_reason='Script sample is outside saved figure x limits; no ordinate recoverable.')
                targets.append(row)
    assert len(targets)==86 and sum(r['source_available'] for r in targets)==84
    states={}
    for name in LAYUPS:
        for kind in ('F','M'):
            for load in loads[name][kind]:
                mass=load_masses(kind,load)
                key=f'{name}|{mass[0]:.5g}|{mass[1]:.5g}'
                states.setdefault(key,dict(key=key,name=name,masses_kg=mass))
    assert len(states)==40
    jobs=[]
    # Each load is paired with its refinement, before moving to another state.
    for state in states.values():
        for n in (64,128):jobs.append(dict(**state,panels=n))
    for row in targets:
        assert row['kind'] in ('F','M')
        mass=load_masses(row['kind'],row['script_load'])
        row['state_key']=f"{row['name']}|{mass[0]:.5g}|{mass[1]:.5g}"
        assert row['state_key'] in states
    out.mkdir(parents=True,exist_ok=True)
    common.write(out/'plan.json',dict(observed_utc=common.utc(),pins={p.relative_to(ROOT).as_posix():common.sha(p) for p in paths},
        jobs=jobs,targets=targets,figures=figures,loads=loads,final_row_audit=final_row_audit,
        marker_stroke_checks=stroke_checks,required=86,available=84,relative_tolerance=.05,
        mesh_relative_gate=.001,mesh_absolute_gates=dict(Z=1e-9,T=1e-7),
        limits=dict(blas_threads=1,address_space_mib=512,cpu_seconds=15,wall_seconds=25),
        protocol='All three layups and all four static observables on the nonnegative branch shown in Figure25. '
        'Original models; only Weight data rows changed following change_mass.m, retaining9.81 and five-significant-digit masses. '
        '64/128 cosine intervals; direct signed weights through structural JSON solve. No experimental ordinate used. '
        'Both source-clipped ordinates remain unavailable in86. Both grids must match each readable target and mesh gate. '
        'The script torque abscissa is a mass, despite its label: physical undeformed couple is1.3734 times the abscissa. '
        'Negative branch is outside this declared plotted scope. Native startup, exact intermediate files and executable remain unavailable.',
        original_archive_unchanged=True,full_family_validated=False))
    print('Prepared80 serial states,86 required targets,84 readable markers.',flush=True)


def run(out,index):
    plan=common.read(out/'plan.json');common.authenticate(plan['pins']);job=plan['jobs'][index]
    folder=out/f'job-{index:02d}';folder.mkdir()
    import numpy as np
    from openswing.asw import parse_asw
    from openswing.bridge import dispatch
    from isae_st3_static_reference import observables
    original=(STATIC/f"[{job['name']}].asw").read_text()
    source=loaded_source(original,job['masses_kg']);model=parse_asw(source)
    weights=[r[5] for r in model.records['weight']]
    np.testing.assert_allclose(weights,np.array(job['masses_kg'])*9.81,atol=1e-14,rtol=0)
    request=dict(action='solve',mode='structural',source=source,
        panels=dict(default=job['panels'],beams={'1':dict(count=job['panels'],spacing='cosine')}),
        numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator='drela-steady-section-v1'),
        gravity=[0.,0.,-9.81],loads=[],tolerance=1e-8,continuation_steps=4)
    common.write(folder/'request.json',request);started=time.monotonic();result=dispatch(request)
    seconds=time.monotonic()-started;common.write(folder/'result.json',result)
    nodes=sorted(result['nodes'],key=lambda n:n['t']);assert nodes[0]['t']==.0001 and nodes[-1]['t']==.558
    assert len(nodes)>=job['panels']+1
    r=np.asarray(nodes[-1]['position']);q=np.asarray(nodes[-1]['rotation'])
    points=np.array([r+q@[-.07,0.,0.],r+q@[.07,0.,0.]])
    forces=np.array([[0.,0.,-w] for w in weights]);force=forces.sum(axis=0);moment=np.cross(points,forces).sum(axis=0)
    checks=dict(residual=result['residual'],force_balance=float(np.max(abs(np.asarray(result['force_balance'])))),
        moment_balance=float(np.max(abs(np.asarray(result['moment_balance'])))),
        gravity_force=float(np.max(abs(np.asarray(result['applied_force'])-force))),
        gravity_moment=float(np.max(abs(np.asarray(result['applied_moment'])-moment))),
        clamp_position=float(np.max(abs(np.asarray(nodes[0]['position'])))),
        clamp_rotation=float(np.max(abs(np.asarray(nodes[0]['rotation'])-np.eye(3)))))
    assert result['converged'] and max(checks.values())<1e-7,checks
    signed=min(weights)<0
    assert (result['mass_properties'].get('physical',True) is False)==signed
    assert ('launch' not in result['equilibrium_state'])==signed
    common.authenticate(plan['pins'])
    report=dict(observed_utc=common.utc(),job=job,observable=observables(r,q),checks=checks,nodes=len(nodes),
        seconds=seconds,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        plan_sha256=common.sha(out/'plan.json'),artifacts={p.name:common.sha(p) for p in folder.iterdir()})
    common.write(folder/'report.json',report)
    print(dict(index=index,**job,observable=report['observable'],seconds=seconds),flush=True)


def summarize(out):
    plan=common.read(out/'plan.json');common.authenticate(plan['pins']);reports=[]
    for i,job in enumerate(plan['jobs']):
        folder=out/f'job-{i:02d}';r=common.read(folder/'report.json')
        assert r['job']==job and r['plan_sha256']==common.sha(out/'plan.json')
        for p,h in r['artifacts'].items():assert common.sha(folder/p)==h
        assert max(r['checks'].values())<1e-7
        reports.append(r)
    lookup={(r['job']['key'],r['job']['panels']):r for r in reports};rows=[]
    for target in plan['targets']:
        values=[plotted(lookup[(target['state_key'],n)]['observable'],target['kind'],target['quantity'],target['name']) for n in (64,128)]
        delta=abs(values[1]-values[0]);mesh_gate=max(plan['mesh_absolute_gates'][target['quantity']],abs(values[1])*plan['mesh_relative_gate'])
        row=dict(**target,predictions=values,mesh_change=delta,mesh_gate=mesh_gate,mesh_pass=delta<=mesh_gate,passed=False)
        if target['source_available']:
            expected=target['expected'];errors=[abs(v-expected) for v in values]
            gate=max(target['original_absolute_tolerance'],abs(expected)*plan['relative_tolerance'])
            row.update(errors=errors,gate=gate,passed=max(errors)<=gate and row['mesh_pass'],
                error_percent=100*errors[1]/abs(expected) if abs(expected)>target['original_absolute_tolerance'] else None)
        rows.append(row)
    summary=dict(observed_utc=common.utc(),required=len(rows),available=sum(r['source_available'] for r in rows),
        passed=sum(r['passed'] for r in rows),rows=rows,mesh_pass=all(r['mesh_pass'] for r in rows),numerical_pass=True,
        curves={name:dict(required=sum(r['figure']==name for r in rows),passed=sum(r['figure']==name and r['passed'] for r in rows)) for name in plan['figures']},
        solver_seconds=sum(r['seconds'] for r in reports),peak_rss_kib=max(r['peak_rss_kib'] for r in reports),
        max_physical_residual=max(max(r['checks'].values()) for r in reports),
        plan_sha256=common.sha(out/'plan.json'),original_archive_unchanged=True,full_family_validated=False)
    common.write(out/'summary.json',summary);print({k:v for k,v in summary.items() if k!='rows'})


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run','summarize'])
    p.add_argument('--output',type=Path,required=True);p.add_argument('--index',type=int)
    a=p.parse_args();common.bounded()
    if a.action=='prepare':prepare(a.output)
    elif a.action=='run':run(a.output,a.index)
    else:summarize(a.output)


if __name__=='__main__':main()
