"""Continuous piecewise-linear replay of saved Gamma shapes in the planar limit.

No fitted coefficients, no new circulation solves, no native ASWING claim.
The exact linear interpolant includes zero circulation at the two physical tips.
Its gradient autocorrelation is constructed from exact interval-overlap events.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import time

import numpy as np
from numpy.polynomial.legendre import leggauss
from scipy.integrate import quad

ROOT=Path(__file__).resolve().parents[1]
LD=np.longdouble


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def utc(): return datetime.now(timezone.utc).isoformat()


def write(p,x): p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')


class Correlation:
    def __init__(self,nodes,values):
        self.x=np.asarray(nodes,dtype=LD);self.g=np.asarray(values,dtype=LD)
        self.slope=np.diff(self.g)/np.diff(self.x)
        jumps=np.diff(np.r_[LD(0),self.slope,LD(0)])
        delta=self.x[:,None]-self.x[None,:]
        weight=-jumps[:,None]*jumps[None,:]
        keep=delta>0
        knots,inverse=np.unique(delta[keep],return_inverse=True)
        events=np.zeros(len(knots),dtype=LD)
        np.add.at(events,inverse,weight[keep])
        self.knots=np.r_[LD(0),knots]
        self.dR=np.r_[-np.sum(jumps*jumps)/2,-np.sum(jumps*jumps)/2+np.cumsum(events)]
        dx=np.diff(self.knots)
        R0=np.sum(self.slope*self.slope*np.diff(self.x))
        self.R=np.r_[R0,R0+np.cumsum(self.dR[:-1]*dx)]
        self.Q=np.r_[LD(0),np.cumsum(self.R[:-1]*dx+self.dR[:-1]*dx*dx/2)]
        assert max(abs(self.R[-1]),abs(self.Q[-1]),abs(self.dR[-1]))<2e-10

    def evaluate(self,delta):
        delta=np.asarray(delta,dtype=LD)
        i=np.searchsorted(self.knots,delta,side='right')-1
        i=np.clip(i,0,len(self.knots)-2)
        dx=delta-self.knots[i]
        return self.R[i]+self.dR[i]*dx,self.Q[i]+self.R[i]*dx+self.dR[i]*dx*dx/2

    def direct(self,delta):
        lo=np.maximum(self.x[:-1,None],self.x[None,:-1]+delta)
        hi=np.minimum(self.x[1:,None],self.x[None,1:]+delta)
        length=np.maximum(hi-lo,0)
        rr=np.sum(self.slope[:,None]*self.slope[None,:]*length)
        gamma_integral=self.g[:-1,None]*length+self.slope[:,None]*(
            (lo-self.x[:-1,None])*length+length*length/2)
        qq=np.sum(self.slope[None,:]*gamma_integral)
        return rr,qq

    def forces(self,order,sweep=30.,d=.75):
        C=LD(np.cos(np.deg2rad(sweep))); S=LD(np.sin(np.deg2rad(sweep)))
        nodes,weights=leggauss(order); half=np.diff(self.knots)/2
        midpoint=(self.knots[:-1]+self.knots[1:])/2
        delta=midpoint[:,None]+half[:,None]*nodes
        weight=half[:,None]*weights
        R,Q=self.evaluate(delta)
        radius=np.hypot(delta,d); h=LD(d-.5)
        DT=np.sum(weight*Q/delta)/(2*np.pi)
        DB=C*np.sum(weight*Q/delta*(radius+C*d)/(d+C*radius))/(2*np.pi)
        sample=d*S*S*np.sum(weight*R/(h+C*np.hypot(delta,h)))/(2*np.pi)
        integrand=R*(np.log((d+C*radius)/(C*delta))-C*np.arcsinh(d/delta))/(2*np.pi)
        # Only the first separation interval touches the logarithmic endpoint.
        # Integrate it adaptively; other intervals use their exact breakpoints.
        first,error=quad(lambda t:float(self.evaluate(t)[0]*(np.log((d+C*np.hypot(t,d))/(C*t))
                                  -C*np.arcsinh(d/t))/(2*np.pi)),0,float(self.knots[1]),
                         epsabs=2e-14,epsrel=2e-12,limit=200)
        assert error<2e-11
        integrated=LD(first)+np.sum(weight[1:]*integrand[1:])
        return dict(order=order,trefftz_drag=float(DT),bound_drag=float(DB),
                    sampled_attached_drag=float(sample),integrated_attached_drag=float(integrated),
                    sampled_total_difference_percent=float(100*((DB+sample)/DT-1)),
                    integrated_total_difference_percent=float(100*((DB+integrated)/DT-1)),
                    integrated_closure_error=float(abs(DB+integrated-DT)))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error('Use a fresh output directory.')
    inputs=[('attached-wake-forces-20261108-n64',5.),('attached-wake-forces-20261108-n128',5.),
            ('attached-wake-forces-20261108-n128-alpha1-residual-check',1.)]
    manifests={};saved=[];pins=None
    for folder,alpha in inputs:
        p=ROOT/'artifacts/isae'/folder
        verify=json.loads((p/'verification.json').read_text())
        for name,digest in verify['artifacts'].items():assert sha(p/name)==digest
        manifests[str(p.relative_to(ROOT))]=sha(p/'verification.json')
        plan=json.loads((p/'plan.json').read_text())
        if pins is None:pins=plan['unchanged_pins']
        assert pins==plan['unchanged_pins']
        saved.append((p,alpha))
    for name,digest in pins.items():assert sha(ROOT/name)==digest
    args.output.mkdir(parents=True);shutil.copyfile(__file__,args.output/'driver-used.py')
    write(args.output/'plan.json',dict(observed_utc=utc(),unchanged_pins=pins,input_manifests=manifests,
        previous_turn='progress: completed solved attached-leg controls and identified force sampling/endpoint limitations',
        reconstruction='Interpolate original Gamma at original bound-interval midpoints linearly, with zero at physical tips; no regression or force/reference fit.',
        geometry='Planar zero-incidence replay of the +30 degree straight bound line; original Gamma is retained, local chord is flattened.',
        force='Pure vortex Kutta-Joukowski bound force, plus sampled or globally chord-integrated AT force. No section-polar magnitude closure.',
        quadrature_orders=[4,8,16],new_circulation_solves=0,
        limitations=['Reconstruction changes the circulation representation and flattens the original incidence; not a native state.',
                     'Integrated total-drag identity does not prove local force/velocity convergence or a winglet-root fix.']))
    records=[];started=time.monotonic()
    try:
        for p,alpha in saved:
            with np.load(p/'sweep-+30.npz') as data:
                nodes=np.r_[data['q'][0]@data['span'],data['mid']@data['span'],data['q'][-1]@data['span']]
                values=np.r_[0.,data['gamma'],0.]
            corr=Correlation(nodes,values)
            discrepancies=[]
            for delta in (.0001,.007,.07,.5,2.,7.5):
                actual=corr.evaluate(delta);expected=corr.direct(LD(delta))
                discrepancies.append(float(max(abs(actual[0]-expected[0]),abs(actual[1]-expected[1]))))
            assert max(discrepancies)<2e-11
            results=[corr.forces(n) for n in (4,8,16)]
            final_difference=max(abs(results[-1][key]-results[-2][key]) for key in
                ('trefftz_drag','bound_drag','sampled_attached_drag','integrated_attached_drag'))
            assert final_difference<2e-11,final_difference
            assert results[-1]['integrated_closure_error']<2e-9
            n=len(values)-2
            np.savez_compressed(args.output/f'alpha{alpha:g}-n{n}.npz',nodes=nodes,gamma=values,
                                correlation_knots=corr.knots,R=corr.R,dR=corr.dR,Q=corr.Q)
            row=dict(source=str(p.relative_to(ROOT)),original_incidence_degrees=alpha,original_panels=n,
                     correlation_intervals=len(corr.knots)-1,maximum_direct_correlation_error=max(discrepancies),
                     terminal_R=float(corr.R[-1]),terminal_Q=float(corr.Q[-1]),
                     final_quadrature_change=final_difference,results=results)
            records.append(row);print(json.dumps(row),flush=True)
        for name,digest in pins.items():assert sha(ROOT/name)==digest
        write(args.output/'results.json',dict(observed_utc=utc(),records=records,seconds=time.monotonic()-started))
        write(args.output/'verification.json',dict(status='verified',observed_utc=utc(),
            artifacts={p.name:sha(p) for p in sorted(args.output.iterdir()) if p.is_file()},unchanged_pin_count=len(pins)))
    except Exception as exc:
        write(args.output/'failure.json',dict(observed_utc=utc(),error_type=type(exc).__name__,error=str(exc),completed_records=records))
        raise


if __name__=='__main__':main()
