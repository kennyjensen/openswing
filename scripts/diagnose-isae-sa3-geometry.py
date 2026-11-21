#!/usr/bin/env python3
"""Independent SA-3 geometry reconstruction from the retained literal table.

No OpenSwing imports, aerodynamic residuals, or equilibrium solves. Natural
cubic coefficients are obtained from a separate second-derivative linear system.
An adaptive arc integral diagnoses the production chordal-arc approximation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import time
import numpy as np
from scipy.integrate import quad
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = Path('/tmp/openswing-isae-sa3-velocity-run-20261025')
CASE = Path('/tmp/openswing-isae-sa3-reference-run-20261025/m400/row22')


def pin(p):
    p = Path(p)
    b = p.read_bytes()
    return dict(path=str(p), bytes=len(b), sha256=hashlib.sha256(b).hexdigest())


def write(p, d):
    p.write_text(json.dumps(d, indent=2, allow_nan=False)+'\n')


def source_tables(source):
    """Read this literal, unscaled single-beam fixture only; not an ASW parser."""
    tables = {}
    header = None
    in_beam = False
    for line in source.splitlines():
        tokens = line.split('#')[0].split()
        if not tokens:
            continue
        if tokens[0].lower() == 'beam':
            assert tokens == ['Beam', '1']
            in_beam = True
        elif in_beam and tokens[0].lower() == 'end':
            break
        elif in_beam and tokens[0] == 't':
            header = tokens
            for name in header[1:]:
                assert name not in tables
                tables[name] = []
        elif in_beam and header:
            # Fortran/ASW permits an exponent sign without an E, e.g. 6.2832+00.
            values = [float(re.sub(r'(?<=[0-9.])([+-]\d+)$', r'E\1', token)
                if 'e' not in token.lower() and 'd' not in token.lower()
                else token.replace('D', 'E').replace('d', 'e')) for token in tokens]
            assert len(values) == len(header)
            for name, value in zip(header[1:], values[1:]):
                tables[name].append([values[0], value])
    return {k: np.asarray(v) for k, v in tables.items()}


class NaturalSpline:
    def __init__(self, rows):
        self.t, self.v = rows.T
        h = np.diff(self.t)
        n = len(self.t)
        assert np.all(h > 0)
        matrix = np.zeros((n, n))
        rhs = np.zeros(n)
        matrix[0, 0] = matrix[-1, -1] = 1
        for i in range(1, n-1):
            matrix[i, i-1:i+2] = [h[i-1], 2*(h[i-1]+h[i]), h[i]]
            rhs[i] = 6*((self.v[i+1]-self.v[i])/h[i]-(self.v[i]-self.v[i-1])/h[i-1])
        self.second = np.linalg.solve(matrix, rhs)

    def __call__(self, t, derivative=False):
        t = np.asarray(t)
        j = np.clip(np.searchsorted(self.t, t, side='right')-1, 0, len(self.t)-2)
        h = self.t[j+1]-self.t[j]
        a, b = (self.t[j+1]-t)/h, (t-self.t[j])/h
        if derivative:
            return (self.v[j+1]-self.v[j])/h + h*((1-3*a*a)*self.second[j]+(3*b*b-1)*self.second[j+1])/6
        return a*self.v[j]+b*self.v[j+1]+h*h*((a**3-a)*self.second[j]+(b**3-b)*self.second[j+1])/6


def main(stage):
    stage.mkdir(parents=True, exist_ok=False)
    source_pins = [pin(CASE/'inputs.json'), pin(CASE/'result.json'), pin(CAPTURE/'capture.npz'),
        pin(__file__), pin(ROOT/'openswing/asw.py'), pin(ROOT/'openswing/geometry.py'),
        pin(ROOT/'openswing/frozen_influence.py'), pin(ROOT/'openswing/aero.py')]
    plan = dict(status='PREDECLARED_SAVED_GEOMETRY_RECONSTRUCTION', sources=source_pins,
        formulas=[154, 155, 156, 157, 158], saved_intervals=400, new_equilibria=0,
        new_aero_residuals=0, production_imports=0,
        reproduction_gates=dict(position_m=5e-11, unit_frame=5e-11, parameter_t=5e-11),
        arc_diagnostic='Adaptive integral of the independently constructed natural-spline axis; same retained node parameters. No new aircraft mesh or physical solution.',
        limits=['Natural spline endpoints are OpenSwing policy; ASWING historical endpoint convention is unproved.',
            'No unsupported nodal averaging or force-point projection is introduced.',
            'A change in geometry alone is not an aerodynamic result.'])
    write(stage/'plan.json', plan)
    started = time.monotonic()
    inp = json.loads((CASE/'inputs.json').read_text())
    saved = np.load(CAPTURE/'capture.npz')
    tables = source_tables(inp['source'])
    x, c = NaturalSpline(tables['x']), NaturalSpline(tables['chord'])
    slope = NaturalSpline(tables['dCLda'])
    assert np.array_equal(tables['y'][:, 0], tables['y'][:, 1])
    assert np.all(tables['z'][:, 1] == 0) and np.all(tables['Xax'][:, 1] == 0)
    assert 'twist' not in tables or np.all(tables['twist'][:, 1] == 0)
    assert np.all(tables['alpha'][:, 1] == 0) and np.all(tables['dCLda'][:, 1] > 0)
    limit = float(tables['x'][-1, 0])
    assert limit == 1.0277
    def position(t):
        return np.column_stack([x(abs(t)), t, np.zeros_like(t)])
    def span(t):
        derivative = x(abs(t), True)*np.sign(t)
        a = np.column_stack([derivative, np.ones_like(t), np.zeros_like(t)])
        return a/np.linalg.norm(a, axis=1)[:, None]
    t0, t1 = saved['r0'][:, 1], saved['r1'][:, 1]
    grid = np.linspace(-limit, limit, 2049)
    points = position(grid)
    arc = np.r_[0., np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]
    s0, s1 = np.interp(t0, grid, arc), np.interp(t1, grid, arc)
    theta0, theta1 = [np.arccos(np.clip(1-2*s/arc[-1], -1, 1)) for s in (s0, s1)]
    sa = arc[-1]*(1-np.cos((theta0+theta1)/2))/2
    t = np.interp(sa, arc, grid)
    fraction = (sa-s0)/(s1-s0)
    r0, r1 = position(t0), position(t1)
    rm = r0+fraction[:, None]*(r1-r0)
    wind = saved['wind']
    def offset(t):
        return c(abs(t))/np.linalg.norm(np.cross(wind, span(t)), axis=1)
    hv = rm+.25*offset(t)[:, None]*wind
    cp = hv+(slope(abs(t))/(4*np.pi)*offset(t))[:, None]*wind
    a, b = r0+.25*offset(t0)[:, None]*wind, r1+.25*offset(t1)[:, None]*wind
    normal = np.tile([0., 0., 1.], (400, 1))
    reconstructed = dict(t=t, r0=r0, r1=r1, rm=rm, span=span(t), chord=c(abs(t)),
        ds=s1-s0, a=a, b=b, hv=hv, cp=cp)
    errors = {k: float(np.max(abs(v-saved[k]))) for k, v in reconstructed.items()}
    assert all(v <= 5e-11 for v in errors.values()), errors
    # Separately integrate exact arc of the current source spline. Do not change
    # the reference model, knot array or saved physical solution.
    def speed(u):
        return float(np.sqrt(1+x(u, True)**2))
    knots = x.t
    intervals = [quad(speed, a, b, epsabs=2e-14, epsrel=2e-13) for a, b in zip(knots[:-1], knots[1:])]
    cumulative = np.r_[0., np.cumsum([r[0] for r in intervals])]
    def half_arc(u):
        j = min(int(np.searchsorted(knots, u, side='right')-1), len(knots)-2)
        return cumulative[j]+quad(speed, knots[j], u, epsabs=2e-14, epsrel=2e-13)[0]
    def exact_arc(t):
        return cumulative[-1]+np.sign(t)*half_arc(abs(float(t)))
    exact_nodes = np.array([exact_arc(ti) for ti in np.r_[t0, t1[-1]]])
    exact_length = 2*cumulative[-1]
    angles = np.arccos(np.clip(1-2*exact_nodes/exact_length, -1, 1))
    exact_sa = exact_length*(1-np.cos((angles[:-1]+angles[1:])/2))/2
    exact_t = np.array([brentq(lambda u:exact_arc(u)-s, a, b, xtol=5e-15) for a, b, s in zip(t0, t1, exact_sa)])
    exact_fraction = (exact_sa-exact_nodes[:-1])/np.diff(exact_nodes)
    exact_rm = r0+exact_fraction[:, None]*(r1-r0)
    exact_hv = exact_rm+.25*offset(exact_t)[:, None]*wind
    exact_cp = exact_hv+(slope(abs(exact_t))/(4*np.pi)*offset(exact_t))[:, None]*wind
    exact = dict(t=exact_t, rm=exact_rm, hv=exact_hv, cp=exact_cp, span=span(exact_t), chord=c(abs(exact_t)), ds=np.diff(exact_nodes))
    arc_changes = {k: float(np.max(abs(v-reconstructed[k]))) for k, v in exact.items()}
    # Independent projection identities quantify, rather than remove, off-line force points.
    segment = b-a
    projection = np.sum((hv-a)*segment, axis=1)/np.sum(segment*segment, axis=1)
    off = np.linalg.norm(hv-a-projection[:, None]*segment, axis=1)
    np.savez_compressed(stage/'geometry.npz', **reconstructed, normal=normal,
        theta0=theta0, theta1=theta1, sa=sa, fraction=fraction, chordal_arc=arc,
        arc_grid=grid, exact_arc_nodes=exact_nodes, exact_sa=exact_sa,
        **{'exact_'+k:v for k,v in exact.items()},
        force_point_projection=projection, force_point_offset=off,
        source_knots=x.t, source_axis=x.v, source_chord=c.v, source_slope=slope.v,
        axis_second=x.second, chord_second=c.second, slope_second=slope.second)
    report = dict(status='PASS_INDEPENDENT_GEOMETRY_RECONSTRUCTION', seconds=time.monotonic()-started,
        source_rows=len(x.t), errors=errors, chordal_axis_length=float(arc[-1]), exact_spline_axis_length=exact_length,
        length_error=float(arc[-1]-exact_length), adaptive_integral_error_sum=float(2*sum(v[1] for v in intervals)),
        same_nodes_exact_arc_changes=arc_changes,
        force_point_offset_max_m=float(off.max()), force_point_offset_to_length_max=float(np.max(off/np.linalg.norm(segment, axis=1))),
        force_point_projection_range=[float(projection.min()), float(projection.max())],
        normals_zero_alpha_exact=bool(np.array_equal(normal, np.tile([0.,0.,1.],(400,1)))),
        limitations=plan['limits'], new_equilibria=0, new_aero_residuals=0,
        sources_unchanged=all(pin(p['path'])==p for p in source_pins), arrays=pin(stage/'geometry.npz'), plan=pin(stage/'plan.json'))
    assert report['sources_unchanged']
    write(stage/'report.json', report)
    print(json.dumps({k: v for k, v in report.items() if k not in ('arrays', 'plan', 'limitations')}, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=Path, required=True)
    main(parser.parse_args().stage)
