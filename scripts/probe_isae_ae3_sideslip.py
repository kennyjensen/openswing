"""Separate AE-3 sideslip input influences and verify the full derivative.

Conditional sibling-control, roll-acceleration base; original equations and
primary comparisons stay unchanged. Lagged-field partials are diagnostics,
not proposed production replacements. Every launch is one bounded serial job.
"""
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from scripts import isae_suite_ae3 as adapter
from scripts.replay_isae_ae3_bounded import LIMITS,THREADS,limits,read,write

OUT=ROOT/'artifacts/isae/ae3-sideslip-20261111'
PREVIOUS=ROOT/'artifacts/isae/ae3-mm-setup-r2-20261111'


def prepare():
    assert not OUT.exists()
    parent=read(PREVIOUS/'plan.json');assert adapter._stable(parent['pins'])
    case=deepcopy(next(c for c in parent['cases'] if c['name']=='sibling-lift-roll-free-op1-m80'))
    paths={Path(p['path']) for p in parent['pins']}
    paths.update((Path(__file__),PREVIOUS/'plan.json',PREVIOUS/'cases'/case['name']/'result.json'))
    catalog=read(ROOT/'docs/validation/aswing-authoritative-sources.json')
    for item in catalog['files']:
        if item['id'] not in ('drela-steady','isae-part-4'):continue
        for key,digest in (('local_text','text_sha256'),('local_pdf','sha256')):
            p=ROOT/item[key];assert adapter._pin(p)['sha256']==item[digest];paths.add(p)
    case['previous_mm_result']=str(PREVIOUS/'cases'/case['name']/'result.json')
    cases=[dict(case,name='tangent-op1-m80',kind='tangent')]
    for magnitude in (1e-4,5e-5):
        for sign in (1,-1):
            cases.append(dict(case,name=f"beta-{sign*magnitude:+.0e}-op1-m80",kind='nonlinear',increment=sign*magnitude))
    OUT.mkdir()
    write(OUT/'plan.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),cases=cases,
          pins=[adapter._pin(p) for p in sorted(paths)],limits=LIMITS,primary_votes_added=0,
          previous_goal_turn='progress: full native-MM diagnostics isolate low-speed CLb as the sole derivative mismatch under the disclosed sibling/roll-constraint setup.',
          references=['Drela steady Eq.1: relative freestream and sideslip sign.',
                      'Eqs.155-157 and Fig.16 pp.32-33: wind-aligned receivers and trailing vorticity.',
                      'Section4.6 pp.36-37: influence dependence and lagging in Newton iteration.',
                      'Sections8.3-8.6 pp.50-54: implicit response and fixed stability-axis force mapping.'],
          gates=dict(base_residual=1e-8,parity=2e-10,reciprocal_condition=1e-10,
                     full_tangent_direction=5e-5,input_refinement=2e-7,linear_residual=1e-8,
                     output_refinement=1e-8,nonlinear_derivative_absolute=1e-8,
                     nonlinear_derivative_relative=5e-4),
          qualifications=['Fixed acceleration means the actual solved nonzero acceleration at the conditional base.',
                          'The full physical state tangent is unchanged for all input-partial decompositions.',
                          'Lagged influence/receiver partials isolate contributions; they are not a recovered native-MM convention.',
                          'No source model, physics, native target, numerical gate or primary denominator changes.']))
    print(json.dumps(dict(cases=[c['name'] for c in cases],limits=LIMITS)),flush=True)


def worker(request_path,digest):
    folder=Path(request_path).parent;started=time.monotonic();cpu=time.process_time()
    phases=(folder/'phases.jsonl').open('x')
    def phase(name):
        phases.write(json.dumps(dict(phase=name,wall_seconds=time.monotonic()-started,
                                    cpu_seconds=time.process_time()-cpu))+'\n');phases.flush()
    try:
        raw=Path(request_path).read_bytes();assert hashlib.sha256(raw).hexdigest()==digest
        packet=json.loads(raw);case=packet['case']
        assert adapter._stable(packet['input_pins'])
        phase('imports')
        import numpy as np
        import resource
        from dataclasses import asdict
        from openswing.asw import parse_asw
        from openswing.aero import FlightCondition
        from openswing.source_airflow import SourceAirflowNetwork
        from openswing.equilibrium_state import restore,identity,matching_identity,capture
        from openswing.derivatives import perturb_condition
        from openswing.operating import OperatingSystem

        request=read(Path(case['folder'])/'request.json');saved=read(Path(case['folder'])/'result.json')
        model=parse_asw(request['source'],beam_interpolation='drela-segspl-v1')
        assert not model.diagnostics
        c=deepcopy(request['condition'])
        for key in ('controls','powers','circulation_modes'):c[key]={int(k):v for k,v in c[key].items()}
        original=SourceAirflowNetwork(model,request['panels'],FlightCondition(**c),request['gravity'],(),
                                     operating_constraints=request['operating_constraints'],steady_trim=True)
        assert matching_identity(identity(original),saved['equilibrium_state']['identity'])
        state=restore(original,saved['equilibrium_state']);assert original.nfev==0
        checks=[]
        def check(name,metric,gate):
            row=dict(name=name,metric=float(metric),gate=float(gate),passed=bool(np.isfinite(metric) and metric<=gate))
            checks.append(row)
            if not row['passed']:raise ValueError(str(row))
        def relative(a,b):
            a,b=np.asarray(a),np.asarray(b)
            return np.max(abs(a-b),initial=0)/max(1.,np.max(abs(b),initial=0))
        residual,data=original.residual(state,detail=True)
        check('constrained_base_residual',np.max(abs(residual)),1e-8)
        condition,motion,values=original.operating.apply(state[original.operating_start:])
        assert np.any(motion.angular_acceleration) and not np.any(motion.rates)
        net=SourceAirflowNetwork(model,request['panels'],condition,request['gravity'],(),steady_trim=True)
        assert net.operating_start==net.size==original.operating_start
        assert all(np.array_equal(net.station_nodes[k][0],v[0]) for k,v in original.station_nodes.items())
        x=state[:original.operating_start].copy()
        r0,base=net.residual(x,detail=True)
        check('fixed_base_residual',np.max(abs(r0)),1e-8)
        check('physical_residual_transfer',relative(r0,residual[:net.size]),2e-10)
        del original,state,residual,data
        qS=.5*condition.density*condition.speed**2*model.reference[0,0]
        def mapped(a):
            return np.array(list(adapter.coefficients(a['distributed_aero_force'],a['distributed_aero_moment'],
                condition.alpha,qS,model.reference[0,1],model.reference[0,2]).values()))
        base_coefficients=mapped(base['aero'])
        check('saved_base_outputs',relative(base_coefficients,mapped(saved)),2e-10)
        def at(z,increment=0.,detail=False):
            actual=perturb_condition(condition,'beta',increment,model)
            net.operating=OperatingSystem(model,actual,actual.motion(),[],net.L,net.F)
            net.aero_key=net.aero_cached=None
            return net.residual(z,detail=detail)
        phase('base_restored')

        if case['kind']=='nonlinear':
            from openswing.bridge import dispatch
            # Capture a new, checked fixed-acceleration state. Never alter the
            # identity or constraint metadata of the original saved packet.
            seed=capture(net,x,residual=float(np.max(abs(r0))))
            actual=perturb_condition(condition,'beta',case['increment'],model)
            solve=dict(action='solve',mode='mounted',source=request['source'],panels=request['panels'],
                       numerics=request['numerics'],condition=asdict(actual),gravity=request['gravity'],
                       tolerance=1e-11,initial_state=seed)
            write(folder/'solve-request.json',solve)
            result=dispatch(solve);write(folder/'solve-result.json',result)
            fresh=SourceAirflowNetwork(model,request['panels'],actual,request['gravity'],(),steady_trim=True)
            assert matching_identity(identity(fresh),result['equilibrium_state']['identity'])
            z=restore(fresh,result['equilibrium_state']);assert fresh.nfev==0
            rr,dd=fresh.residual(z,detail=True)
            check('perturbed_full_residual',np.max(abs(rr)),1e-11)
            check('restored_outputs',relative(mapped(dd['aero']),mapped(result)),2e-10)
            root=next(v['a'] for v in fresh.constraints if v['kind']=='ground')
            check('root_position',np.max(abs(dd['r'][root]-case['job']['root_position'])),1e-10)
            check('root_frame',np.max(abs(dd['Q'][root]-np.eye(3))),1e-10)
            check('preserved_acceleration',relative(dd['motion'].angular_acceleration,motion.angular_acceleration),0.)
            assert result['converged']
            report=dict(increment=case['increment'],coefficients=mapped(result).tolist(),
                        nonlinear_solves=1,equilibrium_initialization=result['equilibrium_initialization'])
        else:
            from scipy.sparse import hstack,save_npz
            from openswing.geometry_tangent import geometry_columns
            from openswing.sparse_newton import memory_bounded_newton_factor
            from openswing.structured_static import IterationFields
            at(x)
            matrix=net.jacobian(x,1.,_direct_geometry=True,_sparse=True)
            fourth,geometry=geometry_columns(net,lambda d:at(x+d),lambda d:x+d,np.maximum(1.,abs(x)),
                step=1e-5,factor=1.,difference_order=4,_nodewise_state=True,_direct_vortex=True,
                _direct_volume=True,_direct_geometry=True,_direct_structural=False)
            matrix=hstack([fourth,matrix[:,6*net.nn:]],format='csc');del fourth
            matrix.sum_duplicates();matrix.eliminate_zeros();matrix.sort_indices()
            norms=np.maximum(np.sqrt(np.asarray(matrix.power(2).sum(axis=0))).ravel(),1e-30)
            scaled=matrix.toarray();scaled/=norms
            singular=np.linalg.svd(scaled,compute_uv=False);del scaled
            reciprocal=float(singular[-1]/singular[0]);check('reciprocal_condition_gate',1e-10/max(reciprocal,1e-300),1.)
            rng=np.random.default_rng(3112)
            for i in range(2):
                d=rng.standard_normal(net.size);d/=max(abs(d))
                check(f'full_tangent_direction_{i}',relative(matrix@d,(at(x+1e-6*d)-at(x-1e-6*d))/2e-6),5e-5)
            at(x);factor=memory_bounded_newton_factor(net,matrix)
            phase('full_tangent_factored')
            class FieldPartial(IterationFields):
                def __init__(self,mode):
                    super().__init__();self.mode=mode
                def fixed_geometry(self,key,compute):
                    if self.phase!='capture' and key=='lifting_geometry':return self.fixed_values[key]
                    return super().fixed_geometry(key,compute)
                def get(self,key,compute):
                    if self.phase!='capture' and self.mode=='fixed_receivers':return compute()
                    return super().get(key,compute)
            outputs={};saved_arrays=dict(state=x,base_coefficients=base_coefficients)
            for mode in ('full','fixed_receivers','fixed_influences'):
                if mode!='full':
                    fields=FieldPartial(mode);net.iteration_fields=fields
                    r,dd=at(x,detail=True)
                    check(mode+'_base_residual_parity',relative(r,r0),2e-10)
                    check(mode+'_base_output_parity',relative(mapped(dd['aero']),base_coefficients),2e-10)
                    fields.phase='diagnostic'
                partials=[];directs=[]
                for h in (1e-4,5e-5):
                    samples=[at(x,m*h,True) for m in (1.,-1.,2.,-2.)]
                    partials.append((8*(samples[0][0]-samples[1][0])-(samples[2][0]-samples[3][0]))/(12*h))
                    f=[mapped(v[1]['aero']) for v in samples]
                    directs.append((8*(f[0]-f[1])-(f[2]-f[3]))/(12*h))
                check(mode+'_input_refinement',relative(*partials),2e-7)
                check(mode+'_direct_refinement',relative(*directs),1e-8)
                net.iteration_fields=None;at(x)
                dx=factor.solve(-partials[1])
                check(mode+'_linear_residual',relative(matrix@dx,-partials[1]),1e-8)
                terms={}
                for group in ('state','geometry','circulation'):
                    direction=dx.copy()
                    if group=='geometry':direction[6*net.nn:]=0.
                    if group=='circulation':direction[:net.gamma_start]=0.;direction[net.operating_start:]=0.
                    estimates=[]
                    for h in (1e-4,5e-5):
                        _,plus=at(x+h*direction,detail=True);_,minus=at(x-h*direction,detail=True)
                        estimates.append((mapped(plus['aero'])-mapped(minus['aero']))/(2*h))
                    check(mode+'_'+group+'_refinement',relative(*estimates),1e-8)
                    terms[group]=estimates[1]
                check(mode+'_state_decomposition',relative(terms['state'],terms['geometry']+terms['circulation']),1e-8)
                total=directs[1]+terms['state']
                outputs[mode]=dict(total=total.tolist(),direct=directs[1].tolist(),
                                  **{k:v.tolist() for k,v in terms.items()})
                saved_arrays.update({mode+'_partial':partials[1],mode+'_response':dx})
            at(x)
            previous=read(case['previous_mm_result'])['observable_report']['values']
            check('previous_full_beta_derivative',relative(outputs['full']['total'],
                  [previous[n+'b'] for n in adapter.NAMES]),1e-8)
            save_npz(folder/'tangent.npz',matrix)
            np.savez(folder/'responses.npz',**saved_arrays)
            report=dict(decomposition=outputs,nonlinear_solves=0,reciprocal_condition=reciprocal,
                        system_size=net.size,matrix_nonzeros=matrix.nnz,factorization_count=1,
                        response_columns=3,factor=factor.report,geometry=geometry)
        phase('complete')
        report.update(status='pending_source_audit',name=case['name'],kind=case['kind'],checks=checks,
                      numerical_pass=False,primary_votes_added=0,coefficient_rows=list(adapter.NAMES),
                      base_coefficients=base_coefficients.tolist(),angular_acceleration=motion.angular_acceleration.tolist(),
                      timing=dict(wall_seconds=time.monotonic()-started,cpu_seconds=time.process_time()-cpu,
                                  peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
        write(folder/'raw-result.json',report)
    except Exception as exc:
        write(folder/'raw-result.json',dict(status='error',numerical_pass=False,
              error=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc()))
    finally:phases.close()


def launch(name):
    plan=read(OUT/'plan.json');assert adapter._stable(plan['pins'])
    case=next(c for c in plan['cases'] if c['name']==name)
    folder=OUT/'cases'/name;folder.mkdir(parents=True,exist_ok=False)
    request=folder/'request.json'
    write(request,dict(case=case,input_pins=[adapter._pin(Path(case['folder'])/p) for p in ('request.json','result.json')]
                      +[adapter._pin(case['previous_mm_result'])]))
    digest=adapter._pin(request)['sha256'];started=time.monotonic()
    with (folder/'stdout.log').open('wb') as out,(folder/'stderr.log').open('wb') as err:
        child=subprocess.Popen([sys.executable,__file__,'worker',str(request),digest],cwd=ROOT,
                env={**os.environ,**THREADS},stdout=out,stderr=err,start_new_session=True,preexec_fn=limits)
        timeout=False
        try:child.wait(timeout=LIMITS['wall_seconds'])
        except subprocess.TimeoutExpired:
            timeout=True;os.killpg(child.pid,signal.SIGKILL);child.wait()
        finally:
            if child.poll() is None:os.killpg(child.pid,signal.SIGKILL);child.wait()
    terminal=dict(observed_utc=datetime.now(timezone.utc).isoformat(),returncode=child.returncode,
                  process_reaped=True,timed_out=timeout,wall_seconds=time.monotonic()-started,limits=LIMITS)
    write(folder/'terminal.json',terminal)
    assert adapter._stable(plan['pins']) and adapter._pin(request)['sha256']==digest
    result=read(folder/'raw-result.json') if (folder/'raw-result.json').exists() else {}
    if child.returncode==0 and result.get('status')=='pending_source_audit':
        assert result['checks'] and all(c['passed'] for c in result['checks'])
        result.update(status='computed',numerical_pass=True)
        write(folder/'result.json',result)
        write(folder/'sources-verified.json',dict(before_and_after=True,plan=adapter._pin(OUT/'plan.json'),
                                               request=adapter._pin(request)))
    print(json.dumps(dict(name=name,**terminal,status=result.get('status','no_result'),
                         checks=len(result.get('checks',[])),error=result.get('error'),
                         CLb={k:v['total'][2] for k,v in result.get('decomposition',{}).items()})),flush=True)


if __name__=='__main__':
    action=sys.argv[1]
    if action=='prepare':prepare()
    elif action=='launch':launch(sys.argv[2])
    elif action=='worker':worker(*sys.argv[2:])
    else:raise ValueError(action)
