"""Recurring ST-2 mechanics comparisons, with one bounded solve per child.

Targets and setup are frozen independently of the current production code.
The reviewed study executors retain complete requests, matrices and results;
this adapter supplies fresh plans and checks paired results without extra votes.
"""
from copy import deepcopy
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

SCOPE = 'st2-mechanics'
INPUTS = 'docs/validation/isae-st2-mechanics-inputs.json'
TARGETS = 'docs/validation/isae-st2-mechanics-scope.json'
LABELS = ('OOP1', 'OOP2', 'T1', 'OOP3', 'IP1', 'T2', 'OOP4')
EXECUTION_HELPERS = ('verify_st2_static_curves.py', 'verify_st2_modal_current.py',
    'verify_sa14_defaults.py', 'isae_suite_extra_polars.py', 'isae_suite_polars.py',
    'isae_suite_sa15.py', 'isae_st2.py', 'isae_st2_loaded_reference.py')
STATIC_GATES = dict(residual=1e-7, force_balance=1e-7, moment_balance=1e-7,
    gravity_force=1e-7, gravity_moment=1e-7, clamp_position=1e-7, clamp_rotation=1e-7)
MODAL_GATES = dict(fresh_residual=1e-9, **{k: v for k, v in STATIC_GATES.items() if k != 'residual'})


def _read(path): return json.loads(Path(path).read_text())
def _sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def _save(path, value): Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')
def _require(condition, message):
    if not condition: raise ValueError('ST2 mechanics: '+message)
def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def plan(root):
    root = Path(root); data = _read(root/INPUTS); scope = _read(root/TARGETS)
    records = {k: scope[k] for k in ('static_targets', 'modal_targets')}
    digest = hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()
    _require(digest == data['targets_sha256'], 'reference values changed; source review required')
    for path, digest in data['source_pins'].items():
        _require(_sha(root/path) == digest, 'reference source changed: '+path)
    sources = [dict(path=p, sha256=h, bytes=(root/p).stat().st_size) for p, h in data['source_pins'].items()]
    sources += [dict(path=p, sha256=_sha(root/p), bytes=(root/p).stat().st_size) for p in (INPUTS, TARGETS)]
    jobs = []
    for kind, configurations in (('static', data['static']), ('modal', data['modal'])):
        for name, config in configurations.items():
            model_path = (next(p for p in data['source_pins'] if p.endswith(f"/Pazy_wing_{config['kind']}_bench.asw"))
                          if kind == 'static' else config['source'])
            targets = [r for r in records[kind+'_targets'] if
                       (r['curve'] in config['curves'] if kind == 'static' else r['orientation'] == name)]
            masses = config['masses'] if kind == 'static' else [None]
            for mass in masses:
                rows = [r for r in targets if kind == 'modal' or r['mass_kg'] == mass]
                observations = [dict(name=r['id'], expected=r['expected'] if kind == 'static' else r['expected_Hz'],
                    tolerance=r['original_absolute_tolerance'] if kind == 'static' else 0.,
                    quantity=r['quantity'] if kind == 'static' else 'frequency_Hz',
                    source=r['source'], original_tokens=r['original_tokens'],
                    comparison='<=', kind='continuous') for r in rows]
                jobs.append(dict(id=f'ST-2/mechanics/{kind}/{name}'+(f'/mass-{mass:g}' if mass is not None else ''),
                    adapter='st2', case_id='ST-2', comparison_scope=SCOPE, target_kind=kind,
                    configuration=name, config=deepcopy(config), mass=mass,
                    model_path=model_path,
                    refine=kind == 'modal' or mass == masses[-1], observations=observations,
                    expected_outputs=len(observations), source_pins=deepcopy(sources), execution_route='worker',
                    complete_family_reproduction=False, literal_input_modified=kind == 'static',
                    qualifications=[data['basis'], 'Original 490-slot archive remains a separate selectable scope.']))
    _require(len(jobs) == 43 and sum(j['expected_outputs'] for j in jobs) == 91, 'mechanics scope changed')
    return jobs


def verify_reference_sources(root, job):
    expected = next((j for j in plan(root) if j['id'] == job.get('id')), None)
    _require(expected is not None and all(job.get(k) == v for k, v in expected.items()), 'job differs from canonical setup')
    return True


def reference_contract(job):
    _require(job.get('comparison_scope') == SCOPE and job.get('case_id') == 'ST-2', 'wrong scope')
    rows = job['observations']
    _require(len(rows) == len({r['name'] for r in rows}) == job['expected_outputs'], 'missing or duplicate target')
    return {r['name']: r for r in rows}


def state_jobs(job):
    if job['target_kind'] == 'modal':
        return [dict(orientation=job['configuration'], nominal=n, nodes=n+2) for n in (78, 158)]
    c = job['config']; masses = [0.] if job['mass'] == 0 else [0., job['mass']]
    jobs = [dict(case=job['configuration'], mass_kg=m, nominal=c['nominal'], scope='curve') for m in masses]
    if job['refine']:
        n = 79 if c['kind'] == 'bending' else 78
        jobs += [dict(case=job['configuration'], mass_kg=m, nominal=n, scope='refinement') for m in masses]
    return jobs


def static_evidence(job, states):
    def observables(scope):
        selected = [s for s in states if s['job']['scope'] == scope]
        zero = next(s['observable'] for s in selected if s['job']['mass_kg'] == 0.)
        loaded = next(s['observable'] for s in selected if s['job']['mass_kg'] == job['mass'])
        return dict(displacement_m=-(loaded['z_m']-zero['z_m']), twist_deg=-loaded['twist_asw_deg'])
    values = observables('curve'); mesh = []
    if job['refine']:
        fine = observables('refinement')
        mesh = [dict(name=k, coarse=values[k], fine=fine[k],
                     relative_change=abs(values[k]-fine[k])/max(abs(fine[k]), 1e-8)) for k in values]
    return values, mesh


def modal_evidence(job, states, folder):
    # Called only after both solver children have exited: their scientific
    # libraries never coexist with the parent's NumPy/SciPy allocation.
    import numpy as np
    from scipy.optimize import linear_sum_assignment
    from scipy.spatial.transform import Rotation, Slerp
    from isae_st2_loaded_reference import section_inertia
    shapes = []
    for i in range(2):
        with np.load(folder/f'job-{i}'/'shapes.npz') as z:
            shapes.append({k: z[k] for k in z.files})
    coarse, fine = shapes; grid = np.linspace(0., .55, 501)
    frame = np.array([[1,0,0],[0,0,-1],[0,1,0]]) if job['configuration'] == 'upright' else np.eye(3)
    rotations = Slerp(fine['stations'], Rotation.from_matrix(fine['rotations']))(grid).as_matrix() @ frame
    factors = np.array([np.linalg.cholesky(section_inertia(s,q,1.23)) for s,q in zip(grid, rotations)])
    factors[[0,-1]] *= np.sqrt(.5)
    def sample(shape):
        return np.asarray([np.column_stack([np.interp(grid,shape['stations'],v[:,i]) for i in range(6)])
                           for v in shape['shapes']])
    a = np.einsum('ngi,gij->ngj', sample(fine), factors).reshape(7,-1)
    b = np.einsum('ngi,gij->ngj', sample(coarse), factors).reshape(7,-1)
    scores = abs(a.conj() @ b.T)**2 / np.outer(np.sum(abs(a)**2,axis=1), np.sum(abs(b)**2,axis=1))
    rr, cc = linear_sum_assignment(-scores)
    _require(np.array_equal(rr,np.arange(7)), 'incomplete mode assignment')
    sampled = sample(fine)
    u = np.einsum('nji,mnj->mni', rotations, sampled[:,:,:3])
    rot = np.einsum('nji,mnj->mni', rotations, sampled[:,:,3:])
    inn = 4.2793e-4 + np.maximum(0.,(grid-.52)/.03)*(.0041-4.2793e-4)
    w = np.ones(len(grid)); w[[0,-1]] = .5
    activity = np.stack((np.sum(w*(.6787*abs(u[:,:,2])**2+6.9567e-5*abs(rot[:,:,0])**2),axis=1),
        np.sum(w*(.6787*abs(u[:,:,0])**2+inn*abs(rot[:,:,2])**2),axis=1),
        np.sum(w*(6.9567e-5+inn)*abs(rot[:,:,1])**2,axis=1),
        np.sum(w*.6787*abs(u[:,:,1])**2,axis=1)),axis=1)
    fractions = activity/activity.sum(axis=1)[:,None]; orders = {}; result = []
    for i in range(7):
        family = ('OOP','IP','T','A')[np.argmax(fractions[i])]; orders[family] = orders.get(family,0)+1
        ca, fi = (s['frequencies'][i]['frequency_Hz'] for s in states)
        result.append(dict(name=job['observations'][i]['name'], coarse_Hz=ca, fine_Hz=fi,
            relative_change=abs(ca/fi-1), shape_MAC=float(scores[i,cc[i]]), coarse_ordinal=int(cc[i])+1,
            label=family+str(orders[family]), activity_fractions=dict(zip(('OOP','IP','T','A'),fractions[i].tolist()))))
    return result


def validate_result_contract(job, result):
    contract = reference_contract(job); checks = result.get('reference_checks', [])
    if result.get('status') != 'computed':
        _require(result.get('reference_match') is not True and result.get('numerical_pass') is not True
                 and result.get('numerical_passed') is not True, 'failed job claims success')
        _require(len(checks) <= len(contract) and len({r.get('name') for r in checks}) == len(checks),
                 'invalid partial output set')
        for row in checks:
            _require(row.get('name') in contract and all(row.get(k) == v for k,v in contract[row['name']].items()),
                     'failed job changed reference metadata')
        return True
    _require(result.get('complete_family_reproduction') is False and result.get('source_pins_unchanged') is True,
             'missing source or scope qualification')
    _require(result.get('comparison_scope') == SCOPE and result.get('literal_input_modified') == job['literal_input_modified'],
             'setup qualification changed')
    _require(len(checks) == len(contract) and {r['name'] for r in checks} == set(contract), 'incomplete observations')
    for row in checks:
        _require(all(row.get(k) == v for k,v in contract[row['name']].items()), 'reference value or precision changed')
    states = result.get('states', []); expected = state_jobs(job)
    _require(len(states) == len(expected) == result.get('solver_calls') and
             all(s.get('job') == e for s,e in zip(states,expected)), 'missing or changed physical state')
    limits = STATIC_GATES if job['target_kind'] == 'static' else MODAL_GATES
    valid = True
    for state in states:
        values = state.get('checks', {})
        _require(set(values) == set(limits), 'missing numerical check')
        valid &= all(_finite(values[k]) and 0 <= values[k] < limit for k,limit in limits.items())
    mesh = result.get('mesh_checks', [])
    if job['target_kind'] == 'static':
        values, expected_mesh = static_evidence(job, states)
        _require(mesh == expected_mesh, 'mesh check differs from physical observables')
        _require(all(r.get('predicted') == values[r['quantity']] for r in checks), 'prediction differs from measured state')
    else:
        _require(len(mesh) == 7 and [r['name'] for r in mesh] == [r['name'] for r in checks], 'missing mode correspondence')
        for state in states:
            audit = state.get('pencil_audits', [])
            _require(len(audit) == 20 and len({r['index'] for r in audit}) == 20, 'missing eigen-equations')
            valid &= all(_finite(r.get(k)) and 0 <= r[k] < 1e-8 for r in audit for k in ('right','left','neutral_relative'))
            _require(len(state.get('frequencies', [])) == 7, 'incomplete positive spectrum')
        for i, (row, m) in enumerate(zip(checks, mesh)):
            pair = [s['frequencies'][i]['frequency_Hz'] for s in states]
            _require(all(_finite(f) and f > 0 for f in pair), 'invalid modal frequency')
            _require(m.get('coarse_Hz') == pair[0] and m.get('fine_Hz') == pair[1] and
                     m.get('relative_change') == abs(pair[0]/pair[1]-1), 'modal evidence detached from frequencies')
            _require(row.get('predicted') == max(pair,key=lambda f:abs(f-row['expected'])), 'favorable mesh substituted')
            family = LABELS[i].rstrip('1234'); fractions = m.get('activity_fractions', {})
            _require(set(fractions) == {'OOP','IP','T','A'} and all(_finite(v) and 0 <= v <= 1 for v in fractions.values())
                     and abs(sum(fractions.values())-1) < 1e-12, 'invalid mode activity')
            valid &= m.get('label') == LABELS[i] and fractions[family] > .55 and m.get('coarse_ordinal') == i+1
            valid &= _finite(m.get('shape_MAC')) and .99 < m['shape_MAC'] <= 1+1e-12
    valid &= all(_finite(r.get('relative_change')) and 0 <= r['relative_change'] < .01 for r in mesh)
    _require(result.get('numerical_pass') is bool(valid), 'numerical pass differs from evidence')
    return True


def verify_artifacts(root, job, result):
    """Authenticate saved evidence for a summary; never import the solver."""
    if result.get('status') != 'computed':
        return []
    container = Path(result['artifact_root'])
    if not container.is_absolute(): container = Path(root)/container
    stages = [container] if (container/'adapter-result.json').is_file() else list(container.glob('st2-mechanics-*'))
    _require(len(stages) == 1, 'missing or ambiguous state artifact directory')
    stage = stages[0]; inner = _read(stage/'plan.json')
    _require(inner['jobs'] == state_jobs(job) and inner['cases'] == {job['configuration']: job['config']},
             'artifact setup differs from canonical job')
    static = job['target_kind'] == 'static'
    expected_files = {'request.json','result.json'} if static else {
        'request.json','result.json','A.npz','M.npz','spectrum.json','shapes.npz'}
    files = [stage/'plan.json', stage/'adapter-result.json']
    saved = _read(stage/'adapter-result.json')
    for key in ('states','mesh_checks','reference_checks','numerical_pass','comparison_scope','literal_input_modified'):
        _require(saved.get(key) == result.get(key), 'adapter evidence differs from saved result: '+key)
    for i, state in enumerate(result['states']):
        child = stage/(f'job-{i:02d}' if static else f'job-{i}')
        _require(state['plan_sha256'] == _sha(stage/'plan.json') and _read(child/'report.json') == state,
                 'child report or plan changed')
        _require(set(state['artifacts']) == expected_files, 'incomplete physical artifacts')
        for name, digest in state['artifacts'].items():
            _require(_sha(child/name) == digest, 'physical artifact changed: '+name)
            files.append(child/name)
        files.append(child/'report.json')
    return [dict(path=str(p.resolve()), bytes=p.stat().st_size, sha256=_sha(p)) for p in files]


def run(root, job):
    _require(all(os.environ.get(k) == '1' for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')),
             'one BLAS thread required')
    resource.setrlimit(resource.RLIMIT_AS, (512*1024**2, 512*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (15,15)); signal.alarm(115)
    root = Path(root); verify_reference_sources(root, job); data = _read(root/INPUTS)
    # Each child independently applies the 512 MiB / 15 CPU s / 25 wall s caps.
    # The parent only imports scientific libraries after all children exit.
    folder = Path(tempfile.mkdtemp(prefix='st2-mechanics-'))
    pins = {p.relative_to(root).as_posix(): _sha(p) for p in sorted((root/'openswing').glob('*.py'))}
    helper_names = (*EXECUTION_HELPERS, 'isae_suite_st2.py', 'isae_suite_st2_modal.py',
                    'isae_st2_archive.py', 'isae_suite_st2_mechanics.py')
    pins.update({'scripts/'+p: _sha(root/'scripts'/p) for p in helper_names})
    pins.update({p['path']: p['sha256'] for p in job['source_pins']})
    static = job['target_kind'] == 'static'
    inner = dict(pins=pins, cases={job['configuration']: job['config']}, jobs=state_jobs(job),
                 modal_survey=data['modal_survey'], gates=data['gates'])
    _save(folder/'plan.json', inner); states = []
    script = 'verify_st2_static_curves.py' if static else 'verify_st2_modal_current.py'
    for i in range(len(inner['jobs'])):
        with (folder/f'child-{i}.stdout').open('w') as stdout, (folder/f'child-{i}.stderr').open('w') as stderr:
            completed = subprocess.run([sys.executable, str(root/'scripts'/script), 'run', '--output', str(folder),
                                        '--index', str(i)], cwd=root, stdout=stdout, stderr=stderr, timeout=30)
        _require(completed.returncode == 0, f'bounded state {i} failed; retained at {folder}')
        path = folder/(f'job-{i:02d}' if static else f'job-{i}')/'report.json'
        state = _read(path)
        _require(state['plan_sha256'] == _sha(folder/'plan.json'), 'child plan changed')
        for name, digest in state['artifacts'].items():
            _require(_sha(path.parent/name) == digest, 'child artifact changed: '+name)
        states.append(state)
    mesh = static_evidence(job, states)[1] if static else modal_evidence(job, states, folder)
    values = static_evidence(job, states)[0] if static else None
    checks = []
    for i, row in enumerate(job['observations']):
        predicted = values[row['quantity']] if static else max(
            (s['frequencies'][i]['frequency_Hz'] for s in states), key=lambda f:abs(f-row['expected']))
        checks.append(dict(**row, predicted=predicted, passed=abs(predicted-row['expected']) <= row['tolerance']))
    for path, digest in pins.items(): _require(_sha(root/path) == digest, 'code or source changed during solve')
    limits = STATIC_GATES if static else MODAL_GATES
    numerical = all(_finite(s['checks'][k]) and 0 <= s['checks'][k] < v for s in states for k,v in limits.items())
    numerical &= all(0 <= m['relative_change'] < .01 for m in mesh)
    if not static:
        numerical &= all(0 <= a[k] < 1e-8 for s in states for a in s['pencil_audits'] for k in ('right','left','neutral_relative'))
        numerical &= all(m['label'] == LABELS[i] and m['activity_fractions'][LABELS[i].rstrip('1234')] > .55
                         and m['coarse_ordinal'] == i+1 and .99 < m['shape_MAC'] <= 1+1e-12 for i,m in enumerate(mesh))
    result = dict(status='computed', comparison_scope=SCOPE, numerical_pass=bool(numerical),
        reference_checks=checks, states=states, mesh_checks=mesh, solver_calls=len(states),
        source_pins_unchanged=True, complete_family_reproduction=False,
        literal_input_modified=job['literal_input_modified'], artifact_root=str(folder),
        qualifications=job['qualifications'], peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    validate_result_contract(job,result); _save(folder/'adapter-result.json',result)
    return result


def mesh_diagnostics(jobs, results):
    return [dict(job_id=j['id'], status='CHECKED_WITHIN_JOB' if results.get(j['id'],{}).get('status') == 'computed'
                 else 'UNAVAILABLE', checks=results.get(j['id'],{}).get('mesh_checks',[])) for j in jobs]
