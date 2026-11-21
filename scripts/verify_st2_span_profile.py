"""Direct-node ST-2 archived span-profile replay on coordinate-supported meshes.

The original8-field/46-row scope stays intact, including unavailable display
fields. Grid selection uses only printed t coordinates, never load values.
"""
import argparse
from decimal import Decimal
import math
from pathlib import Path
import resource
import time

import verify_sa14_defaults as common
from isae_st2_archive import decode_archive_profile,COLUMNS

ROOT=common.ROOT
BASE=ROOT/'reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST2 Pazy_Wing/03_Static_Structural'
FIELDS=('y','z-z0','tw-tw0',"Mc'/10","Ms'/10",'Fn/10')


def printed_interval(field):
    v=Decimal(field['token']);half=Decimal(5).scaleb(v.as_tuple().exponent-1);scale=Decimal(10)**field['power10']
    return v*scale,half*scale


def coordinate_audit(rows):
    n=len(rows)-1;lo=.0001;hi=.55;angle=math.asin(1-2**-24);output={}
    for kind in ('uniform','cosine','modified-cosine'):
        values=[]
        for i,row in enumerate(rows):
            u=math.sin((2*i/n-1)*angle)
            fraction=i/n if kind=='uniform' else (1-math.cos(math.pi*i/n))/2 if kind=='cosine' else (1+.7*u+.3*u**3)/2
            t=lo+(hi-lo)*fraction
            if i==0:t=lo
            if i==n:t=hi
            expected,half=printed_interval(row['fields']['t'])
            values.append(dict(index=i,predicted=t,expected_token=row['fields']['t']['token'],passed=abs(Decimal.from_float(t)-expected)<=half))
        output[kind]=dict(passed=sum(v['passed'] for v in values),required=len(rows),rows=values)
    assert output['modified-cosine']['passed']==len(rows)
    assert output['cosine']['passed']<len(rows) and output['uniform']['passed']<len(rows)
    return output


def prepare(out):
    prior=common.read(ROOT/'artifacts/isae/st2-static-curves-20261109/plan.json');common.authenticate(prior['pins'])
    out.mkdir(parents=True,exist_ok=True);pins=dict(prior['pins'])
    files=[Path(__file__),ROOT/'scripts/isae_st2_archive.py',BASE/'temp.txt',ROOT/'reference/aswing_doc.txt',
        ROOT/'artifacts/isae/st2-modal-current-20261109/tip-pylon-audit.json',
        ROOT/'docs/validation/isae-sa1-sa5-spacing-20261029.md']
    for p in files:pins[p.relative_to(ROOT).as_posix()]=common.sha(p)
    profile=decode_archive_profile((BASE/'temp.txt').read_text());assert len(profile['rows'])==46
    common.write(out/'plan.json',dict(observed_utc=common.utc(),pins=pins,profile=profile,
        coordinate_audit=coordinate_audit(profile['rows']),required=368,
        fields_computed=list(FIELDS),fields_unavailable=['cl','a_flap'],
        jobs=[dict(nominal=n,spacing='modified-cosine',sample_stride=stride,mass_kg=3.) for n,stride in [(45,1),(90,2)]],
        limits=prior['limits'],reference_relative=.05,mesh_peak_relative=.01,
        protocol='Two identical3kg bending setups on45/90 modified-cosine intervals. '
            'Every original t interval is matched, so paired source nodes are used directly, with no field interpolation. '
            'Explicit tip-pylon reconstruction retains original point coordinates and original beam properties. '
            'Use absolute deformed y, z minus jig z, un-negated local twist, and endpoint local prime moments/normal force. '
            'Original model has coincident tension/elastic/reference axes, so prime moments equal local moments. '
            'cl and a_flap remain unavailable: the structural solve exports neither aerodynamic strip coefficients nor this legacy display quantity. '
            'No zero values are invented for those columns. Original near-zero absolute gates are retained.'))
    print('Declared all368 fields;276 mechanical fields computable,92 legacy display fields retained unavailable.')


def run(out,index):
    plan=common.read(out/'plan.json');common.authenticate(plan['pins']);job=plan['jobs'][index];folder=out/f'job-{index}';folder.mkdir()
    import numpy as np
    from isae_st2 import static_model,observables
    from openswing.bridge import dispatch
    model,source,reconstruction=static_model('bending',0,3.,'archive_pylon')
    beam=model.beams[0]
    for name in ('Cea','Nea','Cta','Nta','Ccg','Ncg'):assert np.all(beam.value(name,np.array([.0001,.275,.55]))==0)
    request=dict(action='solve',mode='structural',source=source,
        panels=dict(default=job['nominal'],beams={'1':dict(count=job['nominal'],spacing=job['spacing'])}),
        numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator='drela-steady-section-v1'),
        gravity=[0.,0.,-9.81],loads=[],tolerance=1e-8,continuation_steps=4)
    common.write(folder/'request.json',request);started=time.monotonic();result=dispatch(request)
    seconds=time.monotonic()-started;common.write(folder/'result.json',result)
    nodes=sorted(result['nodes'],key=lambda n:n['t']);assert len(nodes)==job['nominal']+1
    traces={};continuity=0.
    for e in result['elements']:
        for tr in e['endpoint_traces']:
            if tr['node'] in traces:
                for key in ('force','moment','force_local','moment_axes'):
                    continuity=max(continuity,float(np.max(abs(np.asarray(tr[key])-np.asarray(traces[tr['node']][key])))))
            traces[tr['node']]=tr
    assert len(traces)==len(nodes) and continuity<1e-9
    position=np.asarray([n['position'] for n in nodes]);lengths=np.asarray([e['length'] for e in result['elements']]);assert abs(sum(lengths)-.55)<1e-12
    masses=np.zeros(len(nodes));masses[:-1]+=.3745*lengths/2;masses[1:]+=.3745*lengths/2
    force=masses[:,None]*[0.,0.,-9.81];point=position[-1]+np.asarray(nodes[-1]['rotation'])@[.05,.008,0.]
    applied=force.sum(axis=0)+[0.,0.,-3*9.81];moment=np.cross(position,force).sum(axis=0)+np.cross(point,[0.,0.,-3*9.81])
    checks=dict(residual=result['residual'],force_balance=float(np.max(abs(np.asarray(result['force_balance'])))),
        moment_balance=float(np.max(abs(np.asarray(result['moment_balance'])))),
        independent_force=float(np.max(abs(applied-result['applied_force']))),independent_moment=float(np.max(abs(moment-result['applied_moment']))),
        clamp_position=float(np.max(abs(position[0]))),clamp_rotation=float(np.max(abs(np.asarray(nodes[0]['rotation'])-np.eye(3)))),interior_resultant_continuity=continuity)
    assert result['converged'] and max(checks.values())<1e-7
    comparisons=[];station_checks=[]
    for i,row in enumerate(plan['profile']['rows']):
        node=nodes[i*job['sample_stride']];tr=traces[node['index']];obs=observables(node['position'],node['rotation'])
        expected,half=printed_interval(row['fields']['t']);assert abs(Decimal.from_float(node['t'])-expected)<=half
        station_checks.append(dict(row=i,t=node['t'],expected_token=row['fields']['t']['token'],inside_printed_interval=True))
        values={'y':node['position'][1],'z-z0':node['position'][2]-node['jig_position'][2],'tw-tw0':obs['twist_asw_deg'],
                "Mc'/10":tr['moment_axes'][0],"Ms'/10":tr['moment_axes'][1],'Fn/10':tr['force_local'][2]}
        for name in COLUMNS[1:]:
            f=row['fields'][name];target,tolerance=printed_interval(f);v=values.get(name)
            if v is None:
                comparisons.append(dict(row=i,field=name,predicted=None,expected=float(target),expected_token=f['token'],passed=False,status='unavailable_display_field'));continue
            error=abs(Decimal.from_float(v)-target)
            gate=max(tolerance,Decimal('.05')*abs(target)) if abs(target)>Decimal('1e-8') else tolerance
            comparisons.append(dict(row=i,field=name,t=node['t'],predicted=v,expected=float(target),expected_token=f['token'],
                absolute_error=float(error),original_absolute_tolerance=float(tolerance),effective_tolerance=float(gate),
                strict_passed=error<=tolerance,passed=error<=gate,status='computed',
                error_percent=float(100*error/abs(target)) if abs(target)>Decimal('1e-8') else None))
    common.authenticate(plan['pins'])
    report=dict(observed_utc=common.utc(),job=job,checks=checks,reconstruction=reconstruction,stations=station_checks,comparisons=comparisons,
        passed=sum(r['passed'] for r in comparisons),required=368,computed=276,unavailable=92,
        seconds=seconds,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,plan_sha256=common.sha(out/'plan.json'),
        artifacts={p.name:common.sha(p) for p in folder.iterdir()})
    common.write(folder/'report.json',report)
    print({k:report[k]for k in ('job','passed','required','computed','unavailable','checks','seconds','peak_rss_kib')})


def summarize(out):
    plan=common.read(out/'plan.json');common.authenticate(plan['pins']);reports=[]
    for i,job in enumerate(plan['jobs']):
        folder=out/f'job-{i}';r=common.read(folder/'report.json');assert r['job']==job and r['plan_sha256']==common.sha(out/'plan.json')
        for p,h in r['artifacts'].items():assert common.sha(folder/p)==h
        reports.append(r)
    rows=[];mesh={}
    for a,b in zip(reports[0]['comparisons'],reports[1]['comparisons'],strict=True):
        assert all(a[k]==b[k]for k in ('field','row','expected','expected_token','status'))
        rows.append(dict(**b,coarse_passed=a['passed'],both_meshes_pass=a['passed'] and b['passed'],
            mesh_absolute_change=abs(a['predicted']-b['predicted']) if b['predicted']is not None else None))
    for field in FIELDS:
        selected=[r for r in rows if r['field']==field];scale=max(abs(r['predicted'])for r in selected)
        metric=max(r['mesh_absolute_change']for r in selected)/max(scale,1e-12)
        mesh[field]=dict(peak_scaled_change_percent=100*metric,passed=metric<plan['mesh_peak_relative'])
    summary=dict(observed_utc=common.utc(),required=368,computed=276,unavailable=92,passed=sum(r['both_meshes_pass']for r in rows),
        rows=rows,mesh_checks=mesh,mesh_pass=all(r['passed']for r in mesh.values()),
        fields={f:dict(required=46,computed=sum(r['predicted']is not None for r in rows if r['field']==f),
            passed=sum(r['both_meshes_pass']for r in rows if r['field']==f),strict_fine_passed=sum(r.get('strict_passed',False)for r in rows if r['field']==f),
            max_nonzero_error_percent=max((r.get('error_percent')or 0)for r in rows if r['field']==f))for f in COLUMNS[1:]},
        primary_mechanics_scope_changed=False,original_archive_registration_changed=False,
        qualification='Direct-node qualified pylon reconstruction; source t intervals establish compatible modified-cosine45 grid. '
            'Cl/a_flap remain unavailable. Native out-of-domain input semantics and exact historical input bytes remain unknown.')
    common.write(out/'summary.json',summary);print({k:v for k,v in summary.items()if k!='rows'})


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run','summarize']);p.add_argument('--output',type=Path,required=True);p.add_argument('--index',type=int)
    a=p.parse_args()
    if a.action=='prepare':prepare(a.output)
    else:
        common.bounded()
        if a.action=='run':run(a.output,a.index)
        else:summarize(a.output)


if __name__=='__main__':main()
