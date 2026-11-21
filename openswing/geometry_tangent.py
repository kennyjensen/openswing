"""Full geometry derivatives split into local and induced-field contributions.

The local derivative holds induced fields fixed ONLY while taking that partial.
The second partial restores every moving vortex, volume and jet contribution.
This decomposition must never be used without both terms in a physical tangent.
"""
import numpy as np
from scipy.sparse import csc_matrix, hstack
from .aero import AnalysisError, _stall_leakage
from .factored_influence import FactoredInfluence
from .atmosphere import operating_air
from .ground import GroundPlane
from .gust import gust_field
from .local_motion import NetworkMotion, checked_rotation_arc
from .frozen_influence import lifting_geometry
from .volume import VolumeField, body_quadrature
from .body_shoulders import body_shoulders
from .propulsion import engine_load, jet_velocity, jet_profile
from .vector_ops import cross3
from .circulation_tangent import EngineDerivative, flow_load_columns, CirculationDerivativeUnavailable
from .structured_static import (IterationFields, StructuredTangentUnavailable,
    load_kinematic_constraints, structural_column_rows, coloring, frame_load_pattern)


class GeometryDerivativeUnavailable(ValueError):
    """A decomposition outside the explicitly supported physical context."""


class GeometryDerivativeUnresolved(AnalysisError):
    """A moving-field derivative failed its numerical refinement check."""


def refined_field_column(evaluate,h,values,speed,*,tolerance=2e-8,max_refinements=6):
    """Resolve a field column before sharing it between A and output recovery.

    The existing second/fourth-order difference is a cheap trigger. Triggered
    columns require agreement of finer fourth-order or successive Richardson
    estimates. Velocity columns scale with airspeed, circulation residuals are
    dimensionless. All entries survive, including small and zero derivatives.
    Allow six bounded refinements for narrow fields that reach the convergent
    regime late; the accuracy tests and unresolved-derivative failure remain
    unchanged. Already resolved columns incur no additional evaluations.
    """
    def fourth(samples,width):
        return {key:(8*(samples[0][key]-samples[1][key])-(samples[2][key]-samples[3][key]))/(12*width) for key in samples[0]}
    def error(a,b):
        return max((float(np.max(abs(a[key]-b[key])/((1. if key=='circulation_residual' else speed)+np.maximum(abs(a[key]),abs(b[key]))),initial=0.)) for key in a),default=0.)
    coarse=fourth(values,h)
    second={key:(values[0][key]-values[1][key])/(2*h) for key in coarse}
    indicator=error(second,coarse)
    if indicator<=tolerance:return coarse,dict(refinements=0,indicator=indicator,error_estimate=indicator,method='second/fourth indicator')
    previous=None;previous_change=None;last_error=indicator
    for level in range(1,max_refinements+1):
        h/=3
        fine=fourth([evaluate(multiplier*h) for multiplier in (1.,-1.,2.,-2.)],h)
        last_error=error(fine,coarse)
        if not np.isfinite(last_error):
            raise GeometryDerivativeUnresolved('Nonfinite moving-field derivative under step refinement.')
        if last_error<=tolerance:
            return fine,dict(refinements=level,indicator=indicator,error_estimate=last_error,method='fourth-order step agreement')
        # Verify contraction before using a truncation estimate. An observed
        # ratio of at least9 corresponds to order>=2 for this factor3 step.
        # Cap the assumed ratio at81 (fourth order), even if cancellation makes
        # it appear higher. Do not extrapolate into a roundoff-dominated trend.
        if previous_change is not None and last_error>0:
            contraction=previous_change/last_error
            if contraction>=9:
                estimate=last_error/(min(81.,contraction)-1.)
                if estimate<=tolerance:
                    return fine,dict(refinements=level,indicator=indicator,error_estimate=estimate,
                        observed_contraction=contraction,method='contracting fourth-order stencil')
        previous_change=last_error
        extrapolated={key:fine[key]+(fine[key]-coarse[key])/80 for key in fine}
        if previous is not None:
            last_error=error(extrapolated,previous)
            if last_error<=tolerance:
                return extrapolated,dict(refinements=level,indicator=indicator,error_estimate=last_error,method='Richardson step agreement')
        previous,coarse=extrapolated,fine
    raise GeometryDerivativeUnresolved(f'Moving-field derivative did not resolve under step refinement (scaled change {last_error:.3g}); inspect the geometry and difference step.')


class GeometryFields:
    """Only the nonlocal velocity fields; no structural or load recovery work.

    Each query uses the same physical positions, source kernels, exclusions,
    PG/image transforms and jet model as evaluate_aerodynamics. Engine inflow
    includes its local kinematics so the jet geometry derivative is complete.
    The engine query itself excludes local motion: its local load contribution
    is already present in the grouped residual partial.
    """
    def __init__(self, net, fields, *, direct_vortex=False, direct_volume=False, _packed_fields=False):
        self.packed_fields = _packed_fields
        self.net = net
        self.data = d = fields.circulation_aero
        if d is None or fields.circulation_mechanics is None:
            raise GeometryDerivativeUnavailable('Missing physical field capture.')
        self.condition = c = d['condition']
        self.direction = e = d['direction']
        wind = np.array([1., 0., 0.]) if c.freeze_influences else e
        air = operating_air(net.model, c)
        mach = air['ambient_mach'] if c.mach is None else float(c.mach)
        self.pg = np.eye(3)+(1/np.sqrt(1-mach**2)-1)*np.outer(wind, wind)
        self.wind, self.ground = wind, GroundPlane.from_condition(c)
        self.jet_direction = d['jet_direction']
        self.frozen = net.frozen_influences if c.freeze_influences else None
        if c.freeze_influences and self.frozen is None:
            raise GeometryDerivativeUnavailable('Missing configured frozen influence model.')
        self.gust = gust_field(c.gust)
        self.local_values = fields.circulation_mechanics['local_motion'].values
        self.axis = ('vortex', 'axis') in fields.values
        self.engine_nodes = [net.node(*row[2:4]) for row in net.engines]
        self.clips = tuple(v['power_clipped'] for v in d['engines'])
        self.evaluations = 0
        self.preparations = 0
        self.field_batches = 0
        self.field_batch_queries = 0
        self.field_batch_budget_fallbacks = 0
        self.direct_vortex = {} if direct_vortex else None
        self.direct_vortex_bytes = 0
        self.direct_vortex_fallbacks = {}
        self.vortex_sources = None
        self.direct_volume = {} if direct_volume else None
        self.direct_volume_bytes = 0
        self.direct_volume_fallbacks = {}
        self.volume_sources = None
        self.jet_regions = {}
        angles = []
        for mesh in net.meshes:
            if not mesh.beam.lifting: continue
            value = mesh.beam.value
            alpha = np.deg2rad(value('alpha', mesh.tm))
            slope = value('dCLda', mesh.tm)
            for k, setting in c.controls.items():
                alpha += setting*value(f'dCLdF{k}', mesh.tm)/slope
            angles.extend(alpha)
        self.sin_alpha, self.cos_alpha = np.sin(angles), np.cos(angles)

    def check_jet_regions(self, name, points, engines):
        # The disk switch and a torque-carrying centerline are nonsmooth.
        # There the composed finite stencil need not equal a load chain rule.
        # Preserve the caller's full-residual stencil instead of approximating
        # that jump by a smooth partial derivative.
        for i, engine in enumerate(engines):
            if not engine['jet_enabled'] or (engine['thrust'] == 0 and engine['torque'] == 0):
                continue
            relative = points-engine['position']
            downstream = relative@self.jet_direction
            radial = relative-downstream[:, None]*self.jet_direction
            distance = np.linalg.norm(radial, axis=-1)
            outer = jet_profile(engine, downstream, self.data['rho'])[1]
            active = (downstream > 0) & (distance < outer)
            key = (name, i)
            if key not in self.jet_regions:
                self.jet_regions[key] = (active.copy(), radial.copy())
            base_active, base_radial = self.jet_regions[key]
            crosses_axis = engine['torque'] != 0 and np.any(
                active & base_active & (np.einsum('ij,ij->i', radial, base_radial) <= 0))
            if np.any(active != base_active) or crosses_axis:
                raise GeometryDerivativeUnavailable('Moving geometry crosses a powered jet boundary or swirl axis; use full residual stencils.')

    def __call__(self, x):
        return self.evaluate(self.prepare(x))

    def prepare(self, x):
        """Local geometric inputs, before any nonlocal field or jet evaluation."""
        self.preparations += 1
        n, d, c, e = self.net, self.data, self.condition, self.direction
        r, q, *_ = n.unpack(x)
        meshes = n.deformed_meshes(r, q, n.geometry(r, q))
        points = n.point_positions(r, q)
        p = lifting_geometry(meshes, self.wind, _material=n.tangent_influences)
        frozen = self.frozen; ig = frozen.geometry if frozen else p
        volume = None if frozen else VolumeField(n.model, meshes, e, self.pg, points, self.ground)
        cores = np.maximum(c.wake_core_ratio*ig['chord'], ig['ds'])
        engines_at = np.array([r[i]+q[i]@(row[4:7]-n.rj[i])
            for row, i in zip(n.engines, self.engine_nodes)]).reshape(-1, 3)
        queries = {}
        # name -> physical receiver, reference receiver, physical beam, exclusions, bound mask
        for key in ['cp', 'hv']+(['axis'] if self.axis else []):
            point_key = 'rm' if key == 'axis' else key
            queries[key] = (p[point_key], ig[point_key], p['physical'], {},
                None if key == 'cp' else np.eye(len(p['chord']), dtype=bool))
        queries['engine'] = (engines_at, np.array([row[4:7] for row in n.engines]).reshape(-1, 3), None, {}, None)
        for mesh in meshes:
            if mesh.beam.lifting: continue
            locations = body_quadrature(mesh)[1].reshape(-1, 3)
            reference = frozen.body_points[mesh.beam.index] if frozen else locations
            physical = mesh.beam.physical_index
            queries['body', mesh.beam.index] = (locations, reference, np.full(len(locations), physical), {'exclude_body':physical}, None)
            for shoulder in (body_shoulders(mesh) if frozen else volume.body_shoulders[mesh.beam.index]):
                location = shoulder['position']
                reference = (next(s['position'] for s in frozen.volume_field.body_shoulders[mesh.beam.index]
                    if s['t'] == shoulder['t']) if frozen else location)
                queries['shoulder', mesh.beam.index, shoulder['t']] = (location[None, :], reference[None, :],
                    np.array([physical]), {'exclude_body':physical}, None)
        for i, (row, location) in enumerate(zip(n.weights, points)):
            queries['point', i] = (np.asarray(location)[None, :], np.asarray(row[2:5])[None, :], None, {'exclude_point':i}, None)

        frames = (np.concatenate([mesh.frames for mesh in meshes if mesh.beam.lifting])
            if len(p['chord']) else np.empty((0, 3, 3)))
        return dict(r=r, q=q, p=p, volume=volume, cores=cores, engines_at=engines_at,
                    queries=queries, frames=frames)

    def evaluate_many(self, geometries):
        """Reuse matrix slices across original samples; keep all field physics.

        Only queries with both shared maps participate. Other queries, frozen
        influences, and storage-limited contexts keep individual evaluation.
        """
        if (len(geometries)<2 or self.frozen or self.vortex_sources is None
                or self.volume_sources is None or self.direct_vortex is None or self.direct_volume is None):
            return [self.evaluate(g) for g in geometries]
        pairs={name:(v,self.direct_volume.get(name)) for name,v in self.direct_vortex.items()
               if v is not None and v._source is self.vortex_sources
               and self.direct_volume.get(name) is not None
               and self.direct_volume[name]._source is self.volume_sources}
        if not pairs:return [self.evaluate(g) for g in geometries]
        # Account conservatively for one query's matrix slices/work arrays,
        # all owned source changes and the retained per-sample field packets.
        maps=[v for pair in pairs.values() for v in pair]
        working=(3 if self.packed_fields else 2)*max(v.bytes for v in maps)+len(geometries)*3*(
            sum(v.base.nbytes for v in maps)+self.vortex_sources.bytes+self.volume_sources.bytes)
        if working+self.direct_vortex_bytes+self.direct_volume_bytes>128*1024**2:
            self.field_batch_budget_fallbacks+=1
            return [self.evaluate(g) for g in geometries]
        from .vortex_tangent import VortexDerivativeUnavailable
        from .volume_tangent import VolumeDerivativeUnavailable
        packets=[{} for _ in geometries]
        try:
            vortex_changes=[self.vortex_sources.difference(g['p']['a'],g['p']['b'],g['cores'],g['p']['physical']) for g in geometries]
            volume_changes=[self.volume_sources.difference(g['volume']) for g in geometries]
            for name,(vortex,volume) in pairs.items():
                queries=[g['queries'][name] for g in geometries]
                circulation=vortex.values_shared([q[0] for q in queries],vortex_changes,[q[2] for q in queries],_packed=self.packed_fields)
                velocity=volume.values_shared([g['volume'] for g in geometries],[q[0] for q in queries],volume_changes,_packed=self.packed_fields)
                for packet,c,v in zip(packets,circulation,velocity):packet[name]=(c,v)
        except (VortexDerivativeUnavailable,VolumeDerivativeUnavailable) as exc:
            raise GeometryDerivativeUnavailable(str(exc)) from exc
        self.field_batches+=1;self.field_batch_queries+=len(pairs)
        return [self.evaluate(g,_induced=p) for g,p in zip(geometries,packets)]

    def evaluate(self, geometry, *, _induced=None):
        """Evaluate every original physical field at one stencil's geometry."""
        self.evaluations += 1
        n, d, c, e = self.net, self.data, self.condition, self.direction
        r, q, p, volume, cores, engines_at, queries, frames = [geometry[key] for key in
            ('r', 'q', 'p', 'volume', 'cores', 'engines_at', 'queries', 'frames')]
        frozen = self.frozen
        local_values = tuple(np.asarray(v,dtype=float) for v in self.local_values)
        # Preserve the exact positive-zero shortcut and all moving/invalid paths.
        stationary = all(v.shape == (n.nn,3) and not np.any(v.view(np.uint64)) for v in local_values)
        local = None if stationary else NetworkMotion(n, r, q, *local_values)

        parts = {}
        volume_change = None
        vortex_change = None
        def induced(name):
            nonlocal volume_change, vortex_change
            if _induced is not None and name in _induced:
                circulation,velocity=_induced[name]
                if name in ('engine','cp','hv'):parts[name]=(None,velocity,circulation)
                return circulation+c.speed*velocity
            locations, reference, physical, exclusions, bound = queries[name]
            circulation = None
            if not len(p['chord']):
                vortex = None
                circulation = np.zeros((len(locations), 3))
            elif frozen:
                vortex = frozen.factored_vortex(reference, physical, exclude_bound=bound)
            else:
                core = None
                def current_core():
                    return cores[None, :] if physical is None else np.where(
                        np.asarray(physical)[:, None] == p['physical'][None, :], 0., cores[None, :])
                if self.direct_vortex is not None:
                    from .vortex_tangent import VortexFieldTangent, VortexSourceTangent, VortexDerivativeUnavailable
                    if name not in self.direct_vortex:
                        source = self.vortex_sources
                        remaining = 128*1024**2-self.direct_vortex_bytes-self.direct_volume_bytes
                        if source is None:
                            try:source = VortexSourceTangent(p['a'], p['b'], cores, p['physical'], limit=remaining)
                            except VortexDerivativeUnavailable:pass
                        source_bytes = source.bytes if source is not None and self.vortex_sources is None else 0
                        core = current_core()
                        try:
                            tangent = VortexFieldTangent(locations, p['a'], p['b'], e, self.pg,
                                core, d['gamma'], self.ground, exclude_bound=bound,
                                single_dot=isinstance(name, tuple) and name[0] in ('point', 'shoulder'),
                                limit=remaining-source_bytes, _source=source, _physical=physical)
                        except VortexDerivativeUnavailable as exc:
                            # The unperturbed call fixes this decision for the
                            # entire stencil. Keep exact physical evaluation
                            # for this query while retaining other query maps.
                            tangent = None
                            self.direct_vortex_fallbacks[str(name)] = str(exc)
                        self.direct_vortex[name] = tangent
                        if tangent is not None:
                            self.direct_vortex_bytes += tangent.bytes
                            if source_bytes:
                                self.vortex_sources = source
                                self.direct_vortex_bytes += source_bytes
                    tangent = self.direct_vortex[name]
                    if tangent is not None:
                        try:
                            if tangent._source is None:
                                circulation = tangent.value(locations, p['a'], p['b'], current_core() if core is None else core)
                            else:
                                if vortex_change is None:
                                    vortex_change = tangent._source.difference(p['a'], p['b'], cores, p['physical'])
                                circulation = tangent.value_shared(locations, vortex_change, physical)
                        except VortexDerivativeUnavailable as exc:
                            raise GeometryDerivativeUnavailable(str(exc)) from exc
                        vortex = None
                if circulation is None:
                    if core is None:core = current_core()
                    if n.tangent_influences is not None:
                        vortex = n.tangent_influences.factored_vortex(name, locations, p['a'], p['b'], e, self.pg, core, self.ground, bound)
                    else:
                        vortex = FactoredInfluence(locations, p['a'], p['b'],
                            e, self.pg, core, self.ground, exclude_bound=bound)
            velocity = None
            if not frozen and self.direct_volume is not None:
                from .volume_tangent import VolumeFieldTangent, VolumeSourceTangent, VolumeDerivativeUnavailable
                if name not in self.direct_volume:
                    source = self.volume_sources
                    remaining = 128*1024**2-self.direct_vortex_bytes-self.direct_volume_bytes
                    if source is None:
                        try:source = VolumeSourceTangent(volume, limit=remaining)
                        except VolumeDerivativeUnavailable:pass
                    source_bytes = source.bytes if source is not None and self.volume_sources is None else 0
                    try:
                        tangent = VolumeFieldTangent(volume, locations, **exclusions, _source=source,
                            limit=remaining-source_bytes)
                    except VolumeDerivativeUnavailable as exc:
                        tangent = None
                        self.direct_volume_fallbacks[str(name)] = str(exc)
                    self.direct_volume[name] = tangent
                    if tangent is not None:
                        self.direct_volume_bytes += tangent.bytes
                        if source_bytes:
                            self.volume_sources = source
                            self.direct_volume_bytes += source_bytes
                tangent = self.direct_volume[name]
                if tangent is not None:
                    try:
                        if tangent._source is not None and volume_change is None:
                            volume_change = tangent._source.difference(volume)
                        velocity = tangent.value(volume, locations, _change=volume_change if tangent._source is not None else None)
                    except VolumeDerivativeUnavailable as exc:
                        raise GeometryDerivativeUnavailable(str(exc)) from exc
            if velocity is None:
                velocity = (frozen.volume(reference, **exclusions) if frozen else
                    volume.velocity(locations, _tangent=n.tangent_influences, _cache_name=name, **exclusions))
            if circulation is None:
                circulation = vortex.apply(d['gamma'])
            if name in ('engine', 'cp', 'hv'): parts[name] = (vortex, velocity, circulation)
            return circulation+c.speed*velocity

        fields = {'engine':induced('engine')}
        velocity = c.speed*e-cross3(np.asarray(c.rates), engines_at-n.model.reference[3])
        velocity += self.gust.body_velocity(engines_at, c)
        velocity += c.speed*parts['engine'][1]
        rates = np.broadcast_to(np.asarray(c.rates), engines_at.shape).copy()
        for i, position in enumerate(engines_at):
            if local is None:
                velocity[i] -= 0.; rates[i] += 0.
            else:
                mount = local.point('engine', i)
                velocity[i] -= mount.velocity_at(position); rates[i] += mount.rates
        velocity += parts['engine'][2]
        engines = [engine_load(row, c.powers.get(int(row[0]), 0.), d['rho'], position, v, rates[k], q[self.engine_nodes[k]])
            for k, (row, position, v) in enumerate(zip(n.engines, engines_at, velocity))]
        if tuple(engine['power_clipped'] for engine in engines) != self.clips:
            raise AnalysisError('Geometry field stencil crosses an engine power-clipping transition.')
        jets = {}
        for name, query in queries.items():
            if name == 'engine': continue
            self.check_jet_regions(name, query[0], engines)
            jet = jet_velocity(query[0], engines, self.jet_direction, d['rho'])
            fields[name] = induced(name)+jet
            if name in ('cp', 'hv'): jets[name] = jet
        # Retain the composed circulation stencil, including the same scalar
        # normal projection as the complete aerodynamic residual. A stencil of this
        # product differs from a sum of partial stencils by O(h^4), which is
        # measurable near closely spaced lifting-line receivers. These rows
        # need no structural/load recovery and are cheap to evaluate here.
        normal = self.sin_alpha[:, None]*frames[..., 0]+self.cos_alpha[:, None]*frames[..., 2]
        if local is None:
            # Original surface sampling checks the elastic arc on lifting
            # beams. Keep that guard, without constructing unused rotations,
            # zero rates/accelerations or offset-motion arrays.
            for mesh in n.meshes:
                if not mesh.beam.lifting: continue
                sl = n.beam_elements[mesh.beam.index]
                qa,qb = q[n.a[sl]],q[n.b[sl]]
                n.local_maps(('stationary_surface_arc',mesh.beam.index),(qa,qb),
                    lambda rows:(checked_rotation_arc(qa[rows],qb[rows]),))
            surface = None
        else:
            surface = local.surface()
        free = {}
        for name in ('cp', 'hv'):
            free[name] = c.speed*e-cross3(np.asarray(c.rates), p[name]-n.model.reference[3])
            free[name] += self.gust.body_velocity(p[name], c)
            free[name] -= 0. if surface is None else surface.velocity_at(p[name])
            free[name] += c.speed*parts[name][1]
        cp_operator = parts['cp'][0]
        # Full physical samples must project the coefficients before applying
        # circulation, just as evaluate_aerodynamics does. Projecting the
        # already-contracted vector field changes roundoff that is amplified
        # by the geometry difference step. Retained first-order field maps
        # have no physical operator at the perturbed geometry.
        circulation_normal = (np.sum(parts['cp'][2]*normal, axis=-1) if cp_operator is None
                              else cp_operator.projected(normal).apply(d['gamma']))
        rhs = -np.sum(free['cp']*normal, axis=-1)
        v = free['hv']+parts['hv'][2]+jets['hv']
        span = frames[..., 1]
        vp = v-np.sum(v*span, axis=-1)[:, None]*span
        speed = np.maximum(np.linalg.norm(vp, axis=-1), c.speed*1e-12)
        cl = 2*d['gamma']/(p['chord']*speed)
        stall, _ = _stall_leakage(cl, d['p']['clmin'], d['p']['clmax'], c.stall_width)
        leakage = speed/d['p']['slope']*c.stall_factor*stall if c.stall else 0.
        residual = (circulation_normal-rhs+np.sum(jets['cp']*normal, axis=-1)
            -leakage-2/np.pi*d['lag_rate']/speed)/c.speed
        fields['circulation_residual'] = d['basis'].test@residual if d['basis'].modes else residual
        return fields


class FieldDerivative:
    def __init__(self, data, gradients):
        count = gradients['engine'].shape[-1]
        self.sample = np.zeros((len(data['gamma']), count))
        self.gradients = gradients
        self.engines = [EngineDerivative(data, i, gradients['engine'][i]) for i in range(len(data['engines']))]

    def velocity(self, name, points):
        return self.gradients[name]


def geometry_columns(net, residual, state_at, scales, step=1e-5, *, factor=1., progress=None, difference_order=4, _field_columns=None, _direct_vortex=False, _direct_volume=False, _nodewise_state=False, _packed_fields=True, _captured_fields=None, _direct_geometry=False, _rotation_chart='absolute', _strut_tangent=None, _direct_structural=False, _structural_system=None, _column_indices=None):
    """Geometry columns of a physical residual in the caller's state chart.

    residual(increment) evaluates the COMPLETE equations and branch guards;
    state_at(increment) returns the same network coordinates without recovery.
    The caller controls state-chart/condition consistency. Only geometry entries
    are perturbed here. Other columns remain the caller's responsibility.
    An optional ordered, unique subset returns only those columns, while each
    field derivative retains every source/receiver and the complete residual.
    This permits checkpointed assembly without changing the default operator.
    """
    if difference_order not in (1, 4):
        raise ValueError('Geometry difference order must be 1 or 4.')
    if net.iteration_fields is not None or not load_kinematic_constraints(net):
        raise GeometryDerivativeUnavailable('Geometry decomposition requires load/flight-path constraints and unowned fields.')
    count = 6*net.nn; zero = np.zeros(len(scales)); rows = structural_column_rows(net)[:count]
    selected_columns = list(range(count)) if _column_indices is None else list(_column_indices)
    if (not selected_columns or any(not isinstance(j, (int, np.integer)) or isinstance(j, (bool, np.bool_))
                                   or j < 0 or j >= count for j in selected_columns)
            or len(set(selected_columns)) != len(selected_columns)):
        raise ValueError('Geometry column indices must be nonempty, unique integers within the nodal coordinates.')
    selected_set = set(selected_columns)
    original_groups = len(coloring(rows))
    # The complete flow-equation derivative is evaluated separately below and
    # replaces these rows, including local section geometry and moving fields.
    # Its Fourier test rows span a beam, but do not couple the remaining local
    # structural/load probes. Exclude only these subsequently replaced rows
    # from their coloring; keep every mechanical and joint dependency.
    rows = [r[(r < net.gamma_start) | (r >= net.operating_start)] for r in rows]
    load_constraints=[c for c in net.operating.constraints if c.quantity!='flight_path']
    load_rows=np.array([net.operating_start+i for i,c in enumerate(net.operating.constraints)
                       if c.quantity!='flight_path'],dtype=int)
    nodes, components, load_scales = frame_load_pattern(net, rows, constraints=load_constraints)
    groups = coloring(rows); fields = IterationFields()
    fields.capture_circulation = True
    fields.capture_frame_loads = bool(net.operating.count)
    columns = [None]*count
    structural=None;structural_report=None;structural_fallback=None
    old_load_cache = net._tangent_loads
    # A frozen-field partial must never enter a cache of full physical loads.
    net._tangent_loads = None
    net.iteration_fields = fields; net.aero_key = None
    try:
        baseline = residual(zero)
        if net.condition is None:
            raise GeometryDerivativeUnavailable('Vacuum geometry decomposition is not enabled.')
        evaluator = GeometryFields(net, fields, direct_vortex=_direct_vortex, direct_volume=_direct_volume, _packed_fields=_packed_fields)
        base_loads = fields.frame_loads.copy() if fields.capture_frame_loads else None
        if _direct_structural:
            from .structural_geometry import geometry_columns as structural_columns, local_load_rows, StructuralGeometryUnavailable
            try:
                if any(np.any(value) for value in fields.circulation_mechanics['local_motion'].values):
                    raise StructuralGeometryUnavailable('Nonstationary elastic geometry requires rate derivatives.')
                structural,structural_report=structural_columns(net,state_at(zero),chart=_rotation_chart,
                    row_count=len(baseline),system=_structural_system)
            except StructuralGeometryUnavailable as exc:structural_fallback=str(exc)
            else:
                rows=local_load_rows(net);groups=coloring(rows)
                nodes,components,load_scales=frame_load_pattern(net,rows,constraints=load_constraints)
                fields.omit_stationary_mechanics=True
        fields.phase = 'geometry'
        if structural is not None and difference_order==1:
            # Use the same physical local-load baseline as the forward probes;
            # subtracting large internal forces from a balanced residual loses digits.
            baseline=residual(zero)
        if _strut_tangent is not None:
            if (difference_order!=4 or factor!=1. or _rotation_chart!='spatial'
                    or _strut_tangent.owner.network is not net or not _strut_tangent.matches(_strut_tangent.owner)):
                raise GeometryDerivativeUnavailable('Strut tangent does not match this physical geometry partial.')
            fields.omit_strut_loads=True
        if _column_indices is not None:
            groups = [np.array([j for j in group if j in selected_set], dtype=int) for group in groups]
            groups = [group for group in groups if len(group)]
        for group in groups:
            h = step*np.asarray(scales)[group]
            values, loads = [], []
            for multiplier in ((1.,) if difference_order == 1 else (1., -1., 2., -2.)):
                delta = zero.copy(); delta[group] = multiplier*h
                values.append(residual(delta))
                if fields.capture_frame_loads: loads.append(fields.frame_loads.copy())
            diff = values[0]-baseline if difference_order == 1 else 8*(values[0]-values[1])-(values[2]-values[3])
            load_diff = None if not loads else (loads[0]-base_loads if difference_order == 1 else 8*(loads[0]-loads[1])-(loads[2]-loads[3]))
            denominator = 1 if difference_order == 1 else 12
            for j, hj in zip(group, h):
                value = np.zeros(len(baseline)); value[rows[j]] = diff[rows[j]]/(denominator*hj)
                if load_diff is not None:
                    wrench = load_diff[nodes[j]].sum(axis=0)
                    value[load_rows] = wrench[components]/load_scales/(denominator*hj)
                columns[j] = csc_matrix(value[:, None])
    except (StructuredTangentUnavailable, CirculationDerivativeUnavailable) as exc:
        raise GeometryDerivativeUnavailable(str(exc)) from exc
    finally:
        fields.omit_stationary_mechanics=False
        net.iteration_fields = None; net.aero_key = None
        net._tangent_loads = old_load_cache
    # Reevaluate moving fields without any lagged Newton context. Chunk storage
    # bounds temporary field/load Jacobians independently of model column count.
    from .geometry_stencil import GeometryStencil, GeometryStencilUnavailable
    from .geometry_partials import GeometryPartialsUnavailable
    stencil = None;stencil_fallback = None
    direct_geometry=None;direct_geometry_fallback=None
    multipliers = (1.,) if difference_order == 1 else (1., -1., 2., -2.)
    try:
        base_geometry = evaluator.prepare(state_at(zero))
        base_fields = evaluator.evaluate(base_geometry);refinements=[]
        if _direct_geometry:
            from .geometry_field_partials import GeometryFieldPartials
            try:
                direct_geometry=GeometryFieldPartials(evaluator,state_at(zero),chart=_rotation_chart,
                    limit=max(0,64*1024**2-getattr(net.tangent_influences,'bytes',0)))
                direct_geometry.geometry.budget(min(16,count))
                direct_geometry.columns([0])
            except (GeometryPartialsUnavailable,CirculationDerivativeUnavailable,GeometryDerivativeUnavailable) as exc:
                direct_geometry=None;direct_geometry_fallback=str(exc)
        if _nodewise_state and direct_geometry is None:
            try:stencil = GeometryStencil(evaluator,base_geometry,len(multipliers))
            except GeometryStencilUnavailable as exc:stencil_fallback = str(exc)
            if stencil is not None:stencil.build(state_at,zero,scales,step,multipliers)
        for start in range(0, len(selected_columns), 16):
            selected = selected_columns[start:start+16]; gradients = None
            if direct_geometry is not None:
                gradients=direct_geometry.columns(selected)
            else:
                for offset, j in enumerate(selected):
                    h = step*scales[j]; values = []
                    if stencil is not None and len(multipliers)>1:
                        values=evaluator.evaluate_many([stencil.sample(j,phase) for phase in range(len(multipliers))])
                    else:
                        for phase,multiplier in enumerate(multipliers):
                            delta = zero.copy(); delta[j] = multiplier*h
                            values.append(evaluator(state_at(delta)) if stencil is None else evaluator.evaluate(stencil.sample(j,phase)))
                    if gradients is None:
                        gradients = {key:np.zeros(value.shape+(len(selected),)) for key, value in values[0].items()}
                    if difference_order==4:
                        def evaluate(increment):
                            delta=zero.copy();delta[j]=increment
                            return evaluator(state_at(delta))
                        derivative,report=refined_field_column(evaluate,h,values,evaluator.condition.speed)
                        if report['refinements']:refinements.append(dict(column=j,**report))
                    else:derivative={key:(values[0][key]-base_fields[key])/h for key in base_fields}
                    for key,gradient in gradients.items():gradient[...,offset]=derivative[key]
            if _field_columns is not None:_field_columns(selected,gradients)
            direct = flow_load_columns(net, fields, FieldDerivative(fields.circulation_aero, gradients), factor)
            for offset, j in enumerate(selected):
                value = columns[j].toarray().ravel(); value[:net.size] += direct[:, offset]
                if _strut_tangent is not None:
                    value[:net.size]+=_strut_tangent.nodal_struts[:,j].toarray().ravel()
                value[net.gamma_start:net.operating_start] = gradients['circulation_residual'][:, offset]
                columns[j] = csc_matrix(value[:, None])
            if progress is not None: progress(min(start+16, len(selected_columns)), len(selected_columns))
    except (CirculationDerivativeUnavailable,GeometryStencilUnavailable,GeometryPartialsUnavailable) as exc:
        raise GeometryDerivativeUnavailable(str(exc)) from exc
    finally:
        if stencil is not None:stencil.close()
        net.aero_key = None
    result = hstack([columns[j] for j in selected_columns], format='csc')
    if structural is not None:result=result+structural[:,selected_columns]
    if not np.all(np.isfinite(result.data)):
        raise GeometryDerivativeUnavailable('Nonfinite complete geometry derivative.')
    if _captured_fields is not None:
        # Share this invocation's physical base capture with the enclosing
        # Newton assembly. Only publish after successful assembly/restoration;
        # the caller must not retain it across states or derivative contexts.
        _captured_fields['fields'] = fields
    return result, dict(method='grouped local residual plus full moving induced-field chain rule',
        geometry_columns=len(selected_columns), selected_column_indices=None if _column_indices is None else selected_columns,
        local_groups=len(groups), original_local_groups=original_groups,
        structural_geometry=structural_report,structural_fallback=structural_fallback, field_evaluations=evaluator.evaluations,
        direct_geometry_columns=len(selected_columns) if direct_geometry is not None else 0,
        local_geometry_matrix=None if direct_geometry is None or direct_geometry.local_matrix is None else direct_geometry.local_matrix.report(),
        local_geometry_matrix_fallback=None if direct_geometry is None else direct_geometry.local_matrix_fallback,
        retained_strut_columns=0 if _strut_tangent is None else int(np.count_nonzero(np.diff(_strut_tangent.nodal_struts.indptr))),
        direct_geometry_fallback=direct_geometry_fallback,
        geometry_preparations=evaluator.preparations,
        geometry_groups=0 if stencil is None else len(stencil.groups),
        geometry_stencil_bytes=0 if stencil is None else stencil.bytes,
        geometry_stencil_fallback=stencil_fallback,
        field_batches=evaluator.field_batches,field_batch_queries=evaluator.field_batch_queries,
        field_products="packed original geometry samples" if evaluator.packed_fields else "original separate source contractions",
        field_batch_budget_fallbacks=evaluator.field_batch_budget_fallbacks,
        difference_order=difference_order, difference_step=step,
        direct_vortex_queries=0 if evaluator.direct_vortex is None else sum(v is not None for v in evaluator.direct_vortex.values()),
        direct_vortex_bytes=evaluator.direct_vortex_bytes,
        direct_vortex_fallbacks=evaluator.direct_vortex_fallbacks,
        direct_volume_queries=0 if evaluator.direct_volume is None else sum(v is not None for v in evaluator.direct_volume.values()),
        direct_volume_bytes=evaluator.direct_volume_bytes,
        direct_volume_fallbacks=evaluator.direct_volume_fallbacks,
        field_refinement=dict(tolerance=2e-8,columns=len(refinements),extra_evaluations=sum(4*r['refinements'] for r in refinements),details=refinements))
