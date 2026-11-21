"""Independent full-residual audit and report of the new Daedalus app mesh."""
import argparse
from pathlib import Path
from types import SimpleNamespace
from check_daedalus_load_sensitivity import ROOT,SOURCE,read,write
from check_daedalus_default_mesh_response import STUDY,dynamic
from daedalus_bounded_job import run

SEED=STUDY/'trim-1/state.json'
OLD=ROOT/'artifacts/daedalus-mesh-zeros-20261114/coarse-samples'
REFERENCE=ROOT/'docs/validation/daedalus-rudder-four-outputs.csv'
AUDIT=STUDY/'audit-v2'


def audit(folder,args):
    import numpy as np
    import scipy.sparse as sp
    system=dynamic(SimpleNamespace(seed=SEED));n=system.network
    a=sp.load_npz(STUDY/'assembled/A.npz');m=sp.load_npz(STUDY/'assembled/M.npz')
    with np.load(STUDY/'assembled/maps.npz') as data:b,c=data['B'][:,0],data['C']
    zero=np.zeros(system.size);base=system.base_report()
    assert base['modal_base']['kinematically_steady']
    assert abs(base['earth_state']['flight_path'])<1e-7
    assert np.linalg.norm(base['modal_base']['attitude_rates_rad'])<1e-7
    rows=[]
    for sample in read(STUDY/'response/result.json')['samples']:
        f=sample['frequency_hz']
        with np.load(STUDY/f'response/state-{f:.9g}.npz') as data:z,output=data['state'],data['output']
        np.testing.assert_allclose(c@z,output,atol=2e-13,rtol=0)
        for width in (.002,.004):
            def direction(v,rate):
                evaluate=lambda k:system.residual(zero,k*width*v) if rate else system.residual(k*width*v,zero)
                return (evaluate(-2)-8*evaluate(-1)+8*evaluate(1)-evaluate(2))/(12*width)
            state=direction(z.real,False)+1j*direction(z.imag,False)
            mass=-direction(z.real,True)-1j*direction(z.imag,True)
            residual=2j*np.pi*f*mass-state-b
            error=float(max(abs(residual)))
            assert error<1e-9,(f,width,error)
            rows.append(dict(frequency_hz=f,width=width,complete_harmonic_residual=error,
                state_action_error=float(max(abs(a@z-state))),mass_action_error=float(max(abs(m@z-mass)))))
    r0=system.r0;root=r0[n.node(1,0)]
    gravity=np.linalg.norm(base['gravity_body'])
    return dict(checks=rows,base_residual=float(max(abs(system.residual(zero,zero)))),
        weight_lb=float(base['mass_properties']['mass']*gravity),
        airspeed_ft_s=base['reference_flow']['speed'],flight_path_deg=base['earth_state']['flight_path'],
        wing_tip_height_above_root_ft=[float(r0[n.node(1,t),2]-root[2]) for t in (-56,56)],
        qualification='Six direct complete-residual harmonic checks, at two widths. No response is accepted only because it solves the assembled matrices.')


def report(folder,args):
    import csv
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import LogLocator,FuncFormatter,NullFormatter
    old=read(OLD/'result.json');new=read(STUDY/'response/result.json')
    with REFERENCE.open() as stream:reference=list(csv.DictReader(stream))
    with (SOURCE/'report/comparison.csv').open() as stream:curve=list(csv.DictReader(stream))
    rows=[]
    for sample in new['samples']:
        frequency=sample['frequency_hz']
        prior=next(row for row in old['samples'] if abs(row['frequency_hz']-frequency)<1e-12)
        for j,ch in enumerate(new['channels']):
            trace=sorted((float(row['frequency_Hz']),float(row['reference_drawing_magnitude'])) for row in reference if row['channel']==ch)
            f,v=np.array(trace).T
            target=float(np.exp(np.interp(np.log(frequency),np.log(f),np.log(v))))
            old_value=prior['magnitudes'][j];value=sample['magnitude'][j]
            rows.append(dict(channel=ch,frequency_hz=frequency,previous_mesh_magnitude=old_value,
                new_mesh_magnitude=value,reference_magnitude=target,
                change_percent=100*(value/old_value-1),reference_error_percent=100*(value/target-1)))
    with (folder/'comparison.csv').open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    fig,axes=plt.subplots(2,2,figsize=(10,7),layout='constrained')
    for ax,ch,label in zip(axes.flat,new['channels'],['Yaw rate [deg/s/F3]','Roll rate [deg/s/F3]','Sideslip [deg/F3]','Bank [deg/F3]']):
        target=sorted((float(row['frequency_Hz']),float(row['reference_drawing_magnitude'])) for row in reference if row['channel']==ch)
        prior=sorted((float(row['frequency_hz']),float(row['magnitude_display'])) for row in curve if row['channel']==ch and abs(float(row['speed_m_s'])-6.7)<1e-10)
        ax.loglog(*np.array(target).T,color='0.4',label='Drela drawing')
        ax.loglog(*np.array(prior).T,color='#ff4a3d',label='Previous comparison mesh')
        samples=[r for r in rows if r['channel']==ch]
        ax.loglog([r['frequency_hz'] for r in samples],[r['new_mesh_magnitude'] for r in samples],
            'o',color='#ff9f1a',label='New app mesh: sampled points')
        ax.set(xlabel='Frequency [Hz]',ylabel=label,xlim=(.1,10))
        for axis in (ax.xaxis,ax.yaxis):
            axis.set_major_locator(LogLocator(base=10))
            axis.set_major_formatter(FuncFormatter(lambda value,_:f'{value:g}'))
            axis.set_minor_locator(LogLocator(base=10,subs=range(2,10)))
            axis.set_minor_formatter(NullFormatter())
        ax.grid(which='major',alpha=.4);ax.grid(which='minor',alpha=.15);ax.legend(fontsize=7)
    fig.suptitle('Daedalus: new app mesh at the declared 6.7 m/s level-flight trim\nThree checked frequencies; native operating point and mesh remain unknown')
    fig.savefig(folder/'comparison.svg');fig.savefig(folder/'comparison.png',dpi=140);plt.close(fig)
    return dict(rows=rows,audit=read(AUDIT/'result.json'),
        maximum_absolute_magnitude_change_percent=max(abs(r['change_percent']) for r in rows),
        qualification='Source equations and SEGSPL, live influence, Mach 0.1, lag and plume. Previous 108-node comparison mesh versus new 112-node app mesh; not a replay of the former 48-per-beam app default. Three points do not locate a new minimum or establish convergence.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=['audit','report'])
    parser.add_argument('--tag',required=True);args=vars(parser.parse_args())
    inputs=list((ROOT/'openswing').glob('*.py'))+[SEED,REFERENCE,SOURCE/'report/comparison.csv',
        ROOT/'examples/dae.asw',ROOT/'web/daedalus-mesh.json',ROOT/'docs/validation/ISAE_STATUS.md',
        ROOT/'scripts/check_daedalus_default_mesh_response.py',
        ROOT/'scripts/check_daedalus_source_operator.py',ROOT/'scripts/check_daedalus_structural_resolution.py',
        ROOT/'docs/validation/aswing-authoritative-sources.json']
    for directory in [STUDY/'response',STUDY/'assembled',OLD]+([AUDIT] if args['stage']=='report' else []):
        inputs.extend(p for p in directory.iterdir() if p.is_file() and p.suffix in ('.npz','.json'))
    run(STUDY,args['tag'],inputs,globals()[args['stage']],args,__file__)


if __name__=='__main__':main()
