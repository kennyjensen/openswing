"""Compare rotation-invariant lateral-rate magnitudes without fitting axes."""
import argparse
from check_daedalus_load_sensitivity import ROOT,SOURCE,read
from check_daedalus_reference_kinematics import STUDY
from daedalus_bounded_job import run


def report(folder,args):
    import csv,math,re
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import LogLocator,NullFormatter,FuncFormatter
    bounds=read(STUDY/'bounds-v2/result.json')
    curves={}
    for key in ('roll','yaw','bank'):
        with (STUDY/'bounds-v2'/f'{key}-reference.csv').open() as stream:
            rows=list(csv.DictReader(stream))
        curves[key]=np.array([[float(r[k]) for k in list(r)[1:]] for r in rows])
    # Slope per PDF point is checked against the PDF grid in bounds-v2.
    slopes={key:float(-np.polyfit(v[:,1],np.log(v[:,3]),1)[0]) for key,v in curves.items()}
    x0,x1=91.,558.9000244140625
    getx=lambda f:x0+(x1-x0)*np.log10(f/.1)/2
    frequency=lambda x:.1*10**(2*(x-x0)/(x1-x0))
    def graphic_band(key,f,h=.75):
        v=curves[key];x=float(getx(f));lo=max(x0,x-2*h);hi=min(x1,x+2*h)
        locations=np.r_[lo,v[(v[:,0]>lo)&(v[:,0]<hi),0],hi]
        logs=np.interp(locations,v[:,0],np.log(v[:,3]))
        return float(np.exp(logs.min()-h*slopes[key])),float(np.exp(logs.max()+h*slopes[key]))
    records={}
    with (SOURCE/'report/comparison.csv').open() as stream:
        for row in csv.DictReader(stream):
            records.setdefault(float(row['frequency_hz']),{})[row['channel']]=complex(float(row['real_display']),float(row['imag_display']))
    theta=math.radians(bounds['current_elevation_deg'])
    result=[];conservation=0.
    for f,values in sorted(records.items()):
        p,r=values['roll_rate'],values['yaw_rate'];w=2*np.pi*f
        original=float(np.hypot(abs(p),abs(r)))
        for angle in (0.,theta,-theta,np.pi/2,-np.pi/2):
            rotated_p=np.cos(angle)*p+np.sin(angle)*r
            rotated_r=-np.sin(angle)*p+np.cos(angle)*r
            conservation=max(conservation,float(abs(np.hypot(abs(rotated_p),abs(rotated_r))-original)))
        reference={key:float(np.exp(np.interp(getx(f),v[:,0],np.log(v[:,3])))) for key,v in curves.items()}
        bands={key:graphic_band(key,f) for key in curves}
        lo=float(np.hypot(bands['roll'][0],bands['yaw'][0]))
        hi=float(np.hypot(bands['roll'][1],bands['yaw'][1]))
        ref=float(np.hypot(reference['roll'],reference['yaw']))
        trial=[abs(-np.sin(t)*p+np.cos(t)*r) for t in (theta,-theta)]
        row=dict(frequency_hz=f,source_lateral_rate_norm=original,reference_lateral_rate_norm=ref,
            reference_norm_graphic_min=lo,reference_norm_graphic_max=hi,
            combined_relative_difference_percent=100*(original/ref-1),
            minimum_discrepancy_after_graphic_band_percent=100*max(0.,original/hi-1,1-original/lo),
            necessary_joint_5_percent_norm_condition_satisfied=bool(.95*lo<=original<=1.05*hi),
            source_integrated_roll_bank_ratio=w*abs(values['bank'])/abs(p),
            reference_integrated_roll_bank_ratio=w*reference['bank']/reference['roll'],
            yaw_magnitude=abs(r),yaw_reference=reference['yaw'],
            yaw_after_plus_elevation_rotation=float(trial[0]),yaw_after_minus_elevation_rotation=float(trial[1]),
            integrated_body_roll_angle=abs(p)/w,bank_angle=abs(values['bank']),bank_reference=reference['bank'])
        result.append(row)
    assert conservation<2e-14,conservation
    dip=min(result,key=lambda r:abs(r['frequency_hz']-1.15737773741517))
    assert abs(dip['frequency_hz']-1.15737773741517)<1e-12
    # This is only a necessary norm condition. Passing it never proves that
    # either rate, a common rotation, or the aircraft matches the drawing.
    impossible=[r for r in result if not r['necessary_joint_5_percent_norm_condition_satisfied']]
    with (folder/'comparison.csv').open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(result[0]));writer.writeheader();writer.writerows(result)
    palette=re.findall(r"'([^']+)'",(ROOT/'web/plot-colors.js').read_text().split('export const plotColors = Object.freeze([')[1].split(']);')[0])
    f=np.array([r['frequency_hz'] for r in result]);get=lambda key:np.array([r[key] for r in result])
    fig,axes=plt.subplots(1,2,figsize=(11.8,4.8),layout='constrained')
    axes[0].loglog(f,get('source_lateral_rate_norm'),color=palette[0],label='Current full source model')
    axes[0].loglog(f,get('reference_lateral_rate_norm'),color=palette[4],label='Drela drawing')
    axes[0].fill_between(f,get('reference_norm_graphic_min'),get('reference_norm_graphic_max'),color=palette[4],alpha=.2,label='±0.75 PDF-point envelope')
    axes[0].set(title='Invariant under rotation of roll/yaw axes',ylabel='√(|roll rate|² + |yaw rate|²) [deg/s/F3]')
    axes[0].axvline(dip['frequency_hz'],ls=':',color='#6b7280',lw=.8)
    axes[1].semilogx(f,get('source_integrated_roll_bank_ratio'),color=palette[0],label='Current full source model')
    axes[1].semilogx(f,get('reference_integrated_roll_bank_ratio'),color=palette[4],label='Drela drawing')
    axes[1].axhline(1,ls=':',color='#6b7280',lw=.8)
    axes[1].set(title='Bank-angle kinematic clue',ylabel='2πf |bank angle| / |roll rate|')
    for ax in axes:
        ax.set(xlim=(.1,10),xlabel='Frequency [Hz]')
        ax.xaxis.set_major_locator(LogLocator(base=10,numticks=3))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v,pos:f'{v:g}'))
        ax.xaxis.set_minor_locator(LogLocator(base=10,subs=range(2,10)))
        ax.xaxis.set_minor_formatter(NullFormatter())
        ax.grid(which='major',alpha=.4);ax.grid(which='minor',alpha=.15);ax.legend(fontsize=8)
    fig.suptitle('Daedalus output-convention check: no attitude or response fitted',fontsize=12)
    fig.savefig(folder/'reference-kinematics.png',dpi=150);fig.savefig(folder/'reference-kinematics.svg');plt.close(fig)
    summary=dict(dip=dip,frequency_count=len(result),
        necessary_joint_5_percent_condition_impossible_count=len(impossible),
        impossible_frequency_hz=[r['frequency_hz'] for r in impossible],
        maximum_rotation_norm_conservation_error=conservation,reference_kinematic_bounds=bounds,
        qualification='The sum of squared roll/yaw magnitudes is invariant for any real orthogonal rotation in that plane. Both channels within 5% requires the same for their combined norm, allowing the independently declared drawing envelope. This is a necessary condition only; counts are not validation passes. Nonzero-bank rotation can mix unknown pitch response and is outside this invariant. Uncertain historical inputs/physics remain separate. All aircraft states and production equations are unchanged.')
    print('dip',dip,flush=True);print('necessary norm condition impossible',len(impossible),'/',len(result),flush=True)
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--tag',required=True);args=vars(parser.parse_args())
    inputs=[STUDY/'bounds-v2'/name for name in ('result.json','terminal.json','roll-reference.csv','yaw-reference.csv','bank-reference.csv')]
    inputs += [SOURCE/'report/comparison.csv',ROOT/'scripts/check_daedalus_reference_kinematics.py',ROOT/'web/plot-colors.js']
    run(STUDY,args['tag'],inputs,report,args,__file__)


if __name__=='__main__':main()
