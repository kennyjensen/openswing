"""Finish AE-1 bookkeeping after SIGALRM only when every physical check survived.

No solve, residual evaluation, production import, retry or timeout relaxation.
Original worker termination and raw evidence remain immutable.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import resource
import signal
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import isae_suite_ae1 as adapter
from scripts.isae_acceptance import apply_reference_acceptance
from scripts.replay_isae_ae1_bounded import checked_result

RAW_FILES=('job.json','request.json','preflight.json','operations.json',
           'result.json','restored-result.json','physical-checks.json')


def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):
    with Path(path).open('x') as stream:
        json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')
def require(ok,why):
    if not ok:raise ValueError('AE1 saved finalization: '+why)


def validate_saved(job, packet):
    """Bind the adapter's complete check set to both original saved snapshots."""
    cold,fresh=packet['result.json'],packet['restored-result.json']
    checks=packet['physical-checks.json'];preflight=packet['preflight.json']
    require(packet['job.json']==job,'raw job differs')
    request=dict(action='solve',mode='mounted',source=Path(job['source']).read_text(),
        panels=job['panels'],numerics=job['settings'],condition=job['condition'],gravity=job['gravity'])
    require(packet['request.json']==request,'request differs')
    require(packet['operations.json']==job['expected_operations']==dict(cold_solves=1,fresh_residuals=1,retries=0),'operations incomplete')
    require(adapter.validate_physical_checks(job,checks),'physical checks failed')
    by_name={c['name']:c for c in checks}
    require(cold['converged'] and fresh['converged'],'unconverged snapshot')
    require(fresh['residual']==by_name['fresh_full_residual']['metric'] and cold['residual']<=adapter.GATES['residual'],'residual detached from snapshot')
    require(by_name['same_operator_identity']['actual']==cold['equilibrium_state']['identity'],'operator identity differs')
    require(cold['equilibrium_state']['identity']['model_sha256']==job['literal_model_sha256'],'model differs')
    require(preflight['source_sha256']==job['literal_model_sha256'] and preflight['active_weight_count']==0
        and preflight['raw_weight_rows']==job['literal_weight_rows'] and .52 in preflight['stations'],'preflight differs')
    require(preflight['nodes']==cold['structural_nodes']==job['expected_nodes'] and
        preflight['elements']==cold['structural_elements']==job['expected_elements'],'counts differ')
    for label,snapshot in [('cold',cold),('restored',fresh)]:
        require(adapter._setup_evidence(snapshot)==by_name[label+'_operating_setup']['actual'],'operating setup detached')
    for name in ('force','moment'):
        c=by_name[name+'_balance']
        require(c['applied']==cold['applied_'+name] and c['support']==cold['support_'+name],'balance detached')
    # Literal reference origin [0,0,0] is independently pinned by the canonical source.
    wrenches=adapter.reconstruct_wrenches(cold,[0.,0.,0.])
    for name in ('distributed_aero_force','distributed_aero_moment','force','moment'):
        c=by_name['independent_'+name]
        require(c['reported']==cold[name] and c['reconstructed']==wrenches[name],'strip wrench detached')
    sensors=[{k:s[k] for k in ('index','position_earth','axes_earth','elevation')} for s in cold['sensors']]
    tips=[node for node in cold['nodes'] if node['beam']==1 and node['t']==.55]
    c=by_name['independent_sensor_geometry']
    require(c['reported']==sensors and c['tip_nodes']==tips,'sensor geometry detached')
    values=adapter.sensor_values(sensors)
    c=by_name['restored_sensor_parity']
    require(c['reported']==values and c['restored']==adapter.sensor_values(fresh['sensors']),'restored sensors detached')
    root=next(n for n in cold['nodes'] if n['beam']==1 and n['t']==.0001)
    require(by_name['root_clamp_position']['reported']==root['position'] and
        by_name['root_clamp_frame']['reported']==sum(root['rotation'],[]),'root clamp detached')
    return values,checks


def prepare(folder):
    require(read(folder/'terminal.json')['returncode']==-signal.SIGALRM,'not the inspected elapsed-timer termination')
    require(not (folder/'strict-result.json').exists(),'already finalized')
    raw=list((folder/'raw').iterdir());require(len(raw)==1,'ambiguous raw directory');raw=raw[0]
    require(set(p.name for p in raw.iterdir())==set(RAW_FILES),'missing or unexpected raw evidence')
    stage=folder/'finalization';stage.mkdir()
    paths=[folder/'job.json',folder/'terminal.json',*(raw/n for n in RAW_FILES),Path(__file__)]
    save(stage/'plan.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),raw=str(raw),
        reason='SIGALRM after cold result, restored result and all29 physical checks were written; complete bookkeeping without another solve.',
        pins={str(p):sha(p) for p in paths},physical_calls=0,production_imports=0))
    print('Saved immutable finalization plan.')


def run(folder):
    stage=folder/'finalization';plan=read(stage/'plan.json');raw=Path(plan['raw'])
    for path,digest in plan['pins'].items():require(sha(path)==digest,'evidence changed: '+path)
    job=read(folder/'job.json');adapter.verify_reference_sources(ROOT,job)
    require(adapter._stable(job['source_pins']) and adapter._stable(job['kernel_pins']),'source or kernel changed')
    packet={name:read(raw/name) for name in RAW_FILES}
    values,physical=validate_saved(job,packet);checks=adapter._checks(job,values)
    result=dict(id=job['id'],case_id='AE-1',adapter='ae1',status='computed',numerical_pass=True,
        reference_match=all(c['passed'] for c in checks),reference_checks=checks,physical_checks=physical,
        physical_calls=2,operations=packet['operations.json'],source_pins_unchanged=True,kernel_pins_unchanged=True,
        error=None,artifact_directory=str(raw),artifact_files=[adapter._pin(raw/n) for n in RAW_FILES],
        historical_settings_recovered=False,complete_family_reproduction=False,unknown_setup=job['unknown_setup'],
        qualifications=job['qualifications'],reference_scope=job['reference_scope'],
        saved_finalization=dict(plan=str(stage/'plan.json'),original_terminal=str(folder/'terminal.json'),
            original_returncode=-signal.SIGALRM,new_physical_calls=0,production_imports=0))
    adapter.validate_result_contract(job,result)
    view=apply_reference_acceptance(checked_result(job,result),relative_tolerance=.05)
    require(view['status']=='computed','common contract failed')
    require(not any(n=='openswing' or n.startswith('openswing.') for n in sys.modules),'production module imported')
    for path,digest in plan['pins'].items():require(sha(path)==digest,'evidence changed during audit')
    save(folder/'strict-result.json',result);save(folder/'accepted-result.json',view)
    receipt=dict(id=job['id'],status='computed',physical_checks_passed=29,physical_checks_required=29,
        passed=sum(c['passed'] for c in view['reference_checks']),required=6,
        wall_seconds=None,cpu_seconds=None,peak_rss_kib=None,numerical_timing_unavailable=True,
        recovered_from_complete_saved_checks=True,original_worker_returncode=-signal.SIGALRM,
        new_physical_calls=0)
    save(folder/'receipt.json',receipt)
    save(stage/'verification.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),passed=True,
        source_and_kernel_pins_unchanged=True,physical_calls=0,production_imports=0,
        pins={**plan['pins'],str(stage/'plan.json'):sha(stage/'plan.json'),
              **{str(folder/n):sha(folder/n) for n in ('strict-result.json','accepted-result.json','receipt.json')}}))
    print(json.dumps(receipt))


def verify_completed(folder):
    record=read(folder/'finalization/verification.json')
    require(record['passed'] and record['physical_calls']==record['production_imports']==0,'bad finalization receipt')
    for path,digest in record['pins'].items():require(sha(path)==digest,'finalized evidence changed: '+path)
    require(read(folder/'terminal.json')['returncode']==-signal.SIGALRM,'original termination was rewritten')
    return True


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','run','verify'])
    p.add_argument('folder',type=Path);a=p.parse_args()
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,)*2)
    resource.setrlimit(resource.RLIMIT_CPU,(15,)*2);signal.alarm(25)
    {'prepare':prepare,'run':run,'verify':verify_completed}[a.action](a.folder.resolve())
