"""Bounded source-equation K/F comparison and plume-direction regression."""
import argparse
from pathlib import Path
from types import SimpleNamespace
from check_daedalus_load_sensitivity import ROOT, SOURCE, read
from check_daedalus_mesh_residual import accepted
from daedalus_bounded_job import run
import check_daedalus_source_operator as source
import check_daedalus_structural_resolution as resolution

STUDY = ROOT/'artifacts/daedalus-frozen-source-20261114'


def options(args):
    values=dict(args)
    values.update(seed=Path(args['seed']) if args['seed'] else None,
                  matrix=Path(args['matrix']) if args['matrix'] else None,
                  parts=[Path(p) for p in args['parts']],frozen=True,no_lag=False,no_plume=False,fourier=0)
    return SimpleNamespace(**values)


def check(folder,args):
    import pytest
    status=pytest.main(['-q','--tb=short',*args['tests'],*(['-k',args['selection']] if args['selection'] else [])])
    assert status==0, f'pytest status {status}'
    return dict(tests=args['tests'],selection=args['selection'],pytest_status=int(status))


def initialize(folder,args):
    import numpy as np
    from openswing.equilibrium_state import restore_physical_fields
    source.imports();n,_=source.setup(6.7,None,True)
    live=read(SOURCE/'trim-6.7-1/state.json')
    x=restore_physical_fields(n,live)
    result=source.save_state(folder,n,x)
    saved=read(folder/'state.json');assert saved['launch']['condition']['freeze_influences'] is True
    for key in ('gravity','loads','released_constraints','strut_mode'):
        assert saved['launch'][key]==live['launch'][key],key
    assert saved['identity']['stations']==live['identity']['stations']
    result.update(nodes=n.nn,elements=n.ne,circulation=n.ng,
                  qualification='Live source trim used only as an unaccepted physical initial guess for corrected K/F default; a fresh trim is required.')
    assert not result['accepted']
    return result


def compute(folder,args):
    source.imports();opt=options(args)
    if args['stage']=='trim':return source.trim(folder,opt)
    if args['stage'] in ('geometry','geometry_fd'):return resolution.geometry(folder,opt)
    if args['stage']=='geometry_join':return resolution.join_geometry(folder,opt)
    return source.staged_linear(folder,opt)


def matrices(folder):
    import numpy as np
    import scipy.sparse as sp
    from openswing.harmonic_structure import ReusableBeamStructure
    accepted(folder)
    a,m=(sp.load_npz(folder/name) for name in ('A.npz','M.npz'))
    with np.load(folder/'maps.npz') as maps:b,c=maps['B'][:,0],maps['C']
    layout=read(STUDY/'mass/layout.json');nn,ne=layout['nodes'],layout['elements'];gs=layout['circulation']['start']
    for matrix in (a,m):
        for value in (matrix.data,matrix.indices,matrix.indptr):value.flags.writeable=False
    velocity=np.arange(layout['local_velocity']['start'],layout['frame']['start'])
    structure=ReusableBeamStructure(a,m,np.r_[np.arange(6*ne),np.arange(6*(nn+ne),gs)],np.arange(6*(nn+ne)),velocity,velocity)
    return a,m,b,c,structure


def response(folder,args):
    import numpy as np
    from check_daedalus_mesh_zeros import factor_at
    a,m,b,c,structure=matrices(Path(args['matrix']))
    frequencies=sorted(set(np.geomspace(.1,10.,61).tolist()+[.2,1.1,1.15737773741517,1.3]))
    selected=frequencies[args['start']:args['start']+args['count']];states=[];outputs=[];checks=[]
    for f in selected:
        solve=factor_at(a,m,2j*np.pi*f,structure);z,check=solve(b)
        states.append(z);outputs.append(c@z);checks.append(check)
    np.savez_compressed(folder/'arrays.npz',frequencies=selected,states=states,outputs=outputs)
    return dict(frequencies=selected,checks=checks,frequency_count_total=len(frequencies),full_dimension=len(b))


def balance(folder,args):
    """Replay saved harmonic states through the complete current residual."""
    import numpy as np
    from openswing.frequency_response import HarmonicInput
    system=resolution.dynamic(SimpleNamespace(seed=Path(args['seed'])))
    with np.load(Path(args['parts'][0])/'arrays.npz') as saved:
        index=int(np.argmin(abs(saved['frequencies']-args['frequency'])))
        frequency=float(saved['frequencies'][index]);z=saved['states'][index]
    assert abs(frequency-args['frequency'])<1e-12
    zero=np.zeros(system.size);base=system.residual(zero,zero)
    assert max(abs(base))<1e-9
    omega=2*np.pi*frequency;forcing,_=HarmonicInput(system,'control.3',0).at_frequency(omega)
    checks=[];derivatives=[]
    for h in (.001,.0005):
        values=[]
        for part,component in enumerate((np.real,np.imag)):
            def sample(amplitude):
                return system.residual(amplitude*component(z),amplitude*component(1j*omega*z),
                                       forcing=forcing(part,amplitude))
            values.append((8*(sample(h)-sample(-h))-(sample(2*h)-sample(-2*h)))/(12*h))
        derivative=values[0]+1j*values[1];error=float(max(abs(derivative)))
        assert error<2e-8,error
        checks.append(dict(step=h,maximum_scaled_harmonic_residual=error));derivatives.append(derivative)
    difference=float(max(abs(derivatives[0]-derivatives[1])))
    assert difference<2e-8,difference
    return dict(frequency_hz=frequency,full_dimension=system.size,base_residual=float(max(abs(base))),
                frozen_influences=system.network.condition.freeze_influences,checks=checks,
                step_difference=difference,complete_residual_evaluations=17)


def report(folder,args):
    import csv
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import LogLocator, FuncFormatter, NullFormatter
    from check_daedalus_mesh_zeros import CHANNELS
    frequencies=[];outputs=[];checks=[]
    for part in args['parts']:
        path=Path(part);accepted(path)
        plan=read(path/'plan.json');assert plan['arguments']['stage']=='response'
        assert Path(plan['arguments']['matrix']).resolve()==(STUDY/'assembled').resolve()
        with np.load(path/'arrays.npz') as saved:
            frequencies.extend(saved['frequencies']);outputs.extend(saved['outputs'])
        checks.extend(read(path/'result.json')['checks'])
    order=np.argsort(frequencies);frequencies=np.array(frequencies)[order];outputs=np.array(outputs)[order]
    expected=sorted(set(np.geomspace(.1,10.,61).tolist()+[.2,1.1,1.15737773741517,1.3]))
    np.testing.assert_array_equal(frequencies,expected)
    with (SOURCE/'report/comparison.csv').open() as stream:
        old=[r for r in csv.DictReader(stream) if float(r['speed_m_s'])==6.7]
    assert len(old)==260
    live=np.empty_like(outputs);reference=np.empty(outputs.shape,float)
    for i,f in enumerate(frequencies):
        for j,ch in enumerate(CHANNELS):
            rows=[r for r in old if r['channel']==ch and abs(float(r['frequency_hz'])-f)<1e-12]
            assert len(rows)==1
            r=rows[0];live[i,j]=complex(float(r['real_display']),float(r['imag_display']))
            reference[i,j]=float(r['reference_magnitude'])
    uniform=np.array([any(abs(f-v)<1e-12 for v in np.geomspace(.1,10.,61)) for f in frequencies])
    assert uniform.sum()==61
    summaries={};rows=[]
    dip=int(np.argmin(abs(frequencies-1.15737773741517)))
    for name,values in [('live',live),('corrected_frozen',outputs)]:
        magnitude=abs(values);errors=abs(magnitude/reference-1);db=20*np.log10(magnitude/reference)
        summaries[name]=dict(within_5_percent=int((errors<=.05).sum()),comparison_values=260,
            rms_log_magnitude_error_db=float(np.sqrt(np.mean(db[uniform]**2))),
            channel_within_5_percent={ch:int((errors[:,j]<=.05).sum()) for j,ch in enumerate(CHANNELS)},
            channel_rms_db={ch:float(np.sqrt(np.mean(db[uniform,j]**2))) for j,ch in enumerate(CHANNELS)},
            at_reference_dip={ch:float(magnitude[dip,j]) for j,ch in enumerate(CHANNELS)},
            yaw_at_reference_dip_error_percent=float((magnitude[dip,0]/reference[dip,0]-1)*100))
        for i,f in enumerate(frequencies):
            for j,ch in enumerate(CHANNELS):
                rows.append([name,f,ch,values[i,j].real,values[i,j].imag,magnitude[i,j],reference[i,j],100*errors[i,j]])
    with (folder/'comparison.csv').open('x') as stream:
        writer=csv.writer(stream);writer.writerow(['configuration','frequency_hz','channel','real_display','imag_display',
            'magnitude_display','reference_magnitude','absolute_relative_error_percent']);writer.writerows(rows)
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    for j,(ax,ch) in enumerate(zip(axes.flat,CHANNELS)):
        ax.loglog(frequencies,reference[:,j],color='#333333',label='Drela published magnitude')
        ax.fill_between(frequencies,.95*reference[:,j],1.05*reference[:,j],color='#333333',alpha=.12)
        ax.loglog(frequencies,abs(live[:,j]),color='#ff4a3d',label='Live influence (previous)')
        ax.loglog(frequencies,abs(outputs[:,j]),color='#ff9f1a',label='Frozen influence, corrected plume')
        ax.set_title(ch.replace('_',' ').title());ax.set_xlabel('Frequency (cycles/s)')
        ax.set_ylabel(('deg/s' if j<2 else 'deg')+' per F3 unit');ax.set_xlim(.1,10)
        for axis in (ax.xaxis,ax.yaxis):
            axis.set_major_locator(LogLocator(base=10));axis.set_minor_locator(LogLocator(base=10,subs=np.arange(2,10)))
            axis.set_major_formatter(FuncFormatter(lambda x,pos:f'{x:g}'));axis.set_minor_formatter(NullFormatter())
        ax.grid(which='major',color='#aaaaaa',alpha=.6);ax.grid(which='minor',color='#dddddd',alpha=.65)
    axes.flat[0].legend(fontsize=8)
    fig.suptitle('Daedalus at 6.7 m/s: documented K/F settings, separately trimmed\nFull 2044-state response; historical Bode operating point remains unknown')
    fig.savefig(folder/'comparison.png',dpi=150);fig.savefig(folder/'comparison.svg');plt.close(fig)
    return dict(summaries=summaries,reference_at_dip={ch:float(reference[dip,j]) for j,ch in enumerate(CHANNELS)},
        full_dimension=2044,frequency_count=65,new_full_solves=len(checks),
        minimum_reciprocal_condition=min(c['reciprocal_condition'] for c in checks),
        maximum_scaled_residual=max(c['scaled_residual'] for c in checks),
        maximum_backward_error=max(c['backward_error'] for c in checks),
        qualification='Current source/SEGSPL operator; not a reconstruction of the undocumented historical operating point or a browser verification. No ISAE fraction changed.')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage',choices=['check','initialize','trim','geometry','geometry_fd','geometry_join','other','mass','assemble','response','balance','report'])
    p.add_argument('--tag',required=True);p.add_argument('--seed');p.add_argument('--matrix');p.add_argument('--parts',nargs='*',default=[])
    p.add_argument('--speed',type=float,default=6.7);p.add_argument('--start',type=int,default=0)
    p.add_argument('--count',type=int,default=128);p.add_argument('--step',type=float,default=1e-5)
    p.add_argument('--frequency',type=float,default=1.15737773741517)
    p.add_argument('--tests',nargs='*',default=[]);p.add_argument('--selection');args=vars(p.parse_args())
    inputs=[ROOT/'scripts'/s for s in ['check_daedalus_source_operator.py','check_daedalus_structural_resolution.py','check_daedalus_mesh_zeros.py','check_daedalus_mesh_residual.py']]
    inputs+=list((ROOT/'openswing').glob('*.py'))
    inputs+=[ROOT/s for s in ['examples/dae.asw','examples/dae-cruise-physical-mesh-project.json','docs/validation/ISAE_STATUS.md','docs/validation/aswing-authoritative-sources.json',
        'reference/aswing-authoritative-20261108/drela-aswing-steady.pdf','reference/aswing_doc.txt']]
    if args['stage']=='initialize':inputs+=[SOURCE/'trim-6.7-1/state.json']
    if args['seed']:inputs+=[Path(args['seed']).resolve()]
    for folder in [*args['parts'],*([args['matrix']] if args['matrix'] else [])]:
        inputs += [p.resolve() for p in Path(folder).iterdir() if p.suffix in ('.json','.npz')]
    if args['stage']=='response':inputs+=[STUDY/'mass/layout.json']
    if args['stage']=='report':inputs+=[SOURCE/'report/comparison.csv']
    if args['stage']=='check':
        inputs += [ROOT/t.split('::')[0] for t in args['tests']]
        inputs += [ROOT/'tests/test_direct_circulation.py',ROOT/'examples/rectangular.asw',ROOT/'examples/powered.asw']
    worker={'check':check,'initialize':initialize,'response':response,'balance':balance,'report':report}.get(args['stage'],compute)
    run(STUDY,args['tag'],inputs,worker,args,__file__)


if __name__=='__main__':main()
