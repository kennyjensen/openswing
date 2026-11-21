"""Cross-check new reference seams against independently retained formulations."""
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for _name in ('elastic_fin_aero', 'elastic_fin_kinematics', 'free_elastic_aero',
              'coupled_fin_aero_reference', 'rotating_wing_fin_reference'):
    _spec = importlib.util.spec_from_file_location(_name, ROOT/'scripts'/(_name+'.py'))
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_name] = _module
    _spec.loader.exec_module(_module)

MultiSurfaceAero = sys.modules['free_elastic_aero'].MultiSurfaceAero


def _material(chord, xax, alpha, slope, control, cdf, cdp, cm):
    chord = np.asarray(chord)
    n = len(chord)
    p = {k: np.zeros(n) for k in MultiSurfaceAero.scalar_material}
    for k, v in dict(chord=chord, chord0=chord, chord1=chord,
                     Xax=xax, Xax0=xax, Xax1=xax, alpha_radians=alpha,
                     CLa=slope, dCLdF3=control, Cdf=cdf, Cdp=cdp, Cm=cm).items():
        p[k] = np.broadcast_to(v, (n,)).copy()
    return p


def _flow(speed, rho, sound):
    return dict(freestream=[speed, 0., 0.], density=rho, sound_speed=sound,
                pg_mach=0., moment_origin=[0., 0., 0.], wake_core_ratio=.25)


def test_mutual_field_matches_retained_rotating_wing_fin_quadrature():
    old = sys.modules['rotating_wing_fin_reference']
    g = old.geometry(4, .013)
    frame = np.stack((g['c'], g['s'], g['normal']), axis=2)
    n = len(g['ds'])
    sections = {k: g[k] for k in ('r0', 'r1', 'rm', 'ds')}
    sections.update(R0=frame, R1=frame, Rm=frame)
    for k in ('velocity', 'omega', 'acceleration', 'alpha'):
        sections[k] = np.zeros((n, 3))
    p = _material(g['chord'], old.XAX, 2*np.pi/180, 2*np.pi, 0.,
                  old.CDF, old.CDP, old.CM)
    aero = MultiSurfaceAero(p, _flow(old.SPEED, old.RHO, old.SOUND), g['beam'])
    new = aero.base_system(sections)
    for receiver in ('cp', 'hv', 'axis'):
        expected, _ = old.field(g, 32, receiver)
        np.testing.assert_allclose(new['fields'][receiver], expected, atol=3e-13, rtol=2e-12)
        assert new['diagnostics'][receiver]['regularized_integrals'] > 0
    # A live-core probe must remain complex even with real vortex endpoints.
    core_probe = dict(new['geometry'])
    core_probe['source_core'] = core_probe['source_core'].astype(complex)
    core_probe['source_core'][0] += 1e-24j
    tangent = aero.fields(core_probe)['fields']['cp'].imag/1e-24
    assert np.max(abs(tangent[4:, 0])) > 1e-5
    np.testing.assert_array_equal(tangent[:4], 0.)


def test_origin_velocity_is_not_subtracted_twice():
    old = sys.modules['coupled_fin_aero_reference']
    fixture = json.loads((ROOT/'docs/validation/coupled-fin-fixture.json').read_text())
    ref = old.Reference(4, 32, fixture)
    q = ref.base_coordinates()
    q[:6] = [.12, -.08, .03, .02, -.03, .04]
    v = np.array([.35, -.24, .12, .07, -.04, .06, -.03])
    a = np.array([-.15, .12, .05, .04, -.02, .03, .01])
    gamma = np.linspace(.1, .4, 4)
    gamma_dot = np.linspace(-.03, .02, 4)
    g = ref.geometry(q, v, a)
    kin = g['kinematics']
    frame = np.broadcast_to(np.column_stack((g['c'], g['s'], g['normal'])), (4, 3, 3))
    sections = {k: g[k] for k in ('r0', 'r1', 'rm', 'ds')}
    sections.update(R0=frame, R1=frame, Rm=frame,
                    velocity=ref.point_velocity(g['rm'], kin),
                    omega=np.broadcast_to(kin['omega_fin'], (4, 3)),
                    acceleration=ref.point_acceleration(g['rm'], kin),
                    alpha=np.broadcast_to(kin['alpha_fin'], (4, 3)))
    f = fixture['fin']
    p = _material(np.full(4, f['chord']), f['Xax'], np.deg2rad(f['alpha_degrees']),
                  f['CLa'], f['dCLdF3'], f['Cdf'], f['Cdp'], f['Cm'])
    aero = MultiSurfaceAero(p, _flow(fixture['speed'], fixture['density'], fixture['sound_speed']),
                            np.ones(4, int))
    expected = ref.evaluate(q, v, a, gamma, gamma_dot, controlrad=.017, lag=True)
    actual = aero.evaluate(sections, gamma, gamma_dot, control=.017, lag=True,
                           freestream=aero.free-v[:3])
    for name in ('residual', 'velocity', 'cp_velocity', 'axis_velocity'):
        np.testing.assert_allclose(actual[name], expected[name], atol=3e-13, rtol=2e-12)
    # The explicit reference aggregates about moving carrier O, whereas the
    # section map stores its moment about fixed Earth O. Convert that origin.
    wrench = actual['wrenches'].copy()
    wrench[:, 3:] -= np.cross(q[:3], wrench[:, :3])
    np.testing.assert_allclose(wrench, expected['wrenches'][:, -1], atol=3e-12, rtol=2e-12)
