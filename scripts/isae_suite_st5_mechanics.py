"""Repeat the declared ST-5 static mechanics scope with five cold grids."""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile

SCOPE = 'st5-mechanics'
INPUTS = 'docs/validation/isae-st5-recurring-inputs.json'
EXECUTION_HELPERS = ('isae_st5_recurring_worker.py',)
STRUCTURAL = [*range(1, 13), 19, 20]
RULE = 'add_printed_precision'


def read(path): return json.loads(Path(path).read_text())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path, value): Path(path).write_text(json.dumps(value, separators=(',', ':'), allow_nan=False)+'\n')
def require(value, message):
    if not value: raise ValueError('ST5 mechanics: '+message)
def finite(value): return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def plan(root, *, comparison_scopes=()):
    require(not comparison_scopes or list(comparison_scopes) == [SCOPE], 'select the unique declared mechanics scope')
    if not comparison_scopes: return []
    root = Path(root); inputs = read(root/INPUTS); scope = read(root/inputs['scope']); pins = {}
    def pin(path, expected=None):
        path = str(path)
        if path.startswith(str(root)+'/'): path = path[len(str(root))+1:]
        if path.startswith('.reference/'): path = 'reference/'+path[len('.reference/'):]
        if path not in pins:
            raw = (root/path).read_bytes()
            pins[path] = dict(path=path, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        require(expected is None or pins[path]['sha256'] == expected, 'changed reference: '+path)
        return pins[path]
    common = [pin(INPUTS), pin(inputs['scope'], inputs['scope_sha256'])]
    catalog = read(root/'docs/validation/aswing-authoritative-sources.json')
    common.append(pin('docs/validation/aswing-authoritative-sources.json'))
    for item in catalog['files']:
        if item['id'] in ('isae-part-3', 'drela-steady'):
            common += [pin(item['local_pdf'], item['sha256']), pin(item['local_text'], item['text_sha256'])]
    jobs = []
    require([e['case'] for e in inputs['cases']] == [e['case'] for e in scope['cases']], 'case inventory changed')
    for entry, declared in zip(inputs['cases'], scope['cases'], strict=True):
        own = [pin(entry[k], entry[k+'_sha256']) for k in ('reference_plan', 'source', 'target', 'verifier')]
        original = read(root/entry['reference_plan']); target = read(root/entry['target'])
        require(entry['reference_plan_sha256'] == declared['reference_plan_sha256'] and
                (entry['rows'], entry['required']) == (declared['rows'], declared['required']), 'declared scope changed')
        own += [pin(p['path'], p['sha256']) for p in target['source_pins']]
        nodes = {str(b['beam']): sorted({r['printed_t'] if r['exact_anchor_t'] is None else r['exact_anchor_t'] for r in b['rows']}) for b in target['beams']}
        meshes = []
        for level in range(5):
            counts = {k:len(v)-1 for k,v in nodes.items()}
            meshes.append(dict(level=level, intervals_by_beam=counts,
                panels=dict(default=max(counts.values()), beams={k:dict(nodes=v) for k,v in nodes.items()})))
            nodes = {k:sorted(v+[(a+b)/2 for a,b in zip(v[:-1],v[1:])]) for k,v in nodes.items()}
        require(meshes[:len(original['meshes'])] == original['meshes'], 'original station grid changed')
        observations = []
        for block in target['beams']:
            for row in block['rows']:
                for j in STRUCTURAL:
                    expected = float(row['raw_tokens'][j])*block['physical_multipliers'][j]
                    half = float(Decimal(10)**Decimal(Decimal(row['raw_tokens'][j]).as_tuple().exponent))/2*block['physical_multipliers'][j]
                    require(expected == row['physical'][j], 'decoded target changed')
                    observations.append(dict(name=f"b{block['beam']}:line{row['source_line']}:{target['columns'][j]['name']}",
                        beam=block['beam'], source_line=row['source_line'], column=j, quantity=target['columns'][j]['name'],
                        expected=expected, tolerance=half, raw_token=row['raw_tokens'][j],
                        physical_multiplier=block['physical_multipliers'][j], comparison='<=', kind='continuous',
                        source_available=True, source=entry['target'], relative_allowance_rule=RULE))
        require(len(observations) == entry['required'], 'native denominator changed')
        jobs.append(dict(id=f'ST-5/{SCOPE}/{entry["case"]}', adapter='st5', case_id='ST-5',
            comparison_scope=SCOPE, execution_route='worker', target_kind='static', configuration=entry['case'],
            model_path=entry['source'], reference_input=deepcopy(entry), meshes=meshes,
            physical_gates=scope['physical_gates'], convergence=scope['convergence'],
            observations=observations, expected_outputs=len(observations),
            source_pins=list({p['path']:p for p in common+own}.values()),
            complete_family_reproduction=False, literal_input_modified=False,
            qualifications=[scope['rationale'], inputs['qualification'],
                'Printed stations with known exact anchors; original unrounded nodes remain unavailable.',
                'Literal type-2 roller is distinct from the report modified in-plane link. Modal and unresolved display evidence remain separate.']))
    require(len(jobs) == 16 and sum(j['expected_outputs'] for j in jobs) == 16688, 'family scope changed')
    return jobs


def verify_reference_sources(root, job):
    canonical = next((j for j in plan(root, comparison_scopes=[SCOPE]) if j['id'] == job['id']), None)
    require(canonical is not None and all(job.get(k) == v for k,v in canonical.items()), 'job differs from canonical inputs')
    return True


def reference_contract(job):
    require(job.get('adapter') == 'st5' and job.get('case_id') == 'ST-5' and job.get('comparison_scope') == SCOPE, 'wrong scope')
    rows = job['observations']
    require(len(rows) == job['expected_outputs'] == len({r['name'] for r in rows}), 'missing or duplicate targets')
    require(all(r.get('relative_allowance_rule') == RULE for r in rows), 'printed allowance rule changed')
    return {r['name']:r for r in rows}


def state_view(packet):
    return {k:deepcopy(packet[k]) for k in ('level', 'intervals_by_beam', 'checks', 'numerical_gates_pass', 'rows')}


def mesh_checks(job, states):
    a, b = (states[i]['rows'] for i in job['convergence']['final_pair'])
    fields = list(dict.fromkeys(r['quantity'] for r in job['observations']))
    require(len(fields) == 14 and len(a) == len(b) == job['reference_input']['rows'], 'mesh rows missing')
    result = []
    for k, name in enumerate(fields):
        delta = max(abs(x['structural_deformation'][k]-y['structural_deformation'][k]) for x,y in zip(a,b,strict=True))
        envelope = max(abs(y['structural_deformation'][k]) for y in b)
        ratio = delta/envelope if envelope else (0. if delta == 0 else None)
        result.append(dict(name=name, relative_change=ratio, maximum_change=delta, fine_envelope=envelope,
            passes=ratio is not None and ratio <= job['convergence']['relative_limit']))
    return result


def physical(job, state):
    checks = state['checks']; gates = job['physical_gates']
    required = {'fresh_residual','stored_residual','force_balance','moment_balance','clamps','joint_rotation'}
    if 'roller' not in job['configuration']: required.add('joint_position')
    require(set(checks) == required, 'physical checks missing or changed')
    return all(finite(v) and 0 <= v <= (gates['fresh_and_stored_residual'] if 'residual' in k else
        gates['force_and_moment_balance'] if k in ('force_balance','moment_balance') else
        gates['clamp_and_applicable_joint_gap']) for k,v in checks.items())


def build_result(job, states):
    mesh = mesh_checks(job, states)
    rows = {(r['beam'],r['source_line']):r for r in states[0]['rows']}
    checks = []
    for obs in job['observations']:
        value = rows[obs['beam'],obs['source_line']]['values'][obs['column']]
        checks.append(dict(obs, predicted=value, passed=abs(value-obs['expected']) <= obs['tolerance']))
    return dict(status='computed', comparison_scope=SCOPE, states=states, mesh_checks=mesh, reference_checks=checks,
        numerical_pass=all(physical(job,s) for s in states) and all(m['passes'] for m in mesh),
        solver_calls=5, source_pins_unchanged=True, complete_family_reproduction=False,
        literal_input_modified=False, qualifications=job['qualifications'])


def validate_result_contract(job, result):
    reference_contract(job)
    if result.get('status') != 'computed': return True
    require(result.get('comparison_scope') == SCOPE and result.get('source_pins_unchanged') is True, 'missing provenance')
    states = result.get('states', [])
    require(len(states) == result.get('solver_calls') == 5 and [s.get('level') for s in states] == list(range(5)), 'all five states required')
    identities = list(dict.fromkeys((r['beam'],r['source_line']) for r in job['observations']))
    for state, mesh in zip(states,job['meshes'],strict=True):
        require(state['intervals_by_beam'] == mesh['intervals_by_beam'], 'mesh changed')
        require([(r['beam'],r['source_line']) for r in state['rows']] == identities, 'source rows changed')
        require(all(len(r['values']) == 28 and len(r['structural_deformation']) == 14 and
                    all(finite(v) for v in r['values']+r['structural_deformation']) for r in state['rows']), 'invalid structural fields')
        for row in state['rows']:
            v, jig = row['values'], row['jig_frame']
            phi = math.degrees(math.atan2(jig[2][1], jig[1][1]))
            psi = -math.degrees(math.asin(max(-1., min(1., jig[0][1]))))
            deformation = [v[1], v[2]-row['jig_position'][1], v[3], v[4]-phi, v[5], v[6]-psi,
                           *v[7:13], v[19], v[20]]
            require(all(math.isclose(x,y,rel_tol=2e-12,abs_tol=2e-12) for x,y in
                zip(deformation,row['structural_deformation'],strict=True)), 'deformation detached from structural fields')
        require(state['numerical_gates_pass'] is physical(job,state), 'physical pass differs from evidence')
    expected = build_result(job, states)
    for key in ('mesh_checks','reference_checks','numerical_pass'):
        require(result.get(key) == expected[key], 'changed evidence: '+key)
    require(result['numerical_pass'] is True, 'physical or convergence requirement failed')
    return True


def verify_artifacts(root, job, result):
    if result.get('status') != 'computed': return []
    container = Path(result['artifact_root'])
    stages = [container] if (container/'adapter-result.json').is_file() else list(container.glob('st5-mechanics-*'))
    require(len(stages) == 1, 'missing or ambiguous saved evidence')
    folder = stages[0]
    require(read(folder/'job.json') == {k:job[k] for k in read(folder/'job.json')}, 'saved job changed')
    saved = read(folder/'adapter-result.json')
    for key in ('states','mesh_checks','reference_checks','numerical_pass','comparison_scope'):
        require(saved.get(key) == result.get(key), 'saved result changed: '+key)
    manifest = read(folder/'artifacts.json'); files = []
    for item in manifest:
        path = folder/item['path']; raw = path.read_bytes()
        require(len(raw) == item['bytes'] and hashlib.sha256(raw).hexdigest() == item['sha256'], 'changed artifact: '+item['path'])
        files.append(dict(item,path=str(path)))
    required = {'job.json','kernel-pins.json','audit.json','audit/execution.json','adapter-result.json'}
    for i in range(5):
        required.update(f'run-{i}/{name}' for name in ('plan.json','execution.json','summary.json','timing.json'))
        required.update(f'run-{i}/level{i}/{name}' for name in ('result.json','comparison.json','fresh-fields.npz'))
        if 'roller' in job['configuration']: required.add(f'run-{i}/level{i}/joint-mechanics.json')
    require({r['path'] for r in manifest} >= required, 'missing physical artifacts')
    audit = read(folder/'audit.json')
    require(audit == dict(states=5, saved_residuals=5, saved_position_fields=5, passed=True), 'independent audit missing')
    require(read(folder/'audit/execution.json') == dict(returncode=0,terminal=True), 'audit did not finish')
    kernels = {p.relative_to(root).as_posix():sha(p) for p in (Path(root)/'openswing').glob('*.py')}
    require(read(folder/'kernel-pins.json') == kernels, 'saved production identity changed')
    for i,state in enumerate(result['states']):
        receipt = read(folder/f'run-{i}/execution.json')
        require(receipt == dict(returncode=0, terminal=True), 'unfinished child')
        plan = read(folder/f'run-{i}/plan.json')
        require(plan['kernel_pins'] == kernels and plan['meshes'] == [job['meshes'][i]] and
            plan['source_sha256'] == job['reference_input']['source_sha256'] and
            plan['target_sha256'] == job['reference_input']['target_sha256'] and
            plan['script_sha256'] == job['reference_input']['verifier_sha256'], 'saved execution plan changed')
        require(state == state_view(read(folder/f'run-{i}/level{i}/comparison.json')), 'state detached from saved recovery')
    files.append(dict(path=str(folder/'artifacts.json'), bytes=(folder/'artifacts.json').stat().st_size, sha256=sha(folder/'artifacts.json')))
    return files


def run(root, job):
    require(all(os.environ.get(k) == '1' for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')), 'one BLAS thread required')
    root = Path(root); verify_reference_sources(root, job)
    folder = Path(tempfile.mkdtemp(prefix='st5-mechanics-')); save(folder/'job.json',job)
    pins = {p.relative_to(root).as_posix():sha(p) for p in (root/'openswing').glob('*.py')}
    save(folder/'kernel-pins.json',pins)
    for action, level in [('solve',i) for i in range(5)]+[('audit',None)]:
        label = f'run-{level}' if level is not None else 'audit'
        childdir = folder/label; childdir.mkdir()
        command = [sys.executable,str(root/'scripts/isae_st5_recurring_worker.py'),action,str(folder)]
        if level is not None: command.append(str(level))
        with (childdir/'stdout.txt').open('x') as stdout, (childdir/'stderr.txt').open('x') as stderr:
            try: child = subprocess.run(command,cwd=root,stdout=stdout,stderr=stderr,timeout=30)
            except subprocess.TimeoutExpired:
                save(childdir/'execution.json',dict(returncode=None,terminal=True,timeout=True)); raise
        save(childdir/'execution.json',dict(returncode=child.returncode,terminal=True))
        require(child.returncode == 0, f'{label} failed; evidence retained at {folder}')
    for p,h in pins.items(): require(sha(root/p) == h, 'production code changed during solve')
    for p in job['source_pins']: require(sha(root/p['path']) == p['sha256'], 'reference changed during solve')
    result = build_result(job,[state_view(read(folder/f'run-{i}/level{i}/comparison.json')) for i in range(5)])
    result['artifact_root'] = str(folder)
    validate_result_contract(job,result); save(folder/'adapter-result.json',result)
    save(folder/'artifacts.json',[dict(path=str(p.relative_to(folder)),bytes=p.stat().st_size,sha256=sha(p))
        for p in sorted(folder.rglob('*')) if p.is_file()])
    return result


def mesh_diagnostics(jobs,results):
    return [dict(job_id=j['id'], checks=results.get(j['id'],{}).get('mesh_checks',[])) for j in jobs]
