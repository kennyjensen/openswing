"""Bounded unchanged-source ST2 modal execution and saved-evidence contracts.

Importing this module performs no production import or physical evaluation.
One cold public modes request is followed by an exact saved-state restore and
one residual, never a second equilibrium correction or eigenvalue search.
"""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

GATES = dict(base=1e-9, pencil=1e-8, root_absolute=2e-8, root_relative=2e-8,
    neutral_relative=1e-8, mass_pairing=1e-8, mesh_relative=.001,
    relative_balance=1e-7, clamp=1e-10, restored_parity=2e-10)
PROTOCOL = dict(count=20, shift=[-.01, 0.], method='full_shift_invert', step=1e-5,
    rank_tolerance=1e-9, selected_positive_roots=7, positive_imaginary_threshold=0.)
OPERATIONS = dict(cold_bridge_calls=1, equilibrium_solves=1, modal_solves=1,
    fresh_residuals=1, retries=0)
POLICIES = dict(vacuum='drela-fixed-vacuum-v1', still_air='drela-fixed-still-air-v1')
EXACT = ('literal_source_hash', 'literal_reference', 'literal_weight_rows', 'literal_sensor_rows',
    'inactive_null_weights', 'no_parser_diagnostics', 'same_operator_identity', 'restore_without_evaluation',
    'one_restored_residual', 'converged', 'source_policy', 'stationary_setup', 'medium_setup',
    'mesh_panel_setting', 'mandatory_stations_present', 'root_clamp_count', 'zero_material_damping',
    'modal_algorithm', 'full_matrix_shape', 'full_vector_shapes')
PHYSICAL_CHECK_SPECS = {
    **{name:dict(kind='exact') for name in EXACT},
    'modal_spectrum':dict(kind='spectrum'),
    'base_residual':dict(kind='maximum', gate='base'),
    'fresh_full_residual':dict(kind='maximum', gate='base'),
    'force_balance':dict(kind='balance', gate='relative_balance'),
    'moment_balance':dict(kind='balance', gate='relative_balance'),
    'root_clamp_position':dict(kind='clamp', gate='clamp'),
    'root_clamp_frame':dict(kind='clamp', gate='clamp'),
    'independent_real_mass':dict(kind='mass', gate='restored_parity'),
    'independent_gravity_wrench':dict(kind='gravity', gate='restored_parity'),
    'restored_base_parity':dict(kind='parity', gate='restored_parity'),
    'modal_right_pencil':dict(kind='pencil', gate='pencil'),
    'modal_left_pencil':dict(kind='pencil', gate='pencil'),
    'modal_mass_pairing':dict(kind='pairing', gate='mass_pairing'),
    'modal_neutrality':dict(kind='neutral', gate='neutral_relative'),
    'arnoldi_shifted_solves':dict(kind='maximum', fixed_gate=1e-10)}
REQUIRED_PHYSICAL_CHECKS = tuple(PHYSICAL_CHECK_SPECS)


def _require(ok, message):
    if not ok:
        raise ValueError('ST2 modal '+message)


def _finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _vector(v, size=None):
    return isinstance(v, list) and (size is None or len(v)==size) and bool(v) and all(_finite(x) for x in v)


def _relative(a, b):
    _require(_vector(a) and _vector(b,len(a)), 'invalid finite vector evidence.')
    return max(abs(x-y) for x,y in zip(a,b))/(1.+max(map(abs,a+b)))


def _cross(a,b):
    return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]


def _write(path, value):
    Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def _job_contract(job):
    _require(job['numerical_gates']==GATES and job['modal_protocol']==PROTOCOL,
        'gates or modal protocol changed.')
    _require(job['expected_operations']==OPERATIONS and job['nominal'] in (40,80), 'operations or mesh changed.')
    medium=job['medium']; _require(medium in POLICIES, 'unknown medium.')
    _require(job['density']==(None if medium=='vacuum' else 1.23), 'medium density changed.')
    policy=dict(beam_interpolation='drela-segspl-v1',structural_operator=POLICIES[medium])
    _require(job['settings']==policy and job['condition'] is None and job['gravity']==[0.,0.,-9.81],
        'literal stationary source setup changed.')
    _require(job['panels']==dict(default=job['nominal'],beams={'1':dict(count=job['nominal'],spacing='cosine')}) and
        job['expected_nodes']==job['nominal']+2 and job['expected_elements']==job['nominal']+1,
        'prospective mesh contract changed.')
    _require(job['root_position']==[0.,0.,0.] and job['mandatory_stations']==[.0001,.52,.55] and
        job['expected_real_mass']==.373285 and job['continuation_steps']==4, 'source geometry/mass contract changed.')
    return policy


def spectrum_evidence(roots):
    """Select ordinals using computed roots only, retaining every raw component."""
    _require(isinstance(roots,list) and len(roots)==20 and all(_vector(r,2) for r in roots),
        'exactly20 finite raw complex roots are required; no retry.')
    z=[complex(*r) for r in roots]
    positive=sorted((i for i,v in enumerate(z) if v.imag>0),key=lambda i:(z[i].imag,i))
    selected=positive[:7]; witnesses=[];used=[]
    for i in selected:
        candidates=[]
        for k,w in enumerate(z):
            if w.imag>=0:
                continue
            error=abs(w-z[i].conjugate());gate=GATES['root_absolute']+GATES['root_relative']*max(abs(w),abs(z[i]))
            if error<=gate:
                candidates.append(dict(index=k,absolute_error=error,gate=gate))
        witnesses.append(dict(positive_index=i,candidates=candidates))
        if len(candidates)==1:
            used.append(candidates[0]['index'])
    distinct=all(abs(a-b)>GATES['root_absolute']+GATES['root_relative']*max(abs(a),abs(b))
        for i,a in enumerate(z) for b in z[i+1:])
    values={f'row{ordinal:04d}:{component}':roots[index][axis] for ordinal,index in enumerate(selected,1)
        for axis,component in enumerate(('real','imaginary'))}
    return dict(eigenvalues=deepcopy(roots),positive_indices=positive,selected_indices=selected,
        conjugate_witnesses=witnesses,distinct=bool(distinct),positive_enough=len(positive)>=7,
        unique_conjugates=len(used)==7 and len(set(used))==7,values=values)


def validate_modal_evidence(job, evidence):
    _job_contract(job)
    expected=spectrum_evidence(evidence['eigenvalues'])
    _require(all(evidence.get(k)==v for k,v in expected.items()), 'root ordering, values or conjugate evidence changed.')
    _require(expected['distinct'] and expected['positive_enough'] and expected['unique_conjugates'],
        'local root selection incomplete or ambiguous; no adaptive retry.')
    return expected['values']


def _expectations(job, dimension):
    policy=_job_contract(job)
    _require(type(dimension) is int and dimension==18*job['expected_nodes'], 'unexpected fixed full descriptor size.')
    return dict(literal_source_hash=job['literal_model_sha256'],literal_reference=job['literal_reference'],
        literal_weight_rows=job['literal_weight_rows'],literal_sensor_rows=job['literal_sensor_rows'],
        inactive_null_weights=0,no_parser_diagnostics=[],restore_without_evaluation=0,one_restored_residual=1,
        converged=True,source_policy=policy,stationary_setup=dict(frame='fixed',condition=None,gravity=job['gravity'],
            position=[0.,0.,0.],attitude=[0.,0.,0.],velocity=[0.,0.,0.],rates=[0.,0.,0.],acceleration=[0.,0.,0.],
            angular_acceleration=[0.,0.,0.],engines=0,loads=0,struts=0,hinges=0,operating_constraints=0,controller=None),
        medium_setup=dict(vacuum=job['medium']=='vacuum',density=job['density'],circulation_count=0),
        mesh_panel_setting=dict(panels=job['panels'],nodes=job['expected_nodes'],elements=job['expected_elements']),
        mandatory_stations_present={str(t):True for t in job['mandatory_stations']},root_clamp_count=1,
        zero_material_damping=True,modal_algorithm=dict(method='full_shift_invert',requested_method='full_shift_invert',
            count=20,shift=[-.01,0.],difference_step=1e-5,rank_tolerance=None,finite_dimension=None,
            finite_spectrum=None,integrator_deflation_count=0,mass_rank_reduction=False,retained_dimension=dimension,
            arpack_mode=1,bmat='I',which='LM',tolerance=1e-11,factorizations=1),
        full_matrix_shape=dict(A=[dimension,dimension],M=[dimension,dimension],finite=True),
        full_vector_shapes=dict(count=20,dimension=dimension,finite=True))


def validate_physical_checks(job, checks):
    """Recompute metrics from small saved evidence; raw pencils stay in result.json."""
    _job_contract(job)
    _require(isinstance(checks,list), 'physical checks missing.')
    names=[x.get('name') for x in checks]
    _require(len(names)==len(set(names))==len(REQUIRED_PHYSICAL_CHECKS) and set(names)==set(REQUIRED_PHYSICAL_CHECKS),
        'physical check set incomplete, duplicated or unknown.')
    byname={x['name']:x for x in checks}
    expected=_expectations(job,18*job['expected_nodes'])
    roots=byname['modal_spectrum']['evidence']['eigenvalues'];spectrum=spectrum_evidence(roots)
    for row in checks:
        name=row['name'];spec=PHYSICAL_CHECK_SPECS[name];kind=spec['kind']
        if kind=='exact':
            _require('actual' in row and 'expected' in row, 'missing exact evidence.')
            if name=='same_operator_identity':
                identity=row['expected']
                _require(identity.get('model_sha256')==job['literal_model_sha256'] and
                    identity.get('structural_operator')==job['settings']['structural_operator'] and
                    identity.get('beam_interpolation')=='drela-segspl-v1' and
                    identity.get('quiescent_density')==job['density'] and identity.get('circulation_count')==0 and
                    len(identity.get('nodes',[]))==job['expected_nodes'] and len(identity.get('elements',[]))==job['expected_elements'],
                    'saved identity detached from source, medium or mesh.')
            else:
                _require(row['expected']==expected[name], 'canonical expectation changed: '+name)
            passed=row['actual']==row['expected']
        elif kind=='spectrum':
            _require(row['evidence']==spectrum, 'local spectrum evidence changed.')
            passed=spectrum['distinct'] and spectrum['positive_enough'] and spectrum['unique_conjugates']
        else:
            gate=spec.get('fixed_gate',GATES.get(spec.get('gate')))
            _require(row.get('gate')==gate and _finite(row.get('metric')) and row['metric']>=0, 'metric/gate changed: '+name)
            if kind=='maximum':
                _require(_vector(row['values']) and all(x>=0 for x in row['values']), 'invalid norm evidence.')
                metric=max(row['values'])
            elif kind=='balance':
                a,b=row['applied'],row['support'];_require(_vector(a,3) and _vector(b,3), 'invalid balance wrench.')
                metric=math.hypot(*(x+y for x,y in zip(a,b)))/max(1.,math.hypot(*a)+math.hypot(*b))
            elif kind=='clamp':
                target=job['root_position'] if name.endswith('position') else [1.,0.,0.,0.,1.,0.,0.,0.,1.]
                _require(row['expected']==target and _vector(row['reported'],len(target)), 'clamp evidence changed.')
                metric=max(abs(a-b) for a,b in zip(row['reported'],target))
            elif kind=='mass':
                _require(_vector(row['endpoint_masses']) and all(x>=0 for x in row['endpoint_masses']), 'invalid real masses.')
                total=sum(row['endpoint_masses']);_require(row['reconstructed']==total and row['expected']==job['expected_real_mass'], 'real mass changed.')
                metric=_relative([row['reported']],[total]);metric=max(metric,_relative([total],[job['expected_real_mass']]))
            elif kind=='gravity':
                f=[0.,0.,0.];m=[0.,0.,0.]
                for point in row['samples']:
                    _require(_finite(point['mass']) and point['mass']>=0 and _vector(point['position'],3), 'invalid gravity sample.')
                    fi=[point['mass']*g for g in job['gravity']];mi=_cross(point['position'],fi)
                    f=[a+b for a,b in zip(f,fi)];m=[a+b for a,b in zip(m,mi)]
                _require(row['reconstructed_force']==f and row['reconstructed_moment']==m,'gravity reconstruction changed.')
                metric=max(_relative(row['reported_force'],f),_relative(row['reported_moment'],m))
            elif kind=='parity':
                _require(set(row['reported'])==set(row['restored'])=={'positions','rotations','applied_force','applied_moment','support_force','support_moment','sensor_positions'}, 'base parity fields changed.')
                channels={k:_relative(v,row['restored'][k]) for k,v in row['reported'].items()}
                _require(row['channels']==channels,'base parity metrics changed.');metric=max(channels.values())
            elif kind=='pencil':
                entries=row['entries'];_require(len(entries)==20,'missing pencil modes.');metrics=[]
                for i,e in enumerate(entries):
                    _require(e['index']==i and e['eigenvalue']==roots[i] and all(_finite(e[k]) and e[k]>=0 for k in ('residual_norm','vector_norm','A_norm','M_norm','denominator','reported_backward_error')), 'invalid original-pencil evidence.')
                    denominator=(e['A_norm']+abs(complex(*roots[i]))*e['M_norm'])*e['vector_norm']
                    _require(denominator>0 and math.isclose(e['denominator'],denominator,rel_tol=3e-15,abs_tol=0.),'pencil denominator changed.')
                    backward=e['residual_norm']/e['denominator'];_require(e['backward_error']==backward,'pencil metric changed.')
                    metrics.extend([backward,e['reported_backward_error']])
                metric=max(metrics)
            elif kind=='pairing':
                _require(len(row['entries'])==20,'missing mass pairings.');metrics=[]
                for i,e in enumerate(row['entries']):
                    _require(e['index']==i and _vector(e['value'],2) and e['normalized'] is True,'invalid left/right normalization.')
                    error=abs(complex(*e['value'])-1.);_require(e['error']==error,'mass-pairing error changed.');metrics.append(error)
                metric=max(metrics)
            elif kind=='neutral':
                _require(row['eigenvalues']==roots,'neutrality roots detached.');metric=max(abs(a)/max(1.,abs(b)) for a,b in roots)
            else:
                raise ValueError('Unknown ST2 modal check kind.')
            _require(math.isclose(row['metric'],metric,rel_tol=3e-15,abs_tol=1e-30),'independent metric changed: '+name)
            passed=metric<=gate
        _require(isinstance(row.get('passed'),bool) and row['passed'] is bool(passed),'physical boolean changed: '+name)
    gravity=byname['independent_gravity_wrench']
    _require(byname['force_balance']['applied']==gravity['reported_force'] and byname['moment_balance']['applied']==gravity['reported_moment'], 'balance detached from gravity evidence.')
    _require(byname['independent_real_mass']['endpoint_masses']==[p['mass'] for p in gravity['samples']], 'mass and gravity sample scopes differ.')
    return all(row['passed'] for row in checks)


def execute(root, job, stage):
    """Execute the declared modal request once and restore without correcting it."""
    _job_contract(job);root=Path(root).resolve();stage=Path(stage)
    import numpy as np
    import openswing
    from openswing.asw import parse_asw
    from openswing.bridge import dispatch
    from openswing.source_dynamics import SourceDynamicNetwork
    from openswing.source_quiescent import SourceQuiescentNetwork
    from openswing.equilibrium_state import warm_start_recipe,restore,identity,matching_identity
    from openswing.network import network_snapshot
    from openswing.point_objects import active_weights
    _require(Path(openswing.__file__).resolve().parent==root/'openswing','another checkout imported.')
    raw=Path(job['source']).read_bytes();_require(hashlib.sha256(raw).hexdigest()==job['literal_model_sha256'],'literal source changed.')
    request=deepcopy(job['request']);_require(request['source'].encode()==raw,'request changed original bytes.')
    _write(stage/'request.json',request)
    operations=dict(cold_bridge_calls=1,equilibrium_solves=1,modal_solves=1,fresh_residuals=0,retries=0)
    _write(stage/'operations.json',operations)
    result=dispatch(request);_write(stage/'result.json',result)
    base=result['base'];saved=base['equilibrium_state']
    model=parse_asw(raw.decode(),beam_interpolation='drela-segspl-v1')
    cls=SourceDynamicNetwork if job['medium']=='vacuum' else SourceQuiescentNetwork
    kwargs={} if job['density'] is None else dict(quiescent_density=job['density'])
    network=cls(model,job['panels'],None,job['gravity'],[],mesh_recipe=warm_start_recipe(model,job['panels'],saved),**kwargs)
    current_identity=identity(network);_require(matching_identity(saved['identity'],current_identity),'restore identity changed.')
    state=restore(network,saved);restore_evaluations=network.nfev
    zero=np.zeros_like(network.rj);operations['fresh_residuals']=1;_write(stage/'operations.json',operations)
    residual,data=network.residual(state,detail=True,elastic_motion=(zero,zero,zero,zero),circulation_rate=np.zeros(network.circulation_basis.panels))
    fresh=network_snapshot(network,residual,data);_write(stage/'restored-result.json',fresh)
    _write(stage/'restored-residual.json',dict(vector=residual.tolist(),maximum_absolute=float(np.max(abs(residual)))))
    diagnostics=result['diagnostics'];dimension=network.size+6*network.nn
    checks=[]
    def exact(name,actual,expected):checks.append(dict(name=name,actual=actual,expected=expected,passed=bool(actual==expected)))
    def metric(name,value,**evidence):
        spec=PHYSICAL_CHECK_SPECS[name];gate=spec.get('fixed_gate',GATES.get(spec.get('gate')))
        checks.append(dict(name=name,metric=float(value),gate=gate,passed=bool(value<=gate),**evidence))
    expected=_expectations(job,dimension)
    for name,actual in [('literal_source_hash',hashlib.sha256(raw).hexdigest()),('literal_reference',model.reference.tolist()),
        ('literal_weight_rows',[x.tolist() for x in model.records['weight']]),('literal_sensor_rows',[x.tolist() for x in model.records['sensor']]),
        ('inactive_null_weights',len(active_weights(model))),('no_parser_diagnostics',list(model.diagnostics)),
        ('restore_without_evaluation',restore_evaluations),('one_restored_residual',network.nfev),
        ('converged',result['converged'] and base['converged'] and fresh['converged']),
        ('source_policy',dict(beam_interpolation=model.beam_interpolation,structural_operator=diagnostics.get('structural_operator'))),
        ('mesh_panel_setting',dict(panels=base['mesh_discretization']['settings'],nodes=network.nn,elements=network.ne)),
        ('mandatory_stations_present',{str(t):t in network.station_nodes[1][0] for t in job['mandatory_stations']}),
        ('zero_material_damping',not np.any(network.damping_times) and not any(m['constitutive_relaxation'] for m in result['modes']))]:
        exact(name,actual,expected[name])
    exact('same_operator_identity',current_identity,saved['identity'])
    frame=base['modal_base'];motion=network.motion
    exact('stationary_setup',dict(frame=result['frame_mode'],condition=network.condition,gravity=base['gravity_body'],
        position=frame['position_earth'],attitude=frame['attitude'],velocity=frame['velocity_origin_body'],
        rates=motion.rates.tolist(),acceleration=motion.acceleration.tolist(),angular_acceleration=motion.angular_acceleration.tolist(),
        engines=len(network.engines),loads=len(network.loads),struts=len(network.struts),hinges=len(network.hinges),
        operating_constraints=network.operating.count,controller=result['controller']),expected['stationary_setup'])
    exact('medium_setup',dict(vacuum=result['vacuum'],density=None if 'fluid' not in result else result['fluid']['density'],circulation_count=network.ng),expected['medium_setup'])
    arnoldi=diagnostics['arnoldi']
    exact('modal_algorithm',dict(method=diagnostics['method'],requested_method=diagnostics['requested_method'],count=diagnostics['requested_count'],
        shift=diagnostics['shift'],difference_step=diagnostics['difference_step'],rank_tolerance=diagnostics['rank_tolerance'],
        finite_dimension=diagnostics['finite_dimension'],finite_spectrum=diagnostics['finite_spectrum'],
        integrator_deflation_count=diagnostics['integrator_deflation']['count'],
        **{key:arnoldi[key] for key in ('mass_rank_reduction','retained_dimension','arpack_mode','bmat','which','tolerance','factorizations')}),expected['modal_algorithm'])
    norms=[base['residual'],diagnostics['base_residual']];metric('base_residual',max(norms),values=norms)
    metric('fresh_full_residual',float(np.max(abs(residual))),values=[fresh['residual']])
    metric('arnoldi_shifted_solves',arnoldi['maximum_solve_backward_error'],values=[arnoldi['maximum_solve_backward_error']])
    for name in ('force','moment'):
        a,b=base['applied_'+name],base['support_'+name]
        metric(name+'_balance',math.hypot(*(x+y for x,y in zip(a,b)))/max(1.,math.hypot(*a)+math.hypot(*b)),applied=a,support=b)
    clamps=[c['a'] for c in network.constraints if c['kind']=='ground'];exact('root_clamp_count',len(clamps),1)
    _require(len(clamps)==1,'missing or duplicate clamp.')
    for name,vector,target in [('root_clamp_position',data['r'][clamps[0]].tolist(),job['root_position']),
        ('root_clamp_frame',data['Q'][clamps[0]].ravel().tolist(),[1.,0.,0.,0.,1.,0.,0.,0.,1.])]:
        metric(name,max(abs(a-b) for a,b in zip(vector,target)),reported=vector,expected=target)
    samples=[]
    pa,pb,ra,rb,*_=network.geometry(data['r'],data['Q'])
    midpoint=(pa+pb)/2
    for beam,sl,end,mass,arm in network.source_mass_samples:
        rotations=(ra if end==0 else rb)[sl]
        # Completed source gravity is transferred symmetrically to the two
        # nodes. Its first moment uses the interval midpoint plus each local
        # endpoint CG arm, including for nonuniform mass distributions.
        positions=midpoint[sl]+np.einsum('nij,nj->ni',rotations,arm)
        samples.extend(dict(mass=float(m),position=p.tolist()) for m,p in zip(mass,positions))
    masses=[x['mass'] for x in samples];total=sum(masses)
    mass_report=base['mass_properties']['mass']
    metric('independent_real_mass',max(_relative([mass_report],[total]),_relative([total],[job['expected_real_mass']])),
        endpoint_masses=masses,reconstructed=total,reported=mass_report,expected=job['expected_real_mass'])
    force=[0.,0.,0.];moment=[0.,0.,0.]
    for sample in samples:
        f=[sample['mass']*g for g in job['gravity']];m=_cross(sample['position'],f)
        force=[a+b for a,b in zip(force,f)];moment=[a+b for a,b in zip(moment,m)]
    metric('independent_gravity_wrench',max(_relative(base['applied_force'],force),_relative(base['applied_moment'],moment)),
        samples=samples,reconstructed_force=force,reconstructed_moment=moment,reported_force=base['applied_force'],reported_moment=base['applied_moment'])
    def parity_values(packet):
        return dict(positions=[x for n in packet['nodes'] for x in n['position']],
            rotations=[x for n in packet['nodes'] for row in n['rotation'] for x in row],
            **{key:packet[key] for key in ('applied_force','applied_moment','support_force','support_moment')},
            sensor_positions=[x for s in packet['sensors'] for x in s['position_body']])
    original,restored=parity_values(base),parity_values(fresh)
    channels={key:_relative(value,restored[key]) for key,value in original.items()}
    metric('restored_base_parity',max(channels.values()),reported=original,restored=restored,channels=channels)
    a,m=[np.asarray(result['matrices'][key],dtype=float) for key in ('A','M')]
    valid=a.shape==m.shape==(dimension,dimension) and bool(np.all(np.isfinite(a)) and np.all(np.isfinite(m)))
    exact('full_matrix_shape',dict(A=list(a.shape),M=list(m.shape),finite=valid),expected['full_matrix_shape'])
    _require(valid,'invalid full descriptor matrices.')
    roots=[mode['eigenvalue'] for mode in result['modes']];evidence=spectrum_evidence(roots)
    checks.append(dict(name='modal_spectrum',evidence=deepcopy(evidence),passed=bool(evidence['distinct'] and evidence['positive_enough'] and evidence['unique_conjugates'])))
    right_entries=[];left_entries=[];pairings=[];rights=[];lefts=[];anorm=float(np.linalg.norm(a));mnorm=float(np.linalg.norm(m))
    for i,mode in enumerate(result['modes']):
        lam=complex(*mode['eigenvalue']);vectors={}
        for side,entries in [('right',right_entries),('left',left_entries)]:
            v=np.asarray(mode[side]['real'])+1j*np.asarray(mode[side]['imag'])
            _require(v.shape==(dimension,) and np.all(np.isfinite(v)), 'invalid full eigenvector.')
            vectors[side]=v;defect=a@v-lam*(m@v) if side=='right' else a.T@v-lam.conjugate()*(m.T@v)
            vn=float(np.linalg.norm(v));rn=float(np.linalg.norm(defect));denominator=(anorm+abs(lam)*mnorm)*vn
            _require(denominator>0,'zero pencil/vector norm.')
            entries.append(dict(index=i,eigenvalue=mode['eigenvalue'],residual_norm=rn,vector_norm=vn,A_norm=anorm,M_norm=mnorm,
                denominator=denominator,backward_error=rn/denominator,reported_backward_error=mode[side+'_backward_error']))
        pairing=np.vdot(vectors['left'],m@vectors['right']);value=[float(pairing.real),float(pairing.imag)]
        pairings.append(dict(index=i,value=value,error=abs(complex(*value)-1.),normalized=mode['biorthogonal_normalized']))
        rights.append(vectors['right']);lefts.append(vectors['left'])
    exact('full_vector_shapes',dict(count=len(rights),dimension=dimension,finite=True),expected['full_vector_shapes'])
    for name,entries in [('modal_right_pencil',right_entries),('modal_left_pencil',left_entries)]:
        metric(name,max(max(e['backward_error'],e['reported_backward_error']) for e in entries),entries=entries)
    metric('modal_mass_pairing',max(e['error'] for e in pairings),entries=pairings)
    metric('modal_neutrality',max(abs(a)/max(1.,abs(b)) for a,b in roots),eigenvalues=roots)
    pairs=np.column_stack(lefts).conj().T@m@np.column_stack(rights)
    evidence.update(pencil_checks=dict(right=right_entries,left=left_entries,mass_pairing=pairings),
        mass_pairing_matrix=dict(real=pairs.real.tolist(),imag=pairs.imag.tolist(),scope='All returned modes; diagonal acceptance, cross-pair diagnostic.'))
    _write(stage/'modal-evidence.json',evidence);_write(stage/'physical-checks.json',checks)
    validate_physical_checks(job,checks)
    return dict(values=evidence['values'],physical_checks=checks,modal_evidence=evidence,operations=operations)
