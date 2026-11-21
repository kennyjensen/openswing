"""Replay recorded step equations at fixed saved values, without a new solve.

This validates one discrete problem conditional on its stored input history.
It does not establish an entire trajectory, local error estimate, root uniqueness
or continuous force accuracy. Initial records remain explicitly physical-only.
"""
from copy import deepcopy
import numpy as np
from .aero import AnalysisError
from .equilibrium_state import identity, matching_identity, finite_array
from .time_acceptance import VERSION, PRODUCER, BDF_SCHEME, BDF_SCHEME_V1, SOURCE_BDF_SCHEME, RADAU_SCHEME, RADAU_POSITION_SCHEME, INITIAL_SCHEME, chart_layout


def _fail(message):
    raise AnalysisError('Checkpoint accepted method '+message)


def _number(value,name,*,positive=False):
    from .time_state import scalar
    return scalar(value,'accepted method '+name,positive)


def _relative_policy(actual,expected,name):
    """Policy gates may be far below epsilon; no absolute allowance applies."""
    import math
    if isinstance(expected,dict):
        if not isinstance(actual,dict) or actual.keys()!=expected.keys():_fail(name+' fields disagree.')
        for key,value in expected.items():_relative_policy(actual[key],value,name+'.'+key)
    elif isinstance(expected,list):
        if not isinstance(actual,list) or len(actual)!=len(expected):_fail(name+' shape disagrees.')
        for i,value in enumerate(expected):_relative_policy(actual[i],value,name+f'[{i}]')
    elif type(expected) is int:
        if type(actual) is not int or actual!=expected:_fail(name+' disagrees.')
    elif isinstance(expected,float):
        value=_number(actual,name)
        if not math.isclose(value,expected,rel_tol=32*np.finfo(float).eps,abs_tol=0.):_fail(name+' disagrees.')
    elif type(actual)!=type(expected) or actual!=expected:
        _fail(name+' disagrees.')


def _roundoff_tree(actual,expected,name):
    """Compare input/schema data, allowing floating-point reconstruction only."""
    if isinstance(expected,dict):
        if not isinstance(actual,dict) or actual.keys()!=expected.keys():_fail(name+' fields disagree.')
        for key,value in expected.items():_roundoff_tree(actual[key],value,name+'.'+str(key))
    elif isinstance(expected,(list,tuple)):
        if not isinstance(actual,(list,tuple)) or len(actual)!=len(expected):_fail(name+' shape disagrees.')
        for i,value in enumerate(expected):_roundoff_tree(actual[i],value,name+f'[{i}]')
    elif isinstance(expected,(int,float)) and not isinstance(expected,bool):
        a=_number(actual,name);b=_number(expected,name)
        if abs(a-b)>128*np.finfo(float).eps*max(1.,abs(a),abs(b)):_fail(name+' disagrees.')
    elif type(actual)!=type(expected) or actual!=expected:
        _fail(name+' disagrees.')


def _scaled(actual,expected,scale,name):
    a=np.asarray(actual,dtype=float);b=np.asarray(expected,dtype=float)
    if a.shape!=b.shape or not np.all(np.isfinite(a)) or not np.all(np.isfinite(b)):
        _fail(name+' shape or values are invalid.')
    error=float(np.max(abs(a-b)/scale,initial=0.))
    if not np.isfinite(error) or error>1e-8:_fail(f'{name} disagrees (scaled difference {error:.3g}).')
    return error


def _same_state(system,a,b,name):
    """Use fixed physical scales and actual rotations, not inactive cache fields."""
    n=system.network;f=system.feedback
    if a.time!=b.time:_fail(name+' time disagrees.')
    values=[_scaled(getattr(a,key),getattr(b,key),scale,name+'.'+key) for key,scale in
        [('r',n.L),('Q',1.),('u',system.V),('w',system.W),('U',system.V),
         ('Omega',system.W),('position',n.L),('orientation',1.),('gamma',n.gamma_scale)]]
    # State.x's nodal rotations are absolute; compare their matrices above.
    values.append(_scaled(a.x[6*n.nn:],b.x[6*n.nn:],1.,name+'.algebraic_and_circulation'))
    values.append(_scaled(a.feedback,b.feedback,1. if f is None else f.scales,name+'.feedback'))
    _scaled(a.hinge_charts,b.hinge_charts,1.,name+'.hinge_charts')
    if getattr(n,'source_moving',False):
        _scaled(a.source_angles,b.source_angles,1.,name+'.source_angles')
        _scaled(a.source_attitude,b.source_attitude,1.,name+'.source_attitude')
    _roundoff_tree(a.commands,b.commands,name+'.commands')
    if (a.position_history is None)!=(b.position_history is None):_fail(name+' position sample is missing.')
    if a.position_history is not None:
        from .position_history_checkpoint import pack_sample
        _roundoff_tree(pack_sample(a.position_history),pack_sample(b.position_history),name+'.position_sample')
    return max(values,default=0.)


def _same_options(system,a,b,name):
    from .time_state import condition_data,motion_data
    n=system.network
    # Kinematic cache consistency is separately checked against physical state.
    _roundoff_tree(condition_data(a['condition_override']),condition_data(b['condition_override']),name+'.condition')
    _roundoff_tree(motion_data(a['motion_override']),motion_data(b['motion_override']),name+'.motion')
    _roundoff_tree(a.get('operating_targets',{}),b.get('operating_targets',{}),name+'.targets')
    _scaled(a.get('hinge_charts',()),b.get('hinge_charts',()),1.,name+'.hinge_charts')
    for i,scale in enumerate((system.V,system.W,system.A,system.W**2)):
        _scaled(a['elastic_motion'][i],b['elastic_motion'][i],scale,name+f'.elastic_motion[{i}]')
    _scaled(a['circulation_rate'],b['circulation_rate'],n.gamma_scale*system.W,name+'.circulation_rate')
    _scaled(a['gravity_override'],b['gravity_override'],system.A,name+'.gravity')


def _selection(data,previous,time):
    selection=data['selection']
    if not isinstance(selection,dict):_fail('selection is invalid.')
    mode=selection.get('mode')
    if mode=='ordinary':
        if set(selection)!={'mode'}:_fail('ordinary selection has unsupported fields.')
        return
    if mode!='two_half_steps' or selection.get('accepted_substep')!=2:_fail('selection is unsupported.')
    if set(selection)!={'mode','macro_start_time','midpoint_time','macro_end_time','accepted_substep'}:
        _fail('half-step selection fields disagree.')
    start=_number(selection['macro_start_time'],'macro start')
    middle=_number(selection['midpoint_time'],'midpoint')
    end=_number(selection['macro_end_time'],'macro end')
    if not start<middle<end or middle!=previous.time or end!=time:_fail('half-step selection times disagree.')
    _roundoff_tree(middle-start,end-middle,'half-step selection lengths')


def _unpack(n,data,feedback,name):
    """Recorded history cannot use equilibrium warm-start missing-value defaults."""
    from .time_state import unpack_state
    values=data['network']['operating_values']
    if not isinstance(values,dict):_fail(name+' operating values are invalid.')
    for row in n.operating.constraints:
        if row.variable not in values:_fail(name+' is missing active operating value '+row.variable+'.')
        _number(values[row.variable],name+'.'+row.variable)
    return unpack_state(n,data,feedback)


def _position_policy(system,method,order,*,cached=False):
    from .position_history_checkpoint import method_metadata
    expected=None if cached else method_metadata(system,order)
    if expected is None:
        if 'position_history' in method:_fail('unexpected position-history policy metadata.')
    else:
        if 'position_history' not in method:_fail('position-history policy metadata is missing.')
        _roundoff_tree(method['position_history'],expected,'position-history policy')


def validate_accepted_method(model,saved,*,require_discrete=False):
    """Validate optional owned evidence; never downgrade a malformed new record.

The caller's saved mapping is not changed. Legacy and initial records explicitly
report physical-only scope; ``require_discrete`` refuses either. BDF/Radau replay
uses an independent network and original input context, never future forcing.
No initializer, Newton solve, projection or temporal refinement is called.
"""
    if not isinstance(saved,dict):_fail('checkpoint is invalid.')
    if 'accepted_method' not in saved:
        context=saved.get('context')
        if isinstance(context,dict) and isinstance(context.get('setup'),dict) and 'saved_history_scope' in context['setup']:
            _fail('scoped saved history launch requires its accepted method record.')
        if require_discrete:_fail('record is missing; legacy state has no replayable accepted step.')
        return dict(level='legacy_physical_only',discrete_replayed=False,
            limitation='No method-owned evidence; existing physical checkpoint checks remain required.')
    try:
        data=deepcopy(saved['accepted_method'])
        if not isinstance(data,dict) or type(data.get('version')) is not int or data.get('version')!=VERSION or data.get('producer_policy')!=PRODUCER:
            _fail('record version or producer policy is unsupported.')
        kind=data['kind'];schemes={'initial':(INITIAL_SCHEME,),'bdf':(BDF_SCHEME_V1,BDF_SCHEME,SOURCE_BDF_SCHEME),'radau_iia':(RADAU_SCHEME,RADAU_POSITION_SCHEME)}
        if kind not in schemes or data['scheme'] not in schemes[kind]:_fail('scheme is unsupported.')
        level='physical_only' if kind=='initial' else 'captured_discrete_problem'
        if data['validation_level']!=level:_fail('record validation level disagrees with its kind.')
        if require_discrete and kind=='initial':_fail('initial record contains no accepted discrete step.')
        end=_number(data['end_time'],'end time');tolerance=_number(data['tolerance'],'tolerance',positive=True)
        if tolerance>1e-5:_fail('tolerance exceeds the supported solver range.')
        side=data['endpoint_side']
        if side not in ('left','right'):_fail('endpoint side is invalid.')
        inputs=data['accepted_inputs'];setup=inputs['setup'];method=inputs['method']
        _roundoff_tree(method['tolerance'],tolerance,'original tolerance')
        policy=inputs['input_policy']
        if policy not in ('physical_time_forcing','cached_anchor_before_next_inputs'):_fail('input policy is unsupported.')
        if kind!='initial' and policy!='physical_time_forcing':_fail('step requires its original physical forcing.')
        if policy=='cached_anchor_before_next_inputs' and (setup['forcing']!='' or inputs['forcing_offsets']!={}):
            _fail('cached initial anchor must not be evaluated with future forcing.')
        _roundoff_tree(saved['forcing_side'],side,'saved endpoint side')
        _roundoff_tree(saved['validation_loads'],setup['loads'],'saved validation loads')
        # Future input replacement may change forcing and active load lists.
        # The physical model, constraint chart and normalization remain fixed.
        continuation=saved['context']['setup']
        for key in ('panels','condition','motion','gravity','gravity_magnitude','mesh_loads','strut_mode','frame','controller','load_targets','actuator_constraints','saved_history_scope','structural_operator'):
            _roundoff_tree(setup.get(key),continuation.get(key),'original physical setup.'+key)
        scoped='saved_history_scope' in setup or 'saved_history_scope' in continuation
        right_initial=kind=='initial' and data.get('phase')=='history_transition_right_limit'
        if scoped or right_initial:
            from .time_saved_history import validate_scope
            validate_scope(setup,required=True)
            validate_scope(continuation,required=True)
            for key in ('forcing','loads'):
                _roundoff_tree(setup[key],continuation[key],'saved history scope.'+key)
            if policy!='physical_time_forcing':_fail('saved history launch requires its physical forcing policy.')
        from .network import StaticNetwork
        from .equilibrium_state import recipe_from_identity
        from .inertia import Motion
        from .feedback import FeedbackSystem
        from .operating import time_operating_constraints
        from .forcing import TimeForcing
        from .time_integration import TimeSystem,bdf_coefficients,bdf_nonlinear_gate
        from .time_state import read_condition,unpack_options,restore_feedback,checkpoint_frame_options,finite_map
        c=read_condition(setup['condition']);motion=Motion(**setup['motion'])
        from .time_network import time_network_class
        network_class=time_network_class(model,c,frame=setup['frame'],
            structural_operator=setup.get('structural_operator'),identity=inputs.get('identity'),
            controller=setup['controller'],actuator_constraints=setup.get('actuator_constraints'),
            strut_mode=setup['strut_mode'],require_saved_operator=True)
        n=network_class(model,setup['panels'],c,setup['gravity'],setup['mesh_loads'],
            motion if c is None else None,time_operating_constraints(setup['frame'],setup.get('load_targets'),setup.get('actuator_constraints')),setup['strut_mode'],
            mesh_recipe=recipe_from_identity(inputs.get('identity')))
        actual_identity=identity(n)
        if not matching_identity(inputs['identity'],actual_identity) or not matching_identity(saved['context']['identity'],actual_identity):
            _fail('aircraft, mesh or topology identity disagrees.')
        n.loads=deepcopy(setup['loads'])
        f=None if setup['controller'] is None else FeedbackSystem(n,setup['controller'])
        current=_unpack(n,saved['state'],f,'current endpoint')
        endpoint=_unpack(n,data['endpoint']['state'],f,'recorded endpoint')
        if current.time!=end or endpoint.time!=end:_fail('endpoint time disagrees with the physical state.')
        restore_feedback(f,inputs['feedback'],endpoint)
        before_data=data.get('previous') if kind=='bdf' else data.get('seed') if kind=='radau_iia' else None
        before=None if before_data is None else _unpack(n,before_data,f,'step seed')
        forcing=TimeForcing(setup['forcing'],model,c,n.motion,end,setup['frame'],f,
            start_time=end if before is None else before.time,load_targets=setup.get('load_targets'),actuator_constraints=setup.get('actuator_constraints'))
        offsets=finite_map(inputs['forcing_offsets'],[channel['name'] for channel in forcing.channels],'accepted forcing offsets')
        for channel in forcing.channels:channel['initial']=offsets[channel['name']]
        system=TimeSystem(n,forcing,f,gravity_magnitude=setup.get('gravity_magnitude'))
        if kind=='bdf' and ((data['scheme']==SOURCE_BDF_SCHEME) != getattr(n,'source_moving',False)):
            _fail('BDF rotation policy disagrees with the structural operator.')
        position_radau=data['scheme']==RADAU_POSITION_SCHEME
        if position_radau and system.position_lift is None:_fail('position-defect Radau chart requires active position history.')
        _roundoff_tree(data['layout'],chart_layout(system,position_radau=position_radau),'chart layout')
        if system.position_lift is not None:system.position_lift.tolerance=max(tolerance,1e-8)
        current_options=checkpoint_frame_options(n,current,unpack_options(n,current,saved['options']),setup.get('gravity_magnitude'))
        endpoint_options=checkpoint_frame_options(n,endpoint,unpack_options(n,endpoint,data['endpoint']['options']),setup.get('gravity_magnitude'))
        endpoint_defect=_same_state(system,current,endpoint,'recorded endpoint')
        _same_options(system,current_options,endpoint_options,'recorded endpoint options')
        if kind=='initial':
            if data['continuous_certificate'] is not False or not isinstance(data['phase'],str):_fail('initial provenance is invalid.')
            _roundoff_tree(data['selection'],dict(mode='initial_snapshot'),'initial selection')
            _roundoff_tree(method['order'],0,'initial method order')
            _roundoff_tree(method['maximum_step'],0.,'initial method step')
            _position_policy(system,method,0,cached=policy=='cached_anchor_before_next_inputs')
            residual,detail=n.residual(current.x,detail=True,**current_options)
            if f is not None:residual=np.r_[residual,f.evaluate(current,detail)[0]]
            error=float(np.max(abs(residual)))
            if not np.all(np.isfinite(residual)) or error>max(10*tolerance,1e-8):_fail('initial physical residual is inconsistent.')
            return dict(level='initial_physical_only',discrete_replayed=False,phase=data['phase'],
                physical_residual=error,continuous_certificate=False,
                limitation='No hidden-derivative, initial authority or discrete-step authentication is supplied by an initial record.')
        if before is None or not before.time<end:_fail('step seed must precede its endpoint.')
        step=_number(data['step'],'step',positive=True)
        _roundoff_tree(step,end-before.time,'actual step')
        _roundoff_tree(method['maximum_step'],step,'captured step')
        _selection(data,before,end)
        if kind=='bdf':
            order=data['effective_order']
            if isinstance(order,bool) or order not in (1,2):_fail('effective BDF order is invalid.')
            _roundoff_tree(method['order'],order,'effective BDF order')
            past=None if data['previous2'] is None else _unpack(n,data['previous2'],f,'second predecessor')
            if (past is None)!=(order==1):_fail('BDF order and second predecessor disagree.')
            if past is not None and not past.time<before.time:_fail('second predecessor must precede the first.')
            if past is not None and data['selection']['mode']=='two_half_steps' and past.time!=data['selection']['macro_start_time']:
                _fail('accuracy BDF second predecessor is not the macro-step start.')
            continuation_before=saved['older']
            if continuation_before is None:
                replaced=continuation['forcing']!=setup['forcing']
                if end not in forcing.breaks and not replaced:
                    _fail('BDF continuation predecessor is missing without a forcing break or input replacement.')
            else:
                retained=_unpack(n,continuation_before,f,'continuation predecessor')
                _same_state(system,retained,before,'continuation predecessor')
            _position_policy(system,method,order)
            coefficients=bdf_coefficients(end-before.time,None if past is None else before.time-past.time)
            _roundoff_tree(data['coefficients'],coefficients.tolist(),'BDF coefficients')
            values=finite_array(data,'values',(system.size,))
            if system.position_lift is not None:
                for state in (before,past,endpoint):
                    if state is not None:system.position_lift.validate_sample(state,forcing)
            residual,computed,computed_options=system.residual(values,before,past,end,coefficients,side=side,detail=True)
            if data['scheme']==BDF_SCHEME_V1:
                if 'nonlinear_tolerance' in data or 'nonlinear_policy' in data:
                    _fail('legacy BDF record contains a newer nonlinear policy.')
                # Historical producers accepted at the requested tolerance;
                # applying a newer gate would retroactively invalidate them.
                gate=tolerance
            else:
                expected_gate,expected_policy=bdf_nonlinear_gate(system,coefficients,tolerance)
                gate=_number(data['nonlinear_tolerance'],'BDF nonlinear tolerance',positive=True)
                if gate>tolerance:_fail('BDF nonlinear tolerance relaxes the requested tolerance.')
                _relative_policy(gate,expected_gate,'BDF nonlinear tolerance')
                _relative_policy(data['nonlinear_policy'],expected_policy,'BDF nonlinear policy')
        else:
            from .radau_time import NODES,INVERSE
            from .nonlinear_initial import InitialSystem
            _roundoff_tree(method['order'],5,'Radau order')
            if saved['older'] is not None:_fail('Radau producer does not retain a BDF continuation predecessor.')
            _position_policy(system,method,5)
            if position_radau:
                from .position_history_radau import PositionHistoryRadauChart
                chart=PositionHistoryRadauChart(system,before,setup['frame'])
            else:
                chart=InitialSystem(system,before,setup['frame'],apply_forcing=True)
            initial=finite_array(data,'initial_chart_values',(chart.size,))
            if np.any(initial!=0.):_fail('physical Radau chart must start at the recorded seed.')
            increments=finite_array(data,'increments',(3,chart.size))
            times=before.time+NODES*(end-before.time);times[-1]=end
            _roundoff_tree(data['stage_times'],times.tolist(),'Radau stage times')
            expected_sides=['right','right',side]
            if data['stage_sides']!=expected_sides:_fail('Radau stage sides disagree.')
            gate=min(tolerance,max(1e-12,tolerance*min(1.,(end-before.time)*chart.W)**2))
            _roundoff_tree(data['stage_tolerance'],gate,'Radau stage tolerance')
            rates=INVERSE@increments/(end-before.time)
            if not np.all(np.isfinite(rates)):_fail('Radau derived rates are nonfinite.')
            residual=np.concatenate([chart.residual(z,d,t,side=s) for z,d,t,s in zip(increments,rates,times,expected_sides)])
            _,computed,computed_options=chart.residual(increments[-1],rates[-1],end,side=side,detail=True)
        error=float(np.max(abs(residual)))
        if not np.all(np.isfinite(residual)) or error>gate:_fail(f'original discrete residual fails ({error:.3g} > {gate:.3g}).')
        endpoint_defect=max(endpoint_defect,_same_state(system,computed,endpoint,'computed endpoint'))
        _same_options(system,computed_options,endpoint_options,'computed endpoint options')
        return dict(level='recorded_discrete_equations',kind=kind,scheme=data['scheme'],discrete_replayed=True,
            residual=error,tolerance=gate,endpoint_scaled_difference=endpoint_defect,
            selection=deepcopy(data['selection']),root_uniqueness_replayed=False,
            limitation='Conditional on recorded seed/history; no whole-trajectory, root-uniqueness, continuous-force or accuracy-estimator certification.')
    except AnalysisError:
        raise
    except (KeyError,TypeError,ValueError,IndexError,OverflowError) as exc:
        raise AnalysisError(f'Checkpoint accepted method is incomplete or malformed: {exc}') from exc
