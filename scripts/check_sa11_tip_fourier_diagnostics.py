"""Complete independent Fourier diagnostics, retaining every failed gate."""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
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


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--index',type=int,required=True)
    args=p.parse_args();out=args.output.resolve()
    for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):assert os.environ.get(k)=='1'
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2));resource.setrlimit(resource.RLIMIT_CPU,(15,15));signal.alarm(25)
    started=time.monotonic();plan=read(out/'plan.json');case=plan['cases'][args.index]
    for path,digest in plan['pins'].items():assert sha(ROOT/path)==digest,path
    folder=out/case['id'];report=read(folder/'report.json')
    assert report['case']==case and report['plan_sha256']==sha(out/'plan.json') and report['status']=='computed'
    for name,digest in report['artifacts'].items():assert sha(folder/name)==digest,name
    raw=read(folder/'accepted.json');assert raw['converged'] and raw['residual']<1e-8
    import numpy as np
    sys.path.insert(0,str(ROOT))
    from openswing.asw import parse_asw
    from openswing.geometry import model_meshes
    from openswing.arc_length import material_arc
    refpath=ROOT/'scripts/avl_vorvelc_reference.py'
    spec=importlib.util.spec_from_file_location('avl_reference',refpath);ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)
    model=parse_asw((ROOT/case['model_path']).read_text(),beam_interpolation='natural-v1')
    meshes=model_meshes(model,case['mesh'])
    with np.load(folder/'geometry.npz') as f:g={k:f[k] for k in f}
    gamma=np.array([s['circulation'] for s in raw['strips']]);velocity=np.array([s['relative_velocity'] for s in raw['strips']])
    alpha=math.radians(case['alpha']);speed=case['condition']['speed'];e=np.array([math.cos(alpha),0,math.sin(alpha)])
    factor=1/(4*np.arccos(np.longdouble(-1))*np.longdouble('.079577472'))
    hv=ref.matrix(g['hv'],g['a'],g['b'],case['condition']['mach'],exclude_self=True,core_fraction=0.,dtype=np.longdouble)*factor
    independent_v=np.einsum('ijq,j->iq',hv,gamma)+speed*e
    errors=dict(velocity_relative=float(np.max(abs(independent_v-velocity))/speed))
    del hv
    n=len(gamma);width=case['main_modes']+n-case['main_intervals']
    sample=np.zeros((n,width));test=np.zeros((width,n));normals=[];clmin=[];clmax=[];slopes=[];row0=col0=0
    for mesh in meshes:
        ni=len(mesh.tm);modes=case['main_modes'] if mesh.beam.index==1 else 0;ki=modes or ni
        if modes:
            arc=material_arc(mesh.beam);nodes=np.r_[mesh.t0,mesh.t1[-1]]
            theta=np.arccos(np.clip(2*arc.at(nodes)/arc.total-1,-1,1))
            middle=(theta[:-1]+theta[1:])/2;delta=-np.diff(theta)
            # Explicit scalar sine construction, independent of CirculationBasis.
            for i in range(ni):
                for k in range(modes):
                    value=math.sin((k+1)*middle[i]);sample[row0+i,col0+k]=value;test[col0+k,row0+i]=2/math.pi*value*delta[i]
        else:
            sample[row0:row0+ni,col0:col0+ki]=np.eye(ni);test[col0:col0+ki,row0:row0+ni]=np.eye(ni)
        a0=np.deg2rad(mesh.beam.value('alpha',mesh.tm))
        normals.extend(np.sin(a0)[:,None]*mesh.frames[...,0]+np.cos(a0)[:,None]*mesh.frames[...,2])
        for values,key in [(clmin,'CLmin'),(clmax,'CLmax'),(slopes,'dCLda')]:values.extend(mesh.beam.value(key,mesh.tm))
        row0+=ni;col0+=ki
    coefficients=np.array(raw['circulation_discretization']['coefficients'])
    errors['circulation_reconstruction']=float(np.max(abs(sample@coefficients-gamma)))
    normals=np.array(normals);clmin=np.array(clmin);clmax=np.array(clmax);slopes=np.array(slopes)
    cp=ref.matrix(g['cp'],g['a'],g['b'],case['condition']['mach'],exclude_self=False,core_fraction=0.,dtype=np.longdouble)*factor
    aic=np.asarray(np.einsum('ijq,iq->ij',cp,normals),float);del cp
    cl=np.array([s['cl'] for s in raw['strips']]);normal_speed=np.array([s['normal_speed'] for s in raw['strips']])
    sw=case['condition']['stall_width']
    leakage=normal_speed/slopes*case['condition']['stall_factor']*sw*(np.logaddexp(0,(cl-clmax)/sw)-np.logaddexp(0,(clmin-cl)/sw))
    free=normals@(speed*e);local=(aic@gamma+free-leakage)/speed;projected=test@local
    errors['local_residual_reconstruction']=float(np.max(abs(local-np.array(raw['circulation_local_residual']))))
    errors['projected_residual_reconstruction']=float(np.max(abs(projected-np.array(raw['circulation_residual']))))
    system=test@aic@sample;rhs=test@(leakage-free)
    independent_coeff=np.linalg.solve(system,rhs);independent_gamma=sample@independent_coeff
    errors['conditional_gamma_relative']=float(np.max(abs(independent_gamma-gamma))/max(abs(gamma)))
    perp=velocity-np.sum(velocity*g['span'],axis=1)[:,None]*g['span'];mach=np.linalg.norm(perp,axis=1)/340.21
    errors['normal_mach']=float(np.max(abs(mach-np.array([s['normal_mach'] for s in raw['strips']]))))
    force=np.array([math.fsum(s['force'][k] for s in raw['strips']) for k in range(3)])
    qs=.5*1.2256*speed**2*.9329;cl_total=(-e[2]*force[0]+e[0]*force[2])/qs;cd_total=float(force@e)/qs
    moment=math.fsum(s['moment'][1]+s['position'][2]*s['force'][0]-s['position'][0]*s['force'][2] for s in raw['strips'])/(qs*.37874)
    errors['force']=max(abs(cl_total-raw['CL']),abs(cd_total-raw['CD']))
    errors['moment']=abs(moment-raw['Cm_origin'])
    thresholds=dict(velocity_relative=2e-10,circulation_reconstruction=2e-10,
        local_residual_reconstruction=2e-10,projected_residual_reconstruction=2e-10,
        conditional_gamma_relative=2e-9,force=2e-12,moment=2e-12,normal_mach=2e-12)
    checks={key:bool(errors[key]<value) for key,value in thresholds.items()}
    checks.update(normal_mach_valid=bool(max(mach)<1),projected_residual=bool(max(abs(projected))<1e-8))
    result=dict(observed_utc=datetime.now(timezone.utc).isoformat(),verified=all(checks.values()),checks=checks,thresholds=thresholds,diagnostic_only=True,id=case['id'],errors=errors,
        main_modes=case['main_modes'],main_intervals=case['main_intervals'],physical_configuration=case['physical_configuration'],
        local_residual_max=float(max(abs(local))),main_local_residual_max=float(max(abs(local[:case['main_intervals']]))),
        winglet_local_residual_max=float(max(abs(local[case['main_intervals']:]))) if case['physical_configuration']=='upper_winglet' else None,
        projected_residual_max=float(max(abs(projected))),projected_matrix_condition=float(np.linalg.cond(system)),
        sampling_condition=raw['circulation_discretization']['beams'][0]['sampling_condition'],
        minimum_stall_margin_widths=report['minimum_stall_margin_widths'],maximum_normal_mach=float(max(mach)),
        coefficients={key:raw[key] for key in ('CL','CD','CDi','CDi_near','CDp')},
        physical_solves=0,primary_passes_added=0,seconds=time.monotonic()-started,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        report_sha256=sha(folder/'report.json'),plan_sha256=sha(out/'plan.json'),checker_sha256=sha(Path(__file__)),
        reference_operator_sha256=sha(refpath))
    serialized=json.dumps(result,indent=2,allow_nan=False)+'\n'
    with (folder/'diagnostic-verification.json').open('x') as f:f.write(serialized)
    signal.alarm(0);print(json.dumps({k:v for k,v in result.items() if k not in ('coefficients','report_sha256','plan_sha256','checker_sha256','reference_operator_sha256')},indent=2))


if __name__=='__main__':main()
