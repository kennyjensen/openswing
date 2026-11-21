"""Bounded AE-3 full-Newton control response, checked by nonlinear perturbations.

Diagnostic use of existing complete source equations; no production/default
changes and no native-ASWING votes. All launches are serial and reaped.
"""
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/isae/ae3-control-derivative-r2-20261111'
BASE=ROOT/'artifacts/isae/ae3-current-20261111'
sys.path.insert(0,str(ROOT))
from scripts.probe_isae_ae2_cold_trace import read,write,pin,THREADS
LIMITS=dict(address_space_bytes=512*1024**2,cpu_seconds=15,wall_seconds=25)


def checked():
    plan=read(OUT/'plan.json')
    for p in plan['pins']:
        assert pin(p['path'])==p,p['path']
    return plan


def prepare():
    assert not OUT.exists()
    parent=read(BASE/'plan.json')
    # Check actual production/input witnesses, not evolving status prose.
    for p in parent['pins']:
        assert pin(p['path'])==p,p['path']
    paths={p['path'] for p in parent['pins']}
    paths.update(str(p) for p in (Path(__file__),BASE/'plan.json',BASE/'assessment.json',
        ROOT/'scripts/probe_isae_ae2_cold_trace.py',
        ROOT/'reference/aswing_doc.txt',ROOT/'docs/validation/aswing-authoritative-references.md',
        ROOT/'docs/validation/aswing-authoritative-sources.json'))
    paths.update(str(p) for p in (ROOT/'openswing').rglob('*.py'))
    catalog=read(ROOT/'docs/validation/aswing-authoritative-sources.json')
    for item in catalog['files']:
        if item['id'] not in ('drela-steady','isae-part-4'):continue
        for key,digest in (('local_pdf','sha256'),('local_text','text_sha256')):
            p=ROOT/item[key];assert pin(p)['sha256']==item[digest];paths.add(str(p))
    cases=[]
    for job in parent['jobs']:
        if job['execution_route']!='worker' or job['nominal']!=80 or job['native_operating_point'] not in (1,6):continue
        old=BASE/'jobs'/job['id'];strict=read(old/'strict-result.json')
        assert strict['numerical_pass'] and strict['status']=='computed'
        baseline=Path(strict['artifact_directory'])/'result.json'
        paths.update(str(p) for p in (old/'strict-result.json',old/'terminal.json',baseline))
        common=dict(job=job,baseline=str(baseline))
        cases.append(dict(name=f"tangent-op{job['native_operating_point']}-m80",kind='tangent',**common))
        for h in (.001,.0005):
            for sign in (1,-1):
                cases.append(dict(name=f"nonlinear-op{job['native_operating_point']}-h{h:g}-{'plus' if sign==1 else 'minus'}",
                    kind='nonlinear',increment=sign*h,**common))
    assert len(cases)==10
    write(OUT/'plan.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        previous_goal_turn='progress: actual rigid AE-3 matches native AVL on two meshes; investigate coupled derivative next',
        cases=cases,pins=[pin(p) for p in sorted(paths)],limits=LIMITS,primary_votes_added=0,
        method='Restore literal source-coupled F1=1 state. Check source-airflow zero-rate parity. Build existing full sparse Newton Jacobian with complete local and induced-field geometry terms; analytic source mechanical and circulation columns. Analytic file-control RHS; exact beam elimination or allocation-only sparse recovery. Compare with fresh full residual directions and separately reconverged F1 perturbations. No geometry-lagged tangent.',
        gates=dict(base_residual=1e-8,operator_parity=2e-10,linear_residual=1e-8,
            control_partial_relative=2e-7,directional_tangent_relative=5e-5,
            nonlinear_derivative_relative=5e-4,nonlinear_derivative_absolute=1e-8),
        limitations=['First-order local geometry differences in existing Newton Jacobian are disclosed and independently checked.',
            'This is not adoption of a general derivative implementation or an all-analytic path.',
            'No original input edits, fitted slopes, changed node arrays or thresholds.',
            'Original ASWING, modified ASWING-m and experiments remain separate.']))
    print(json.dumps(dict(cases=[c['name'] for c in cases],pins=len(paths))),flush=True)


def worker(name):
    folder=OUT/'cases'/name;plan=read(OUT/'plan.json')
    case=next(c for c in plan['cases'] if c['name']==name);job=case['job']
    start=time.monotonic();events=(folder/'phases.jsonl').open('x')
    def phase(value):
        events.write(json.dumps(dict(phase=value,wall_seconds=time.monotonic()-start,cpu_seconds=time.process_time()))+'\n');events.flush()
    phase('before_imports')
    import numpy as np
    from dataclasses import replace
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition
    from openswing.source_coupled import SourceCoupledNetwork
    from openswing.source_airflow import SourceAirflowNetwork
    from openswing.equilibrium_state import restore,identity,matching_identity
    from openswing.operating import OperatingSystem
    from scripts.isae_suite_ae3 import coefficients
    phase('imports_complete')
    assert all(os.environ.get(k)=='1' for k in THREADS)
    model=parse_asw(Path(job['source']).read_text(),beam_interpolation=job['settings']['beam_interpolation'])
    c=deepcopy(job['condition'])
    for key in ('controls','powers','circulation_modes'):c[key]={int(k):v for k,v in c[key].items()}
    condition=FlightCondition(**c);baseline=read(case['baseline'])
    net=SourceCoupledNetwork(model,job['panels'],condition,job['gravity'])
    assert not model.diagnostics and net.ne==job['expected_elements']
    assert matching_identity(identity(net),baseline['equilibrium_state']['identity'])
    x=restore(net,baseline['equilibrium_state']);assert net.nfev==0
    r0,data=net.residual(x,detail=True)
    checks=[]
    def check(key,value,gate):checks.append(dict(name=key,metric=float(value),gate=gate,passed=bool(np.isfinite(value) and value<=gate)))
    def relative(a,b):return float(np.max(abs(np.asarray(a)-b))/max(1.,np.max(abs(a)),np.max(abs(b))))
    check('base_full_residual',np.max(abs(r0)),plan['gates']['base_residual'])
    qS=.5*condition.density*condition.speed**2*model.reference[0,0]
    def mapped(packet):
        return np.array(list(coefficients(packet['distributed_aero_force'],packet['distributed_aero_moment'],
            condition.alpha,qS,model.reference[0,1],model.reference[0,2]).values()))
    base=mapped(data['aero']);check('baseline_coefficients',relative(base,mapped(baseline)),2e-10)
    phase('base_restored')
    if case['kind']=='nonlinear':
        from openswing.bridge import dispatch
        from scripts.isae_suite_ap1 import reconstruct_wrenches
        c['controls'][1]+=case['increment']
        request=dict(action='solve',mode='mounted',source=Path(job['source']).read_text(),
            panels=job['panels'],numerics=job['settings'],condition=c,gravity=job['gravity'],
            initial_state=baseline['equilibrium_state'])
        write(folder/'request.json',request)
        result=dispatch(request)
        write(folder/'result.json',result)
        updated=SourceCoupledNetwork(model,job['panels'],FlightCondition(**c),job['gravity'])
        assert matching_identity(identity(updated),result['equilibrium_state']['identity'])
        state=restore(updated,result['equilibrium_state']);assert updated.nfev==0
        residual,fresh=updated.residual(state,detail=True)
        check('fresh_full_residual',np.max(abs(residual)),1e-8)
        check('restored_coefficients',relative(mapped(fresh['aero']),mapped(result)),2e-10)
        wrench=reconstruct_wrenches(result,model.reference[1])
        check('independent_coefficients',relative(mapped(result),mapped(wrench)),2e-10)
        for key in ('force','moment'):
            a,b=np.array(result['applied_'+key]),np.array(result['support_'+key])
            check(key+'_balance',np.linalg.norm(a+b)/max(1.,np.linalg.norm(a)+np.linalg.norm(b)),1e-7)
        root=next(v['a'] for v in updated.constraints if v['kind']=='ground')
        check('root_position',np.max(abs(fresh['r'][root]-job['root_position'])),1e-10)
        check('root_frame',np.max(abs(fresh['Q'][root]-np.eye(3))),1e-10)
        assert result['converged'] and result['aerodynamic_influences']['frozen']==condition.freeze_influences
        report=dict(increment=case['increment'],coefficients=mapped(result).tolist(),
            base_coefficients=base.tolist(),maximum_displacement=result['max_displacement'])
        phase('nonlinear_reconverged')
    else:
        from scipy.sparse import save_npz
        from openswing.derivative_controls import capture_control_columns
        from openswing.sparse_newton import memory_bounded_newton_factor
        flowing=SourceAirflowNetwork(model,job['panels'],condition,job['gravity'],(),steady_trim=True)
        assert flowing.size==net.size and flowing.station_nodes[1][0].tolist()==net.station_nodes[1][0].tolist()
        flow_r,flow_data=flowing.residual(x,detail=True)
        check('airflow_operator_base_parity',relative(flow_r,r0),2e-10)
        check('airflow_operator_output_parity',relative(mapped(flow_data['aero']),base),2e-10)
        # Also compare away from equilibrium: accidental agreement at a root
        # is insufficient to establish the zero-rate residual identity.
        rng=np.random.default_rng(3101)
        directions=[rng.standard_normal(net.size) for _ in range(2)]
        for i,d in enumerate(directions):
            d/=np.max(abs(d));trial=x+1e-6*d
            check(f'airflow_off_state_parity_{i}',relative(net.residual(trial),flowing.residual(trial)),2e-10)
        del flowing
        phase('operator_parity_checked')
        matrix=net.jacobian(x,1.,_direct_geometry=True,_sparse=True)
        save_npz(folder/'jacobian.npz',matrix)
        phase('full_jacobian_ready')
        audit={};base_residual=net.residual(x)
        partial=capture_control_columns(net,x,net.residual,base_residual,controls=[1],
            response='fixed_acceleration',feedback=None,step=1e-5,report=audit)
        assert partial is not None and audit['enabled']
        partial=partial[:,0]
        def at(z,increment,detail=False):
            actual=replace(condition,controls={1:1.+increment})
            net.operating=OperatingSystem(model,actual,actual.motion(),[],net.L,net.F)
            net.aero_key=net.aero_cached=None
            return net.residual(z,detail=detail)
        h=1e-4
        numerical=(at(x,h)-at(x,-h))/(2*h)
        check('analytic_control_partial',relative(partial,numerical),2e-7)
        factor=memory_bounded_newton_factor(net,matrix)
        dx=factor.solve(-partial)
        check('full_linear_residual',relative(matrix@dx,-partial),1e-8)
        phase('linear_control_response_ready')
        for i,d in enumerate(directions+[dx/max(1.,np.max(abs(dx)))]):
            h=1e-6
            numerical=(at(x+h*d,0)-at(x-h*d,0))/(2*h)
            check(f'full_tangent_direction_{i}',relative(matrix@d,numerical),5e-5)
        derivative=[]
        for h in (1e-4,5e-5):
            _,plus=at(x+h*dx,h,True);_,minus=at(x-h*dx,-h,True)
            derivative.append((mapped(plus['aero'])-mapped(minus['aero']))/(2*h))
        check('output_step_refinement',relative(derivative[0],derivative[1]),1e-8)
        at(x,0)
        np.savez(folder/'response.npz',state=x,control_partial=partial,state_derivative=dx,
            coefficients=base,coefficient_derivative=derivative[1])
        report=dict(base_coefficients=base.tolist(),coefficient_derivative=derivative[1].tolist(),
            system_size=net.size,matrix_nonzeros=matrix.nnz,source_airflow_parity_tested=True,
            factor=factor.report,control_partial=audit,
            geometry=net.geometry_derivative_diagnostics,
            mechanical=net.mechanical_derivative_diagnostics,
            circulation=net.circulation_derivative_diagnostics,
            maximum_state_response=float(np.max(abs(dx))),residual_evaluations=net.nfev)
        phase('tangent_checks_complete')
    report.update(name=name,kind=case['kind'],speed=condition.speed,checks=checks,
        numerical_pass=all(c['passed'] for c in checks),coefficient_rows=['CX','CY','CL','Cl','Cm','Cn'],
        primary_votes_added=0)
    write(folder/'report.json',report)
    assert report['numerical_pass'],checks
    print(json.dumps({k:report[k] for k in ('name','kind','numerical_pass','base_coefficients')}
        | {k:report[k] for k in ('coefficient_derivative','coefficients') if k in report}),flush=True)


def launch(name):
    plan=checked();case=next(c for c in plan['cases'] if c['name']==name)
    folder=OUT/'cases'/name;folder.mkdir(parents=True,exist_ok=False)
    write(folder/'started.json',dict(case=case,plan=pin(OUT/'plan.json'),observed_utc=datetime.now(timezone.utc).isoformat()))
    def caps():
        resource.setrlimit(resource.RLIMIT_AS,(LIMITS['address_space_bytes'],)*2)
        resource.setrlimit(resource.RLIMIT_CPU,(LIMITS['cpu_seconds'],)*2)
    start=time.monotonic();pid=0;timeout=False
    with (folder/'stdout.log').open('x') as out,(folder/'stderr.log').open('x') as err:
        child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'worker',name],cwd=ROOT,
            env={**os.environ,**THREADS},preexec_fn=caps,stdout=out,stderr=err,start_new_session=True)
        try:
            while not pid:
                pid,status,usage=os.wait4(child.pid,os.WNOHANG)
                if pid:break
                if time.monotonic()-start>LIMITS['wall_seconds']:
                    timeout=True;os.killpg(child.pid,signal.SIGKILL);pid,status,usage=os.wait4(child.pid,0);break
                time.sleep(.05)
        finally:
            if not pid:os.killpg(child.pid,signal.SIGKILL);pid,status,usage=os.wait4(child.pid,0)
            child.returncode=os.waitstatus_to_exitcode(status)
    terminal=dict(returncode=child.returncode,process_reaped=True,supervisor_timeout=timeout,
        cpu_seconds=usage.ru_utime+usage.ru_stime,wall_seconds=time.monotonic()-start,
        peak_rss_kib=usage.ru_maxrss,limits=LIMITS,observed_utc=datetime.now(timezone.utc).isoformat())
    write(folder/'terminal.json',terminal);checked()
    write(folder/'sources-verified.json',dict(all_pins_checked=True,plan=pin(OUT/'plan.json')))
    print(json.dumps(dict(name=name,**terminal)),flush=True)
    if child.returncode:sys.exit(1)
    print((folder/'stdout.log').read_text(),end='')


if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='launch':launch(sys.argv[2])
    elif sys.argv[1]=='worker':worker(sys.argv[2])
    else:raise ValueError(sys.argv[1])
