"""Moving pylon sensors from the published unsteady formulation, section 10.

Axes use aft-positive V, right-positive beta, up-positive alpha. Accelerometer
output is specific force a-g; GPS and angular motion use inertial transport.
Error-integral and controller states are separate differential variables, not
inferred by integrating output samples here.
"""
import numpy as np
from .geometry import surface_frame
from .ground import body_to_earth
from .local_motion import LocalMotion


UNITS = dict(speed='input L/T', alpha='deg', beta='deg', bank='deg', elevation='deg', heading='deg',
    air_velocity_sensor='input L/T', rates_sensor='rad/input T', acceleration_sensor='input L/T^2',
    angular_acceleration_sensor='rad/input T^2', position_earth='input L', velocity_earth='input L/T',
    anchor_position_body='input L', anchor_velocity_body='input L/T', position_body='input L',
    displacement_body='input L', force_local='input F', moment_local='input F L', circulation='input L^2/T',
    strain='dimensionless', curvature_change='rad/input L', shell_strain='dimensionless',
    shell_shear_stress='input F/L^2')
LIMITATIONS = [
    'Sensor axes and locations follow their rigid pylons. Relative body position/velocity describe the beam anchor; GPS and inertial measurements describe the pylon tip.',
    'Full airflow includes the implemented regularized lifting-line, volume, propulsive jet and gust fields. Near-filament/core and ASWING sensor-flow parity require independent refinement.',
    'Structural force/moment use the inward endpoint trace and left trace at an interior anchor, in the anchor csn frame. Both adjacent traces are exported; exact ASWING trace choice at load/property jumps is unverified.',
    'Mechanical strain and shell stress use the selected adjacent element material midpoint, whose location is reported. They are not exact nodal or pylon-tip strain measurements.',
    'Zero airspeed makes flow angles undefined. At a vertical sensor V axis, bank/heading are undefined; Euler-angle branches are not a global attitude representation.',
    'Selected measurements can drive scheduled feedback and differential error integrals. Full control-file index/unit mapping and arbitrary custom controller parity remain unverified.'
]


def source_sensor_limitations(network, data):
    """Keep source sensor sampling claims consistent with material damping."""
    from .source_recovery import source_damping_elements
    limitations = [
        LIMITATIONS[0],
        'Structural loads and strain use the inward endpoint and left trace at an interior sensor anchor, each in its actual one-sided section frame. Both adjacent traces remain available.',
        'Shell strain/stress use the selected one-sided properties at the sensor anchor, not an adjacent element average. Exact historical ASWING trace choice at jumps remains unverified.',
        ('Still-air modal analysis has no mean airflow; flow quantities remain unavailable.' if getattr(network, 'source_quiescent', False) else
         'Vacuum dynamics has no airflow; flow quantities remain unavailable.' if getattr(network, 'source_dynamic', False) else
         'Static analysis has no airflow or time evolution; flow quantities remain unavailable.' if data['aero'] is None else
         'Steady sensor airflow uses the current aerodynamic field; no time evolution or dynamic launch is available for this source operator.'),
        LIMITATIONS[4]]
    if np.any(source_damping_elements(network)):
        limitations[1] = ('Structural loads use the inward endpoint and left trace at an interior sensor anchor, in its actual one-sided section frame. Both load traces remain available. Damped endpoint mechanical strains are unavailable because no endpoint material-rate interpolation is prescribed.')
        limitations[2] = ('For a damped selected interval, sensor mechanical and shell axial strains are that adjacent source constitutive interval estimate, with averaged shell properties and reported strain_sample_t/strain_transform_average; strain_axes_body is null because the transform average is nonorthogonal. Total-torque shell shear stress remains an anchor sample. Undamped intervals retain their original sided anchor strains. Exact historical ASWING output sampling remains unverified.')
    return limitations


def _direction(value):
    """Normalize arbitrary finite vector magnitudes without overflow/underflow."""
    if not np.any(value):
        return None
    with np.errstate(over='ignore', under='ignore'):
        length = np.linalg.norm(value)
    if not np.isfinite(length) or length < np.sqrt(np.finfo(float).tiny):
        value = value/np.max(np.abs(value))
        length = np.linalg.norm(value)
    return value/length


def sensor_orientation(row):
    """Available triad and V direction, with no invented missing direction.

    Unsteady Eqs. 95--97/105/112--116 define location, speed and the V-axis
    angles independently of the complete Eq. 98 sensor transformation.
    The existing cross-product conditioning guard still bounds that triad.
    """
    values = np.asarray(row, dtype=float)
    if values.shape != (12,) or not np.all(np.isfinite(values)):
        raise ValueError('Sensor requires twelve finite fields after scaling and offsets.')
    v, a = (_direction(values[part]) for part in (slice(6,9), slice(9,12)))
    if v is None and a is None:
        return np.eye(3), np.array([1.,0.,0.]), None
    if v is None or a is None:
        return None, v, 'Sensor Vspec and Aspec must both be nonzero, or both omitted for the default axes.'
    b = np.cross(a, v); nb = np.linalg.norm(b)
    if nb < 1e-10:
        reason = ('Sensor Vspec and Aspec are parallel.' if not np.any(b) else
                  'Sensor Vspec and Aspec are too nearly parallel to resolve the full triad.')
        return None, v, reason
    b /= nb
    return np.column_stack([v, b, np.cross(v, b)]), v, None


def sensor_metadata(row):
    axes, v, reason = sensor_orientation(row)
    return dict(axes_available=axes is not None, v_axis_available=v is not None,
                axes_unavailable_reason=reason)


def sensor_axes(row):
    """Require the complete columns [V, beta, alpha] in undeformed body axes."""
    axes, _, reason = sensor_orientation(row)
    if axes is None:
        raise ValueError(reason)
    return axes


def validate_sensors(model):
    seen, diagnostics = set(), []
    beams = {b.index:b for b in model.beams}
    for row in model.records.get('sensor', []):
        axes, _, reason = sensor_orientation(row)
        index = int(row[0])
        if row[0] != index or index <= 0 or index in seen:
            raise ValueError('Sensor indices must be unique positive integers.')
        seen.add(index)
        if row[1] != int(row[1]) or int(row[1]) not in beams:
            raise ValueError('Sensor must reference a declared integer beam index.')
        beam = beams[int(row[1])]
        lo, hi = beam.domain
        if not lo <= row[2] <= hi:
            raise ValueError(f'Sensor {index} station lies outside beam {beam.index}.')
        if axes is None:
            diagnostics.append(f'Sensor {index}: {reason} Measurements requiring the full triad are unavailable; independent position, motion and speed outputs remain available.')
    return diagnostics


def sensor_euler(axes_earth):
    """Apparent bank/elevation/heading of the sensor triad, degrees."""
    v, b, a = np.asarray(axes_earth).T
    horizontal = np.hypot(v[0], v[1])
    singular = horizontal < 1e-10
    return dict(bank=None if singular else float(np.rad2deg(np.arctan2(-b[2], a[2]))),
                elevation=float(np.rad2deg(np.arctan2(-v[2], horizontal))),
                heading=None if singular else float(np.rad2deg(np.arctan2(-v[1], v[0]))),
                attitude_singular=bool(singular))


def measure_sensor(row, anchor, rotation, local, motion, *, model, condition, gravity,
                   airflow=None, frame=None):
    """Pure measurement at a known moving anchor; all vector inputs are body axes."""
    beam = next(b for b in model.beams if b.index == int(row[1]))
    jig = beam.position(row[2])
    point = np.asarray(anchor)+rotation@(row[3:6]-jig)
    original_axes, original_v, reason = sensor_orientation(row)
    axes = None if original_axes is None else rotation@original_axes
    if frame is None:
        earth = np.eye(3) if condition is None else body_to_earth(condition.attitude)
        origin = np.zeros(3) if condition is None else np.asarray(condition.position_earth)
        velocity = np.zeros(3) if condition is None else -condition.speed*condition.vectors()[0]-np.cross(motion.rates, model.reference[3])
    else:
        earth, origin, velocity = (np.asarray(frame[k]) for k in ('body_to_earth', 'position_earth', 'velocity_origin_body'))
    absolute_velocity = velocity+np.cross(motion.rates, point)+local.velocity_at(point)
    acceleration = local.absolute_acceleration(point, motion, model.reference[2])
    angular = local.absolute_angular_acceleration(motion)
    if axes is not None:
        angles = sensor_euler(earth@axes)
    elif original_v is not None:
        v = earth@rotation@original_v
        horizontal = np.hypot(v[0], v[1]); singular = horizontal < 1e-10
        angles = dict(bank=None, elevation=float(np.rad2deg(np.arctan2(-v[2], horizontal))),
            heading=None if singular else float(np.rad2deg(np.arctan2(-v[1], v[0]))),
            attitude_singular=bool(singular))
    else:
        angles = dict(bank=None, elevation=None, heading=None, attitude_singular=True)
    out = dict(index=int(row[0]), beam=int(row[1]), t=float(row[2]), position_body=point.tolist(),
        axes_available=axes is not None, v_axis_available=original_v is not None, axes_unavailable_reason=reason,
        axes_body=None if axes is None else axes.tolist(), axes_earth=None if axes is None else (earth@axes).tolist(),
        anchor_position_body=np.asarray(anchor).tolist(), anchor_velocity_body=local.velocity.tolist(),
        displacement_body=(np.asarray(anchor)-jig).tolist(),
        position_earth=(origin+earth@point).tolist(), velocity_earth=(earth@absolute_velocity).tolist(),
        rates_sensor=None if axes is None else (axes.T@(motion.rates+local.rates)).tolist(),
        angular_acceleration_sensor=None if axes is None else (axes.T@angular).tolist(),
        acceleration_sensor=None if axes is None else (axes.T@(acceleration-gravity)).tolist(),
        **angles)
    mode = 'unavailable' if condition is None else condition.sensor_flow
    out.update(flow_mode=mode, flow_singular=None, speed=None, alpha=None, beta=None, air_velocity_sensor=None)
    if condition is not None:
        wind = -absolute_velocity if mode == 'kinematic' else np.asarray(airflow)
        if axes is None:
            speed = float(np.linalg.norm(wind))
            out.update(speed=speed, flow_singular=bool(speed < 1e-12*max(1., condition.speed)))
            return out
        sensed = axes.T@wind
        speed = float(np.linalg.norm(sensed))
        out.update(speed=speed, flow_singular=bool(speed < 1e-12*max(1., condition.speed)), air_velocity_sensor=sensed.tolist(),
            alpha=None if speed < 1e-12*max(1., condition.speed) else float(np.rad2deg(np.arctan2(sensed[2], sensed[0]))),
            beta=None if speed < 1e-12*max(1., condition.speed) else float(np.rad2deg(np.arctan2(-sensed[1], np.hypot(sensed[0], sensed[2])))))
    return out


def network_sensors(network, data, elements, frame=None):
    """Measurements and one-sided load traces from the common network state."""
    sensors = []
    if not network.model.records.get('sensor'):
        return sensors
    n, c, motion = network, data['condition'], data['motion']
    local = data['local_motion']
    source = 'source_discrete' in data
    if not source:
        pa, pb, *_ = n.geometry(data['r'], data['Q'])
    for k, row in enumerate(n.model.records.get('sensor', [])):
        i = n.node(*row[1:3]); beam = next(b for b in n.model.beams if b.index == int(row[1]))
        field = LocalMotion(data['r'][i], *([np.zeros(3)]*4 if local is None else [v[i] for v in local.values]))
        airflow = None if data['aero'] is None else data['aero']['sensor_airflow'][k]['relative_velocity']
        out = measure_sensor(row, data['r'][i], data['Q'][i], field, motion, model=n.model, condition=c,
                             gravity=data['gravity'], airflow=airflow, frame=frame)
        # The midpoint law uses one anchor frame; source recovery has already
        # resolved the axes and resultants on each side.
        if not source:
            axes = data['Q'][i]@surface_frame(beam, row[2])
        traces = []
        sl = n.beam_elements[beam.index]
        for side, ids, end, sign in [('left', n.b, 1, -1), ('right', n.a, 0, 1)]:
            for j in range(sl.start, sl.stop):
                if ids[j] != i: continue
                if source:
                    endpoint = next(v for v in elements[j]['endpoint_traces'] if v['side'] == side)
                    traces.append(dict(side=side, element=j, force_local=endpoint['force_local'],
                        moment_local=endpoint['moment_local'], section_axes_body=endpoint['frame'],
                        strain=endpoint['strain'], curvature_change=endpoint['curvature_change'], shell=endpoint['shell']))
                    if 'strain_source' in endpoint:
                        traces[-1].update(strain_source=endpoint['strain_source'],
                            strain_unavailable_reason=endpoint['strain_unavailable_reason'])
                else:
                    offset = (pb[j] if end else pa[j])-data['r'][i]
                    force = data['N'][j]+sign*data['element_forces'][j, end]
                    moment = data['M'][j]+sign*np.cross(pb[j]-pa[j], data['N'][j])/2+np.cross(offset, data['N'][j])
                    moment += sign*data['element_moments'][j, end]
                    traces.append(dict(side=side, element=j, force_local=(axes.T@force).tolist(), moment_local=(axes.T@moment).tolist()))
        selected = traces[0]  # left interior/end; right at the first endpoint
        section = elements[selected['element']]
        out.update(force_local=selected['force_local'], moment_local=selected['moment_local'],
            load_trace=selected['side'], section_traces=traces,
            section_axes_body=selected['section_axes_body'] if source else axes.tolist(),
            strain=section['strain'], curvature_change=section['curvature_change'],
            shell_strain=section['shell']['axial_strain'], shell_shear_stress=section['shell']['shear_stress'],
            strain_sample_t=section['t'], strain_axes_body=section['frame'], circulation=None, circulation_sample_t=None)
        if source:
            out.update(strain=selected['strain'],
                curvature_change=selected['curvature_change'], shell_strain=selected['shell']['axial_strain'],
                shell_shear_stress=selected['shell']['shear_stress'], strain_sample_t=float(row[2]),
                strain_axes_body=selected['section_axes_body'], strain_sample_location='one-sided sensor anchor section')
            if selected.get('strain_source') == 'unavailable_endpoint_material_rate':
                out.update(strain=section['strain'], curvature_change=section['curvature_change'],
                    shell_strain=section['shell']['axial_strain'],
                    strain_source='source_discrete_damped_constitutive',
                    strain_sample_t=section['t'], strain_sample_element=selected['element'],
                    strain_sample_side=selected['side'], strain_axes_body=None,
                    strain_transform_average=section['transform_average'],
                    strain_sample_location='selected adjacent element constitutive average',
                    shell_strain_sample_t=section['t'], shell_shear_stress_sample_t=float(row[2]),
                    shell_shear_stress_source='total_section_resultant')
        if data['aero'] is not None and beam.lifting:
            strips = [s for s in data['aero']['strips'] if s['beam'] == beam.index]
            strip = min(strips, key=lambda s:abs(s['t']-section['t']))
            out.update(circulation=strip['circulation'], circulation_sample_t=strip['t'])
        sensors.append(out)
    return sensors


def rigid_sensors(model, condition, result):
    z = np.zeros(3); motion = condition.motion()
    earth = body_to_earth(condition.attitude)
    gravity = earth.T@np.array([0., 0., -(model.constants[0] if condition.gravity_magnitude is None else condition.gravity_magnitude)])
    output = []
    for row, flow in zip(model.records.get('sensor', []), result['sensor_airflow']):
        beam = next(b for b in model.beams if b.index == int(row[1])); anchor = beam.position(row[2])
        out = measure_sensor(row, anchor, np.eye(3), LocalMotion(anchor,z,z,z,z), motion, model=model,
                             condition=condition, gravity=gravity, airflow=flow['relative_velocity'])
        for key in ('force_local','moment_local','strain','curvature_change','shell_strain','shell_shear_stress'):
            out[key] = None
        strips = [s for s in result['strips'] if s['beam'] == beam.index and s['circulation'] is not None]
        strip = min(strips, key=lambda s:abs(s['t']-row[2])) if strips else None
        out.update(circulation=None if strip is None else strip['circulation'],
                   circulation_sample_t=None if strip is None else strip['t'], strain_sample_t=None,
                   load_trace=None, section_traces=[])
        output.append(out)
    return output
