"""Plot the fixed-layout sensor-average diagnostic; no dynamic solve."""
from check_daedalus_load_sensitivity import ROOT, read
from daedalus_bounded_job import run
import check_daedalus_sensor_average as audit

SOURCE = audit.STUDY/'audit-v4'
REFERENCE = audit.response.STUDY/'report/reference.json'
LABELS = {'frame':'Aircraft frame', 'cabin_three':'3 cabin sensors',
    'cabin_wing_root_two':'Cabin + wing root (2)',
    'wing_cabin_four':'Cabin + wing root + both wingtips (4)',
    'wing_three':'Wing root + both wingtips (3)',
    'centerline_six':'6 centerline sensors', 'aircraft_seven':'7 aircraft locations',
    'component_midpoints_five':'5 component midpoints',
    'distributed_fifteen':'15 distributed sensors', 'all_nodes_equal':'All 103 nodes, equal weights',
    'equal_components_length_mean':'Equal component / length average'}


def report(folder, args):
    import hashlib
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import LogLocator, FuncFormatter, NullFormatter
    data=read(SOURCE/'result.json'); terminal=read(SOURCE/'terminal.json')
    assert terminal['returncode']==0 and terminal['process_reaped'] and terminal['inputs_unchanged']
    for path,sha in read(SOURCE/'plan.json')['inputs_sha256'].items():
        assert hashlib.sha256(__import__('pathlib').Path(path).read_bytes()).hexdigest()==sha,path
    reference=read(REFERENCE)['channels']['yaw_rate']['vertices']
    f=np.array([r['frequency_hz'] for r in data['rows']])
    native=np.array(reference);fig,axes=plt.subplots(1,2,figsize=(13.5,5.6),constrained_layout=True)
    groups=[['frame','cabin_three','aircraft_seven','distributed_fifteen','all_nodes_equal'],
            ['frame','cabin_three','cabin_wing_root_two','wing_cabin_four','wing_three']]
    colors={'frame':'#222222','cabin_three':'#969696','aircraft_seven':'#d55e00','distributed_fifteen':'#cc79a7',
            'all_nodes_equal':'#009e73','cabin_wing_root_two':'#0072b2','wing_cabin_four':'#d55e00','wing_three':'#009e73'}
    for ax,keys,title in zip(axes,groups,['Averages including the tail','Wing and cabin averages']):
        ax.loglog(native[:,2],native[:,3],'--',color='#8b2aa5',lw=2,label='Drela drawing (setup unknown)')
        for key in keys:
            ax.loglog(f,[r['values'][key]['magnitude'] for r in data['rows']],color=colors[key],lw=1.5,
                ls=':' if key=='cabin_three' else '-',label=LABELS[key])
        ax.set(title=title,xlabel='Frequency (Hz)',ylabel='Yaw-rate magnitude (deg/s per F3)',xlim=(.1,10))
        for axis in (ax.xaxis,ax.yaxis):
            axis.set_major_locator(LogLocator(base=10));axis.set_major_formatter(FuncFormatter(lambda x,_:f'{x:g}'))
            axis.set_minor_locator(LogLocator(base=10,subs=range(2,10)));axis.set_minor_formatter(NullFormatter())
        ax.grid(which='major',color='#c1c7cd',lw=.7);ax.grid(which='minor',color='#e4e7eb',lw=.4)
        ax.legend(fontsize=8,loc='upper left');ax.set_axisbelow(True)
    axes[0].set_ylim(.01,20)
    axes[1].set_ylim(.005,.5);axes[1].set_xlim(.6,3)
    axes[1].set_xticks([.6,1,1.5,2,3]);axes[1].xaxis.set_major_formatter(FuncFormatter(lambda x,_:f'{x:g}'))
    axes[1].axvline(data['native_dip']['frequency_hz'],color='#8b2aa5',lw=.8,ls=':')
    fig.suptitle('Daedalus: spatially averaged gyro responses\nUnchanged 6.7 m/s level-flight solution; complex averages with fixed positive weights',fontsize=12)
    fig.savefig(folder/'comparison.svg');fig.savefig(folder/'comparison.png',dpi=140);plt.close(fig)
    minima={}
    for key in LABELS:
        row=min((r for r in data['rows'] if .7<=r['frequency_hz']<=3),key=lambda r:r['values'][key]['magnitude'])
        minima[key]=dict(label=LABELS[key],frequency_hz=row['frequency_hz'],magnitude=row['values'][key]['magnitude'])
    return dict(source=str(SOURCE.relative_to(ROOT)),samples=data['frequencies'],sampled_minima_07_to_3_hz=minima,
        qualification='No fitting or new solve; only sampled minima, not refined extrema. All layouts, locations, complex values and both sensor-axis conventions remain in the source diagnostic.')


if __name__=='__main__':
    inputs=[SOURCE/p for p in ['result.json','terminal.json','plan.json']]+[REFERENCE,ROOT/'scripts/check_daedalus_sensor_average.py']
    run(audit.STUDY,'report',inputs,report,{},__file__)
