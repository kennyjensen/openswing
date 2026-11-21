"""Prescribed smooth circulation: discrete versus continuous swept wake.

Fixed origin receiver, straight bound line, zero core/PG/stall. Analytic
symmetric-exclusion coefficients distinguish a continuum singularity from
solver or moving-probe effects. One bounded serial job per spacing policy.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import time

import numpy as np
from scipy.integrate import quad, quad_vec

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from openswing.aero import semi_infinite_vortex, finite_vortex


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def portable(x):
    if isinstance(x,np.ndarray): return x.tolist()
    if isinstance(x,np.generic): return x.item()
    if isinstance(x,dict): return {k:portable(v) for k,v in x.items()}
    if isinstance(x,(tuple,list)): return [portable(v) for v in x]
    return x


def write(path,value): path.write_text(json.dumps(portable(value),indent=2,allow_nan=False)+'\n')


def gamma(s,asymmetry): return (1-s*s)*(1+asymmetry*s)


def gamma_prime(s,asymmetry): return asymmetry-2*s-3*asymmetry*s*s


def analytic_ray(point,s,sweep):
    """Direct scalar-component semi-infinite Biot-Savart expression."""
    tangent=np.array([np.sin(sweep),np.cos(sweep),0.])
    x,y,z=point-s*tangent
    h2=y*y+z*z
    assert h2>0.
    factor=(1+x/np.sqrt(x*x+h2))/(4*np.pi*h2)
    return np.array([0.,-z,y])*factor


def continuum(point,sweep,asymmetry):
    # Gamma(-1)=Gamma(+1)=0: there are no endpoint jump filaments.
    value,estimate=quad_vec(lambda s:-gamma_prime(s,asymmetry)*analytic_ray(point,s,sweep),
                            -1.,1.,points=[0.],epsabs=2e-11,epsrel=2e-11,limit=1000)
    assert estimate<1e-9,estimate
    return value,float(estimate)


def cutoff_reference(sweep,asymmetry,cutoff):
    """Symmetrically exclude |s|<delta; this is not a production core."""
    sine,cosine=np.sin(sweep),np.cos(sweep)
    predicted=(-4*(1-cutoff)+3*asymmetry*sine*(1-cutoff**2)
               -2*asymmetry*sine*np.log(1/cutoff))/(4*np.pi*cosine)
    def scalar(s):
        return gamma_prime(s,asymmetry)*(1-np.sign(s)*sine)/(4*np.pi*cosine*s)
    first,e0=quad(scalar,-1.,-cutoff,epsabs=2e-12,epsrel=2e-12)
    second,e1=quad(scalar,cutoff,1.,epsabs=2e-12,epsrel=2e-12)
    observed=first+second
    np.testing.assert_allclose(observed,predicted,atol=2e-12,rtol=2e-12)
    return dict(cutoff=cutoff,analytic=predicted,quadrature=observed,
                error=abs(predicted-observed),quadrature_estimate=e0+e1)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spacing',choices=('cosine','uniform'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): parser.error('Use a fresh output directory.')
    counts=[15,31,63,127,255,511]
    sweeps=[-30.,0.,30.];asymmetries=[0.,.2]
    # Fixed physical probes, independent of N. Origin lies inside a central
    # interval for odd N, never on a source wake origin. Off-line points have
    # positive distance from every wake filament/sheet.
    heights=[0.,-.1,-.01,-.001,.001,.01,.1]
    points=np.array([[0.,0.,z] for z in heights])
    pins={str(p.relative_to(ROOT)):sha(p) for p in sorted(ROOT.glob('openswing/**/*.py'))+
          [ROOT/'docs/validation/ISAE_STATUS.md',ROOT/'docs/validation/isae-progress-scopes.json']}
    args.output.mkdir(parents=True)
    shutil.copyfile(__file__,args.output/'driver-used.py')
    plan=dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        previous_turn='progress: fixed SA-11 wake probes and circulation metrics isolated localized grid sensitivity',
        unchanged_pins=pins,driver_sha256=sha(Path(__file__)),spacing=args.spacing,panels=counts,
        source_line='r(s)=s*(sin(Lambda),cos(Lambda),0), -1<=s<=1 m',
        circulation='Gamma(s)=(1-s^2)*(1+a*s) m^2/s, in the declared metre coordinate',
        gamma_scale=1.,half_arclength=1.,sweeps_degrees=sweeps,asymmetries=asymmetries,
        source_sampling='Gamma sampled at the Glauert-angle midpoint of every interval, for both spacings.',
        probes=points,wake_direction=[1.,0.,0.],core=0.,mach=0.,new_circulation_solves=0,
        continuum='Integral of -dGamma/ds times the analytic semi-infinite ray; endpoint Gamma=0.',
        on_line_log_coefficient='-Gamma_prime(0)*tan(Lambda)/(2*pi), derived without fitting.',
        scope='Controlled wake mechanism, not a solved aircraft or native ASWING reference comparison.',
        gates=dict(discrete_scalar_atol=2e-11,discrete_scalar_rtol=2e-11,
                   final_log_increment_relative_error=.005,far_probe_final_error=2e-4),
        dlr_source=dict(url='https://unicado.pages.rwth-aachen.de/unicado.gitlab.io/documentation/analysis/aerodynamic_analysis/references/LIFTING_LINE_V3.2_UserDoc.pdf',
                        page=97,local_sha256=sha(ROOT/'.reference/winglet-literature-20261107/dlr-lifting-line-3.2-manual.pdf')))
    write(args.output/'plan.json',plan)
    started=time.monotonic();records=[];references=[]
    try:
        for degrees in sweeps:
            sweep=np.deg2rad(degrees);tangent=np.array([np.sin(sweep),np.cos(sweep),0.])
            for asymmetry in asymmetries:
                continuous=[]
                for point in points[1:]:
                    value,estimate=continuum(point,sweep,asymmetry)
                    continuous.append(dict(point=point,velocity=value,estimate=estimate))
                references.append(dict(sweep_degrees=degrees,asymmetry=asymmetry,
                    off_line=continuous,
                    symmetric_exclusions=[cutoff_reference(sweep,asymmetry,d) for d in (.1,.01,.001,.0001)],
                    log_coefficient=-asymmetry*np.tan(sweep)/(2*np.pi),
                    finite_symmetric_limit=(-1/(np.pi*np.cos(sweep)) if asymmetry==0. or degrees==0. else None)))
                for count in counts:
                    nodes=(-np.cos(np.linspace(0,np.pi,count+1)) if args.spacing=='cosine'
                           else np.linspace(-1.,1.,count+1))
                    theta=np.arccos(np.clip(-nodes,-1.,1.))
                    sample=-np.cos((theta[:-1]+theta[1:])/2)
                    circulation=gamma(sample,asymmetry)
                    strengths=np.r_[-circulation[0],circulation[:-1]-circulation[1:],circulation[-1]]
                    xyz=nodes[:,None]*tangent
                    assert np.min(abs(nodes))>0. and nodes[count//2]<0<nodes[count//2+1]
                    kernel=semi_infinite_vortex(points[:,None,:],xyz[None,:,:],np.array([1.,0.,0.]))
                    wake=np.einsum('ijk,j->ik',kernel,strengths)
                    # Independent component formula at the fixed origin.
                    scalar=-math.fsum(strengths*(1-np.sign(nodes)*np.sin(sweep))/nodes)/(4*np.pi*np.cos(sweep))
                    np.testing.assert_allclose(wake[0],[0.,0.,scalar],atol=2e-11,rtol=2e-11)
                    # All straight bound segments are collinear with the origin.
                    # Omit only the own interval, as in production force sampling.
                    keep=np.arange(count)!=count//2
                    bound=np.sum(finite_vortex(np.zeros(3),xyz[:-1][keep],xyz[1:][keep])*circulation[keep,None],axis=0)
                    assert np.linalg.norm(bound)<2e-10
                    exact=np.array([r['velocity'] for r in continuous])
                    errors=np.linalg.norm(wake[1:]-exact,axis=1)
                    if count==counts[-1]:
                        far=np.isclose(abs(np.array(heights[1:])),.1)
                        assert np.max(errors[far])<plan['gates']['far_probe_final_error']
                    records.append(dict(sweep_degrees=degrees,asymmetry=asymmetry,panels=count,
                        gamma_samples=circulation,nodes=nodes,glauert_samples=sample,
                        ray_strengths=strengths,wake=wake,bound_at_origin=bound,
                        off_line_reference_error=errors,scalar_check_error=abs(wake[0,2]-scalar)))
        # Separate the odd part of Gamma so the analytic logarithmic term is
        # checked without contamination by the finite symmetric loading.
        increments=[]
        for degrees in (-30.,30.):
            selected=[]
            for count in counts:
                r0=next(r for r in records if r['sweep_degrees']==degrees and r['asymmetry']==0. and r['panels']==count)
                r1=next(r for r in records if r['sweep_degrees']==degrees and r['asymmetry']==.2 and r['panels']==count)
                selected.append(float(r1['wake'][0,2]-r0['wake'][0,2]))
            coefficient=-.2*np.tan(np.deg2rad(degrees))/(2*np.pi)
            for i in range(1,len(counts)):
                predicted=coefficient*np.log(counts[i]/counts[i-1])
                observed=selected[i]-selected[i-1]
                error=abs((observed-predicted)/predicted)
                increments.append(dict(sweep_degrees=degrees,first=counts[i-1],second=counts[i],
                    analytic_coefficient=coefficient,predicted=predicted,observed=observed,relative_error=error))
                if i==len(counts)-1: assert error<plan['gates']['final_log_increment_relative_error']
        # Unswept odd loading has zero symmetric principal-value contribution.
        for count in counts:
            values=[next(r for r in records if r['sweep_degrees']==0. and r['asymmetry']==a and r['panels']==count)['wake'][0,2] for a in asymmetries]
            assert abs(values[1]-values[0])<2e-11
        for name,digest in pins.items(): assert sha(ROOT/name)==digest,name
        result=dict(observed_utc=datetime.now(timezone.utc).isoformat(),spacing=args.spacing,
            records=records,continuous_references=references,log_increments=increments,
            maximum_scalar_check_error=max(r['scalar_check_error'] for r in records),
            maximum_cutoff_identity_error=max(c['error'] for r in references for c in r['symmetric_exclusions']),
            total_seconds=time.monotonic()-started,new_circulation_solves=0,
            production_and_primary_counts_unchanged=True)
        write(args.output/'results.json',result)
        write(args.output/'verification.json',dict(status='verified',observed_utc=datetime.now(timezone.utc).isoformat(),
            artifacts={p.name:sha(p) for p in sorted(args.output.iterdir()) if p.is_file()},unchanged_pin_count=len(pins)))
        print(json.dumps(portable(dict(status='verified',spacing=args.spacing,fields=len(records),
            final_increments=[r for r in increments if r['second']==counts[-1]],
            scalar_error=result['maximum_scalar_check_error'],cutoff_error=result['maximum_cutoff_identity_error'],
            seconds=result['total_seconds']))))
    except Exception as exc:
        write(args.output/'failure.json',dict(error_type=type(exc).__name__,error=str(exc),
            observed_utc=datetime.now(timezone.utc).isoformat(),records=records,references=references))
        raise


if __name__=='__main__': main()
