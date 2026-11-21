"""Bounded, solved straight-wing control for attached wake and force consistency.

Research harness for Gaunaa et al. 2026 sections 2–3, not native ASWING or a
complete Vortex-Step-Method application. Runs three sweeps on one grid.
"""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
from types import SimpleNamespace, MethodType

import numpy as np
from scipy.integrate import quad_vec
from scipy.optimize import root

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from openswing.aero import finite_vortex, semi_infinite_vortex


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def utc(): return datetime.now(timezone.utc).isoformat()


def portable(x):
    if isinstance(x, np.ndarray): return x.tolist()
    if isinstance(x, np.generic): return x.item()
    if isinstance(x, dict): return {k: portable(v) for k, v in x.items()}
    if isinstance(x, (tuple, list)): return [portable(v) for v in x]
    return x


def write(p, value):
    p.write_text(json.dumps(portable(value), indent=2, allow_nan=False)+'\n')


class Control:
    def __init__(self, n, sweep, incidence=5.):
        angle = np.deg2rad(incidence)
        lam = np.deg2rad(sweep)
        self.span = np.array([np.sin(lam), np.cos(lam), 0.])
        horizontal_chord = np.array([np.cos(lam), -np.sin(lam), 0.])
        self.chord = np.cos(angle)*horizontal_chord - np.sin(angle)*np.array([0., 0., 1.])
        self.normal = np.cross(self.chord, self.span)
        self.s = -5*np.cos(np.linspace(0, np.pi, n+1))
        self.q = self.s[:, None]*self.span
        self.te = self.q + .75*self.chord
        self.mid = (self.q[:-1]+self.q[1:])/2
        self.cp = self.mid + .5*self.chord
        self.at_points = self.q + .5*self.chord
        self.ds = np.diff(self.s)
        self.jump = np.zeros((n+1, n))
        self.jump[np.arange(n), np.arange(n)] = -1.
        self.jump[np.arange(n)+1, np.arange(n)] = 1.
        self.cp_total = self.influence(self.cp)
        self.cp_inner = self.cp_total.copy()
        self.cp_inner[np.arange(n), np.arange(n)] += self.normal/np.pi
        self.quarter = self.influence(self.mid, quarter=True)
        self.at = self.influence(self.at_points, at=True)
        self.Ax = self.cp_inner@self.chord
        self.Az = self.cp_inner@self.normal

    def influence(self, points, *, quarter=False, at=False):
        bound = finite_vortex(points[:, None], self.q[None, :-1], self.q[None, 1:])
        if quarter:
            # Every bound segment lies on the same straight line as the
            # receiver. Its self-line principal-value contribution is zero.
            bound[:] = 0.
        attached = finite_vortex(points[:, None], self.q[None], self.te[None])
        if at:
            attached[np.arange(len(self.q)), np.arange(len(self.q))] = 0.
        free = semi_infinite_vortex(points[:, None], self.te[None], np.array([1., 0., 0.]))
        return bound + np.einsum('ijk,jl->ilk', attached+free, self.jump)

    def local(self, gamma):
        x = self.chord[0]+self.Ax@gamma
        z = self.normal[0]+self.Az@gamma
        return x, z, np.hypot(x, z), np.arctan2(z, x)

    def residual(self, gamma):
        _, _, speed, angle = self.local(gamma)
        return gamma-np.pi*speed*angle

    def jacobian(self, gamma):
        x, z, speed, angle = self.local(gamma)
        return np.eye(len(gamma))-np.pi*(
            ((angle*x-z)/speed)[:, None]*self.Ax
            + ((angle*z+x)/speed)[:, None]*self.Az)

    def quadrature(self, point, gamma, own_attached=None):
        """Independent direct Biot-Savart integration of all finite edges/rays."""
        strengths = self.jump@gamma
        starts = np.vstack([self.q[:-1], self.q])
        edges = np.vstack([np.diff(self.q, axis=0), self.te-self.q])
        weights = np.r_[gamma, strengths]
        if own_attached is not None:
            keep = np.arange(len(weights)) != len(gamma)+own_attached
            starts, edges, weights = starts[keep], edges[keep], weights[keep]
        def finite(t):
            delta = point-starts-t*edges
            return np.sum(weights[:, None]*np.cross(edges, delta)/np.linalg.norm(delta, axis=1)[:, None]**3, axis=0)/(4*np.pi)
        def infinite(t):
            delta = point-self.te-t*np.array([1., 0., 0.])
            return np.sum(strengths[:, None]*np.cross([1., 0., 0.], delta)/np.linalg.norm(delta, axis=1)[:, None]**3, axis=0)/(4*np.pi)
        f, ef = quad_vec(finite, 0., 1., epsabs=2e-11, epsrel=2e-11)
        w, ew = quad_vec(infinite, 0., np.inf, epsabs=2e-11, epsrel=2e-11)
        assert ef+ew < 2e-8
        return f+w, float(ef+ew)

    def trefftz(self, gamma):
        q = self.te.copy(); q[:, 0] = 0.
        midpoint = (q[:-1]+q[1:])/2
        delta = midpoint[:, None]-q[None]
        strength = self.jump@gamma
        v = np.sum(strength[None, :, None]*np.cross([1., 0., 0.], delta)
                   / (2*np.pi*np.sum(delta*delta, axis=-1))[:, :, None], axis=1)
        return .5*np.sum(gamma*np.cross(v, np.diff(q, axis=0))[:, 0])


def source_methods():
    directory = ROOT/'third_party/vortex_step_method'
    meta = json.loads((directory/'SOURCE.json').read_text())
    pins = {}
    for entry in meta['files']:
        if 'sha256' in entry:
            p = directory/entry['path']
            assert sha(p) == entry['sha256'], p
            pins[str(p.relative_to(ROOT))] = sha(p)
    p = directory/'src/VSM/core/BodyAerodynamics.py'
    tree = ast.parse(p.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'BodyAerodynamics')
    names = ['compute_attached_trailed_vortex_forces', 'compute_trefftz_plane_induced_drag']
    selected = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert len(selected) == 2
    namespace = {'np': np}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(p), 'exec'), namespace)
    return namespace, pins, meta['revision']


def check_source(control, gamma, force_at, trefftz, namespace):
    # The retained method orders sections right-to-left, with bound vortices
    # directed section 2 -> section 1. Adapt ordering, not the method bodies.
    panels = [SimpleNamespace(bound_point_1=control.q[i+1], bound_point_2=control.q[i],
              TE_point_1=control.te[i+1], TE_point_2=control.te[i])
              for i in range(len(gamma)-1, -1, -1)]
    body = SimpleNamespace(panels=panels, _va=np.array([1., 0., 0.]), _body_rates=np.zeros(3),
                           _aerodynamic_center_location=.25, _control_point_location=.75)
    body._wake_directions = lambda speeds, units: (units, speeds)
    def callback(points, b1, b2, te1, te2, g, directions, speeds, core):
        np.testing.assert_allclose(points, control.at_points[::-1], atol=2e-15, rtol=0.)
        np.testing.assert_array_equal(g, gamma[::-1])
        assert core == 0.
        # This callback deliberately uses this diagnostic's zero-core field;
        # VSM's viscous wake cores are not part of the declared comparison.
        return np.einsum('ijk,j->ik', control.at, gamma)[::-1]
    namespace['induced_velocity_at_points'] = callback
    actual, points = MethodType(namespace['compute_attached_trailed_vortex_forces'], body)(
        gamma[::-1], 1., 0., np.tile([1., 0., 0.], (len(gamma), 1)))
    actual_drag = MethodType(namespace['compute_trefftz_plane_induced_drag'], body)(gamma[::-1], 1.)
    np.testing.assert_allclose(actual[::-1], force_at, atol=2e-13, rtol=2e-12)
    np.testing.assert_allclose(actual_drag, trefftz, atol=2e-13, rtol=2e-12)
    return dict(attached_force_error=float(np.max(abs(actual[::-1]-force_at))),
                trefftz_drag_error=abs(actual_drag-trefftz))


def run(n, sweep, incidence, output, namespace):
    started = time.monotonic()
    c = Control(n, sweep, incidence)
    initial = np.linalg.solve(c.cp_total@c.normal, -np.full(n, c.normal[0]))
    solution = root(c.residual, initial, jac=c.jacobian, method='hybr', options={'xtol': 1e-10})
    gamma = solution.x
    error = float(np.max(abs(c.residual(gamma))))
    # MINPACK can report stagnation after reaching floating-point accuracy.
    # Accept by the declared equation residual, retain its status, and still
    # require positive circulation/axial speed and the Jacobian checks below.
    assert error < 1e-10, (solution.message, error)
    x, z, speed, angle = c.local(gamma)
    assert np.min(gamma) > 0 and np.min(x) > 0.
    direction = np.cos(np.arange(n)+.3); direction /= np.linalg.norm(direction)
    step = 2e-6
    fd = (c.residual(gamma-2*step*direction)-8*c.residual(gamma-step*direction)
          +8*c.residual(gamma+step*direction)-c.residual(gamma+2*step*direction))/(12*step)
    jac_error = float(np.max(abs(fd-c.jacobian(gamma)@direction)))
    assert jac_error < 2e-8
    v_quarter = [1., 0., 0.]+np.einsum('ijk,j->ik', c.quarter, gamma)
    vp = v_quarter-np.outer(v_quarter@c.span, c.span)
    unit_lift = np.cross(vp, c.span)/np.linalg.norm(vp, axis=1)[:, None]
    force_section = (gamma*speed*c.ds)[:, None]*unit_lift
    v_at = [1., 0., 0.]+np.einsum('ijk,j->ik', c.at, gamma)
    force_at = (c.jump@gamma)[:, None]*np.cross(v_at, c.te-c.q)
    total = force_section.sum(axis=0)+force_at.sum(axis=0)
    moment = np.cross(c.mid, force_section).sum(axis=0)+np.cross(c.at_points, force_at).sum(axis=0)
    drag_t = c.trefftz(gamma)
    source = check_source(c, gamma, force_at, drag_t, namespace)
    quadrature = []
    if n == 16:
        for name, point, tensor, own in [('control', c.cp[n//3], c.cp_total[n//3], None),
                                        ('attached', c.at_points[n//3], c.at[n//3], n//3)]:
            independent, estimate = c.quadrature(point, gamma, own)
            defect = float(np.max(abs(independent-tensor.T@gamma)))
            assert defect < 2e-9, (name, defect)
            quadrature.append(dict(receiver=name, error=defect, estimate=estimate))
    np.savez_compressed(output/f'sweep-{sweep:+03d}.npz', q=c.q, te=c.te, mid=c.mid, cp=c.cp,
                        span=c.span, chord=c.chord, normal=c.normal, ds=c.ds, jump=c.jump,
                        gamma=gamma, initial_gamma=initial, cp_total=c.cp_total, cp_inner=c.cp_inner,
                        quarter=c.quarter, attached=c.at, at_points=c.at_points,
                        v_quarter=v_quarter, v_at=v_at, force_section=force_section, force_at=force_at)
    return dict(sweep_degrees=sweep, incidence_degrees=incidence, panels=n, residual=error, jacobian_error=jac_error,
                root_evaluations=solution.nfev, gamma_min=np.min(gamma), gamma_max=np.max(gamma),
                root_reported_success=bool(solution.success), root_message=str(solution.message),
                section_force=force_section.sum(axis=0), attached_force=force_at.sum(axis=0),
                total_force=total, total_moment=moment, trefftz_drag=drag_t,
                full_drag_difference_percent=100*(total[0]/drag_t-1),
                section_only_drag_difference_percent=100*(force_section[:, 0].sum()/drag_t-1),
                peak_quarter_speed=np.max(np.linalg.norm(v_quarter, axis=1)),
                peak_attached_speed=np.max(np.linalg.norm(v_at, axis=1)),
                source_checks=source, independent_quadrature=quadrature,
                seconds=time.monotonic()-started)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--panels', type=int, choices=(16, 32, 64, 128), required=True)
    parser.add_argument('--incidence', type=float, choices=(1., 5.), default=5.)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists(): parser.error('Use a fresh output directory.')
    namespace, sources, revision = source_methods()
    pins = {str(p.relative_to(ROOT)): sha(p) for p in sorted(ROOT.glob('openswing/**/*.py'))+
            [ROOT/'docs/validation/ISAE_STATUS.md', ROOT/'docs/validation/isae-progress-scopes.json']}
    args.output.mkdir(parents=True)
    shutil.copyfile(__file__, args.output/'driver-used.py')
    plan = dict(observed_utc=utc(), previous_turn='progress: prescribed swept-wake limit isolated the near-wake singularity',
        unchanged_pins=pins, source_pins=sources, source_revision=revision,
        source_methods='Unmodified AT force and Trefftz methods; AT field callback uses the independently checked zero-core control field, not VSM viscous kernels.',
        panels=args.panels, sweeps_degrees=[0, 30, -30], span_arclength=10., chord=1.,
        incidence_degrees=args.incidence, speed=1., density=1., core=0., PG_Mach=0.,
        geometry='Straight oblique wing. Local chord perpendicular to bound line and rotated by the declared incidence about span. Cosine nodes; arithmetic midpoint samples. Attached legs 0.75 chord; wind-aligned free wake.',
        equation='Gamma=pi*c*|V_inner_3/4|*atan2(V_inner_3/4.n,V_inner_3/4.c), Cl=2*pi*alpha, Cd=Cm=0.',
        force='Section magnitude rho*Gamma*|V_inner_3/4|*ds, direction perpendicular to V_inner_1/4; add rho*jumpGamma*(V_at x attached_leg), sampled at section 3/4 chord.',
        reference='Independent Trefftz-plane drag for the same computed circulation, not a published ASWING output.',
        gates=dict(circulation_residual=1e-10, jacobian=2e-8, quadrature=2e-9),
        solver_acceptance='Equation residual plus positive Gamma/axial flow and Jacobian check; MINPACK status is recorded, not used instead of these checks.',
        source_url='https://backend.orbit.dtu.dk/ws/portalfiles/portal/446323265/Gaunaa_2026_J._Phys._Conf._Ser._3224_042030.pdf',
        limitations=['Straight bound line only; curved self-field correction and sharp fork mapping absent.',
                     'No automatic acceptance gate on force agreement; discrepancies are recorded.',
                     'No post-stall, compressibility, dynamic, aeroelastic or native ASWING validation.'])
    write(args.output/'plan.json', plan)
    rows = []
    try:
        for sweep in plan['sweeps_degrees']:
            row = run(args.panels, sweep, args.incidence, args.output, namespace)
            rows.append(row)
            print(json.dumps(portable(row)), flush=True)
        for name, digest in {**pins, **sources}.items(): assert sha(ROOT/name) == digest, name
        write(args.output/'results.json', dict(observed_utc=utc(), records=rows))
        write(args.output/'verification.json', dict(observed_utc=utc(), status='verified',
              artifacts={p.name: sha(p) for p in sorted(args.output.iterdir()) if p.is_file()},
              unchanged_pin_count=len(pins)))
    except Exception as exc:
        write(args.output/'failure.json', dict(observed_utc=utc(), error_type=type(exc).__name__,
                                             error=str(exc), completed_records=rows))
        raise


if __name__ == '__main__': main()
