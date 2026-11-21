"""Separate cross-surface kernel/core and geometry conventions on saved runs."""
import argparse
from check_daedalus_load_sensitivity import ROOT,read
from daedalus_bounded_job import run

STUDY=ROOT/'artifacts/daedalus-coupled-avl-20261114'
TAGS=['base','yaw-plus','yaw-minus','roll-plus','roll-minus']
STAGES=['native','source_kernel','source_core','control_point','normal','force_receiver','force_vector','moment_arm']


def analyze(folder,args):
    import numpy as np
    from openswing.factored_influence import FactoredInfluence
    from avl_vorvelc_reference import matrix as native_matrix
    with np.load(STUDY/'base/geometry.npz') as saved:g={k:saved[k] for k in saved.files}
    with np.load(STUDY/'base/native-fields.npz') as saved:base={k:saved[k] for k in saved.files}
    n=len(g['a']);physical=g['physical'];same=physical[:,None]==physical[None,:]
    transverse=np.linalg.norm((base['RV2']-base['RV1'])[:,1:],axis=1)
    native_core=g['native_core_fraction']*transverse[None,:]
    source_core=np.where(same,0.,np.maximum(.25*g['chord'],g['ds'])[None,:])
    operators={};geometry={};arrays={};cases=[]
    for stage,label in enumerate(STAGES):
        cp=base['RC'] if stage<3 else g['cp'];normal=base['ENC'] if stage<4 else g['normal']
        hv=base['RV'] if stage<5 else g['hv'];dl=base['RV2']-base['RV1'] if stage<6 else g['force_vector']
        location=base['RV'] if stage<7 else g['moment_location']
        if stage==0:
            icp=native_matrix(cp,g['a'],g['b'],0.,core_fraction=g['native_core_fraction'])
            ihv=native_matrix(hv,g['a'],g['b'],0.,core_fraction=g['native_core_fraction'],exclude_self=True)
        else:
            core=native_core if stage==1 else source_core
            icp=FactoredInfluence(cp,g['a'],g['b'],[1.,0.,0.],np.eye(3),core).matrix()
            ihv=FactoredInfluence(hv,g['a'],g['b'],[1.,0.,0.],np.eye(3),core,exclude_bound=np.eye(n,dtype=bool)).matrix()
        operators[label]=(np.einsum('ijk,ik->ij',icp,normal),ihv)
        geometry[label]=(cp,normal,hv,dl,location)
        arrays[label+'_cp_velocity']=icp;arrays[label+'_hv_velocity']=ihv
    native_errors=[];source_errors=[]
    for tag in TAGS:
        result=read(STUDY/tag/'result.json');source=read(STUDY/tag/'openswing.json')
        with np.load(STUDY/tag/'native-fields.npz') as saved:f={k:saved[k] for k in saved.files}
        for name in ('RV1','RV2','RC','ENC','RV','VINF'):np.testing.assert_array_equal(base[name],f[name])
        rates=np.zeros(3);rates[{'x':0,'y':1,'z':2}[result['axis']]]=result['rate_rad_per_length']
        stages=[]
        for stage,label in enumerate(STAGES):
            operator,ihv=operators[label];cp,normal,hv,dl,location=geometry[label]
            free=f['VINF']+np.cross(cp-g['reference'][3],rates)
            gamma=np.linalg.solve(operator,-np.sum(free*normal,axis=1))
            induced=np.einsum('ijk,j->ik',ihv,gamma)
            velocity=f['VINF']+np.cross(hv-g['reference'][3],rates)+induced
            force=gamma[:,None]*np.cross(velocity,dl);moment=np.cross(location-g['reference'][1],force)
            wrenches={str(beam):np.r_[force[g['beam']==beam].sum(axis=0),moment[g['beam']==beam].sum(axis=0)].tolist() for beam in (1,2,3,5)}
            wrench=np.r_[force.sum(axis=0),moment.sum(axis=0)]
            error=float(max(abs(operator@gamma+np.sum(free*normal,axis=1))));assert error<1e-11
            stages.append(dict(name=label,wrench=wrench.tolist(),surfaces=wrenches,circulation=gamma.tolist(),residual=error))
            if stage==0:
                errors=dict(gamma=float(max(abs(gamma-f['GAM'].ravel()))),
                    induced=float(np.max(abs(induced-f['VV']))),wrench=float(max(abs(wrench-result['native_circulatory_wrench']))))
                assert max(errors.values())<2e-10,errors
                native_errors.append(errors)
            if stage==len(STAGES)-1:
                errors=dict(gamma=float(max(abs(gamma-np.array([s['circulation'] for s in source['strips']])))),
                    velocity=float(np.max(abs(velocity-np.array([s['relative_velocity'] for s in source['strips']])))),
                    wrench=float(max(abs(wrench-result['openswing_circulatory_wrench']))))
                assert max(errors.values())<2e-10,errors
                source_errors.append(errors)
        cases.append(dict(tag=tag,axis=result['axis'],rate=result['rate_rad_per_length'],stages=stages))
    derivatives=[]
    for axis in ('x','z'):
        plus=next(c for c in cases if c['axis']==axis and c['rate']>0)
        minus=next(c for c in cases if c['axis']==axis and c['rate']<0)
        divisor=plus['rate']-minus['rate']
        stages=[]
        for p,m in zip(plus['stages'],minus['stages']):
            surfaces={beam:((np.array(p['surfaces'][beam])-m['surfaces'][beam])/divisor).tolist() for beam in p['surfaces']}
            stages.append(dict(name=p['name'],wrench=((np.array(p['wrench'])-m['wrench'])/divisor).tolist(),surfaces=surfaces))
        derivatives.append(dict(axis=axis,stages=stages))
    np.savez_compressed(folder/'operators.npz',**arrays,native_core=native_core,source_core=source_core,**g)
    for derivative in derivatives:
        print('axis',derivative['axis'],flush=True)
        for s in derivative['stages']:print(s['name'],'total Mx/Mz',s['wrench'][3::2],'fin Fy/Mz',[s['surfaces']['3'][j] for j in (1,5)],flush=True)
    return dict(stages=STAGES,cases=cases,derivatives=derivatives,native_replay_errors=native_errors,source_replay_errors=source_errors,
        qualification='Ordered conditional differences on fixed loaded geometry and prescribed rigid-body rates. Native and source endpoints are verified. Core-kernel, core-radius, receiver, normal and force-convention changes are diagnostics, not proposed production substitutions or additive physical error sources.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--tag',required=True);args=vars(parser.parse_args())
    inputs=[ROOT/'scripts/check_daedalus_coupled_avl.py',ROOT/'scripts/avl_vorvelc_reference.py',
        ROOT/'docs/validation/aswing-authoritative-sources.json',ROOT/'reference/aswing-authoritative-20261108/drela-aswing-steady.pdf']
    inputs += [STUDY/tag/name for tag in TAGS for name in ('native-fields.npz','geometry.npz','openswing.json','result.json','terminal.json','native-terminal.json')]
    inputs += list((ROOT/'openswing').glob('*.py'))
    run(STUDY,args['tag'],inputs,analyze,args,__file__)


if __name__=='__main__':main()
