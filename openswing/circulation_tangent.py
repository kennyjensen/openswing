"""Direct circulation columns at fixed geometry and local/frame motion.

Section/body/point loads and their nodal transfer are differentiated analytically.
Each engine's axial-inflow derivative uses two refined centered steps; transverse
blade-load derivatives are exact. Jets retain the engine-inflow chain rule.
The caller keeps full residual acceptance and a numerical-column fallback.
"""
import numpy as np
from .vector_ops import cross3
from .propulsion import engine_load, jet_velocity
from .volume import body_quadrature


class CirculationDerivativeUnavailable(ValueError):
    """A derivative branch cannot be resolved within this calculation's gates."""


def dot(a, jac):
    return np.einsum('...i,...ij->...j', a, jac)


def cross(a, jac):
    """a cross each derivative column; xyz is the penultimate Jacobian axis."""
    return np.moveaxis(cross3(a[..., None, :], np.moveaxis(jac, -2, -1)), -1, -2)


def norm_gradient(value, jac, floor=0.):
    speed = np.linalg.norm(value, axis=-1)
    return np.divide(dot(value, jac), speed[..., None], out=np.zeros(jac.shape[:-2]+(jac.shape[-1],)),
                     where=(speed > floor)[..., None])


def norm_product(value, jac):
    speed = np.linalg.norm(value, axis=-1)
    return speed[..., None, None]*jac+value[..., :, None]*norm_gradient(value, jac)[..., None, :]


def resolved(coarse, fine, description):
    error = float(np.max(abs(coarse-fine), initial=0.))
    scale = max(1., float(np.max(abs(fine), initial=0.)))
    if not np.isfinite(error) or error > 1e-8*scale:
        raise CirculationDerivativeUnavailable(description+' did not resolve under step refinement.')
    return fine


class EngineDerivative:
    def __init__(self, data, index, inflow):
        self.engine = engine = data['engines'][index]
        self.density, self.direction = data['rho'], data['jet_direction']
        self.axes = axes = engine['axes']
        row = data['engine_rows'][index]
        velocity = data['engine_velocity'][index]
        self.axial_gradient = axes[:, 0]@inflow
        self.steps, self.states = [], []
        count = inflow.shape[-1]
        self.force, self.moment = np.zeros((3, count)), np.zeros((3, count))
        # A proportional engine at zero thrust/torque has no inflow-dependent
        # force, moment or jet. Its declared disk still remains in the model.
        if engine['type'] == 0 and engine['thrust'] == 0 and engine['torque'] == 0:
            return
        rotation = None if data['engine_rotations'] is None else data['engine_rotations'][index]
        step = 1e-5*max(data['condition'].speed, abs(engine['axial_velocity']))
        if not np.isfinite(step) or step <= 0:
            raise CirculationDerivativeUnavailable('Engine inflow has no finite differentiation scale.')
        derivatives = []
        for h in [step, step/3]:
            try:
                pair = [engine_load(row, data['condition'].powers.get(int(row[0]), 0.), self.density,
                    data['engine_points'][index], velocity+sign*h*axes[:, 0],
                    data['engine_rates'][index], rotation) for sign in [1., -1.]]
            except ValueError as exc:
                raise CirculationDerivativeUnavailable('Engine axial-inflow perturbation: '+str(exc)) from exc
            if any(state['power_clipped'] != engine['power_clipped'] for state in pair):
                raise CirculationDerivativeUnavailable('Engine axial-inflow stencil crosses power clipping.')
            self.steps.append(h); self.states.append(pair)
            derivatives.append(np.r_[(pair[0]['force']-pair[1]['force'])/(2*h),
                                     (pair[0]['moment']-pair[1]['moment'])/(2*h)])
        axial = resolved(*derivatives, 'Engine load derivative')
        self.force = axial[:3, None]*self.axial_gradient
        self.moment = axial[3:, None]*self.axial_gradient
        if engine['type'] == 2:
            cl, cla, s0, c0, s1, c1, _, c2, _, _ = row[15:25]
            radius = engine['radius']; omega = row[13]
            vd = engine['axial_velocity']+engine['delta_velocity']/2
            tip = abs(omega)*radius
            fv = self.density*radius**2/4*((cla*s0-cl*c0)*vd+2*cl*s1*tip)
            mv = -self.density*radius**3/4*((cla*c1+cl*s1)*vd+2*cl*c2*tip)
            transverse = axes[:, 1:]@(axes[:, 1:].T@inflow)
            self.force += fv*transverse
            self.moment += -np.sign(omega)*mv*transverse

    def jet(self, points):
        count = len(self.axial_gradient)
        if not self.states or not self.engine['jet_enabled']:
            return np.zeros(points.shape+(count,))
        derivatives = []
        for h, pair in zip(self.steps, self.states):
            try:
                derivatives.append((jet_velocity(points, [pair[0]], self.direction, self.density)
                    -jet_velocity(points, [pair[1]], self.direction, self.density))/(2*h))
            except ValueError as exc:
                raise CirculationDerivativeUnavailable('Engine jet perturbation: '+str(exc)) from exc
        derivative = resolved(*derivatives, 'Engine jet derivative')
        return derivative[..., None]*self.axial_gradient


_COLUMN_BUDGET = 128*1024**2


class FlowDerivative:
    def __init__(self, net, fields, data, columns=slice(None)):
        self.fields, self.data = fields, data
        self.sample = net.gamma_scale*data['basis'].sample[:, columns]
        # Includes temporary flow/load matrices and the returned residual block.
        receivers = fields.vortex_receiver_count()
        estimate = 8*self.sample.shape[1]*(net.size+18*receivers)
        if estimate > _COLUMN_BUDGET:
            raise CirculationDerivativeUnavailable('Direct circulation derivative storage exceeds its budget.')
        engine_inflow = self.vortex('engine')
        self.engines = [EngineDerivative(data, i, engine_inflow[i]) for i in range(len(data['engines']))]

    def vortex(self, name):
        return self.fields.vortex_column_map(name).apply_columns(self.sample)

    def velocity(self, name, points):
        result = self.vortex(name)
        for engine in self.engines:
            result += engine.jet(points)
        return result


def surface_derivatives(data, flow, circulation_rate_factor=0., *, distributed_only=False,
                        residual_only=False):
    from .aero import _stall_leakage
    p, gamma, rate = data['p'], data['gamma'], data['lag_rate']
    rho, condition = data['rho'], data['condition']
    v, span = data['velocity'], p['s']
    dv = flow.velocity('hv', p['hv'])
    dcp = flow.velocity('cp', p['cp'])
    vp = v-np.sum(v*span, axis=-1)[:, None]*span
    dvp = dv-span[:, :, None]*dot(span, dv)[:, None, :]
    floor = condition.speed*1e-12
    speed = np.maximum(np.linalg.norm(vp, axis=-1), floor)
    dspeed = norm_gradient(vp, dvp, floor)
    cl = 2*gamma/(p['chord']*speed)
    dcl = 2/(p['chord']*speed)[:, None]*(flow.sample-gamma[:, None]/speed[:, None]*dspeed)
    fstall, dfstall = _stall_leakage(cl, p['clmin'], p['clmax'], condition.stall_width)
    dt = dot(p['normal'], dcp)+(2/np.pi*rate/speed**2)[:, None]*dspeed
    normal_partial = getattr(flow, 'normal_partial', None)
    if normal_partial is not None:
        dt += dot(data['cp_velocity'], normal_partial)
    # A BDF circulation column changes both Gamma and Gamma-dot. The same
    # derivative enters shed-vorticity downwash, rate lift and profile drag.
    lag_gradient = (circulation_rate_factor*flow.sample if condition.aero_lag
                    else np.zeros_like(flow.sample))
    dt -= (2/np.pi/speed)[:, None]*lag_gradient
    leakage = ((condition.stall_factor/p['slope'])[:, None]
               *(speed[:, None]*dfstall[:, None]*dcl+fstall[:, None]*dspeed)) if condition.stall else 0.
    residual = (dt-leakage)/condition.speed
    speed_partial = getattr(flow, 'speed_partial', None)
    if speed_partial is not None:
        base_leakage = condition.stall_factor/p['slope']*fstall*speed if condition.stall else 0.
        residual -= ((data['tangency']-base_leakage)/condition.speed**2)[:, None]*speed_partial[None, :]
    residual = data['basis'].test@residual if data['basis'].modes else residual
    if residual_only:
        # The circulation finish only solves the tangency/leakage rows. Do not
        # allocate section loads or their mechanical transfer for unused rows.
        return None, None, residual
    vxspan = cross3(v, span)
    dvxspan = -cross(span, dv)
    lift = rho*p['ds'][:, None, None]*(vxspan[:, :, None]*flow.sample[:, None, :]+gamma[:, None, None]*dvxspan)
    circulation_rate = (rho*p['ds']*p['chord']*rate)[:, None, None]*(dvxspan/speed[:, None, None]
                         -vxspan[:, :, None]/speed[:, None, None]**2*dspeed[:, None, :])
    circulation_rate += (rho*p['ds']*p['chord']/speed)[:, None, None]*vxspan[:, :, None]*lag_gradient[:, None, :]
    t = data['tangency']
    profile = .5*(p['chord']*p['cdf'])[:, None, None]*norm_product(v, dv)
    profile += .5*(p['chord']*p['cdp'])[:, None, None]*(speed[:, None, None]*dvp+vp[:, :, None]*dspeed[:, None, :])
    cdp_partial = getattr(flow, 'cdp_partial', None)
    if cdp_partial is not None:
        profile += (.5*p['chord']*speed)[:, None, None]*vp[:, :, None]*cdp_partial[:, None, :]
    profile += 2*p['chord'][:, None, None]*((t*t/speed)[:, None, None]*dvp
                +vp[:, :, None]*((2*t/speed)[:, None]*dt-(t*t/speed**2)[:, None]*dspeed)[:, None, :])
    profile *= (rho*p['ds'])[:, None, None]
    arm = ((.25-p['xax'])*p['chord'])[:, None]*p['c']
    moment = cross(arm, lift+circulation_rate)
    moment += cross(p['profile_arm'], profile)
    beta = np.sqrt(1-(speed/data['sound_speed'])**2)
    coefficient = .5*rho*p['ds']*p['chord']**2*p['cm']*(2*speed/beta+speed**3/data['sound_speed']**2/beta**3)
    moment += (coefficient[:, None]*span)[:, :, None]*dspeed[:, None, :]
    cm_partial = getattr(flow, 'cm_partial', None)
    if cm_partial is not None:
        moment += (.5*rho*p['ds']*p['chord']**2*speed**2/beta)[:, None, None]*span[:, :, None]*cm_partial[:, None, :]
    force = lift+circulation_rate+profile
    if not distributed_only and np.any(data['rates']):
        axis = flow.velocity('axis', p['rm'])
        drate = dot(cross3(data['rates'], p['section_normal']), axis)
        mass = rho*np.pi/4*p['chord']**2*p['ds']
        added = (mass[:, None]*p['section_normal'])[:, :, None]*drate[:, None, :]
        mid = ((.5-p['xax'])*p['chord'])[:, None]*p['c']
        force += added
        moment += cross(mid, added)-(mass*p['chord']/4)[:, None, None]*span[:, :, None]*drate[:, None, :]
    return force, moment, residual


def body_derivatives(mesh, velocity, flow, density):
    t, positions, radius, weights = body_quadrature(mesh)
    dv = flow.velocity(('body', mesh.beam.index), positions.reshape(-1, 3)).reshape(positions.shape+(flow.sample.shape[1],))
    span = mesh.frames[:, None, :, 1]
    along = np.sum(velocity*span, axis=-1); dalong = dot(span, dv)
    normal = velocity-along[..., None]*span
    dn = dv-span[..., :, None]*dalong[..., None, :]
    area = 2*np.pi*radius*mesh.beam.value('radius', t, derivative=1)*(mesh.t1-mesh.t0)[:, None]/mesh.length[:, None]
    force = (density*area*weights)[..., None, None]*(along[..., None, None]*dn+normal[..., :, None]*dalong[..., None, :])
    force += (density*radius*weights)[..., None, None]*(mesh.beam.value('Cdf', t)[..., None, None]*norm_product(velocity, dv)
               +mesh.beam.value('Cdp', t)[..., None, None]*norm_product(normal, dn))
    return (t-mesh.t0[:, None])/(mesh.t1-mesh.t0)[:, None], force


def transfer(motion, beam, fraction, force, moment):
    """Derivative of NetworkMotion.nodal_wrenches, with a final column axis."""
    net = motion.network; sl = net.beam_elements[beam]
    f = np.broadcast_to(fraction, force.shape[:-2])
    wa, wb = motion.wrench_weights(beam, f)
    for ids, weight, angular, position in ((net.a[sl], 1-f, wa, motion.pa[sl]), (net.b[sl], f, wb, motion.pb[sl])):
        nf = weight[..., None, None]*force
        nm = angular.swapaxes(-1, -2)@moment
        if f.ndim == 2: nf, nm = nf.sum(axis=1), nm.sum(axis=1)
        yield ids, nf, nm+cross(position-motion.r[ids], nf)


def circulation_columns(net, fields, factor, *, circulation_rate_factor=0.):
    data, mechanics = fields.circulation_aero, fields.circulation_mechanics
    if data is None or mechanics is None:
        raise CirculationDerivativeUnavailable('Missing fixed-geometry circulation capture.')
    bytes_per_column = 8*(net.size+18*fields.vortex_receiver_count())
    if bytes_per_column*net.ng <= _COLUMN_BUDGET:
        flow = FlowDerivative(net, fields, data)
        return flow_load_columns(net, fields, flow, factor, circulation_rate_factor=circulation_rate_factor)

    # Retain the same direct derivative on larger meshes by limiting the
    # temporary flow and load matrices to a group of circulation columns.
    width = (_COLUMN_BUDGET-8*net.size*net.ng)//bytes_per_column
    if width < 1:
        raise CirculationDerivativeUnavailable('Direct circulation derivative storage exceeds its budget.')
    result = np.empty((net.size, net.ng))
    for first in range(0, net.ng, width):
        columns = slice(first, first+width)
        flow = FlowDerivative(net, fields, data, columns)
        result[:, columns] = flow_load_columns(net, fields, flow, factor,
                                               circulation_rate_factor=circulation_rate_factor)
    return result


def circulation_residual_columns(net, fields):
    """Exact steady circulation block without assembling mechanical load rows.

    Uses the same stall, induced-flow, engine-jet and basis chain rules as the
    complete columns. The caller must recheck every physical equation after
    applying a circulation-only correction.
    """
    data = fields.circulation_aero
    if data is None:
        raise CirculationDerivativeUnavailable('Missing fixed-geometry circulation capture.')
    flow = FlowDerivative(net, fields, data)
    block = surface_derivatives(data, flow, residual_only=True)[2]
    if not np.all(np.isfinite(block)):
        raise CirculationDerivativeUnavailable('Nonfinite direct circulation derivative.')
    return block


def flow_load_columns(net, fields, flow, factor, *, circulation_rate_factor=0.):
    """Common load/transfer chain rule for circulation or induced-field changes.

    Geometry, local kinematics, condition and material properties are fixed in
    this partial derivative. A geometry assembler must add its local derivative
    separately, including geometry changes in engine loads and load transfer.
    """
    data, mechanics = fields.circulation_aero, fields.circulation_mechanics
    count = flow.sample.shape[1]
    if not np.isfinite(circulation_rate_factor) or circulation_rate_factor < 0:
        raise CirculationDerivativeUnavailable('Invalid circulation time-derivative coefficient.')
    surface_force, surface_moment, residual = surface_derivatives(data, flow, circulation_rate_factor)
    force = np.zeros((net.nn, 3, count)); moment = np.zeros_like(force)
    end_moment = np.zeros((net.ne, 2, 3, count))
    motion, r, Q = mechanics['local_motion'], mechanics['r'], mechanics['Q']
    bodies = {mesh.beam.index: (mesh, v) for mesh, v in data['bodies']}
    for mesh in mechanics['meshes']:
        sl = net.beam_elements[mesh.beam.index]
        if mesh.beam.lifting:
            indices = np.flatnonzero(data['p']['beam'] == mesh.beam.index)
            fraction = net.fractions[mesh.beam.index]
            df, dm = surface_force[indices], surface_moment[indices]
        else:
            _, velocity = bodies[mesh.beam.index]
            fraction, df = body_derivatives(mesh, velocity, flow, data['rho']); dm = np.zeros_like(df)
        source_transfer = getattr(net, 'steady_lifting_wrenches', None)
        if source_transfer is not None:
            if not mesh.beam.lifting:
                # Source balances transfer each complete section wrench
                # symmetrically for bodies as well as lifting surfaces.
                # Integrate the body quadrature and its moment about mesh.rm
                # before applying that same transfer. Generic motion weights
                # give different endpoint loads despite the same total wrench.
                positions = body_quadrature(mesh)[1]
                dm = cross(positions-mesh.rm[:, None, :], df).sum(axis=1)
                df = df.sum(axis=1)
            wrenches = source_transfer(mesh, df, dm)
        else:
            wrenches = transfer(motion, mesh.beam.index, fraction, df, dm)
        for end, (ids, nf, nm) in enumerate(wrenches):
            np.add.at(force, ids, nf); np.add.at(moment, ids, nm); end_moment[sl, end] += nm
    for index, (position, velocity, area) in enumerate(data['points']):
        dv = flow.velocity(('point', index), position[None, :])[0]
        df = .5*data['rho']*area*norm_product(velocity, dv)
        node = net.node(*net.weights[index][:2]); force[node] += df; moment[node] += cross(position-r[node], df)
    for shoulder in data['shoulders']:
        position, span, velocity = [np.asarray(shoulder[key]) for key in ['position', 'tangent', 'incident_velocity']]
        dv = flow.velocity(('shoulder', shoulder['beam'], shoulder['t']), position[None, :])[0]
        along = velocity@span; dalong = span@dv; normal = velocity-along*span
        df = data['rho']*shoulder['area_jump']*((dv-span[:, None]*dalong)*along+normal[:, None]*dalong)
        node = net.node(shoulder['beam'], shoulder['t']); force[node] += df; moment[node] += cross(position-r[node], df)
    for derivative, engine in zip(flow.engines, data['engines']):
        node = net.node(engine['beam'], engine['t'])
        force[node] += derivative.force
        moment[node] += derivative.moment+cross(engine['position']-r[node], derivative.force)
    result = np.zeros((net.size, count))
    start = 6*net.ne
    result[start:start+3*net.nn] = factor/net.F*force.reshape(-1, count)
    result[start+3*net.nn:start+6*net.nn] = factor/(net.F*net.L)*moment.reshape(-1, count)
    constraint_start = 6*(net.ne+net.nn)
    for joint in net.constraints:
        if joint['type'] != 3 or factor == 0: continue
        i, j, e, end, law = [joint[key] for key in ['a', 'b', 'element', 'end', 'law']]
        sign = -1 if end else 1
        offset = (motion.pb[e]-r[net.b[e]]) if end else (motion.pa[e]-r[net.a[e]])
        internal = (mechanics['M'][e]+sign*cross3(motion.pb[e]-motion.pa[e], mechanics['N'][e])/2
                    +cross3(offset, mechanics['N'][e])+sign*factor*mechanics['element_moments'][e, int(end)])
        axis = Q[i]@law.axis; mh = float(internal@axis)
        knots = law.curve[:-1, 0][np.diff(law.curve[:, 0]) == 0]
        if np.any(abs(knots-mh) <= 1e-8*max(1., abs(mh))):
            raise CirculationDerivativeUnavailable('Hinge moment is at a slope break.')
        # Current hinge charts are fixed in this circulation/field partial.
        # log(exp(-chart*axis)@Q[i].T@Q[j]) is therefore constant; only
        # -(law.angle(moment, factor)-chart)*axis varies with the end load.
        gradient = -law.axis*np.deg2rad(law.spline.evaluate(mh, derivative=1))
        dm = sign*factor*(axis@end_moment[e, int(end)])
        row = constraint_start+joint['sl'].start+3
        result[row:row+3] = gradient[:, None]*dm
    result[net.gamma_start:net.operating_start] = residual
    if net.operating.count:
        from .structured_static import load_kinematic_constraints
        if not load_kinematic_constraints(net):
            raise CirculationDerivativeUnavailable('Unsupported operating rows in circulation tangent.')
        total_force=force.sum(axis=0)
        total_moment=(moment+cross(r-net.model.reference[1],force)).sum(axis=0)
        for i,c in enumerate(net.operating.constraints):
            # Flight path has no circulation dependence at fixed condition.
            # Its angle/control/attitude columns remain complete residual probes.
            if c.quantity=='flight_path':continue
            value,scale=(total_force,net.F) if c.quantity.startswith('force.') else (total_moment,net.F*net.L)
            result[net.operating_start+i]=value['xyz'.index(c.quantity[-1])]/scale
    if not np.all(np.isfinite(result)):
        raise CirculationDerivativeUnavailable('Nonfinite direct circulation derivative.')
    return result
