"""Report native multi-surface rate comparison and conditional feedback checks."""
import argparse
from check_daedalus_load_sensitivity import ROOT,SOURCE,read
from daedalus_bounded_job import run

STUDY=ROOT/'artifacts/daedalus-coupled-avl-20261114'
NATIVE=['base','yaw-plus','yaw-minus','roll-plus','roll-minus']
FEEDBACK=['full-feedback-low','full-feedback-dip','full-feedback-high']


def report(folder,args):
    import csv,re
    import numpy as np
    import scipy.sparse as sp
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    replay=read(STUDY/'replay/result.json');cases=[read(STUDY/tag/'result.json') for tag in NATIVE]
    feedback=[read(STUDY/tag/'result.json') for tag in FEEDBACK]
    derivatives=[]
    for entry in replay['derivatives']:
        first,last=entry['stages'][0],entry['stages'][-1]
        derivatives.append(dict(axis=entry['axis'],native=first['wrench'],openswing=last['wrench'],
            relative_difference_percent=(100*(np.array(last['wrench'])/first['wrench']-1)).tolist(),
            surfaces={beam:dict(native=first['surfaces'][beam],openswing=last['surfaces'][beam],
                relative_difference_percent=(100*(np.array(last['surfaces'][beam])/first['surfaces'][beam]-1)).tolist()) for beam in first['surfaces']}))
    for item in feedback:
        base=np.array(item['outputs'][0]['magnitude'])
        for row in item['outputs']:row['amplitude_change_percent']=(100*(np.array(row['magnitude'])/base-1)).tolist()
    with np.load(STUDY/'replay/operators.npz') as archive:
        beam=archive['beam'];native_core=archive['native_core'];source_core=archive['source_core']
    core_ranges=[]
    for source,target in [(1,3),(3,1)]:
        index=np.ix_(beam==target,beam==source)
        core_ranges.append(dict(source=source,target=target,native_range=[float(native_core[index].min()),float(native_core[index].max())],
            source_range=[float(source_core[index].min()),float(source_core[index].max())]))
    with np.load(ROOT/'artifacts/daedalus-load-sensitivity-20261113/reference-dip/arrays.npz') as archive:z=archive['state']
    action_checks=[]
    for tag in ('feedback-blocks','full-feedback-blocks'):
        for channel in read(STUDY/tag/'result.json')['channels']:
            matrix=sp.load_npz(STUDY/tag/f"A-{channel['source_beam']}-to-{channel['target_beam']}.npz")
            magnitude=float(max(abs(matrix@z)));relative=channel['complete_action_error']/magnitude
            assert relative<2e-5,(tag,relative)
            action_checks.append(dict(blocks=tag,source=channel['source_beam'],target=channel['target_beam'],
                action_maximum=magnitude,relative_action_error=relative))
    palette=re.findall(r"'([^']+)'",(ROOT/'web/plot-colors.js').read_text().split('export const plotColors = Object.freeze([')[1].split(']);')[0])
    fig,axes=plt.subplots(1,2,figsize=(12,5.2),layout='constrained')
    labels=['AVL','ASW kernel','ASW core','Control point','Normal','Force velocity','Force vector','Moment arm']
    for i,entry in enumerate(replay['derivatives']):
        values=np.array([stage['surfaces']['3'][5] for stage in entry['stages']]);values=100*values/values[0]
        axes[0].plot(np.arange(len(values)),values,'o-',color=palette[i],label={'x':'Roll-rate input','z':'Yaw-rate input'}[entry['axis']])
    axes[0].set(xticks=np.arange(len(labels)),xticklabels=labels,ylabel='Fin yaw-moment derivative / native value [%]',title='Ordered convention replay\nLoaded, interacting surfaces; steady, Mach zero')
    axes[0].tick_params(axis='x',labelrotation=45,labelsize=8);axes[0].axhline(100,color='#6b7280',ls=':',lw=.8)
    names=['Wing → fin removed','Fin → wing removed','Both removed'];x=np.arange(len(feedback))
    for i,label in enumerate(names):
        values=[case['outputs'][i+1]['amplitude_change_percent'][0] for case in feedback]
        axes[1].bar(x+(i-1)*.23,values,width=.22,color=palette[i],label=label)
    axes[1].set(xticks=x,xticklabels=[f"{case['frequency_hz']:.4g}" for case in feedback],xlabel='Frequency [Hz]',ylabel='Yaw-amplitude change from full baseline [%]',
        title='Direct circulation + vortex-motion feedback\nConditional removal in the complete dynamic system')
    axes[1].axhline(0,color='#6b7280',lw=.8)
    for ax in axes:ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True);ax.legend(fontsize=8)
    fig.suptitle('Daedalus wing–fin airflow interaction: native comparison and Bode diagnostic',fontsize=12)
    fig.savefig(folder/'coupled-avl-feedback.png',dpi=160);fig.savefig(folder/'coupled-avl-feedback.svg');plt.close(fig)
    with (folder/'steady-derivatives.csv').open('x',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['axis','stage','beam_or_total','Fx','Fy','Fz','Mx','My','Mz'])
        for entry in replay['derivatives']:
            for stage in entry['stages']:
                writer.writerow([entry['axis'],stage['name'],'total',*stage['wrench']])
                for b,values in stage['surfaces'].items():writer.writerow([entry['axis'],stage['name'],b,*values])
    with (folder/'feedback.csv').open('x',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['frequency_hz','case','channel','real','imag','magnitude','amplitude_change_percent'])
        for case in feedback:
            for row in case['outputs']:
                for j,channel in enumerate(case['channels']):writer.writerow([case['frequency_hz'],row['case'],channel,row['real'][j],row['imag'][j],row['magnitude'][j],row['amplitude_change_percent'][j]])
    checks={key:max(case[key] for case in cases) for key in ('matched_coordinate_relative_gamma_error','matched_coordinate_max_field_error','native_force_reconstruction_error')}
    result=dict(derivatives=derivatives,feedback=feedback,core_ranges=core_ranges,action_checks=action_checks,native_checks=checks,
        native_replay_error=max(max(e.values()) for e in replay['native_replay_errors']),
        source_replay_error=max(max(e.values()) for e in replay['source_replay_errors']),
        qualification='Steady native AVL and full dynamic conditional checks have separate conditions and scopes. No physical parameter, production equation, operating point or reference denominator is changed. Direct airflow feedback removal does not remove structural/free-frame or indirect aerodynamic coupling.')
    print('rate derivative differences',derivatives,flush=True)
    print('feedback',[(c['frequency_hz'],[r['amplitude_change_percent'][0] for r in c['outputs']]) for c in feedback],flush=True)
    print('checks',checks,'action',action_checks,flush=True)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--tag',required=True);args=vars(parser.parse_args())
    inputs=[ROOT/'web/plot-colors.js',ROOT/'scripts/check_daedalus_coupled_avl.py',ROOT/'scripts/replay_daedalus_coupled_avl.py',
        ROOT/'scripts/check_daedalus_circulation_feedback.py',ROOT/'artifacts/daedalus-load-sensitivity-20261113/reference-dip/arrays.npz']
    inputs += [STUDY/tag/name for tag in [*NATIVE,*FEEDBACK,'replay','feedback-blocks','full-feedback-blocks'] for name in ('result.json','terminal.json')]
    inputs += [STUDY/'replay/operators.npz']+[STUDY/tag/f'A-{source}-to-{target}.npz' for tag in ('feedback-blocks','full-feedback-blocks') for source,target in [(1,3),(3,1)]]
    run(STUDY,args['tag'],inputs,report,args,__file__)


if __name__=='__main__':main()
