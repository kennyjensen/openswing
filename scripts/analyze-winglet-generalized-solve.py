"""Independent saved-state arithmetic and comparison; no new solver calls."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
FINITE=ROOT/'artifacts/isae/winglet-finite-chord-20261107'
BASELINE=ROOT/'artifacts/isae/unswept-winglet-junction-20261107'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def cross(a,b):
    return np.array([a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batches',type=Path,nargs=3,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error('Use a fresh output directory.')
    finite_verify=json.loads((FINITE/'verification.json').read_text())
    assert all(sha(FINITE/p)==pin for p,pin in finite_verify['artifacts'].items())
    finite=json.loads((FINITE/'results.json').read_text())
    baseline_verify=json.loads((BASELINE/'verification.json').read_text())
    assert all(sha(BASELINE/p)==pin for p,pin in baseline_verify['artifacts'].items())
    baseline={r['request']['main_intervals']:r['result'] for r in json.loads((BASELINE/'results.json').read_text())
              if r['request']['sampling']=='arithmetic-control'}
    rows=[];states={};audits=[];all_pins=[]
    for batch in args.batches:
        plan=json.loads((batch/'plan.json').read_text());verification=json.loads((batch/'verification.json').read_text())
        assert all(sha(batch/p)==pin for p,pin in verification['artifacts'].items())
        assert all(sha(ROOT/p)==pin for p,pin in plan['unchanged_pins'].items())
        current=json.loads((batch/'results.json').read_text())
        assert [r['request'] for r in current]==plan['requests'] and len(current)==3
        all_pins.append(dict(batch=str(batch),results_sha256=sha(batch/'results.json'),plan_sha256=sha(batch/'plan.json')))
        for row in current:
            key=(row['request']['main_intervals'],row['request']['mode'])
            assert key not in states
            path=batch/row['artifact']['path'];assert sha(path)==row['artifact']['sha256']
            with np.load(path) as store:data={k:store[k] for k in store.files}
            states[key]=data
            # Componentwise compensated field sum, scalar section equation,
            # and scalar force/moment arithmetic independent of driver einsum.
            velocities=[];residual=[];forces=[];moments=[]
            for i,gamma in enumerate(data['gamma']):
                v=np.array([math.fsum(float(a)*float(g) for a,g in zip(data['tensor'][i,:,k],data['gamma']))
                            +(1. if k==0 else 0.) for k in range(3)])
                va=math.fsum(float(a)*float(b) for a,b in zip(v,data['axial'][i]))
                vn=math.fsum(float(a)*float(b) for a,b in zip(v,data['normal'][i]))
                rp=gamma-math.pi*.1*math.hypot(va,vn)*math.atan2(vn,va)
                force=1.225*gamma*cross(v,data['dl'][i])
                velocities.append(v);residual.append(rp);forces.append(force);moments.append(cross(data['points'][i],force))
            velocities,forces,moments,residual=map(np.asarray,(velocities,forces,moments,residual))
            np.testing.assert_allclose(velocities,data['velocity'],atol=2e-12,rtol=2e-12)
            np.testing.assert_allclose(forces,data['forces'],atol=2e-13,rtol=2e-12)
            np.testing.assert_allclose(moments,data['moments'],atol=2e-13,rtol=2e-12)
            assert np.max(abs(residual))<1e-11 and row['status']=='converged'
            total_force=np.array([math.fsum(forces[:,k]) for k in range(3)])
            total_moment=np.array([math.fsum(moments[:,k]) for k in range(3)])
            np.testing.assert_allclose(total_force,row['force'],atol=2e-13,rtol=2e-12)
            np.testing.assert_allclose(total_moment,row['moment'],atol=2e-13,rtol=2e-12)
            assert abs(total_force[2]/.06125-row['CL'])<2e-12
            assert abs(total_force[0]/.06125-row['CD'])<2e-12
            assert abs(total_moment[1]/.006125-row['Cm'])<2e-12
            symmetry=max(abs(total_force[1]),abs(total_moment[0]),abs(total_moment[2]))
            assert symmetry<2e-12
            assert np.min(data['gamma'])>0. and row['minimum_axial_velocity']>0.
            audits.append(dict(request=row['request'],maximum_scalar_gamma_residual=float(np.max(abs(residual))),
                maximum_velocity_difference=float(np.max(abs(velocities-data['velocity']))),
                force_symmetry_absolute=float(symmetry)))
            rows.append(row)
    assert set(states)=={(n,m) for n in (50,100,200) for m in ('raw','connected','separate-groups')}
    comparisons=[]
    for row in rows:
        n=row['request']['main_intervals']
        if n not in (50,100):continue
        comparator=next(r for r in finite if r['chord_rows']==4 and r['main_span_intervals']==n)
        span_CL=comparator['loads']['all_spanwise']['force'][2]/.06125
        comparisons.append(dict(request=row['request'],finite_chord_case=comparator['case'],
            full_edge_CL_relative_difference_percent=100*(row['CL']/comparator['CL']-1),
            spanwise_only_CL_relative_difference_percent=100*(row['CL']/span_CL-1),
            full_edge_CD_relative_difference_percent=100*(row['CD']/comparator['CD']-1),
            baseline_aswing_CL_difference_percent=100*(row['CL']/baseline[n]['CL']-1),
            meaning='Model comparison with distinct force definitions; not an accuracy/pass score.'))
    refinement=[]
    for mode in ('raw','connected','separate-groups'):
        ordered=sorted([r for r in rows if r['request']['mode']==mode],key=lambda r:r['request']['main_intervals'])
        refinement.append(dict(mode=mode,
            coarse_to_fine_percent={k:100*(ordered[-1][k]/ordered[0][k]-1) for k in ('CL','CD','Cm','maximum_speed')},
            last_refinement_percent={k:100*(ordered[-1][k]/ordered[-2][k]-1) for k in ('CL','CD','Cm','maximum_speed')}))
    plt.rcParams.update({'font.size':9,'axes.grid':True,'grid.alpha':.23})
    fig,axes=plt.subplots(2,2,figsize=(10.5,7.3),constrained_layout=True)
    colors={'raw':'#0072B2','connected':'#009E73','separate-groups':'#D55E00'}
    labels={'raw':'Uncorrected NLL','connected':'Connected generalized NLL','separate-groups':'Generalized, separate groups'}
    for mode in colors:
        ordered=sorted([r for r in rows if r['request']['mode']==mode],key=lambda r:r['request']['main_intervals'])
        n=[r['request']['main_intervals'] for r in ordered]
        for ax,key in ((axes[0,0],'CL'),(axes[0,1],'CD'),(axes[1,0],'maximum_speed')):
            ax.plot(n,[r[key] for r in ordered],'o-',color=colors[mode],label=labels[mode])
        data=states[(100,mode)];mask=data['material_stations']>=0.
        axes[1,1].plot(data['material_stations'][mask],data['gamma'][mask],color=colors[mode],label=labels[mode])
    for ax,key in ((axes[0,0],'CL'),(axes[0,1],'CD')):
        ax.plot([50,100,200],[baseline[n][key] for n in (50,100,200)],':',color='.4',label='ASWING-style tangency')
        controls=[next(r for r in finite if r['chord_rows']==4 and r['main_span_intervals']==n) for n in (50,100)]
        ax.plot([50,100],[r[key] for r in controls],'ks--',label='4-row VLM, full edge loads')
        ax.set_xlabel('Main-wing span intervals N');ax.set_ylabel(key)
    axes[0,0].legend(fontsize=7)
    axes[0,0].set_title('Solved lift: different formulations remain distinct')
    axes[0,1].set_title('Solved drag')
    axes[1,0].set_xlabel('Main-wing span intervals N');axes[1,0].set_ylabel('Peak speed / freestream')
    axes[1,0].set_title('Velocity benefit survives the circulation solve')
    axes[1,1].set_xlabel('Material distance from center s [m]');axes[1,1].set_ylabel('Circulation [m²/s]')
    axes[1,1].axvline(.5,color='.5',linewidth=1);axes[1,1].set_xlim(0.,.7)
    axes[1,1].set_title('N100 circulation; winglet starts at s=0.5')
    fig.suptitle('Sharp unswept winglet — nonlinear section-equation comparison\n'
                 'Ideal section law; no ASWING reference validation or production change',fontsize=12)
    args.output.mkdir(parents=True)
    (args.output/'analysis-driver-used.py').write_bytes(Path(__file__).read_bytes())
    for ext in ('png','svg'):fig.savefig(args.output/('generalized-solve-comparison.'+ext),dpi=170)
    plt.close(fig)
    summary=dict(utc=datetime.now(timezone.utc).isoformat(),batch_pins=all_pins,solved_states=len(rows),
        converged_states=sum(r['status']=='converged' for r in rows),new_solves_in_analysis=0,
        scalar_audits=audits,model_comparisons=comparisons,refinement=refinement,
        maximum_gamma_residual=max(r['maximum_gamma_residual'] for r in rows),
        maximum_independent_scalar_gamma_residual=max(r['maximum_scalar_gamma_residual'] for r in audits),
        maximum_source_residual=max(r['maximum_source_residual'] for r in rows),
        maximum_source_equation_difference=max(r['maximum_source_equation_difference'] for r in rows),
        maximum_jacobian_directional_error=max(r['maximum_jacobian_directional_error'] for r in rows),
        numerical_solve_seconds=sum(r['seconds'] for r in rows),maximum_solve_seconds=max(r['seconds'] for r in rows),
        source_status_scope_verified_unchanged=True,all_gamma_and_axial_velocities_positive=True,
        finite_chord_result_sha256=sha(FINITE/'results.json'),baseline_result_sha256=sha(BASELINE/'results.json'),
        analysis_driver_sha256=sha(Path(__file__)),
        files={p.name:sha(p) for p in args.output.iterdir() if p.is_file()})
    (args.output/'analysis.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:summary[k] for k in ('solved_states','converged_states','maximum_independent_scalar_gamma_residual',
        'maximum_source_equation_difference','maximum_jacobian_directional_error','numerical_solve_seconds',
        'maximum_solve_seconds','refinement')},indent=2))


if __name__=='__main__':main()
