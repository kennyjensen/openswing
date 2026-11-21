"""Original AE4 modal inventory and an opt-in, declared alpha-zero sweep.

Planning/blocker validation use only stdlib. All eighteen original modal tables
remain required in the historical ledger. The supplemental executable scope
repeats every row of the undeformed alpha-zero table on two declared meshes.
It does not recover historical setup or cover sensor/time histories.
"""
from copy import deepcopy
from decimal import Decimal
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
MANIFEST_SHA256 = '813347a3bd9fcbd029a1ec86e0c3141f82422af26f33ebde7c2f732a16bf27f6'
FAMILY = '4 - Aeroelasticity/AE - Aeroelastic Cases/AE-4-D Pazy Wing - Flutter boundaries'
PREFIX = '.reference/isae-validation/' + REVISION + '/' + FAMILY + '/'
SCOPE = 'ae4-undeformed-alpha0'
TABLE = '2-Flutter_Undeformed/alpha_0_eig.txt'
GRIDS = (40, 80)
TABLES = tuple('1-Flutter_Deformed/' + n + '.txt' for n in (
    'alpha0', 'alpha0_25eig', 'alpha0eig', 'alpha_0_25_eig', 'alpha_0_5_eig', 'alpha_0_5eig',
    'alpha_0_eig', 'alpha_1_eig', 'alpha_2_5_eig', 'alpha_2_eig', 'alpha_3_eig', 'alpha_4_eig',
    'alpha_5_eig', 'alpha_6_eig', 'alpha_7_eig', 'divergence_alpha_0_eig')) + (
    TABLE, '2-Flutter_Undeformed/divergence_alpha_0_eig.txt')
BLOCKS = dict(
    HISTORICAL_SETUP_UNAUTHENTICATED='Historical startup, mesh and aerodynamic flags are unavailable; declared alternatives are separate.',
    COUPLED_BASE_UNREVIEWED='This deformed operating sweep has no reviewed base-state and modal-branch reconstruction.',
    NO_EXACT_DRIVER_PAIRING='No retained script in this directory writes this exact modal filename.',
    DIVERGENCE_BRANCH_UNREVIEWED='This separate divergence driver needs its own operating-index and real-pole branch mapping.',
    UNKNOWN_INITIAL_POINT='Native operating point 1 precedes every explicitly commanded IAS; no speed is invented.')
QUALIFICATIONS = [
    'Original ASWING modal exports only; experiments are not targets. Every printed real and imaginary component remains required.',
    'The historical ledger and supplemental declared scope reuse target cells; meshes and duplicate archive files are not independent evidence.',
    'The declared undeformed alpha-zero scope uses fixed frame, solid wall, density1.23, PG0, lag, current influences and pointwise circulation; historical settings remain unauthenticated.',
    'Literal plus-stack mapping is index=IAS+1, unlike the author plotting helper. Initial point1 and absent terminal modal point110 remain unresolved.',
    'Original NN4/shift0+200i is a local search. Complete positive-frequency sets use frequency order, with independently certified real poles retained separately; native modal identity and real-pole pairing remain unresolved.',
    'Nominal cosine40/80 retain the material boundary; original I40 spacing/count bookkeeping is unknown. Mesh changes are reported separately from native accuracy.',
    'This adapter covers modal tables only. Sensor histories, LCO time histories, all other operating branches and whole-family validation remain unfinished.',
]
OPERATIONS = dict(cold_bridge_calls=1, modal_solves=1, retries=0)


def require(ok, message):
    if not ok:
        raise ValueError('AE4: ' + message)


def finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def pin(root, path):
    path = Path(path)
    absolute = Path(root)/path
    with absolute.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return dict(path=str(path), bytes=absolute.stat().st_size, sha256=digest)


def helper(root=ROOT):
    spec = importlib.util.spec_from_file_location('_ae4_suite_anchor', Path(root)/'scripts/verify-isae-ae4-wall-modes.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def decode_table(text):
    lines = text.splitlines()
    require(len(lines) > 3 and lines[2].split() == ['#', 'Op.Point', 'Eigenvalue'], 'modal header changed')
    rows = []
    for line, raw in enumerate(lines, 1):
        if not raw.strip() or raw.lstrip().startswith('#'):
            continue
        tokens = raw.split()
        require(len(tokens) == 3 and tokens[0].isdigit() and int(tokens[0]) > 0, 'modal row grammar changed')
        numbers = [Decimal(t.replace('D', 'E')) for t in tokens[1:]]
        require(all(n.is_finite() for n in numbers), 'nonfinite modal target')
        rows.append(dict(line=line, tokens=tokens, values=[int(tokens[0]), *map(float, numbers)]))
    require(bool(rows), 'empty modal table')
    return rows


def _table_record(root, relative, manifest=None):
    root = Path(root)
    require(relative in TABLES, 'unknown modal table')
    manifest_path = '.reference/isae-validation/manifest.json'
    mp = pin(root, manifest_path)
    require(mp['sha256'] == MANIFEST_SHA256, 'reference manifest changed')
    manifest = manifest or json.loads((root/manifest_path).read_text())
    require(manifest['revision'] == REVISION, 'reference revision changed')
    def original(path):
        p = pin(root, path)
        key = path.split(REVISION+'/', 1)[1]
        require(all(p[k] == manifest['files'][key][k] for k in ('bytes', 'sha256')), 'original bytes changed: '+path)
        return p
    table = PREFIX+relative
    parent = str(Path(table).parent)
    model = parent+'/Pazy_wing.asw'
    sources = [mp, original(table), original(model)]
    drivers = []
    for candidate in sorted((root/parent).glob('*.sh')):
        commands = [l.strip().lower() for l in candidate.read_text().splitlines() if l.strip()]
        if any(a == 'ww' and b == Path(relative).name.lower() for a,b in zip(commands, commands[1:])):
            require('aswing pazy_wing <<eof' in commands[1], 'driver invokes a different model')
            drivers.append(candidate.relative_to(root).as_posix())
    require(len(drivers) <= 1, 'ambiguous exact modal writer')
    sources += [original(p) for p in drivers]
    block = ('NO_EXACT_DRIVER_PAIRING' if not drivers else
             'DIVERGENCE_BRANCH_UNREVIEWED' if 'divergence' in relative else
             'HISTORICAL_SETUP_UNAUTHENTICATED' if relative == TABLE else 'COUPLED_BASE_UNREVIEWED')
    rows = decode_table((root/table).read_text())
    same = [p for p in TABLES if p != relative and
            manifest['files'][FAMILY+'/'+p]['sha256'] == sources[1]['sha256']]
    return dict(id='AE-4:historical:'+relative, case_id='AE-4', adapter='ae4',
        comparison_scope='historical-modal-exports', target_kind='native_modal',
        execution_route='unsupported', blocker_code=block, unsupported_reason=BLOCKS[block],
        table_relative=relative, model_path=model, table_path=table, driver_path=drivers[0] if drivers else None,
        source_pins=sources, table_sha256=sources[1]['sha256'], identical_archive_files=same,
        reference_rows=rows, expected_outputs=2*len(rows), required_components=['real', 'imaginary'],
        expected_operations=dict(cold_bridge_calls=0, modal_solves=0, retries=0),
        qualifications=QUALIFICATIONS.copy(), complete_family_reproduction=False,
        historical_settings_authenticated=False, native_modal_identity_verified=False)


def _sensor_pin(root, manifest=None):
    sensor = PREFIX+'2-Flutter_Undeformed/aswing_alpha_0.txt'
    manifest = manifest or json.loads((Path(root)/'.reference/isae-validation/manifest.json').read_text())
    sp = pin(root, sensor)
    require(all(sp[k] == manifest['files'][FAMILY+'/2-Flutter_Undeformed/aswing_alpha_0.txt'][k]
                for k in ('bytes','sha256')), 'sensor witness changed')
    return sp


def _declared(root, original, index, nominal, *, sensor=None, anchor=None):
    require(type(index) is int and 1 <= index <= 109 and type(nominal) is int and nominal in GRIDS, 'declared point or mesh changed')
    h = anchor or helper(root)
    rows = [r for r in original['reference_rows'] if r['values'][0] == index]
    require(bool(rows), 'missing native operating point')
    if index > 1:
        require(rows == h.declared_targets((Path(root)/original['driver_path']).read_text(),
                    original['reference_rows'], index-1), 'literal stack binding changed')
    sp = sensor or _sensor_pin(root)
    result = deepcopy({k:v for k,v in original.items() if k!='reference_rows'})
    result.update(id=f'AE-4:declared:op{index:03d}:n{nominal}', comparison_scope=SCOPE,
        execution_route='worker' if index > 1 else 'unsupported',
        blocker_code=None if index > 1 else 'UNKNOWN_INITIAL_POINT',
        unsupported_reason=None if index > 1 else BLOCKS['UNKNOWN_INITIAL_POINT'],
        reference_rows=deepcopy(rows), expected_outputs=2*len(rows), native_index=index,
        IAS=index-1 if index > 1 else None, nominal=nominal,
        expected_operations=OPERATIONS.copy() if index > 1 else dict(cold_bridge_calls=0, modal_solves=0, retries=0),
        suggested_address_cap_mib=512 if nominal == 40 else 768,
        mesh_relative_gate=.001, source_pins=original['source_pins']+[sp])
    return result


def plan(root, *, comparison_scopes=()):
    require(len(set(comparison_scopes)) == len(comparison_scopes) and set(comparison_scopes) <= {SCOPE}, 'unknown comparison scope')
    folder = Path(root)/PREFIX
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob('*.txt') if 'Op.Point' in p.read_text()[:250]}
    require(actual == set(TABLES), 'unaccounted original modal table')
    manifest = json.loads((Path(root)/'.reference/isae-validation/manifest.json').read_text())
    jobs = [_table_record(root, relative, manifest) for relative in TABLES]
    require(sum(j['expected_outputs'] for j in jobs) == 9480, 'original modal denominator changed')
    if SCOPE in comparison_scopes:
        original = next(j for j in jobs if j['table_relative'] == TABLE)
        sensor, anchor = _sensor_pin(root, manifest), helper(root)
        jobs += [_declared(root, original, index, nominal, sensor=sensor, anchor=anchor)
                 for index in range(1, 110) for nominal in GRIDS]
    return jobs


def validate_record_contract(job, root=ROOT):
    original = _table_record(root, job.get('table_relative'))
    if job.get('comparison_scope') == SCOPE:
        require(original['table_relative'] == TABLE, 'declared scope changed source table')
        original = _declared(root, original, job.get('native_index'), job.get('nominal'))
    require(all(job.get(k) == v for k,v in original.items()), 'source, coordinates, required targets or qualifications changed')
    return True


def reference_contract(job):
    contract = {}
    for row in job['reference_rows']:
        for k, name in enumerate(('real','imaginary'), 1):
            expected = Decimal(row['tokens'][k].replace('D','E'))
            half = Decimal(10)**expected.as_tuple().exponent/2
            contract[f"line{row['line']}:{name}"] = dict(expected=float(expected), tolerance=float(half),
                exact_decimal_expected=str(expected), exact_decimal_tolerance=str(half), unit='1/s')
    require(len(contract) == job['expected_outputs'], 'target count changed')
    return contract


def reference_checks(job, roots=None, classifications=None):
    rows = helper().compare_roots([dict(eigenvalue=r) for r in roots], job['reference_rows'],
                                  classifications=classifications) if roots is not None else []
    values = {r['original']['line']:r['actual'] for r in rows if r['status']=='computed'}
    checks = []
    for name, target in reference_contract(job).items():
        line, component = name.split(':')
        value = values.get(int(line[4:]), [None,None])[component == 'imaginary']
        passed = value is not None and abs(Decimal(str(value))-Decimal(target['exact_decimal_expected'])) <= Decimal(target['exact_decimal_tolerance'])
        checks.append(dict(name=name, **target, predicted=value, comparison='<=', passed=passed))
    return checks


def request(job, source):
    n, speed = job['nominal'], job['IAS']
    return dict(action='modes', source=source,
        numerics=dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-moving-airflow-v1'),
        panels=dict(default=n, beams={'1':dict(count=n, spacing='cosine')}),
        condition=dict(speed=speed, alpha=0., beta=0., density=1.23, mach=0., gravity_magnitude=9.81,
            ground_effect=1, ground_normal=[0.,0.,1.], position_earth=[0.,0.,0.], attitude=[0.,0.,0.],
            rates=[0.,0.,0.], acceleration=[0.,0.,0.], angular_acceleration=[0.,0.,0.],
            circulation_modes={'1':0}, freeze_influences=False, aero_lag=True, wake_core_ratio=.25,
            stall=True, stall_factor=40., stall_width=.05),
        modes=dict(frame='fixed', count=4, shift=[0.,200.], method='full_shift_invert', tolerance=1e-9,
                   step=1e-5, rank_tolerance=1e-9, matrices=True))


def _identity(job):
    return {k:deepcopy(job[k]) for k in ('comparison_scope','qualifications','complete_family_reproduction',
                                       'historical_settings_authenticated','native_modal_identity_verified')}


def validate_blocked(root, job):
    validate_record_contract(job, root)
    require(job['execution_route'] == 'unsupported', 'executable job cannot become a blocker')
    return dict(status='unsupported', numerical_pass=False, reference_match=False,
        reference_checks=reference_checks(job), source_pins_unchanged=True,
        operations=deepcopy(job['expected_operations']), blocker_code=job['blocker_code'],
        reason=job['unsupported_reason'], **_identity(job))


def assess_raw(job, raw, payload):
    """Independent full-pencil, mass and clamp checks, with compact audit fields."""
    import numpy as np
    from scripts.isae_modal_classification import classify_modes
    from scripts.isae_pencil_actions import pencil_residuals,real_pencil,matrix_norm
    a,m = real_pencil(raw['matrices'])
    norm_a,norm_m = float(matrix_norm(a)),float(matrix_norm(m))
    layout = raw['diagnostics']['state_layout']
    proofs = []
    for i, mode in enumerate(raw['modes']):
        pole = complex(*mode['eigenvalue'])
        right,left = [np.asarray(mode[k]['real'])+1j*np.asarray(mode[k]['imag']) for k in ('right','left')]
        require(right.shape == left.shape == (a.shape[0],) and np.isfinite(right).all() and np.isfinite(left).all(), 'incomplete vectors')
        right_residual, left_residual, pair = pencil_residuals(a,m,pole,right,left)
        residuals = [right_residual,left_residual]
        root = np.r_[right[:6], right[layout['local_velocity']['start']:layout['local_velocity']['start']+3],
                     right[layout['local_rates']['start']:layout['local_rates']['start']+3]]
        proofs.append(dict(mode_index=i, eigenvalue=mode['eigenvalue'], A_norm=norm_a, M_norm=norm_m,
            residual_norms=[float(np.linalg.norm(v)) for v in residuals],
            vector_norms=[float(np.linalg.norm(v)) for v in (right,left)],
            mass_pair=[float(pair.real),float(pair.imag)],
            clamp_norm=float(np.max(abs(root))), right_max=float(np.max(abs(right)))))
    diag,base = raw['diagnostics'],raw['base']
    evidence = dict(request=payload, converged=raw['converged'], base_converged=base['converged'],
        base_residual=diag['base_residual'], frame=raw['frame_mode'], vacuum=raw['vacuum'],
        structural_operator=diag['structural_operator'], method=diag['method'],
        requested_count=diag['requested_count'], shift=diag['shift'], time_scale=diag['time_scale'],
        nodes=base['structural_nodes'], elements=base['structural_elements'],
        gravity=base['gravity_body'], wall=base['ground_plane'], full_dimension=a.shape[0],
        layout_root_start=layout['node_coordinates']['start'], frame_width=layout['frame']['width'],
        eigenvalues=[mode['eigenvalue'] for mode in raw['modes']], pencil_proofs=proofs,
        classifications=classify_modes(raw['modes'],a,m,shift=diag['shift'],characteristic_rate=diag['time_scale']))
    checks = reference_checks(job, evidence['eigenvalues'], evidence['classifications'])
    return dict(status='computed', numerical_pass=True, reference_match=all(c['passed'] for c in checks),
        reference_checks=checks, numerical_evidence=evidence, source_pins_unchanged=True,
        operations=OPERATIONS.copy(), **_identity(job))


def _validate_evidence(job, e):
    require(e['request'] == request(job, (ROOT/job['model_path']).read_text()), 'declared request changed')
    require(e['converged'] is True and e['base_converged'] is True and finite(e['base_residual'])
        and 0 <= e['base_residual'] <= 1e-7, 'base equilibrium failed')
    require(e['frame']=='fixed' and e['vacuum'] is False and e['structural_operator']=='drela-moving-airflow-v1'
        and e['method']=='full_shift_invert' and e['requested_count']==4 and e['shift']==[0.,200.]
        and e['nodes']==job['nominal']+2 and e['elements']==job['nominal']+1
        and e['gravity']==[0.,0.,-9.81] and e['layout_root_start']==0 and e['frame_width']==0,
        'physical setup, mesh or mode search changed')
    require(e['full_dimension']==19*e['nodes']-1, 'complete descriptor dimension changed')
    wall = e['wall']
    require(wall['flag']==1 and wall['normal_body']==[0.,0.,1.] and wall['normal_earth']==[0.,0.,1.]
        and wall['wall_roots']==[dict(beam=1,t=.0001)] and wall['offset']==0
        and wall['position_earth']==[0.,0.,0.] and wall['attitude']==[0.,0.,0.]
        and wall['wall_root_derivative_probe'] is False, 'stationary solid wall/clamp changed')
    roots, proofs, classes = e['eigenvalues'],e['pencil_proofs'],e['classifications']
    require(len(roots)==len(proofs)==len(classes)==4 and finite(e['time_scale']) and e['time_scale']>0, 'incomplete selected spectrum')
    for i,(root,p,c) in enumerate(zip(roots,proofs,classes)):
        require(len(root)==2 and all(finite(v) for v in root) and p['mode_index']==c['mode_index']==i
            and p['eigenvalue']==c['eigenvalue']==root, 'spectrum detached from physical evidence')
        for key in ('A_norm','M_norm','clamp_norm','right_max'):
            require(finite(p[key]) and p[key]>=0, 'invalid pencil norm')
        require(len(p['residual_norms'])==len(p['vector_norms'])==2 and all(finite(v) and v>=0 for v in p['residual_norms'])
            and all(finite(v) and v>0 for v in p['vector_norms']), 'invalid vector/residual norm')
        denominator = p['A_norm']+abs(complex(*root))*p['M_norm']
        require(denominator>0 and all(r/(denominator*n)<=1e-8 for r,n in zip(p['residual_norms'],p['vector_norms'])), 'full-pencil residual failed')
        require(len(p['mass_pair'])==2 and all(finite(v) for v in p['mass_pair']) and
            abs(complex(*p['mass_pair'])-1)<=1e-6 and p['right_max']>0 and p['clamp_norm']/p['right_max']<=1e-8,
            'mass normalization or clamp failed')
        window = 1e-9*max(abs(complex(*root)), e['time_scale']*1e-6)
        require(c['imaginary_candidate_window']==window, 'classification threshold changed')
        kind = 'positive_frequency' if root[1]>0 else 'negative_frequency'
        if abs(root[1])<=window:
            kind = 'unresolved_near_real'
            for side in ('left','right'):
                v=c[side]
                require(v['phase_gate']==1e-10 and v['residual_gate']==1e-8 and
                    all(finite(v[k]) and v[k]>=0 for k in ('phase_defect','real_pencil_relative_residual')), 'invalid real-pole certificate')
                require(v['passed'] is (v['phase_defect']<=1e-10 and v['real_pencil_relative_residual']<=1e-8), 'real-pole certificate flag changed')
            require(finite(c['projected_mass_pairing']) and c['projected_mass_pairing']>=0, 'invalid projected mass')
            if c['left']['passed'] and c['right']['passed'] and c['projected_mass_pairing']>0:
                kind='certified_real'
        require(c['classification']==kind, 'classification changed without physical proof')


def validate_result_contract(job, result):
    validate_record_contract(job)
    require(all(result.get(k)==v for k,v in _identity(job).items()), 'conditional qualifications lost')
    require(result.get('source_pins_unchanged') is True and result.get('operations')==job['expected_operations'], 'source or operation evidence missing')
    if job['execution_route']=='unsupported':
        require(result.get('status')=='unsupported' and result.get('numerical_pass') is False
            and result.get('blocker_code')==job['blocker_code'] and
            all(result.get(k,0)==0 for k in ('physical_calls','physical_solver_calls','production_imports')), 'blocked route promoted')
        checks=reference_checks(job)
    else:
        require(result.get('status')=='computed' and result.get('numerical_pass') is True, 'missing computed evidence')
        _validate_evidence(job, result['numerical_evidence'])
        e=result['numerical_evidence']
        checks=reference_checks(job,e['eigenvalues'],e['classifications'])
    require(result.get('reference_checks')==checks and result.get('reference_match') is
            (result['status']=='computed' and all(c['passed'] for c in checks)), 'reference or ordinal evidence changed')
    return True


def run(root, job):
    validate_record_contract(job, root)
    require(job['execution_route']=='worker', 'blocked job cannot run')
    stage = Path(os.environ.get('TMPDIR', Path(root)/'artifacts/isae/ae4-worker-artifacts')).resolve()
    if not stage.is_relative_to(Path(root).resolve()):
        stage=Path(root)/'artifacts/isae/ae4-worker-artifacts'
    stage.mkdir(parents=True,exist_ok=True)
    folder=Path(tempfile.mkdtemp(prefix='ae4-',dir=stage))/'anchor'
    h=helper(root)
    raw=h.run(folder,job['nominal'],speed=job['IAS'])
    payload=json.loads((folder/'request.json').read_text())
    result=assess_raw(job,raw,payload)
    result['artifacts']=[pin(root,p.relative_to(root).as_posix()) for p in sorted(folder.iterdir()) if p.is_file()]
    validate_record_contract(job,root)
    validate_result_contract(job,result)
    return result


def verify_artifacts(root, result):
    """The independent summary also authenticates retained full raw artifacts."""
    if result.get('status')!='computed':
        return
    artifacts=result.get('artifacts',[])
    require({Path(p['path']).name for p in artifacts} >= {'request.json','result.json','report.json','plan.json'}, 'full modal artifacts missing')
    for p in artifacts:
        require(pin(root,p['path'])==p, 'retained artifact changed')
    byname={Path(p['path']).name:Path(root)/p['path'] for p in artifacts}
    r=json.loads(byname['report.json'].read_text())
    require(r['status']=='computed' and r['selected_eigenvalues']==result['numerical_evidence']['eigenvalues']
        and r['root_classifications']==result['numerical_evidence']['classifications'], 'compact spectrum detached from pinned helper report')


def mesh_diagnostics(jobs, results):
    """Prospective 0.1% component gate, separate from native reference accuracy."""
    rows=[]
    points=sorted({j['native_index'] for j in jobs if j.get('comparison_scope')==SCOPE})
    for point in points:
        pair={j['nominal']:j for j in jobs if j.get('comparison_scope')==SCOPE and j['native_index']==point}
        row=dict(native_index=point,IAS=point-1 if point>1 else None,status='INCOMPLETE',relative_gate=.001,checks=[])
        if all(n in pair and results.get(pair[n]['id'],{}).get('status')=='computed' for n in GRIDS):
            a,b=[results[pair[n]['id']]['reference_checks'] for n in GRIDS]
            for c,f in zip(a,b):
                x,y=c.get('predicted'),f.get('predicted')
                available=finite(x) and finite(y)
                limit=max(f['tolerance'],.001*abs(y)) if available else None
                row['checks'].append(dict(name=f['name'],coarse=x,fine=y,allowance=limit,
                    absolute_change=abs(x-y) if available else None,passed=available and abs(x-y)<=limit))
            row['status']='PASS' if all(c['passed'] for c in row['checks']) else 'FAIL'
        rows.append(row)
    return rows
