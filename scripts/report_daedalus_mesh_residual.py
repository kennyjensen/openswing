"""Report exact mesh-response accounting with mapping qualifications."""
import argparse
from check_daedalus_mesh_residual import ROOT,STUDY,CHANNELS,accepted,packet,map_folder
from daedalus_bounded_job import run


def report(folder,args):
    import csv
    import numpy as np
    p=accepted(STUDY/'projection');data=packet(STUDY/'capture');groups=p['groups']
    broad_names=['wing_position','other_position','remaining_structure','net_force','net_moment','readout','other_equations']
    buckets=[['beam1:position'],[f'beam{i}:position' for i in range(2,6)],
        [name for name in groups if (name.startswith('beam') and not name.endswith(':position')) or name=='joints_ground'],
        ['net_force'],['net_moment'],[],[name for name in groups if not name.startswith('beam') and name not in ('joints_ground','net_force','net_moment')]]
    rows=[];details=[];contributions={};closures=[]
    for row in p['entries']:
        values=np.array(row['contribution_real'])+1j*np.array(row['contribution_imag'])
        value=np.array([sum(values[groups.index(name)] for name in names) for names in buckets],complex)
        value[5]=complex(*row['readout']);actual=complex(*row['actual'])
        error=float(abs(value.sum()-actual));assert error<2e-10;closures.append(error)
        fractions=100*np.real(value*np.conj(actual))/abs(actual)**2
        assert abs(sum(fractions)-100)<2e-7
        contributions[(row['channel'],row['case'])]=value
        for j,name in enumerate(broad_names):
            rows.append(dict(channel=row['channel'],case=row['case'],group=name,
                real=float(value[j].real),imag=float(value[j].imag),projection_percent=float(fractions[j])))
        for j,name in enumerate(groups):
            details.append(dict(channel=row['channel'],case=row['case'],group=name,
                real=float(values[j].real),imag=float(values[j].imag),projection_percent=row['projection_on_actual_change_percent'][j]))
    invariance=max(float(max(abs(contributions[(channel,'objective-repeat')]-contributions[(channel,'objective-reference')]))) for channel in CHANNELS)
    assert invariance<2e-10
    complete=packet(map_folder('compatible-repeat'));original=packet(map_folder('objective-repeat'))
    common=data['common_fine_nodes'];nf=len(data['fine_r'])
    np.testing.assert_array_equal(complete['state'][:6*nf].reshape(nf,6)[common],original['state'][:6*nf].reshape(nf,6)[common])
    completion=accepted(map_folder('compatible-repeat'))['inserted_node_completion'];assert len(completion)==103
    assert all(accepted(map_folder(case))['position_internal_dependency']==0 for case in p['cases'])
    dual=packet(STUDY/'adjoint-roll_rate')['adjoint'];span=[]
    actual=complete['actual_change'][1]
    nodes=np.flatnonzero(data['node_beam']==1)[1::2]
    parents=np.unique(data['element_parent'][data['element_beam']==1])
    for case in ('objective-repeat','material-repeat','compatible-repeat'):
        mapped=packet(map_folder(case))
        for node,parent in zip(nodes,parents):
            es=np.flatnonzero(data['element_parent']==parent);ix=(6*es[:,None]+np.arange(3)).ravel()
            v=-np.vdot(dual[ix],mapped['residual'][ix])
            span.append(dict(case=case,parent=int(parent),loaded_span_position_ft=float(data['fine_r'][node,1]),
                real=float(v.real),imag=float(v.imag),projection_percent=float(100*(v*actual.conjugate()).real/abs(actual)**2)))
    for name,values in [('broad-accounting.csv',rows),('row-accounting.csv',details),('wing-position-accounting.csv',span)]:
        with (folder/name).open('x',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(values[0]));writer.writeheader();writer.writerows(values)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(13,5),layout='constrained');x=np.arange(6);width=.25
    for j,(case,name,color) in enumerate((('objective-repeat','Rigid-section transport','#ff4a3d'),
        ('material-repeat','Material interpolation','#ff9f1a'),('compatible-repeat','Inserted-node completion','#ffd166'))):
        values=[next(r['projection_percent'] for r in rows if r['channel']=='roll_rate' and r['case']==case and r['group']==group) for group in broad_names[:6]]
        axes[0].bar(x+(j-1)*width,values,width,color=color,edgecolor='#555',linewidth=.5,label=name)
        values=[r for r in span if r['case']==case]
        axes[1].plot([r['loaded_span_position_ft'] for r in values],[r['projection_percent'] for r in values],'.-',color=color,linewidth=1.5,label=name)
    axes[0].set(xticks=x,xticklabels=['Wing\nposition','Other\nposition','Other\nstructure','Net\nforce','Net\nmoment','Readout'],ylabel='Signed projection onto complex roll change (%)',title='Equation attribution depends on the motion mapping')
    axes[1].set(xlabel='Loaded spanwise position (ft)',ylabel='Contribution of each original wing interval (%)',title='Wing position compatibility')
    for ax in axes:ax.axhline(0,color='#555',linewidth=.8);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True);ax.legend(fontsize=8)
    fig.suptitle('Exact equation accounting at 1.5 Hz; signed contributions can cancel',fontsize=12)
    fig.savefig(folder/'mesh-residual-accounting.png',dpi=150);fig.savefig(folder/'mesh-residual-accounting.svg');plt.close(fig)
    result=dict(frequency_hz=1.5,broad_rows=rows,wing_position_rows=span,
        maximum_identity_closure=max(closures),broad_internal_force_mapping_difference=invariance,
        original_projection_replay_error=p['original_projection_replay_error'],
        completed_nodes=len(completion),maximum_completion_condition=max(r['condition'] for r in completion),
        maximum_inserted_translation_change_ft=max(r['translation_change_ft'] for r in completion),
        maximum_inserted_rotation_change_rad=max(r['rotation_change_rad'] for r in completion),
        preserved_original_nodes=len(common),rank_probe=accepted(STUDY/'rank-probe'),
        qualifications=['All percentages project complex row contributions onto the observed whole-mesh change; they are not amplitude changes or positive fractions of physical causes.',
            'Both discretization and equilibrium change between the saved aircraft. This identity does not separate those causes.',
            'The internal-force variant uses the current refined OpenSwing solution, not native ASWING data.',
            'The completed mapping changes only inserted-node trial poses while retaining every original-node motion and each local torsional null component.',
            'Kinematic/circulation remainders are retained in the CSV; the plot omits their numerically negligible bars. No reference curve or physical parameter is fitted.'])
    print([r for r in rows if r['channel']=='roll_rate'],flush=True);return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--tag',required=True);args=vars(parser.parse_args())
    inputs=[ROOT/'scripts/check_daedalus_mesh_residual.py',ROOT/'docs/validation/ISAE_STATUS.md',ROOT/'docs/validation/aswing-authoritative-sources.json',
        STUDY/'rank-probe/result.json',STUDY/'rank-probe/terminal.json']
    folders=[STUDY/'capture',STUDY/'projection',*[map_folder(case) for case in ('objective-repeat','objective-reference','material-repeat','compatible-repeat')],*[STUDY/f'adjoint-{channel}' for channel in CHANNELS]]
    inputs += [folder/name for folder in folders for name in ('arrays.npz','result.json','terminal.json')]
    run(STUDY,args['tag'],inputs,report,args,__file__)


if __name__=='__main__':main()
