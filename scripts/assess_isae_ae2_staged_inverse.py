"""Audit complete staged AE-2 evidence; reuse saved tangents for sensitivity."""
import argparse
from datetime import datetime
import json
import math
from pathlib import Path
import resource
import signal
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.probe_isae_ae2_staged_inverse import checked,read,write,pin,now


def assess(stage):
    import numpy as np
    from scripts.isae_custom_tangent_stages import assemble,conclude
    plan=checked(stage);control=read(stage/'control.json');assert control['status']=='PASS'
    coarse=read(Path(plan['parent'])/'assessment.json');rows=[];pins=[];physical=0
    for case in plan['cases']:
        folder=stage/'cases'/case['name'];report=read(folder/'report.json')
        assert report['status']=='computed' and all(c['passed'] for c in report['checks'])
        assert report['result']==pin(folder/'result.json') and report['fresh_result']==pin(folder/'restored-result.json')
        assert report['candidate']==pin(folder/'candidate.json')
        pending=read(folder/'candidate.json');assert all(pin(p['path'])==p for p in pending['pins'])
        request=read(folder/'request.json')
        assert {k:v for k,v in request.items() if k!='initial_state'}==case['request']
        result=read(folder/'result.json');fresh=read(folder/'restored-result.json')
        s=result['sensors'][0];other=fresh['sensors'][0]
        values=dict(IAS=result['operating_values']['speed'],RY_m=s['position_earth'][1],
            Psi_deg=s['heading'],sensor_V_m_s=s['speed'],sensor_beta_deg=s['beta'])
        assert values==report['values'] and all(math.isfinite(v) for v in values.values())
        assert max(result['residual'],fresh['residual'])<=1e-8
        assert math.dist(s['position_earth'],other['position_earth'])<=1e-10
        assert abs(s['heading']-other['heading'])<=1e-8 and abs(s['beta']-other['beta'])<=1e-8
        assert result['structural_operator']==case['request']['numerics']['structural_operator']
        assert result['equilibrium_state']['identity']['beam_interpolation']==case['request']['numerics']['beam_interpolation']
        norm=lambda v:math.sqrt(sum(x*x for x in v))
        for kind in ('force','moment'):
            a,b=result['applied_'+kind],result['support_'+kind]
            assert norm([x+y for x,y in zip(a,b)])<=1e-7*(norm(a)+norm(b))
        flow=s['air_velocity_sensor'];assert abs(norm(flow)-s['speed'])<=1e-12
        assert abs(math.degrees(math.asin(-flow[1]/norm(flow)))-s['beta'])<=1e-10
        state=result['equilibrium_state']
        assert max(map(abs,state['positions'][0]+state['rotations'][0]))<=1e-10
        assert abs(values['RY_m']-case['native_row']['values']['RY_m'])<=1e-8
        blocks=[]
        for index in range(6):
            p=folder/'columns'/f'{index:03d}.npz';r=read(p.with_suffix('.json'))
            assert r['block']==pin(p) and r['candidate']==pin(folder/'candidate.json')
            with np.load(p) as data:b={k:data[k].copy() for k in data.files}
            b.update(first=int(b['first']),stop=int(b['stop']),mismatch=float(b['mismatch']))
            assert int(b['residual_evaluations'])==1+4*(b['stop']-b['first'])
            blocks.append(b)
        jac,_=assemble(blocks,case['size']);tangent=conclude(blocks,case['size'])
        assert tangent==report['custom_tangent']
        with np.load(folder/'candidate.npz') as data:x=data['x'].copy()
        assert abs(case['request']['condition']['speed']*math.exp(x[-1])-values['IAS'])<=1e-12
        # R_custom=(Y-Ytarget)/scale, and the final variable is log(U/U0).
        # Differentiate every equilibrium row, reusing the complete saved J.
        rhs=np.zeros(len(x));rhs[-1]=1/case['request']['operating_constraints'][0]['residual_scale']
        dx_dy=np.linalg.solve(jac,rhs)
        defect=float(np.max(abs(jac@dx_dy-rhs)));assert defect<=1e-10
        derivative=values['IAS']*float(dx_dy[-1])
        old,=[r for r in coarse['rows'] if r['mesh']==20 and r['inverse'] and r['native_speed']==case['native_speed']]
        mesh={key:100*abs(values[key]-old['values'][key])/abs(values[key]) for key in values}
        rows.append(dict(name=case['name'],native_speed=case['native_speed'],values=values,
            coarse_values=old['values'],coarse_to_fine_percent=mesh,
            speed_error_percent=100*(values['IAS']-case['native_speed'])/case['native_speed'],
            heading_error_percent=100*(values['Psi_deg']-case['native_row']['values']['Psi_deg'])/abs(case['native_row']['values']['Psi_deg']),
            fresh_residual=fresh['residual'],tangent=tangent,speed_derivative_per_tip_y=derivative,
            tangent_solve_defect=defect,physical_checks=len(report['checks'])))
        physical+=len(report['checks'])
        pins += [pin(p) for p in sorted(folder.rglob('*')) if p.is_file()]
    near={r['native_speed']:r for r in rows if r['native_speed'] in (17,19)}
    secant=(near[17]['values']['IAS']-near[19]['values']['IAS'])/(near[17]['values']['RY_m']-near[19]['values']['RY_m'])
    tangent_mean=sum(r['speed_derivative_per_tip_y'] for r in near.values())/2
    derivative_error=abs(secant-tangent_mean)/abs(secant)
    assert derivative_error<=.01
    terminals=[read(p) for p in sorted((stage/'executions').glob('*/terminal.json'))]
    expected={('control','control',0)}|{(c['name'],task,index) for c in plan['cases'] for task,indices in
        [('candidate',[0]),('column',range(6)),('finalize',[0])] for index in indices}
    assert {(r['case'],r['task'],r['index']) for r in terminals}==expected and len(terminals)==25
    assert all(r['returncode']==0 and r['reaped'] and not r['supervisor_timeout'] for r in terminals)
    utc_gaps=[(datetime.fromisoformat(r['finished_utc'])-datetime.fromisoformat(r['started_utc'])).total_seconds()-r['seconds'] for r in terminals]
    checked(stage);assert not any(n=='openswing' or n.startswith('openswing.') for n in sys.modules)
    path=stage/'assessment.json';assert not path.exists()
    report=dict(observed_utc=now(),status='COMPLETE_STAGED_INVERSE_AUDIT_PASS',rows=rows,
        physical_checks_passed=physical,complete_tangent_columns=3*546,centered_and_one_sided_perturbations=4*3*546,
        native_votes_added=0,physical_residual_calls=0,new_solves=0,production_imports=0,
        matrix_reuse=dict(linear_solves=3,secant=secant,mean_local_derivative=tangent_mean,relative_difference=derivative_error),
        execution=dict(stages=len(terminals),max_cpu_seconds=max(r['cpu_seconds'] for r in terminals),
            max_peak_rss_kib=max(r['peak_rss_kib'] for r in terminals),all_reaped=True,
            maximum_utc_minus_monotonic_seconds=max(utc_gaps),
            note='UTC and monotonic durations differ for one stage; CPU and RSS values are actual resource receipts, not inferred from timestamps.'),
        pins=pins,plan=pin(stage/'plan.json'),assessor=pin(__file__),control=pin(stage/'control.json'),
        limitations=plan['qualifications'])
    write(path,report)
    print(json.dumps({k:report[k] for k in ('status','rows','physical_checks_passed','matrix_reuse','execution')},indent=2))


def plot(stage):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    report=read(stage/'assessment.json');rows=sorted(report['rows'],key=lambda r:r['values']['IAS'])
    plan=read(stage/'plan.json')
    fig,ax=plt.subplots(figsize=(8,5.3));fig.subplots_adjust(left=.12,right=.98,top=.9,bottom=.2)
    for key,label,color in [('coarse_values','OpenSwing nominal 20','#0072B2'),('values','OpenSwing nominal 40','#D55E00')]:
        ax.plot([r[key]['IAS'] for r in rows],[r[key]['RY_m'] for r in rows],'o-',color=color,label=label)
    ax.scatter([c['native_speed'] for c in plan['cases']],[c['native_row']['values']['RY_m'] for c in plan['cases']],
        marker='x',color='black',s=75,label='Archived ASWING',zorder=5)
    point,=[r for r in rows if r['native_speed']==17];y=point['values']['RY_m']
    ax.annotate('',xy=(point['values']['IAS'],y),xytext=(17,y),arrowprops=dict(arrowstyle='<->',color='#666666'))
    ax.text(17.3,y+.0015,f"Nominal 40 requires {point['values']['IAS']:.3f} m/s")
    ax.set(xlabel='Airspeed (m/s)',ylabel='Tip sensor Earth Y (m)',xlim=(16.7,19.3),
        title='AE-2: inverse-speed discrepancy persists on the finer grid')
    ax.grid(alpha=.25);ax.legend(loc='upper right',fontsize=9)
    fig.text(.5,.04,'Tip Y prescribed; airspeed solved. All complete tangent checks pass. No native passes added.',ha='center',fontsize=8)
    fig.savefig(stage/'inverse-speed.png',dpi=160,bbox_inches='tight');fig.savefig(stage/'inverse-speed.svg',bbox_inches='tight');plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('assess','plot'));p.add_argument('--stage',type=Path,required=True)
    a=p.parse_args();resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,)*2);resource.setrlimit(resource.RLIMIT_CPU,(15,)*2);signal.alarm(30)
    {'assess':assess,'plot':plot}[a.action](a.stage.resolve())
