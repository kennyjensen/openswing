"""Bounded independent audit of all current beam compatibility Jacobian rows."""
import argparse
from pathlib import Path
from check_daedalus_load_sensitivity import ROOT,SOURCE,read
from check_daedalus_circulation_phase import dump,restore
from daedalus_bounded_job import run

STUDY=ROOT/'artifacts/daedalus-source-strain-20261114'
BALANCE=ROOT/'artifacts/daedalus-source-balance-20261114'
PROPERTIES=['EIcc','GJ','EInn','EIcs','EIcn','EIsn','EA','GKc','GKn','Cea','Nea','Cta','Nta']


def capture(folder,args):
    import numpy as np
    from check_daedalus_wing_paper import dynamic
    system=dynamic();n=system.network
    original=restore(BALANCE/'capture-dip/fixture.pkl');base=original['base']
    r,Q,N,M,_,_=n.unpack(system.base)
    for actual,expected in [(r,base['r']),(Q,base['Q']),(N,base['N']),(M,base['M'])]:np.testing.assert_array_equal(actual,expected)
    assert not np.any(n.offa) and not np.any(n.offb) and not np.any(n.damping_times)
    material={key:[] for key in PROPERTIES};body=[];beam_ids=[];stations=[]
    for mesh in n.meshes:
        beam=mesh.beam
        for key in PROPERTIES:
            material[key].append(np.c_[beam.value(key,mesh.t0,side='right'),beam.value(key,mesh.t1,side='left')])
        body.extend([not beam.lifting]*len(mesh.length));beam_ids.extend([beam.index]*len(mesh.length));stations.extend(mesh.tm)
    fixture=dict(ends=n.ends,positions=r,frames=np.stack([Q[n.a]@n.R0a,Q[n.b]@n.R0b],axis=1),
        jig_frames=np.stack([n.R0a,n.R0b],axis=1),force=N,moment=M,length=n.ds,
        material={key:np.concatenate(value) for key,value in material.items()},body=np.array(body),
        beam=np.array(beam_ids),station=np.array(stations),L=n.L,F=n.F,ML=n.F*n.L,size=system.size)
    dump(folder/'fixture.pkl',fixture)
    return dict(nodes=n.nn,elements=n.ne,compatibility_rows=6*n.ne,size=system.size,
        operator=n.structural_operator,native_residual_evaluations=0,
        material_sampling='Literal parsed endpoint tables with right/left side selection; fixed unloaded mesh arc lengths. Native compliance, Euler maps and derivatives are not expected-physics inputs.')


def analyze(folder,args):
    import numpy as np
    import scipy.sparse as sp
    from daedalus_source_strain_reference import Compatibility
    fixture=restore(STUDY/'capture/fixture.pkl');ref=Compatibility(fixture)
    original=restore(BALANCE/'capture-dip/fixture.pkl');nn=original['layout']['nodes'];ne=len(fixture['ends'])
    reference_base=ref.residual();base=np.load(BALANCE/'capture-dip/base-targets.npz')['residual'][:6*ne]
    base_error=float(max(abs(reference_base-base)));assert base_error<2e-8
    results={};arrays=dict(base_residual=reference_base,base_native=base)
    for case,tag in [('slow','analyze-slow'),('dip','analyze-dip-v2')]:
        native=np.load(BALANCE/('capture-'+case)/'arrays.npz');z=native['state']
        pose=z[:6*nn].reshape(nn,6);internal=z[6*nn:6*(nn+ne)].reshape(ne,6)
        value,terms=ref.tangent(fixture['L']*pose[:,:3],pose[:,3:],fixture['F']*internal[:,:3],fixture['ML']*internal[:,3:])
        differences={width:float(max(abs(value-native[width+'_residual'][:6*ne]))) for width in ('wide','fine')}
        differences['matrix_action']=float(max(abs(value-native['matrix_action'][:6*ne])))
        assert max(differences.values())<2e-8,differences
        assembled=np.load(BALANCE/tag/'arrays.npz')['expected_residual'].copy();assembled[:6*ne]=value
        complete_error=float(max(abs(assembled-native['matrix_action'])));assert complete_error<2e-8
        perbeam={str(beam):dict(max_residual=float(np.max(abs(value.reshape(ne,6)[fixture['beam']==beam]))),
            max_changing_curvature_map=float(np.max(abs(terms['changing_K'][fixture['beam']==beam])))) for beam in sorted(set(fixture['beam']))}
        results[case]=dict(comparisons=differences,complete_matrix_action_error=complete_error,
            complete_harmonic_residual=float(max(abs(assembled))),per_beam=perbeam)
        arrays.update({case+'_compatibility':value,case+'_full_residual':assembled,
            **{case+'_'+key:term for key,term in terms.items()}})
    expected=ref.matrix(fixture['size']);native=sp.load_npz(SOURCE/'assembled-6.7/A.npz')[:6*ne].toarray()
    difference=abs(expected-native);gate=2e-7+2e-7*abs(expected)
    np.savez_compressed(folder/'matrix.npz',expected=expected,native=native)
    assert np.all(difference<=gate),(float(difference.max()),np.unravel_index(difference.argmax(),difference.shape))
    mass=sp.load_npz(SOURCE/'assembled-6.7/M.npz')[:6*ne]
    forcing=np.load(SOURCE/'assembled-6.7/maps.npz')['B'][:6*ne]
    assert max(abs(mass.data),default=0)==0 and np.max(abs(forcing),initial=0)==0
    action_errors={}
    for case in results:
        z=np.load(BALANCE/('capture-'+case)/'arrays.npz')['state']
        error=float(max(abs(expected@z-arrays[case+'_compatibility'])));assert error<2e-10
        action_errors[case]=error
    arrays.update(beam=fixture['beam'],station=fixture['station'])
    np.savez_compressed(folder/'arrays.npz',**arrays)
    result=dict(base_comparison_error=base_error,base_residual=float(max(abs(reference_base))),responses=results,
        full_jacobian=dict(rows=6*ne,columns=fixture['size'],entries=int(expected.size),max_absolute_error=float(difference.max()),
            max_gate_ratio=float(np.max(difference/gate)),mass_rows_zero=True,input_rows_zero=True,action_errors=action_errors),
        frame_reconstruction_error=ref.reconstruction_error,curvature_map_complex_width_difference=ref.k_partial_step_error,
        max_endpoint_angle_difference_rad=float(np.max(abs(ref.delta_angles))),
        max_map_condition=float(np.max(np.linalg.cond(ref.K))),
        qualification='Independent published source compatibility and complete state Jacobian at the supplied loaded model. Combined with preceding independent balance, all 2044 rows are checked along two supplied complex response states. Parsed endpoint properties and selected discrete averaging remain input assumptions; no independent trim/response or native-ASWING match is claimed.')
    print(result,flush=True);return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=['capture','analyze'])
    parser.add_argument('--tag',required=True);args=vars(parser.parse_args())
    inputs=[ROOT/'scripts/daedalus_source_strain_reference.py',ROOT/'scripts/check_daedalus_wing_paper.py',
        ROOT/'scripts/check_daedalus_source_operator.py',ROOT/'scripts/check_daedalus_circulation_phase.py',
        ROOT/'examples/dae.asw',ROOT/'examples/dae-cruise-physical-mesh-project.json',SOURCE/'trim-6.7-1/state.json',
        ROOT/'docs/validation/aswing-authoritative-sources.json',ROOT/'reference/aswing-authoritative-20261108/drela-aswing-steady.pdf',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf']
    inputs+=list((ROOT/'openswing').glob('*.py'))
    for case,tag in [('slow','analyze-slow'),('dip','analyze-dip-v2')]:
        inputs += [BALANCE/('capture-'+case)/name for name in ('fixture.pkl','arrays.npz','base-targets.npz','terminal.json')]
        inputs += [BALANCE/tag/name for name in ('arrays.npz','result.json','terminal.json')]
    if args['stage']=='analyze':
        inputs += [STUDY/'capture'/name for name in ('fixture.pkl','result.json','terminal.json')]
        inputs += [SOURCE/'assembled-6.7'/name for name in ('A.npz','M.npz','maps.npz')]
    run(STUDY,args['tag'],inputs,globals()[args['stage']],args,__file__)


if __name__=='__main__':main()
