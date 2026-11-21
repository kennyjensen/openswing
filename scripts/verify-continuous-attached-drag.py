"""Continuous polynomial circulation: attached-force sampling versus integration.

Straight planar wing, prescribed Gamma, no circulation solve or core. Exact
polynomial correlations reduce the double integrals to one-dimensional ones.
Independent direct velocity integration checks the reduced force expressions.
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
from numpy.polynomial import Polynomial as Poly
from numpy.polynomial.legendre import leggauss
from scipy.integrate import quad

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from openswing.aero import semi_infinite_vortex


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def utc(): return datetime.now(timezone.utc).isoformat()


def portable(x):
    if isinstance(x, np.ndarray): return x.tolist()
    if isinstance(x, np.generic): return x.item()
    if isinstance(x, dict): return {k: portable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)): return [portable(v) for v in x]
    return x


def write(p, value): p.write_text(json.dumps(portable(value), indent=2, allow_nan=False)+'\n')


def correlation(first, second, length):
    """Exact coefficient arithmetic for integral f(s) g(s-delta) ds.

    delta >= 0; compact support [-L,L] overlaps over [delta-L,L].
    No regression or fitted polynomial coefficients are used.
    """
    delta = Poly([0., 1.]); lower = delta-length
    shifted = [sum((float(second.coef[j])*math.comb(j,k)*(-delta)**(j-k)
                    for j in range(k,len(second.coef))), Poly([0.]))
               for k in range(len(second.coef))]
    result = Poly([0.])
    for i, a in enumerate(first.coef):
        for j, b in enumerate(shifted):
            power = i+j+1
            result += a*b*(length**power-lower**power)/power
    return result


def integrate(function, upper):
    value, error = quad(function, 0., upper, epsabs=2e-13, epsrel=2e-12, limit=200)
    assert error < 1e-10, error
    return float(value), float(error)


def attached_quarter(s, gamma, length, attached_length):
    """Analytic PV velocity from the continuum of finite chordwise legs."""
    # Gamma'(s+u)=g1+2*g2*u+3*g3*u^2, and density is -Gamma'.
    g1 = gamma.deriv()(s)
    g2 = gamma.deriv(2)(s)/2
    g3 = gamma.coef[3] if len(gamma.coef)>3 else 0.
    h = attached_length
    def primitives(u):
        r = np.hypot(u,h)
        return np.log(abs(u)/(r+h)), h*np.arcsinh(u/h), h*r
    left = primitives(-length-s); right = primitives(length-s)
    return (g1*(right[0]-left[0])+2*g2*(right[1]-left[1])+3*g3*(right[2]-left[2]))/(4*np.pi)


def direct(sweep, gamma, length, d, order):
    """Direct vector Biot-Savart wake quadrature, independent of pair kernels."""
    nodes, weights = leggauss(order)
    s, weights = length*nodes, length*weights
    lam = np.deg2rad(sweep); C, S = np.cos(lam), np.sin(lam)
    span = np.array([S,C,0.]); chord = np.array([C,-S,0.])
    q = s[:,None]*span; te = q+d*chord
    density = -gamma.deriv()(s)
    # Use the production vector kernel here, not the scalar pair formulas.
    free_q = semi_infinite_vortex(q[:,None],te[None],np.array([1.,0.,0.]))[:,:,2]@(density*weights)
    points = q+.5*chord
    free_at = semi_infinite_vortex(points[:,None],te[None],np.array([1.,0.,0.]))[:,:,2]@(density*weights)
    at_q = attached_quarter(s,gamma,length,d)
    bound_drag = -C*np.dot(weights*gamma(s),free_q+at_q)
    # The globally integrated bound and attached self-fields cancel from AT
    # drag for compact continuous Gamma. This checks the remaining free field.
    at_drag = -S*d*np.dot(weights*gamma.deriv()(s),free_at)
    return dict(order=order,bound_drag=float(bound_drag),sampled_attached_drag=float(at_drag))


def case(sweep, asymmetry, length=5., scale=.2, d=.75):
    started = time.monotonic()
    gamma = Poly([scale, scale*asymmetry/length, -scale/length**2, -scale*asymmetry/length**3])
    gradient = gamma.deriv()
    R = correlation(gradient,gradient,length)
    Q = correlation(gamma,gradient,length)
    # Analytically Q(0)=integral Gamma*Gamma'=0 since both endpoint values vanish.
    assert abs(Q.coef[0])<1e-14
    original_constant=float(Q.coef[0]); Q.coef[0]=0.
    np.testing.assert_allclose(Q.deriv().coef,R.coef,atol=2e-16,rtol=2e-13)
    assert abs(Q(2*length))<2e-13
    q_over_delta=Poly(Q.coef[1:])
    C=np.cos(np.deg2rad(sweep)); S=np.sin(np.deg2rad(sweep))
    upper=2*length
    DT=float(q_over_delta.integ()(upper)/(2*np.pi))
    DB,eb=integrate(lambda delta:C*q_over_delta(delta)*
        (np.hypot(delta,d)+C*d)/(d+C*np.hypot(delta,d))/(2*np.pi),upper)
    h=d-.5
    DA_sample,es=integrate(lambda delta:d*S*S*R(delta)/
                          (h+C*np.hypot(delta,h))/(2*np.pi),upper)
    if abs(S)<1e-14:
        DA_exact,ee=0.,0.
    else:
        # Integrate the symmetric wake kernel along the attached leg FIRST.
        # Its logarithmic delta=0 endpoint is integrable, not cut off.
        DA_exact,ee=integrate(lambda delta:R(delta)*(np.log((d+C*np.hypot(delta,d))/(C*delta))
                   -C*np.arcsinh(d/delta))/(2*np.pi),upper)
    conservation_error=abs(DB+DA_exact-DT)
    assert conservation_error<2e-11
    # Independent correlation checks at interior separations by direct products.
    correlation_error=0.
    for delta in (.07,.5,2.,7.5):
        rr,_=quad(lambda s:gradient(s)*gradient(s-delta),delta-length,length,epsabs=1e-13)
        qq,_=quad(lambda s:gamma(s)*gradient(s-delta),delta-length,length,epsabs=1e-13)
        correlation_error=max(correlation_error,abs(rr-R(delta)),abs(qq-Q(delta)))
    assert correlation_error<2e-13
    raw=[direct(sweep,gamma,length,d,n) for n in (64,128,256)]
    for row in raw:
        row['bound_error']=abs(row['bound_drag']-DB)
        row['sampled_attached_error']=abs(row['sampled_attached_drag']-DA_sample)
    assert raw[-1]['bound_error']<2e-9
    assert raw[-1]['sampled_attached_error']<2e-9
    # Verify the symmetrized semi-infinite kernel algebra independently.
    span=np.array([S,C,0.]);chord=np.array([C,-S,0.])
    kernel_error=0.
    for distance in (.25,.75):
        for delta in (0.,.1,.5,2.):
            plus=semi_infinite_vortex(delta*span-distance*chord,np.zeros(3),np.array([1.,0.,0.]))[2]
            minus=semi_infinite_vortex(-delta*span-distance*chord,np.zeros(3),np.array([1.,0.,0.]))[2]
            r=np.hypot(delta,distance)
            expected_sum=S/(2*np.pi*(distance+C*r))
            expected_difference=delta/(2*np.pi*r*(distance+C*r))
            kernel_error=max(kernel_error,abs(plus+minus-expected_sum),abs(plus-minus-expected_difference))
    assert kernel_error<2e-13
    return dict(sweep_degrees=sweep,asymmetry=asymmetry,gamma_coefficients=gamma.coef,
        gradient_correlation_coefficients=R.coef,cross_correlation_coefficients=Q.coef,
        analytically_zero_Q_constant_before_enforcement=original_constant,
        trefftz_drag=DT,bound_drag=DB,sampled_attached_drag=DA_sample,integrated_attached_drag=DA_exact,
        sampled_total_drag=DB+DA_sample,integrated_total_drag=DB+DA_exact,
        sampled_total_difference_percent=100*((DB+DA_sample)/DT-1),
        integrated_total_difference_percent=100*((DB+DA_exact)/DT-1),
        conservation_error=conservation_error,maximum_correlation_error=correlation_error,
        maximum_pair_kernel_error=kernel_error,quadrature_error_estimates=[eb,es,ee],
        direct_checks=raw,seconds=time.monotonic()-started)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error('Use a fresh output directory.')
    pins={str(p.relative_to(ROOT)):sha(p) for p in sorted(ROOT.glob('openswing/**/*.py'))+
          [ROOT/'docs/validation/ISAE_STATUS.md',ROOT/'docs/validation/isae-progress-scopes.json']}
    args.output.mkdir(parents=True);shutil.copyfile(__file__,args.output/'driver-used.py')
    plan=dict(observed_utc=utc(),previous_turn='progress: solved attached-leg forces reduced drag discrepancy but retained endpoint fields and a sub-percent gap',
        unchanged_pins=pins,sweeps=[0,30,-30],asymmetries=[0.,.2],half_arclength=5.,chord=1.,
        gamma_scale=.2,gamma='G*(1-s^2/L^2)*(1+a*s/L)',attached_length=.75,attached_force_sample=.5,
        speed=1.,density=1.,incidence=0.,core=0.,new_circulation_solves=0,
        bound_force='Kutta-Joukowski on the bound line; no section polar/force-magnitude closure.',
        sampled_attached='Single sample at 3/4 chord, times full attached length.',
        integrated_attached='Analytic chord integral of the globally summed free-wake force; self-field cancellation requires continuous Gamma with zero endpoints.',
        reference='Continuous Trefftz energy, equivalently the integrated continuous Hilbert downwash.',
        limitations=['Prescribed circulation does not solve this zero-incidence boundary condition.',
                     'Flat straight line and equal chord only; no actual SA-11 fork or curved force law.',
                     'A finite integrated drag does not establish finite local forces or velocities.',
                     'No acceptance or reference replacement for native ASWING.'],
        gates=dict(conservation_absolute=2e-11,direct_force_absolute=2e-9,pair_kernel=2e-13))
    write(args.output/'plan.json',plan);rows=[]
    try:
        for asymmetry in plan['asymmetries']:
            for sweep in plan['sweeps']:
                row=case(sweep,asymmetry);rows.append(row)
                print(json.dumps(portable(row)),flush=True)
        for name,digest in pins.items():assert sha(ROOT/name)==digest,name
        write(args.output/'results.json',dict(observed_utc=utc(),records=rows))
        write(args.output/'verification.json',dict(status='verified',observed_utc=utc(),
            artifacts={p.name:sha(p) for p in sorted(args.output.iterdir()) if p.is_file()},unchanged_pin_count=len(pins)))
    except Exception as exc:
        write(args.output/'failure.json',dict(observed_utc=utc(),error_type=type(exc).__name__,error=str(exc),completed_records=rows))
        raise


if __name__=='__main__':main()
