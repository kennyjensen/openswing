"""Reproduce the inclined discrete equations and test controlled grid halving."""
from hashlib import sha256
import json
from pathlib import Path
import numpy as np
from isae_ua_discrete_reference import derivative_weights,kinematics
from isae_ua_wing_incidence_refined import AccurateInclinedWing

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/ua2-incidence-startup-20261101'


def discrete(wing,times):
    times=np.array(times);motion=[wing.motion(t,.5,.95,10.) for t in times]
    acceleration=np.array([r[2] for r in motion]);velocity,position=kinematics(times,acceleration)
    gamma=np.zeros((len(times),20));rate=np.zeros_like(gamma);lift=np.zeros(len(times))
    gamma[0]=wing.steady();lift[0]=wing.fields(gamma[0],velocity[0],acceleration[0],rate=rate[0])['CL']
    maximum_residual=0.;maximum_iterations=0
    for i in range(1,len(times)):
        k0,_,k2=derivative_weights(times,i);previous=gamma[i-1];older=gamma[max(0,i-2)]
        current=previous.copy()
        for iteration in range(12):
            derivative=k0*(current-previous)+k2*(older-previous)
            residual=derivative-wing.rates(current,velocity[i])
            error=float(np.max(abs(residual)))
            if error<1e-9:break
            current-=np.linalg.solve(k0*np.eye(20)-wing.jacobian(current,velocity[i]),residual)
        else:raise RuntimeError(f'Independent discrete solve failed: {i}, {error}')
        gamma[i]=current;rate[i]=derivative
        lift[i]=wing.fields(current,velocity[i],acceleration[i],rate=rate[i])['CL']
        maximum_residual=max(maximum_residual,error);maximum_iterations=max(maximum_iterations,iteration)
    return dict(circulation=gamma,circulation_rate=rate,CL=lift,velocity=velocity,position=position,
        maximum_residual=maximum_residual,maximum_iterations=maximum_iterations)


def main():
    assert not (BASE/'grid-diagnostic.json').exists()
    paths=[Path(__file__).resolve(),BASE/'audit.json',*[ROOT/'scripts'/n for n in
        ('isae_ua_discrete_reference.py','isae_ua_wing_incidence.py','isae_ua_wing_incidence_refined.py','isae_ua_wing_nonlinear.py')]]
    pins={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in paths}
    (BASE/'grid-diagnostic-plan.json').write_text(json.dumps(dict(source_sha256=pins,
        identity_gate_fraction=1e-7,scope='Independent discrete reproduction and prediction on a nested grid; no production pass added.'),indent=2)+'\n')
    audit=json.loads((BASE/'audit.json').read_text());wing=AccurateInclinedWing(20,alpha_deg=9.)
    results={}
    for n,saved in audit['results'].items():
        rows=saved['rows'];times=np.array([r['time'] for r in rows]);calc=discrete(wing,times)
        differences={}
        for key in ('CL','circulation','circulation_rate'):
            observed=np.array([r[key] for r in rows]);scale=np.max(abs(observed),axis=0)
            differences[key]=float(np.max(abs(calc[key]-observed)/scale))
        differences['velocity']=float(np.max(abs(calc['velocity']-[r['heave_velocity'] for r in rows]))/4.75)
        differences['position']=float(np.max(abs(calc['position']-[r['heave_position'] for r in rows]))/.25)
        assert max(differences.values())<1e-7
        results[n]=dict(identity_differences=differences,maximum_equation_residual=calc['maximum_residual'])
    coarse=[r['time'] for r in audit['results']['160']['rows']]
    times=np.array([0.,*[v for a,b in zip(coarse,coarse[1:]) for v in ((a+b)/2,b)]])
    np.testing.assert_allclose(times[::2],coarse,atol=0,rtol=0)
    calc=discrete(wing,times)
    expected=wing.integrate(times,amplitude_ratio=.5,k=.95)['rows']
    steady=wing.steady();steady_cl=wing.fields(steady,0.,0.)['CL'];errors={}
    for key in ('CL','circulation','circulation_rate'):
        target=np.array([r[key] for r in expected])
        center=steady_cl if key=='CL' else steady if key=='circulation' else 0.
        scale=np.max(abs(target-center),axis=0)
        errors[key]=float(np.max(abs(calc[key]-target)/scale))
    ratios={k:errors[k]/audit['results']['160']['error_fractions'][k] for k in errors}
    output=dict(identity_results=results,nested_grid=times.tolist(),predicted_errors=errors,
        predicted_ratios=ratios,prediction_only=True,native_ASWING_comparison=False,source_sha256=pins)
    assert all(sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in pins.items())
    (BASE/'grid-diagnostic.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps({k:v for k,v in output.items() if k not in ('nested_grid','source_sha256')}))


if __name__=='__main__':main()
