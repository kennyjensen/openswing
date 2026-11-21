"""Independent residue check and saved-data presentation for current modes."""
import argparse
from check_daedalus_source_modes import STUDY,ROOT,SOURCE,CHANNELS,matrices
from check_daedalus_load_sensitivity import read
from daedalus_bounded_job import run

COMPARISON=STUDY/'compare-112-final'
CONTOUR=STUDY/'contour-v3'


def contour(folder,args):
    import numpy as np
    import scipy.sparse as sp
    from scipy.sparse.linalg import splu
    matrix=SOURCE/'assembled-6.7'
    a,m=(sp.load_npz(matrix/name).tocsc() for name in ('A.npz','M.npz'))
    maps=np.load(matrix/'maps.npz');b=maps['B'][:,0];c=maps['C']
    ar,mr,br,_,keep=matrices()
    bootstrap=splu((ar+.01*mr).tocsc());bootstrap.solve(np.ones(len(keep)));del bootstrap
    removed=np.setdiff1d(np.arange(len(b)),keep)
    saved=np.load(COMPARISON/'arrays.npz');values=saved['values'];residues=saved['residues']
    ranked=read(COMPARISON/'result.json')['ranked_components']
    pairs=[entry for entry in ranked if len(entry['indices'])==2][:2]
    rows=[];arrays={}
    for index,pair in enumerate(pairs):
        j=pair['indices'][0];center=values[j];radius=.2
        distance=min(abs(np.delete(values,j)-center));assert distance>3*radius
        phase=np.exp(2j*np.pi*np.arange(16)/16);responses=[];backward=[]
        for point in center+radius*phase:
            # Cyclic-coordinate elimination avoids the full factor's large
            # near-pole fill. Recover those four coordinates and verify every
            # original equation; no dynamical mode is removed from this solve.
            k=(point*m-a).tocsc()
            # Removed rows affect retained RHS only through heading-rate
            # elimination. For F3 all four removed RHS entries are zero.
            assert np.max(abs(b[removed]),initial=0)==0
            z=np.empty(len(b),complex)
            z[keep]=splu((point*mr-ar).tocsc()).solve(br.astype(complex))
            z[removed]=np.linalg.solve(k[removed,:][:,removed].toarray(),b[removed]-k[removed,:][:,keep]@z[keep])
            responses.append(c@z)
            denominator=np.max(np.asarray(abs(k).sum(axis=1)))*np.max(abs(z))+np.max(abs(b))
            backward.append(float(np.max(abs(k@z-b))/denominator))
        responses=np.array(responses)
        fine=np.mean(radius*phase[:,None]*responses,axis=0)
        coarse=np.mean(radius*phase[::2,None]*responses[::2],axis=0)
        expected=residues[:,j];error=abs(fine-expected);change=abs(coarse-fine)
        assert np.all(error<1e-9+1e-6*abs(expected)),error
        assert np.all(change<1e-9+2e-6*abs(fine)),change
        assert max(backward)<1e-10
        rows.append(dict(eigenvalue=[float(center.real),float(center.imag)],radius=radius,
            nearest_other_computed_pole_distance=float(distance),
            max_modal_relative_error=float(max(error/np.maximum(abs(expected),1e-14))),
            max_8_to_16_relative_change=float(max(change/np.maximum(abs(fine),1e-14))),
            max_backward_error=max(backward)))
        arrays.update({f'pair{index}_'+key:value for key,value in dict(contour16=fine,contour8=coarse,modal=expected,responses=responses).items()})
    np.savez_compressed(folder/'arrays.npz',**arrays)
    print(rows,flush=True)
    return dict(pairs=rows,full_dimension=2044,solves=32,
        qualification='Full-pencil contour integrals check two isolated modal residues without using left eigenvectors in the estimator. This is numerical verification, not a native-ASWING comparison.')


def report(folder,args):
    import csv
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import LogLocator,FuncFormatter
    data=np.load(COMPARISON/'arrays.npz');f=data['frequencies'];full=data['full'];reference=data['reference']
    reduced=data['reduced'];counts=data['retained'];dip=int(np.argmin(abs(f-1.15737773741517)))
    # The source comparison contains a 61-point log grid plus four inserted
    # diagnostic frequencies. Use only that grid for equally weighted dB RMS.
    uniform=np.min(abs(f[:,None]-np.logspace(-1,1,61)[None,:]),axis=1)<1e-12
    metrics=[]
    for label,response in [('Full system',full)]+[(str(count)+' modes',reduced[i]) for i,count in enumerate(counts)]:
        db=20*np.log10(abs(response)/reference)
        row=dict(model=label,dip_magnitude=abs(response[dip]).tolist(),
            dip_signed_reference_error_percent=((abs(response[dip])/reference[dip]-1)*100).tolist(),
            rms_db=[float(np.sqrt(np.mean(db[uniform,j]**2))) for j in range(4)],
            low_frequency_0_1_magnitude=abs(response[0]).tolist(),
            low_frequency_0_1_error_percent=((abs(response[0])/reference[0]-1)*100).tolist())
        metrics.append(row)
    fig,axes=plt.subplots(2,2,figsize=(11,8),layout='constrained')
    labels=['Yaw rate [deg/s/F3]','Roll rate [deg/s/F3]','Sideslip [deg/F3]','Bank [deg/F3]']
    for j,ax in enumerate(axes.ravel()):
        ax.loglog(f,reference[:,j],'o',ms=2.8,color='black',label='Drela drawing (digitized)')
        ax.loglog(f,abs(full[:,j]),color='#059669',lw=2,label='Full system')
        for count,color in [(28,'#9ca3af'),(57,'#7c3aed'),(112,'#ea580c')]:
            i=int(np.flatnonzero(counts==count)[0])
            ax.loglog(f,abs(reduced[i,:,j]),color=color,lw=1.5,label=f'{count} modes')
        ax.axvline(f[dip],color='#6b7280',lw=.8,ls=':')
        ax.set(xlabel='Frequency [Hz]',ylabel=labels[j],xlim=(.1,10))
        ax.xaxis.set_major_locator(LogLocator(base=10))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda value,_:f'{value:g}'))
        ax.grid(which='major',alpha=.4);ax.grid(which='minor',alpha=.14)
    axes[0,0].legend(fontsize=8,loc='lower left')
    fig.suptitle('Daedalus: modal truncation can deepen the yaw dip\nFixed current 6.7 m/s model; historical ROM settings unknown',fontsize=13)
    fig.savefig(folder/'modal-comparison.png',dpi=160);fig.savefig(folder/'modal-comparison.svg');plt.close(fig)
    with (folder/'comparison.csv').open('x',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['model','frequency_hz','channel','real','imag','magnitude','reference_magnitude'])
        for label,response in [('full',full)]+[(str(count),reduced[i]) for i,count in enumerate(counts)]:
            for i,frequency in enumerate(f):
                for j,channel in enumerate(CHANNELS):writer.writerow([label,frequency,channel,response[i,j].real,response[i,j].imag,abs(response[i,j]),reference[i,j]])
    old=np.load(STUDY/'compare-57/arrays.npz');oldi=int(np.flatnonzero(old['retained']==57)[0]);newi=int(np.flatnonzero(counts==57)[0])
    old_change=float(np.max(abs(old['reduced'][oldi]-reduced[newi])));assert old_change<2e-7
    summary=dict(channels=CHANNELS,metrics=metrics,first_57_repeat_max_complex_difference=old_change,
        contour=read(CONTOUR/'result.json'),comparison_checks=read(COMPARISON/'result.json'),
        qualification='No modal selection or physical parameter is fitted to the drawing. The 57-mode near-dip match changes when more modes are included and does not establish historical ASWING agreement.')
    for row in metrics:
        if row['model'] in ('Full system','28 modes','57 modes','112 modes'):print(row,flush=True)
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=['contour','report']);parser.add_argument('--tag',required=True)
    args=vars(parser.parse_args());inputs=[ROOT/'scripts/check_daedalus_source_modes.py']
    inputs += [COMPARISON/name for name in ('arrays.npz','result.json','terminal.json')]
    inputs += [SOURCE/'assembled-6.7'/name for name in ('A.npz','M.npz','maps.npz')]
    if args['stage']=='report':
        inputs += [STUDY/'compare-57'/name for name in ('arrays.npz','result.json','terminal.json')]
        inputs += [CONTOUR/name for name in ('arrays.npz','result.json','terminal.json')]
    run(STUDY,args['tag'],inputs,globals()[args['stage']],args,__file__)


if __name__=='__main__':main()
