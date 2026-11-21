"""AE6 original modal ledger and explicitly declared airflow comparisons.

Planning and blocked routes are stdlib-only. Native roots are matched injectively
by complex distance, as in the retained AE6/ST4 anchor, with no identity claim.
"""
from copy import deepcopy
from decimal import Decimal
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
MANIFEST_SHA256 = '813347a3bd9fcbd029a1ec86e0c3141f82422af26f33ebde7c2f732a16bf27f6'
CACHE = '.reference/isae-validation/' + REVISION + '/'
FAMILY = '4 - Aeroelasticity/AE - Aeroelastic Cases/AE-6-D Moderate Aspect Ratio Wing - Effect of Nacelle Position on flutter Onset'
PREFIX = CACHE + FAMILY + '/Simulation_file/'
ST4 = CACHE + '3 - Structure/CASE - ST4 Concentrated weight/Simulation_files/'
GROUPS = ('Weight0', 'Weight7a', 'Weight7c', 'Weight7d', 'Weight7e', 'Weight7f')
SCOPE = 'ae6-declared-airflow'
GRIDS = (32, 64)
OPERATIONS = dict(cold_bridge_calls=1, modal_solves=1, retries=0)
BLOCKS = dict(
    HISTORICAL_SETUP_UNAUTHENTICATED='Original startup, operating altitude, aerodynamic flags and mesh arrays are unavailable; declared alternatives remain separate.',
    MALFORMED_LITERAL_MODEL='Original W0M.asw has no final End. This adapter does not repair the source or invent historical parser behavior.')
QUALIFICATIONS = [
    'Original ASWING exports are targets; experiments are not. Every real and imaginary component remains required.',
    'All six model/driver/modal-table triples are byte-identical ST4 copies. Mesh repeats and historical/declared scopes add no independent targets.',
    'Literal driver stack maps point1 to the first commanded IAS, then one plus and speed per point. Commanded tail points with no modal exports have no invented targets.',
    'Declared zero-altitude air uses each literal model Constant block. Fixed frame, PG0, current influences, lag, pointwise circulation and nominal cosine32/64 do not recover historical settings.',
    'Injective minimum complex-distance correspondence uses all selected roots, including real poles. Native eigenvector identity remains unverified.',
    'Literal zero reference area and dimensional loads are retained. No fitted material or aerodynamic parameters are used.',
    'Other nacelle positions, aggregate tables, vacuum output and exact flutter onset remain outside this modal adapter; no whole-family validation follows.',
]


def require(ok, message):
    if not ok:
        raise ValueError('AE6: ' + message)


def finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def pin(root, path):
    absolute = Path(root)/path
    with absolute.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return dict(path=str(path), bytes=absolute.stat().st_size, sha256=digest)


def helper(root=ROOT):
    spec = importlib.util.spec_from_file_location('_ae6_suite_anchor', Path(root)/'scripts/verify-isae-ae6-anchor.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def literal_constants(text):
    """Read this pinned SI archive's Constant block without production imports.

    Preserve source coordinates and tokens. As documented, the last data line
    supplies the constants. Do not let the first configuration supply another's
    density, gravity or sound speed.
    """
    lines=[(i,re.split(r'[!#%]',raw,maxsplit=1)[0].strip())
           for i,raw in enumerate(text.splitlines(),1)]
    lines=[(i,line) for i,line in lines if line]
    def block(names):
        starts=[k for k,(_,line) in enumerate(lines) if line.lower() in names]
        require(len(starts)==1,'ambiguous or missing '+names[0]+' block')
        following=lines[starts[0]+1:]
        end=next((i for i,(_,line) in enumerate(following) if line.lower()=='end'),None)
        require(end is not None and end>0,'unterminated or empty '+names[0]+' block')
        return following[:end]
    units=[line.split() for _,line in block(('unit','units'))]
    require(all(len(row)==3 for row in units),'unsupported Unit grammar')
    require([(row[0],float(row[1]),row[2]) for row in units]==
        [('L',1.,'m'),('T',1.,'s'),('F',1.,'N')],'archive SI units changed')
    rows=block(('constant',))
    for _,line in rows:
        tokens=line.split()
        require(len(tokens)==3,'Constant requires gravity, density and sound speed')
        values=[float(t.replace('D','E').replace('d','e')) for t in tokens]
        require(all(finite(v) and v>0 for v in values),'invalid Constant value')
    return dict(line=rows[-1][0],tokens=tokens,gravity=values[0],density=values[1],sound_speed=values[2])


def driver_speeds(text):
    """Check the complete relevant command stack, not just occurrences of !V."""
    commands = [line.strip().lower() for line in text.splitlines() if line.strip()]
    match = re.search(r'/aswing\s+([^\s]+)\s+<<eof', commands[1])
    require(match is not None, 'model invocation changed')
    oper = commands[commands.index('oper')+1:commands.index('!!b 0.0')]
    require(len(oper) % 2 == 1, 'operating stack changed')
    speeds = []
    for index, command in enumerate(oper):
        if index % 2:
            require(command == '+', 'operating point increment changed')
        else:
            tokens = command.split()
            require(len(tokens) == 2 and tokens[0] == '!v', 'speed command changed')
            speed = float(tokens[1])
            require(finite(speed) and speed > 0, 'invalid speed')
            speeds.append(speed)
    require(commands[commands.index('!!b 0.0')+1:commands.index('xx')] == ['%','a','p','d'], 'OPER constraints changed')
    require(commands[commands.index('modes')+1:commands.index('nn')] == ['%','.','p','d'], 'MODE constraints changed')
    i = commands.index('nn')
    require(commands[i+1] == '16' and [float(v) for v in commands[i+2].split()] == [0.,300.], 'mode count or shift changed')
    require(commands[commands.index('ww')+1] == 'eig.txt', 'modal writer changed')
    return match[1], speeds


def _table_record(root, group, manifest=None, decoder=None):
    root = Path(root)
    require(group in GROUPS, 'unknown configuration')
    mp = pin(root, '.reference/isae-validation/manifest.json')
    require(mp['sha256'] == MANIFEST_SHA256, 'reference manifest changed')
    manifest = manifest or json.loads((root/mp['path']).read_text())
    require(manifest['revision'] == REVISION, 'reference revision changed')
    def original(path):
        p = pin(root, path)
        require(all(p[k] == manifest['files'][path[len(CACHE):]][k] for k in ('bytes','sha256')), 'original bytes changed: '+path)
        return p
    parent = PREFIX+group+'/'
    driver, table = parent+'Flutter_analysis.sh', parent+'eig.txt'
    driver_pin, table_pin = original(driver), original(table)
    stem, speeds = driver_speeds((root/driver).read_text())
    candidates = [p for p in (root/parent).glob('*.asw') if p.stem.lower() == stem]
    require(len(candidates) == 1, 'ambiguous literal model')
    model = candidates[0].relative_to(root).as_posix()
    model_pin = original(model)
    rows = (decoder or helper(root).rows)((root/table).read_text())
    indices = sorted({r['index'] for r in rows})
    require(indices == list(range(1, max(indices)+1)) and max(indices) <= len(speeds), 'native index has no literal speed')
    overlaps = []
    for p in (model_pin, driver_pin, table_pin):
        other = original(ST4+('' if group=='Weight0' else group+'/')+Path(p['path']).name)
        require(other['sha256'] == p['sha256'], 'ST4 duplicate identity changed')
        overlaps.append(dict(AE6=p, ST4=other, identical=True))
    source = (root/model).read_text()
    constants = literal_constants(source)
    lines = [l.strip() for l in source.splitlines() if l.strip() and not l.lstrip().startswith('#')]
    require((lines[-1].lower() == 'end') is (group != 'Weight0'), 'literal model termination changed')
    return dict(id='AE-6:historical:'+group, case_id='AE-6', adapter='ae6', group=group,
        comparison_scope='historical-modal-exports', target_kind='native_modal', execution_route='unsupported',
        blocker_code='HISTORICAL_SETUP_UNAUTHENTICATED', unsupported_reason=BLOCKS['HISTORICAL_SETUP_UNAUTHENTICATED'],
        model_path=model, driver_path=driver, table_path=table, table_sha256=table_pin['sha256'], source_constants=constants,
        source_pins=[mp,model_pin,driver_pin,table_pin]+[p['ST4'] for p in overlaps], ST4_overlaps=overlaps,
        reference_rows=rows, commanded_speeds=speeds, expected_outputs=2*len(rows), required_components=['real','imaginary'],
        expected_operations=dict(cold_bridge_calls=0,modal_solves=0,retries=0), qualifications=QUALIFICATIONS.copy(),
        complete_family_reproduction=False, historical_settings_authenticated=False, native_modal_identity_verified=False)


def _declared(original, index, nominal):
    require(type(index) is int and type(nominal) is int and nominal in GRIDS, 'invalid point or mesh')
    rows = [r for r in original['reference_rows'] if r['index'] == index]
    require(bool(rows) and index <= len(original['commanded_speeds']), 'native point missing')
    blocked = original['group'] == 'Weight0'
    result = deepcopy({k:v for k,v in original.items() if k != 'reference_rows'})
    result.update(id=f"AE-6:declared:{original['group']}:op{index:03d}:n{nominal}", comparison_scope=SCOPE,
        execution_route='unsupported' if blocked else 'worker',
        blocker_code='MALFORMED_LITERAL_MODEL' if blocked else None,
        unsupported_reason=BLOCKS['MALFORMED_LITERAL_MODEL'] if blocked else None,
        reference_rows=deepcopy(rows), expected_outputs=2*len(rows), native_index=index,
        IAS=original['commanded_speeds'][index-1], nominal=nominal,
        extra_weight_nodes=1 if original['group'] in ('Weight0','Weight7a','Weight7c') else 0,
        expected_operations=original['expected_operations'].copy() if blocked else OPERATIONS.copy(),
        suggested_address_cap_mib=512 if nominal==32 else 768, mesh_relative_gate=.001)
    return result


def plan(root, *, comparison_scopes=()):
    require(len(set(comparison_scopes)) == len(comparison_scopes) and set(comparison_scopes) <= {SCOPE}, 'unknown scope')
    require({p.parent.name for p in (Path(root)/PREFIX).glob('*/eig.txt')} == set(GROUPS), 'modal inventory changed')
    manifest = json.loads((Path(root)/'.reference/isae-validation/manifest.json').read_text())
    decoder = helper(root).rows
    jobs = [_table_record(root,g,manifest,decoder) for g in GROUPS]
    require(sum(j['expected_outputs'] for j in jobs) == 3348, 'original denominator changed')
    if SCOPE in comparison_scopes:
        jobs += [_declared(j,i,n) for j in jobs[:]
                 for i in sorted({r['index'] for r in j['reference_rows']}) for n in GRIDS]
    return jobs


def validate_record_contract(job, root=ROOT):
    original = _table_record(root,job.get('group'))
    if job.get('comparison_scope') == SCOPE:
        original = _declared(original,job.get('native_index'),job.get('nominal'))
    require(all(job.get(k) == v for k,v in original.items()), 'source, coordinates, targets or qualifications changed')
    return True


def reference_contract(job):
    contract = {}
    for row in job['reference_rows']:
        for k,name in enumerate(('real','imaginary')):
            value = Decimal(row['tokens'][k+1].replace('D','E'))
            half = Decimal(10)**value.as_tuple().exponent/2
            contract[f"line{row['line']}:{name}"] = dict(expected=float(value),tolerance=float(half),
                exact_decimal_expected=str(value),exact_decimal_tolerance=str(half),unit='1/s')
    require(len(contract) == job['expected_outputs'], 'target count changed')
    return contract


def reference_checks(job, roots=None):
    values = {}
    if roots is not None:
        import numpy as np
        from scipy.optimize import linear_sum_assignment
        expected = np.asarray([complex(*r['eigenvalue']) for r in job['reference_rows']])
        actual = np.asarray([complex(*r) for r in roots])
        require(len(actual) >= len(expected) and np.isfinite(actual).all(), 'incomplete finite selected spectrum')
        rows, selected = linear_sum_assignment(abs(expected[:,None]-actual[None,:]))
        require(list(rows) == list(range(len(expected))) and len(set(selected)) == len(expected), 'noninjective modal correspondence')
        values = {job['reference_rows'][i]['line']:roots[k] for i,k in zip(rows,selected)}
    checks = []
    for name,target in reference_contract(job).items():
        line,component = name.split(':')
        value = values.get(int(line[4:]),[None,None])[component=='imaginary']
        passed = value is not None and abs(Decimal(str(value))-Decimal(target['exact_decimal_expected'])) <= Decimal(target['exact_decimal_tolerance'])
        checks.append(dict(name=name,**target,predicted=value,comparison='<=',passed=passed))
    return checks


def request(job, source):
    n = job['nominal']
    constants = literal_constants(source)
    require(constants==job['source_constants'],'request constants detached from original model')
    return dict(action='modes', source=source,
        numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator='drela-moving-airflow-v1'),
        panels=dict(default=n,beams={'1':dict(count=n,spacing='cosine')}),
        condition=dict(speed=job['IAS'],alpha=0.,beta=0.,density=constants['density'],mach=0.,gravity_magnitude=constants['gravity'],
            position_earth=[0.,0.,0.],attitude=[0.,0.,0.],rates=[0.,0.,0.],acceleration=[0.,0.,0.],
            angular_acceleration=[0.,0.,0.],ground_effect=0,freeze_influences=False,aero_lag=True,
            circulation_modes={'1':0},wake_core_ratio=.25,stall=True,stall_factor=40.,stall_width=.05),
        modes=dict(frame='fixed',count=16,shift=[0.,300.],method='full_shift_invert',
            step=1e-5,rank_tolerance=1e-9,tolerance=1e-9,matrices=True))


def _identity(job):
    return {k:deepcopy(job[k]) for k in ('comparison_scope','qualifications','complete_family_reproduction',
        'historical_settings_authenticated','native_modal_identity_verified')}


def validate_blocked(root, job):
    validate_record_contract(job,root)
    require(job['execution_route']=='unsupported','executable job cannot become a blocker')
    return dict(status='unsupported',numerical_pass=False,reference_match=False,
        reference_checks=reference_checks(job),source_pins_unchanged=True,operations=job['expected_operations'].copy(),
        blocker_code=job['blocker_code'],reason=job['unsupported_reason'],**_identity(job))


def assess_raw(job, raw, payload):
    """Recompute original left/right pencil residuals, mass pairing and clamps."""
    import numpy as np
    a,m = [np.asarray(raw['matrices'][k]) for k in ('A','M')]
    require(a.ndim==2 and a.shape==m.shape and a.shape[0]==a.shape[1] and
        np.isfinite(a).all() and np.isfinite(m).all(), 'invalid full pencil')
    an,mn = float(np.linalg.norm(a)),float(np.linalg.norm(m))
    d,b = raw['diagnostics'],raw['base']
    layout = d['state_layout'];proofs=[]
    for i,mode in enumerate(raw['modes']):
        pole=complex(*mode['eigenvalue'])
        v,w=[np.asarray(mode[k]['real'])+1j*np.asarray(mode[k]['imag']) for k in ('right','left')]
        require(v.shape==w.shape==(len(a),) and np.isfinite(v).all() and np.isfinite(w).all(), 'incomplete vectors')
        pair=w.conj()@m@v
        clamp=np.r_[v[:6],v[layout['local_velocity']['start']:layout['local_velocity']['start']+3],
            v[layout['local_rates']['start']:layout['local_rates']['start']+3]]
        proofs.append(dict(mode_index=i,eigenvalue=mode['eigenvalue'],A_norm=an,M_norm=mn,
            residual_norms=[float(np.linalg.norm(a@v-pole*(m@v))),float(np.linalg.norm(w.conj()@a-pole*(w.conj()@m)))],
            vector_norms=[float(np.linalg.norm(x)) for x in (v,w)],mass_pair=[float(pair.real),float(pair.imag)],
            clamp_norm=float(np.max(abs(clamp))),right_max=float(np.max(abs(v)))))
    e=dict(request=payload,converged=raw['converged'],base_converged=b['converged'],base_residual=d['base_residual'],
        frame=raw['frame_mode'],vacuum=raw['vacuum'],structural_operator=d['structural_operator'],method=d['method'],
        requested_count=d['requested_count'],shift=d['shift'],nodes=b['structural_nodes'],elements=b['structural_elements'],
        gravity=b['gravity_body'],wall=b['ground_plane'],full_dimension=len(a),layout=layout,
        reference_flow=b['reference_flow'],atmosphere=b['atmosphere'],CL=b['CL'],CD=b['CD'],
        eigenvalues=[mode['eigenvalue'] for mode in raw['modes']],pencil_proofs=proofs)
    checks=reference_checks(job,e['eigenvalues'])
    return dict(status='computed',numerical_pass=True,reference_match=all(c['passed'] for c in checks),
        reference_checks=checks,numerical_evidence=e,source_pins_unchanged=True,operations=OPERATIONS.copy(),**_identity(job))


def _validate_evidence(job,e):
    require(e['request']==request(job,(ROOT/job['model_path']).read_text()),'declared request changed')
    require(e['converged'] is True and e['base_converged'] is True and finite(e['base_residual'])
        and 0 <= e['base_residual'] <= 1e-7,'base equilibrium failed')
    nodes=job['nominal']+1+job['extra_weight_nodes']
    constants=job['source_constants']
    require(e['frame']=='fixed' and e['vacuum'] is False and e['structural_operator']=='drela-moving-airflow-v1'
        and e['method']=='full_shift_invert' and e['requested_count']==16 and e['shift']==[0.,300.]
        and e['nodes']==nodes and e['elements']==nodes-1 and e['full_dimension']==19*nodes-1
        and e['gravity']==[0.,0.,-constants['gravity']] and e['CL'] is None and e['CD'] is None,'physical setup or mesh changed')
    layout=e['layout']
    require(layout['node_coordinates']['start']==0 and layout['frame']['width']==0
        and layout['local_velocity']['start']==13*nodes-1 and layout['local_velocity']['width']==3*nodes
        and layout['local_rates']['start']==16*nodes-1 and layout['local_rates']['width']==3*nodes
        and layout['circulation']['width']==nodes-1,'full physical state layout changed')
    require(e['wall']['flag']==0 and e['wall']['kind']=='off','ground image unexpectedly enabled')
    flow,atmos=e['reference_flow'],e['atmosphere']
    require(flow['speed']==job['IAS'] and flow['equivalent_airspeed']==job['IAS'] and flow['alpha']==0 and flow['beta']==0 and
        atmos['density']==constants['density'] and atmos['density_source']=='override' and atmos['density_ratio']==1.
        and atmos['altitude_m']==0. and atmos['sound_speed']==constants['sound_speed'] and
        atmos['gravity_magnitude']==constants['gravity'] and atmos['equivalent_airspeed']==job['IAS'],
        'flow or source atmosphere changed')
    pressure=.5*constants['density']*job['IAS']**2
    require(all(finite(value) and math.isclose(value,pressure,rel_tol=1e-14,abs_tol=0)
        for value in (flow['dynamic_pressure'],atmos['dynamic_pressure'])),'dynamic pressure changed')
    roots,proofs=e['eigenvalues'],e['pencil_proofs']
    require(len(roots)==len(proofs)==16,'incomplete selected spectrum')
    for i,(root,p) in enumerate(zip(roots,proofs)):
        require(len(root)==2 and all(finite(v) for v in root) and p['mode_index']==i and p['eigenvalue']==root,'spectrum detached from pencil evidence')
        require(all(finite(p[k]) and p[k]>=0 for k in ('A_norm','M_norm','clamp_norm','right_max')),'invalid pencil norm')
        require(len(p['residual_norms'])==len(p['vector_norms'])==2 and
            all(finite(v) and v>=0 for v in p['residual_norms']) and all(finite(v) and v>0 for v in p['vector_norms']),'invalid residual norms')
        denominator=p['A_norm']+abs(complex(*root))*p['M_norm']
        require(denominator>0 and all(r/(denominator*n)<=1e-8 for r,n in zip(p['residual_norms'],p['vector_norms'])),'full-pencil residual failed')
        require(len(p['mass_pair'])==2 and all(finite(v) for v in p['mass_pair']) and
            abs(complex(*p['mass_pair'])-1)<=1e-6 and p['right_max']>0 and p['clamp_norm']/p['right_max']<=1e-8,'mass pairing or clamp failed')


def validate_result_contract(job,result):
    validate_record_contract(job)
    require(all(result.get(k)==v for k,v in _identity(job).items()),'conditional qualifications lost')
    require(result.get('source_pins_unchanged') is True and result.get('operations')==job['expected_operations'],'source or operation evidence missing')
    if job['execution_route']=='unsupported':
        require(result.get('status')=='unsupported' and result.get('numerical_pass') is False and
            result.get('blocker_code')==job['blocker_code'] and all(result.get(k,0)==0 for k in
            ('physical_calls','physical_solver_calls','production_imports')),'blocked route promoted')
        checks=reference_checks(job)
    else:
        require(result.get('status')=='computed' and result.get('numerical_pass') is True,'missing computed evidence')
        _validate_evidence(job,result['numerical_evidence'])
        checks=reference_checks(job,result['numerical_evidence']['eigenvalues'])
    require(result.get('reference_checks')==checks and result.get('reference_match') is
        (result['status']=='computed' and all(c['passed'] for c in checks)),'reference evidence changed')
    return True


def _write(path,value):
    with path.open('w') as stream:
        json.dump(value,stream,indent=2,allow_nan=False)
        stream.write('\n')


def run(root,job):
    validate_record_contract(job,root)
    require(job['execution_route']=='worker','blocked job cannot run')
    stage=Path(os.environ.get('TMPDIR',Path(root)/'artifacts/isae/ae6-worker-artifacts')).resolve()
    if not stage.is_relative_to(Path(root).resolve()):
        stage=Path(root)/'artifacts/isae/ae6-worker-artifacts'
    stage.mkdir(parents=True,exist_ok=True)
    folder=Path(tempfile.mkdtemp(prefix='ae6-',dir=stage))
    payload=request(job,(Path(root)/job['model_path']).read_text())
    _write(folder/'request.json',payload);_write(folder/'plan.json',job)
    from openswing.bridge import dispatch
    started=time.monotonic()
    raw=dispatch(payload)
    seconds=time.monotonic()-started
    _write(folder/'result.json',raw)
    result=assess_raw(job,raw,payload)
    result['solve_seconds']=seconds
    validate_record_contract(job,root);validate_result_contract(job,result)
    _write(folder/'report.json',result)
    result['artifacts']=[pin(root,p.relative_to(root).as_posix()) for p in sorted(folder.iterdir())]
    return result


def verify_artifacts(root,result):
    if result.get('status')!='computed':
        return
    artifacts=result.get('artifacts',[])
    require(len(artifacts)==4 and {Path(p['path']).name for p in artifacts}==
        {'request.json','plan.json','result.json','report.json'},'complete modal artifacts missing')
    for p in artifacts:
        require(pin(root,p['path'])==p,'retained artifact changed')
    paths={Path(p['path']).name:Path(root)/p['path'] for p in artifacts}
    report=json.loads(paths['report.json'].read_text())
    require(all(result.get(k)==v for k,v in report.items()),'compact report detached from pinned artifacts')
    job=json.loads(paths['plan.json'].read_text())
    validate_result_contract(job,report)
    rebuilt=assess_raw(job,json.loads(paths['result.json'].read_text()),json.loads(paths['request.json'].read_text()))
    require(all(report.get(k)==v for k,v in rebuilt.items()),'full physical evidence differs from compact report')


def mesh_diagnostics(jobs,results):
    rows=[]
    declared=[j for j in jobs if j.get('comparison_scope')==SCOPE]
    for group,point in sorted({(j['group'],j['native_index']) for j in declared}):
        pair={j['nominal']:j for j in declared if j['group']==group and j['native_index']==point}
        row=dict(group=group,native_index=point,IAS=next(iter(pair.values()))['IAS'],status='INCOMPLETE',relative_gate=.001,checks=[])
        if all(n in pair and results.get(pair[n]['id'],{}).get('status')=='computed' for n in GRIDS):
            coarse,fine=[results[pair[n]['id']]['reference_checks'] for n in GRIDS]
            require([c['name'] for c in coarse]==[c['name'] for c in fine],'mesh correspondence changed')
            for c,f in zip(coarse,fine):
                x,y=c.get('predicted'),f.get('predicted');available=finite(x) and finite(y)
                limit=max(f['tolerance'],.001*abs(y)) if available else None
                row['checks'].append(dict(name=f['name'],coarse=x,fine=y,allowance=limit,
                    absolute_change=abs(x-y) if available else None,passed=available and abs(x-y)<=limit))
            row['status']='PASS' if all(c['passed'] for c in row['checks']) else 'FAIL'
        rows.append(row)
    return rows
