"""AE3 native coefficients, derivatives, mass properties and normalized rates.

Planning is source-only. Workers use one cold source-coupled equilibrium and
one restored residual. Native auxiliary outputs use an explicitly checked
moving-source extension. Unresolved embedded ASWING-labelled arrays stay visible.
"""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import tempfile
import traceback

from scripts.isae_suite_ap1 import reconstruct_wrenches

CATALOG = 'docs/validation/isae-ae3-reference.json'
CATALOG_SHA256 = '1a05d227901584bef399e6229281cc0846592e8c178fd663fbac0614ade99a3e'
POLICY = dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-steady-coupled-v1')
GATES = dict(residual=1e-8, relative_balance=1e-7, restored_parity=2e-10, clamp=1e-10)
NOMINALS = (80, 160)
NATIVE_KINDS = ('native_coefficients','native_derivatives','native_mass_properties','native_normalized_rates')
AUXILIARY_NOMINAL = 80
OBSERVABLE_PARAMETERS = ('u','alpha','beta','p','q','r','control.1')
OBSERVABLE_GATES = dict(operator_parity=2e-10,input_refinement=2e-7,directional_tangent=5e-5,
    linear_residual=1e-8,output_refinement=1e-8,mass_recovery=2e-10,
    reciprocal_condition=1e-10,base_residual=1e-8)
NAMES = ('CX', 'CY', 'CL', 'Cl', 'Cm', 'Cn')
REFERENCE = [[.185,.15,1.2192],[0.,0.,0.],[0.,0.,0.],[0.,0.,0.]]
WEIGHTS = [[1.,y,.0122,y,0.]+[0.]*12 for y in (.6096,-.6096)]
MANDATORY = [-.6096,-.8*.6096,0.,.8*.6096,.6096]
QUALIFICATIONS = [
    'All six native finite F1=+1 file-unit states are retained. This is a finite-control static comparison, not a zero-control derivative.',
    'Roll_rate.sh names Straight_20O and the six archived speeds; !!F1 1.0 applies to all stacked points. The fmat title Mowe_temp differs from the retained model title, so exact historical input/build identity is not established.',
    'The original model bytes, Weight scale0, section slopes, stiffness, reference area.185, chord.15 and span1.2192 remain unchanged; no primary-experiment normalization or sign conversion is applied.',
    'Nominal80/160 current cosine intervals were selected prospectively. The exact root and flap discontinuities remain mandatory; historical NODE arrays are unknown.',
    'Mounted zero-rate states use literal rhoSL1.2256, declared TAS equal to driver IAS, Mach0, identity pose, gravity[0,0,-9.81], no ground images, frozen-jig influences and core.25. Frozen influences follow the documented OPER K/F default and OpenSwing default; the archived mask/startup, atmosphere and exact K/F state remain conditional.',
    'Six coefficients use distributed aerodynamic wrench, literal qS and reference lengths, stability x-forward/z-down axes, and CL=-Fz/qS. Direct point/engine forces are kept separately.',
    'Native auxiliary outputs use nominal80 with a zero-rate moving-source parity check. Derivatives hold accelerations fixed, use fixed base axes/qS, radians and normalized rates, and reuse one full coupled factorization. The archived MM response convention remains conditional.',
    'Mass tensors are the separately reported steady §8.7 integrals, not an aggregate replacement for the structural descriptor. The verified zero-real-mass model uses the native origin display convention for its undefined real CG.',
    'Embedded original and modified-ASWING-labelled arrays are separate source-qualified targets, blocked on exact producer and input conventions. Modified-code arrays are not equivalent to native ASWING exports; experimental arrays are excluded.',
    'Original printed half-last-place gates remain unchanged. Mesh changes are descriptive; numerical success does not establish historical setup or full-family reproduction.']
UNKNOWN_SETUP = ['historical exact model/build despite displayed Mowe_temp title', 'constraint mask %4 23/P/d and startup branch',
    'IAS/TAS and atmosphere implementation', 'K/F, wake core and historical node arrays', 'embedded-array exact producer/input conventions']
BLOCKERS = {
    'embedded_source_array': ('EMBEDDED_PRODUCER_UNRESOLVED', 'The ASWING-labelled postprocessor array is retained, but exact producing input/build/constraint and observable conventions are not uniquely recovered.'),
    'model_inventory': ('NO_PAIRED_EXPORT', 'No retained native numerical export is paired with this original model; zero targets are not a pass.')}
PHYSICAL_CHECK_SPECS = {
    **{name:dict(kind='exact') for name in ('same_operator_identity','restore_without_evaluation','one_restored_residual',
        'converged','no_parser_diagnostics','cold_operating_setup','restored_operating_setup','restored_condition','source_policy','literal_source_hash',
        'literal_reference','literal_weight_rows','inactive_null_weights','no_engines_or_extra_loads','mesh_panel_setting',
        'mandatory_stations_present','root_clamp_count','finite_coefficients')},
    'fresh_full_residual':dict(kind='metric',gate='residual'),
    **{name:dict(kind='balance',gate='relative_balance') for name in ('force_balance','moment_balance')},
    **{name:dict(kind='clamp',gate='clamp') for name in ('root_clamp_position','root_clamp_frame')},
    **{'independent_'+name:dict(kind='vector',gate='restored_parity') for name in ('distributed_aero_force','distributed_aero_moment','force','moment')},
    'independent_coefficient_mapping':dict(kind='coefficients',gate='restored_parity'),
    'restored_coefficient_parity':dict(kind='parity',gate='restored_parity')}
REQUIRED_PHYSICAL_CHECKS = tuple(PHYSICAL_CHECK_SPECS)


def _require(ok, message):
    if not ok: raise ValueError('AE3 '+message)


def _finite(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def _pin(path):
    path=Path(path).resolve(); raw=path.read_bytes()
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def _write(path, value):
    Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def _decimal(token):
    value=Decimal(token.replace('D','E').replace('d','e'))
    _require(value.is_finite(), 'nonfinite native target.')
    half=Decimal(5).scaleb(value.as_tuple().exponent-1)
    return float(value),float(half),str(value),str(half)


def _context(root):
    root=Path(root).resolve(); path=root/CATALOG
    _require(_pin(path)['sha256']==CATALOG_SHA256, 'reference catalog changed; re-audit extraction.')
    catalog=json.loads(path.read_text())
    _require(catalog['schema_version']==1 and catalog['family_id']=='AE-3', 'invalid reference catalog schema.')
    pins=[]
    for item in catalog['source_pins']:
        actual=_pin(root/item['path'])
        _require(all(actual[k]==item[k] for k in ('bytes','sha256')), 'original/extractor source changed: '+item['path'])
        pins.append(actual)
    for p in (path,Path(__file__),root/'scripts/isae_suite_ap1.py',root/'scripts/isae_ae3_observables.py'):
        pin=_pin(p)
        if not any(item['path']==pin['path'] for item in pins): pins.append(pin)
    return root,catalog,pins


def _observation(item, *, name=None):
    result=deepcopy(item)
    if name is not None:
        result['source_name']=result.get('name'); result['name']=name
    expected,tolerance,exact,half=_decimal(result['expected_token'])
    _require(result['expected']==expected and result['tolerance']==tolerance, 'catalog target/precision changed.')
    result.update(exact_decimal_expected=exact,exact_decimal_tolerance=half)
    return result


def _jobs(root,catalog,pins,only=None):
    kernels=None
    def packet(identifier,kind,coordinate,observations,rows,model,table,driver=None,nominal=None,condition=None,extra=None):
        nonlocal kernels
        if only is not None and only!=identifier: return None
        worker=kind in NATIVE_KINDS
        if worker and kernels is None: kernels=[_pin(p) for p in sorted((root/'openswing').glob('*.py'))]
        job=dict(id=identifier,case_id='AE-3',adapter='ae3',target_kind=kind,
            source_group='native_fmat' if kind.startswith('native_') else 'embedded_postprocessor' if kind=='embedded_source_array' else 'model_inventory',
            coordinate_id=coordinate,execution_route='worker' if worker else 'unsupported',model_path=model,
            source=None if model is None else str(root/model),table_path=table,driver_path=driver,
            observations=observations,reference_rows=rows,expected_outputs=len(observations),
            nominal=nominal,mesh='none' if nominal is None else f'm{nominal}',
            panels=None if nominal is None else dict(default=nominal,beams={'1':dict(count=nominal,spacing='cosine')}),
            settings=deepcopy(POLICY) if worker else None,condition=condition,gravity=[0.,0.,-9.81] if worker else None,
            source_pins=pins,kernel_pins=kernels if worker else [],numerical_gates=deepcopy(GATES) if worker else None,
            expected_operations=dict(cold_solves=int(worker),fresh_residuals=int(worker),retries=0),
            suggested_cap_seconds=180,original_file_modified=False,historical_settings_recovered=False,
            complete_family_reproduction=False,qualifications=list(QUALIFICATIONS),unknown_setup=list(UNKNOWN_SETUP),
            reference_scope='Native source outputs and separately qualified embedded arrays; full family remains open.')
        if worker:
            job.update(literal_model_sha256=_pin(root/model)['sha256'],literal_reference=deepcopy(REFERENCE),
                literal_weight_rows=deepcopy(WEIGHTS),mandatory_stations=list(MANDATORY),root_position=[-.0523,0.,0.],
                expected_elements=nominal+2,expected_nodes=nominal+3,
                mesh_scope='Prospective current80/160 cosine intervals; historical NODE arrays unrecovered.')
            if kind!='native_coefficients':
                job['expected_operations']['observable_batches']=1
                job['observable_settings']=dict(structural_operator='drela-moving-airflow-v1',
                    response='fixed_acceleration',derivative_parameters=['u','alpha','beta','p','q','r','control.1'],
                    mass_report='Drela steady §8.7; verified zero real mass/inertia',
                    normalization='fixed base stability axes and qS; radians, normalized rates, file F1 units')
        else:
            job['blocker_code'],job['unsupported_reason']=BLOCKERS[kind]
        if kind=='model_inventory':
            job['required_components']=[];job['expected_operations']['cold_bridge_calls']=0
        if extra: job.update(extra)
        return job
    for state in catalog['native_exports']:
        coordinate=state['id']; allobs=state['observations']; meta=state['condition']
        condition=dict(speed=meta['speed'],alpha=meta['alpha_deg'],beta=meta['beta_deg'],density=meta['density'],mach=meta['mach'],
            controls={'1':meta['flap1']},powers={},attitude=[0.,0.,0.],position_earth=[0.,0.,0.],
            rates=[0.,0.,0.],acceleration=[0.,0.,0.],angular_acceleration=[0.,0.,0.],ground_effect=0,
            ground_normal=[0.,0.,1.],freeze_influences=True,wake_core_ratio=.25,circulation_modes={'1':0},
            stall=True,stall_factor=40.,stall_width=.05,aero_lag=True)
        _require(meta['angular_rates_deg_s']==[0.,0.,0.] and condition['controls']=={'1':1.}, 'unsupported native rates/control.')
        groups=[('native_coefficients',{'base_coefficient'},NOMINALS),
                ('native_derivatives',{'stability_derivative','control_derivative'},(AUXILIARY_NOMINAL,)),
                ('native_mass_properties',{'mass_inertia','centroid'},(AUXILIARY_NOMINAL,)),
                ('native_normalized_rates',{'normalized_rate'},(AUXILIARY_NOMINAL,))]
        for kind,categories,nominals in groups:
            observations=[_observation(item) for item in allobs if item['category'] in categories]
            if kind=='native_coefficients': observations=sorted(observations,key=lambda item:NAMES.index(item['name']))
            for nominal in nominals:
                suffix=f'-m{nominal}' if kind=='native_coefficients' else ''
                row=deepcopy(state['reference_row']); row['row_number']=state['operating_point']
                job=packet(f'AE-3-{coordinate}-{kind.removeprefix("native_")}{suffix}',kind,coordinate,observations,[row],
                    state['model_path'],state['table_path'],state['driver_path'],nominal,deepcopy(condition) if nominal else None,
                    dict(native_context=deepcopy(state['context']),native_operating_point=state['operating_point']))
                if job: yield job
    for index,series in enumerate(catalog['postprocessor']['series'],1):
        coordinate=f'embedded-{index:02d}'
        observations=[_observation(item,name=f'{coordinate}-value-{j:03d}') for j,item in enumerate(series['values'],1)]
        rows=[dict(row_number=j,series_id=coordinate,source_line=item['source_line'],source_column_1based=item.get('source_column_1based'))
              for j,item in enumerate(observations,1)]
        job=packet('AE-3-'+coordinate,'embedded_source_array',coordinate,observations,rows,None,series['source_path'],
            extra=dict(series_id=coordinate,source_variant=series['variant'],embedded_kind=series['kind'],embedded_series=deepcopy(series)))
        if job: yield job
    for entry in catalog['model_inventory']:
        if entry['paired_native_exports']: continue
        coordinate=Path(entry['model_path']).stem
        job=packet('AE-3-model-'+coordinate,'model_inventory',coordinate,[],[],entry['model_path'],None,
            extra=dict(model_inventory=deepcopy(entry)))
        if job: yield job


def plan(root):
    root,catalog,pins=_context(root); jobs=list(_jobs(root,catalog,pins))
    _require(sum(j['expected_outputs'] for j in jobs)==725 and sum(j['execution_route']=='worker' for j in jobs)==30,
        'complete AE3 scalar/worker scope changed.')
    _require(len({j['id'] for j in jobs})==len(jobs), 'duplicate job identifiers.')
    return jobs


def verify_reference_sources(root,job):
    root,catalog,pins=_context(root); canonical=list(_jobs(root,catalog,pins,only=job.get('id')))
    _require(len(canonical)==1 and all(job.get(k)==v for k,v in canonical[0].items()),
        'job differs from original targets, source pairing or declared setup/code.')
    return True


def reference_contract(job):
    _require(job.get('case_id')=='AE-3' and job.get('adapter')=='ae3' and
        job.get('target_kind') in {*NATIVE_KINDS,*BLOCKERS}, 'invalid family/scope.')
    obs=job.get('observations',[]); names=[item['name'] for item in obs]
    _require(len(names)==len(set(names))==job['expected_outputs'], 'missing/duplicate reference channels.')
    if job['target_kind']=='native_coefficients':
        _require(tuple(names)==NAMES and job['nominal'] in NOMINALS and job['settings']==POLICY and job['numerical_gates']==GATES,
            'six-coefficient policy/mesh/gates changed.')
    elif job['target_kind'] in NATIVE_KINDS:
        _require(job['nominal']==AUXILIARY_NOMINAL and job['settings']==POLICY and job['numerical_gates']==GATES,
            'native auxiliary policy/mesh/gates changed.')
    for item in obs:
        value,half,exact,precision=_decimal(item['expected_token'])
        _require((item['expected'],item['tolerance'],item['exact_decimal_expected'],item['exact_decimal_tolerance'])==
                 (value,half,exact,precision), 'native printed target/precision changed.')
    return {item['name']:{k:v for k,v in item.items() if k!='name'} for item in obs}


def _checks(job,values,reason=None):
    rows=[]
    for name,ref in reference_contract(job).items():
        value=values.get(name); valid=_finite(value); error=abs(value-ref['expected']) if valid else None
        rows.append(dict(name=name,**ref,predicted=value if valid else None,abs_error=error,comparison='<=',
            passed=bool(valid and error<=ref['tolerance']),unavailable_reason=None if valid else reason))
    return rows


def validate_blocked(root,job):
    _require(job['execution_route']=='unsupported', 'coefficient state requires worker.')
    verify_reference_sources(root,job)
    return dict(id=job['id'],case_id='AE-3',adapter='ae3',status='unsupported',numerical_pass=False,reference_match=False,
        reference_checks=_checks(job,{},job['unsupported_reason']),physical_checks=[],operations=deepcopy(job['expected_operations']),
        physical_calls=0,production_imports=0,source_pins_unchanged=True,kernel_pins_unchanged=True,
        blocker_code=job['blocker_code'],unsupported_reason=job['unsupported_reason'],complete_family_reproduction=False)


def coefficients(force,moment,alpha,qS,chord,span):
    """Literal stability-axis normalization, independent of production helper."""
    _require(len(force)==len(moment)==3 and all(_finite(x) for x in list(force)+list(moment)+[alpha,qS,chord,span]) and
             min(qS,chord,span)>0, 'invalid coefficient wrench/reference.')
    c,s=math.cos(math.radians(alpha)),math.sin(math.radians(alpha)); x,y,z=force; mx,my,mz=moment
    return dict(CX=(-c*x-s*z)/qS,CY=y/qS,CL=(-s*x+c*z)/qS,
        Cl=(-c*mx-s*mz)/(qS*span),Cm=my/(qS*chord),Cn=(s*mx-c*mz)/(qS*span))


def _relative(a,b):
    if not isinstance(a,list): a,b=[a],[b]
    _require(isinstance(b,list) and len(a)==len(b)>0 and all(_finite(x) for x in a+b), 'invalid independent evidence.')
    return max(abs(x-y) for x,y in zip(a,b))/(1.+max(map(abs,a+b)))


def _setup(result):
    g,i=result['ground_plane'],result['aerodynamic_influences']
    return dict(ground_flag=g['flag'],normal_earth=g['normal_earth'],ground_offset=g['offset'],position_earth=g['position_earth'],
        attitude=g['attitude'],frozen=i['frozen'],wind_angles=i['wind_angles'],pg_mach=i['pg_mach'],core_ratio=result['wake_core']['ratio'],
        density=result['atmosphere']['density'],dynamic_pressure=result['atmosphere']['dynamic_pressure'],gravity_body=result['gravity_body'])


def _expectations(job):
    c=job['condition'];setup=dict(ground_flag=0,normal_earth=[0.,0.,1.],ground_offset=0.,position_earth=[0.,0.,0.],attitude=[0.,0.,0.],
        frozen=c['freeze_influences'],wind_angles=[0.,0.] if c['freeze_influences'] else [c['alpha'],c['beta']],
        pg_mach=0.,core_ratio=.25,density=c['density'],
        dynamic_pressure=.5*c['density']*c['speed']**2,gravity_body=job['gravity'])
    return dict(restore_without_evaluation=0,one_restored_residual=1,converged=True,no_parser_diagnostics=[],cold_operating_setup=setup,
        restored_operating_setup=setup,restored_condition=c,source_policy=dict(numerics=POLICY,operator=POLICY['structural_operator'],launch=False),
        literal_source_hash=job['literal_model_sha256'],literal_reference=REFERENCE,literal_weight_rows=WEIGHTS,inactive_null_weights=0,
        no_engines_or_extra_loads=dict(engines=0,loads=0,struts=0,hinges=0,sensors=0),mesh_panel_setting=dict(panels=job['panels'],nodes=job['expected_nodes'],elements=job['expected_elements']),
        mandatory_stations_present={str(t):True for t in MANDATORY},root_clamp_count=1,finite_coefficients={name:True for name in NAMES})


def validate_physical_checks(job,checks):
    _require(job['numerical_gates']==GATES,'physical gates changed.')
    names=[item.get('name') for item in checks]
    _require(len(names)==len(set(names))==len(REQUIRED_PHYSICAL_CHECKS) and set(names)==set(REQUIRED_PHYSICAL_CHECKS),
        'physical check set incomplete or duplicated.')
    expected=_expectations(job)
    for item in checks:
        name=item['name']; spec=PHYSICAL_CHECK_SPECS[name]
        if spec['kind']=='exact':
            _require('actual' in item and 'expected' in item,'missing exact evidence.')
            if name in expected: _require(item['expected']==expected[name],'physical expectation changed.')
            passed=item['actual']==item['expected']
        else:
            metric=item.get('metric');gate=GATES[spec['gate']]
            _require(_finite(metric) and metric>=0 and item.get('gate')==gate,'invalid metric/gate.')
            if spec['kind']=='vector': _require(metric==_relative(item['reported'],item['reconstructed']),'wrench metric changed.')
            elif spec['kind']=='balance':
                a,b=item['applied'],item['support']
                _require(len(a)==len(b)==3 and all(_finite(x) for x in a+b),'invalid balance evidence.')
                value=math.hypot(*(x+y for x,y in zip(a,b)))/max(1.,math.hypot(*a)+math.hypot(*b))
                _require(math.isclose(metric,value,rel_tol=2e-15,abs_tol=1e-30),'balance metric changed.')
            elif spec['kind']=='clamp':
                reference=job['root_position'] if name.endswith('position') else [1.,0.,0.,0.,1.,0.,0.,0.,1.]
                _require(item['expected']==reference and len(item['reported'])==len(reference) and all(_finite(x) for x in item['reported']) and
                         metric==max(abs(x-y) for x,y in zip(item['reported'],reference)),'clamp metric changed.')
            elif spec['kind']=='coefficients':
                c=job['condition'];qS=.5*c['density']*c['speed']**2*REFERENCE[0][0]
                values=coefficients(item['force'],item['moment'],c['alpha'],qS,REFERENCE[0][1],REFERENCE[0][2])
                _require(item['reconstructed']==values and set(item['reported'])==set(NAMES),'coefficient evidence changed.')
                channels={key:_relative(item['reported'][key],values[key]) for key in NAMES}
                _require(item['channels']==channels and metric==max(channels.values()),'coefficient metric changed.')
            elif spec['kind']=='parity':
                a,b=item['reported'],item['restored'];_require(set(a)==set(b)==set(NAMES),'restored channels incomplete.')
                channels={key:_relative(a[key],b[key]) for key in NAMES}
                _require(item['channels']==channels and metric==max(channels.values()),'restored metric changed.')
            passed=metric<=gate
        _require(isinstance(item.get('passed'),bool) and item['passed'] is bool(passed),'physical flag changed.')
    return all(item['passed'] for item in checks)


def validate_result_contract(job,result):
    contract=reference_contract(job); checks=result.get('reference_checks',[]); names=[item.get('name') for item in checks]
    _require(len(names)==len(set(names)) and set(names)<=set(contract),'duplicate/unknown result channels.')
    for item in checks:
        _require(all(item.get(k)==v for k,v in contract[item['name']].items()) and item.get('comparison','<=')=='<=','saved target changed.')
    if job['execution_route']=='unsupported':
        _require(result.get('status')!='computed' and result.get('numerical_pass') is not True and result.get('numerical_passed') is not True and
            result.get('reference_match') is not True and result.get('physical_calls',0)==result.get('physical_solver_calls',0)==0 and
            result.get('operations')==job['expected_operations'] and all(item.get('predicted') is None and item.get('passed') is False for item in checks),
            'blocked scope cannot claim physics or predictions.')
        if result.get('status')=='unsupported': _require(len(checks)==len(contract) and result.get('source_pins_unchanged') is True,'incomplete blocked record.')
    elif result.get('status')=='computed':
        _require(job['target_kind'] in NATIVE_KINDS and result.get('numerical_pass') is True and result.get('source_pins_unchanged') is True and
            result.get('kernel_pins_unchanged') is True and result.get('physical_calls')==2+int(job['target_kind']!='native_coefficients') and
            result.get('operations')==job['expected_operations'] and validate_physical_checks(job,result.get('physical_checks',[])),
            'computed state lacks complete physical evidence.')
        physical={item['name']:item for item in result['physical_checks']}; mapped=physical['independent_coefficient_mapping']
        values=mapped['reported']
        _require(mapped['force']==physical['independent_distributed_aero_force']['reconstructed'] and
            mapped['moment']==physical['independent_distributed_aero_moment']['reconstructed'] and
            values==physical['restored_coefficient_parity']['reported'],'prediction differs from checked aerodynamic wrench.')
        if job['target_kind']=='native_coefficients':
            _require(len(checks)==6 and all(item['predicted']==values[item['name']] for item in checks),
                'coefficient predictions differ from checked wrench.')
        else:
            report=result.get('observable_report')
            validate_observable_report(job,report,values)
            _require(len(checks)==len(contract) and all(item['predicted']==report['values'][item['name']] for item in checks),
                'auxiliary predictions differ from checked source observables.')
        for item in checks:
            error=abs(item['predicted']-item['expected'])
            _require(item['abs_error']==error and item['passed'] is (error<=item['tolerance']),'printed comparison flag changed.')
        _require(result.get('reference_match') is all(item['passed'] for item in checks),'whole-state flag changed.')
    return True


def _stable(pins):
    try: return all(_pin(item['path'])==item for item in pins)
    except OSError: return False


def validate_observable_report(job,report,base_values):
    """Validate numerical evidence independently of native agreement."""
    observable_gates,PARAMETERS=OBSERVABLE_GATES,OBSERVABLE_PARAMETERS
    _require(isinstance(report,dict) and report.get('source_operator')=='drela-moving-airflow-v1' and
        report.get('base_operator')==POLICY['structural_operator'] and report.get('base_coefficients')==base_values and
        report.get('numerical_gates')==observable_gates,'missing/changed auxiliary source evidence.')
    checks=report.get('checks',[]);names=[item.get('name') for item in checks]
    required={'base_residual','base_operator_parity','base_output_parity','off_state_operator_parity_0',
              'off_state_operator_parity_1','apparent_mass_acceleration_recovery'}
    expected_gates={name:observable_gates['operator_parity'] for name in required}
    expected_gates.update(base_residual=observable_gates['base_residual'],apparent_mass_acceleration_recovery=observable_gates['mass_recovery'])
    derivative=job['target_kind']=='native_derivatives'
    if derivative:
        expected_gates.update(reciprocal_condition_gate=1.,analytic_control_partial=observable_gates['input_refinement'])
        expected_gates.update({f'full_tangent_direction_{i}':observable_gates['directional_tangent'] for i in range(2)})
        for group in ('input_refinement','linear_residual','output_refinement'):
            expected_gates.update({group+'_'+parameter:observable_gates[group] for parameter in PARAMETERS})
        _require(report.get('parameters')==list(PARAMETERS) and report.get('coefficient_rows')==list(NAMES) and
            report.get('response')=='fixed_acceleration' and report.get('axes')=='stability' and
            _finite(report.get('reciprocal_condition')) and report['reciprocal_condition']>=observable_gates['reciprocal_condition'],
            'derivative conventions/rank evidence changed.')
    _require(set(names)==set(expected_gates) and len(names)==len(set(names)),'incomplete/duplicate auxiliary checks.')
    for item in checks:
        value=item.get('metric');gate=expected_gates[item['name']]
        _require(_finite(value) and 0<=value<=gate and item.get('gate')==gate and item.get('passed') is True,
                 'failed or changed auxiliary numerical gate.')
    _require(report.get('factorization_count')==int(derivative) and report.get('response_columns')==(7 if derivative else 0),
        'derivative factorization/column accounting changed.')
    _require(report.get('mass_properties',{}).get('zero_real_mass_verified') is True and
        report['mass_properties'].get('physical_real_centroid') is None,'zero-real-mass convention lost.')
    mass=report['mass_properties']
    _require(mass.get('origin')==mass.get('reported_real_centroid')==mass.get('apparent_reference')==[0.,0.,0.],
        'mass reporting reference changed.')
    records=mass.get('real_record_maxima',[])
    _require(records and all(set(row)=={'mass','inertia','spin'} and all(_finite(x) and x==0 for x in row.values())
                            for row in records),'nonzero or missing real-mass evidence.')
    def matrix(key,rows,cols,source=report):
        value=source.get(key,[])
        _require(isinstance(value,list) and len(value)==rows and all(isinstance(row,list) and len(row)==cols and
            all(_finite(x) for x in row) for row in value),'invalid observable matrix: '+key)
        return value
    apparent=matrix('apparent_spatial_matrix',6,6,mass)
    recovered=matrix('acceleration_recovered_apparent_spatial_matrix',6,6,mass)
    recovery=max(abs(a-b) for ar,br in zip(recovered,apparent) for a,b in zip(ar,br))/max(1.,max(abs(x) for row in apparent for x in row))
    evidence={row['name']:row for row in checks}
    _require(math.isclose(evidence['apparent_mass_acceleration_recovery']['metric'],recovery,rel_tol=2e-15,abs_tol=1e-30),
        'acceleration recovery metric changed.')
    values={f'{prefix}_{axis}':0. for prefix in ('mass_centroid','center_of_mass','jig_center_of_mass') for axis in 'xyz'}
    values.update({'real_mass_'+axis:0. for axis in ('xx','yy','zz')})
    for suffix,i,j in (('xx',0,0),('xy',0,1),('xz',0,2),('yy',1,1),('yz',1,2),('zz',2,2)):
        values['apparent_mass_'+suffix]=apparent[i][j]
        for about in ('origin','centroid'):
            values[f'real_inertia_{about}_{suffix}']=0.
            values[f'apparent_inertia_{about}_{suffix}']=apparent[i+3][j+3]
    c=job['condition'];chord,span=REFERENCE[0][1:];a=math.radians(c['alpha']);wx,wy,wz=c['rates']
    rates=(wx,wy,wz,-math.cos(a)*wx-math.sin(a)*wz,wy,math.sin(a)*wx-math.cos(a)*wz)
    labels=('body_Wx_b_2V','body_Wy_c_2V','body_Wz_b_2V','stability_p_b_2V','stability_q_c_2V','stability_r_b_2V')
    values.update({name:rate*length/(2*c['speed']) for name,rate,length in zip(labels,rates,(span,chord,span)*2)})
    if derivative:
        derivatives=matrix('coefficient_derivatives',6,7)
        values.update({name+suffix:derivatives[i][j] for i,name in enumerate(NAMES)
                       for j,suffix in enumerate(('u','a','b','p','q','r','dF1'))})
        _require(report.get('normalization')==dict(qS=.5*c['density']*c['speed']**2*REFERENCE[0][0],chord=chord,span=span,
            axes='fixed base stability axes',angles='radians',rates='p b/2V, q c/2V, r b/2V',control='file F1 units'),
            'derivative normalization changed.')
        _require(evidence['reciprocal_condition_gate']['metric']==observable_gates['reciprocal_condition']/report['reciprocal_condition'],
            'derivative rank metric changed.')
    saved=report.get('values',{})
    _require(set(saved)==set(values) and all(_finite(saved[k]) and math.isclose(saved[k],v,rel_tol=2e-15,abs_tol=1e-30)
            for k,v in values.items()),'auxiliary predictions differ from physical tensor/rate/derivative mapping.')
    _require(all(_finite(report.get('values',{}).get(name)) for name in reference_contract(job)),
        'missing or nonfinite auxiliary predictions.')
    return True


def _execute(root,job,stage):
    import numpy as np
    import openswing
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition
    from openswing.bridge import dispatch
    from openswing.source_coupled import SourceCoupledNetwork
    from openswing.equilibrium_state import identity,matching_identity,warm_start_recipe,restore
    from openswing.network import network_snapshot
    from openswing.point_objects import active_weights
    _require(Path(openswing.__file__).resolve().parent==root/'openswing','worker imported another checkout.')
    raw=Path(job['source']).read_bytes();_require(hashlib.sha256(raw).hexdigest()==job['literal_model_sha256'],'literal source changed.')
    request=dict(action='solve',mode='mounted',source=raw.decode(),panels=job['panels'],numerics=job['settings'],condition=job['condition'],gravity=job['gravity'])
    _write(stage/'request.json',request)
    model=parse_asw(raw.decode(),beam_interpolation=POLICY['beam_interpolation']);condition=deepcopy(job['condition'])
    for key in ('powers','controls','circulation_modes'):condition[key]={int(k):v for k,v in condition[key].items()}
    preflight=SourceCoupledNetwork(model,job['panels'],FlightCondition(**condition),job['gravity'])
    stations=preflight.station_nodes[1][0].tolist()
    _require(preflight.nn==job['expected_nodes'] and preflight.ne==job['expected_elements'] and
             all(t in stations for t in MANDATORY) and not model.diagnostics and
             [row.tolist() for row in model.records['weight']]==WEIGHTS and not active_weights(model),'literal preflight failed.')
    _write(stage/'preflight.json',dict(nodes=preflight.nn,elements=preflight.ne,stations=stations,raw_weight_rows=WEIGHTS,residuals=preflight.nfev))
    operations=dict(cold_solves=1,fresh_residuals=0,retries=0);_write(stage/'operations.json',operations)
    result=dispatch(request);_write(stage/'result.json',result)
    recipe=warm_start_recipe(model,job['panels'],result['equilibrium_state'])
    network=SourceCoupledNetwork(model,job['panels'],FlightCondition(**condition),job['gravity'],mesh_recipe=recipe)
    _require(matching_identity(result['equilibrium_state']['identity'],identity(network)),'restored operator/mesh changed.')
    checks=[]
    def exact(name,actual,expected):checks.append(dict(name=name,actual=actual,expected=expected,passed=actual==expected))
    def metric(name,value,**evidence):
        gate=GATES[PHYSICAL_CHECK_SPECS[name]['gate']];checks.append(dict(name=name,metric=value,gate=gate,passed=bool(value<=gate),**evidence))
    exact('same_operator_identity',identity(network),result['equilibrium_state']['identity'])
    state=restore(network,result['equilibrium_state']);exact('restore_without_evaluation',network.nfev,0)
    operations['fresh_residuals']=1;_write(stage/'operations.json',operations)
    residual,data=network.residual(state,detail=True);fresh=network_snapshot(network,residual,data);_write(stage/'restored-result.json',fresh)
    exact('one_restored_residual',network.nfev,1);exact('converged',result['converged'],True);exact('no_parser_diagnostics',list(model.diagnostics),[]);metric('fresh_full_residual',float(np.max(abs(residual))))
    expected=_expectations(job)
    exact('cold_operating_setup',_setup(result),expected['cold_operating_setup']);exact('restored_operating_setup',_setup(fresh),expected['restored_operating_setup'])
    restored={key:getattr(network.condition,key) for key in job['condition']}
    for key in ('powers','controls','circulation_modes'):restored[key]={str(k):v for k,v in restored[key].items()}
    exact('restored_condition',restored,job['condition'])
    exact('source_policy',dict(numerics=result.get('numerics'),operator=result['structural_operator'],launch='launch' in result['equilibrium_state']),expected['source_policy'])
    exact('literal_source_hash',hashlib.sha256(Path(job['source']).read_bytes()).hexdigest(),expected['literal_source_hash'])
    exact('literal_reference',model.reference.tolist(),REFERENCE);exact('literal_weight_rows',[row.tolist() for row in model.records['weight']],WEIGHTS)
    exact('inactive_null_weights',len(active_weights(model)),0)
    exact('no_engines_or_extra_loads',dict(engines=len(result['engines']),loads=len(network.loads),struts=len(result['struts']),hinges=len(result['hinges']),sensors=len(result['sensors'])),expected['no_engines_or_extra_loads'])
    exact('mesh_panel_setting',dict(panels=result['mesh_discretization']['settings'],nodes=network.nn,elements=network.ne),expected['mesh_panel_setting'])
    exact('mandatory_stations_present',{str(t):t in network.station_nodes[1][0] for t in MANDATORY},expected['mandatory_stations_present'])
    for name in ('force','moment'):
        a,b=result['applied_'+name],result['support_'+name]
        metric(name+'_balance',math.hypot(*(x+y for x,y in zip(a,b)))/max(1.,math.hypot(*a)+math.hypot(*b)),applied=a,support=b)
    clamps=[c['a'] for c in network.constraints if c['kind']=='ground'];exact('root_clamp_count',len(clamps),1);_require(len(clamps)==1,'root clamp changed.')
    p,q=data['r'][clamps[0]].tolist(),data['Q'][clamps[0]].ravel().tolist();eye=[1.,0.,0.,0.,1.,0.,0.,0.,1.]
    metric('root_clamp_position',max(abs(x-y) for x,y in zip(p,job['root_position'])),reported=p,expected=job['root_position'])
    metric('root_clamp_frame',max(abs(x-y) for x,y in zip(q,eye)),reported=q,expected=eye)
    wrench=reconstruct_wrenches(result,model.reference[1])
    for name in ('distributed_aero_force','distributed_aero_moment','force','moment'):
        metric('independent_'+name,_relative(result[name],wrench[name]),reported=result[name],reconstructed=wrench[name])
    c=job['condition'];qS=.5*c['density']*c['speed']**2*REFERENCE[0][0]
    def mapped(packet):return coefficients(packet['distributed_aero_force'],packet['distributed_aero_moment'],c['alpha'],qS,REFERENCE[0][1],REFERENCE[0][2])
    values,independent,restored_values=mapped(result),mapped(wrench),mapped(fresh)
    channels={name:_relative(values[name],independent[name]) for name in NAMES}
    metric('independent_coefficient_mapping',max(channels.values()),reported=values,reconstructed=independent,channels=channels,
        force=wrench['distributed_aero_force'],moment=wrench['distributed_aero_moment'])
    exact('finite_coefficients',{name:_finite(value) for name,value in values.items()},expected['finite_coefficients'])
    channels={name:_relative(values[name],restored_values[name]) for name in NAMES}
    metric('restored_coefficient_parity',max(channels.values()),reported=values,restored=restored_values,channels=channels)
    validate_physical_checks(job,checks);_write(stage/'physical-checks.json',checks)
    if job['target_kind']!='native_coefficients':
        from scripts.isae_ae3_observables import complete_observables
        operations['observable_batches']=1;_write(stage/'operations.json',operations)
        report=complete_observables(network,state,data,values,derivatives=job['target_kind']=='native_derivatives')
        validate_observable_report(job,report,values);_write(stage/'observable-report.json',report)
        values={**values,**report['values']}
    return values,checks


def run(root,job):
    root=Path(root).resolve()
    if job['execution_route']=='unsupported':return validate_blocked(root,job)
    verify_reference_sources(root,job)
    stage=Path(tempfile.mkdtemp(prefix='openswing-isae-suite-ae3-'+job['id']+'-'));_write(stage/'job.json',job)
    values,physical,error={},[],None
    try:values,physical=_execute(root,job,stage)
    except Exception as exc:
        error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc());_write(stage/'exception.json',error)
    operations=json.loads((stage/'operations.json').read_text()) if (stage/'operations.json').exists() else dict(cold_solves=0,fresh_residuals=0,retries=0)
    checks=_checks(job,values,'Worker failed or output unavailable.');source_stable=_stable(job['source_pins'])
    kernel_stable=_stable(job['kernel_pins']) and {item['path'] for item in job['kernel_pins']}=={str(p.resolve()) for p in (root/'openswing').glob('*.py')}
    numerical=bool(error is None and physical and validate_physical_checks(job,physical) and source_stable and kernel_stable and
        operations==job['expected_operations'] and all(item['predicted'] is not None for item in checks))
    result=dict(id=job['id'],case_id='AE-3',adapter='ae3',status='computed' if numerical else 'numerical_failure',numerical_pass=numerical,
        reference_match=numerical and all(item['passed'] for item in checks),reference_checks=checks,physical_checks=physical,
        physical_calls=operations['cold_solves']+operations['fresh_residuals']+operations.get('observable_batches',0),operations=operations,source_pins_unchanged=source_stable,
        kernel_pins_unchanged=kernel_stable,error=error,artifact_directory=str(stage),artifact_files=[_pin(p) for p in sorted(stage.iterdir()) if p.is_file()],
        historical_settings_recovered=False,complete_family_reproduction=False,unknown_setup=job['unknown_setup'],
        qualifications=job['qualifications'],reference_scope=job['reference_scope'])
    if (stage/'observable-report.json').exists():result['observable_report']=json.loads((stage/'observable-report.json').read_text())
    validate_result_contract(job,result);_write(stage/'adapter-result.json',result)
    return result


def mesh_diagnostics(jobs,results):
    groups={}
    for job in jobs:
        if job.get('adapter')=='ae3' and job.get('target_kind')=='native_coefficients':groups.setdefault(job['coordinate_id'],[]).append(job)
    rows=[]
    for coordinate,pair in sorted(groups.items()):
        pair=sorted(pair,key=lambda job:job['nominal']);_require(len(pair)<=2 and len({job['nominal'] for job in pair})==len(pair),'duplicate grid coordinate.')
        packets=[results.get(job['id'],{}) for job in pair]
        row=dict(coordinate_id=coordinate,jobs=[job['id'] for job in pair],passed=None,acceptance_gate=None,
            scope='Prospective current80/160 interval sensitivity; no historical grid/full-family claim.')
        if len(pair)!=2 or any(packet.get('status')!='computed' for packet in packets):row.update(status='UNAVAILABLE',channels={})
        else:
            values=[{item['name']:item['predicted'] for item in packet['reference_checks']} for packet in packets];changes={}
            for name in NAMES:
                a,b=(value[name] for value in values);delta=abs(b-a)
                changes[name]=dict(coarse=a,fine=b,abs_change=delta,relative_change=delta/abs(b) if b else (0. if delta==0 else None))
            row.update(status='COMPARED',channels=changes)
        rows.append(row)
    return rows
