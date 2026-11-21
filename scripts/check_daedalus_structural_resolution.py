"""Current-source Daedalus refinement, with checkpointed serial assembly.

Every existing physical breakpoint and attachment survives. Each lifting
interval is bisected in whole-beam Glauert angle; each body interval is
bisected in material position. Interpolated fields are only an initial guess.
All steady and dynamic equations must be recomputed on the resulting mesh.
"""
import argparse
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
import traceback
from types import SimpleNamespace

from check_daedalus_load_sensitivity import ROOT,SOURCE,LIMITS,read,write,pin,utc
import check_daedalus_source_operator as source

STUDY=ROOT/'artifacts/daedalus-structural-resolution-20261113'
BASE=SOURCE/'trim-6.7-1/state.json'


def setup(seed):
    from openswing.asw import parse_asw
    from openswing.source_airflow import SourceAirflowNetwork
    from openswing.equilibrium_state import restore
    from openswing.time_state import read_condition
    packet=read(seed);launch=packet['launch']
    config=read(source.PROJECT)['cases'][0]['configuration']
    model=parse_asw(config['source'],beam_interpolation='drela-segspl-v1')
    panels=dict(default=16,beams={k:dict(nodes=v[0]) for k,v in packet['identity']['stations'].items()})
    n=SourceAirflowNetwork(model,panels,read_condition(launch['condition']),launch['gravity'],launch['loads'],
        operating_constraints=launch['released_constraints'],strut_mode=launch['strut_mode'],
        mesh_recipe='physical-breaks-v1',steady_trim=True)
    return n,restore(n,packet)


def dynamic(args):
    import numpy as np
    from openswing.linear_dynamics import _dynamic_base
    from openswing.operating import time_load_constraints
    n,x=setup(args.seed)
    assert max(abs(n.residual(x)))<=1e-9
    zero=np.zeros_like(n.rj)
    return _dynamic_base(n,x,time_load_constraints('free'),'free',
        dict(elastic_motion=(zero,zero,zero,zero),circulation_rate=np.zeros(n.circulation_basis.panels)),
        position=(0,0,0),attitude=(0,0,0),velocity=(0,0,0),gravity_magnitude=None)


def initialize(folder,args):
    import numpy as np
    from openswing.source_airflow import SourceAirflowNetwork
    from openswing.local_motion import NetworkMotion
    from openswing.network import log
    from openswing.equilibrium_state import capture,restore_physical_fields
    coarse,x=setup(BASE);r,Q,N,M,reactions,gamma=coarse.unpack(x)
    baseline=float(max(abs(coarse.residual(x))));assert baseline<1e-9
    motion=NetworkMotion(coarse,r,Q,*([np.zeros_like(r)]*4))
    panels={};positions={};rotations={};midpoints={}
    for mesh in coarse.meshes:
        if mesh.beam.lifting:
            arc=sum(mesh.length)*(1+np.cos((mesh.theta[:-1]+mesh.theta[1:])/2))/2
            fraction=(arc-np.r_[0.,np.cumsum(mesh.length)[:-1]])/mesh.length
        else:fraction=np.full(len(mesh.tm),.5)
        fraction=np.column_stack((np.zeros(len(fraction)),fraction,np.ones(len(fraction))))
        stations=mesh.t0[:,None]+fraction*(mesh.t1-mesh.t0)[:,None]
        points,frames,_=motion.sample(mesh.beam.index,fraction)
        key=mesh.beam.index
        panels[key]=dict(nodes=np.r_[stations[:,:-1].ravel(),stations[-1,-1]].tolist())
        positions[key]=np.vstack((points.origin[:,:-1].reshape(-1,3),points.origin[-1,-1]))
        rotations[key]=np.concatenate((frames[:,:-1].reshape(-1,3,3),frames[-1,-1][None]))
        midpoints[key]=fraction[:,1].tolist()
    launch=read(BASE)['launch']
    n=SourceAirflowNetwork(coarse.model,dict(default=16,beams=panels),coarse.condition,
        launch['gravity'],launch['loads'],operating_constraints=launch['released_constraints'],
        strut_mode=launch['strut_mode'],mesh_recipe='physical-breaks-v1',steady_trim=True)
    assert n.gravity_override==coarse.gravity_override
    assert n.nc==coarse.nc
    pose=np.zeros_like(n.rj);rotation=np.zeros((n.nn,3,3));force=[];moment=[]
    for mesh in n.meshes:
        key=mesh.beam.index;t,ids=n.station_nodes[key];old_t,_=coarse.station_nodes[key]
        np.testing.assert_array_equal(t[::2],old_t)
        pose[ids]=positions[key];rotation[ids]=rotations[key]
        force.extend(np.repeat(N[coarse.beam_elements[key]],2,axis=0))
        moment.extend(np.repeat(M[coarse.beam_elements[key]],2,axis=0))
    packet=dict(read(BASE),positions=pose.tolist(),rotations=log(rotation).tolist(),
        internal_force=np.array(force).tolist(),internal_moment=np.array(moment).tolist(),
        reactions=reactions.tolist(),circulation=np.repeat(gamma,2).tolist())
    guess=restore_physical_fields(n,packet)
    result=source.save_state(folder,n,guess)
    saved=read(folder/'state.json')
    for key in ('gravity','loads','released_constraints','strut_mode'):
        assert saved['launch'][key]==launch[key],key
    result.update(original_residual=baseline,nodes=n.nn,elements=n.ne,circulation=n.ng,
        original_nodes=coarse.nn,original_elements=coarse.ne,original_circulation=coarse.ng,
        inserted_fractions=midpoints,
        qualification='Unaccepted initial guess: sampled original positions/rotations and repeated interval loads/circulation. Every original station remains; a full new trim is required.')
    assert not result['accepted'], 'Do not skip the new trim based on interpolation.'
    return result


def geometry(folder,args):
    import numpy as np
    import scipy.sparse as sp
    from openswing.geometry_tangent import geometry_columns
    from openswing.tangent_influences import TangentInfluences
    steady=args.stage in ('trim_geometry','trim_geometry_fd')
    if steady:
        trim,x=setup(args.seed);n,base=source.canonical(trim,x);size=n.size
        scales=np.maximum(1.,abs(base));zero=np.zeros(size)
        residual=lambda d:n.residual(base+d)
        state_at=lambda d:base+d
        support=None
    else:
        from openswing.support_outputs import SupportTangent
        system=dynamic(args);n=system.network;size=system.size;zero=np.zeros(size)
        scales=np.r_[np.maximum(1.,abs(system.base)),np.ones(size-n.size)]
        residual=lambda d:system.residual(d,zero)
        state_at=lambda d:system.unpack(d,zero)[0].x
        support=SupportTangent(system)
    n.tangent_influences=TangentInfluences(local_geometry=True);n.aero_key=None
    indices=list(range(args.start,min(6*n.nn,args.start+args.count)))
    if args.stage=='check_columns':indices=[647,0,400,72,73,74,96,97,98,300,301,302]
    if args.stage.endswith('_fd'):
        columns=[];step_checks=[]
        for j in indices:
            values=[]
            for width in (args.step,args.step/2):
                h=width*scales[j];d=zero.copy();d[j]=h
                values.append((8*(residual(d)-residual(-d))-(residual(2*d)-residual(-2*d)))/(12*h))
            error=float(np.linalg.norm(values[1]-values[0])/max(np.linalg.norm(values[1]),1e-30))
            assert error<2e-5,(j,error)
            step_checks.append(dict(column=j,halved_step_relative_error=error))
            columns.append(sp.csc_matrix(values[-1][:,None]))
        matrix=sp.hstack(columns,format='csc')
        diagnostics=dict(method='Fourth-order complete residual differences',step=args.step,step_checks=step_checks)
    else:
        matrix,diagnostics=geometry_columns(n,residual,state_at,scales,args.step,
            _direct_vortex=True,_direct_volume=True,_nodewise_state=True,_direct_geometry=True,
            _rotation_chart='absolute' if steady else 'spatial',_strut_tangent=support,
            _direct_structural=False,_structural_system=None if steady else system,
            _column_indices=indices,progress=lambda *v:print('columns',*v,flush=True))
    assert matrix.shape==(size,len(indices))
    checks=[]
    # Complete physical residual probes, distinct from decomposed field checks.
    for k in sorted(set([0,len(indices)//2,len(indices)-1])):
        j=indices[k];h=args.step*scales[j];d=zero.copy();d[j]=h
        fd=(8*(residual(d)-residual(-d))-(residual(2*d)-residual(-2*d)))/(12*h)
        error=float(np.linalg.norm(matrix[:,k].toarray().ravel()-fd)/max(np.linalg.norm(fd),1e-30))
        assert error<2e-5,(j,error)
        checks.append(dict(column=j,complete_residual_relative_error=error))
    if args.stage=='check_columns':
        expected=sp.load_npz(SOURCE/'assembled-6.7/A.npz')[:,indices]
        difference=matrix-expected
        error=float(np.linalg.norm(difference.data)/np.linalg.norm(expected.data));assert error<2e-5,error
        invalid=[[],[0,0],[-1],[6*n.nn],[.2],[True]]
        for values in invalid:
            try:geometry_columns(n,residual,state_at,scales,_column_indices=values)
            except ValueError:pass
            else:raise AssertionError(('Invalid subset accepted',values))
        diagnostics.update(saved_full_matrix_relative_error=error,invalid_subsets_rejected=len(invalid))
    sp.save_npz(folder/'geometry-part.npz',matrix)
    return dict(size=size,nodes=n.nn,elements=n.ne,columns=indices,diagnostics=diagnostics,checks=checks)


def trim_other(folder,args):
    import numpy as np
    import scipy.sparse as sp
    from openswing.mechanical_tangent import source_network_mechanical_columns
    from openswing.structured_static import linearization
    from openswing.circulation_tangent import circulation_columns
    n,x=setup(args.seed);p,y=source.canonical(n,x)
    _,data=p.residual(y,detail=True)
    mechanical,diagnostics=source_network_mechanical_columns(p,data,np.maximum(1.,abs(y)),1e-5)
    with linearization(p,y,1.,capture_circulation=True) as (fields,_):
        circulation=circulation_columns(p,fields,1.)
    shared=sp.hstack((mechanical,sp.csc_matrix(circulation)),format='csc')
    sp.save_npz(folder/'shared.npz',shared)
    controls=[]
    for j in range(n.operating_start,n.size):
        h=1e-5*max(1.,abs(x[j]));d=np.zeros(n.size);d[j]=h
        controls.append((8*(n.residual(x+d)-n.residual(x-d))-(n.residual(x+2*d)-n.residual(x-2*d)))/(12*h))
    sp.save_npz(folder/'controls.npz',sp.csc_matrix(np.array(controls).T))
    return dict(size=n.size,canonical_size=p.size,shared_columns=list(range(6*n.nn,n.operating_start)),
        diagnostics=diagnostics,trim_variables=[c.variable for c in n.operating.constraints])


def join_trim(folder,args):
    import numpy as np
    import scipy.sparse as sp
    n,x=setup(args.seed);p,y=source.canonical(n,x);indices=[];blocks=[]
    for part in args.parts[:-1]:
        plan=read(part/'plan.json');result=read(part/'result.json');terminal=read(part/'terminal.json')
        assert terminal['returncode']==0 and terminal['process_reaped'] and terminal['inputs_unchanged']
        assert plan['inputs_sha256'][str(args.seed.resolve())]==pin(args.seed)
        indices+=result['columns'];blocks.append(sp.load_npz(part/'geometry-part.npz'))
    assert indices==list(range(6*n.nn))
    other=args.parts[-1];plan=read(other/'plan.json');assert read(other/'terminal.json')['returncode']==0
    assert plan['inputs_sha256'][str(args.seed.resolve())]==pin(args.seed)
    block=sp.hstack(blocks+[sp.load_npz(other/'shared.npz')],format='csc')
    mapping={c.quantity:p.operating_start+i for i,c in enumerate(p.operating.constraints)}
    rows=[block[:n.operating_start]]
    for c in n.operating.constraints:
        rows.append(sp.csc_matrix((1,n.operating_start)) if c.quantity=='flight_path' else block[mapping[c.quantity]:mapping[c.quantity]+1])
    tangent=sp.hstack((sp.vstack(rows,format='csc'),sp.load_npz(other/'controls.npz')),format='csc')
    rng=np.random.default_rng(762);checks=[]
    for _ in range(3):
        d=rng.normal(size=n.size);d/=np.linalg.norm(d);h=2e-6
        fd=(n.residual(x+h*d)-n.residual(x-h*d))/(2*h)
        error=float(np.linalg.norm(tangent@d-fd)/np.linalg.norm(fd));assert error<2e-5,error
        checks.append(error)
    sp.save_npz(folder/'trim-tangent.npz',tangent)
    return dict(size=n.size,geometry_columns=len(indices),full_directional_relative_errors=checks,
        rank_check_pending=True,qualification='Assembled and directionally checked; separate rank certificate required before a Newton correction.')


def rank_trim(folder,args):
    import scipy.sparse as sp
    from openswing.equilibrium_state import check_tangent_rank
    assert read(args.matrix/'terminal.json')['returncode']==0
    matrix=sp.load_npz(args.matrix/'trim-tangent.npz')
    result=check_tangent_rank(matrix,progress=lambda *v:print(*v,flush=True))
    sp.save_npz(folder/'trim-tangent.npz',matrix)
    return dict(size=matrix.shape[0],tangent_rank_check=result,rank_check_pending=False)


def correct(folder,args):
    import numpy as np
    import scipy.sparse as sp
    import scipy.sparse.linalg as spla
    n,x=setup(args.seed);matrix=sp.load_npz(args.matrix/'trim-tangent.npz')
    assert read(args.matrix/'terminal.json')['returncode']==0 and matrix.shape==(n.size,n.size)
    assert read(args.matrix/'result.json')['rank_check_pending'] is False
    factor=spla.splu(matrix);history=[float(max(abs(n.residual(x))))]
    for _ in range(6):
        r=n.residual(x);error=float(max(abs(r)))
        if error<=1e-9:break
        delta=factor.solve(-r)
        for power in range(9):
            trial=x+delta/2**power
            try:next_error=float(max(abs(n.residual(trial))))
            except ValueError:continue
            if next_error<error*(1-1e-4/2**power) or next_error<=1e-9:
                x=trial;history.append(next_error);break
        else:raise RuntimeError('Full residual line search failed.')
        print('residual',next_error,flush=True)
    return source.save_state(folder,n,x,residual_history=history,
        qualification='Full original trim residual; reused tangent is a Newton accelerator, not frozen aerodynamic physics.')


def join_geometry(folder,args):
    import scipy.sparse as sp
    system=dynamic(args);indices=[];blocks=[]
    for part in args.parts:
        plan=read(part/'plan.json');record=read(part/'result.json');terminal=read(part/'terminal.json')
        assert terminal['returncode']==0 and terminal['process_reaped'] and terminal['inputs_unchanged']
        assert plan['inputs_sha256'][str(args.seed.resolve())]==pin(args.seed)
        indices+=record['columns'];blocks.append(sp.load_npz(part/'geometry-part.npz'))
    assert indices==list(range(6*system.network.nn))
    matrix=sp.hstack(blocks,format='csc');sp.save_npz(folder/'geometry.npz',matrix)
    return dict(size=system.size,geometry_columns=len(indices))


def response(folder,args):
    import numpy as np
    import scipy.sparse as sp
    from openswing.frequency_response import harmonic_solve
    from openswing.harmonic_structure import ReusableBeamStructure
    assert read(args.matrix/'terminal.json')['returncode']==0
    a=sp.load_npz(args.matrix/'A.npz');m=sp.load_npz(args.matrix/'M.npz')
    maps=np.load(args.matrix/'maps.npz');rows=[]
    layout=read(STUDY/'mass-v3/layout.json');nn=layout['nodes'];ne=layout['elements']
    assert a.shape==m.shape==(layout['frame']['start']+12,)*2
    for pencil in (a,m):
        for array in (pencil.data,pencil.indices,pencil.indptr):array.flags.writeable=False
    velocities=np.arange(layout['local_velocity']['start'],layout['frame']['start'])
    structure=ReusableBeamStructure(a,m,
        np.r_[np.arange(6*ne),np.arange(6*(nn+ne),layout['circulation']['start'])],
        np.arange(6*(nn+ne)),velocities,velocities)
    for frequency in args.frequencies:
        z,checks=harmonic_solve(a,m,maps['B'][:,0],2*np.pi*frequency,_structure=structure)
        out=maps['C']@z
        rows.append(dict(frequency_hz=frequency,real=out.real.tolist(),imag=out.imag.tolist(),
            magnitude=abs(out).tolist(),checks=checks))
        np.savez_compressed(folder/f'state-{frequency:.9g}.npz',state=z,output=out)
        print('response',frequency,abs(out).tolist(),flush=True)
    return dict(size=a.shape[0],channels=source.CHANNELS,samples=rows,structure=structure.report)


def response_profile(folder,args):
    import scipy.sparse as sp
    import openswing.harmonic_structure as harmonic
    result={}
    class Captured(Exception):pass
    def capture(factor):
        import ctypes
        matrix=factor._pending_matrix
        result.update(shape=list(matrix.shape),nonzeros=matrix.nnz,
            density=matrix.nnz/matrix.shape[0]**2,sparse_bytes=harmonic.storage(matrix),
            dense_bytes=matrix.shape[0]**2*matrix.dtype.itemsize,
            process_memory=[line for line in Path('/proc/self/status').read_text().splitlines()
                            if line.startswith(('Vm','Rss'))])
        native=ctypes.CDLL(None);native.malloc_trim.argtypes=[ctypes.c_size_t];native.malloc_trim.restype=ctypes.c_int
        result['allocator_trim_result']=native.malloc_trim(0)
        result['process_memory_after_trim']=[line for line in Path('/proc/self/status').read_text().splitlines()
                                            if line.startswith(('Vm','Rss'))]
        sp.save_npz(folder/'schur.npz',matrix)
        raise Captured
    original=harmonic.DiagonalFactor.factorize
    harmonic.DiagonalFactor.factorize=capture
    try:
        try:response(folder,args)
        except Captured:pass
        else:raise AssertionError('Expected a diagonal-elimination capture.')
    finally:harmonic.DiagonalFactor.factorize=original
    result['qualification']='Storage observation before factorization; no response or convergence claim.'
    return result


def comparison(folder,args):
    import csv,re
    import numpy as np
    import scipy.sparse as sp
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import LogLocator,FuncFormatter,NullFormatter
    from openswing.frequency_response import harmonic_solve
    fine=[]
    for tag in ('response-neighbors','response-final'):
        terminal=read(STUDY/tag/'terminal.json')
        assert terminal['returncode']==0 and terminal['process_reaped'] and terminal['inputs_unchanged']
        fine+=read(STUDY/tag/'result.json')['samples']
    fine.sort(key=lambda row:row['frequency_hz'])
    assert len({row['frequency_hz'] for row in fine})==len(fine)
    with source.REFERENCE.open() as f:raw=list(csv.DictReader(f))
    reference={name:np.array([[float(r['frequency_Hz']),float(r['reference_drawing_magnitude'])]
        for r in raw if r['channel']==name]) for name in source.CHANNELS}
    with (SOURCE/'report/comparison.csv').open() as f:curve=list(csv.DictReader(f))
    a=sp.load_npz(SOURCE/'assembled-6.7/A.npz');m=sp.load_npz(SOURCE/'assembled-6.7/M.npz')
    maps=np.load(SOURCE/'assembled-6.7/maps.npz');records=[];replay_error=0.
    for row in fine:
        frequency=row['frequency_hz'];z,checks=harmonic_solve(a,m,maps['B'][:,0],2*np.pi*frequency)
        coarse=maps['C']@z;refined=np.array(row['real'])+1j*np.array(row['imag'])
        drawing=np.array([np.exp(np.interp(np.log(frequency),np.log(reference[k][:,0]),np.log(reference[k][:,1]))) for k in source.CHANNELS])
        for i,name in enumerate(source.CHANNELS):
            previous=[r for r in curve if r['channel']==name and abs(float(r['frequency_hz'])-frequency)<1e-12]
            if previous:
                assert len(previous)==1;previous=previous[0]
                old=complex(float(previous['real_display']),float(previous['imag_display']))
                np.testing.assert_allclose(coarse[i],old,atol=2e-12,rtol=2e-10)
                replay_error=max(replay_error,float(abs(coarse[i]-old)))
        records.append(dict(frequency_hz=frequency,coarse_magnitude=abs(coarse).tolist(),
            refined_magnitude=abs(refined).tolist(),drawing_magnitude=drawing.tolist(),
            complex_mesh_change_percent=(100*abs(refined-coarse)/abs(refined)).tolist(),
            signed_amplitude_change_percent=(100*(abs(refined)/abs(coarse)-1)).tolist(),
            reference_error_percent=(100*(abs(refined)/drawing-1)).tolist(),
            coarse_checks=checks,refined_checks=row['checks']))
    palette=re.findall(r'#[0-9a-fA-F]{6}',(ROOT/'web/plot-colors.js').read_text().split('surfaceColors = Object.freeze([')[1].split(']);')[0])
    fig,axes=plt.subplots(2,2,figsize=(11,7.6),layout='constrained')
    for i,name in enumerate(source.CHANNELS):
        ax=axes.flat[i];ax.set_facecolor('#111827')
        old=[r for r in curve if r['channel']==name]
        ax.loglog([float(r['frequency_hz']) for r in old],[float(r['magnitude_display']) for r in old],
            color=palette[0],label='108 nodes / 82 lifting panels',lw=1.6)
        ax.loglog([r['frequency_hz'] for r in records],[r['refined_magnitude'][i] for r in records],
            'o',color=palette[1],label='211 nodes / 164 lifting panels',markersize=5,fillstyle='none')
        ax.loglog(reference[name][:,0],reference[name][:,1],color='white',ls='--',label='Drela drawing',lw=1.5)
        ax.set_title(['Yaw rate','Roll rate','Sideslip','Bank angle'][i]);ax.set_xlim(.1,10)
        ax.set_xlabel('Frequency [cycles/s]');ax.set_ylabel(('deg/s' if i<2 else 'deg')+' per native F3')
        for axis in (ax.xaxis,ax.yaxis):
            axis.set_major_locator(LogLocator(base=10));axis.set_minor_locator(LogLocator(base=10,subs=np.arange(2,10)))
            axis.set_major_formatter(FuncFormatter(lambda x,pos:f'{x:g}'));axis.set_minor_formatter(NullFormatter())
        ax.grid(which='major',color='white',alpha=.3);ax.grid(which='minor',color='white',alpha=.12)
    axes.flat[0].legend(facecolor='#111827',labelcolor='white',fontsize=8)
    fig.suptitle('Daedalus: full current-source mesh refinement, independently trimmed at 6.7 m/s\nFine markers are six solved frequencies; reference operating settings remain unknown')
    fig.savefig(folder/'comparison.png',dpi=150);fig.savefig(folder/'comparison.svg');plt.close(fig)
    with (folder/'comparison.csv').open('x',newline='') as f:
        writer=csv.writer(f);writer.writerow(['frequency_hz','channel','coarse','refined','drawing','complex_mesh_change_percent','signed_amplitude_change_percent','reference_error_percent'])
        for row in records:
            for i,name in enumerate(source.CHANNELS):
                writer.writerow([row['frequency_hz'],name]+[row[k][i] for k in ('coarse_magnitude','refined_magnitude','drawing_magnitude','complex_mesh_change_percent','signed_amplitude_change_percent','reference_error_percent')])
    return dict(comparisons=records,saved_coarse_replay_absolute_error=replay_error,
        qualification='Two complete current-source meshes at separately converged equilibria. Six paired frequencies do not establish full-spectrum or asymptotic mesh convergence.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['init','check_columns','trim_geometry','trim_geometry_fd','trim_other','trim_join','trim_rank','correct','geometry','geometry_fd','geometry_join','other','mass','assemble','response','response_profile','unit_tests','comparison'])
    parser.add_argument('--tag',required=True);parser.add_argument('--seed',type=Path)
    parser.add_argument('--matrix',type=Path);parser.add_argument('--parts',type=Path,nargs='+')
    parser.add_argument('--start',type=int,default=0);parser.add_argument('--count',type=int,default=96)
    parser.add_argument('--step',type=float,default=1e-5)
    parser.add_argument('--frequencies',type=float,nargs='+',default=[.1,1.,1.15737773741517])
    parser.add_argument('--test-selection',default='not physical_pencils and not controller_and and not frequency_runs')
    args=parser.parse_args();args.speed=6.7
    if args.stage in ('check_columns','unit_tests'):args.seed=BASE
    if args.stage!='init' and args.seed is None:parser.error('--seed is required for this stage')
    STUDY.mkdir(exist_ok=True);folder=STUDY/args.tag;folder.mkdir(exist_ok=False)
    (folder/'runner.py').write_bytes(Path(__file__).read_bytes())
    inputs=[Path(__file__),ROOT/'scripts/check_daedalus_source_operator.py',ROOT/'scripts/check_daedalus_load_sensitivity.py',
        source.PROJECT,ROOT/'examples/dae.asw',BASE,ROOT/'reference/aswing-authoritative-20261108/drela-aswing-steady.pdf',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf',ROOT/'docs/validation/aswing-authoritative-sources.json']
    if args.seed:inputs.append(args.seed)
    if args.stage=='check_columns':inputs.append(SOURCE/'assembled-6.7/A.npz')
    if args.stage in ('response','response_profile'):inputs.append(STUDY/'mass-v3/layout.json')
    if args.stage=='unit_tests':inputs.append(ROOT/'tests/test_harmonic_structure.py')
    if args.stage=='comparison':
        inputs += [STUDY/tag/name for tag in ('response-neighbors','response-final') for name in ('plan.json','result.json','terminal.json')]
        inputs += [SOURCE/'assembled-6.7'/name for name in ('A.npz','M.npz','maps.npz')]
        inputs += [SOURCE/'report/comparison.csv',source.REFERENCE,ROOT/'web/plot-colors.js']
    for part in (args.parts or [])+([args.matrix] if args.matrix else []):
        inputs+=list(part.glob('*.npz'))+[part/name for name in ('plan.json','result.json','terminal.json')]
    pins={str(p.resolve()):pin(p) for p in inputs+list((ROOT/'openswing').glob('*.py'))}
    arguments={k:str(v) if isinstance(v,Path) else [str(p) for p in v] if isinstance(v,list) else v for k,v in vars(args).items()}
    write(folder/'plan.json',dict(observed_utc=utc(),arguments=arguments,inputs_sha256=pins,limits=LIMITS,
        allocator_environment={key:os.environ.get(key) for key in ('MALLOC_MMAP_THRESHOLD_','MALLOC_TRIM_THRESHOLD_')}))
    started=time.monotonic();sys.stdout.flush();pid=os.fork()
    if pid==0:
        code=0
        for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
        resource.setrlimit(resource.RLIMIT_AS,(LIMITS['address_space_bytes'],)*2)
        resource.setrlimit(resource.RLIMIT_CPU,(LIMITS['cpu_seconds'],)*2);sys.path.insert(0,str(ROOT))
        with (folder/'stdout.log').open('x') as out,(folder/'stderr.log').open('x') as err:
            os.dup2(out.fileno(),1);os.dup2(err.fileno(),2)
            try:
                source.imports();source.dynamic=dynamic
                if args.stage=='init':result=initialize(folder,args)
                elif args.stage in ('geometry','geometry_fd','trim_geometry','trim_geometry_fd','check_columns'):result=geometry(folder,args)
                elif args.stage=='trim_other':result=trim_other(folder,args)
                elif args.stage=='trim_join':result=join_trim(folder,args)
                elif args.stage=='trim_rank':result=rank_trim(folder,args)
                elif args.stage=='correct':result=correct(folder,args)
                elif args.stage=='geometry_join':result=join_geometry(folder,args)
                elif args.stage=='response':result=response(folder,args)
                elif args.stage=='response_profile':result=response_profile(folder,args)
                elif args.stage=='comparison':result=comparison(folder,args)
                elif args.stage=='unit_tests':
                    import pytest
                    selection=args.test_selection
                    status=pytest.main(['-q','tests/test_harmonic_structure.py','-k',selection,'-p','no:cacheprovider'])
                    assert status==0,status
                    result=dict(exit_code=int(status),selection=selection)
                else:result=source.staged_linear(folder,args)
                write(folder/'result.json',result)
            except BaseException:traceback.print_exc();code=1
            sys.stdout.flush();sys.stderr.flush()
        os._exit(code)
    reaped=0;timed_out=False
    try:
        while not reaped:
            reaped,status,usage=os.wait4(pid,os.WNOHANG)
            if reaped:break
            if time.monotonic()-started>LIMITS['wall_seconds']:
                timed_out=True;os.kill(pid,signal.SIGKILL);reaped,status,usage=os.wait4(pid,0);break
            time.sleep(.05)
    finally:
        if not reaped:os.kill(pid,signal.SIGKILL);reaped,status,usage=os.wait4(pid,0)
    terminal=dict(observed_utc=utc(),returncode=os.waitstatus_to_exitcode(status),process_reaped=True,timed_out=timed_out,
        cpu_seconds=usage.ru_utime+usage.ru_stime,wall_seconds=time.monotonic()-started,peak_rss_kib=usage.ru_maxrss,
        limits=LIMITS,inputs_unchanged=all(pin(p)==h for p,h in pins.items()))
    write(folder/'terminal.json',terminal);print(json.dumps(terminal),flush=True)
    raise SystemExit(terminal['returncode'] or (0 if terminal['inputs_unchanged'] else 1))


if __name__=='__main__':main()
