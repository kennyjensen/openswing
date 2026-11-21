"""Portable physical steady-state guesses for checked equilibrium continuation.

This is an OpenSwing format, not an ASWING .pnt or unsteady restart file.
The aircraft and mesh must match. Steady reuse solves all equations again;
time launch preserves the saved setup and checks its zero-local-rate residual.
"""
import hashlib
from dataclasses import asdict
import numpy as np
from .aero import AnalysisError
from .discretization import CURRENT_MESH_RECIPE, LEGACY_MESH_RECIPE, checked_recipe
from .beam_spline import NATURAL


def recipe_from_identity(saved):
    """Resolve saved construction without changing any identity or state field.

    Old packets predate recipe metadata and used all property-table breaks for
    both required nodes and arc quadrature. The v1 recipe removed reporting-only
    breaks; v2 integrates the physical spline arc. Replaying either old packet
    retains its original equations.
    """
    if not isinstance(saved, dict):
        raise AnalysisError('Saved mesh identity is missing or malformed.')
    try:
        return checked_recipe(saved.get('mesh_recipe', LEGACY_MESH_RECIPE))
    except (TypeError, ValueError) as exc:
        raise AnalysisError('Unknown saved mesh recipe; cannot reconstruct its discretization.') from exc


def warm_start_recipe(model, panels, saved):
    """Keep the requested mesh; reuse an old recipe only with its old settings."""
    if saved is None:
        return CURRENT_MESH_RECIPE
    if not isinstance(saved, dict):
        raise AnalysisError('Expected an OpenSwing equilibrium state.')
    recipe = recipe_from_identity(saved.get('identity'))
    if recipe != CURRENT_MESH_RECIPE:
        from .discretization import normalize, beam_settings
        launch = saved.get('launch')
        if not isinstance(launch, dict) or 'panels' not in launch:
            raise AnalysisError('Saved legacy equilibrium mesh settings do not match the request; recompute for the new mesh.')
        requested, original = normalize(panels, model), normalize(launch['panels'], model)
        # The UI may serialize an empty override map as an integer count.
        # Compare the actual per-beam settings, keeping explicit nodes distinct
        # from count/spacing settings even when they happen to generate alike.
        if any(beam_settings(b, requested) != beam_settings(b, original) for b in model.beams):
            raise AnalysisError('Saved legacy equilibrium mesh settings do not match the request; recompute for the new mesh.')
    return recipe


def identity(n):
    result = dict(model_sha256=hashlib.sha256(n.model.dumps().encode()).hexdigest(),
        nodes=n.rj.tolist(),elements=np.column_stack((n.a,n.b)).tolist(),
        stations={str(k):[ts.tolist(),ids.tolist()] for k,(ts,ids) in n.station_nodes.items()},
        constraints=[dict(kind=c['kind'],type=c['type'],a=int(c['a']),b=None if c['b'] is None else int(c['b'])) for c in n.constraints],
        circulation_count=n.ng)
    # Untagged packets retain the historical natural beam interpolation.
    # Keep their identity bytes unchanged; a nondefault policy must never
    # reuse the same-source/mesh identity of different material equations.
    if n.model.beam_interpolation != NATURAL:
        result['beam_interpolation'] = n.model.beam_interpolation
    if getattr(n, 'structural_operator', None) is not None:
        result['structural_operator'] = n.structural_operator
    # Source Eq.48 uses a different deformed arc metric from older packets.
    # Preserve ordinary-policy identity bytes; source descendants share this tag.
    if getattr(n, 'deformed_interval_measure', None) is not None:
        result['deformed_interval_measure'] = n.deformed_interval_measure
    # Absence is the historical all-table recipe. Preserve old packet identity
    # exactly; fresh states explicitly identify the corrected construction.
    if n.mesh_recipe != LEGACY_MESH_RECIPE:
        result['mesh_recipe'] = n.mesh_recipe
    if getattr(n, 'quiescent_density', None) is not None:
        result['quiescent_density'] = n.quiescent_density
        if any(not beam.lifting for beam in n.model.beams):
            result['quiescent_body_added_mass_factor'] = n.quiescent_body_added_mass_factor
    if n.circulation_basis.modes:
        result['circulation_modes']={str(k):v for k,v in n.circulation_basis.modes.items()}
    if getattr(n, 'rigid_weight_attachments', None):
        from copy import deepcopy
        result['rigid_weight_attachments'] = deepcopy(n.rigid_weight_attachments)
    return result


def reaction_scales(n):
    out=np.empty(n.nc)
    for c in n.constraints:
        out[c['sl']]=([n.F]*3+[n.F*n.L]*3) if c['type'] in (0,3) else [n.F*(n.L if c['type']==2 else 1.)]*3
    return out


def feedback_layout(feedback):
    if feedback is None:return None
    return dict(actuators=[o['actuator'] for o in feedback.outputs],integrals=list(feedback.integrals),
        signals=list(feedback.signals),states=[dict(name=s['name'],unit=s['unit']) for s in feedback.states])


def hinge_charts(n,x,*,centers=None):
    """Physical lifted hinge angles; matrices alone contain no turn count."""
    from .network import exp,log
    q=exp(np.asarray(x[:6*n.nn]).reshape(n.nn,6)[:,3:])
    from .hinge_history import current,checked,joints
    values=current(n) if centers is None else checked(n,centers)
    result=[]
    for c,center in zip(joints(n),values):
        law=c['law']
        relative=q[c['a']].T@q[c['b']]
        angle=center+float(law.axis@log(exp(-center*law.axis)@relative))
        result.append(dict(joint=law.index,angle_rad=angle))
    return result


def checked_hinge_charts(n,saved,x):
    from .network import exp,log
    joints=[c for c in n.constraints if c['type']==3]
    rows=saved.get('hinge_charts')
    if not isinstance(rows,list) or len(rows)!=len(joints):
        raise AnalysisError('Invalid saved equilibrium hinge_charts layout.')
    q=exp(np.asarray(x[:6*n.nn]).reshape(n.nn,6)[:,3:])
    centers=[]
    for c,row in zip(joints,rows):
        if (not isinstance(row,dict) or set(row)!={'joint','angle_rad'}
                or type(row['joint']) is not int or row['joint']!=c['law'].index):
            raise AnalysisError('Invalid saved equilibrium hinge_charts joint identity.')
        angle=row['angle_rad']
        if isinstance(angle,bool) or not isinstance(angle,(int,float)):
            raise AnalysisError('Invalid saved equilibrium hinge_charts angle_rad.')
        try:angle=float(angle)
        except OverflowError as exc:raise AnalysisError('Invalid saved equilibrium hinge_charts angle_rad.') from exc
        if not np.isfinite(angle):raise AnalysisError('Invalid saved equilibrium hinge_charts angle_rad.')
        relative=q[c['a']].T@q[c['b']]
        centered=exp(-angle*c['law'].axis)@relative
        if not np.all(np.isfinite(centered)):
            raise AnalysisError('Saved equilibrium hinge_charts cannot represent the saved rotations.')
        defect=float(np.linalg.norm(log(centered)))
        if not np.isfinite(defect) or defect>1e-7:
            raise AnalysisError('Saved equilibrium hinge_charts disagree with the saved rotations.')
        centers.append(float(angle))
    return centers


def capture(n,x,*,feedback=None,feedback_values=None,commands=None,residual=None,include_launch=True,launch_frame=None,hinge_charts_override=None):
    r,q,force,moment,reaction,gamma=n.unpack(x)
    condition,motion,operating=n.operating.apply(x[n.operating_start:])
    control=None
    if feedback is not None:
        control=dict(layout=feedback_layout(feedback),values=np.asarray(feedback_values,dtype=float).tolist(),
            commands={**feedback.commands,**feedback.bias,**(commands or {})},
            prescribed_bias={o['actuator']:float(getattr(n.condition,o['attribute']).get(o['index'],0.)) for o in feedback.outputs})
    saved=dict(format='openswing-equilibrium',version=1,identity=identity(n),
        positions=r.tolist(),rotations=np.asarray(x[:6*n.nn]).reshape(n.nn,6)[:,3:].tolist(),
        internal_force=force.tolist(),internal_moment=moment.tolist(),reactions=(reaction*reaction_scales(n)).tolist(),
        circulation=gamma.tolist(),operating_values={k:float(v) for k,v in operating.items()},feedback=control,
        residual=None if residual is None else float(residual),
        units='Physical quantities in ASW input units; spatial rotation vectors in radians. Numerical solver scales are not stored.',
        limitations=['This is a steady state. It contains no unsteady history or derivative state.',
                    'The source and mesh must match. Steady reuse corrects the full equilibrium; time launch validates the saved setup at zero local rates.',
                    'Local correction does not prove that a nonlinear branch is unique or that a fold has been followed.'])
    if n.hinges:
        saved.update(version=2,hinge_charts=hinge_charts(n,x,centers=hinge_charts_override))
        saved['limitations'].append('Hinge angle_rad values retain the unwrapped static branch in radians. Matrices alone cannot authenticate their whole-turn count; time/checkpoint chart persistence is not provided by this static format.')
    if include_launch:
        from .time_state import portable,condition_data,motion_data
        saved['launch']=portable(dict(version=1,panels=n.panels,condition=condition_data(condition),motion=motion_data(motion),
            gravity=n.gravity if n.gravity_override else None,loads=n.loads,
            strut_mode='wire' if n.tension_only else 'bilateral',controller=None if feedback is None else feedback.definition,
            frame=launch_frame or dict(position=[0,0,0],attitude=[0,0,0],velocity=[0,0,0],gravity_magnitude=None),
            released_constraints=[asdict(c) for c in n.operating.constraints]))
        if getattr(n, 'quiescent_density', None) is not None:
            saved['launch']['quiescent_density'] = n.quiescent_density
            if any(not beam.lifting for beam in n.model.beams):
                saved['launch']['quiescent_body_added_mass_factor'] = n.quiescent_body_added_mass_factor
    return saved


def validate(n,saved):
    if (not isinstance(saved,dict) or saved.get('format')!='openswing-equilibrium'
            or type(saved.get('version')) is not int or saved['version'] not in (1,2)):
        raise AnalysisError('Expected a version-1 or version-2 OpenSwing equilibrium state.')
    current = identity(n)
    if ('deformed_interval_measure' in current and isinstance(saved.get('identity'), dict)
            and saved['identity'].get('structural_operator') == current.get('structural_operator')
            and saved['identity'].get('deformed_interval_measure') != current['deformed_interval_measure']):
        raise AnalysisError('Saved source interval measure is missing or incompatible. Recompute the source equilibrium before reuse.')
    if not matching_identity(saved.get('identity'),current):
        raise AnalysisError('Saved equilibrium aircraft, mesh or constraint layout does not match the current configuration.')
    if n.hinges and saved['version']==1:
        raise AnalysisError('Version-1 hinge equilibrium states do not retain winding. Recompute the static equilibrium; no zero-turn branch is inferred.')
    if not n.hinges and (saved['version']!=1 or 'hinge_charts' in saved):
        raise AnalysisError('A non-hinge equilibrium requires the version-1 format without hinge_charts.')


def matching_identity(saved,current):
    """Exact model/topology match, allowing only mesh-generation roundoff.

    Native and WASM libm can differ by a few ulps in cosine-spaced stations.
    These coordinates describe the same mesh; they are not a new geometry or
    permission to interpolate a saved state onto a different discretization.
    """
    if not isinstance(saved,dict) or saved.keys()!=current.keys():return False
    if any(saved[k]!=current[k] for k in current if k not in ('nodes','stations')):return False
    def roundoff_equal(a,b):
        try:a,b=np.asarray(a,dtype=float),np.asarray(b,dtype=float)
        except (ValueError,TypeError,OverflowError):return False
        if a.shape!=b.shape or not np.all(np.isfinite(a)) or not np.all(np.isfinite(b)):return False
        scale=max(float(np.max(abs(b),initial=0.)),np.finfo(float).tiny)
        return bool(np.all(abs(a-b)<=8*np.finfo(float).eps*scale))
    if not roundoff_equal(saved['nodes'],current['nodes']):return False
    stations=saved['stations']
    if not isinstance(stations,dict) or stations.keys()!=current['stations'].keys():return False
    for name,(points,indices) in current['stations'].items():
        entry=stations[name]
        if not isinstance(entry,list) or len(entry)!=2 or entry[1]!=indices:return False
        if not roundoff_equal(entry[0],points):return False
    return True


def finite_array(saved,key,shape):
    try:out=np.asarray(saved[key],dtype=float)
    except (KeyError,ValueError,TypeError) as exc:raise AnalysisError(f'Invalid saved equilibrium {key}.') from exc
    if out.shape!=shape or not np.all(np.isfinite(out)):raise AnalysisError(f'Invalid saved equilibrium {key} shape or values.')
    return out


def restore(n,saved,*,install_hinge_charts=True):
    if isinstance(saved,dict) and type(saved.get('version')) is int and saved['version']==1 and n.hinges:
        from .legacy_hinge_state import recover
        saved=recover(n,saved)
    validate(n,saved)
    x=restore_physical_fields(n,saved)
    if n.hinges:
        centers=checked_hinge_charts(n,saved,x)
        if install_hinge_charts:
            for c,center in zip((c for c in n.constraints if c['type']==3),centers):
                c['angle_chart']=center
    return x


def restore_physical_fields(n,saved):
    """Decode physical fields only; caller validates identity and owns charts."""
    x=np.zeros(n.size)
    x[:6*n.nn].reshape(n.nn,6)[:,:3]=(finite_array(saved,'positions',(n.nn,3))-n.rj)/n.L
    x[:6*n.nn].reshape(n.nn,6)[:,3:]=finite_array(saved,'rotations',(n.nn,3))
    internal=x[6*n.nn:6*(n.nn+n.ne)].reshape(n.ne,6)
    internal[:,:3]=finite_array(saved,'internal_force',(n.ne,3))/n.F
    internal[:,3:]=finite_array(saved,'internal_moment',(n.ne,3))/(n.F*n.L)
    x[6*(n.nn+n.ne):n.gamma_start]=finite_array(saved,'reactions',(n.nc,))/reaction_scales(n)
    x[n.gamma_start:n.operating_start]=n.circulation_basis.encode(finite_array(saved,'circulation',(n.circulation_basis.panels,)))/n.gamma_scale
    values=saved.get('operating_values',{})
    if not isinstance(values,dict):raise AnalysisError('Invalid saved operating values.')
    for i,c in enumerate(n.operating.constraints):
        if c.variable not in values:continue  # A new trim variable starts at its prescribed value.
        value=values[c.variable]
        if not isinstance(value,(int,float)) or not np.isfinite(value):raise AnalysisError('Invalid saved operating value.')
        if c.variable=='speed':
            if value<=0:raise AnalysisError('Saved equilibrium speed must be positive.')
            x[n.operating_start+i]=np.log(value/n.operating.base[c.variable])
        else:x[n.operating_start+i]=(value-n.operating.base[c.variable])/n.operating.scale[c.variable]
    return x


def restore_feedback(n,feedback,state,saved,*,preserve_commands=False):
    data=saved.get('feedback')
    if not isinstance(data,dict) or data.get('layout')!=feedback_layout(feedback):
        raise AnalysisError('Saved equilibrium controller state layout does not match.')
    values=finite_array(data,'values',(feedback.size,))
    expected=set(feedback.commands)|set(feedback.bias)
    commands=data.get('commands')
    if not isinstance(commands,dict) or set(commands)!=expected or any(not isinstance(v,(int,float)) or not np.isfinite(v) for v in commands.values()):
        raise AnalysisError('Saved controller commands do not match the selected channels.')
    prescribed=data.get('prescribed_bias',{})
    if not isinstance(prescribed,dict) or set(prescribed)!=set(feedback.bias) or any(not isinstance(v,(int,float)) or not np.isfinite(v) for v in prescribed.values()):
        raise AnalysisError('Invalid saved actuator bias definition.')
    explicit=feedback.definition.get('commands',{})
    for name in feedback.commands:
        if preserve_commands or name not in explicit:feedback.commands[name]=float(commands[name])
    for name in feedback.bias:
        # A changed prescribed setting is an explicit new bias. Otherwise
        # retain the solved command, including a previous command-trim result.
        if preserve_commands or feedback.bias[name]==prescribed[name]:feedback.bias[name]=float(commands[name])
    state.feedback=values.copy();feedback.base=values.copy()


def check_tangent_rank(jac,progress=None):
    """Preserve the full column-scaled SVD gate, with sparse certification."""
    from scipy.sparse import issparse
    if issparse(jac):
        from .sparse_rank import column_scaled_inverse_bound
        report=None if progress is None else lambda done,total:progress('equilibrium_rank',done,total)
        bound=column_scaled_inverse_bound(jac,progress=report)
        if bound > 1e-10:
            return dict(rank_check='sparse inverse-norm certificate',
                column_scaled_reciprocal_condition=None,
                column_scaled_reciprocal_condition_lower_bound=bound)
        jac=jac.toarray()
    if progress is not None:progress('equilibrium_rank_svd',0,jac.shape[0])
    norms=np.linalg.norm(jac,axis=0)
    singular=np.linalg.svd(jac/np.maximum(norms,1e-30),compute_uv=False)
    reciprocal=float(singular[-1]/singular[0]) if singular[0]>0 else 0.
    if not np.isfinite(reciprocal) or reciprocal<1e-10:
        raise AnalysisError('Warm equilibrium tangent is singular; refine the parameter step or inspect a fold/mechanism.')
    return dict(rank_check='full-Jacobian SVD',column_scaled_reciprocal_condition=reciprocal)


def correct(n,initial,tolerance,residual_options,*,final_tangent=None,progress=None):
    from contextlib import nullcontext
    from .time_integration import newton,StepFailure
    from .seeded_corrector import attach,phase
    if isinstance(initial,dict) and initial.get('feedback') is not None:
        raise AnalysisError('A controller equilibrium seed requires the matching controller definition.')
    snapshot=[(c,c.get('angle_chart')) for c in n.constraints if c['type']==3]
    x=restore(n,initial)
    function=lambda v:n.residual(v,1.,**residual_options)
    from .source_coupled import SourceCoupledNetwork
    from .source_airflow import SourceAirflowNetwork
    if (type(n) is SourceCoupledNetwork or
            (type(n) is SourceAirflowNetwork and n.steady_trim)):
        # Constrained wall-root probes belong inside the network Jacobian.
        # Keep its dense recovery path as well as its sparse beam factors:
        # generic residual differences can move the clamped root through the
        # image plane. Physical trial states still use the ordinary residual.
        function.jacobian_builder=lambda v:n.jacobian(v,1.,_direct_geometry=False,**residual_options)
    if progress is not None:
        # Newton already observes its residual and dense matrix assembly. Keep
        # these separate from time integration and final acceptance checks.
        def iteration_progress(stage,current,total):
            names={'time_iteration':'equilibrium_iteration',
                   'time_tangent':'equilibrium_iteration_tangent'}
            progress(names.get(stage,stage),current,total)
        function.progress=iteration_progress
    seeded_report={}
    trace=[]
    def limit_correction(delta):
        # Each node moves by at most one radian. Relative hinge increments
        # therefore remain inside the current half-turn chart.
        largest=np.max(np.linalg.norm(delta[:6*n.nn].reshape(n.nn,6)[:,3:],axis=1),initial=0.)
        return delta/max(1.,float(largest))
    def accepted_state(value):
        from .network import exp,log
        value=value.copy()
        rows=hinge_charts(n,value)
        for c,row in zip((c for c in n.constraints if c['type']==3),rows):
            c['angle_chart']=row['angle_rad']
        nodal=value[:6*n.nn].reshape(n.nn,6)
        nodal[:,3:]=log(exp(nodal[:,3:]))
        trace.append(rows)
        return value
    try:
        hooks=dict(limit_correction=limit_correction,accepted_state=accepted_state) if n.hinges else {}
        with attach(n,function,initial,residual_options,final_tangent=final_tangent,report=seeded_report) as builder:
            observed=builder is not None
            if observed:
                # Observe only an eligible native instance. Declined adapters
                # retain their old attribute requirements and result schema.
                n._seeded_corrector_diagnostics=seeded_report
            with phase(n,seeded_report,'newton') if observed else nullcontext():
                values,iteration_factor,iterations,builds=newton(function,x,tolerance,**hooks)
                # This factor is no longer used. Release its full matrix and LU
                # before constructing a fresh final tangent and rank check.
                del iteration_factor
                if builder is not None:builder.after_newton()
            if observed:
                seeded_report.update(newton_tangent_builds=builds,
                    dense_tangent_builds=builds-len(seeded_report['builds']))
        with phase(n,seeded_report,'final_tangent') if observed else nullcontext():
            if observed:
                # Same complete final equations and probes as the dense path.
                # Never reuse a Newton approximation for the acceptance check.
                report=None if progress is None else lambda stage,done,total:progress('equilibrium_tangent',done,total)
                jac=n.jacobian(values,1.,_sparse=True,_direct_geometry=False,progress=report)
            else:
                final_options=residual_options
                if final_tangent is None and progress is not None:
                    from .network import StaticNetwork
                    # Preserve adapters that do not accept a progress keyword.
                    # Never retry a failed assembly merely to report progress.
                    if getattr(n.jacobian,'__func__',None) is StaticNetwork.jacobian:
                        final_options=dict(residual_options,progress=lambda stage,done,total:
                            progress('equilibrium_final_tangent',done,total))
                jac=(n.jacobian(values,1.,**final_options) if final_tangent is None else final_tangent(values))
        with phase(n,seeded_report,'final_rank') if observed else nullcontext():
            rank=check_tangent_rank(jac,progress)
    except BaseException as exc:
        for c,center in snapshot:
            if center is None:c.pop('angle_chart',None)
            else:c['angle_chart']=center
        if isinstance(exc,(AnalysisError,StepFailure,ValueError)):
            raise AnalysisError(f'Warm equilibrium correction failed: {exc}') from exc
        raise
    n.equilibrium_diagnostics=dict(initialization='saved physical equilibrium',newton_iterations=iterations,tangent_builds=builds,
        residual=float(np.max(abs(function(values)))),**rank)
    if observed:n.equilibrium_diagnostics['seeded_corrector']=seeded_report
    if n.hinges:n.equilibrium_diagnostics['hinge_chart_updates']=trace
    if final_tangent is not None:
        n.equilibrium_diagnostics['final_tangent']='provided physical tangent; absolute-rotation chart retained for rank check'
    return values,1
