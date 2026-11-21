"""Source-generated AP2 propeller-position sweeps and retained unpaired exports.

Each grid job has one cold mounted solve and one restored residual. Only the
two Engine rows are reconstructed from the archived MATLAB producer; original
files remain unchanged. Stored MAT ratio equality is a separate diagnostic
from the native printed precision of the retained CL/CD exports.
"""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import tempfile
import traceback

from scripts.isae_suite_ap1 import header_values, reconstruct_wrenches


CATALOG = 'docs/validation/isae-ap2-reference.json'
CATALOG_SHA256 = '16244f64b1544dd88cd4faf809e25a4399dc18a24e4860948d6f01142d02a617'
POLICY = dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-steady-coupled-v1')
GATES = dict(residual=1e-8, relative_balance=1e-7, restored_parity=2e-10, clamp=1e-10)
CHANNELS = ('CL', 'CD', 'CL_CD_ratio')
QUALIFICATIONS = [
    'All 117 stored MAT ratio cells are retained on both declared meshes; the three unpaired exports remain blocked.',
    'Original files are unchanged. Intermediate inputs reconstruct only the two Engine rows using the archived generator and five-significant-digit tokens; original-byte provenance is not claimed for generated states.',
    'APROPOS1 retains Cdp=.0045 and APROPOS retains Cdp=.005. No geometry, stiffness, mass, aerodynamic property or coefficient is fitted.',
    'The command scripts select CL/CD and name the retained CSV outputs. Their indexing conflicts with the commented MATLAB Var11/Var17 producer; complete exporter history is not recovered.',
    'MAT ratio equality uses its stored binary64 value, tolerance zero. This is storage identity, not recovered ASWING coefficient printing precision or a physical accuracy threshold.',
    'The two endpoint coefficient pairs have their own native half-last-place precision. Their MAT ratios are algebraically dependent evidence, not independent validations.',
    'Nominal 150/300 intervals reconstruct the original NODE I150 command; exact historical nodes, atmosphere/PG, K/F, core and continuation are unknown.',
    'Coordinates from experimental files supply the documented input grid only; experimental force or ratio values are not acceptance targets.',
    'Mounted cold states use literal density, zero Mach, fixed influences disabled and core ratio .25; historical setup is conditional.',
    'Lift and drag coefficients use distributed aerodynamic forces and literal reference area; engine thrust remains in total forces and moments.',
    'Computed jobs and scalar equality cannot establish an entire family pass. Mesh changes are descriptive, without a new acceptance gate.']
UNKNOWN_SETUP = ['exact archived nodes', 'atmosphere/PG and IAS/TAS interpretation',
                 'original K/F and core', 'startup and continuation', 'exporter/producer revision']

PHYSICAL_CHECK_SPECS = {
    **{name:dict(kind='exact') for name in ('same_operator_identity', 'restore_without_evaluation',
        'one_restored_residual', 'converged', 'source_policy', 'two_shared_power_engines',
        'literal_reference_normalization', 'root_clamp_count', 'finite_outputs')},
    'fresh_full_residual':dict(kind='metric', gate='residual'),
    **{name:dict(kind='balance', gate='relative_balance') for name in ('force_balance','moment_balance')},
    **{name:dict(kind='metric', gate='clamp') for name in ('engine_position_error','root_clamp_position','root_clamp_frame')},
    **{'independent_'+name:dict(kind='independent', gate='restored_parity') for name in (
        'distributed_aero_force','distributed_aero_moment','engine_force','engine_moment','force','moment','CL','CD','CL_CD_ratio')},
    'restored_output_parity':dict(kind='parity', gate='restored_parity')}
REQUIRED_PHYSICAL_CHECKS = tuple(PHYSICAL_CHECK_SPECS)


def _require(ok, message):
    if not ok:
        raise ValueError('AP2 '+message)


def _pin(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def _write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _context(root):
    root = Path(root).resolve()
    _require(_pin(root/CATALOG)['sha256']==CATALOG_SHA256, 'reference catalog changed; re-audit original source extraction.')
    catalog = json.loads((root/CATALOG).read_text())
    _require(catalog.get('format') == 'isae-ap2-reference' and catalog.get('version') == 1,
             'unsupported reference catalog.')
    originals = []
    for pin in catalog['source_pins']:
        actual = _pin(root/pin['path'])
        _require(actual['sha256'] == pin['sha256'] and actual['bytes'] == pin['bytes'],
                 'original source changed: '+pin['path'])
        originals.append(actual)
    helpers = [root/CATALOG, root/'scripts/isae_suite_ap2.py', root/'scripts/isae_suite_ap1.py',
               root/'scripts/extract-isae-ap2-reference.py']
    return root, catalog, originals+[_pin(p) for p in helpers]


def reconstruct_source(raw, tokens, original_endpoint=False):
    """Replay the producer's two Engine-row replacements, preserving other bytes."""
    lines = raw.splitlines(keepends=True)
    markers = (b'#  Propeller 1 position', b'# Propeller 2 position')
    for marker, key in zip(markers, ('positive','negative')):
        indices = [i+1 for i,line in enumerate(lines) if marker in line]
        _require(len(indices) == 1 and indices[0] < len(lines), 'Engine marker missing/duplicated.')
        i = indices[0]
        _require(len(tokens[key]) == 15, 'Engine token count changed.')
        if original_endpoint:
            _require(lines[i].split() == [t.encode('ascii') for t in tokens[key]],
                     'retained endpoint differs from reconstructed Engine tokens.')
        else:
            ending = b'\r\n' if lines[i].endswith(b'\r\n') else b'\n' if lines[i].endswith(b'\n') else b''
            lines[i] = ' '.join(tokens[key]).encode('ascii')+ending
    return raw if original_endpoint else b''.join(lines)


def _observations(row, series):
    ratio = row['ratio']
    _require(_finite(ratio) and ratio.hex() == row['ratio_hex'], 'MAT stored value changed.')
    observations = [dict(name='CL_CD_ratio', expected=ratio, tolerance=0., expected_hex=row['ratio_hex'],
        precision_scope='Exact stored MAT binary64 identity; original coefficient printing precision unrecovered.',
        source_table=series['mat_path'], source_row=row['row_index']+1, source_column=row['col_index']+1,
        units='dimensionless', missing=False)]
    if row['paired_csv'] is not None:
        for name in ('CL','CD'):
            observations.append(dict(row['paired_csv'][name], name=name, source_table=series['csv_path'],
                                     units='dimensionless', missing=False,
                                     precision_scope='Native CL/CD token half-last-place.'))
    return observations


def _jobs(root, catalog, pins, only=None):
    kernel = None
    for series in catalog['series']:
        rows = series['rows']
        _require(len(rows) == math.prod(series['shape']) and series['shape'] in ([4,13],[5,13]),
                 'complete grid shape changed.')
        for row in rows:
            coordinate = f"{series['id']}-z{row['row_index']+1:02d}-y{row['col_index']+1:02d}"
            for nominal in (150,300):
                identifier = f'AP-2-{coordinate}-m{nominal}'
                if only is not None and only != identifier:
                    continue
                if kernel is None:
                    kernel = [_pin(p) for p in sorted((root/'openswing').glob('*.py'))]
                observations = _observations(row, series)
                source = reconstruct_source((root/series['model_path']).read_bytes(), row['engine_tokens'], row['original_endpoint'])
                _require(hashlib.sha256(source).hexdigest() == row['generated_source_sha256'], 'generated source hash differs from producer catalog.')
                yield dict(id=identifier, case_id='AP-2', adapter='ap2', target_kind='grid_state', execution_route='worker',
                    coordinate_id=coordinate, model_path=series['model_path'], source=str(root/series['model_path']),
                    driver_path=series['driver_path'], table_path=series['mat_path'],
                    source_row=deepcopy(row), series_id=series['id'], alpha=series['alpha'],
                    reference_rows=[dict(row_number=row['row_number'],grid_row=row['row_index']+1,
                                         grid_column=row['col_index']+1,coordinate_id=coordinate)],
                    observations=observations, expected_outputs=len(observations), nominal=nominal,
                    mesh=f'm{nominal}', panels=nominal, settings=deepcopy(POLICY),
                    condition=dict(speed=50.,alpha=float(series['alpha']),beta=0.,density=1.2256,mach=0.,
                        controls={'1':0.},powers={'1':330.},freeze_influences=False,wake_core_ratio=.25,
                        attitude=[0.,0.,0.],rates=[0.,0.,0.],acceleration=[0.,0.,0.],angular_acceleration=[0.,0.,0.]),
                    source_pins=pins, kernel_pins=kernel, numerical_gates=deepcopy(GATES),
                    expected_operations=dict(cold_solves=1,fresh_residuals=1,retries=0),suggested_cap_seconds=180,
                    original_file_modified=False, generated_engine_positions=not row['original_endpoint'],
                    historical_settings_recovered=False, unknown_setup=list(UNKNOWN_SETUP),
                    complete_family_reproduction=False, qualifications=list(QUALIFICATIONS),
                    reference_scope='One original MAT ratio cell and any paired native endpoint coefficients; all source-generated grid positions retained.')
    for export in catalog['unpaired']:
        identifier = 'AP-2-unpaired-'+Path(export['table_path']).stem
        if only is not None and only != identifier:
            continue
        observations = [dict(o,source_table=export['table_path'],units='dimensionless',missing=False,
                            precision_scope='Native CL/CD token half-last-place.') for o in export['observations']]
        yield dict(id=identifier,case_id='AP-2',adapter='ap2',target_kind='unpaired_operating',execution_route='unsupported',
            coordinate_id=identifier,model_path=None,source=None,driver_path=None,table_path=export['table_path'],
            reference_rows=deepcopy(export['rows']),observations=observations,expected_outputs=len(observations),
            nominal=None,mesh='none',panels=None,settings=None,condition=None,source_pins=pins,kernel_pins=[],
            numerical_gates=None,expected_operations=dict(cold_solves=0,fresh_residuals=0,retries=0),
            blocker_code='UNPAIRED_REFERENCE',unsupported_reason='No unique original input/operating-state pairing is established for this TXT export; matching a ratio alone does not identify its inputs.',
            original_file_modified=False,generated_engine_positions=False,historical_settings_recovered=False,
            unknown_setup=list(UNKNOWN_SETUP),complete_family_reproduction=False,qualifications=list(QUALIFICATIONS),
            reference_scope='Both original coefficient tokens remain required but unavailable until their producing state is recovered.')


def plan(root):
    root, catalog, pins = _context(root)
    jobs = list(_jobs(root,catalog,pins))
    _require(len(jobs)==237 and sum(j['expected_outputs'] for j in jobs)==248 and
             sum(j['execution_route']=='worker' for j in jobs)==234, 'full AP2 accounting changed.')
    return jobs


def verify_reference_sources(root, job):
    root,catalog,pins = _context(root)
    canonical = list(_jobs(root,catalog,pins,only=job.get('id')))
    _require(len(canonical)==1 and all(job.get(k)==v for k,v in canonical[0].items()),
             'job differs from original sources, producer reconstruction, scope or current numerical code.')
    return True


def reference_contract(job):
    _require(job.get('case_id')=='AP-2' and job.get('adapter')=='ap2' and
             job.get('target_kind') in ('grid_state','unpaired_operating'), 'invalid reference route.')
    observations=job.get('observations',[])
    _require(len(observations)==job['expected_outputs'] and len({o['name'] for o in observations})==len(observations),
             'incomplete or duplicated targets.')
    for o in observations:
        _require(_finite(o['expected']) and _finite(o['tolerance']) and o['tolerance']>=0, 'invalid reference precision.')
        if o['name']=='CL_CD_ratio':
            _require(o['tolerance']==0. and o['expected'].hex()==o['expected_hex'], 'stored MAT identity changed.')
    return {o['name']:{k:v for k,v in o.items() if k!='name'} for o in observations}


def _checks(job, values, reason=None):
    checks=[]
    for o in job['observations']:
        value=values.get(o['name']); valid=_finite(value)
        error=abs(value-o['expected']) if valid else None
        checks.append(dict(o,predicted=value if valid else None,abs_error=error,comparison='<=',
            passed=bool(valid and error<=o['tolerance']),unavailable_reason=None if valid else reason))
    return checks


def _stable(pins):
    try:
        return all(_pin(p['path'])==p for p in pins)
    except OSError:
        return False


def validate_blocked(root, job):
    _require(job['execution_route']=='unsupported', 'grid comparison requires a worker.')
    verify_reference_sources(root,job)
    return dict(id=job['id'],case_id='AP-2',adapter='ap2',target_kind=job['target_kind'],status='unsupported',
        numerical_pass=False,reference_match=False,reference_checks=_checks(job,{},job['unsupported_reason']),
        physical_checks=[],physical_calls=0,production_imports=0,operations=dict(cold_solves=0,fresh_residuals=0,retries=0),
        source_pins_unchanged=True,kernel_pins_unchanged=True,blocker_code=job['blocker_code'],
        unsupported_reason=job['unsupported_reason'],complete_family_reproduction=False,qualifications=job['qualifications'])


def _expectations():
    return dict(restore_without_evaluation=0,one_restored_residual=1,converged=True,
        source_policy=dict(numerics=POLICY,operator=POLICY['structural_operator'],launch=False),
        two_shared_power_engines=[dict(power=330.,clipped=False)]*2,
        literal_reference_normalization=[.1536,.24,.64],root_clamp_count=1,
        finite_outputs={name:True for name in CHANNELS})


def _relative(reported, reconstructed):
    if not isinstance(reported,list):reported,reconstructed=[reported],[reconstructed]
    _require(isinstance(reconstructed,list) and len(reported)==len(reconstructed) and len(reported) in (1,3) and
             all(_finite(v) for v in reported+reconstructed),'invalid independent values.')
    return max(abs(a-b) for a,b in zip(reported,reconstructed))/(1.+max(map(abs,reported+reconstructed)))


def validate_physical_checks(job, checks):
    _require(job['numerical_gates']==GATES,'physical gates changed.')
    names=[c.get('name') for c in checks]
    _require(len(names)==len(set(names))==len(REQUIRED_PHYSICAL_CHECKS) and set(names)==set(REQUIRED_PHYSICAL_CHECKS),
             'physical check set incomplete or duplicated.')
    for c in checks:
        spec=PHYSICAL_CHECK_SPECS[c['name']]
        if spec['kind']=='exact':
            _require('actual' in c and 'expected' in c,'missing physical comparison evidence.')
            if c['name'] in _expectations():
                _require(c['expected']==_expectations()[c['name']],'physical expectation changed.')
            passed=c['actual']==c['expected']
        else:
            metric=c.get('metric');gate=GATES[spec['gate']]
            _require(_finite(metric) and metric>=0 and c.get('gate')==gate,'invalid physical metric.')
            if spec['kind']=='independent':
                _require(metric==_relative(c.get('reported'),c.get('reconstructed')),'independent metric disagrees with vectors.')
            elif spec['kind']=='balance':
                a,b=c.get('applied'),c.get('support')
                _require(isinstance(a,list) and isinstance(b,list) and len(a)==len(b)==3 and
                         all(_finite(v) for v in a+b),'missing balance vectors.')
                value=math.hypot(*(x+y for x,y in zip(a,b)))/max(1.,math.hypot(*a)+math.hypot(*b))
                _require(math.isclose(metric,value,rel_tol=2e-15,abs_tol=1e-30),'balance metric disagrees with vectors.')
            elif spec['kind']=='parity':
                a,b=c.get('reported'),c.get('restored')
                _require(isinstance(a,dict) and isinstance(b,dict) and set(a)==set(b)==set(CHANNELS) and
                         all(_finite(v) for v in list(a.values())+list(b.values())),'missing restored outputs.')
                channels={k:abs(a[k]-b[k])/(1.+abs(a[k])) for k in CHANNELS}
                _require(c.get('channels')==channels and metric==max(channels.values()),'restored metric changed.')
            elif c['name']=='engine_position_error':
                expected=[[float(x) for x in job['source_row']['engine_tokens'][key][4:7]] for key in ('positive','negative')]
                actual=c.get('reported')
                _require(c.get('expected')==expected and isinstance(actual,list) and len(actual)==2 and
                         all(isinstance(row,list) and len(row)==3 and all(_finite(v) for v in row) for row in actual),
                         'engine geometry differs from declared generated input.')
                recomputed=max(abs(a-b) for row_a,row_b in zip(actual,expected) for a,b in zip(row_a,row_b))
                _require(metric==recomputed,'engine geometry metric differs from vectors.')
            passed=metric<=gate
        _require(isinstance(c.get('passed'),bool) and c['passed']==bool(passed),'physical pass inconsistent.')
    return all(c['passed'] for c in checks)


def validate_result_contract(job, result):
    reference_contract(job)
    if job['execution_route']=='unsupported':
        _require(result.get('status')!='computed' and result.get('numerical_pass') is not True and
                 result.get('reference_match') is not True and result.get('physical_calls',0)==0 and
                 result.get('operations')==dict(cold_solves=0,fresh_residuals=0,retries=0) and
                 all(c.get('predicted') is None and c.get('passed') is False for c in result.get('reference_checks',[])),
                 'unpaired export cannot claim physical execution or agreement.')
    elif result.get('status')=='computed':
        _require(job['target_kind']=='grid_state' and result.get('numerical_pass') is True and
                 result.get('source_pins_unchanged') is True and result.get('kernel_pins_unchanged') is True and
                 result.get('operations')==dict(cold_solves=1,fresh_residuals=1,retries=0) and
                 result.get('physical_calls')==2 and validate_physical_checks(job,result.get('physical_checks',[])),
                 'computed grid state lacks complete physical evidence.')
        physical={c['name']:c for c in result['physical_checks']}
        values={name:physical['independent_'+name]['reported'] for name in CHANNELS}
        _require(values==physical['restored_output_parity']['reported'],
                 'independent and restored output evidence differs.')
        _require(values['CD']!=0 and _relative(values['CL_CD_ratio'],values['CL']/values['CD'])<=GATES['restored_parity'],
                 'ratio is inconsistent with the coefficient outputs.')
        checks=result.get('reference_checks',[])
        _require(len(checks)==job['expected_outputs'] and
                 {c['name'] for c in checks}=={c['name'] for c in job['observations']} and
                 all(c.get('predicted')==values[c['name']] for c in checks),
                 'reference predictions differ from independently checked physical outputs.')
    return True


def _values(result, condition):
    header=header_values(result,condition)
    return dict(CL=header['avg CL'],CD=header['avg CD'],CL_CD_ratio=header['L/D'])


def _execute(root, job, stage):
    import numpy as np
    import openswing
    from openswing.bridge import dispatch
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition
    from openswing.equilibrium_state import identity,restore
    from openswing.source_coupled import SourceCoupledNetwork
    from openswing.network import network_snapshot
    _require(Path(openswing.__file__).resolve().parent==root/'openswing','worker imported another checkout.')
    row=job['source_row']
    source=reconstruct_source(Path(job['source']).read_bytes(),row['engine_tokens'],row['original_endpoint'])
    _require(hashlib.sha256(source).hexdigest()==row['generated_source_sha256'],'generated model changed.')
    (stage/'generated.asw').write_bytes(source)
    request=dict(action='solve',mode='mounted',source=source.decode('utf-8'),panels=job['panels'],
                 numerics=job['settings'],condition=job['condition'])
    _write(stage/'request.json',request)
    operations=dict(cold_solves=1,fresh_residuals=0,retries=0)
    _write(stage/'operations.json',operations)
    result=dispatch(request)
    _write(stage/'result.json',result)
    model=parse_asw(request['source'],beam_interpolation=job['settings']['beam_interpolation'])
    condition=deepcopy(job['condition'])
    for key in ('powers','controls'):condition[key]={int(k):v for k,v in condition[key].items()}
    network=SourceCoupledNetwork(model,job['panels'],FlightCondition(**condition))
    checks=[]
    def exact(name,actual,expected):
        checks.append(dict(name=name,actual=actual,expected=expected,passed=actual==expected))
    def metric(name,value,**details):
        gate=GATES[PHYSICAL_CHECK_SPECS[name]['gate']]
        checks.append(dict(name=name,metric=value,gate=gate,passed=bool(value<=gate),**details))
    exact('same_operator_identity',identity(network),result['equilibrium_state']['identity'])
    state=restore(network,result['equilibrium_state'])
    exact('restore_without_evaluation',network.nfev,0)
    operations['fresh_residuals']=1;_write(stage/'operations.json',operations)
    residual,data=network.residual(state,detail=True)
    fresh=network_snapshot(network,residual,data);_write(stage/'restored-result.json',fresh)
    exact('one_restored_residual',network.nfev,1)
    exact('converged',result['converged'],True)
    metric('fresh_full_residual',float(np.max(np.abs(residual))))
    exact('source_policy',dict(numerics=result.get('numerics'),operator=result['structural_operator'],
        launch='launch' in result['equilibrium_state']),_expectations()['source_policy'])
    for key in ('force','moment'):
        a,b=result['applied_'+key],result['support_'+key]
        relative=math.hypot(*(x+y for x,y in zip(a,b)))/max(1.,math.hypot(*a)+math.hypot(*b))
        metric(key+'_balance',relative,applied=a,support=b)
    exact('two_shared_power_engines',[dict(power=e['requested_power'],clipped=e['power_clipped']) for e in result['engines']],
          _expectations()['two_shared_power_engines'])
    exact('literal_reference_normalization',model.reference[0].tolist(),[.1536,.24,.64])
    positions=[[float(x) for x in row['engine_tokens'][key][4:7]] for key in ('positive','negative')]
    actual=[e['position'] for e in result['engines']]
    _require(len(actual)==2,'missing engine geometry.')
    metric('engine_position_error',float(np.max(np.abs(np.asarray(actual)-positions))),reported=actual,expected=positions)
    reconstructed=reconstruct_wrenches(result,model.reference[1])
    for name,value in reconstructed.items():
        metric('independent_'+name,_relative(result[name],value),reported=result[name],reconstructed=value)
    clamps=[c['a'] for c in network.constraints if c['kind']=='ground']
    exact('root_clamp_count',len(clamps),1)
    metric('root_clamp_position',float(max((np.max(abs(data['r'][node]-network.rj[node])) for node in clamps),default=1.)))
    metric('root_clamp_frame',float(max((np.max(abs(data['Q'][node]-np.eye(3))) for node in clamps),default=1.)))
    values,restored=_values(result,job['condition']),_values(fresh,job['condition'])
    independent=_values(dict(reconstructed,CDi=result['CDi'],efficiency=result['efficiency']),job['condition'])
    for name in CHANNELS:
        metric('independent_'+name,_relative(values[name],independent[name]),reported=values[name],reconstructed=independent[name])
    exact('finite_outputs',{k:_finite(v) for k,v in values.items()},{k:True for k in CHANNELS})
    parity={k:abs(values[k]-restored[k])/(1.+abs(values[k])) for k in CHANNELS}
    metric('restored_output_parity',max(parity.values()),channels=parity,reported=values,restored=restored)
    validate_physical_checks(job,checks);_write(stage/'physical-checks.json',checks)
    return values,checks


def run(root, job):
    root=Path(root).resolve()
    if job.get('execution_route')=='unsupported':return validate_blocked(root,job)
    verify_reference_sources(root,job)
    stage=Path(tempfile.mkdtemp(prefix='openswing-isae-suite-ap2-'+job['id']+'-'))
    _write(stage/'job.json',job)
    values,physical,error={},[],None
    try:
        values,physical=_execute(root,job,stage)
    except Exception as exc:
        error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
        _write(stage/'exception.json',error)
    operations=json.loads((stage/'operations.json').read_text()) if (stage/'operations.json').exists() else dict(cold_solves=0,fresh_residuals=0,retries=0)
    source_stable=_stable(job['source_pins'])
    kernel_stable=_stable(job['kernel_pins']) and {p['path'] for p in job['kernel_pins']}=={str(p.resolve()) for p in (root/'openswing').glob('*.py')}
    checks=_checks(job,values,'Worker failed or output unavailable.')
    numerical=bool(error is None and physical and validate_physical_checks(job,physical) and source_stable and kernel_stable and
                   operations==job['expected_operations'] and all(c['predicted'] is not None for c in checks))
    result=dict(id=job['id'],case_id='AP-2',adapter='ap2',target_kind=job['target_kind'],
        status='computed' if numerical else 'numerical_failure',numerical_pass=numerical,
        reference_match=numerical and all(c['passed'] for c in checks),reference_checks=checks,
        physical_checks=physical,physical_calls=operations['cold_solves']+operations['fresh_residuals'],operations=operations,
        error=error,source_pins_unchanged=source_stable,kernel_pins_unchanged=kernel_stable,
        artifact_directory=str(stage),artifact_files=[_pin(p) for p in sorted(stage.iterdir()) if p.is_file()],
        historical_settings_recovered=False,unknown_setup=job['unknown_setup'],complete_family_reproduction=False,
        qualifications=job['qualifications'],reference_scope=job['reference_scope'])
    validate_result_contract(job,result);_write(stage/'adapter-result.json',result)
    return result


def mesh_diagnostics(jobs, results):
    groups={}
    for job in jobs:
        if job.get('adapter')=='ap2' and job.get('execution_route')=='worker':
            groups.setdefault(job['coordinate_id'],[]).append(job)
    rows=[]
    for coordinate,pair in sorted(groups.items()):
        pair=sorted(pair,key=lambda j:j['nominal'])
        _require(len(pair)<=2 and len({j['nominal'] for j in pair})==len(pair),'duplicate mesh state.')
        packets=[results.get(j['id'],{}) for j in pair]
        row=dict(coordinate_id=coordinate,jobs=[j['id'] for j in pair],passed=None,acceptance_gate=None,
            scope='Descriptive change at the same source-generated position; no family pass or new mesh gate.')
        if len(pair)!=2 or any(p.get('status')!='computed' for p in packets):
            row.update(status='UNAVAILABLE',channels={})
        else:
            values=[{c['name']:c['predicted'] for c in p['reference_checks']} for p in packets]
            channels={}
            for name in values[0]:
                a,b=(v[name] for v in values);delta=abs(b-a)
                channels[name]=dict(coarse=a,fine=b,abs_change=delta,relative_change=delta/abs(b) if b else (0. if delta==0 else None))
            row.update(status='COMPARED',channels=channels)
        rows.append(row)
    return rows
