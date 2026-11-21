"""Opt-in native SA6 dimensional mass tensors; source planning is stdlib-only."""
import copy
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import time

try:
    from . import isae_suite_sa6_controls as common
    from . import isae_suite_sa6_mass_math as tensor_math
except ImportError:
    import isae_suite_sa6_controls as common
    import isae_suite_sa6_mass_math as tensor_math

SCOPE = 'sa6-mass-rigid'
KIND = 'native_mass_tensors'
ROUTE = 'rigid_mass_properties'
CATALOG = 'artifacts/isae/sa6-mass-tensors-20261028/tensor-source-catalog.json'
CATALOG_SHA256 = 'e17b17414ae50e50b7bd879365c6538d4fc50568ffdaf8bd1340dd0f0158af0b'
AUDIT = 'artifacts/isae/sa6-mass-tensors-20261028/source-audit.json'
AUDIT_SHA256 = 'f85b4c351019dbd9a16ad8561b1ee72a5f41c25b99f4f2503b3487a41a9c9d7c'
NUMBER = re.compile(r'[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[Ee][+-]?\d+)?')
ROWS = {15:('real_mass.xx','apparent_mass.xx','apparent_mass.xy','apparent_mass.xz'),
        16:('real_mass.yy','apparent_mass.yy','apparent_mass.yz'),17:('real_mass.zz','apparent_mass.zz')}
for first,origin in ((21,'origin'),(27,'centroid')):
    for offset,components in enumerate((('xx','xy','xz'),('yy','yz'),('zz',))):
        ROWS[first+offset] = tuple(f'{kind}_inertia_{origin}.{c}' for kind in ('real','apparent') for c in components)
NAMES = tuple(name for names in ROWS.values() for name in names)
OPERATIONS = dict(aerodynamic_calls=0,nonlinear_solves=0,derivative_factorizations=0,
                  geometry_evaluations=1,real_element_assemblies=1)
GATES = dict(tensor_evidence=tensor_math.GATE,literal_geometry=2e-12)
# eigvalsh may differ by a few last bits after JSON/process transfer. This is
# only a saved-metric identity allowance; both values must pass the fixed gate.
PSD_METRIC_ROUNDOFF = 64*sys.float_info.epsilon
MANDATORY_Y = (-.333*.762,0.,.333*.762)
QUALIFICATIONS = [
    'All 33 original dimensional body-axis cells per file; real mass has only three printed diagonals. No unprinted matrix entries become targets.',
    'Current undeformed rigid geometry with the literal 4-degree physical section twist, physical normal and midchord arm. No aerodynamic or nonlinear solution is needed.',
    'All real mass is zero, so physical real CG remains undefined (None). Centroid-labelled tensors are evaluated at the explicit archived zero coordinate as a reporting reference, not an invented physical CG. No apparent CG is defined.',
    'Original malformed tensor unit labels remain preserved. Literal m, s and N units imply kg for mass and kg m^2 for inertia; no stability-axis rotation, off-diagonal sign reversal or nondimensionalization.',
    'Tiny original nonzeros remain required targets with their exact printed precision; no snapping, source replacement or geometry inferred from target values.',
    'A separate conditional mass-tensor ledger preserves all 44 original states and both declared 64/128 meshes. Historical producer, startup, native mesh and deformed-shape output identity remain unauthenticated.',
    'Current cosine reconstruction includes the original doubled control-table stations at ±(.333×.762) and the root station 0, giving 66/130 intervals. This is not recovery of historical NODE coordinates.',
]
require,finite = common.require,common.finite


def identifies(job):
    return (job.get('target_kind')==KIND or job.get('comparison_scope')==SCOPE or
            job.get('execution_route')==ROUTE or job.get('id','').endswith(':rigid-mass'))


def node_recipe(count):
    require(type(count) is int and count in (64,128),'Unreviewed tensor mesh request.')
    return dict(kind='current_cosine_with_source_discontinuities',nominal_intervals=count,
                mandatory_y=list(MANDATORY_Y),expected_intervals=count+2)


def declared_nodes(job):
    """Independent scalar reconstruction of this straight literal current mesh."""
    count=job['settings']['panels'];node_recipe(count)
    nodes=[-.762+1.524*(1-math.cos(math.pi*i/count))/2 for i in range(count+1)]
    for point in MANDATORY_Y:
        nodes=[point if abs(y-point)<1e-11*1.524 else y for y in nodes]
    return sorted(set(nodes+list(MANDATORY_Y)))


def decode(text):
    lines=text.splitlines(keepends=True)
    require(len(lines)==106 and lines[3].strip()=='Mass and Inertia tensors in body axes...', 'Native tensor header changed.')
    for row,word in ((13,'Real mass tensor'),(19,'Real inertia tensor about xyz = 0,0,0'),(25,'Real inertia tensor about mass centroid')):
        require(word in lines[row-1], 'Native tensor reference header changed.')
    fields={}
    for row,names in ROWS.items():
        matches=list(NUMBER.finditer(lines[row-1]));require(len(matches)==len(names),'Native tensor row shape changed.')
        for name,match in zip(names,matches):
            token=match.group();value=Decimal(token);half=Decimal(5).scaleb(value.as_tuple().exponent-1)
            require(value.is_finite(),'Nonfinite native tensor.')
            start=sum(len(line) for line in lines[:row-1])+match.start()
            fields[name]=dict(token=token,value=float(value),tolerance=float(half),exact_decimal_expected=str(value),
                exact_decimal_tolerance=str(half),negative_zero=value.is_zero() and value.is_signed(),source_line=row,
                source_column_1based=match.start()+1,source_character_start_0based=start,source_character_end_0based=start+len(token),
                axes='body',units='kg m^2' if 'inertia' in name else 'kg')
    return fields


def plan(root,static_jobs,pin):
    root=Path(root)
    for path,sha in ((CATALOG,CATALOG_SHA256),(AUDIT,AUDIT_SHA256)):
        require(hashlib.sha256((root/path).read_bytes()).hexdigest()==sha,'Frozen tensor source evidence changed.')
    catalog=json.loads((root/CATALOG).read_text());files={f['path']:f for f in catalog['files']}
    require(len(files)==44 and catalog['counts']['native_targets']==1452,'Incomplete native tensor catalog.')
    helpers=[pin(Path(p).resolve(),root) for p in (__file__,common.__file__,tensor_math.__file__,root/CATALOG,root/AUDIT)]
    # Every immutable dependency of the frozen source catalog is pinned directly.
    for evidence in catalog['source_pins']:
        actual=pin(root/evidence['path'],root);require(actual==evidence,'Tensor catalog dependency changed.')
        if actual not in helpers:helpers.append(actual)
    jobs=[]
    for base in static_jobs:
        if base['execution_route']!='rigid_static_coefficients':continue
        record=files[base['table_path']];fields=decode((root/base['table_path']).read_text())
        for original in record['observations']:
            field=fields[original['label']]
            require(all(field[k]==original[v] for k,v in (
                ('token','token'),('source_line','line'),('source_column_1based','column_1based'),
                ('exact_decimal_tolerance','half_printed_unit'),('negative_zero','negative_zero'))),'Tensor decode/catalog mismatch.')
        centroid={o['label']:o for o in record['centroid_context']}
        point=[float(Decimal(centroid['mass_centroid.'+axis]['token'])) for axis in 'xyz']
        require(point==[0.,0.,0.],'Original reported tensor reference changed.')
        job=copy.deepcopy(base)
        job.update(id=base['id']+':rigid-mass',base_static_job_id=base['id'],target_kind=KIND,comparison_scope=SCOPE,
            execution_route=ROUTE,expected_outputs=33,required_outputs=list(NAMES),numerical_gates=dict(GATES),
            expected_operations=dict(OPERATIONS),reported_centroid=point,physical_real_cg_expected=None,
            tensor_axes='body',tensor_units={'mass':'kg','inertia':'kg m^2'},
            tensor_mesh_recipe=node_recipe(base['settings']['panels']),
            historical_producer_authenticated=False,reporting_reference_is_physical_centroid=False,
            tensor_source_headers=copy.deepcopy(record['raw_header']),tensor_centroid_context=copy.deepcopy(record['centroid_context']))
        job['static_reference_row']=copy.deepcopy(base['reference_row'])
        job['reference_row']['fields']=fields
        job['sources']+= [p for p in helpers if p not in job['sources']]
        job['qualifications']=[q for q in base['qualifications'] if not q.startswith('Six static')]+QUALIFICATIONS
        validate_record_contract(job);jobs.append(job)
    require(len(jobs)==len({j['id'] for j in jobs})==88,'Mass scope requires all 88 mesh jobs.')
    return jobs


def validate_record_contract(job):
    require(job.get('adapter')=='sa6' and job.get('case_id')=='SA-6' and job.get('target_kind')==KIND and
            job.get('comparison_scope')==SCOPE and job.get('execution_route')==ROUTE and
            job.get('id')==job.get('base_static_job_id','')+':rigid-mass','Invalid SA6 tensor scope identity.')
    require(job.get('expected_outputs')==33 and job.get('required_outputs')==list(NAMES) and
            set(job['reference_row']['fields'])==set(NAMES),'Tensor scope requires all 33 native cells.')
    require(job.get('numerical_gates')==GATES and job.get('expected_operations')==OPERATIONS and
            job.get('reported_centroid')==[0.,0.,0.] and job.get('physical_real_cg_expected','missing') is None and
            job.get('reporting_reference_is_physical_centroid') is False and job.get('tensor_axes')=='body' and
            job.get('tensor_units')=={'mass':'kg','inertia':'kg m^2'} and
            job.get('tensor_mesh_recipe')==node_recipe(job['settings']['panels']) and
            job.get('historical_producer_authenticated') is False and job.get('complete_family_reproduction') is False,
            'Tensor reporting reference, units, gates or qualifications changed.')
    reference_contract(job,validate=False)
    return True


def reference_contract(job,*,validate=True):
    if validate:validate_record_contract(job)
    out={}
    for name in NAMES:
        f=job['reference_row']['fields'][name];value=Decimal(f['token']);half=Decimal(5).scaleb(value.as_tuple().exponent-1)
        require(value.is_finite() and f['value']==float(value) and f['tolerance']==float(half) and
            f['exact_decimal_expected']==str(value) and f['exact_decimal_tolerance']==str(half) and
            f['negative_zero'] is (value.is_zero() and value.is_signed()) and f['axes']=='body' and
            f['units']==('kg m^2' if 'inertia' in name else 'kg') and
            all(type(f[k]) is int and f[k]>0 for k in ('source_line','source_column_1based')) and
            type(f['source_character_start_0based']) is int and f['source_character_start_0based']>=0 and
            f['source_character_end_0based']==f['source_character_start_0based']+len(f['token']),
            'Native tensor precision, position or units changed.')
        out[name]=dict(expected=f['value'],expected_token=f['token'],tolerance=f['tolerance'],
            **{k:f[k] for k in ('exact_decimal_expected','exact_decimal_tolerance','negative_zero','source_line','source_column_1based',
                'source_character_start_0based','source_character_end_0based','axes','units')})
    return out


def reference_checks(job,values=None,reason=None):
    values=values or {};checks=[]
    for name,ref in reference_contract(job).items():
        value=values.get(name);error=abs(Decimal(str(value))-Decimal(ref['exact_decimal_expected'])) if finite(value) else None
        checks.append(dict(name=name,**ref,predicted=value if finite(value) else None,abs_error=float(error) if error is not None else None,
            passed=error is not None and error<=Decimal(ref['exact_decimal_tolerance']),
            **({} if error is not None else dict(unavailable_reason=reason or 'No finite current tensor.'))))
    return checks


def evidence_checks(job,evidence):
    require(evidence['density']==job['settings']['density'] and evidence['body_added_mass_factor']==job['settings']['body_added_mass_factor'] and
            evidence['reported_centroid']==job['reported_centroid'] and evidence['physical_real_cg'] is None and evidence['real_mass']==0 and
            evidence['reference_span']==1.524,
            'Tensor source density, reporting point or undefined CG changed.')
    geometry=evidence['geometry'];panels=geometry['lifting_panels']
    require(geometry['beam_count']==len(panels)==1 and geometry['nonlifting_beams']==0 and geometry['body_panels']==[],
            'Literal single lifting beam changed.')
    for record in evidence['real_records']:
        require(all(value==0 for value in record['mass']) and
                all(value==0 for tensor in record['inertia'] for row in tensor for value in row) and
                all(value==0 for row in record['spin'] for value in row), 'Literal zero real mass/inertia/spin changed.')
    angle=math.radians(4.);c,s=math.cos(angle),math.sin(angle)
    wanted=[[c,0.,s],[0.,1.,0.],[-s,0.,c]];errors=[];ends=[]
    nodes=declared_nodes(job)
    for beam in panels:
        n=len(beam['ds']);require(n==len(nodes)-1==job['tensor_mesh_recipe']['expected_intervals'],'Declared tensor mesh inventory changed.')
        common.vector(beam['ds'],n,'interval length');require(all(ds>0 for ds in beam['ds']),'Nonpositive tensor intervals.')
        common.vector(beam['chord'],n,'chord');common.vector(beam['xax'],n,'axis')
        for key in ('rm','r0','r1'):common.matrix(beam[key],n,3,key)
        require(len(beam['frame'])==n,'Missing physical frames.')
        for i in range(n):
            frame=common.matrix(beam['frame'][i],3,3,'physical frame')
            errors += [abs(frame[a][b]-wanted[a][b]) for a in range(3) for b in range(3)]
            errors += [abs(beam['chord'][i]-.254),abs(beam['xax'][i])]
            for key in ('rm','r0','r1'):
                p=beam[key][i];errors += [abs(p[0]),abs(p[2]),max(0.,abs(p[1])-.762)]
            y0,y1,ym=beam['r0'][i][1],beam['r1'][i][1],beam['rm'][i][1]
            errors += [abs(y0-nodes[i]),abs(y1-nodes[i+1])]
            errors += [abs(beam['ds'][i]-(y1-y0)),max(0.,y0-ym,ym-y1)]
            midpoint=.5*(math.sqrt(max(0.,(y0+.762)*(y1+.762)))-math.sqrt(max(0.,(.762-y0)*(.762-y1))))
            errors.append(abs(ym-midpoint))
            if i:errors.append(abs(y0-beam['r1'][i-1][1]))
            ends.extend((beam['r0'][i][1],beam['r1'][i][1]))
        errors.append(abs(sum(beam['ds'])-1.524))
    errors += [abs(min(ends)+.762),abs(max(ends)-.762)]
    checks=tensor_math.validate_tensor_evidence(evidence)
    checks += [dict(name='literal SA6 physical geometry',value=max(errors),comparison='<=',tolerance=GATES['literal_geometry'],
                    passed=max(errors)<=GATES['literal_geometry']),
               dict(name='zero real mass has undefined physical centroid',passed=True)]
    return checks


def validate_result_contract(job,result):
    validate_record_contract(job);contract=reference_contract(job);checks=result.get('reference_checks',[])
    require(len(checks)<=33 and len({c.get('name') for c in checks})==len(checks),'Duplicate/excess tensor checks.')
    for check in checks:
        name=check.get('name');require(name in contract and all(check.get(k)==v for k,v in contract[name].items()),'Changed tensor reference metadata.')
        wanted=reference_checks(job,{name:check.get('predicted')})[NAMES.index(name)]
        require(check.get('passed') is wanted['passed'] and check.get('abs_error')==wanted['abs_error'],'Changed tensor Decimal comparison.')
    if result.get('status')!='computed':
        require(result.get('numerical_pass') is not True and result.get('numerical_passed') is not True and result.get('reference_match') is not True,
                'Failed tensor result claims success.')
        return True
    require(all(result.get(k)==v for k,v in job.items() if k!='result' and not k.startswith('_summary_')) and result.get('sources_unchanged') is True and
            result.get('physical_calls')==0 and result.get('factorizations')==0 and result.get('operations')==OPERATIONS and len(checks)==33,
            'Incomplete computed tensor contract or hidden solve.')
    canonical=evidence_checks(job,result['evidence'])
    retained=result.get('numerical_checks',[])
    compatible=len(retained)==len(canonical)
    for actual,expected in zip(retained,canonical):
        if actual==expected:continue
        compatible = compatible and (
            expected['name'].endswith(' positive semidefinite') and
            set(actual)==set(expected) and
            {k:v for k,v in actual.items() if k!='value'}=={k:v for k,v in expected.items() if k!='value'} and
            actual.get('passed') is True and expected.get('passed') is True and
            finite(actual.get('value')) and finite(expected.get('value')) and
            0<=actual['value']<=actual['tolerance'] and 0<=expected['value']<=expected['tolerance'] and
            abs(actual['value']-expected['value'])<=PSD_METRIC_ROUNDOFF)
    require(compatible and all(c['passed'] for c in canonical) and result.get('numerical_pass') is True,
            'Incomplete or failed tensor evidence.')
    wanted=reference_checks(job,tensor_math.tensor_predictions(result['evidence']))
    require(checks==wanted and result.get('reference_match') is all(c['passed'] for c in wanted),'Detached tensor prediction.')
    return True


def _execute(root,job):
    from openswing import asw,geometry
    for module in (asw,geometry):
        require(Path(module.__file__).resolve()==root/'openswing'/(module.__name__.split('.')[-1]+'.py'),'Wrong production import root.')
    s=job['settings'];model=asw.parse_asw((root/job['model_path']).read_text(),beam_interpolation=s['beam_interpolation'])
    require(not model.diagnostics and float(model.constants[1])==s['density'],'Literal model/density changed.')
    meshes=geometry.model_meshes(model,s['panels'])
    return tensor_math.compute_tensor_evidence(model,meshes,s['density'],job['reported_centroid'],s['body_added_mass_factor'])


def run(root,job,verify):
    root=Path(root).resolve();start=time.monotonic()
    result=dict(copy.deepcopy(job),status='error',numerical_pass=False,reference_match=False,physical_calls=0,factorizations=0,
        sources_unchanged=False,numerical_checks=[],reference_checks=reference_checks(job),operations=dict(OPERATIONS,geometry_evaluations=0,real_element_assemblies=0))
    try:
        verify(root,job);result['operations']['geometry_evaluations']=1
        evidence=_execute(root,job);result['evidence']=evidence;result['operations']['real_element_assemblies']=1
        result['numerical_checks']=evidence_checks(job,evidence)
        result['reference_checks']=reference_checks(job,tensor_math.tensor_predictions(evidence))
        result['numerical_pass']=all(c['passed'] for c in result['numerical_checks'])
        result['status']='computed' if result['numerical_pass'] else 'numerical_failure'
        result['reference_match']=result['numerical_pass'] and all(c['passed'] for c in result['reference_checks'])
    except Exception as exc:
        result.update(status='error',error_type=type(exc).__name__,error=str(exc),numerical_pass=False,reference_match=False)
    finally:
        try:verify(root,job);result['sources_unchanged']=True
        except (OSError,ValueError):result.update(status='source_mismatch',numerical_pass=False,reference_match=False,sources_unchanged=False)
        result['seconds']=time.monotonic()-start
    # Tensor helper guarantees JSON-compatible evidence; reject nonfinite saved data.
    try:json.dumps(result,allow_nan=False)
    except (ValueError,TypeError):
        result.pop('evidence',None);result.update(status='numerical_failure',numerical_pass=False,reference_match=False,
            numerical_checks=[],reference_checks=reference_checks(job,reason='Nonfinite or nonserializable tensor evidence.'))
    return result
