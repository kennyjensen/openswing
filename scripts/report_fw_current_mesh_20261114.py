"""Current-default FW root comparisons; legacy-mesh results stay separate."""
import argparse
import json
from pathlib import Path
from check_daedalus_load_sensitivity import ROOT,pin,write
from check_fw_current_mesh_20261114 import STUDY
from daedalus_bounded_job import run

CASES={64:['slow','damped','low','oscillatory'],38:['slow','middle','damped','flutter']}


def report(folder,args):
    import numpy as np
    from scipy.optimize import linear_sum_assignment
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    reference=json.loads((ROOT/'docs/validation/fw-reference.json').read_text())
    cases=[];checks=[];used=[];pins={};runners={}
    for speed,groups in CASES.items():
        trimtag='cold-trim-32-64' if speed==64 else 'trim-32-38'
        trim=json.loads((STUDY/trimtag/'result.json').read_text())
        assert trim['mesh_recipe']=='accurate-arc-v2' and trim['residual']<1e-10
        used += [trimtag,f'matrices-32-{speed}']
        found=[]
        for group in groups:
            tag=f'modes-{speed}-{group}';used += [tag,f'directions-{speed}-{group}']
            data=json.loads((STUDY/tag/'result.json').read_text())
            assert data['mesh_recipe']=='accurate-arc-v2'
            found += [dict(group=group,index=i,**r) for i,r in enumerate(data['modes'])]
            direct=json.loads((STUDY/f'directions-{speed}-{group}'/'result.json').read_text())
            assert direct['mesh_recipe']=='accurate-arc-v2'
            checks += [dict(speed_ft_s=speed,group=group,**r) for r in direct['checks']]
        native=next(p for p in reference['points'] if p['speed_ft_s']==speed)
        r=np.array([complex(*v) for v in native['plotted_roots_per_s']])
        c=np.array([complex(*v['eigenvalue']) for v in found])
        pairwise=abs(c[:,None]-c[None,:]);np.fill_diagonal(pairwise,np.inf)
        assert np.min(pairwise)>1e-5
        rows,cols=linear_sum_assignment(abs(r[:,None]-c[None,:]))
        assert len(rows)==9
        comparisons=[]
        for i,j in zip(rows,cols):
            delta=c[j]-r[i]
            comparisons.append(dict(label=f'R{i+1}',reference=native['plotted_roots_per_s'][i],
                current=found[j]['eigenvalue'],group=found[j]['group'],index=found[j]['index'],
                difference=[float(delta.real),float(delta.imag)],
                relative_complex_distance_percent=float(100*abs(delta)/abs(r[i])),
                growth_relative_error_percent=None if abs(r[i].real)<.01 else float(100*delta.real/r[i].real),
                frequency_relative_error_percent=None if abs(r[i].imag)<.01 else float(100*delta.imag/r[i].imag)))
        cases.append(dict(speed_ft_s=speed,trim=trim,comparisons=comparisons,
            unmatched=[v for j,v in enumerate(found) if j not in cols],
            maximum_complex_error_percent=max(v['relative_complex_distance_percent'] for v in comparisons),
            maximum_pencil_backward_error=max(max(v['right_backward_error'],v['left_backward_error']) for v in found)))
    assert all(c['accepted'] for c in checks)
    used += ['layout-fixed-32-64','trim-32-50']
    terminals=[]
    for tag in used:
        job=STUDY/tag
        terminal=json.loads((job/'terminal.json').read_text())
        assert terminal['returncode']==0 and terminal['process_reaped'] and terminal['inputs_unchanged']
        terminals.append(terminal)
        plan=json.loads((job/'plan.json').read_text())
        for name,sha in plan['inputs_sha256'].items():
            if Path(name).name in ('check_fw_current_mesh_20261114.py','check_fw_current_directions_20261114.py'):
                saved=job/'runner.py'
                if pin(saved)==sha:runners[str(saved)]=sha
                else:
                    # A directions job imports the current-mesh helper, which
                    # may later gain CLI/reporting options. Its full source is
                    # pinned independently in the corresponding matrix/root
                    # jobs' immutable runners; retain that exact version.
                    candidates=[p for p in STUDY.glob('*/runner.py') if pin(p)==sha]
                    assert candidates,name
                    runners[str(candidates[0])]=sha
            elif name not in pins:
                assert pin(Path(name))==sha,name
                pins[name]=sha
            else:assert pins[name]==sha
    previous=json.loads((ROOT/'artifacts/fw-modes-20261114/report-fixed/result.json').read_text())
    current64=next(c for c in cases if c['speed_ft_s']==64)
    mesh_changes=[]
    for old,new in zip(previous['comparisons'],current64['comparisons']):
        assert old['label']==new['label']
        a,b=complex(*old['current']),complex(*new['current'])
        mesh_changes.append(dict(label=new['label'],legacy=old['current'],fresh=new['current'],
            relative_complex_change_percent=100*abs(b-a)/abs(a)))
    fig,axes=plt.subplots(1,2,figsize=(10.5,6.2),gridspec_kw={'width_ratios':[1.4,1]})
    for case in sorted(cases,key=lambda c:c['speed_ft_s']):
        speed=case['speed_ft_s'];color='#c86820' if speed==38 else '#007fba'
        for ax,subset in [(axes[0],case['comparisons']),(axes[1],case['comparisons'][:3])]:
            a=np.array([v['reference'] for v in subset]);b=np.array([v['current'] for v in subset])
            ax.scatter(a[:,0],a[:,1],s=65,facecolors='none',edgecolors=color,linewidths=1.6,
                       label=f'{speed} ft/s published',zorder=3)
            ax.scatter(b[:,0],b[:,1],s=40,marker='x',color=color,linewidths=1.7,
                       label=f'{speed} ft/s current',zorder=4)
            for x,y in zip(a,b):ax.plot([x[0],y[0]],[x[1],y[1]],color=color,linewidth=.8)
        extra=case['unmatched']
        if extra:axes[0].scatter([v['eigenvalue'][0] for v in extra],[v['eigenvalue'][1] for v in extra],
                                marker='^',color='#777777',s=45,label='Additional current root')
    for ax in axes:
        ax.grid(True,color='#dedede',linewidth=.7)
        ax.axhline(0,color='#999999',linewidth=.8);ax.axvline(0,color='#999999',linewidth=.8)
        ax.set_xlabel('Growth rate, σ (1/s)');ax.set_ylabel('Angular frequency, ω (rad/s)')
    axes[0].set_xlim(-18,2.5);axes[0].set_ylim(-1.8,29);axes[0].legend(loc='upper left',fontsize=8)
    axes[0].set_title('All plotted roots at the two speeds',fontsize=12)
    axes[1].set_xlim(-.32,.005);axes[1].set_ylim(-.04,.82);axes[1].set_title('Slow modes, enlarged',fontsize=12)
    fig.suptitle('FW · fresh default mesh, 40 lifting panels',fontsize=15)
    fig.text(.5,.02,'Cold start at 64 ft/s; full equilibrium continuation through 50 to 38 ft/s.\n'
             'Native mesh unspecified. These are root comparisons, not native Bode gain/phase validation.',
             ha='center',fontsize=9,color='#444444')
    fig.tight_layout(rect=(0,.08,1,.94));fig.savefig(folder/'comparison.png',dpi=160);fig.savefig(folder/'comparison.svg');plt.close(fig)
    write(folder/'checks.json',checks);write(folder/'source-pins.json',dict(inputs=pins,runners=runners))
    return dict(scope='Current-default accurate-arc-v2 mesh, all nine published roots at 38 and 64 ft/s.',
        cases=cases,legacy_mesh_changes_at_64=mesh_changes,
        fresh_mesh_compared_positions=18,total_published_positions=108,
        direct_residual_passed=sum(c['accepted'] for c in checks),direct_residual_total=len(checks),
        maximum_scaled_full_residual=max(c['scaled_full_mode_residual'] for c in checks),
        successful_jobs=len(used),max_cpu_seconds=max(t['cpu_seconds'] for t in terminals),
        max_wall_seconds=max(t['wall_seconds'] for t in terminals),max_rss_kib=max(t['peak_rss_kib'] for t in terminals),
        limitation='Counts are comparison coverage, not blanket pass claims. Other speeds, native mesh and forced-response gain/phase remain open.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--tag',required=True);args=vars(parser.parse_args())
    inputs=[ROOT/'scripts/check_fw_current_mesh_20261114.py',ROOT/'scripts/check_fw_current_directions_20261114.py',
            ROOT/'docs/validation/fw-reference.json',ROOT/'artifacts/fw-modes-20261114/report-fixed/result.json']
    for p in STUDY.glob('*/result.json'):
        if not p.parent.name.startswith('report'):
            inputs += [p,p.parent/'terminal.json',p.parent/'plan.json',p.parent/'runner.py']
    run(STUDY,args['tag'],inputs,report,args,__file__)
