"""Explicit, overlapping ST4 paper and paired-native frequency scopes."""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import tempfile

SCOPES = ('st4-mechanics', 'st4-native')
INPUTS = 'docs/validation/isae-st4-mechanics-inputs.json'
TARGETS = 'docs/validation/isae-st4-mechanics-targets.json'
EXECUTION_HELPERS = ('isae_st4_worker.py', 'verify_st4_mechanics_current.py',
    'summarize_st4_mechanics_current.py', 'isae_st4_mechanics.py', 'isae_suite_modes.py',
    'verify_sa14_defaults.py', 'verify-isae-st4-transfer-current.py', 'isae_st4_transfer.py',
    'isae_st4_spectrum.py', 'isae_acceptance.py', 'isae_suite_extra_polars.py',
    'isae_suite_polars.py', 'isae_suite_sa15.py')
PHYSICAL_CHECKS = {'base_residual', 'fresh_residual', 'zero_force', 'zero_moment',
                   'undeformed', 'rotation', 'total_mass', 'first_moment'}


def read(path): return json.loads(Path(path).read_text())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path, value): Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')
def require(value, message):
    if not value: raise ValueError('ST4 mechanics: '+message)
def finite(value): return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def plan(root, *, comparison_scopes=()):
    require(not comparison_scopes or len(comparison_scopes) == 1 and comparison_scopes[0] in SCOPES,
            'select exactly one paper or native scope; they overlap')
    if not comparison_scopes: return []
    root = Path(root); data = read(root/INPUTS); targets = read(root/TARGETS)
    require(hashlib.sha256(json.dumps(targets, sort_keys=True).encode()).hexdigest() == data['targets_sha256'], 'targets changed')
    for p, h in data['source_pins'].items(): require(sha(root/p) == h, 'source changed: '+p)
    pins = [dict(path=p, sha256=sha(root/p), bytes=(root/p).stat().st_size)
            for p in [*data['source_pins'], INPUTS, TARGETS]]
    paper = comparison_scopes[0] == SCOPES[0]
    names = list(dict.fromkeys(r['model'] for r in targets['paper'])) if paper else list(targets['direct_exports'])
    jobs = []
    for name in names:
        model = data['models'][name]
        source = ('reference/aswing-authoritative-20261108/isae-part-3-structure.pdf' if paper
                  else str(Path(model['path']).parent/'vaccum.txt'))
        rows = (sorted((r for r in targets['paper'] if r['model'] == name), key=lambda r:r['expected'])
                if paper else targets['direct_exports'][name])
        observations = []
        for i, row in enumerate(rows, 1):
            expected = row['expected'] if paper else row['eigenvalue'][1]
            tolerance = row['original_absolute_tolerance'] if paper else row['half_printed_units'][1]
            observations.append(dict(name=f'{name}:frequency:{i}', ordinal=i, expected=expected, tolerance=tolerance,
                exact_decimal_expected=row['raw_token'] if paper else row['exact_decimal_values'][1],
                exact_decimal_tolerance=str(tolerance) if paper else row['exact_decimal_half_units'][1],
                quantity='frequency_Hz' if paper else 'frequency_rad_s', kind='continuous', comparison='<=',
                source_available=True, source=source, target=deepcopy(row)))
        jobs.append(dict(id=f'ST-4/{comparison_scopes[0]}/{name}', adapter='st4', case_id='ST-4',
            comparison_scope=comparison_scopes[0], execution_route='worker', target_kind='modal',
            configuration=name, model_path=model['path'], model=deepcopy(model),
            panels=[64, 128] if paper else [128, 192], observations=observations,
            expected_outputs=len(observations), source_pins=deepcopy(pins),
            complete_family_reproduction=False, literal_input_modified=False,
            qualifications=[data['basis'], data['qualification'], *sorted({r.get('qualification','') for r in rows} - {''})]))
    require(len(jobs) == (24 if paper else 5) and sum(j['expected_outputs'] for j in jobs) == (72 if paper else 31), 'scope denominator changed')
    return jobs


def verify_reference_sources(root, job):
    canonical = next((j for j in plan(root, comparison_scopes=[job['comparison_scope']]) if j['id'] == job['id']), None)
    require(canonical is not None and all(job.get(k) == v for k,v in canonical.items()), 'job differs from canonical setup')
    return True


def reference_contract(job):
    require(job.get('adapter') == 'st4' and job.get('case_id') == 'ST-4' and job.get('comparison_scope') in SCOPES, 'wrong scope')
    rows = job['observations']
    require(len(rows) == job['expected_outputs'] == len({r['name'] for r in rows}), 'missing targets')
    return {r['name']:r for r in rows}


def state_jobs(job): return [dict(model=job['configuration'], panels=n) for n in job['panels']]


def request_for(root, job, panels):
    return dict(action='modes', mode='modes', source=(Path(root)/job['model_path']).read_text(), condition=None,
        panels=dict(default=panels, beams={'1':dict(count=panels, spacing='cosine')}),
        numerics=dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-fixed-vacuum-v1'),
        modes=dict(frame='fixed', vacuum=True, count=16, shift=[-.1,300.], method='full_shift_invert',
                   position=[0.,0.,0.], attitude=[0.,0.,0.], gravity_magnitude=0., matrices=False))


def predicted(row, pair): return max(pair, key=lambda x:abs(x-row['expected']))
def strict_pass(row, value):
    return abs(Decimal(str(value))-Decimal(row['exact_decimal_expected'])) <= Decimal(row['exact_decimal_tolerance'])


def numerical(job, states, mesh):
    valid = all(set(s.get('checks', {})) == PHYSICAL_CHECKS and
        all(finite(v) and 0 <= v < 1e-7 for v in s['checks'].values()) and
        finite(s.get('independent_transfer_relative')) and 0 <= s['independent_transfer_relative'] < 1e-7 and
        len(s.get('pencil_audits', [])) == 16 and len({a['index'] for a in s['pencil_audits']}) == 16 and
        all(finite(a.get(k)) and 0 <= a[k] < 1e-8 for a in s['pencil_audits']
            for k in ('left', 'right', 'mass_pairing', 'neutral_relative')) for s in states)
    valid &= all(finite(m.get('relative_change')) and 0 <= m['relative_change'] <= .001 and
        finite(m.get('shape_MAC')) and .99 <= m['shape_MAC'] <= 1+1e-12 and m.get('mutual_shape_assignment') is True and
        finite(m.get('discrete_relative')) and 0 <= m['discrete_relative'] < 1e-7 and
        (finite(m.get('continuous_relative')) and 0 <= m['continuous_relative'] <= .001
         if job['comparison_scope'] == 'st4-native' else m.get('continuous_relative') is None) for m in mesh)
    return bool(valid)


def validate_result_contract(job, result):
    reference_contract(job)
    if result.get('status') != 'computed': return True
    require(result.get('comparison_scope') == job['comparison_scope'] and result.get('source_pins_unchanged') is True, 'scope or provenance missing')
    states, mesh, checks = (result.get(k, []) for k in ('states', 'mesh_checks', 'reference_checks'))
    require(len(states) == result.get('solver_calls') == 2 and [s.get('job') for s in states] == state_jobs(job), 'physical states changed')
    require(len(mesh) == len(checks) == job['expected_outputs'], 'missing evidence or targets')
    for i, (row, m, c) in enumerate(zip(job['observations'], mesh, checks, strict=True)):
        require(all(c.get(k) == v for k,v in row.items()), 'reference target changed')
        scale = 2*math.pi if row['quantity'] == 'frequency_rad_s' else 1.
        pair = [s['positive_frequencies_Hz'][i]*scale for s in states]
        require(all(finite(x) and x > 0 for x in pair), 'invalid frequency')
        # Mesh change is evaluated before the units conversion, as in the reviewed study.
        change = abs(states[0]['positive_frequencies_Hz'][i]/states[1]['positive_frequencies_Hz'][i]-1)
        require(m.get('name') == row['name'] and m.get('predictions') == pair and m.get('relative_change') == change, 'mesh evidence detached from states')
        require(c.get('predicted') == predicted(row, pair), 'prediction detached from both meshes')
    require(result.get('numerical_pass') is numerical(job, states, mesh), 'numerical pass differs from evidence')
    return True


def verify_artifacts(root, job, result):
    if result.get('status') != 'computed': return []
    container = Path(result['artifact_root'])
    if not container.is_absolute(): container = Path(root)/container
    stages = [container] if (container/'adapter-result.json').is_file() else list(container.glob('st4-mechanics-*'))
    require(len(stages) == 1, 'missing or ambiguous saved evidence')
    folder = stages[0]; inner = read(folder/'plan.json'); saved = read(folder/'adapter-result.json')
    require(inner['jobs'] == state_jobs(job) and all(job.get(k) == v for k,v in inner['comparison_job'].items()) and
            inner['models'] == {job['configuration']:job['model']}, 'saved setup changed')
    for key in ('states', 'mesh_checks', 'reference_checks', 'numerical_pass', 'comparison_scope'):
        require(saved.get(key) == result.get(key), 'saved result changed: '+key)
    evidence = read(folder/'evidence.json')
    require(evidence['mesh_checks'] == result['mesh_checks'] and evidence['plan_sha256'] == sha(folder/'plan.json'), 'saved audit changed')
    files = [folder/p for p in ('plan.json', 'adapter-result.json', 'evidence.json', 'audit.json')]
    require(read(folder/'audit.json') == dict(returncode=0, terminal=True), 'audit did not finish')
    for i, state in enumerate(result['states']):
        child = folder/f'job-{i:02d}'
        require(read(child/'report.json') == state and state['plan_sha256'] == sha(folder/'plan.json'), 'child report changed')
        require(set(state['artifacts']) == {'request.json','result.json','A.npz','M.npz','shapes.npz'}, 'missing physical artifacts')
        require(read(child/'request.json') == request_for(root, job, job['panels'][i]), 'saved request changed')
        for name, digest in state['artifacts'].items():
            require(sha(child/name) == digest, 'physical artifact changed: '+name); files.append(child/name)
        receipt = folder/f'child-{i}.json'
        require(read(receipt) == dict(returncode=0, terminal=True), 'child did not finish')
        files.extend([receipt, child/'report.json'])
    return [dict(path=str(p.resolve()), bytes=p.stat().st_size, sha256=sha(p)) for p in files]


def run(root, job):
    require(all(os.environ.get(k) == '1' for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')), 'one BLAS thread required')
    resource.setrlimit(resource.RLIMIT_AS, (512*1024**2,)*2)
    resource.setrlimit(resource.RLIMIT_CPU, (15,)*2); signal.alarm(90)
    root = Path(root); verify_reference_sources(root, job)
    folder = Path(tempfile.mkdtemp(prefix='st4-mechanics-'))
    pins = {p.relative_to(root).as_posix():sha(p) for p in sorted((root/'openswing').glob('*.py'))}
    pins.update({'scripts/'+p:sha(root/'scripts'/p) for p in (*EXECUTION_HELPERS, 'isae_suite_st4_mechanics.py','run-isae-suite.py','summarize-isae-suite.py')})
    pins.update({p['path']:p['sha256'] for p in job['source_pins']})
    save(folder/'plan.json', dict(pins=pins, jobs=state_jobs(job), models={job['configuration']:job['model']},
                                comparison_job=job, pencil_gate=1e-8))
    for action, index, label in [('solve',0,'child-0'), ('solve',1,'child-1'), ('audit',None,'audit')]:
        command = [sys.executable, str(root/'scripts/isae_st4_worker.py'), action, str(folder)]
        if index is not None: command.append(str(index))
        with (folder/(label+'.stdout')).open('w') as stdout, (folder/(label+'.stderr')).open('w') as stderr:
            try:
                child = subprocess.run(command, cwd=root, stdout=stdout, stderr=stderr, timeout=30)
            except subprocess.TimeoutExpired:
                save(folder/(label+'.json'), dict(returncode=None, terminal=True, timeout=True)); raise
        save(folder/(label+'.json'), dict(returncode=child.returncode, terminal=True))
        require(child.returncode == 0, f'{label} failed; evidence at {folder}')
    states = [read(folder/f'job-{i:02d}'/'report.json') for i in range(2)]
    mesh = read(folder/'evidence.json')['mesh_checks']
    checks = []
    for row, m in zip(job['observations'], mesh, strict=True):
        value = predicted(row, m['predictions'])
        checks.append(dict(row, predicted=value, passed=strict_pass(row, value)))
    for p,h in pins.items(): require(sha(root/p) == h, 'source changed during run: '+p)
    result = dict(status='computed', comparison_scope=job['comparison_scope'], states=states, mesh_checks=mesh,
        reference_checks=checks, numerical_pass=numerical(job, states, mesh), solver_calls=2, source_pins_unchanged=True,
        complete_family_reproduction=False, literal_input_modified=False, qualifications=job['qualifications'], artifact_root=str(folder))
    validate_result_contract(job, result); save(folder/'adapter-result.json', result)
    verify_artifacts(root, job, result)
    return result


def mesh_diagnostics(jobs, results):
    return [dict(job_id=j['id'], checks=results.get(j['id'], {}).get('mesh_checks', [])) for j in jobs]
