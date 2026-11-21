"""Continuous-time linearization of the common elastic/flight residual.

Unsteady formulation §§11.3, 13: M dz/dt = A z, with M=-R_zdot and
A=R_z. Positions, circulation, local rates, aircraft motion, internal loads
and constraints remain coupled. The common residual retains the selected
aerodynamic-lag setting; with lag disabled, circulation is algebraic, along
with internal loads and reactions.
"""
from copy import copy
import numpy as np
from scipy.linalg import svd, eig, lu_factor, lu_solve, qr
from scipy.sparse.linalg import LinearOperator, eigs, ArpackNoConvergence
from scipy.sparse import csc_matrix, bmat, issparse
from scipy.sparse.linalg import splu, norm as sparse_norm
from .aero import AnalysisError
from .ground import body_to_earth
from .inertia import Motion
from .local_motion import rotation_matrix as exp, rotation_vector as log, left_jacobian, mv
from .network import StaticNetwork, equilibrate, network_result, network_snapshot
from .operating import OperatingSystem, time_load_constraints
from .time_integration import TimeState, TimeSystem
from .wall_root import wall_root_linearization

SECTION_OUTPUTS = ('cm', 'f_aero', 'f_reac', 'da_eff')


def euler_matrix(attitude):
    """ASWING bank/elevation/heading rates (rad/T) → body rotation rate."""
    phi, theta, _ = np.deg2rad(attitude)
    return np.array([[-1., 0., np.sin(theta)],
                     [0., np.cos(phi), np.sin(phi)*np.cos(theta)],
                     [0., np.sin(phi), -np.cos(phi)*np.cos(theta)]])


class DynamicSystem:
    """Local state chart around a converged, zero-local-rate operating point.

    Nodal rotation perturbations are spatial increments about their loaded
    rotations. Aircraft angles use the published Euler chart, in radians.
    Derivatives are per input time, not per nondimensional time. The nonzero
    base trajectory derivative is retained when forming a frozen linearization.
    """
    def __init__(self, network, state, frame='fixed', *, position=(0, 0, 0), attitude=(0, 0, 0), velocity=(0, 0, 0), gravity_magnitude=None, controller=None):
        if frame not in ('fixed', 'prescribed', 'free', 'mixed'):
            raise AnalysisError('Modal frame must be fixed, prescribed, free or mixed.')
        if getattr(network, 'source_dynamic', False):
            _source_dynamic_scope(network.model, network.condition, frame=frame,
                motion=network.motion, velocity=velocity, controller=controller,
                operating_constraints=network.operating.constraints,
                quiescent_density=network.quiescent_density, structural_operator=network.structural_operator)
        self.network, self.base, self.frame = network, np.asarray(state).copy(), frame
        self._sensor_output_mask = None
        self._section_output_mask = None
        self.gravity_magnitude = gravity_magnitude
        self.feedback=controller
        self.time_system = TimeSystem(network,controller=controller)
        self.L, self.V, self.W = network.L, self.time_system.V, self.time_system.W
        self.Ascale = self.V*self.W
        self.r0, self.Q0, *_, self.gamma0 = network.unpack(state)
        from .hinge_history import at_network
        self.hinge_charts=at_network(network,self.Q0)
        c, motion, _ = network.operating.apply(state[network.operating_start:])
        self.condition, self.motion = c, motion
        if c is not None:
            position, attitude = c.position_earth, c.attitude
            velocity = -c.speed*c.vectors()[0]-np.cross(motion.rates, network.model.reference[3])
        self.position, self.attitude, self.U0 = map(lambda x: np.asarray(x, dtype=float), (position, attitude, velocity))
        if any(v.shape != (3,) or not np.all(np.isfinite(v)) for v in (self.position, self.attitude, self.U0)):
            raise AnalysisError('Modal base pose and velocity must contain finite xyz vectors.')
        if frame != 'fixed' and abs(np.cos(np.deg2rad(self.attitude[1]))) < 1e-7:
            raise AnalysisError('Modal Euler chart is singular at vertical elevation; choose a different base attitude.')
        self.R0 = body_to_earth(self.attitude)
        self.Omega0 = motion.rates
        self.Udot0 = motion.at(np.zeros(3), network.model.reference[2])-np.cross(self.Omega0, self.U0)
        self.Omegadot0 = motion.angular_acceleration
        self.pdot0 = self.R0@self.U0
        self.angle_dot0 = np.linalg.solve(euler_matrix(self.attitude), self.Omega0) if frame != 'fixed' else np.zeros(3)
        self.velocity_start = network.size
        self.frame_start = network.size+6*network.nn
        self.feedback_start=self.frame_start+(12 if frame!='fixed' else 0)
        self.size = self.feedback_start+(0 if controller is None else controller.size)
        self.dynamic_indices = np.r_[np.arange(6*network.nn),
            np.arange(network.gamma_start, network.operating_start), np.arange(self.velocity_start, self.feedback_start),
            [] if controller is None else np.arange(self.feedback_start+controller.count,self.size)].astype(int)

    def unpack(self, z, zdot):
        n = self.network
        x = self.base+z[:n.size]
        increment = z[:6*n.nn].reshape(n.nn, 6)
        r = self.r0+self.L*increment[:, :3]
        angles = increment[:, 3:]
        q, = n.local_maps(('dynamic_rotation', id(self)), (angles, self.Q0),
            lambda rows: (exp(angles[rows])@self.Q0[rows],))
        k = x[:6*n.nn].reshape(n.nn, 6)
        k[:, :3] = (r-n.rj)/n.L
        chart, = n.local_maps(('dynamic_chart', id(self)), (q,), lambda rows: (log(q[rows]),))
        k[:, 3:] = chart
        u, w = z[self.velocity_start:self.frame_start].reshape(2, n.nn, 3)
        udot, wdot = zdot[self.velocity_start:self.frame_start].reshape(2, n.nn, 3)
        if self.frame != 'fixed':
            U, Omega, position, angles = z[self.frame_start:self.feedback_start].reshape(4, 3)
            U = self.U0+self.V*U
            Omega = self.Omega0+self.W*Omega
            position = self.position+self.L*position
            attitude = self.attitude+np.rad2deg(angles)
        else:
            U, Omega, position, attitude = self.U0, self.Omega0, self.position, self.attitude
        gamma = n.circulation_basis.decode(x[n.gamma_start:n.operating_start]*n.gamma_scale)
        from .hinge_history import lifted
        charts=lifted(n,q,self.hinge_charts,self.Q0)
        state = TimeState(0. if self.condition is None else self.condition.time, x, r, q, self.V*u, self.W*w,
                          U, Omega, position, body_to_earth(attitude), gamma,
                          np.empty(0) if self.feedback is None else self.feedback.base+self.feedback.scales*z[self.feedback_start:],hinge_charts=charts)
        options = self.time_system.options(state, self.V*udot, self.W*wdot,
                                          n.circulation_basis.decode(zdot[n.gamma_start:n.operating_start]*n.gamma_scale))
        if n.hinges:options['hinge_charts']=self.hinge_charts
        if self.gravity_magnitude is not None and not n.gravity_override:
            options['gravity_override'] = state.orientation.T@np.array([0., 0., -self.gravity_magnitude])
        return state, attitude, options

    def physical_state(self, z, zdot, forcing=None):
        state, attitude, options = self.unpack(z, zdot)
        if forcing is not None:
            options = forcing(state, options)
        state.commands=options.pop('feedback_commands',{})
        return state, attitude, options

    def snapshot(self, z, zdot, *, forcing=None):
        """One load evaluation for physical outputs and controller recovery."""
        n = self.network
        state, _, options = self.physical_state(z, zdot, forcing)
        residual, data = n.residual(state.x, detail=True, **options)
        if self.feedback is not None:
            _, state.feedback_report = self.feedback.evaluate(state, data,
                self.feedback.scales*zdot[self.feedback_start:])
        result = network_snapshot(n, residual, data, sensor_frame=dict(body_to_earth=state.orientation,
            position_earth=state.position, velocity_origin_body=state.U))
        if self.feedback is not None:result['feedback']=state.feedback_report
        return state, result

    def residual(self, z, zdot, *, detail=False, forcing=None):
        n = self.network
        state, attitude, options = self.physical_state(z, zdot, forcing)
        if self.feedback is None:base=n.residual(state.x,**options)
        else:base,data=n.residual(state.x,detail=True,**options)
        dot = zdot[:6*n.nn].reshape(n.nn, 6)
        angle = z[:6*n.nn].reshape(n.nn, 6)[:, 3:]
        rows = [base, ((self.L*dot[:, :3]-state.u)/self.V).ravel(),
                ((mv(left_jacobian(angle), dot[:, 3:])-state.w)/self.W).ravel()]
        if self.frame != 'fixed':
            _, motion, _ = n.operating.apply(state.x[n.operating_start:],
                condition_override=options['condition_override'], motion_override=options['motion_override'])
            Ud, Od, pd, ad = zdot[self.frame_start:self.feedback_start].reshape(4, 3)
            rows += [(self.Udot0+self.V*Ud+np.cross(state.Omega, state.U)
                      -motion.at(np.zeros(3), n.model.reference[2]))/self.Ascale,
                     (self.Omegadot0+self.W*Od-motion.angular_acceleration)/self.W**2,
                     (self.pdot0+self.L*pd-state.orientation@state.U)/self.V,
                     (euler_matrix(attitude)@(self.angle_dot0+ad)-state.Omega)/self.W]
        if self.feedback is not None:
            control,state.feedback_report=self.feedback.evaluate(state,data,self.feedback.scales*zdot[self.feedback_start:])
            rows.append(control)
        result = np.concatenate(rows)
        return (result, state, options) if detail else result

    def base_report(self):
        z = np.zeros(self.size)
        residual, state, options = self.residual(z, z, detail=True)
        result = network_result(self.network, state.x, sensor_frame=dict(body_to_earth=state.orientation,
            position_earth=state.position, velocity_origin_body=state.U), **options)
        if self.feedback is not None:result['feedback']=state.feedback_report
        if getattr(self, 'steady_trim', None) is not None:result['steady_trim']=self.steady_trim
        if getattr(self,'equilibrium_state',None) is not None:
            from copy import deepcopy
            result['equilibrium_state']=deepcopy(self.equilibrium_state)
            result['equilibrium_state']['residual']=float(np.max(abs(residual)))
            result['equilibrium_initialization']=self.equilibrium_initialization
        from .sensors import UNITS
        self._sensor_output_mask = [{key: sensor.get(key) is not None
            and not (key == 'speed' and sensor['flow_singular'])
            and not (key in ('bank', 'elevation', 'heading') and sensor['attitude_singular'])
            for key in UNITS} for sensor in result['sensors']]
        self._section_output_mask = [{key: strip.get(key) is not None for key in SECTION_OUTPUTS}
                                     for strip in result.get('strips', [])]
        result['modal_base'] = dict(frame=self.frame, load_targets={c.quantity:c.target for c in self.network.operating.constraints}, velocity_origin_body=self.U0.tolist(),
            position_earth=self.position.tolist(), attitude=self.attitude.tolist(),
            body_to_earth=self.R0.tolist(),
            velocity_derivative_body=self.Udot0.tolist(), angular_acceleration_body=self.Omegadot0.tolist(),
            velocity_origin_earth=self.pdot0.tolist(), attitude_rates_rad=self.angle_dot0.tolist(),
            continuous_residual=float(np.max(abs(residual))),
            kinematically_steady=bool(max(np.linalg.norm(self.Udot0)/self.Ascale,
                np.linalg.norm(self.Omegadot0)/self.W**2, np.linalg.norm(self.angle_dot0[:2])/self.W) < 1e-7))
        return result


@wall_root_linearization
def linearize(system, step=1e-5, progress=None, *, sparse=False, _stationary=False, _output_fields=False):
    if not sparse:
        return _linearize(system, step, progress, stationary=_stationary)
    # Exact pair reuse only: a Bode tangent must include ALL geometry feedback.
    # In particular this must never enter the lagged Newton iteration context.
    from .tangent_influences import TangentInfluences
    n=system.network
    previous=n.tangent_influences
    n.tangent_influences=TangentInfluences(local_geometry=True);n.aero_key=None
    try:
        return _linearize(system, step, progress, sparse=True, stationary=_stationary, output_fields=_output_fields)
    finally:
        n.tangent_influences=previous;n.aero_key=None


def dynamic_circulation_columns(system):
    """Shared steady/unsteady load derivatives at fixed state and state rate.

    Capture only the unperturbed physical evaluation. Never enter a lagged
    geometry phase: every remaining state column uses the full moving fields.
    Frame kinematics do not depend directly on circulation. Controllers can,
    so they retain the full residual stencil until their chain rule is shared.
    """
    from .structured_static import IterationFields, StructuredTangentUnavailable
    from .circulation_tangent import circulation_columns, CirculationDerivativeUnavailable
    n=system.network
    if system.feedback is not None or n.iteration_fields is not None:
        raise CirculationDerivativeUnavailable('Controller or enclosing iteration requires full circulation probes.')
    fields=IterationFields();fields.capture_circulation=True
    n.iteration_fields=fields;n.aero_key=None
    try:
        zero=np.zeros(system.size)
        system.residual(zero,zero)
        block=circulation_columns(n,fields,1.)
    except StructuredTangentUnavailable as exc:
        raise CirculationDerivativeUnavailable(str(exc)) from exc
    finally:
        n.iteration_fields=None;n.aero_key=None
    result=np.zeros((system.size,n.ng))
    result[:n.size]=block
    return result


def source_geometry_supports(system):
    """Conservative supports for local fixed-frame source geometry equations.

    No field is frozen: these operators have only adjacent beam, attachment
    and joint loads. Nonintersecting supports can share full residual probes.
    Unknown operators/overrides and global frame/control equations retain
    individual columns until their complete dependence has been established.
    """
    from .source_discrete import SourceDiscreteNetwork, SourceSectionNetwork
    from .source_dynamics import SourceDynamicNetwork, SourceMovingNetwork
    from .source_quiescent import SourceQuiescentNetwork
    n=system.network
    if (type(system) is not DynamicSystem or
            type(n) not in (SourceDynamicNetwork,SourceQuiescentNetwork,SourceMovingNetwork) or
            system.frame!='fixed' or system.feedback is not None or n.condition is not None or
            n.ng or n.operating.count or n.engines or n.iteration_fields is not None):
        return None
    methods=((system,'residual',DynamicSystem.residual),
        (n,'residual',SourceDiscreteNetwork.residual),
        (n,'external',type(n).external),
        (n,'geometry',StaticNetwork.geometry),
        (n,'constitutive_response',SourceSectionNetwork.constitutive_response),
        (n,'constitutive_motion',SourceDynamicNetwork.constitutive_motion),
        (n,'material_strain_rate',SourceDynamicNetwork.material_strain_rate))
    if any(getattr(getattr(owner,name),'__func__',None) is not expected
           for owner,name,expected in methods):
        return None
    from .structured_static import structural_column_rows
    rows=structural_column_rows(n)[:6*n.nn]
    for column in range(6*n.nn):
        node=column//6
        kinematic=np.r_[n.size+3*node+np.arange(3),
                        n.size+3*n.nn+3*node+np.arange(3)]
        rows[column]=np.unique(np.r_[rows[column],kinematic])
    return rows


def _linearize(system, step=1e-5, progress=None, *, sparse=False, stationary=False, output_fields=False):
    if not np.isfinite(step) or not 1e-7 <= step <= 1e-3:
        raise AnalysisError('Dynamic linearization step must be between 1e-7 and 1e-3.')
    size = system.size
    column_count = system.network.size if stationary else size
    zero = np.zeros(size)
    baseline = system.residual(zero, zero)
    if np.max(abs(baseline)) > 1e-7:
        raise AnalysisError('Dynamic linearization requires a converged consistent base state.')
    _, state0, options0 = system.residual(zero, zero, detail=True)
    _, data0 = system.network.residual(state0.x, detail=True, **options0)
    if system.feedback is not None:system.feedback.check_linearization(state0,data0,moving_speed=system.frame!='fixed')
    n = system.network
    clips = () if data0['aero'] is None else tuple(e['power_clipped'] for e in data0['aero']['engines'])
    if n.tension_only and any(abs(s['strain']) < 10*step for s in data0['struts']):
        raise AnalysisError('Modal base is too close to a wire slack/taut transition for a unique tangent.')
    for hinge in data0['hinges']:
        law = n.hinges[hinge['joint']]
        for point in law.spline.breaks:
            if abs(hinge['structural_moment']-point) < 10*step*n.F*n.L and not np.isclose(
                law.spline.evaluate(point, side='left', derivative=1),
                law.spline.evaluate(point, side='right', derivative=1), rtol=1e-7, atol=1e-12):
                raise AnalysisError('Modal base is too close to a Jangle slope break for a unique tangent.')

    def checked(z, zdot):
        residual, state, options = system.residual(z, zdot, detail=True)
        if n.aero_cached is not None and tuple(e['power_clipped'] for e in n.aero_cached['engines']) != clips:
            raise AnalysisError('Modal difference stencil crosses an engine power-clipping transition.')
        if n.tension_only:
            from .struts import strut_load
            for row, original in zip(n.struts, data0['struts']):
                i = n.node(*row[:2])
                point = state.r[i]+state.Q[i]@(row[2:5]-n.rj[i])
                if strut_load(row, point, tension_only=True)['slack'] != original['slack']:
                    raise AnalysisError('Modal difference stencil crosses a wire slack/taut transition.')
        if data0['hinges']:
            _, data = n.residual(state.x, detail=True, **options)
            for before, after in zip(data0['hinges'], data['hinges']):
                law = n.hinges[before['joint']]
                for point in law.spline.breaks:
                    if (before['structural_moment']-point)*(after['structural_moment']-point) <= 0 and not np.isclose(
                        law.spline.evaluate(point, side='left', derivative=1),
                        law.spline.evaluate(point, side='right', derivative=1), rtol=1e-7, atol=1e-12):
                        raise AnalysisError('Modal difference stencil crosses a Jangle slope break.')
        return residual
    a = [None]*column_count if sparse else np.empty((size, column_count))
    def save(column, values):
        if sparse:
            from scipy.sparse import csc_matrix
            a[column]=csc_matrix(values[:,None])
        else:a[:,column]=values
    side_check=system.feedback is not None and system.feedback.needs_side_check
    from .control_expressions import check_sides
    feedback_rows=slice(system.feedback_start,None)
    scales = np.r_[np.maximum(1., abs(system.base)), np.ones(size-system.network.size)]
    from .wall_root import wall_root_coordinate_scales
    scales, wall_steps = wall_root_coordinate_scales(system, scales, step)
    groups=[];supports={};direct_columns=set()
    system.state_derivative_diagnostics=dict(difference_order=4,direct_circulation_columns=0,
        circulation_method='fourth-order full residual differences',circulation_fallback=None,
        grouped_reaction_columns=0,mechanical_column_groups=0,
        direct_mechanical_columns=0,mechanical_fallback=None,
        direct_local_motion_columns=0,local_motion_fallback=None,
        grouped_geometry_columns=0,geometry_column_groups=0,
        split_geometry_columns=0,geometry_method='fourth-order full residual differences',geometry_fallback=None)
    system.state_derivative_diagnostics['wall_root_coordinate_steps'] = wall_steps
    retained = None if stationary else getattr(system, '_equilibrium_tangent', None)
    reused = retained is not None and retained.matches(system, step, sparse)
    if reused:
        for j in range(n.size):
            if sparse:a[j]=retained.matrix[:,j].copy()
            else:a[:,j]=retained.matrix[:,j]
        direct_columns.update(range(n.size))
        from copy import deepcopy
        system.state_derivative_diagnostics.update(deepcopy(retained.diagnostics))
    system.state_derivative_diagnostics['equilibrium_columns_reused'] = n.size if reused else 0
    fields=None
    if output_fields:
        from .output_fields import FieldTangent,FieldUnavailable
        from .circulation_tangent import CirculationDerivativeUnavailable
        old=getattr(system,'_output_field_tangent',None)
        if reused:
            if old is not None and old.matches(system,step):fields=old
        else:
            try:fields=FieldTangent(system,step)
            except (FieldUnavailable,CirculationDerivativeUnavailable):pass
        system._output_field_tangent=fields
    if progress is not None:progress(0,size+len(system.dynamic_indices))
    if not reused and sparse and system.feedback is None and n.condition is not None:
        from .geometry_tangent import geometry_columns, GeometryDerivativeUnavailable
        support=None
        if n.struts:
            from .support_outputs import SupportTangent, SupportUnavailable
            try:
                support=getattr(system,'_support_output_tangent',None)
                if support is None or not support.matches(system):
                    support=SupportTangent(system);system._support_output_tangent=support
            except SupportUnavailable:
                support=None
        try:
            geometry,diagnostics=geometry_columns(n,lambda z:checked(z,zero),
                lambda z:system.unpack(z,zero)[0].x,scales,step,
                progress=None if progress is None else lambda done,total:progress(done,size+len(system.dynamic_indices)),
                _field_columns=None if fields is None else fields.geometry_columns,
                _direct_vortex=True, _direct_volume=True, _nodewise_state=True,
                _direct_geometry=True, _rotation_chart='spatial', _strut_tangent=support,
                _direct_structural=True, _structural_system=system)
        except GeometryDerivativeUnavailable as exc:
            system.state_derivative_diagnostics['geometry_fallback']=str(exc)
            if fields is not None:fields.disable('Full geometry derivative fallback: '+str(exc))
        else:
            for j in range(6*n.nn):
                a[j]=geometry[:,j];direct_columns.add(j)
            system.state_derivative_diagnostics.update(split_geometry_columns=6*n.nn,
                geometry_method=diagnostics['method'],geometry_assembly=diagnostics)
    if not reused and sparse and n.ng:
        from .circulation_tangent import CirculationDerivativeUnavailable
        try:
            direct=dynamic_circulation_columns(system)
        except CirculationDerivativeUnavailable as exc:
            system.state_derivative_diagnostics['circulation_fallback']=str(exc)
        else:
            for k,j in enumerate(range(n.gamma_start,n.operating_start)):
                save(j,direct[:,k]);direct_columns.add(j)
            system.state_derivative_diagnostics.update(direct_circulation_columns=n.ng,
                circulation_method='shared direct fixed-state load derivatives; refined engine inflow chain rule')
    if not reused:
        from .mechanical_tangent import mechanical_columns,MechanicalDerivativeUnavailable
        try:
            mechanical,diagnostics=mechanical_columns(system,data0,scales,step)
        except MechanicalDerivativeUnavailable as exc:
            system.state_derivative_diagnostics['mechanical_fallback']=str(exc)
        else:
            for k,j in enumerate(range(6*n.nn,n.gamma_start)):
                if sparse:a[j]=mechanical[:,k]
                else:a[:,j]=mechanical[:,k].toarray().ravel()
                direct_columns.add(j)
            system.state_derivative_diagnostics.update(direct_mechanical_columns=mechanical.shape[1],
                mechanical_assembly=diagnostics)
    if not reused and sparse and system.feedback is None and not n.operating.custom and not n.hinges:
        from .structured_static import structural_column_rows, coloring
        rows=structural_column_rows(n)
        # At fixed geometry, joint/ground reactions act only on their incident
        # nodal balances. Their conservative supports are already part of the
        # same mechanical graph as internal beam loads. Disjoint columns may
        # share the original full-residual stencil, with no lagged physics.
        mechanical=np.array([j for j in range(6*n.nn,n.gamma_start) if j not in direct_columns],dtype=int)
        supports={j:rows[j] for j in mechanical}
        groups=[mechanical[group] for group in coloring([rows[j] for j in mechanical])]
        system.state_derivative_diagnostics.update(grouped_reaction_columns=n.nc if len(mechanical) else 0,
            mechanical_column_groups=len(groups))
    if not reused and sparse and (fields is None or not fields.active):
        geometry_rows=source_geometry_supports(system)
        if geometry_rows is not None:
            from .structured_static import coloring
            columns=np.array([j for j in range(6*n.nn) if j not in direct_columns],dtype=int)
            geometry_groups=[columns[group] for group in coloring([geometry_rows[j] for j in columns])]
            supports.update({j:geometry_rows[j] for j in columns})
            groups.extend(geometry_groups)
            system.state_derivative_diagnostics.update(grouped_geometry_columns=len(columns),
                geometry_column_groups=len(geometry_groups),
                geometry_method='fourth-order full residual differences on disjoint local source supports')
    if not stationary and sparse:
        from .local_rate_tangent import local_rate_columns, LocalRateUnavailable
        try:
            local,columns,diagnostics=local_rate_columns(system)
        except LocalRateUnavailable as exc:
            system.state_derivative_diagnostics['local_motion_fallback']=str(exc)
        else:
            for k,j in enumerate(columns):
                a[j]=local[:,k];direct_columns.add(j)
            system.state_derivative_diagnostics.update(direct_local_motion_columns=len(columns),
                local_motion_assembly=diagnostics)
    if not stationary and sparse and system.feedback is None and not n.operating.count:
        # At fixed geometry, local elastic velocity affects only incident
        # elements and attached objects. Vortex/volume coefficients depend on
        # geometry and the aircraft wind, not these local velocities. Engine
        # mounts can change a nonlocal jet: keep their six columns individual.
        # A zero/nonzero local-rate branch merely enables the axis velocity
        # used by the apparent-mass rate term; zero-rate sections multiply it
        # by zero, so it introduces no cross-node support.
        from .structured_static import structural_column_rows,coloring
        rows=structural_column_rows(n)
        engine_nodes={n.node(*row[2:4]) for row in n.engines}
        columns=[];velocity_rows=[]
        for node in range(n.nn):
            if node in engine_nodes:continue
            for component in range(6):
                j=system.velocity_start+(component//3)*3*n.nn+3*node+component%3
                if j in direct_columns:continue
                kinematic=n.size+(component//3)*3*n.nn+3*node+component%3
                support=np.unique(np.r_[rows[6*node+component],kinematic])
                supports[j]=support;columns.append(j);velocity_rows.append(support)
        columns=np.array(columns)
        groups += [columns[group] for group in coloring(velocity_rows)]
    groups += [np.array([j]) for j in range(column_count) if j not in supports and j not in direct_columns]
    completed=len(direct_columns)
    if progress is not None:progress(completed,size+len(system.dynamic_indices))
    for columns in groups:
        h = step*scales[columns]
        delta = zero.copy(); delta[columns] = h
        # Fourth-order differences suppress artificial constraint leakage from
        # cubic geometric terms when short braces accompany a long wing.
        collect=fields is not None and fields.active and any(j in fields.pending for j in columns)
        if collect and len(columns)!=1:
            fields.disable('Output field columns require individual physical probes.');collect=False
        if collect:
            values=[];field_values=[]
            for multiplier in (1,-1,2,-2):
                z=multiplier*delta
                value,field_value=fields.probe(lambda:checked(z,zero),z,zero)
                values.append(value);field_values.append(field_value)
            plus,minus,plus2,minus2=values
            if fields.active:
                try:fields.save(int(columns[0]),(8*(field_values[0]-field_values[1])-(field_values[2]-field_values[3]))/(12*h[0]))
                except FieldUnavailable as exc:fields.disable(exc)
        else:plus,minus,plus2,minus2=checked(delta,zero),checked(-delta,zero),checked(2*delta,zero),checked(-2*delta,zero)
        if side_check:check_sides(*(v[feedback_rows] for v in (baseline,minus,plus,minus2,plus2)),h[0])
        difference=8*(plus-minus)-(plus2-minus2)
        for j,hj in zip(columns,h):
            value=difference/(12*hj)
            if j in supports:
                selected=np.zeros(size);selected[supports[j]]=value[supports[j]];value=selected
            save(j,value)
        completed+=len(columns)
        if progress is not None:
            progress(completed, size+len(system.dynamic_indices))
    if sparse:
        from scipy.sparse import hstack
        a=hstack(a,format='csc')
        from .structural_outputs import compatibility_columns, StructuralOutputUnavailable
        from scipy.sparse import vstack
        try:
            compatible=compatibility_columns(system)
        except StructuralOutputUnavailable as exc:
            system.state_derivative_diagnostics['compatibility_fallback']=str(exc)
        else:
            # Keep local-motion damping and all aircraft/controller columns.
            a=vstack([hstack([compatible,a[:6*n.ne,n.size:]],format='csc'),
                a[6*n.ne:]],format='csc')
            system.state_derivative_diagnostics.update(compatibility_rows_reused=6*n.ne,
                compatibility_method='retained section-output C and complete compliance')
    if not np.all(np.isfinite(a.data if sparse else a)):
        raise AnalysisError('Nonfinite dynamic tangent.')
    if stationary:return a
    if fields is not None:fields.finish()
    from .descriptor_mass import mass_matrix
    m = mass_matrix(system,state0,data0,step,progress,sparse=sparse)
    if not np.all(np.isfinite(m.data if sparse else m)):
        raise AnalysisError('Nonfinite dynamic tangent.')
    return a, m


def finite_subspace(a, m, tolerance):
    """Two-sided constraint staircase for constant M zdot=A z.

    Column-pivoted QR supplies the derivative range and constraint nullspace;
    singular values still diagnose numerical rank. Remove each established
    algebraic equation together with its constrained coordinate, so discarded
    rows cannot reappear as constraints through roundoff on the next stair.
    No inverse of the singular derivative matrix is formed.

    The requested cutoff and weak-inertia guard classify the original M.
    Restricting coordinates can contract a *retained* physical derivative
    below that cutoff. Later stairs distinguish it from roundoff instead of
    silently deleting it. The actual thresholds are included in the report.
    """
    z = np.eye(a.shape[1])
    az, mz = np.array(a, copy=True), np.array(m, copy=True)
    mass_norm = np.linalg.norm(m, 2)
    threshold = tolerance*max(np.linalg.norm(a, 2), mass_norm, 1.)
    projected_threshold = min(threshold, 100*np.finfo(float).eps*max(mass_norm, 1.))
    history = []
    for iteration in range(a.shape[1]+1):
        if not z.shape[1]:
            return z, history
        singular = svd(mz, compute_uv=False)
        derivative_threshold = threshold if iteration == 0 else projected_threshold
        rank = int(np.sum(singular > derivative_threshold))
        if iteration == 0 and rank < len(singular) and singular[rank] > 100*np.finfo(float).eps*max(1., singular[0]):
            raise AnalysisError('Dynamic derivative rank is ambiguous at this tolerance; lower the rank tolerance and refine the difference step, or use full_shift_invert for nearby roots. A weak inertia must not be silently discarded.')
        # Householder bases preserve sparse exact zeros much more accurately
        # than small singular vectors of a strongly scaled derivative matrix.
        u, _, _ = qr(mz, mode='full', pivoting=True)
        constraints = u[:, rank:].T@az
        cs = svd(constraints, compute_uv=False)
        # A weak retained derivative amplifies backward error in its left-null
        # vectors. Propagate that uncertainty to C; otherwise repeated hidden
        # constraint differentiation can remove real finite modes. The final
        # eigenpairs must still satisfy the complete ORIGINAL pencil.
        constraint_threshold = max(threshold, 20*np.finfo(float).eps*np.linalg.norm(az, 2)
                                   *singular[0]/singular[rank-1]) if rank else threshold
        removed = int(np.sum(cs > constraint_threshold))
        history.append(dict(dimension=z.shape[1], derivative_rank=rank, constraints=removed,
                            smallest_derivative=float(singular[rank-1]) if rank else None,
                            largest_discarded_derivative=float(singular[rank]) if rank < len(singular) else 0.,
                            threshold=float(derivative_threshold), requested_threshold=float(threshold),
                            constraint_threshold=float(constraint_threshold),
                            largest_discarded_constraint=float(cs[removed]) if removed < len(cs) else 0.,
                            reduction='Two-sided orthogonal constraint staircase with column-pivoted QR bases.'))
        # A regular square pencil has independent algebraic rows at every
        # stair. A deficient row rank is a singular/underdetermined problem.
        if removed != az.shape[0]-rank:
            raise AnalysisError('Dynamic pencil is underdetermined: unconstrained massless motion or dependent constraints.')
        if not removed:
            return z, history
        v, _, _ = qr(constraints.T, mode='full', pivoting=True)
        null = v[:, removed:]
        z = z@null
        az, mz = u[:, :rank].T@az@null, u[:, :rank].T@mz@null
    raise AnalysisError('Dynamic constraint reduction did not terminate.')


class IntegratorDeflation:
    """Extract exact lambda factors by row/column Laplace expansion.

    A zero A column with exactly one nonzero M entry, or its row analogue,
    factors the determinant by -lambda*M_ij. No tolerance changes any entry.
    Repeated removal handles coordinate integrator chains before orthogonal
    constraint reduction mixes their exact zeros with roundoff. The original
    pencil still supplies every final eigenvector residual and left vector.
    """
    def __init__(self,a,m):
        self.a,self.m=np.array(a,copy=True),np.array(m,copy=True)
        rows=list(range(len(a)));columns=rows.copy();self.operations=[]
        while len(self.a):
            cs=np.flatnonzero(np.all(self.a==0,axis=0)&(np.sum(self.m!=0,axis=0)==1))
            rs=np.flatnonzero(np.all(self.a==0,axis=1)&(np.sum(self.m!=0,axis=1)==1))
            if len(cs):
                j=int(cs[0]);i=int(np.flatnonzero(self.m[:,j]!=0)[0]);side='column'
            elif len(rs):
                i=int(rs[0]);j=int(np.flatnonzero(self.m[i]!=0)[0]);side='row'
            else:break
            self.operations.append(dict(index=j,side=side,row=rows.pop(i),column=columns.pop(j),
                pivot=float(self.m[i,j]),a=self.a[i].copy(),m=self.m[i].copy()))
            self.a=np.delete(np.delete(self.a,i,axis=0),j,axis=1)
            self.m=np.delete(np.delete(self.m,i,axis=0),j,axis=1)
        self.rows,self.columns=rows,columns

    def lift(self,vector,value):
        v=np.asarray(vector,dtype=complex)
        if not self.operations:return v
        if value==0:raise AnalysisError('A zero root needs the original pencil nullspace, not integrator back-substitution.')
        for op in reversed(self.operations):
            v=np.insert(v,op['index'],0.)
            if op['side']=='column':
                v[op['index']]=(op['a']@v-value*(op['m']@v))/(value*op['pivot'])
            if not np.all(np.isfinite(v)):raise AnalysisError('Integrator eigenvector recovery overflowed; inspect a nearly zero physical root and state scaling.')
            v/=max(np.max(abs(v)),1.)
        return v

    def report(self):
        return dict(count=len(self.operations),
            operations=[{k:op[k] for k in ('side','row','column','pivot')} for op in self.operations],
            criterion='Exact zero A row/column and exactly one nonzero M entry; no numerical zero threshold.',
            retained_rows=self.rows,retained_columns=self.columns)


def integrator_kernel(a):
    """Null vectors with complete pivoting and no small-pivot deletion.

    Deflation guarantees a singular A. An SVD rank cutoff could mix its exact
    kernel with a genuinely weak nonzero mode. Complete-pivot elimination keeps
    every nonzero pivot and finds the coordinate freedoms that actually remain.
    Final vectors must still satisfy the original full-pencil residual check.
    """
    work=np.array(a,copy=True);size=len(work);columns=np.arange(size);rank=0
    while rank<size:
        i,j=np.unravel_index(np.argmax(abs(work[rank:,rank:])),(size-rank,size-rank))
        i+=rank;j+=rank
        if work[i,j]==0:break
        work[[rank,i]]=work[[i,rank]];work[:,[rank,j]]=work[:,[j,rank]]
        columns[[rank,j]]=columns[[j,rank]]
        work[rank,rank:]/=work[rank,rank]
        factors=work[:,rank].copy();factors[rank]=0
        work[:,rank:]-=factors[:,None]*work[rank,rank:]
        work[:,rank]=0.;work[rank,rank]=1.;rank+=1
    vectors=np.zeros((size,size-rank))
    vectors[columns[:rank]]=-work[:rank,rank:]
    vectors[columns[rank:]]=np.eye(size-rank)
    return vectors


def _sparse_adjoint(a, m, value, right, pencil_norm):
    """Recover a simple pole's original-pencil left vector by bordering.

    For P=A-lambda M and P r=0, solve
        [P.H  r] [w] = [0]
        [c.H  0] [q]   [1],  c=M r.
    A simple finite pole has w.H M r != 0, so the border is nonsingular.
    Multiplying the top equation by r.H shows q=0. Thus the recovered vector
    includes the original algebraic reaction components, with no truncation
    of the descriptor equations. Repeated or poorly conditioned poles use
    the existing generalized-Schur/null-space recovery instead.
    """
    r=right/np.linalg.norm(right);c=m@r;cn=np.linalg.norm(c)
    if not np.isfinite(cn) or not cn:return None
    c=c/cn;p=a.conj().T-np.conj(value)*m.conj().T
    matrix=bmat([[p,csc_matrix(r[:,None])],[csc_matrix(c.conj()[None,:]),None]],format='csc')
    rhs=np.zeros(len(right)+1,dtype=complex);rhs[-1]=1.
    try:
        factor=splu(matrix);solution=factor.solve(rhs)
    except (RuntimeError,ValueError):
        return None
    w=solution[:-1];wn=np.linalg.norm(w)
    if not np.isfinite(wn) or not wn:return None
    w=w/wn
    # This tighter acceptance check only chooses the recovery algorithm. The
    # unchanged full-pencil checks below still certify every returned mode.
    error=np.linalg.norm(p@w)/max(pencil_norm,np.finfo(float).tiny)
    if error>1e-11 or abs(np.vdot(w,c))<1e-8:return None
    return w[:,None]


def eigensystem(a, m, *, time_scale=1., count=16, shift=(-.01, 0.), method='dense', rank_tolerance=1e-9):
    """Finite modes of a descriptor pencil, including left/right residuals."""
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        raise AnalysisError('Mode count must be a positive integer.')
    if method not in ('dense', 'shift_invert', 'full_shift_invert'):
        raise AnalysisError('Mode method must be dense, shift_invert or full_shift_invert.')
    if not np.isfinite(rank_tolerance) or not 1e-12 <= rank_tolerance <= 1e-5:
        raise AnalysisError('Descriptor rank tolerance must be between 1e-12 and 1e-5.')
    shift = np.asarray(shift, dtype=float)
    if shift.shape != (2,) or not np.all(np.isfinite(shift)):
        raise AnalysisError('Mode shift must contain finite real and imaginary parts, in 1/input T.')
    if not np.isfinite(time_scale) or time_scale <= 0:
        raise AnalysisError('Mode time scale must be finite and positive.')
    direct = method == 'full_shift_invert'
    if direct:
        a, m = csc_matrix(a), csc_matrix(m)
        a = a.astype(np.result_type(a.dtype, float), copy=False)
        m = m.astype(np.result_type(m.dtype, float), copy=False)
        # Same Euclidean row equilibration, without dense square matrices.
        # Scale copies so the physical A/M returned to callers stay intact.
        aa, mm = a.copy(), m.copy()
        mm.data *= time_scale
        def row_norm(matrix):
            return np.sqrt(np.asarray(matrix.conj().multiply(matrix).real.sum(axis=1)).ravel())
        row_scale = np.maximum(np.maximum(row_norm(aa), row_norm(mm)), 1e-30)
        aa.data /= row_scale[aa.indices]
        mm.data /= row_scale[mm.indices]
    else:
        row_scale = np.maximum(np.maximum(np.linalg.norm(a, axis=1), np.linalg.norm(m*time_scale, axis=1)), 1e-30)
        aa, mm = a/row_scale[:, None], m*time_scale/row_scale[:, None]
    full_size = a.shape[0]
    integrators=None if direct else IntegratorDeflation(aa,mm)
    da,dm=(aa,mm) if direct else (integrators.a,integrators.m)
    zero_count=0 if direct else len(integrators.operations)
    mu = complex(*shift)/time_scale
    if direct:
        # The rational operator retains algebraic equations and arbitrarily
        # weak inertias. Infinite roots map to zero inverse eigenvalues; Arnoldi
        # searches the largest inverses, i.e. finite roots near the shift.
        # This local search does NOT establish the total finite dimension.
        if count >= full_size-1:
            raise AnalysisError('Full descriptor Arnoldi requires count below the pencil dimension minus one; reduce count or use the dense reduction.')
        ar, mr = da, dm
        dynamic_dimension = dimension = condition = None
        right, rh, used = None, [], method
    else:
        right,rh=finite_subspace(da,dm,rank_tolerance) if len(da) else (np.empty((0,0)),[])
        dynamic_dimension=right.shape[1]
        dimension=dynamic_dimension+zero_count
        if not dimension:
            raise AnalysisError('No finite dynamic modes: check that the model has mass or aerodynamic lag states.')
        # A Z lies in range(M Z). Project onto that range rather than repeating
        # the staircase on the transpose, which squares poor conditioning.
        test, _ = qr(dm@right, mode='economic')
        ar, mr = test.T@da@right, test.T@dm@right
        sv = svd(mr, compute_uv=False)
        condition = float(sv[-1]/sv[0]) if dynamic_dimension else None
        if condition is not None and condition < 1e-12:
            raise AnalysisError('Finite dynamic mass pencil is too ill-conditioned; inspect scaling and constraints.')
        used = method if count < dynamic_dimension-1 else 'dense'
    shift_condition = None
    arnoldi = None
    dense_values = None
    if direct:
        from .modal_arnoldi import shifted_modes
        values,vr,arnoldi=shifted_modes(ar,mr,mu,count)
    elif not dynamic_dimension:
        values,vr=np.empty(0,dtype=complex),np.empty((0,0),dtype=complex)
    elif used == 'dense':
        values, vr = eig(ar, mr, right=True)
        dense_values = values.copy()
        order = np.argsort(abs(values-mu), kind='stable')[:count]
        values, vr = values[order], vr[:, order]
    else:
        matrix = ar-mu*mr
        s = svd(matrix, compute_uv=False)
        shift_condition = float(s[-1]/s[0]) if s[0] else 0.
        if shift_condition < 1e-12:
            raise AnalysisError('Mode shift is on or too near a pole; choose a different shift (nonzero for rigid-body zero modes).')
        factor = lu_factor(matrix)
        operator = LinearOperator(ar.shape, matvec=lambda x: lu_solve(factor, mr@x), dtype=complex)
        try:
            inverse, vr = eigs(operator, k=count, which='LM', tol=1e-11, maxiter=max(500, 30*len(ar)),
                               v0=np.linspace(1., 2., len(ar)).astype(complex))
        except ArpackNoConvergence as exc:
            raise AnalysisError('Shift-and-invert modes did not converge; change shift/count or use the dense solve.') from exc
        if np.any(abs(inverse) <= 100*np.finfo(float).eps*max(np.max(abs(inverse)), 1.)):
            raise AnalysisError('The Arnoldi search includes unresolved infinite or very distant roots; reduce count or move the shift.')
        values = mu+1/inverse
        order = np.argsort(abs(values-mu), kind='stable'); values, vr = values[order], vr[:, order]
    reduced_vectors=vr if direct else right@vr
    # Computed exact zeros can also remain in a dense quotient. Recover all
    # zero vectors from the original A nullspace, including the known factors.
    zero_vectors=None;zero_index=0
    if zero_count:
        zero_vectors=integrator_kernel(aa)
        if not zero_vectors.shape[1]:raise AnalysisError('The exact integrator factors have no resolved original-pencil nullspace.')
    candidates=[]
    for value,vector in zip(values,reduced_vectors.T):
        if value==0 and zero_count:
            lifted=zero_vectors[:,zero_index%zero_vectors.shape[1]];zero_index+=1
        else:lifted=vector if direct else integrators.lift(vector,value)
        candidates.append((value,lifted,False))
    for _ in range(zero_count):
        candidates.append((0j,zero_vectors[:,zero_index%zero_vectors.shape[1]],True));zero_index+=1
    selected=np.argsort([abs(value-mu) for value,_,_ in candidates],kind='stable')[:count]
    # Refine simple Ritz pairs against the full pencil before recovering their
    # adjoints. Keep the full Schur fallback lazy, so ordinary simple
    # poles do not require another cubic eigensolve on the original pencil.
    full_values,full_left=None,None
    sparse_a=sparse_m=None;recovered=[]
    recovery=dict(sparse_adjoint=0,conjugate_reuse=0,sparse_rejected=0,
                  schur_pencils=0,schur_vectors=0,nullspace_fallback=0,exact_kernel=0)
    inverse_records=[]
    refinement_records=[]
    if direct:
        from .modal_arnoldi import inverse_left,conjugate_left,selected_clusters
        from .modal_refinement import refine_simple_pair
        recovery.update(inverse_iteration=0,inverse_iteration_failed=0,repeated_pole_fallback=0,
                        conjugate_rejected=0,bordered_refinement=0)
        sparse_a,sparse_m=csc_matrix(aa),csc_matrix(mm)
        clusters=selected_clusters([candidates[k][0]*time_scale for k in selected])
        repeated_selected={selected[j] for group in clusters if len(group)>1 for j in group}
    if dense_values is not None and len(a)>=64 and np.count_nonzero(aa)+np.count_nonzero(mm)<=.1*len(a)**2:
        sparse_a,sparse_m=csc_matrix(aa),csc_matrix(mm)
    real_pencil=np.isrealobj(aa) and np.isrealobj(mm)
    zero_left=integrator_kernel(aa.T) if zero_count else None
    if zero_left is not None and not zero_left.shape[1]:raise AnalysisError('Exact integrator factors have no resolved left nullspace.')
    modes = []
    left_bases = []
    # Reuse the already assembled sparse pencil for complex-vector checks.
    # Forming A-lambda*M, or multiplying a real dense matrix by a complex
    # vector, can otherwise allocate another full complex matrix per mode.
    residual_a, residual_m = (sparse_a, sparse_m) if sparse_a is not None else (aa, mm)
    a_norm, m_norm = (sparse_norm(aa), sparse_norm(mm)) if direct else (np.linalg.norm(aa), np.linalg.norm(mm))
    for k in selected:
        value,vk,exact_zero=candidates[k]
        pivot = np.argmax(abs(vk)); vk = vk/vk[pivot]
        refined_left=None
        if direct and k not in repeated_selected:
            value,vk,refined_left,record=refine_simple_pair(sparse_a,sparse_m,value,vk)
            refinement_records.append({**record,'selected_index':int(k),
                'eigenvalue':[float(value.real*time_scale),float(value.imag*time_scale)]})
        # Recover the left vector from the ORIGINAL equilibrated pencil. The
        # projection test basis does not contain the left reaction components.
        # For a repeated pole choose the null-space combination that pairs with
        # this right vector, when such a pairing exists.
        pencil_norm=a_norm+abs(value)*m_norm
        null=None;direct_inverse=False
        if value==0 and zero_left is not None:
            null,_=qr(zero_left,mode='economic')
            recovery['exact_kernel']+=1
        elif direct:
            if refined_left is not None:
                null=(refined_left/np.linalg.norm(refined_left))[:,None]
                recovery['bordered_refinement']+=1
                direct_inverse=True
            if k in repeated_selected:
                recovery['repeated_pole_fallback']+=1
                inverse_records.append(dict(status='NOT_ATTEMPTED',reason='repeated_selected_pole',
                    eigenvalue=[float(value.real*time_scale),float(value.imag*time_scale)]))
            elif null is None:
                if real_pencil:
                    for previous,basis in recovered:
                        if (previous.imag*value.imag < 0 and
                                abs(previous.conjugate()-value)<=1e-12*max(1.,abs(value))):
                            left,record=conjugate_left(sparse_a,sparse_m,value,vk,previous,basis)
                            if left is None:
                                recovery['conjugate_rejected']+=1
                            else:
                                null=(left/np.linalg.norm(left))[:,None]
                                recovery['conjugate_reuse']+=1
                                record['source_eigenvalue']=[float(previous.real*time_scale),float(previous.imag*time_scale)]
                                inverse_records.append({**record,'eigenvalue':[float(value.real*time_scale),float(value.imag*time_scale)]})
                                break
                if null is None:
                    left,record=inverse_left(sparse_a,sparse_m,value,vk)
                    inverse_records.append({**record,'eigenvalue':[float(value.real*time_scale),float(value.imag*time_scale)]})
                    if left is None:recovery['inverse_iteration_failed']+=1
                    else:
                        null=(left/np.linalg.norm(left))[:,None]
                        recovery['inverse_iteration']+=1;direct_inverse=True
        elif sparse_a is not None and value!=0 and np.sum(abs(dense_values-value)<1e-7*max(1.,abs(value)))==1:
            if real_pencil:
                for previous,basis in recovered:
                    if abs(previous.conjugate()-value)<=1e-12*max(1.,abs(value)):
                        trial=basis.conj()
                        if np.linalg.norm((sparse_a.conj().T-value.conjugate()*sparse_m.conj().T)@trial)<=1e-11*pencil_norm:
                            null=trial;recovery['conjugate_reuse']+=1;break
            if null is None:
                null=_sparse_adjoint(sparse_a,sparse_m,value,vk,pencil_norm)
                if null is None:recovery['sparse_rejected']+=1
                else:recovery['sparse_adjoint']+=1;recovered.append((value,null))
        if null is None:
            if full_values is None:
                homogeneous,full_left=eig(aa.toarray() if issparse(aa) else aa,
                    mm.toarray() if issparse(mm) else mm,left=True,right=False,homogeneous_eigvals=True)
                alpha,beta=homogeneous;full_values=np.full(len(alpha),complex(np.inf))
                valid=abs(beta)>np.finfo(float).tiny;full_values[valid]=alpha[valid]/beta[valid]
                recovery['schur_pencils']+=1
            matched=np.flatnonzero(abs(full_values-value)<1e-7*max(1.,abs(value)))
            if len(matched):
                null,triangular,_=qr(full_left[:,matched],mode='economic',pivoting=True)
                null=null[:,abs(np.diag(triangular))>1e-10]
            else:null=np.empty((full_size,0))
            recovery['schur_vectors']+=1
        error = np.linalg.norm(residual_a.T@null.conj()-value*(residual_m.T@null.conj()))/max(pencil_norm,np.finfo(float).tiny)
        if not null.shape[1] or error > 1e-9:
            recovery['nullspace_fallback']+=1
            pencil = (aa-value*mm).conj().T
            _, singular, vh = svd(pencil.toarray() if issparse(pencil) else pencil)
            null = vh[singular <= max(1e-12, 100*np.finfo(float).eps*full_size)*singular[0]].conj().T
            if not null.shape[1]:
                null = vh[-1:].conj().T
        if direct:left_bases.append(null*time_scale/row_scale[:,None])
        mv = residual_m@vk
        wk = null@(null.conj().T@mv)
        if np.linalg.norm(wk) < 1e-12*np.linalg.norm(mv):
            wk = null[:, 0]
        wk = wk/np.linalg.norm(wk)
        pairing = np.vdot(wk, mv)
        normalized = abs(pairing) > 1e-9*np.linalg.norm(mv)
        if normalized:
            wk = wk/np.conj(pairing)
        av = residual_a@vk
        wa, wm = residual_a.T@wk.conj(), residual_m.T@wk.conj()
        right_residual, left_residual = av-value*mv, wa-value*wm
        er = np.linalg.norm(right_residual)/(np.linalg.norm(av)+abs(value)*np.linalg.norm(mv)+1e-30)
        el = np.linalg.norm(left_residual)/(np.linalg.norm(wa)+abs(value)*np.linalg.norm(wm)+1e-30)
        # The normwise residual remains meaningful for exact zero eigenvalues.
        backward = np.linalg.norm(right_residual)/max(pencil_norm*np.linalg.norm(vk),np.finfo(float).tiny)
        left_backward = np.linalg.norm(left_residual)/max(pencil_norm*np.linalg.norm(wk),np.finfo(float).tiny)
        if max(backward, left_backward) > (1e-7 if direct else max(1e-7, 100*rank_tolerance)):
            raise AnalysisError('A mode fails the full descriptor residual check; refine the linearization/rank tolerance.')
        lam = value*time_scale
        modes.append(dict(eigenvalue=[float(lam.real), float(lam.imag)], right=vk, left=wk*time_scale/row_scale,
                          right_backward_error=float(backward), left_backward_error=float(left_backward),
                          right_relative_residual=float(er), left_relative_residual=float(el),
                          biorthogonal_normalized=bool(normalized),exact_integrator=bool(exact_zero)))
        if direct_inverse and normalized and real_pencil:
            recovered.append((value,(wk/np.linalg.norm(wk))[:,None]))
    biorthogonality=None
    if direct:
        from .modal_arnoldi import pair_selected_modes
        biorthogonality=pair_selected_modes(modes,left_bases,a,m)
    # The shifted selection controls returned vectors, not spectrum coverage.
    # A dense solve already computed every reduced finite root; retain that
    # census so downstream comparisons cannot mistake the selected subset for
    # the lowest modes. Arnoldi provides no complete census. Deflated zeros
    # belong to the full finite spectrum even when no dynamic quotient remains.
    finite_spectrum = None
    if used == 'dense':
        all_values = np.r_[np.empty(0, dtype=complex) if dense_values is None else dense_values,
                           np.zeros(zero_count)]*time_scale
        finite_spectrum = dict(
            scope='Complete numerically reduced finite spectrum, including deflated zero roots.',
            eigenvalues=[[float(value.real), float(value.imag)] for value in all_values])
    return modes, dict(full_dimension=full_size, finite_dimension=dimension, eliminated_dimension=None if direct else full_size-dimension,
        method=used, requested_method=method, requested_count=count, shift=shift.tolist(),
        pencil_storage='sparse' if direct else 'dense',
        rank_tolerance=None if direct else rank_tolerance, time_scale=time_scale, finite_mass_reciprocal_condition=condition,
        shift_pencil_reciprocal_condition=shift_condition, finite_spectrum=finite_spectrum,
        **(dict(arnoldi=arnoldi,biorthogonality=biorthogonality,inverse_iteration=inverse_records,
                right_refinement=refinement_records) if direct else {}),
        spectrum_scope='Local full-descriptor Arnoldi search; total finite dimension unclassified.' if direct else 'Numerically reduced finite pencil.',
        right_reduction=rh,integrator_deflation={**(integrators.report() if integrators is not None else
            dict(count=0,operations=[],criterion='Not applied: full descriptor retained for the published shifted Arnoldi operator.',
                 retained_rows=list(range(full_size)),retained_columns=list(range(full_size)))),
            'original_A_nullity_estimate':None if zero_vectors is None else zero_vectors.shape[1],
            'quotient_finite_dimension':dynamic_dimension},
        left_recovery=('Checked bordered Ritz refinement with reused adjoint LU, otherwise ASWING Eq150 inverse iteration and checked simple conjugate adjoints for real pencils; explicit original-pencil Schur/null-space fallback for singular, unresolved or repeated poles; Eq152 selected-space pairing' if direct else
            'Original A kernel for certified integrators; checked sparse bordered adjoints for simple dense-spectrum poles, with original generalized-Schur/null-space fallback and repeated-pole pairing'),
        left_recovery_counts=recovery)


def _dynamic_base(network, x, constraints, frame, options, *, position, attitude, velocity,
                  gravity_magnitude, controller=None):
    """Express one accepted physical equilibrium in its final dynamic chart."""
    c, motion, _ = network.operating.apply(x[network.operating_start:])
    n = copy(network)
    n.condition, n.motion = c, motion
    n.operating = OperatingSystem(n.model,c,motion,constraints,n.L,n.F)
    n.size = n.operating_start+len(constraints)
    base = np.r_[x[:n.operating_start],np.zeros(len(constraints))]
    n.aero_key = n.mass_key = None
    if np.max(abs(n.residual(base,**options))) > 1e-7:
        raise AnalysisError('Dynamic base net loads must satisfy the selected frame targets. Compute a matching equilibrium or trim first.')
    if controller is not None:controller.network=n
    return DynamicSystem(n,base,frame,position=position,attitude=attitude,velocity=velocity,
                         gravity_magnitude=gravity_magnitude,controller=controller)


def _source_dynamic_scope(model, condition, *, frame, motion=None, velocity=(0, 0, 0),
                          controller=None, operating_constraints=(), load_targets=None,
                          quiescent_density=None, strut_mode='bilateral',
                          structural_operator='drela-fixed-vacuum-v1'):
    """Validate the selected source operator without broadening old policies."""
    from .beam_spline import DRELA_SEGSPL
    from .source_quiescent import FLUID_POLICY
    from .source_dynamics import MOVING_POLICY, check_frame_constraints
    from .source_airflow import AIRFLOW_POLICY
    if strut_mode not in ('bilateral', 'wire'):
        raise AnalysisError('Strut mode must be bilateral or wire.')
    if structural_operator == AIRFLOW_POLICY:
        from .aero import FlightCondition
        if model.beam_interpolation != DRELA_SEGSPL:
            raise AnalysisError('Source airflow dynamics requires drela-segspl-v1 beam interpolation.')
        if not isinstance(condition, FlightCondition) or quiescent_density is not None:
            raise AnalysisError('Source airflow dynamics requires a FlightCondition and no separate quiescent fluid.')
        check_frame_constraints(operating_constraints, 'Source airflow dynamics')
        if load_targets is not None or not operating_constraints:
            time_load_constraints('prescribed' if frame == 'fixed' else frame, load_targets)
        if frame not in ('fixed', 'prescribed', 'free', 'mixed'):
            raise AnalysisError('Source airflow frame must be fixed, prescribed, free or mixed.')
        return
    if structural_operator == MOVING_POLICY:
        if model.beam_interpolation != DRELA_SEGSPL:
            raise AnalysisError('Source moving vacuum dynamics requires drela-segspl-v1 beam interpolation.')
        if (condition is not None or quiescent_density is not None or controller is not None):
            raise AnalysisError('Source moving vacuum dynamics requires no airflow, quiescent fluid or controller.')
        v = np.asarray(velocity, dtype=float)
        if v.shape != (3,) or not np.all(np.isfinite(v)):
            raise AnalysisError('Source moving vacuum dynamics requires a finite frame velocity.')
        check_frame_constraints(operating_constraints)
        # DynamicSystem already owns the canonical constraints. The factory
        # validates the requested frame/targets before network construction.
        if load_targets is not None or not operating_constraints:
            time_load_constraints('prescribed' if frame == 'fixed' else frame, load_targets)
        if frame not in ('fixed', 'prescribed', 'free', 'mixed'):
            raise AnalysisError('Source moving vacuum frame must be fixed, prescribed, free or mixed.')
        return
    still_air = structural_operator == FLUID_POLICY
    medium = 'still-air' if still_air else 'vacuum'
    if model.beam_interpolation != DRELA_SEGSPL:
        raise AnalysisError(f'Source {medium} dynamics requires drela-segspl-v1 beam interpolation.')
    if still_air:
        from .quiescent import density_value
        density_value(quiescent_density)
    if (frame != 'fixed' or condition is not None or (not still_air and quiescent_density is not None)
            or controller is not None or len(operating_constraints)
            or load_targets not in (None, {})):
        raise AnalysisError(f'Source {medium} dynamics requires a fixed frame without airflow, controller, operating constraints, load targets; density is supported only by the explicit still-air policy.')
    v = np.asarray(velocity, dtype=float)
    if v.shape != (3,) or not np.all(np.isfinite(v)) or np.any(v != 0):
        raise AnalysisError(f'Source {medium} dynamics requires zero frame velocity.')
    if motion is not None and any(np.any(getattr(motion, name))
            for name in ('rates', 'acceleration', 'angular_acceleration')):
        raise AnalysisError(f'Source {medium} dynamics requires zero frame rates and accelerations.')


def make_system(model, condition=None, panels=8, *, frame='fixed', gravity=None, loads=(), motion=None,
                operating_constraints=(), tolerance=1e-9, continuation_steps=4, strut_mode='bilateral',
                position=(0, 0, 0), attitude=(0, 0, 0), velocity=(0, 0, 0), gravity_magnitude=None, controller=None,
                initial_state=None, load_targets=None, progress=None, structured_base=False,
                _retain_equilibrium_tangent=None, quiescent_density=None,
                quiescent_body_added_mass_factor=None, structural_operator=None):
    if quiescent_density is None and quiescent_body_added_mass_factor is not None:
        raise AnalysisError('A still-air body coefficient requires explicit quiescent_density.')
    network_class = StaticNetwork
    if structural_operator not in (None, 'midpoint-v1'):
        from .source_dynamics import SourceDynamicNetwork, DYNAMIC_POLICY, SourceMovingNetwork, MOVING_POLICY
        from .source_quiescent import SourceQuiescentNetwork, FLUID_POLICY
        from .source_airflow import SourceAirflowNetwork, AIRFLOW_POLICY
        classes = {DYNAMIC_POLICY: SourceDynamicNetwork, FLUID_POLICY: SourceQuiescentNetwork,
                   MOVING_POLICY: SourceMovingNetwork, AIRFLOW_POLICY: SourceAirflowNetwork}
        if structural_operator not in classes:
            raise AnalysisError('Unknown or unsupported dynamic structural operator.')
        _source_dynamic_scope(model, condition, frame=frame, motion=motion,
            velocity=velocity, controller=controller, operating_constraints=operating_constraints,
            load_targets=load_targets, quiescent_density=quiescent_density, strut_mode=strut_mode,
            structural_operator=structural_operator)
        network_class = classes[structural_operator]
    if quiescent_density is not None:
        from .quiescent import prepare
        if condition is not None:
            if (quiescent_body_added_mass_factor is not None
                    and quiescent_body_added_mass_factor != condition.body_added_mass_factor):
                raise AnalysisError('FlightCondition body coefficient conflicts with the still-air body coefficient.')
            quiescent_body_added_mass_factor = condition.body_added_mass_factor
        quiescent_density, position, attitude, gravity_magnitude = prepare(model, condition, quiescent_density,
            frame=frame, motion=motion, velocity=velocity, position=position, attitude=attitude,
            gravity_magnitude=gravity_magnitude, controller=controller,
            operating_constraints=operating_constraints, load_targets=load_targets)
        condition = None
    if frame not in ('fixed', 'prescribed', 'free', 'mixed'):
        raise AnalysisError('Modal frame must be fixed, prescribed, free or mixed.')
    dynamic_constraints=time_load_constraints('prescribed' if frame=='fixed' else frame,load_targets)
    if gravity_magnitude is not None and (not np.isfinite(gravity_magnitude) or gravity_magnitude < 0):
        raise AnalysisError('Modal gravity magnitude must be finite and nonnegative.')
    constraints = list(operating_constraints) or dynamic_constraints
    feedback, trim, retained_system = None, None, None
    pose = dict(position=position,attitude=attitude,velocity=velocity,gravity_magnitude=gravity_magnitude)
    if controller is not None:
        from .steady_feedback import solve_feedback_base
        n, state, feedback, options, steps, diagnostics = solve_feedback_base(model, condition, panels,
            controller=controller, gravity=gravity, loads=loads, motion=motion, operating_constraints=constraints,
            tolerance=tolerance, continuation_steps=continuation_steps, strut_mode=strut_mode,
            residual_options={'zero_local_rates':True},initial_state=initial_state,
            network_class=network_class)
        x=state.x
        _, data=n.residual(x, detail=True, **options)
        c, motion=data['condition'],data['motion']
        trim=dict(operating_constraints=data['operating_constraints'], operating_values=data['operating_values'],
                  controller_equilibrium=diagnostics)
        # Trim commands become prescribed constants in the dynamic problem.
        # Actual actuator values remain separate algebraic dynamic unknowns.
        feedback.commands.update({name:state.commands[name] for name in feedback.signals})
        feedback.bias.update({name:state.commands[name] for name in feedback.bias})
    else:
        from .equilibrium_state import warm_start_recipe
        n = network_class(model, panels, condition, gravity, loads, motion, constraints, strut_mode,
                          quiescent_density=quiescent_density,
                          quiescent_body_added_mass_factor=quiescent_body_added_mass_factor,
                          mesh_recipe=warm_start_recipe(model, panels, initial_state))
        n._frequency_local_geometry=structured_base
        zero = np.zeros_like(n.rj)
        options = dict(elastic_motion=(zero, zero, zero, zero), circulation_rate=np.zeros(n.circulation_basis.panels))
        if condition is None and not n.gravity_override:
            options['gravity_override'] = body_to_earth(attitude).T@np.array([0., 0., -(model.constants[0] if gravity_magnitude is None else gravity_magnitude)])
        if (initial_state is not None and _retain_equilibrium_tangent is not None
                and n.operating.constraints == dynamic_constraints and not n.operating.custom):
            from .equilibrium_state import correct
            from .equilibrium_tangent import retain_for_rank
            tangent_step, tangent_sparse = _retain_equilibrium_tangent
            def final_tangent(values):
                nonlocal retained_system
                candidate = _dynamic_base(n,values,dynamic_constraints,frame,options,**pose)
                # The zero-rate dynamic and steady equations must describe the
                # same operating point before sharing their physical block.
                zero=np.zeros(candidate.size)
                physical=candidate.residual(zero,zero)[:n.size]
                original=n.residual(values,**options)
                if not np.allclose(physical,original,atol=2e-13,rtol=2e-13):
                    return n.jacobian(values,1.,**options)
                def report(done,total):
                    if progress is not None:progress('equilibrium_tangent',min(done,n.size),n.size)
                matrix=retain_for_rank(candidate,values,tangent_step,sparse=tangent_sparse(candidate.size),progress=report)
                retained_system=candidate
                return matrix
            x,steps=correct(n,initial_state,tolerance,options,final_tangent=final_tangent,progress=progress)
        elif initial_state is None:
            # Cold stationary bases share checked steady continuation; the
            # explicit structured_base flag only selects local geometry reuse.
            from .time_integration import initial_equilibrium
            x,steps=initial_equilibrium(n,options,tolerance,continuation_steps,progress)
        else:
            x, steps = equilibrate(n, tolerance, continuation_steps,initial_state=initial_state,progress=progress, **options)
        c, motion, _ = n.operating.apply(x[n.operating_start:])
    from .equilibrium_state import capture
    saved_equilibrium=capture(n,x,feedback=feedback,
        feedback_values=None if feedback is None else state.feedback,
        commands=None if feedback is None else state.commands,
        launch_frame=dict(position=position,attitude=attitude,velocity=velocity,gravity_magnitude=gravity_magnitude))
    system = retained_system or _dynamic_base(n,x,dynamic_constraints,frame,options,controller=feedback,**pose)
    system.steady_trim=trim
    system.equilibrium_state=saved_equilibrium
    system.equilibrium_initialization=diagnostics if feedback is not None else getattr(n,'equilibrium_diagnostics',dict(initialization='undeformed load continuation'))
    return system, steps


def complex_data(value):
    array = np.asarray(value)
    return dict(real=array.real.tolist(), imag=array.imag.tolist())


@wall_root_linearization
def output_perturbation(system, vector, rate, step=1e-5, *, forcing=None, input_scale=1., _field_tangent=None,
                        _load_tangent=None, _load_input=None):
    """Physical complex output, including input and derivative feedthrough.

    forcing(part, increment) returns a real residual-options transformation;
    part 0/1 denotes the real/imaginary spatial input. The stencil bounds the
    scaled state displacement while retaining a useful physical input step.
    """
    n = system.network
    if system._section_output_mask is None or system._sensor_output_mask is None:
        system.base_report()
    requested_step=step
    v, rate = np.asarray(vector), np.asarray(rate)
    if forcing is None:
        # A homogeneous direction can be rescaled without changing its tangent.
        # Initial spectra can be much smaller than the loaded state; applying
        # the input-amplitude cap here would subtract indistinguishable loads.
        # Grow a small-direction stencil only until its rate increment reaches
        # the nominal step. Preserve the established state stencil for ordinary
        # normalized modes: shrinking it by a large modal rate loses strains
        # when loaded positions are subtracted in the output recovery.
        norm=max(float(np.max(abs(v))),min(float(np.max(abs(rate)))/system.W,1.))
        step=step/(norm if norm else 1.)
    else:
        step = min(step*input_scale, step/max(float(np.max(abs(v))), 1e-30))
    snapshots = [];point_positions=[]
    field_input=None if _field_tangent is None else _field_tangent.input_column(forcing)
    if forcing is not None and field_input is None:_field_tangent=None
    for component, part in enumerate((np.real, np.imag)):
        for sign in (1, -1):
            z, zdot = sign*step*part(v), sign*step*part(rate)
            applied = None if forcing is None else forcing(component, sign*step)
            if _field_tangent is None:state,snapshot=system.snapshot(z,zdot,forcing=applied)
            else:
                delta=0. if forcing is None else sign*step*part(field_input)
                state,snapshot=_field_tangent.snapshot(z,zdot,forcing=applied,input_delta=delta)
            def earth(points):
                if not np.size(points):
                    return []
                return (np.asarray(points)@state.orientation.T+state.position).tolist()
            snapshot['earth_geometry'] = [dict(index=b['index'], **{field:earth(b[field])
                for field in ('quads', 'axis', 'streamwise_quads') if field in b}) for b in snapshot['geometry']]
            snapshot['earth_attachments'] = [dict(kind=a['kind'], segments=earth(a['segments'])) for a in snapshot['attachments']]
            snapshots.append(snapshot)
            point_positions.append(n.point_positions(state.r,state.Q))

    if _field_tangent is not None and not _field_tangent.active:
        return output_perturbation(system,vector,rate,requested_step,forcing=forcing,input_scale=input_scale)

    def delta(values, period=None):
        if any(value is None for value in values):
            return None
        a, b, c, d = map(np.asarray, values)
        real, imag = a-b, c-d
        if period is not None:
            real, imag = (v-period*np.round(v/period) for v in (real, imag))
        return complex_data((real+1j*imag)/(2*step))

    shape = v[:6*n.nn].reshape(n.nn, 6)
    velocity, rates = v[system.velocity_start:system.frame_start].reshape(2, n.nn, 3)
    output = dict(nodes=[dict(index=i, displacement=complex_data(n.L*shape[i, :3]),
                              rotation=complex_data(shape[i, 3:]), velocity=complex_data(system.V*velocity[i]),
                              rates=complex_data(system.W*rates[i])) for i in range(n.nn)])
    for key in ('geometry', 'earth_geometry'):
        output[key] = [dict(index=b['index'], **{field:delta([s[key][i][field] for s in snapshots])
                       for field in ('quads', 'axis', 'streamwise_quads') if field in b})
                       for i, b in enumerate(snapshots[0][key])]
    for key in ('attachments', 'earth_attachments'):
        output[key] = [dict(kind=a['kind'], segments=delta([s[key][i]['segments'] for s in snapshots]))
                       for i, a in enumerate(snapshots[0][key])]
    output['global'] = {key:delta([s.get(key) for s in snapshots]) for key in
                       ('force', 'moment', 'moment_origin', 'applied_force', 'applied_moment', 'support_force', 'support_moment',
                        'surface_force', 'distributed_aero_force', 'distributed_aero_moment', 'circulation_rate_force',
                        'circulation_rate_moment', 'body_force', 'engine_force', 'engine_moment', 'apparent_force',
                        'apparent_moment', 'distributed_aero_moment_origin', 'CL', 'CD', 'CDi', 'CDi_near', 'CLi', 'CYi', 'CDp', 'CDam', 'CDbody', 'CDeng', 'CY', 'Cl', 'Cm', 'Cm_origin', 'Cn')}
    from .output_derivatives import aerodynamic_moments
    for key,value in aerodynamic_moments(snapshots,point_positions,n.model.reference[1],step).items():
        output['global'][key]=complex_data(value)
    from .support_outputs import support_outputs
    for key,value in support_outputs(system,v,snapshots).items():
        output['global'][key]=complex_data(value)
    if _load_tangent is not None:
        from .applied_load_outputs import AppliedLoadUnavailable
        try:values=_load_tangent.apply(v,rate,forcing,_load_input,snapshots)
        except AppliedLoadUnavailable as exc:
            key=str(exc);_load_tangent.fallbacks[key]=_load_tangent.fallbacks.get(key,0)+1
        else:
            for key,value in values.items():output['global'][key]=complex_data(value)
    output['operating'] = {key:delta([s['operating_values'][key] for s in snapshots])
                           for key in snapshots[0]['operating_values']}
    output['strips'] = [dict(beam=strip['beam'], t=strip['t'], **{key:delta([s['strips'][i].get(key) for s in snapshots])
                            for key in ('force', 'moment', 'circulation', 'cl', 'apparent_force')})
                       for i, strip in enumerate(snapshots[0].get('strips', []))]
    for i, strip in enumerate(output['strips']):
        # A finite pair of perturbed samples does not define a derivative of
        # an unavailable base quantity (notably incidence at stagnation).
        strip.update({key: delta([s['strips'][i].get(key) for s in snapshots])
                      if system._section_output_mask[i][key] else None for key in SECTION_OUTPUTS})
    if 'section_output_definitions' in snapshots[0]:
        output['section_output_definitions'] = dict(snapshots[0]['section_output_definitions'],
            linearization='Complex perturbations about the loaded base, including changes of section normal, current length and relative flow, and direct input/rate terms. da_eff uses radians. Undefined base quantities remain unavailable.')
    from .structural_outputs import structural_outputs
    physical_sections=structural_outputs(system,v,step,snapshots)
    if physical_sections is not None:
        output['sections'] = [dict(beam=section['beam'],t=section['t'],
            **{key:None if value is None else complex_data(value) for key,value in values.items()})
            for section,values in zip(snapshots[0]['elements'],physical_sections)]
    else:
        output['sections'] = [dict(beam=section['beam'], t=section['t'], **{key:delta([s['elements'][i].get(key) for s in snapshots])
                                  for key in ('force_local', 'moment_local', 'strain', 'curvature_change', 'axial_strain_tension')})
                             for i, section in enumerate(snapshots[0]['elements'])]
        for i, section in enumerate(output['sections']):
            section['shell_strain'] = delta([s['elements'][i]['shell']['axial_strain'] for s in snapshots])
            section['shell_shear_stress'] = delta([s['elements'][i]['shell']['shear_stress'] for s in snapshots])
    from .span_output_derivatives import add_span_outputs
    add_span_outputs(output, snapshots, delta)
    from .sensors import UNITS
    output['sensors'] = [dict(index=sensor['index'], beam=sensor['beam'], t=sensor['t'],
        **{key:delta([s['sensors'][i].get(key) for s in snapshots], 360 if key in ('alpha','beta','bank','elevation','heading') else None)
           if system._sensor_output_mask[i][key] else None
           for key in UNITS}) for i,sensor in enumerate(snapshots[0]['sensors'])]
    if system.frame != 'fixed':
        U, Omega, p, angles = v[system.frame_start:system.feedback_start].reshape(4, 3)
        output['frame'] = dict(velocity_origin_body=complex_data(system.V*U), rates_body=complex_data(system.W*Omega),
                               position_earth=complex_data(system.L*p), attitude_rad=complex_data(angles))
    else:
        output['frame'] = None
    if system.feedback is not None:
        from .feedback import ANGLE_CHANNELS
        output['feedback']={f'{group}_{name}':delta([s['feedback'][group][name] for s in snapshots],
            360 if group in ('errors','measurements','commands') and name.split('[')[0] in ANGLE_CHANNELS else None)
            for group,values in snapshots[0]['feedback'].items() for name in values}
        for j,state in enumerate(system.feedback.states,system.feedback.state_start):
            index=system.feedback_start+j;scale=system.feedback.scales[j]
            output['feedback']['states_'+state['name']]=complex_data(scale*v[index])
            output['feedback']['state_rates_'+state['name']]=complex_data(scale*rate[index])
    return output


def modal_output(system, mode, step=1e-5):
    """Linear eigenmode output in the saved right-vector normalization."""
    v = mode['right']
    return output_perturbation(system, v, complex(*mode['eigenvalue'])*v, step)


def state_layout(system):
    """Scaled descriptor coordinates shared by modal and forced responses."""
    n = system.network
    return dict(network_size=n.size, nodes=n.nn, elements=n.ne,
                        node_coordinates=dict(start=0, width=6*n.nn, order='interleaved body translation / L and spatial rotation in radians', translation_scale=n.L),
                        internal_loads=dict(start=6*n.nn, width=6*n.ne, force_scale=n.F, moment_scale=n.F*n.L),
                        reactions=dict(start=6*(n.nn+n.ne), width=n.nc),
                        circulation=dict(start=n.gamma_start, width=n.ng, scale=n.gamma_scale, discretization=n.circulation_basis.report()),
                        operating=dict(start=n.operating_start, variables=[c.variable for c in n.operating.constraints],
                                       scales=[n.operating.scale[c.variable] for c in n.operating.constraints]),
                        local_velocity=dict(start=system.velocity_start, width=3*n.nn, scale=system.V),
                        local_rates=dict(start=system.velocity_start+3*n.nn, width=3*n.nn, scale=system.W),
                        frame=dict(start=system.frame_start, width=12 if system.frame != 'fixed' else 0,
                                   order='U_body, Omega_body, position_Earth, bank/elevation/heading',
                                   scales=[system.V, system.W, system.L, 1.]),
                        feedback=None if system.feedback is None else dict(start=system.feedback_start,
                            actuators=list(system.feedback.bias),integrals=system.feedback.integrals,
                            states=[s['name'] for s in system.feedback.states],scales=system.feedback.scales.tolist()))


def solve_modes(model, condition=None, panels=8, *, frame='fixed', count=16, shift=(-.01, 0.), method='dense',
                step=1e-5, rank_tolerance=1e-9, matrices=False, progress=None, vacuum=False,
                quiescent_density=None, **base_options):
    if base_options.get('structural_operator') in ('drela-fixed-vacuum-v1', 'drela-fixed-still-air-v1', 'drela-moving-vacuum-v1') and condition is not None:
        raise AnalysisError('Source modes require no FlightCondition; a vacuum flag does not discard an aerodynamic setup.')
    if vacuum and quiescent_density is not None:
        raise AnalysisError('Vacuum and quiescent_density are mutually exclusive.')
    if vacuum and condition is not None:
        if model.records.get('engine'):
            raise AnalysisError('Vacuum modes with Engine blocks are not implemented; use a structural-only configuration with rotor inertia in Weight records.')
        if base_options.get('operating_constraints'):
            raise AnalysisError('Vacuum modes do not accept aerodynamic trim targets.')
        base_options.update(motion=condition.motion(), position=condition.position_earth, attitude=condition.attitude,
            gravity_magnitude=condition.gravity_magnitude,
            velocity=(-condition.speed*condition.vectors()[0]-np.cross(condition.rates, model.reference[3])).tolist())
        condition = None
    system, continuation = make_system(model, condition, panels, frame=frame, quiescent_density=quiescent_density, **base_options)
    # Full-pencil Arnoldi can share the checked geometry, circulation and local
    # motion derivatives already used by frequency analysis. These retain all
    # moving induced-field terms and fall back to full residual differences.
    structured = method == 'full_shift_invert'
    a, m = linearize(system, step, progress, sparse=structured)
    assembly = dict(structured=structured)
    if structured:
        assembly.update(A_nonzeros=int(a.nnz), M_nonzeros=int(m.nnz))
        assembly['storage'] = 'sparse through full-pencil iteration; dense only for requested matrix export or recovery fallback'
    modes, metadata = eigensystem(a, m, time_scale=system.W, count=count, shift=shift,
                                 method=method, rank_tolerance=rank_tolerance)
    n = system.network
    base = system.base_report()
    base['continuation_steps'] = continuation
    base['limitations'][0] = 'Loaded base state for the frozen continuous-time modal linearization.'
    damping_times = np.unique(n.damping_times[n.damping_times > 0])
    for index, mode in enumerate(modes):
        lam = complex(*mode['eigenvalue'])
        mode['index'] = index
        mode['frequency'] = abs(lam.imag)/(2*np.pi)
        mode['damping_ratio'] = float(-lam.real/abs(lam)) if abs(lam) > 1e-10*system.W else None
        threshold = 1e-7*max(system.W, abs(lam))
        mode['stability'] = 'neutral' if lam==0 else 'near neutral' if abs(lam.real) <= threshold else 'unstable' if lam.real > 0 else 'decaying'
        mode['stability_tolerance']=float(threshold)
        mode['constitutive_relaxation'] = bool(any(abs(lam+1/t) < 1e-5*max(abs(lam), 1/t) for t in damping_times))
        mode['output'] = modal_output(system, mode, step)
        mode['right'], mode['left'] = complex_data(mode['right']), complex_data(mode['left'])
    residual_zero = system.residual(np.zeros(system.size), np.zeros(system.size))
    metadata.update(difference_step=step, state_difference_order=4, derivative_linearization=system.derivative_diagnostics,
                    state_linearization=system.state_derivative_diagnostics, matrix_assembly=assembly,
                    base_residual=float(np.max(abs(residual_zero))),
                    continuation_steps=continuation, residual_evaluations=n.nfev,
                    normalization='Right vector pivot is real and one in scaled state coordinates. When possible, left^H M right = 1 with physical input-time M.',
                    equation='M dz/dt = A z; eigenvalues have units 1/input T; time and frequency use the ASW input time unit.',
                    state_layout=state_layout(system))
    metadata['material_damping'] = n.damping_report()
    limitations = [
        'Experimental eigenmodes of the complete implemented unsteady residual; ASWING discrete/executable parity and measured flutter validation remain unverified.',
        'Coefficients are frozen at this operating point. Untrimmed, spatial-gust and ground-varying states need a separate check that the base changes slowly relative to the mode.',
        'The reduced methods classify algebraic and differentiated constraints numerically. Full-descriptor Arnoldi retains them in a local search and leaves the total finite dimension unclassified. Check mesh, difference step, rank and nearby shifts; eigenpair residuals alone do not prove physical accuracy.',
        'The published strain-rate law can produce finite relaxation poles, including in zero-compliance directions and massless elements. Poles near -1/damping_time are labeled, not silently removed.',
        'Eigenvector magnitude and phase are arbitrary. Output geometry and loads are linear perturbations about the loaded base, not a finite-amplitude nonlinear simulation.',
        'Repeated or defective zero modes may not admit individual left/right mass normalization; those pairs are marked. Mode truncation and ROM validity are not established.',
        'Exact coordinate integrator factors preserve their zero roots. Other small computed roots are not snapped to zero; the near-neutral display threshold is not an eigenvalue error bound. General Jordan chains and invariant subspaces are not constructed.',
        'Prescribed and mixed motion retain all twelve frame kinematic states; selected accelerations follow net-load targets and other accelerations remain prescribed. Fixed frame omits these states entirely.',
        'Declared feedback adds algebraic actuator settings and differential error integrals. Other settings are held at their solved base values. Arbitrary custom controller and full control-file parity remain unverified.'
    ]
    if metadata['method'] == 'full_shift_invert':
        limitations[6] = ('Full-pencil Arnoldi applies no integrator deflation and certifies no exact zero multiplicity. '
            'Small computed roots are not snapped to zero; the near-neutral display threshold is not an eigenvalue error bound. '
            'General Jordan chains are not constructed. Left inverse-iteration failures and repeated-pole recovery are reported explicitly.')
    if getattr(n, 'source_dynamic', False):
        limitations[0] = ('Fixed-frame vacuum eigenmodes of the explicit source endpoint-average structural/inertia operator. '
            'Historical ASWING discrete/executable parity remains unverified.')
        limitations[1] = 'Coefficients are linearized about a stationary loaded structural equilibrium in a fixed frame; airflow and moving-frame dynamics are unavailable.'
        limitations[3] += (' Source rates use unsteady Eq.60 and full Eq.62 with local-axis Eq.57 damping; '
            'endpoint time averaging and exact historical implementation remain unverified. Damped sensor strains are sided interval estimates, not pointwise anchor samples.')
        limitations[7] = 'The fixed frame omits aircraft translational/rotational states. No prescribed, free or mixed frame is supported by this policy.'
        limitations[8] = ('Controllers, aerodynamic apparent mass and flow coupling are outside this bounded policy. '
            'Endpoint-averaged inertia is a finite-difference operator, not a conventional symmetric finite-element mass matrix; variable properties need separate consistency checks.')
        metadata['structural_operator'] = n.structural_operator
        if getattr(n, 'source_moving', False):
            limitations[0] = ('Vacuum eigenmodes of the source endpoint-average operator with moving-frame real inertia. '
                'Historical ASWING discrete/executable parity remains unverified.')
            limitations[1] = ('Coefficients are frozen at the loaded base pose and motion. A rotating or accelerating trajectory '
                'can change these coefficients; local poles do not establish stability of that full trajectory.')
            limitations[7] = ('Fixed frame omits aircraft perturbations; prescribed, free and mixed frames retain all twelve '
                'frame kinematic states. Canonical net-load targets determine selected frame accelerations from the same nodal wrenches.')
            limitations.append('Angular inertia uses alpha_o + omega_dot + Omega cross omega from Earth-frame angular momentum. '
                'The transport term is absent from printed Eqs.40/47; this physical interpretation is explicit, not verified historical code parity.')
        if getattr(n, 'source_quiescent', False):
            limitations[0] = ('Fixed-frame still-air eigenmodes with source endpoint-average real and apparent inertia. '
                'Historical ASWING discrete/executable parity remains unverified.')
            limitations[8] = ('Controllers and circulatory flow coupling are outside this bounded policy. '
                'Stationary surface/body apparent inertia adds only acceleration terms. Endpoint-averaged real and fluid inertia '
                'need not produce a symmetric global mass matrix for varying properties.')
        if getattr(n, 'source_airflow', False):
            limitations[0] = ('Flowing-air eigenmodes of the source moving beam operator coupled to circulation. '
                'Historical ASWING discrete/executable parity remains unverified.')
            limitations[8] = ('Real inertia and material damping use source endpoint averages; circulating and apparent-fluid '
                'loads use Glauert aerodynamic sections with symmetric box-wrench transfer. No second apparent mass is added. '
                'This fluid quadrature differs from the stationary source still-air policy. '
                'Controllers and stepped axes are not yet supported by this source policy.')
    result = dict(analysis='eigenmodes', converged=True, base=base, frame_mode=frame, frame_load_targets=base['modal_base']['load_targets'], modes=modes,
                  vacuum=condition is None and quiescent_density is None, diagnostics=metadata, limitations=limitations,
                  controller=None if system.feedback is None else system.feedback.report())
    if quiescent_density is not None:
        result['fluid'] = base['fluid']
        limitations.extend(base['fluid']['limitations'])
        result['rom_output_catalog'] = []
    else:
        from .rom_outputs import output_catalog
        result['rom_output_catalog'] = output_catalog(base)
    if not metadata['material_damping']['passive']:
        limitations.append('The specified componentwise material damping fails the finite-strain passivity diagnostic. Growth can arise from that constitutive law; it must not automatically be attributed to aerodynamic flutter.')
    if matrices:
        result['matrices'] = dict(A=(a.toarray() if issparse(a) else a).tolist(),
                                  M=(m.toarray() if issparse(m) else m).tolist())
    return result
