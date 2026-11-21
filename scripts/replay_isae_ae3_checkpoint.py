"""Complete one AE-3 auxiliary comparison from an authenticated equilibrium.

The base solve and its restored checks remain in their original artifact.
Only exact, current-code coefficient checkpoints with identical physical
settings are accepted. No equilibrium solve starts in the auxiliary worker.
"""
import argparse
from copy import deepcopy
from datetime import datetime,timezone
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from scripts import isae_suite_ae3 as adapter
from scripts.replay_isae_ae3_bounded import LIMITS,THREADS,limits,read,write,runner
from scripts.isae_acceptance import apply_reference_acceptance

AUXILIARY={'native_derivatives','native_mass_properties','native_normalized_rates'}
PAIR_FIELDS=('coordinate_id','native_operating_point','source','model_path','literal_model_sha256',
    'nominal','panels','settings','condition','gravity','literal_reference','literal_weight_rows',
    'mandatory_stations','root_position','expected_elements','expected_nodes','numerical_gates',
    'source_pins','kernel_pins')


def validate_pair(job,base_job,base):
    if job['target_kind'] not in AUXILIARY or base_job['target_kind']!='native_coefficients':
        raise ValueError('Checkpoint reuse requires a native coefficient base and a native auxiliary target.')
    if any(job.get(key)!=base_job.get(key) for key in PAIR_FIELDS):
        raise ValueError('Checkpoint physical settings or source identity differ from the target.')
    if base.get('id')!=base_job['id'] or base.get('status')!='computed':
        raise ValueError('Checkpoint base is not a completed matching coefficient job.')
    adapter.validate_result_contract(base_job,base)
    return True


def validate_receipt(job,result):
    """Source-only audit, including the exact inherited solve/check evidence."""
    evidence=result.get('equilibrium_reuse',{})
    pins=evidence.get('pins',[])
    if not pins or not adapter._stable(pins):raise ValueError('Checkpoint evidence or execution source changed.')
    base=read(evidence['base_result']);base_job=read(evidence['base_request'])['job']
    validate_pair(job,base_job,base)
    if not adapter._stable(base['artifact_files']):raise ValueError('Authenticated base artifact changed.')
    if result['physical_checks']!=base['physical_checks']:
        raise ValueError('Inherited physical checks changed.')
    if evidence.get('worker_operations')!=dict(cold_solves=0,restores=1,observable_batches=1):
        raise ValueError('Checkpoint worker operation accounting changed.')
    if evidence.get('inherited_operations')!=base['operations'] or evidence.get('prior_partial_observables_reused') is not False:
        raise ValueError('Checkpoint operation provenance changed.')
    if evidence.get('restore_without_evaluation') is not True or evidence.get('matching_operator_identity') is not True:
        raise ValueError('Missing exact restore evidence.')
    adapter.validate_result_contract(job,result)
    return True


def load_input(packet):
    suite=runner()
    if not suite.stable_code(ROOT,packet['code_sha256']) or not adapter._stable(packet['execution_pins']):
        raise ValueError('Code changed after checkpoint planning.')
    job=packet['job'];adapter.verify_reference_sources(ROOT,job)
    base_job=read(packet['base_request'])['job'];base=read(packet['base_result'])
    adapter.verify_reference_sources(ROOT,base_job)
    validate_pair(job,base_job,base)
    if not adapter._stable(packet['base_pins']) or not adapter._stable(base['artifact_files']):
        raise ValueError('Base evidence changed before reuse.')
    if not adapter._stable(job['kernel_pins']):raise ValueError('Kernel changed before checkpoint reuse.')
    return job,base_job,base


def load_worker_input(request_path,expected_digest):
    raw=Path(request_path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected_digest:
        raise ValueError('Supervisor-authenticated checkpoint request changed.')
    packet=json.loads(raw);job=packet['job'];base_job=packet['verified_base_job'];base=packet['verified_base_result']
    validate_pair(job,base_job,base)
    if adapter._pin(packet['checkpoint_path'])!=packet['checkpoint_pin']:
        raise ValueError('Equilibrium checkpoint changed after source audit.')
    if adapter._pin(job['source'])['sha256']!=job['literal_model_sha256']:
        raise ValueError('Physical model changed after source audit.')
    return packet,job,base_job,base


def worker(request_path,output_path,request_digest):
    folder=Path(output_path).parent
    started=time.monotonic();cpu=time.process_time();phases=(folder/'phases.jsonl').open('x')
    def phase(name):
        phases.write(json.dumps(dict(phase=name,wall_seconds=time.monotonic()-started,cpu_seconds=time.process_time()-cpu))+'\n');phases.flush()
    try:
        phase('authenticated_request')
        packet,job,base_job,base=load_worker_input(request_path,request_digest)
        phase('imports')
        from openswing.asw import parse_asw
        from openswing.aero import FlightCondition
        from openswing.source_coupled import SourceCoupledNetwork
        from openswing.equilibrium_state import restore,identity,matching_identity,warm_start_recipe
        from scripts.isae_ae3_observables import complete_observables
        phase('restore')
        model=parse_asw(Path(job['source']).read_text(),beam_interpolation=job['settings']['beam_interpolation'])
        condition=deepcopy(job['condition'])
        for key in ('controls','powers','circulation_modes'):condition[key]={int(k):v for k,v in condition[key].items()}
        raw=read(packet['checkpoint_path']);saved=raw['equilibrium_state']
        recipe=warm_start_recipe(model,job['panels'],saved)
        network=SourceCoupledNetwork(model,job['panels'],FlightCondition(**condition),job['gravity'],mesh_recipe=recipe)
        if not matching_identity(identity(network),saved['identity']):raise ValueError('Checkpoint operator or node layout changed.')
        state=restore(network,saved)
        if network.nfev!=0:raise ValueError('Checkpoint restore unexpectedly evaluated the source.')
        values={check['name']:check['predicted'] for check in base['reference_checks']}
        phase('observables')
        report=complete_observables(network,state,None,values,derivatives=job['target_kind']=='native_derivatives')
        adapter.validate_observable_report(job,report,values);write(folder/'observable-report.json',report)
        phase('result_validation')
        checks=adapter._checks(job,report['values'])
        evidence=dict(base_result=packet['base_result'],base_request=packet['base_request'],
            pins=[*packet['base_pins'],*packet['execution_pins'],adapter._pin(request_path),packet['checkpoint_pin']],inherited_operations=base['operations'],
            worker_operations=dict(cold_solves=0,restores=1,observable_batches=1),
            restore_without_evaluation=True,matching_operator_identity=True,prior_partial_observables_reused=False,
            scope='Operations/physical_calls count unique completed phases in the evidence chain, including the inherited cold solve and restored checks; this worker starts no solve. All auxiliary calculations and gates are freshly evaluated.',
            source_audit='Supervisor verifies canonical jobs, kernel and artifact hashes before and after the bounded worker. The worker verifies the immutable request digest, checkpoint bytes and literal model before restoring.')
        write(folder/'equilibrium-reuse.json',evidence)
        result=dict(id=job['id'],case_id='AE-3',adapter='ae3',status='pending_source_audit',numerical_pass=False,
            reference_match=False,reference_checks=checks,
            physical_checks=deepcopy(base['physical_checks']),physical_calls=3,operations=deepcopy(job['expected_operations']),
            source_pins_unchanged=False,kernel_pins_unchanged=False,
            observable_report=report,equilibrium_reuse=evidence,error=None,artifact_directory=str(folder),
            artifact_files=[adapter._pin(folder/name) for name in ('observable-report.json','equilibrium-reuse.json')],
            historical_settings_recovered=False,complete_family_reproduction=False,unknown_setup=job['unknown_setup'],
            qualifications=job['qualifications'],reference_scope=job['reference_scope'])
        phase('complete')
        result['worker_timing']=dict(cpu_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-started,
            peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        write(output_path,result)
    except Exception as exc:
        write(output_path,dict(status='error',numerical_pass=False,reference_match=False,reference_checks=[],
            error=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc()))
    finally:phases.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--base-run',type=Path)
    parser.add_argument('--job-pattern')
    parser.add_argument('--worker',nargs=3)
    args=parser.parse_args()
    if args.worker:return worker(*args.worker)
    if args.output_dir is None or args.base_run is None or not args.job_pattern:
        parser.error('--output-dir, --base-run and --job-pattern are required')
    directory=args.output_dir.resolve();directory.mkdir(parents=True,exist_ok=True)
    suite=runner();jobs=adapter.plan(ROOT);pins=suite.code_pins(ROOT,['ae3'])
    pins['scripts/replay_isae_ae3_bounded.py']=suite.digest(ROOT/'scripts/replay_isae_ae3_bounded.py')
    execution_pins=[adapter._pin(__file__)]
    if (directory/'plan.json').exists():
        plan=read(directory/'plan.json')
        if any(plan[k]!=v for k,v in dict(jobs=jobs,code_sha256=pins,limits=LIMITS,execution_pins=execution_pins).items()):
            raise ValueError('Checkpoint completion plan changed; use a new directory.')
    else:
        plan=dict(observed_utc=datetime.now(timezone.utc).isoformat(),jobs=jobs,code_sha256=pins,
            limits=LIMITS,execution_pins=execution_pins,previous_goal_turn='progress: full native adapter implemented and 67 tests passed; bounded replay exposed verified auxiliary-work and import timeouts.')
        write(directory/'plan.json',plan)
    selected=[j for j in jobs if j['target_kind'] in AUXILIARY and fnmatch.fnmatchcase(j['id'],args.job_pattern)]
    if len(selected)!=1:raise ValueError('Select exactly one auxiliary job per invocation.')
    job=selected[0]
    base_job=next(j for j in jobs if j['target_kind']=='native_coefficients' and j['nominal']==job['nominal'] and j['coordinate_id']==job['coordinate_id'])
    base_folder=args.base_run.resolve()/'jobs'/base_job['id']
    base_request,base_result=base_folder/'request.json',base_folder/'strict-result.json'
    packet=dict(job=job,code_sha256=pins,execution_pins=execution_pins,
        base_request=str(base_request),base_result=str(base_result),base_pins=[adapter._pin(p) for p in (base_request,base_result)])
    _,verified_base_job,verified_base=load_input(packet)
    checkpoint=Path(verified_base['artifact_directory'])/'result.json'
    packet.update(verified_base_job=verified_base_job,verified_base_result=verified_base,
        checkpoint_path=str(checkpoint),checkpoint_pin=adapter._pin(checkpoint))
    folder=directory/'jobs'/job['id'];folder.mkdir(parents=True,exist_ok=False)
    request,output=folder/'request.json',folder/'worker-result.json';write(request,packet)
    request_digest=adapter._pin(request)['sha256']
    before=time.monotonic();started=datetime.now(timezone.utc).isoformat()
    with (folder/'stdout.log').open('wb') as out,(folder/'stderr.log').open('wb') as err:
        child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker',str(request),str(output),request_digest],
            cwd=ROOT,env={**os.environ,**THREADS},stdout=out,stderr=err,start_new_session=True,preexec_fn=limits)
        timed=False
        try:child.wait(timeout=LIMITS['wall_seconds'])
        except subprocess.TimeoutExpired:
            timed=True
            try:os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            child.wait()
        finally:
            if child.poll() is None:
                try:os.killpg(child.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                child.wait()
    result=read(output) if output.exists() and child.returncode==0 else dict(status='timeout' if timed else 'process_error',
        numerical_pass=False,reference_match=False,reference_checks=[],exit_code=child.returncode)
    if not suite.stable_code(ROOT,pins) or not adapter._stable(execution_pins):raise ValueError('Code changed during checkpoint worker.')
    if result['status']=='pending_source_audit':
        load_input(packet)
        if adapter._pin(request)['sha256']!=request_digest:raise ValueError('Worker request changed during execution.')
        result.update(status='computed',numerical_pass=True,source_pins_unchanged=True,kernel_pins_unchanged=True,
            reference_match=all(c['passed'] for c in result['reference_checks']))
        validate_receipt(job,result)
        result=suite.checked_result(job,result)
    elif result['status']=='computed':raise ValueError('Worker bypassed the supervisor source audit.')
    write(folder/'strict-result.json',result)
    write(folder/'result.json',apply_reference_acceptance(result,relative_tolerance=.05))
    terminal=dict(status=result['status'],subprocess_started=True,process_reaped=True,exit_code=child.returncode,
        timed_out=timed,started_utc=started,ended_utc=datetime.now(timezone.utc).isoformat(),
        wall_seconds=time.monotonic()-before,limits=LIMITS,cold_solves_started=0)
    write(folder/'terminal.json',terminal)
    print(json.dumps(dict(job=job['id'],**terminal)),flush=True)


if __name__=='__main__':main()
