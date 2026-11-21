"""Independent continuous-structure/discrete-aero free elastic response.

No production imports. Rod compliance is condensed exactly to the receiving
nodes at each requested frequency; no elastic modes or rigid-body modes are
truncated. This verifies a declared combined component, not Daedalus parity.
"""
import numpy as np
from scipy.linalg import lu_factor, lu_solve, get_lapack_funcs

from elastic_fin_kinematics import NodalSampler
from free_elastic_aero import MultiSurfaceAero, FreeFeedback


def checked_solve(matrix, rhs):
    matrix, rhs = np.asarray(matrix), np.asarray(rhs)
    vector = rhs.ndim == 1
    if vector:
        rhs = rhs[:, None]
    rows = np.max(abs(matrix), axis=1)
    if np.any(rows == 0):
        raise ValueError('Empty independent equation')
    scaled = matrix/rows[:, None]
    columns = np.max(abs(scaled), axis=0)
    if np.any(columns == 0):
        raise ValueError('Empty independent unknown')
    scaled = scaled/columns
    lu, piv = lu_factor(scaled)
    rcond, info = get_lapack_funcs('gecon', (scaled,))(lu, np.linalg.norm(scaled, 1))
    solution = lu_solve((lu, piv), rhs/rows[:, None])/columns[:, None]
    residual = matrix@solution-rhs
    denominator = abs(matrix)@abs(solution)+abs(rhs)
    if np.any((denominator == 0) & (abs(residual) != 0)):
        raise ValueError('Nonzero residual in an empty equation')
    backward = np.divide(abs(residual), denominator, out=np.zeros_like(denominator),
                         where=denominator != 0)
    diagnostic = dict(reciprocal_condition=float(rcond),
                      component_backward=float(np.max(backward)),
                      absolute_residual=float(np.max(abs(residual))),
                      condition_info=int(info))
    if info or rcond < 1e-12 or diagnostic['component_backward'] > 1e-10:
        raise ValueError('Independent solve failed its original numerical gates: '+str(diagnostic))
    if not np.all(np.isfinite(solution)):
        raise ValueError('Nonfinite independent solution')
    return (solution[:, 0] if vector else solution), dict(
        matrix=matrix, rhs=rhs, residual=residual, denominator=denominator,
        row_scales=rows, column_scales=columns, diagnostics=diagnostic)


def geometry(fixture, n):
    """Literal cosine nodes, midangle receiving stations and affine base."""
    positions, frames, endpoints, fractions, physical, nodes, panel_branch = [], [], [], [], [], [], []
    material = {key: [] for key in MultiSurfaceAero.scalar_material}
    for name in ('wing', 'fin'):
        branch = fixture['branches'][name]
        length = branch['length']; offset = len(positions)
        s = length/2*(1-np.cos(np.arange(n+1)*np.pi/n))
        s[0], s[-1] = 0., length
        sm = length/2*(1-np.cos((np.arange(n)+.5)*np.pi/n))
        fraction = (sm-s[:-1])/np.diff(s)
        c, span = (np.asarray(branch[k]) for k in ('chord_direction', 'span_direction'))
        frame = np.column_stack((c, span, np.cross(c, span)))
        stretch = 1+branch['tension']/branch['stiffness']['EA']
        r = np.asarray(branch['root'])+stretch*s[:, None]*span
        positions.extend(r); frames.extend([frame]*(n+1))
        endpoints.extend(np.column_stack((np.arange(n)+offset, np.arange(n)+offset+1)))
        fractions.extend(fraction); physical.extend([branch['physical_id']]*n)
        panel_branch.extend([name]*n)
        nodes.extend(dict(branch=name, s=float(value), t=float(value-length/2)) for value in s)
        constants = dict(chord=branch['chord'], chord0=branch['chord'], chord1=branch['chord'],
                         Xax=branch['Xax'], Xax0=branch['Xax'], Xax1=branch['Xax'],
                         alpha_radians=np.deg2rad(branch['alpha_degrees']), CLa=branch['CLa'],
                         dCLdF3=branch['dCLdF'] if branch['control'] == 3 else 0.,
                         Cdf=branch['Cdf'], Cdp=branch['Cdp'], Cm=branch['Cm'],
                         dCMdF3=0., dCDdF3=0.)
        for key, value in constants.items():
            material[key].extend([value]*n)
    return dict(positions=np.asarray(positions), material_frames=np.asarray(frames),
                endpoints=np.asarray(endpoints), fractions=np.asarray(fractions),
                physical=np.asarray(physical), material={k: np.asarray(v) for k, v in material.items()},
                nodes=nodes, panel_branch=panel_branch)


def aerodynamic_model(fixture, n, quadrature):
    g = geometry(fixture, n)
    sampler = NodalSampler(g['positions'], g['material_frames'], g['endpoints'], g['fractions'])
    flow = dict(freestream=[fixture['speed'], 0., 0.], density=fixture['density'],
                sound_speed=fixture['sound_speed'], pg_mach=fixture['mach'],
                moment_origin=fixture['carrier']['origin'],
                wake_core_ratio=fixture['condition']['wake_core_ratio'])
    aero = MultiSurfaceAero(g['material'], flow, g['physical'], quadrature)
    return sampler, aero, g


def manufacture(fixture, n):
    """Only Q32 defines loads, then every reference/native variant holds them."""
    sampler, aero, g = aerodynamic_model(fixture, n, 32)
    section = sampler.sample()
    base = aero.base_system(section)
    gamma, solve = checked_solve(base['W'], base['rhs'])
    response = aero.evaluate(section, gamma)
    counterloads = sampler.transfer(section, response['strip_force'], response['strip_moment_axis'])
    fixed = -counterloads.copy()
    for j, name in enumerate(('wing', 'fin')):
        branch = fixture['branches'][name]
        fixed[(j+1)*(n+1)-1, :3] += branch['tension']*np.asarray(branch['span_direction'])
    balancer = np.r_[fixture['base']['carrier_balancer_force'],
                     fixture['base']['carrier_balancer_moment']]
    # This checks manufacturing origins, not a production equilibrium solve.
    net = fixed+counterloads
    balance = np.r_[np.sum(net[:, :3], axis=0),
                    np.sum(net[:, 3:]+np.cross(g['positions'], net[:, :3]), axis=0)]+balancer
    if np.max(abs(balance)) > 1e-10 or np.max(abs(response['residual'])) > 1e-10:
        raise ValueError('Independent manufactured base is not balanced')
    if any(np.max(abs(gamma[np.asarray(g['panel_branch']) == name])) < 1e-6 for name in ('wing', 'fin')):
        raise ValueError('Both surfaces require nonzero loaded circulation')
    return dict(n=n, quadrature=32, gamma=gamma, counterloads=counterloads,
                body_fixed_nodal_loads=fixed, carrier_balancer=balancer,
                balance=balance, geometry=g, section=section, response=response, solve=solve)


def derivative_model(fixture, n, manufactured, quadrature, epsilon):
    sampler, aero, _ = aerodynamic_model(fixture, n, quadrature)
    feedback = FreeFeedback(sampler, aero, manufactured['gamma'], lag=fixture['condition']['aero_lag'])
    return feedback.derivatives(epsilon)


def harmonic(fixture, green, derivative, frequency_hz):
    blocks, shapes = derivative['blocks'], derivative['shapes']
    H = green['motion_map']
    nq = H.shape[0]; nm = nq-6; ng = blocks['gamma']['residual'].shape[1]
    if H.shape[1] != nm+6:
        raise ValueError('Unexpected mechanical Green input basis')
    omega = 2*np.pi*frequency_hz
    def coefficients(output):
        return (blocks['q'][output]+1j*omega*blocks['v'][output]-omega**2*blocks['a'][output],
                blocks['gamma'][output]+1j*omega*blocks['gamma_dot'][output],
                blocks['control'][output][:, 0])
    Fq, Fg, Fc = coefficients('nodal_wrench')
    Eq, Eg, Ec = coefficients('residual')
    mechanical = H[:, :nm]
    K = np.block([[np.eye(nq)-mechanical@Fq, -mechanical@Fg], [Eq, Eg]])
    rhs = np.zeros((nq+ng, 2), complex)
    rhs[:nq, 0] = mechanical@Fc
    rhs[nq:, 0] = -Ec
    rhs[:nq, 1] = H[:, -1]  # +1 Nm physical carrier Mz
    solution, solve = checked_solve(K, rhs)
    q, gamma = solution[:nq], solution[nq:]
    outputs = {}
    for key, shape in shapes.items():
        U, G, C = coefficients(key)
        value = U@q+G@gamma
        value[:, 0] += C
        outputs[key] = value.reshape(*shape, 2)
    r0 = green['base']['positions']
    nodes = q[6:].reshape(-1, 6, 2)
    body = nodes.copy()
    for column in range(2):
        body[:, :3, column] -= q[:3, column]+np.cross(q[3:6, column], r0)
        body[:, 3:, column] -= q[3:6, column]
    frame_velocity = 1j*omega*q[:3]+np.cross(q[3:6].T, [fixture['speed'], 0., 0.]).T
    outputs.update(node_absolute_motion=nodes, node_body_motion=body,
                   frame_motion=q[:6], frame_velocity=frame_velocity,
                   frame_rates=1j*omega*q[3:6], gamma=gamma)
    return dict(solution=solution, outputs=outputs, solve=solve, frequency_Hz=frequency_hz)
