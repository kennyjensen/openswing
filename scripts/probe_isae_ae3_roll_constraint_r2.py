"""Test the disclosed conditional interpretation of AE-3's % / 4 23 toggle.

No archived mask is available. One flap/no engine implies row23=net Mx if
the active-control table layout follows the retained manual. Column4 is roll
acceleration. Test this hypothesis; do not silently replace the baseline.
"""
from datetime import datetime, timezone
from copy import deepcopy
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import probe_isae_ae3_derivatives_r3 as supervisor
from scripts.probe_isae_ae2_cold_trace import read,write,pin

OUT=ROOT/'artifacts/isae/ae3-roll-constraint-r2-20261111'
BASE=ROOT/'artifacts/isae/ae3-control-derivative-r3-20261111'
supervisor.OUT=OUT
# The shared supervisor must launch this worker, not its original module.
supervisor.__file__=__file__


def prepare():
    assert not OUT.exists()
    parent=read(BASE/'plan.json')
    for p in parent['pins']:assert pin(p['path'])==p,p['path']
    cases=[]
    for previous in parent['cases']:
        case=deepcopy(previous)
        case.update(name=f"roll-free-op{case['job']['native_operating_point']}-m80",kind='roll_constraint')
        if case['job']['native_operating_point']==1:
            case['saved_result']=str(ROOT/'artifacts/isae/ae3-roll-constraint-20261111/cases/roll-free-op1-m80/result.json')
        cases.append(case)
    paths={p['path'] for p in parent['pins']}
    paths.update(str(p) for p in (Path(__file__),BASE/'plan.json',
        ROOT/'reference/aswing-authoritative-20261108/aswing-extended-user-manual.pdf',
        ROOT/'reference/aswing-authoritative-20261108/aswing-extended-user-manual.txt',
        BASE/'reference-review/extended-manual-p12.png'))
    for case in cases:
        if 'saved_result' in case:
            old=Path(case['saved_result']).parent
            paths.update(str(old/name) for name in ('result.json','report.json','terminal.json','sources-verified.json'))
    write(OUT/'plan.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        cases=cases,pins=[pin(p) for p in sorted(paths)],limits=supervisor.LIMITS,primary_votes_added=0,
        oracle_revision='Initial low-speed solve converged, but the old static test oracle included apparent-fluid loads in distributed aerodynamic coefficients. Preserve that failed report. Independently subtract the separately exported apparent strip force/couple; also verify the full fluid wrench. Low-speed state is restored, not re-solved.',
        previous_goal_turn='progress: matched actual rigid AE-3 to native AVL',
        current_progress='Full coupled fixed-acceleration control derivative now checked against nonlinear perturbations; inspect acceleration constraint next',
        method=__doc__,
        constraint=dict(variable='angular_acceleration.x',quantity='moment.x',target=0.),
        source_evidence=['Original Roll_rate.sh lines16-19: % / 4 23 / P / d.',
            'Extended user manual Fig1.5 p12 and p13: first six columns are translational/angular accelerations; active flap/engine rows precede net forces/moments.',
            'Original manual Selection and modification of constraints via keyboard: coordinates select table col,row. P applies all points.',
            'Drela steady Eqs212-213 include structural and acceleration responses coupled to force/moment constraints.'],
        qualifications=['Row23 inference assumes the depicted active-control layout also applies to the archived build; exact default mask and toggle behavior are not recovered.',
            'Zero printed angular rate does not establish zero angular acceleration.',
            'Literal model, coefficients, references, density, mesh and updated influences unchanged; source moving-airflow policy is explicit.',
            'A diagnostic only. Original mounted comparison and all 725 targets remain.']))
    print('Prepared low-speed saved-state re-audit and one high-speed roll-constraint solve.',flush=True)


def worker(name):
    import numpy as np
    from openswing.bridge import dispatch
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition
    from openswing.source_airflow import SourceAirflowNetwork
    from openswing.equilibrium_state import restore,identity,matching_identity
    from scripts.isae_suite_ae3 import coefficients
    plan=read(OUT/'plan.json');case=next(c for c in plan['cases'] if c['name']==name)
    job=case['job'];folder=OUT/'cases'/name
    c=deepcopy(job['condition'])
    for key in ('controls','powers','circulation_modes'):c[key]={int(k):v for k,v in c[key].items()}
    request=dict(action='solve',mode='mounted',source=Path(job['source']).read_text(),
        numerics=dict(beam_interpolation=job['settings']['beam_interpolation'],structural_operator='drela-moving-airflow-v1'),
        condition=c,gravity=job['gravity'],panels=job['panels'],operating_constraints=[plan['constraint']])
    write(folder/'request.json',request)
    events=(folder/'progress.jsonl').open('x')
    def progress(stage,current,total):
        if stage=='static_load':
            events.write(__import__('json').dumps(dict(stage=stage,current=current,total=total))+'\n');events.flush()
    result=read(case['saved_result']) if 'saved_result' in case else dispatch(request,progress=progress)
    write(folder/'result.json',result)
    model=parse_asw(request['source'],beam_interpolation=job['settings']['beam_interpolation'])
    assert not model.diagnostics and model.controls==[1] and not model.engine_controls
    net=SourceAirflowNetwork(model,job['panels'],FlightCondition(**c),job['gravity'],(),
        operating_constraints=[plan['constraint']],steady_trim=True)
    assert matching_identity(identity(net),result['equilibrium_state']['identity'])
    x=restore(net,result['equilibrium_state']);assert net.nfev==0
    residual,data=net.residual(x,detail=True)
    checks=[]
    def check(key,value,gate):checks.append(dict(name=key,metric=float(value),gate=gate,passed=bool(np.isfinite(value) and value<=gate)))
    qS=.5*c['density']*c['speed']**2*model.reference[0,0]
    def mapped(packet):return coefficients(packet['distributed_aero_force'],packet['distributed_aero_moment'],
        c['alpha'],qS,model.reference[0,1],model.reference[0,2])
    values=mapped(result);check('fresh_full_residual',np.max(abs(residual)),1e-8)
    forces=np.array([s['force'] for s in result['strips']]);moments=np.array([s['moment'] for s in result['strips']])
    arms=np.array([s['position'] for s in result['strips']])-model.reference[1]
    af=np.array([s['apparent_force'] for s in result['strips']]);am=np.array([s['apparent_moment'] for s in result['strips']])
    independent=dict(distributed_aero_force=(forces-af).sum(axis=0),
        distributed_aero_moment=(np.cross(arms,forces-af)+moments-am).sum(axis=0))
    check('full_fluid_force',np.max(abs(forces.sum(axis=0)-result['force']))/max(1.,qS),2e-10)
    check('full_fluid_moment',np.max(abs((np.cross(arms,forces)+moments).sum(axis=0)-result['moment']))/max(1.,qS*model.reference[0,2]),2e-10)
    for label,packet in (('fresh',data['aero']),('independent',independent)):
        other=mapped(packet);check(label+'_coefficients',max(abs(values[k]-other[k]) for k in values),2e-10)
    net_moment=(data['moment']+np.cross(data['r']-model.reference[1],data['force'])).sum(axis=0)
    check('net_roll_moment',abs(net_moment[0])/max(1.,qS*model.reference[0,2]),1e-8)
    for key in ('force','moment'):
        a,b=np.array(result['applied_'+key]),np.array(result['support_'+key])
        check(key+'_balance',np.linalg.norm(a+b)/max(1.,np.linalg.norm(a)+np.linalg.norm(b)),1e-7)
    root=next(v['a'] for v in net.constraints if v['kind']=='ground')
    check('root_position',np.max(abs(data['r'][root]-job['root_position'])),1e-10)
    check('root_frame',np.max(abs(data['Q'][root]-np.eye(3))),1e-10)
    check('angular_rates',np.max(abs(data['motion'].rates)),0.)
    original=read(case['baseline']);original_values=mapped(original)
    references={v['name']:v['expected'] for v in job['observations']}
    report=dict(name=name,values=values,fixed_acceleration=original_values,native=references,
        error_percent={k:100*abs(values[k]-references[k])/abs(references[k]) for k in values if references[k]},
        angular_acceleration_body=data['motion'].angular_acceleration.tolist(),
        operating_values=result['operating_values'],net_roll_moment=float(net_moment[0]),
        nonlinear_solves=0 if 'saved_result' in case else 1,
        checks=checks,numerical_pass=all(v['passed'] for v in checks),primary_votes_added=0)
    write(folder/'report.json',report);assert report['numerical_pass'],checks
    print(__import__('json').dumps(report),flush=True)


if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='launch':supervisor.launch(sys.argv[2])
    elif sys.argv[1]=='worker':worker(sys.argv[2])
    else:raise ValueError(sys.argv[1])
