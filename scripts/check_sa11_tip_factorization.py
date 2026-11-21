"""Check four-factor accounting and independently replay winglet constraints."""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import itertools
import json
import math
import os
from pathlib import Path
import resource
import signal
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def write(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')


def bounded():
    for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):assert os.environ.get(k)=='1'
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU,(15,15));signal.alarm(25)


def prepare(out):
    bounded();parent=read(out/'plan.json');pins=dict(parent['pins'])
    for path,digest in pins.items():assert sha(ROOT/path)==digest,path
    for case in parent['cases']:
        folder=out/case['id'];report=read(folder/'report.json')
        assert report['plan_sha256']==sha(out/'plan.json')
        for name,digest in report['artifacts'].items():assert sha(folder/name)==digest
        for name in ('report.json','common-intervals.npz'):
            pins[str((folder/name).relative_to(ROOT))]=sha(folder/name)
    for path in (Path(__file__),out/'plan.json'):
        pins[str(path.relative_to(ROOT))]=sha(path)
    write(out/'constraint-plan-r2.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),pins=pins,
        preparation_correction='The first check stopped before the conditional replay because algebraically identical source endpoints differ by1.11e-16m. Retain its plan/script/receipt; verify endpoint equality within2e-15m and record that difference. No physical result was discarded.',
        protocol='Two alpha2.75/3saved pairs. Independently average all24factor-order telescoping paths to check attribution. At unchanged winglet control points, rebuild full zero-core PG matrix, saved stall leakage and normal direction. Solve only the32-by32conditional winglet linear equations with saved main circulation prescribed; keep the original stall leakage on the RHS. Attribute the winglet circulation change to outer-main, interior-main and leakage forcing. This is a conditional algebra check,not a new coupled physical equilibrium.',
        source_basis='Drela steady Eqs200--204 with frozen influences. Keep the small nonzero stall-leakage term instead of asserting perfectly attached flow.',
        physical_solves=0,primary_passes_added=0,limits='One BLAS thread,512MiB,15CPU/25wall seconds per audit.'))
    signal.alarm(0);print(dict(prepared=True,pins=len(pins)))


def run(out,index):
    bounded();started=time.monotonic();plan=read(out/'constraint-plan-r2.json')
    for path,digest in plan['pins'].items():assert sha(ROOT/path)==digest,path
    parent=read(out/'plan.json');case=parent['cases'][index];folder=out/case['id'];r=read(folder/'report.json')
    keys=list(r['change']);terms={f:{k:[] for k in keys} for f in parent['factors']}
    # This path-permutation reduction does not use the driver's subset weights.
    for order in itertools.permutations(range(4)):
        bits=[0]*4
        for i in order:
            previous=r['corners'][''.join(map(str,bits))];bits[i]=1
            current=r['corners'][''.join(map(str,bits))]
            for k in keys:terms[parent['factors'][i]][k].append(current[k]-previous[k])
    shapley_error=0.
    for factor in terms:
        for k,values in terms[factor].items():
            assert len(values)==24
            shapley_error=max(shapley_error,abs(math.fsum(values)/24-r['attribution'][factor][k]))
    assert shapley_error<2e-12
    import numpy as np
    sys.path.insert(0,str(ROOT))
    from openswing.asw import parse_asw
    from openswing.geometry import model_meshes
    avl_path=ROOT/'scripts/avl_vorvelc_reference.py'
    spec=importlib.util.spec_from_file_location('avl_reference',avl_path);avl=importlib.util.module_from_spec(spec);spec.loader.exec_module(avl)
    model=parse_asw((ROOT/case['model_path']).read_text(),beam_interpolation='natural-v1')
    with np.load(folder/'common-intervals.npz') as f:common={k:f[k] for k in f}
    raw=[read(ROOT/s['raw']) for s in case['states']];g=[]
    for state in case['states']:
        with np.load(ROOT/state['geometry']) as f:g.append({k:f[k] for k in f})
    meshes=model_meshes(model,case['states'][0]['mesh'])
    normals=[];slopes=[];lower=[];upper=[]
    for mesh in meshes[1:]:
        alpha=np.deg2rad(mesh.beam.value('alpha',mesh.tm))
        normals.extend(np.sin(alpha)[:,None]*mesh.frames[...,0]+np.cos(alpha)[:,None]*mesh.frames[...,2])
        for values,key in [(slopes,'dCLda'),(lower,'CLmin'),(upper,'CLmax')]:values.extend(mesh.beam.value(key,mesh.tm))
    normals=np.array(normals);slopes=np.array(slopes);lower=np.array(lower);upper=np.array(upper)
    assert np.array_equal(g[0]['cp'][32:],g[1]['cp'][46:])
    endpoint_difference=max(float(np.max(abs(common[k+'_0']-common[k+'_1']))) for k in ('a','b'))
    assert endpoint_difference<2e-15
    cp=g[0]['cp'][32:];speed=case['condition']['speed'];angle=math.radians(case['alpha'])
    wind=speed*np.array([math.cos(angle),0,math.sin(angle)])
    op=avl.matrix(cp,common['a_0'],common['b_0'],case['condition']['mach'],exclude_self=False,core_fraction=0.,dtype=np.longdouble)
    op/=4*np.arccos(np.longdouble(-1))*np.longdouble('.079577472')
    a=np.einsum('ijq,iq->ij',op,normals);main=common['beam']==1
    amm=np.asarray(a[:,main],float);aww=np.asarray(a[:,~main],float);free=normals@wind
    gamma=[common[f'gamma_{i}'] for i in (0,1)];leak=[];errors=[];predicted=[]
    for i,count in enumerate((32,46)):
        strips=raw[i]['strips'][count:];cl=np.array([s['cl'] for s in strips])
        normal_speed=np.array([s['normal_speed'] for s in strips]);width=case['condition']['stall_width']
        assert np.all(cl<upper) and np.all(cl>lower)
        leakage=normal_speed/slopes*case['condition']['stall_factor']*width*(np.log1p(np.exp((cl-upper)/width))-np.log1p(np.exp((lower-cl)/width)))
        leak.append(leakage)
        v=np.linalg.solve(aww,leakage-free-amm@gamma[i][main]);predicted.append(v)
        errors.append(float(np.max(abs(v-gamma[i][~main]))/max(abs(gamma[i][~main]))))
    assert max(errors)<2e-10,errors
    delta_main=gamma[1][main]-gamma[0][main];actual=gamma[1][~main]-gamma[0][~main]
    nodes=common['nodes_0'];t=.5*(nodes[:-1]+nodes[1:]);tip=(abs(t)>1.0413)
    forcing=dict(outer_main=-amm[:,tip]@delta_main[tip],interior_main=-amm[:,~tip]@delta_main[~tip],stall_leakage=leak[1]-leak[0])
    response={k:np.linalg.solve(aww,v) for k,v in forcing.items()}
    closure=float(np.max(abs(sum(response.values())-actual)))
    assert closure<2e-10
    norm=float(np.linalg.norm(actual));assert norm>0
    # Signed projection onto the actual change vector sums to100%; report
    # response norms too, so cancellation is visible rather than hidden.
    contribution={k:dict(forcing_max_mps=float(max(abs(forcing[k]))),response_norm=float(np.linalg.norm(v)),
                         signed_projection_percent=float(100*np.dot(v,actual)/(norm*norm))) for k,v in response.items()}
    result=dict(observed_utc=datetime.now(timezone.utc).isoformat(),verified=True,alpha=case['alpha'],
        shapley_permutation_error=shapley_error,conditional_gamma_relative_errors=errors,
        response_closure=closure,source_endpoint_roundoff_m=endpoint_difference,winglet_matrix_condition=float(np.linalg.cond(aww)),
        actual_winglet_gamma_change_norm=norm,
        winglet_gamma_relative_change_percent=float(100*norm/np.linalg.norm(gamma[0][~main])),
        contributions=contribution,maximum_stall_leakage_mps=max(float(max(abs(v))) for v in leak),
        physical_solves=0,primary_passes_added=0,seconds=time.monotonic()-started,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        parent_report_sha256=sha(folder/'report.json'),plan_sha256=sha(out/'constraint-plan-r2.json'))
    write(folder/'constraint-verification.json',result);signal.alarm(0)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('prepare','run'))
    p.add_argument('--output',type=Path,required=True);p.add_argument('--index',type=int)
    args=p.parse_args()
    if args.action=='prepare':prepare(args.output.resolve())
    else:run(args.output.resolve(),args.index)
