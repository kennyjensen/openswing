"""Independent saved-field audit for the two declared SA-12 parallel-wake setups."""
import math


def replay(model, settings, raw):
    import numpy as np
    from openswing.geometry import model_meshes
    from openswing.frozen_influence import lifting_geometry
    from avl_vorvelc_reference import matrix

    assert settings['mach'] == 0. and settings['ground_effect'] == 1
    assert settings['ground_normal'] == [0., 0., 1.] and settings['beta'] == 0.
    assert not model.diagnostics and raw['converged'] and raw['residual'] < 1e-8
    meshes = model_meshes(model, settings['panels'])
    sample = lambda key: np.concatenate([m.beam.value(key, m.tm) for m in meshes])
    span = np.concatenate([m.frames[..., 1] for m in meshes])
    normal = np.concatenate([np.sin(np.deg2rad(m.beam.value('alpha', m.tm)))[:, None] * m.frames[..., 0]
        + np.cos(np.deg2rad(m.beam.value('alpha', m.tm)))[:, None] * m.frames[..., 2] for m in meshes])
    alpha = math.radians(settings['alpha'])
    wind = np.array([math.cos(alpha), 0., math.sin(alpha)])
    lift = np.array([-math.sin(alpha), 0., math.cos(alpha)])
    frozen = settings['freeze_influences']
    direction = np.array([1., 0., 0.]) if frozen else wind
    ground_normal = np.array([0., 0., 1.]) if frozen else lift
    assert settings['attitude'] == [0., 0. if frozen else settings['alpha'], 0.]
    height = settings['position_earth'][2]
    rotation = np.array([direction, [0., 1., 0.], ground_normal])
    np.testing.assert_allclose(rotation @ rotation.T, np.eye(3), rtol=0., atol=1e-14)
    g = lifting_geometry(meshes, direction)
    reflect = lambda points: points - 2 * (points @ ground_normal + height)[:, None] * ground_normal
    image_a, image_b = reflect(g['a']), reflect(g['b'])
    gamma = np.array([s['circulation'] for s in raw['strips']])
    speed, rho = settings['speed'], settings['density']
    np.testing.assert_allclose(g['hv'], [s['velocity_position'] for s in raw['strips']], rtol=0., atol=2e-12)
    scale = np.longdouble(1) / (4 * np.arccos(np.longdouble(-1)) * np.longdouble('.079577472'))
    velocities = []
    for points, exclude in ((g['hv'], True), (g['cp'], False)):
        operator = matrix(points @ rotation.T, g['a'] @ rotation.T, g['b'] @ rotation.T,
            0., exclude_self=exclude, core_fraction=0., dtype=np.longdouble)
        operator -= matrix(points @ rotation.T, image_a @ rotation.T, image_b @ rotation.T,
            0., exclude_self=False, core_fraction=0., dtype=np.longdouble)
        velocities.append(np.asarray(np.einsum('ijq,j->iq', operator, gamma) * scale, dtype=float) @ rotation + speed * wind)
        del operator
    v, vcp = velocities
    perp = v - np.sum(v * span, axis=1)[:, None] * span
    vp = np.linalg.norm(perp, axis=1)
    cl = 2 * gamma / (vp * g['chord'])
    width = settings['stall_width']
    f = width * (np.logaddexp(0, (cl - sample('CLmax')) / width)
                 - np.logaddexp(0, (sample('CLmin') - cl) / width))
    tangent = np.sum(vcp * normal, axis=1)
    leakage = vp * settings['stall_factor'] * f / sample('dCLda')
    vortex = rho * gamma[:, None] * np.cross(v, span) * g['ds'][:, None]
    friction = .5 * rho * np.linalg.norm(v, axis=1)[:, None] * v * (g['chord'] * sample('Cdf') * g['ds'])[:, None]
    pressure = .5 * rho * vp[:, None] * perp * (g['chord'] * sample('Cdp') * g['ds'])[:, None]
    stall_drag = 2 * rho * perp / vp[:, None] * (tangent**2 * g['chord'] * g['ds'])[:, None]
    force = vortex + friction + pressure + stall_drag
    total = np.array([math.fsum(force[:, i]) for i in range(3)])
    qs = .5 * rho * speed**2 * model.reference[0, 0]
    wake = np.zeros_like(g['hv'])
    for endpoints, sign in ((g['b'], 1), (g['a'], -1), (image_b, -1), (image_a, 1)):
        r = g['hv'][:, None, :] - endpoints[None, :, :]
        r -= (r @ direction)[..., None] * direction
        radius_squared = np.sum(r * r, axis=2)
        assert np.min(radius_squared) > 0
        wake += sign * np.einsum('ijq,j->iq', np.cross(direction, r) / radius_squared[..., None], gamma) / (2 * math.pi)
    cdi = -.5 * rho * math.fsum(gamma * np.sum(wake * np.cross(direction, g['b'] - g['a']), axis=1)) / qs
    moment = math.fsum(s['moment'][1] + (s['position'][2] - model.reference[1, 2]) * s['force'][0]
                      - (s['position'][0] - model.reference[1, 0]) * s['force'][2] for s in raw['strips'])
    errors = dict(velocity_relative=float(np.max(abs(v - [s['relative_velocity'] for s in raw['strips']])) / speed),
        section_cl=float(max(abs(cl - [s['cl'] for s in raw['strips']]))),
        tangency_relative=float(max(abs(tangent - leakage)) / speed),
        force_vector=float(np.max(abs(force - [s['force'] for s in raw['strips']]))),
        CL=abs(float(total @ lift / qs) - raw['CL']), CD=abs(float(total @ wind / qs) - raw['CD']),
        CDi=abs(float(cdi) - raw['CDi']), Cm=abs(float(moment / (qs * model.reference[0, 1])) - raw['Cm']))
    assert errors['velocity_relative'] < 2e-10 and errors['section_cl'] < 2e-12, errors
    assert errors['tangency_relative'] < 1e-8 and errors['force_vector'] < 1e-9, errors
    assert max(errors[k] for k in ('CL', 'CD', 'CDi', 'Cm')) < 2e-12, errors
    return dict(verified=True, errors=errors,
        minimum_stall_margin_widths=float(min(np.minimum(sample('CLmax')-cl, cl-sample('CLmin')) / width)),
        drag_parts={key:float(math.fsum(value @ wind) / qs) for key,value in
            [('circulation',vortex),('friction',friction),('pressure',pressure),('stall',stall_drag)]},
        freestream_ground_normal_speed=float(speed * wind @ ground_normal))
