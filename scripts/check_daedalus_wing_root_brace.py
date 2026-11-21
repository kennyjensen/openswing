"""Verify the shared component brace law/tangent against production loads."""
import argparse
from check_daedalus_load_sensitivity import ROOT,read
from daedalus_bounded_job import run
STUDY=ROOT/'artifacts/daedalus-wing-root-20261114'


def work(folder,args):
    import numpy as np
    from scipy.spatial.transform import Rotation
    from openswing.asw import parse_asw
    from openswing.geometry import surface_frame
    from openswing.struts import strut_load
    from daedalus_wing_root_reference import brace_state
    fixture=read(STUDY/'prepare/fixture.json');model=parse_asw((ROOT/'examples/dae.asw').read_text(),beam_interpolation='drela-segspl-v1')
    row,=[r for r in model.records['strut'] if int(r[0])==1 and r[1]>0];beam=model.beams[0]
    jig_frame=surface_frame(beam,row[1]);jig_arm=row[2:5]-beam.position(row[1]);states=[]
    for tag in ('compact-14-v3','n28-v2','n56'):
        data=np.load(STUDY/tag/'arrays.npz');index,=np.flatnonzero(data['stations']==row[1])
        states.append((tag,data['positions'][index],data['frames'][index]))
    data=np.load(STUDY/'samples-tight-dip/arrays.npz');index,=np.flatnonzero(data['stations']==row[1])
    states.append(('continuum',data['base_state'][index,:3],data['base_state'][index,3:12].reshape(3,3)))
    results=[];saved={}
    for tag,position,frame in states:
        def physical(delta):
            r=position+delta[:3];q=Rotation.from_rotvec(delta[3:]).as_matrix()@frame@jig_frame.T
            arm=q@jig_arm;native=strut_load(row,r+arm)
            return np.r_[native['force'],np.cross(arm,native['force'])]
        reference=brace_state(position,frame,fixture['brace']);exact=reference['tangent']
        baseline_error=float(max(abs(physical(np.zeros(6))-np.r_[reference['force'],reference['moment']])));assert baseline_error<2e-10
        stencils=[]
        for step in (1e-3,5e-4):
            matrix=np.empty((6,6))
            for j in range(6):
                delta=np.zeros(6);delta[j]=step
                matrix[:,j]=(8*(physical(delta)-physical(-delta))-(physical(2*delta)-physical(-2*delta)))/(12*step)
            stencils.append(matrix)
        scales=np.array([100.]*3+[5600.]*3)[:,None]
        error=float(np.max(abs((stencils[-1]-exact)/scales)))
        step_error=float(np.max(abs((stencils[-1]-stencils[0])/scales)))
        assert error<2e-8 and step_error<2e-8,(error,step_error)
        results.append(dict(state=tag,base_wrench_error=baseline_error,scaled_tangent_error=error,scaled_step_error=step_error))
        saved[tag+'_analytic']=exact;saved[tag+'_stencil']=stencils[-1]
    np.savez_compressed(folder/'arrays.npz',**saved)
    return dict(cases=results,qualification='The native compact adapter and continuum share the explicit brace helper. This separate comparison checks its force, rotating-arm couple and tangent against production strut_load at four loaded states; it does not establish historical ASWING brace-law equivalence.')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--tag',required=True);args=vars(p.parse_args())
    inputs=[ROOT/'scripts/daedalus_wing_root_reference.py',ROOT/'examples/dae.asw',STUDY/'prepare/fixture.json',ROOT/'docs/validation/ISAE_STATUS.md']
    inputs+=list((ROOT/'openswing').glob('*.py'))
    inputs += [STUDY/tag/'arrays.npz' for tag in ('compact-14-v3','n28-v2','n56','samples-tight-dip')]
    run(STUDY,args['tag'],inputs,work,args,__file__)


if __name__=='__main__':main()
