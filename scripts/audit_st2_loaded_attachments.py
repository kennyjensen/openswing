"""Independent rigid-arm kinematics and terminal-evidence audit; no solves."""
from pathlib import Path
import verify_sa14_defaults as common

ROOT=common.ROOT
OUT=ROOT/'artifacts/isae/st2-loaded-attachment-modes-20261109/replay'


def main():
    common.bounded()
    import numpy as np
    plan=common.read(OUT/'plan.json'); common.authenticate(plan['pins'])
    summary=common.read(OUT/'summary.json')
    assert summary['plan_sha256']==common.sha(OUT/'plan.json') and summary['passed']
    states=[]; rows=[]
    for i,job in enumerate(plan['jobs']):
        receipt=common.read(OUT/f'execution-{i}.json')
        assert receipt['returncode']==0 and receipt['terminal_utc'] and not receipt.get('timeout')
        folder=OUT/f'job-{i}'; report=common.read(folder/'report.json')
        assert report==summary['states'][i]
        for name,digest in report['artifacts'].items(): assert common.sha(folder/name)==digest
        result=common.read(folder/'result.json'); nodes=result['base']['nodes']; n=len(nodes)
        assert [v['index'] for v in nodes]==list(range(n))
        main_nodes=[k for k,v in enumerate(nodes) if v['beam']==1]
        tip=main_nodes[-1]; end=n-1
        r=np.asarray([v['position'] for v in nodes]); q=np.asarray([v['rotation'] for v in nodes])
        # These two declared straight jig spans determine the state length units.
        length=.55 if job['variant']=='pylon' else .558
        jig=np.asarray([v['jig_position'] for v in nodes])
        assert abs(np.linalg.norm(np.ptp(jig,axis=0))-length)<1e-15
        positive=sorted([m for m in result['modes'] if m['eigenvalue'][1]>1e-6],key=lambda m:m['eigenvalue'][1])
        modes=[]
        for k,mode in enumerate(positive):
            vector=np.asarray(mode['right']['real'])+1j*np.asarray(mode['right']['imag'])
            geometry=vector[:6*n].reshape(n,6); dr=length*geometry[:,:3]; theta=geometry[:,3:]
            scale=max(float(np.max(np.linalg.norm(dr,axis=1))+.55*np.max(np.linalg.norm(theta,axis=1))),1e-30)
            motion=dr[tip]+np.cross(theta[tip],q[tip]@np.array([.05,.008,0.]))
            check=dict(job=i,ordinal=k+1,extension_position=0.,extension_rotation=0.,point_motion=0.)
            if job['variant']=='extension':
                for j in range(tip+1,n):
                    expected=dr[tip]+np.cross(theta[tip],r[j]-r[tip])
                    check['extension_position']=max(check['extension_position'],float(np.linalg.norm(dr[j]-expected)/scale))
                    check['extension_rotation']=max(check['extension_rotation'],float(.55*np.linalg.norm(theta[j]-theta[tip])/scale))
                actual=dr[end]+np.cross(theta[end],q[end]@np.array([.05,0.,0.]))
                check['point_motion']=float(np.linalg.norm(motion-actual)/scale)
                assert max(check[name] for name in ('extension_position','extension_rotation','point_motion'))<1e-7
                motion=actual
            modes.append(dict(main=np.column_stack((dr[main_nodes]/.55,theta[main_nodes])).ravel(),
                point=motion,lam=complex(*mode['eigenvalue']),scale=scale))
            rows.append(check)
        states.append(modes)
    pairs=[]
    for i,j in ((0,1),(2,3)):
        for k,(left,right) in enumerate(zip(states[i],states[j],strict=True)):
            # Eigenvector amplitude/phase is arbitrary; match main-wing geometry only.
            factor=np.vdot(right['main'],left['main'])/np.vdot(right['main'],right['main'])
            motion_error=float(np.linalg.norm(left['point']-factor*right['point'])/left['scale'])
            a=left['lam']*left['point']; b=factor*right['lam']*right['point']
            mass_action_left=3*float(np.vdot(a,a).real); mass_action_right=3*float(np.vdot(b,b).real)
            mass_relative=abs(mass_action_left-mass_action_right)/max(mass_action_left,mass_action_right,1e-30)
            assert motion_error<1e-7 and mass_relative<1e-7
            pairs.append(dict(left=i,right=j,ordinal=k+1,point_motion_relative=motion_error,
                              point_velocity_mass_quadratic_relative=mass_relative))
    common.write(OUT/'attachment-audit.json',dict(observed_utc=common.utc(),
        script_sha256=common.sha(Path(__file__)),plan_sha256=common.sha(OUT/'plan.json'),
        summary_sha256=common.sha(OUT/'summary.json'),all_children_terminal=True,
        rigid_arm_checks=rows,paired_point_checks=pairs,solver_calls=0,production_imports=0,
        maximum_kinematic_error=max(r[k] for r in rows for k in ('extension_position','extension_rotation','point_motion')),
        maximum_paired_point_motion_error=max(r['point_motion_relative'] for r in pairs),
        maximum_point_velocity_mass_quadratic_error=max(r['point_velocity_mass_quadratic_relative'] for r in pairs),
        counts_changed=False,native_parsing_verified=False))
    print(dict(states=4,rigid_extension_modes=12,paired_modes=len(pairs),
        maximum_point_motion_error=max(r['point_motion_relative'] for r in pairs),
        maximum_mass_quadratic_error=max(r['point_velocity_mass_quadratic_relative'] for r in pairs)))


if __name__=='__main__':main()
