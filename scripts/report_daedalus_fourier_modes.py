"""Compare saved Fourier/pointwise temporal mode truncations without fitting."""
import argparse
import importlib.util
from pathlib import Path
from check_daedalus_load_sensitivity import ROOT,read
from daedalus_bounded_job import run

STUDY=ROOT/'artifacts/daedalus-fourier-modes-20261114'
POINT=ROOT/'artifacts/daedalus-source-modes-20261114'
OLD_DRIVER=POINT/'shared-driver-8ae6737824e3.py'
CHANNELS=['yaw_rate','roll_rate','sideslip','bank']


def report(folder,args):
    import numpy as np
    import check_daedalus_source_modes as current
    spec=importlib.util.spec_from_file_location('prior_daedalus_modes',OLD_DRIVER)
    prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
    old=prior.matrices();new=current.matrices();default_errors=[]
    for a,b in zip(old,new):
        error=float(np.max(abs((a-b).data),initial=0)) if hasattr(a,'tocsc') else float(np.max(abs(a-b),initial=0))
        assert error==0;default_errors.append(error)
    del old,new
    datasets={}
    for name,path in [('pointwise',POINT/'compare-112-final'),('fourier8',STUDY/'compare-65-final')]:
        with np.load(path/'arrays.npz') as archive:
            data={key:archive[key] for key in ('frequencies','full','reference','values','residues','retained','reduced')}
        data['checks']=read(path/'result.json');datasets[name]=data
    p=datasets['pointwise'];q=datasets['fourier8'];f=p['frequencies']
    np.testing.assert_array_equal(f,q['frequencies']);np.testing.assert_array_equal(p['reference'],q['reference'])
    dip=int(np.argmin(abs(f-1.15737773741517)));reference=p['reference']
    uniform=np.min(abs(f[:,None]-np.logspace(-1,1,61)[None,:]),axis=1)<1e-12
    def metrics(response):
        return dict(dip_magnitudes=abs(response[dip]).tolist(),
            dip_signed_reference_error_percent=((abs(response[dip])/reference[dip]-1)*100).tolist(),
            low_frequency_yaw_error_percent=float((abs(response[0,0])/reference[0,0]-1)*100),
            rms_db=np.sqrt(np.mean((20*np.log10(abs(response[uniform])/reference[uniform]))**2,axis=0)).tolist())
    counts=[];cutoffs=[];responses={}
    for case,data in datasets.items():
        counts.append(dict(case=case,selection='full',retained=None,**metrics(data['full'])))
        for i,count in enumerate(data['retained']):
            counts.append(dict(case=case,selection='mode-count',retained=int(count),**metrics(data['reduced'][i])))
        assert np.max(abs(data['values']))>44
        for cutoff in (5.,10.,20.,40.):
            selected=np.flatnonzero(abs(data['values'])<=cutoff)
            values=data['values'][selected];residues=data['residues'][:,selected]
            # Exact conjugate completion was already enforced by the checked
            # modal comparison; the magnitude cutoff must preserve every pair.
            assert max(min(abs(values-lam.conjugate())) for lam in values)<1e-10
            response=(residues[None,:,:]/(2j*np.pi*f[:,None,None]-values[None,None,:])).sum(axis=2)
            responses[(case,cutoff)]=response
            cutoffs.append(dict(case=case,pole_magnitude_cutoff_per_s=cutoff,retained=len(selected),
                nearest_pole_magnitude_to_cutoff=float(min(abs(abs(data['values'])-cutoff))),**metrics(response)))
    cutoff_differences=[]
    for cutoff in (5.,10.,20.,40.):
        a=responses[('pointwise',cutoff)];b=responses[('fourier8',cutoff)]
        cutoff_differences.append(dict(cutoff_per_s=cutoff,
            dip_complex_difference_relative_to_pointwise=(abs(b[dip]-a[dip])/abs(a[dip])).tolist(),
            dip_yaw_magnitude_change_percent=float((abs(b[dip,0])/abs(a[dip,0])-1)*100)))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import LogLocator,FuncFormatter
    labels=['Yaw rate [deg/s/F3]','Roll rate [deg/s/F3]','Sideslip [deg/F3]','Bank [deg/F3]']
    def style(ax,j):
        ax.set(xlabel='Frequency [Hz]',ylabel=labels[j],xlim=(.1,10))
        ax.xaxis.set_major_locator(LogLocator(base=10));ax.xaxis.set_major_formatter(FuncFormatter(lambda value,_:f'{value:g}'))
        ax.grid(which='major',alpha=.4);ax.grid(which='minor',alpha=.14)
        ax.axvline(f[dip],color='#6b7280',ls=':',lw=.8)
    fig,axes=plt.subplots(2,2,figsize=(11,8),layout='constrained')
    requests=[16,24,40,q['checks']['available_modes']]
    for j,ax in enumerate(axes.ravel()):
        ax.loglog(f,reference[:,j],'o',ms=2.8,color='black',label='Drela drawing')
        ax.loglog(f,abs(q['full'][:,j]),lw=2,color='#059669',label='Full Fourier system')
        for requested,color in zip(requests,['#9ca3af','#7c3aed','#ea580c','#2563eb']):
            row=next(row for row in q['checks']['truncations'] if row['requested_modes']==requested)
            count=row['retained_modes'];i=int(np.flatnonzero(q['retained']==count)[0])
            ax.loglog(f,abs(q['reduced'][i,:,j]),lw=1.4,color=color,label=f'{count} temporal modes')
        style(ax,j)
    axes[0,0].legend(fontsize=8,loc='lower left')
    fig.suptitle('Daedalus: eight Fourier circulation coefficients per lifting beam\nSame aircraft and 6.7 m/s operating condition; temporal truncation only',fontsize=13)
    fig.savefig(folder/'fourier-modes.png',dpi=160);fig.savefig(folder/'fourier-modes.svg');plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4.6),layout='constrained')
    for ax,cutoff in zip(axes,(20.,40.)):
        ax.loglog(f,reference[:,0],'o',ms=3,color='black',label='Drela drawing')
        ax.loglog(f,abs(p['full'][:,0]),lw=2,color='#059669',label='Full pointwise system')
        ax.loglog(f,abs(q['full'][:,0]),lw=1.3,ls='--',color='#164e63',label='Full Fourier system')
        for case,color in [('pointwise','#7c3aed'),('fourier8','#ea580c')]:
            n=next(row['retained'] for row in cutoffs if row['case']==case and row['pole_magnitude_cutoff_per_s']==cutoff)
            ax.loglog(f,abs(responses[(case,cutoff)][:,0]),color=color,lw=1.5,label=f'{case}: {n} modes')
        style(ax,0);ax.set_title(f'Pole-magnitude cutoff |λ| ≤ {cutoff:g} s⁻¹')
        ax.set_ylim(.025,.5);ax.legend(fontsize=8,loc='lower left')
    fig.suptitle('Matched pole ranges: circulation representation changes modal bookkeeping',fontsize=13)
    fig.savefig(folder/'matched-cutoffs.png',dpi=160);fig.savefig(folder/'matched-cutoffs.svg');plt.close(fig)
    import csv
    with (folder/'comparison.csv').open('x',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['case','selection','frequency_hz','channel','real','imag','magnitude','reference'])
        for case,data in datasets.items():
            cases=[('full',data['full'])]+[(f'count-{n}',data['reduced'][i]) for i,n in enumerate(data['retained'])]
            cases += [(f'cutoff-{cutoff:g}',response) for (key,cutoff),response in responses.items() if key==case]
            for name,response in cases:
                for i,frequency in enumerate(f):
                    for j,channel in enumerate(CHANNELS):writer.writerow([case,name,frequency,channel,response[i,j].real,response[i,j].imag,abs(response[i,j]),reference[i,j]])
    for row in counts:
        if row['case']=='fourier8':print(row,flush=True)
    print('cutoffs',cutoffs,flush=True);print('cutoff differences',cutoff_differences,flush=True)
    return dict(channels=CHANNELS,default_helper_exact_errors=default_errors,mode_counts=counts,
        cutoffs=cutoffs,cutoff_differences=cutoff_differences,
        fourier_numerical_checks=q['checks'],
        qualification='Fixed existing pointwise and Fourier source-equation matrices, documented modal projection, predeclared count and pole-magnitude selections. No fit, production correction or historical operating-setting identification.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--tag',required=True);args=vars(parser.parse_args())
    inputs=[ROOT/'scripts/check_daedalus_source_modes.py',OLD_DRIVER]
    inputs += [path/name for path in (POINT/'compare-112-final',STUDY/'compare-65-final') for name in ('arrays.npz','result.json','terminal.json')]
    source=ROOT/'artifacts/daedalus-source-20261113'
    inputs += [source/'assembled-6.7'/name for name in ('A.npz','M.npz','maps.npz')]
    inputs += [source/'mass-6.7/layout.json',ROOT/'docs/validation/aswing-authoritative-sources.json',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-steady.pdf',ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf']
    run(STUDY,args['tag'],inputs,report,args,__file__)


if __name__=='__main__':main()
