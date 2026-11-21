"""Explicit primary-property AE-1-S reconstruction, not the literal ISAE model.

One full beam represents an ideal solid-wall half-wing by reflection.  The
material parameter increases from the negative tip to the positive tip; this
requires odd torsion/bending coupling fields, not ASWING's all-even shorthand.
Only the positive half is compared with the published skin-on measurements.
No equilibrium, modal, or time calculation is performed by this adapter.
"""
from pathlib import Path
import hashlib
import math

import numpy as np

from pazy_primary_conm2 import ROOT, CACHE, FOLDER, source, projection


ISAE_REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
ISAE = ROOT / '.reference/isae-validation' / ISAE_REVISION
CASE = ISAE / '4 - Aeroelasticity/AE - Aeroelastic Cases/AE-1-S Pazy Wing - Steady Deflection'
PRIMARY_AERO = CACHE / '03_2023_JA_Riso_Cesnik/04_Static_Aeroelastic'
LITERAL_SHA256 = '5086107d412ebf8f43ef75173fe553914fb074dd7dca3b93f7bd56ab365c17c8'
NOMINAL_SEMISPAN = .55
CHORD = .1
REFERENCE_X_OVER_C = .441
MIDCHORD_OFFSET = (.5 - REFERENCE_X_OVER_C) * CHORD
LE_OFFSET = -REFERENCE_X_OVER_C * CHORD
TE_OFFSET = (1. - REFERENCE_X_OVER_C) * CHORD
GRAVITY = (0., 0., 0.)
DENSITY = 1.23
MODEL_GRAVITY = 9.81  # Converts positive Weight entries to physical mass only.
SOUND_SPEED = 340.21
SECTION = dict(dCLda=6.1185, CLmax=1.1, CLmin=-1.1, alpha=0., Cm=0., Cdf=0., Cdp=0.)
ODD_FIELDS = frozenset({'EIcs', 'EIsn'})
REFLECTION = np.diag([1., -1., 1.])
STRAIN_REFLECTION = np.diag([1., -1., 1., 1.])
PILOT_CONDITIONS = ((5., 30.), (5., 40.), (7., 30.))


def pin(path):
    path = Path(path)
    raw = path.read_bytes()
    return dict(path=str(path.resolve()), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def _line(values):
    return ' '.join(format(float(value), '.17g') for value in values)


def configuration(refinement, *, mirrored=True):
    """Return (ASW text, provenance/geometry data, explicit mesh settings).

    refinement=2/4 gives 30/60 intervals per half.  The half-only option uses
    t=1+y to avoid implicit mirroring. Mounted steady solves require a solid
    image plane and tangential flow; condition() defaults to no images.
    Unsteady wall-root motion remains unsupported. No production is imported.
    """
    if isinstance(refinement, bool) or refinement not in (2, 4):
        raise ValueError('AE-1 pilot refinement must be 2 or 4 (30 or 60 half intervals).')
    if not isinstance(mirrored, bool):
        raise ValueError('mirrored must be a boolean.')
    literal = pin(CASE / 'Pazy_wing.asw')
    if literal['sha256'] != LITERAL_SHA256:
        raise ValueError('Pinned literal ISAE AE-1 input changed.')
    original = source(1)
    y = original['coordinates'][:, 1]
    length = float(y[-1])
    # Keep all original section and lumped-mass stations.  No stretching to
    # the nominal experimental normalization span, and no mass interpolation.
    positive = np.unique(np.concatenate([
        np.linspace(a, b, refinement + 1) for a, b in zip(y[:-1], y[1:])]))
    nodes = np.r_[-positive[:0:-1], positive] if mirrored else 1. + positive
    offset_t = 0. if mirrored else 1.
    root_t = offset_t
    sides = (-1, 1) if mirrored else (1,)
    weights = []
    weight_metadata = []
    for side in sides:
        transform = REFLECTION if side < 0 else np.eye(3)
        for i, (position, offset, mass, tensor) in enumerate(zip(
                original['coordinates'], original['offset'], original['mass'], original['inertia'])):
            point = transform @ (position + offset)
            tensor = transform @ tensor @ transform.T
            station = offset_t + side * float(position[1])
            # ASW Weight stores signed products, not tensor off-diagonals.
            values = np.array([tensor[0, 0], tensor[1, 1], tensor[2, 2],
                               -tensor[0, 1], -tensor[0, 2], -tensor[1, 2]])
            weights.append([1, station, *point, MODEL_GRAVITY * mass,
                            0, 0, 0, 0, 0, *(MODEL_GRAVITY * values)])
            weight_metadata.append(dict(kind='primary_nodal_mass', source_node=i, side=side,
                t=station, position=point.tolist(), mass_kg=float(mass), inertia=tensor.tolist()))
        # Avin Test 2 places the additional 10 g at the TE.  Riso instead says
        # 10 mm behind the TE.  Preserve the disagreement; it has zero load
        # effect in this stationary, zero-gravity pilot.  Do not add again the
        # original calibration masses already represented in the 16 tensors.
        point = transform @ np.array([TE_OFFSET, length, 0.])
        station = offset_t + side * length
        weights.append([1, station, *point, MODEL_GRAVITY * .01])
        weight_metadata.append(dict(kind='additional_test2_tip_mass', side=side,
            t=station, position=point.tolist(), mass_kg=.01, inertia=np.zeros((3, 3)).tolist()))

    half_count = 15 * refinement
    full_span = (2 if mirrored else 1) * length
    rows = [
        '! Explicit AE-1-S mixed-source reconstruction; not the literal ISAE attachment.',
        '! Primary skin1 section properties and CONM2-audited nodal tensors.',
        '! Only intrinsic axial/torsion K12 is projected out; no fitted coefficients.',
        '! Full mirror: EIcs/EIsn odd; other mapped section fields even.',
        '! Zero-gravity static scope; Test2 additional 10 g follows Avin TE location.',
        'Name', 'AE-1-S primary skin1 explicit ' + ('full mirror' if mirrored else 'half test fixture'),
        'End', 'Unit', 'L 1 m', 'T 1 s', 'F 1 N', 'End', 'Constant',
        _line([MODEL_GRAVITY, DENSITY, SOUND_SPEED]), 'End', 'Reference',
        _line([CHORD * full_span, CHORD, full_span]), 'End', 'Ground',
        _line([1, root_t, 0]), 'End', 'Weight',
        *[_line(row) for row in weights], 'End', 'Beam 1', 'Explicit primary Pazy material axis',
        't x y z chord Xax']
    geom_y = [-length, 0., length] if mirrored else [0., length]
    for value in geom_y:
        rows.append(_line([offset_t + value, 0., value, 0., CHORD, REFERENCE_X_OVER_C]))
    keys = list(projection(original['stiffness'][0])[0])
    rows.append('t ' + ' '.join(keys))
    sections = []
    # Segment pairs preserve exact one-sided section jumps, including the
    # odd-field discontinuity at the central clamp.  Never interpolate it.
    for side in sides:
        indices = range(14, -1, -1) if side < 0 else range(15)
        for i in indices:
            mapped, projected, error = projection(original['stiffness'][i])
            values = [(-mapped[key] if side < 0 and key in ODD_FIELDS else mapped[key]) for key in keys]
            lo, hi = ((-y[i + 1], -y[i]) if side < 0 else (y[i], y[i + 1]))
            rows += [_line([offset_t + lo, *values]), _line([offset_t + hi, *values])]
            sections.append(dict(side=side, source_section=i, start=float(offset_t + lo),
                end=float(offset_t + hi), fields=dict(zip(keys, values)),
                energy_projection_bound=float(error)))
    rows.append('t ' + ' '.join(SECTION))
    for station in (float(nodes[0]), float(nodes[-1])):
        rows.append(_line([station, *SECTION.values()]))
    rows += ['End', '']

    source_paths = [Path(__file__), ROOT / 'scripts/pazy_primary.py',
                    ROOT / 'scripts/pazy_primary_conm2.py', CASE / 'Pazy_wing.asw',
                    CASE / 'README.txt', CASE / 'Static_Aeroelastic.m',
                    CASE / 'alpha5.sh', CASE / 'alpha7.sh']
    source_paths += [CACHE / name for name in original['sources']]
    data = dict(skin=1, mirrored=mirrored, coordinates=original['coordinates'].copy(),
        material_stations=y.copy(), positive_nodes=positive.copy(), nodes=nodes.copy(),
        half_intervals=half_count, intervals=half_count * len(sides),
        actual_semispan=length, nominal_semispan=NOMINAL_SEMISPAN,
        root_t=root_t, tip_t=offset_t + length, parameter_offset=offset_t,
        chord=CHORD, reference_x_over_c=REFERENCE_X_OVER_C,
        weights=weight_metadata, sections=sections,
        source_pins=[pin(path) for path in source_paths],
        assumptions=dict(gravity='explicitly neglected', wall='ideal solid plane represented by symmetric full wing' if mirrored else 'half fixture only',
            section='literal ISAE dCLda/CL bounds and zero Cm/profile drag defaults',
            atmosphere='rho=1.23 kg/m3 inherited from ISAE; Mach explicitly zero, not a measured tunnel atmosphere',
            tip_mass='Avin Test2 10g atTE; Riso says 10mm behindTE; stationary zero-g results are independent of this choice',
            parity='S=diag(1,-1,1); Kminus=P Kplus P, P=diag(1,-1,1,1) in [eps_s,kappa_s,kappa_c,kappa_n]',
            equilibrium_branch='Independent cold jig per condition; nominal four load-continuation steps; stability not established',
            limitations='Primary K12 projection, ideal mirror wall, rigid tip approximation, unknown experimental initial shape and covariance.'))
    panels = dict(default=half_count * len(sides), beams={'1': dict(nodes=nodes.tolist())})
    return '\n'.join(rows), data, panels


def half_configuration(refinement):
    """Source fixture for image-equivalence tests; not a coupled pilot."""
    return configuration(refinement, mirrored=False)


def condition(alpha, speed):
    """Explicit positive-speed pilot condition; use condition=None at zero flow."""
    if not math.isfinite(float(alpha)) or not math.isfinite(float(speed)) or speed <= 0:
        raise ValueError('AE-1 aerodynamic conditions require finite alpha and positive speed; zero-flow baseline uses None.')
    from openswing.aero import FlightCondition
    return FlightCondition(speed=float(speed), alpha=float(alpha), beta=0., density=DENSITY,
        mach=0., gravity_magnitude=0., position_earth=(0., 0., 0.), attitude=(0., 0., 0.),
        ground_effect=0, ground_normal=(0., 1., 0.), rates=(0., 0., 0.),
        acceleration=(0., 0., 0.), angular_acceleration=(0., 0., 0.),
        controls={}, powers={}, circulation_modes={}, stall=True, stall_factor=40.,
        stall_width=.05, aero_lag=True, wake_core_ratio=.25, freeze_influences=False)


def observables(position, rotation, baseline=None):
    """Positive-tip chord recovery; optional subtraction of its own baseline.

    rotation is the node deformation Q in the straight +x chord/+y span jig.
    Positive twist uses atan2(z_LE-z_TE, x_TE-x_LE), matching the primary
    differential-chord convention and the accepted Pazy structural recovery.
    """
    position, rotation = np.asarray(position, dtype=float), np.asarray(rotation, dtype=float)
    if position.shape != (3,) or rotation.shape != (3, 3):
        raise ValueError('Tip position/rotation must have shapes (3,) and (3,3).')
    if not np.all(np.isfinite(position)) or not np.all(np.isfinite(rotation)):
        raise ValueError('Tip position and rotation must be finite.')
    le = position + rotation @ np.array([LE_OFFSET, 0., 0.])
    te = position + rotation @ np.array([TE_OFFSET, 0., 0.])
    mid = .5 * (le + te)
    twist = float(np.rad2deg(np.arctan2(le[2] - te[2], te[0] - le[0])))
    out = dict(leading_edge_position_m=le.tolist(), trailing_edge_position_m=te.tolist(),
               midchord_position_m=mid.tolist(), twist_xz_deg=twist,
               vertical_displacement_percent=float(100 * mid[2] / NOMINAL_SEMISPAN),
               twist_deg=twist)
    if baseline is not None:
        out['vertical_displacement_percent'] = float(100 * (mid[2] - baseline['midchord_position_m'][2]) / NOMINAL_SEMISPAN)
        out['twist_deg'] = twist - baseline['twist_xz_deg']
    return out


def datasets():
    """Pinned source coordinates/values; missing experimental entries stay None.

    These are processed sweep curves, not a claim about raw acquisition count.
    values keeps every source column; measured/modeled vertical displacement
    and twist are column1, in percent nominal semispan and degrees respectively.
    """
    result = []
    for alpha in (5, 7):
        for folder, suffix, reference in [('03_Experimental', 'exp', 'experiment'),
                                          ('02_Beam', 'UVLM', 'UM/NAST-VLM')]:
            for kind, quantity, units in [('disp', 'displacement', 'percent nominal semispan'),
                                           ('rot', 'twist', 'degree')]:
                name = f'static_aeroelastic_sweep_aoa{alpha}_skin1_{kind}_{suffix}.txt'
                path = CASE / folder / name
                values = [[float(token) for token in line.split()] for line in path.read_text().splitlines() if line.strip()]
                finite = [math.isfinite(row[1]) for row in values]
                values = [[value if math.isfinite(value) else None for value in row] for row in values]
                result.append(dict(alpha_deg=alpha, angle_deg=alpha, skin=1, quantity=quantity,
                    reference=reference, units=units, values=values, finite_value=finite,
                    path=str(path), source_pin=pin(path),
                    baseline='published processed sweep values; absent zero-speed experiment is not manufactured',
                    convention='5deg midchord directly measured; 7deg estimated from meanLE/TE; twist from differentialLE/TE'))
    return result
