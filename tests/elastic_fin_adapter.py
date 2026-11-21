"""Portable native adapter for the accepted loaded elastic boom-fin regression.

The equations, clamp/offset joint, independently manufactured dead loads and
physical response mapping are retained from the accepted 2026-10-25 study.
All quantities use its clamp gauge and original ft/lb/s units unless labeled
physical. Importing this helper does not construct a model or evaluate physics.
"""
from copy import deepcopy
import math


def explicit_mesh(fixture, subdivisions):
    """Bisect original material intervals; retain the shared fin root once."""
    if type(subdivisions) is not int or subdivisions not in (1, 2, 4):
        raise ValueError('Only the declared 1/2/4 subdivisions are supported.')
    branches = fixture['branches']
    original = {
        3: sorted(set(branches['lower']['stations'] + branches['upper']['stations'])),
        4: branches['boom']['stations'],
    }
    beams = {}
    for beam, stations in original.items():
        nodes = [a + (b-a)*j/subdivisions
                 for a, b in zip(stations[:-1], stations[1:])
                 for j in range(subdivisions)] + [stations[-1]]
        beams[str(beam)] = {'nodes': nodes}
    return {'default': 16, 'beams': beams}


def frozen_loads(fixture, mesh, independent_counterloads):
    """Original spatial dead wrench minus independent base aero, exactly once.

    Counterload records: {beam:3, t, force:[3], moment:[3]}, one per fin node.
    moment is the nodal intrinsic couple from the independent transpose map,
    NOT a moment about the global origin. Values are positive base aero loads;
    this function subtracts them. Counterloads must already include all base
    aerodynamic families. No native evaluation occurs in this function.
    """
    def vector(value):
        if len(value) != 3 or not all(math.isfinite(float(v)) for v in value):
            raise ValueError('A load must contain three finite components.')
        return [float(v) for v in value]

    rows = {}
    for name, branch in fixture['branches'].items():
        for t, force, moment in zip(branch['stations'], branch['dead_force'], branch['dead_moment']):
            key = (int(branch['beam']), float(t))
            if key == (4, 0.):
                if any(force) or any(moment):
                    raise ValueError('Cut dead load must stay zero; clamp carries its reaction.')
                continue
            if key == (3, 0.):
                if any(force) or any(moment):
                    raise ValueError('Branch root arrays must exclude the shared root dead wrench.')
                continue
            if key in rows:
                raise ValueError('Duplicate original dead load.')
            rows[key] = [vector(force), vector(moment)]
    rows[3, 0.] = [vector(fixture['joint_dead_force_fin_root']),
                    vector(fixture['joint_dead_moment_fin_root'])]
    expected = {(3, float(t)) for t in mesh['beams']['3']['nodes']}
    seen = set()
    for row in independent_counterloads:
        key = (int(row['beam']), float(row['t']))
        if key not in expected or key in seen:
            raise ValueError('Counterloads require each declared fin node exactly once.')
        seen.add(key)
        old = rows.setdefault(key, [[0., 0., 0.], [0., 0., 0.]])
        for i, name in enumerate(('force', 'moment')):
            old[i] = [a-b for a, b in zip(old[i], vector(row[name]))]
    if seen != expected:
        raise ValueError('Missing independently manufactured fin counterloads.')
    return [dict(beam=b, t=t, force=f, moment=m)
            for (b, t), (f, m) in sorted(rows.items())]


def build_network(fixture, subdivisions, independent_counterloads, flight, *, residual_observer=None):
    """Construct only; native residual/correction/linearization are separate.

    flight requires speed, density, mach, physical_wind, aero_lag, stall,
    wake_core_ratio. The runner must freeze these settings explicitly.
    Radius is removed only from boom4; model.dumps() records that edit.
    """
    import numpy as np
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition
    from openswing.network import StaticNetwork

    model = parse_asw(fixture['reduced_source'])
    beams = {b.index: b for b in model.beams}
    if set(beams) != {3, 4} or not beams[3].lifting or beams[4].lifting:
        raise ValueError('Expected the literal fin3 and nonlifting boom4.')
    if beams[3].domain != (-3.5, 5.) or beams[4].domain != (0., 20.):
        raise ValueError('Unexpected literal domain; do not mirror or shorten the fin.')
    if model.diagnostics or any(model.records.get(k) for k in ('weight', 'engine', 'strut', 'jangle')):
        raise ValueError('Unexpected extra physics in this isolated component.')
    if (not np.array_equal(np.asarray(model.records.get('ground', [])), [[4., 0., 0.]])
            or not np.array_equal(np.asarray(model.records.get('joint', [])), [[4., 3., 20., 0., 0.]])):
        raise ValueError('The literal clamp and rigid offset joint must be retained.')
    before = deepcopy(beams[4].distributions)
    if beams[4].distributions.pop('radius', None) is None:
        raise ValueError('Expected an explicit original boom radius to remove.')
    for key, value in before.items():
        if key != 'radius':
            current = beams[4].distributions[key]
            if not (np.array_equal(value.t, current.t) and np.array_equal(value.values, current.values)):
                raise ValueError('Radius amendment changed another distribution.')
    transform = np.asarray(fixture['gauge']['physical_to_gauge_rotation'], dtype=float)
    wind = np.asarray(flight['physical_wind'], dtype=float)
    if wind.shape != (3,) or not np.all(np.isfinite(wind)) or np.linalg.norm(wind) == 0:
        raise ValueError('physical_wind must be a finite nonzero direction.')
    wind = transform @ (wind / np.linalg.norm(wind))
    condition = FlightCondition(
        speed=float(flight['speed']), density=float(flight['density']), mach=float(flight['mach']),
        alpha=float(np.degrees(np.arctan2(wind[2], wind[0]))),
        beta=float(np.degrees(np.arcsin(-np.clip(wind[1], -1., 1.)))),
        rates=(0., 0., 0.), acceleration=(0., 0., 0.), angular_acceleration=(0., 0., 0.),
        controls={}, powers={}, ground_effect=0, freeze_influences=False,
        circulation_modes={3: 0}, aero_lag=flight['aero_lag'], stall=flight['stall'],
        wake_core_ratio=float(flight['wake_core_ratio']), gust=None, altitude_m=0.)
    mesh = explicit_mesh(fixture, subdivisions)
    loads = frozen_loads(fixture, mesh, independent_counterloads)

    class CountedNetwork(StaticNetwork):
        def residual(self, *args, **kwargs):
            if residual_observer is not None:
                residual_observer()
            return super().residual(*args, **kwargs)

    network = CountedNetwork(model, mesh, condition, [0., 0., 0.], loads)
    if network.operating.count or network.nc != 12 or network.hinges:
        raise ValueError('Expected only the six-row clamp and six-row rigid offset joint.')
    if not np.array_equal(network.offa, np.zeros_like(network.offa)) or not np.array_equal(network.offb, np.zeros_like(network.offb)):
        raise ValueError('Unexpected endpoint offsets; counterload map must be re-reviewed.')
    for beam, (stations, _) in network.station_nodes.items():
        if not np.array_equal(stations, mesh['beams'][str(beam)]['nodes']):
            raise ValueError('Native mandatory stations differ from the frozen independent mesh.')
    return network, dict(model_source=model.dumps(), mesh=mesh, loads=deepcopy(loads),
                         condition=condition, source_scope='boom radius only; fin properties literal')


def seed_packet(network, independent):
    """Map an independently evaluated continuum guess into current native scales.

    nodes: records beam,t,position,material_rotation (gauge spatial triad).
    elements: beam,t0,t1,force,moment (gauge N,M at the native element center).
    reactions: kind,force,moment, where both are the wrench ON the first node,
      and moment is about that node. Exactly one ground and one joint record.
    gamma: physical pointwise circulation in increasing fin station order;
    gamma_tm: independently calculated material receiver stations, checked in
    order against native stations at 2e-11 absolute + 2e-11 relative tolerance.
    Returns (raw_guess, portable_packet, mapping_diagnostics). No old normalized
    vector or native coordinates are supplied to the independent reference.
    """
    import numpy as np
    from openswing.geometry import surface_frame
    from openswing.local_motion import rotation_vector
    from openswing.equilibrium_state import capture

    n = network
    def finite(value, shape):
        out = np.asarray(value, dtype=float)
        if out.shape != shape or not np.all(np.isfinite(out)):
            raise ValueError('Independent seed shape/finiteness mismatch.')
        return out
    node_rows = {(int(v['beam']), float(v['t'])): v for v in independent['nodes']}
    element_rows = {(int(v['beam']), float(v['t0']), float(v['t1'])): v for v in independent['elements']}
    if len(node_rows) != n.nn or len(element_rows) != n.ne:
        raise ValueError('Independent seed must cover every native node/element exactly once.')
    x = np.zeros(n.size)
    kin = x[:6*n.nn].reshape(n.nn, 6)
    positions = np.empty((n.nn, 3))
    for mesh in n.meshes:
        ts, ids = n.station_nodes[mesh.beam.index]
        jig = surface_frame(mesh.beam, ts)
        for t, i, rj in zip(ts, ids, jig):
            row = node_rows[mesh.beam.index, float(t)]
            r = finite(row['position'], (3,)); material = finite(row['material_rotation'], (3, 3))
            if np.max(abs(material.T @ material - np.eye(3))) > 1e-10 or np.linalg.det(material) <= 0:
                raise ValueError('Independent material triad is not a proper rotation.')
            positions[i] = r
            kin[i, :3] = (r-n.rj[i])/n.L
            kin[i, 3:] = rotation_vector(material @ rj.T)
        block = x[6*n.nn:6*(n.nn+n.ne)].reshape(n.ne, 6)
        sl = n.beam_elements[mesh.beam.index]
        for j, a, b in zip(range(sl.start, sl.stop), mesh.t0, mesh.t1):
            row = element_rows[mesh.beam.index, float(a), float(b)]
            block[j, :3] = finite(row['force'], (3,))/n.F
            block[j, 3:] = finite(row['moment'], (3,))/(n.F*n.L)
    reactions = {v['kind']: v for v in independent['reactions']}
    if set(reactions) != {'ground', 'joint'} or len(independent['reactions']) != 2:
        raise ValueError('Independent seed requires both support wrench guesses.')
    raw = x[6*(n.nn+n.ne):n.gamma_start]
    for constraint in n.constraints:
        row = reactions[constraint['kind']]
        force = finite(row['force'], (3,)); moment = finite(row['moment'], (3,))
        if constraint['b'] is not None:
            moment = moment - np.cross(positions[constraint['b']]-positions[constraint['a']], force)
        raw[constraint['sl']] = np.r_[force/n.F, moment/(n.F*n.L)]
    receivers = np.concatenate([m.tm for m in n.meshes if m.beam.lifting])
    independent_receivers = finite(independent['gamma_tm'], receivers.shape)
    difference = abs(independent_receivers-receivers)
    tolerance = 2e-11+2e-11*abs(receivers)
    if (np.any(np.diff(independent_receivers) <= 0)
            or np.any(np.diff(receivers) <= 0)
            or np.any(difference > tolerance)):
        raise ValueError('Independent circulation receiver stations do not match native ordering.')
    mapping = dict(receiver_count=len(receivers), absolute_tolerance=2e-11,
                   relative_tolerance=2e-11, relative_reference='native material station',
                   maximum_absolute_difference=float(np.max(difference)),
                   maximum_tolerance_ratio=float(np.max(difference/tolerance)),
                   independently_calculated_coordinates_retained=True)
    x[n.gamma_start:n.operating_start] = n.circulation_basis.encode(
        finite(independent['gamma'], (n.ng,)))/n.gamma_scale
    return x, capture(n, x, include_launch=True), mapping


def correct_base(network, packet, *, tolerance, progress=None):
    """One native full equilibrium correction; caller saves/checks returned data."""
    from openswing.network import equilibrate
    from openswing.linear_dynamics import DynamicSystem
    value, steps = equilibrate(network, tolerance=tolerance, initial_state=packet, progress=progress)
    return DynamicSystem(network, value, 'fixed'), value, steps


def assemble(system, fixture, *, step, progress=None, output_fields=False):
    """One full A/M assembly, reusable at every frequency; inputs are separate."""
    from openswing.linear_dynamics import linearize
    A, M = linearize(system, step=step, progress=progress, sparse=True, _output_fields=output_fields)
    return A, M, dict(state=deepcopy(system.state_derivative_diagnostics),
                     mass=deepcopy(getattr(system, 'derivative_diagnostics', None)))


def input_rhs(system, fixture, *, step):
    """Native F3 fourth-order full-residual partial, then physical tip Mz.

    Returns the five original F3 residual packets and derivative metadata for
    the runner to save, plus the forcing callable needed for output recovery.
    F3 is per FILE FLAP SETTING, not per radian. There is no guessed sign or
    coefficient conversion. Both columns are frequency independent here.
    """
    import numpy as np
    from openswing.frequency_response import HarmonicInput, input_partials
    n = system.network
    channel = HarmonicInput(system, 'control.3', 0)
    packets = []
    original = system.residual
    prior_override = system.__dict__.get('residual')
    had_override = 'residual' in system.__dict__
    def record(*args, **kwargs):
        value = original(*args, **kwargs)
        packets.append(np.asarray(value).copy())
        return value
    system.residual = record
    before = n.nfev
    try:
        control, forcings, profiles = input_partials(
            system, [channel], 0., step, constant_inputs={},
            _field_tangent=getattr(system, '_output_field_tangent', None))
    finally:
        if had_override:
            system.residual = prior_override
        else:
            system.__dict__.pop('residual', None)
    if len(packets) != 5 or n.nfev-before != 5:
        raise ValueError('Expected one baseline and four fresh full native F3 probes.')
    B = np.zeros((system.size, 2), dtype=control.dtype)
    B[:, 0] = control[:, 0]
    tip = n.node(3, 5.)
    T = np.asarray(fixture['gauge']['physical_to_gauge_rotation'])
    B[6*n.ne+3*n.nn+3*tip:6*n.ne+3*n.nn+3*tip+3, 1] = T @ np.array([0., 0., 1.])/(n.F*n.L)
    metadata = dict(input=deepcopy(channel.report), profiles=deepcopy(profiles),
                    residual_calls=n.nfev-before, derivative_step=step,
                    packet_order=['base', '+h', '-h', '+2h', '-2h'],
                    h=step*channel.scale, columns=['control.3', 'upper_tip_physical_Mz'],
                    second_column='exact external nodal couple partial; original F*L normalization')
    return B, metadata, packets, forcings[0]


def harmonic(A, M, B, frequency_hz):
    """Original full sparse pencil and gates; no pole filling or model reduction."""
    from openswing.frequency_response import harmonic_solve
    return harmonic_solve(A, M, B, 2*math.pi*frequency_hz)


def nodal_response(system, fixture, state):
    """Exact loaded-chart nodal translations/spatial rotations in physical axes."""
    import numpy as np
    n = system.network; z = np.asarray(state)
    if z.shape != (system.size, 2):
        raise ValueError('Expected native F3 and physical upper-tip Mz columns.')
    q = z[:6*n.nn].reshape(n.nn, 6, 2)
    Qcut = np.asarray(fixture['gauge']['cut']['rotation'])
    return np.concatenate([np.einsum('ij,njk->nik', Qcut, n.L*q[:, :3]),
                           np.einsum('ij,njk->nik', Qcut, q[:, 3:])], axis=1)


def base_geometry(system, fixture):
    """Audit geometry only; never use this output to manufacture counterloads."""
    import numpy as np
    from openswing.geometry import surface_frame
    n = system.network
    r, Q, *_ = n.unpack(system.base)
    cut = fixture['gauge']['cut']; Qcut = np.asarray(cut['rotation'])
    physical_r = np.asarray(cut['position']) + (r-np.asarray(cut['jig_position'])) @ Qcut.T
    material = np.empty_like(Q)
    for mesh in n.meshes:
        ts, ids = n.station_nodes[mesh.beam.index]
        material[ids] = Q[ids] @ surface_frame(mesh.beam, ts)
    return dict(positions_gauge=r, rotations_Q_gauge=Q, material_rotations_gauge=material,
                positions_physical=physical_r,
                material_rotations_physical=np.einsum('ij,njk->nik', Qcut, material),
                meshes_gauge=n.deformed_meshes(r, Q, n.geometry(r, Q)),
                stations={str(b): (ts.copy(), ids.copy()) for b, (ts, ids) in n.station_nodes.items()})


def reaction_response(system, fixture, state):
    """Native support actions on each component, with loaded offset-arm terms."""
    import numpy as np
    n = system.network; z = np.asarray(state)
    if z.shape != (system.size, 2):
        raise ValueError('Expected two full harmonic state columns.')
    r, _, _, _, base_reactions, _ = n.unpack(system.base)
    dr = n.L*z[:6*n.nn].reshape(n.nn, 6, 2)[:, :3]
    raw = z[6*(n.nn+n.ne):n.gamma_start]
    Qcut = np.asarray(fixture['gauge']['cut']['rotation'])
    result = []
    for c in n.constraints:
        v = raw[c['sl']]; dF = n.F*v[:3]; dT = n.F*n.L*v[3:]
        dM = dT.copy()
        if c['b'] is not None:
            arm = r[c['b']]-r[c['a']]
            darm = dr[c['b']]-dr[c['a']]
            F0 = n.F*base_reactions[c['sl']][:3]
            dM += np.cross(darm.T, F0).T + np.cross(arm, dF.T).T
        result.append(dict(kind=c['kind'], force=Qcut@dF, moment=Qcut@dM,
                           other_force=None if c['b'] is None else -Qcut@dF,
                           other_moment=None if c['b'] is None else -Qcut@dT))
    return result
