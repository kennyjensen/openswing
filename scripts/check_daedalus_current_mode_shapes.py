"""Physical deformation and material strain participation of two current poles.

This uses saved eigensolutions, not a new aircraft solve or fitted parameter.
The positive quadratic material-strain measure omits geometric/prestress and
aerodynamic energy and must not be described as total modal energy.
"""
import argparse
from pathlib import Path
from check_daedalus_load_sensitivity import ROOT,SOURCE,read
from daedalus_bounded_job import run

STUDY=ROOT/'artifacts/daedalus-mode-shapes-20261114'
MODES=ROOT/'artifacts/daedalus-source-modes-20261114'
STRAIN=ROOT/'artifacts/daedalus-source-strain-20261114'
PAPER=ROOT/'reference/daedalus-flight-research-20261114'


def analyze(folder,args):
    import pickle
    import numpy as np
    import scipy.sparse as sp
    from daedalus_source_strain_reference import Compatibility,GENERATORS
    with (STRAIN/'capture/fixture.pkl').open('rb') as stream:fixture=pickle.load(stream)
    ref=Compatibility(fixture);nn=len(fixture['positions']);ne=len(fixture['ends'])
    assert nn==108 and ne==103 and fixture['size']==2044
    for key in ('EIcs','EIcn','EIsn','Cea','Nea','Cta','Nta'):assert np.max(abs(fixture['material'][key]))==0
    a,m=(sp.load_npz(SOURCE/'assembled-6.7'/name).tocsc() for name in ('A.npz','M.npz'))
    with np.load(MODES/'compare-112-final/arrays.npz') as archive:
        values=archive['values'];vectors=archive['vectors']
    with np.load(MODES/'paired-112-batch3/arrays.npz') as archive:keep=archive['keep']
    removed=np.setdiff1d(np.arange(2044),keep)
    ranked=read(MODES/'compare-112-final/result.json')['ranked_components']
    pairs=[row for row in ranked if len(row['indices'])==2][:2]
    pairs.sort(key=lambda row:row['damped_frequency_hz'])
    beam=fixture['beam'];station=fixture['station'];r=fixture['positions']
    groups={'wing':beam==1,'stabilizer':beam==2,'fin':beam==3,
        'forward_boom':(beam==4)&(station<2.5),'aft_boom':(beam==4)&(station>=2.5),'fairing':beam==5}
    assert np.all(sum(mask.astype(int) for mask in groups.values())==1)
    nodes={key:np.unique(fixture['ends'][mask]) for key,mask in groups.items()}
    assert 14 in nodes['wing'] and 75 in nodes['aft_boom']
    def amplitude(v):
        aa=np.sum(v.real**2,axis=-1);bb=np.sum(v.imag**2,axis=-1);ab=np.sum(v.real*v.imag,axis=-1)
        return np.sqrt((aa+bb+np.sqrt((aa-bb)**2+4*ab**2))/2)
    rows=[];arrays=dict(positions=r,ends=fixture['ends'],beam=beam,station=station)
    for k,pair in enumerate(pairs):
        j=pair['indices'][0];value=values[j];z=np.empty(2044,complex);z[keep]=vectors[:,j]
        pencil=(value*m-a).tocsc()
        z[removed]=np.linalg.solve(pencil[removed,:][:,removed].toarray(),-pencil[removed,:][:,keep]@z[keep])
        # Set only the arbitrary display amplitude and phase, never a property.
        pose=z[:6*nn].reshape(nn,6);dr=fixture['L']*pose[:,:3]
        dominant=np.unravel_index(np.argmax(abs(dr)),dr.shape)
        z*=np.exp(-1j*np.angle(dr[dominant]))/(max(amplitude(dr))*304.8)
        pose=z[:6*nn].reshape(nn,6);dr=fixture['L']*pose[:,:3];theta=pose[:,3:]
        internal=z[6*nn:6*(nn+ne)].reshape(ne,6)
        dn=fixture['F']*internal[:,:3];dm=fixture['ML']*internal[:,3:]
        av=a@z;mv=m@z;residual=float(np.linalg.norm(av-value*mv)/(np.linalg.norm(av)+abs(value)*np.linalg.norm(mv)))
        assert residual<1e-7
        compatibility,_=ref.tangent(dr,theta,dn,dm)
        assert max(abs(compatibility))<2e-8
        endpoint_theta=theta[[ref.a,ref.b]].transpose(1,0,2)
        dframes=np.einsum('nej,jkl->nekl',endpoint_theta,GENERATORS)@ref.frame
        dmean=dframes.mean(axis=1)
        local_force=np.einsum('nji,nj->ni',dmean,ref.force)+np.einsum('nji,nj->ni',ref.mean_frame,dn)
        local_moment=np.einsum('nji,nj->ni',dmean,ref.moment)+np.einsum('nji,nj->ni',ref.mean_frame,dm)
        local=np.c_[local_force,local_moment];strain=np.einsum('nij,nj->ni',ref.law,local)
        energy=.25*fixture['length'][:,None]*np.real(local.conj()*strain)
        assert np.min(energy)>=-1e-15 and energy.sum()>0
        energy=np.maximum(energy,0);total=float(energy.sum())
        fractions={key:float(energy[mask].sum()/total) for key,mask in groups.items()}
        assert abs(sum(fractions.values())-1)<2e-14
        directions=energy.sum(axis=0)/total
        node_amplitude=amplitude(dr)*304.8;assert abs(max(node_amplitude)-1)<2e-14
        root_removed={}
        for name,root in [('wing',14),('aft_boom',75)]:
            ids=nodes[name];relative=dr[ids]-dr[root]-np.cross(theta[root],r[ids]-r[root])
            root_removed[name]=dict(nodes=ids,translation=relative*304.8,root=root)
        row=dict(eigenvalue=[float(value.real),float(value.imag)],damped_frequency_hz=float(value.imag/(2*np.pi)),
            decay_rate_per_s=float(-value.real),material_strain_fraction=fractions,
            material_components=dict(zip(['chord_shear','axial','normal_shear','bend_about_chord','torsion','bend_about_normal'],directions.tolist())),
            wing_bending_components=(energy[groups['wing'],3:].sum(axis=0)/total).tolist(),
            body_relative_displacement_max_mm={key:float(max(node_amplitude[ids])) for key,ids in nodes.items()},
            root_removed_component_max_mm={key:np.max(abs(data['translation']),axis=0).tolist() for key,data in root_removed.items()},
            eigen_residual=residual,independent_compatibility_max=float(max(abs(compatibility))),
            normalization='Maximum body-relative nodal harmonic displacement envelope is 1 mm; this is arbitrary eigenmode scale, not response per F3.')
        rows.append(row)
        arrays.update({f'mode{k}_state':z,f'mode{k}_energy':energy,f'mode{k}_displacement_mm':dr*304.8})
        for key,data in root_removed.items():arrays.update({f'mode{k}_{key}_nodes':data['nodes'],f'mode{k}_{key}_relative_mm':data['translation']})
    np.savez_compressed(folder/'arrays.npz',**arrays)
    # Table 2-3 prints imperial and SI inertias. Preserve both, rather than
    # treating the apparent decimal/conversion discrepancy as an aircraft input.
    factor=14.59390293720636*.3048**2
    imperial=np.array([[815.7,82.9,849.8],[1596.9,138.6,1185.8]])
    printed=np.array([[11057.,1124.,11520.],[21648.,1879.,16070.]])
    conversions=dict(slug_ft2_to_kg_m2=factor,printed_slug_ft2=imperial.tolist(),
        computed_kg_m2=(factor*imperial).tolist(),printed_kg_m2=printed.tolist(),
        printed_over_computed=(printed/(factor*imperial)).tolist(),
        interpretation='Printed rows disagree by approximately ten. The Light Eagle values are not substituted for literal Daedalus inputs.')
    print(rows,flush=True);print('inertia conversions',conversions,flush=True)
    return dict(modes=rows,inertia_conversion_check=conversions,
        qualification='Material-strain and deformation diagnostics of two saved current eigenmodes. The material quadratic omits geometric/prestress and fluid terms and is not total modal energy. NASA prototype dynamics are not a matched Daedalus/ASWING validation.')


def plot(folder,args):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    data=np.load(STUDY/'analyze/arrays.npz');rows=read(STUDY/'analyze/result.json')['modes']
    fig,axes=plt.subplots(1,3,figsize=(13,4.5),layout='constrained')
    colors=['#7c3aed','#059669'];groups=list(rows[0]['material_strain_fraction'])
    labels=['Wing','Stabilizer','Fin','Forward boom','Aft boom','Fairing']
    for k,(row,color) in enumerate(zip(rows,colors)):
        label=f"{row['damped_frequency_hz']:.4f} Hz"
        axes[0].barh(np.arange(len(groups))+.18*(2*k-1),[100*row['material_strain_fraction'][key] for key in groups],height=.34,color=color,label=label)
        for ax,key,coordinate,component in [(axes[1],'wing',1,0),(axes[2],'aft_boom',0,1)]:
            ids=data[f'mode{k}_{key}_nodes'];order=np.argsort(data['positions'][ids,coordinate])
            ax.plot(data['positions'][ids,coordinate][order],abs(data[f'mode{k}_{key}_relative_mm'][order,component]),color=color,label=label)
    axes[0].set(yticks=np.arange(len(groups)),yticklabels=labels,xlabel='Share of material-strain quadratic [%]',title='Elastic material participation')
    axes[1].set(xlabel='Body span coordinate [ft]',ylabel='Wing fore/aft deformation amplitude [mm]',title='Wing, root rigid motion removed')
    axes[2].set(xlabel='Body streamwise coordinate [ft]',ylabel='Boom lateral deformation amplitude [mm]',title='Aft boom, root rigid motion removed')
    for ax in axes:ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.suptitle('Two current Daedalus modes that cancel in the rudder response\nEach mode scaled to 1 mm maximum body-relative nodal motion; no physical parameter fitted',fontsize=12)
    fig.savefig(folder/'mode-shapes.png',dpi=160);fig.savefig(folder/'mode-shapes.svg');plt.close(fig)
    return dict(modes=rows,normalization='Arbitrary 1 mm nodal envelope for each eigenmode.',source='analyze/result.json')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=['analyze','plot']);parser.add_argument('--tag',required=True);args=vars(parser.parse_args())
    inputs=[ROOT/'scripts/daedalus_source_strain_reference.py',STRAIN/'capture/fixture.pkl',
        MODES/'compare-112-final/arrays.npz',MODES/'compare-112-final/result.json',MODES/'paired-112-batch3/arrays.npz',
        PAPER/'sullivan-zerweckh-1988-flight-tests.pdf',PAPER/'receipt.json',ROOT/'docs/validation/aswing-authoritative-sources.json']
    inputs += [SOURCE/'assembled-6.7'/name for name in ('A.npz','M.npz')]
    if args['stage']=='plot':inputs += [STUDY/'analyze'/name for name in ('arrays.npz','result.json','terminal.json')]
    run(STUDY,args['tag'],inputs,globals()[args['stage']],args,__file__)


if __name__=='__main__':main()
