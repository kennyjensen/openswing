"""Verify the symmetric fixed-fixed column subspace using a literal half model.

The full column has length 2L, midpoint mass 2m, clamps at both ends, and
equal compressive end forces P. Reflection about its midpoint gives a half
with a fixed root, rotation-fixed/free-to-translate tip and mass m. This
tests the first symmetric buckling mode; antisymmetric and fixture modes are
outside this model. No original ISAE/ASWING numerical export is claimed.

For each bending EI, q=sqrt(P/EI), a=qL and
k=Pq/(2tan(a/2)-a), lambda^2=-k/m. Endpoint-average integration of the
first-order equations replaces a inside tan by 2n atan(qL/(2n)), while the
subtracted qL is unchanged. Thus Pcr,n=EI*(2n/L*tan(pi/(2n)))^2.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import resource
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT/'examples/fixed-fixed-column-half.asw'
L = 1.
MASS = 1.
RIGIDITIES = {2: 100., 0: 200.}
GATES = dict(pole=2e-6, shape=2e-7, residual=1e-9, backward=1e-8,
             balance=1e-7, straight=1e-8, mass=1e-12)


def critical(ei=100., count=None):
    return ei*(math.pi/L if count is None else 2*count/L*math.tan(math.pi/(2*count)))**2


def stiffness(load, ei, count=None):
    if load == 0:
        return 12*ei/L**3/(1 if count is None else 1-1/count**2)
    q = math.sqrt(load/ei)
    a = q*L if count is None else 2*count*math.atan(q*L/(2*count))
    return load*q/(2*math.tan(a/2)-q*L)


def shapes(load, ei, count):
    """Exact discrete transverse displacement and rotation per unit tip motion."""
    displacement, rotation = [], []
    h = L/count
    for j in range(count+1):
        s = h*j
        if load == 0:
            den = L**3-L*h*h
            w = (3*L*s*s-2*s**3-h*h*s)/den
            theta = 6*s*(L-s)/den
        else:
            q = math.sqrt(load/ei)
            step = 2*math.atan(q*h/2)
            a, b = count*step, j*step
            den = 2*math.tan(a/2)-q*L
            w = (math.tan(a/2)*(1-math.cos(b))+math.sin(b)-q*s)/den
            theta = q*(math.tan(a/2)*math.sin(b)+math.cos(b)-1)/den
        displacement.append(w)
        rotation.append(theta)
    return displacement, rotation


def write(path, value):
    with Path(path).open('w') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(args):
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    load = args.ratio*critical(count=args.intervals if args.grid_critical else None)
    paths = [*sorted((ROOT/'openswing').glob('*.py')), MODEL, Path(__file__),
             ROOT/'.reference/asw_theory.pdf', ROOT/'.reference/asw_uns_theory.pdf']
    pins = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    request = dict(action='modes', mode='modes', source=MODEL.read_text(), condition=None,
        panels=dict(default=args.intervals, beams={'1':dict(count=args.intervals, spacing='uniform')}),
        numerics=dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-fixed-vacuum-v1'),
        modes=dict(frame='fixed', vacuum=True, count=4, shift=[-.02, 0.], method=args.method,
            step=1e-5, rank_tolerance=1e-9, matrices=False,
            position=[0., 0., 0.], attitude=[-90., 0., 0.], gravity_magnitude=load))
    write(out/'request.json', request)
    write(out/'plan.json', dict(arguments=vars(args), source_pins=pins, gates=GATES,
        load=load, continuous_critical_load=critical(), discrete_critical_load=critical(count=args.intervals),
        native_ASWING_validation=False, scope=__doc__, expected_cold_solves=1, expected_fresh_restores=1))
    started = time.monotonic()
    report = dict(status='RUNNING', native_ASWING_validation=False, goal_complete=False)
    try:
        import numpy as np
        from scipy.sparse import issparse, save_npz, csr_matrix, load_npz
        from scipy.sparse.linalg import norm as sparse_norm
        sys.path.insert(0, str(ROOT))
        import openswing.linear_dynamics as dynamics
        from openswing.bridge import dispatch
        from openswing.asw import parse_asw
        from openswing.source_dynamics import SourceDynamicNetwork
        from openswing.equilibrium_state import warm_start_recipe, restore
        from openswing.network import network_snapshot
        original = dynamics.linearize
        captured = []

        def retain(system, *a, **kw):
            assert not captured
            aa, mm = original(system, *a, **kw)
            save_npz(out/'A.npz', aa if issparse(aa) else csr_matrix(aa))
            save_npz(out/'M.npz', mm if issparse(mm) else csr_matrix(mm))
            captured.append(True)
            return aa, mm

        print(f'BEGIN symmetric fixed-fixed column n={args.intervals} P/Pcr={load/critical():.9g}', flush=True)
        dynamics.linearize = retain
        tick = time.monotonic()
        try:
            result = dispatch(request)
        finally:
            dynamics.linearize = original
        report['solve_seconds'] = time.monotonic()-tick
        write(out/'result.json', result)
        assert result['converged'] and result['base']['converged'] and len(result['modes']) == 4
        if args.method == 'dense':
            assert result['diagnostics']['finite_dimension'] == 4
        base = result['base']
        model = parse_asw(request['source'], beam_interpolation='drela-segspl-v1')
        saved = base['equilibrium_state']
        net = SourceDynamicNetwork(model, request['panels'], None, base['gravity_body'], [],
            mesh_recipe=warm_start_recipe(model, request['panels'], saved))
        state = restore(net, saved)
        assert net.nfev == 0
        zero = np.zeros_like(net.rj)
        residual, data = net.residual(state, detail=True, elastic_motion=(zero, zero, zero, zero),
            circulation_rate=np.zeros(net.circulation_basis.panels))
        assert net.nfev == 1
        fresh = network_snapshot(net, residual, data)
        write(out/'fresh-base.json', fresh)
        assert fresh['converged']
        assert fresh['structural_nodes'] == args.intervals+1 and fresh['structural_elements'] == args.intervals
        checks = dict(residual=float(np.max(abs(residual))),
            balance=max(float(np.linalg.norm(fresh[k])) for k in ('force_balance', 'moment_balance')),
            straight=max(float(np.linalg.norm(np.asarray(node['position'])-[0., L*j/args.intervals, 0.]))
                         for j, node in enumerate(fresh['nodes'])),
            mass=abs(fresh['mass_properties']['mass']-MASS), pole=0., shape=0., backward=0.)
        aa, mm = load_npz(out/'A.npz'), load_npz(out/'M.npz')
        na, nm = sparse_norm(aa, np.inf), sparse_norm(mm, np.inf)
        modes = []
        for mode in result['modes']:
            pole = complex(*mode['eigenvalue'])
            for side in ('right', 'left'):
                v = np.asarray(mode[side]['real'])+1j*np.asarray(mode[side]['imag'])
                diff = aa@v-pole*(mm@v) if side == 'right' else aa.T@v-pole.conjugate()*(mm.T@v)
                # Transposed matrices have different infinity norms.
                an, mn = (na, nm) if side == 'right' else (sparse_norm(aa.T, np.inf), sparse_norm(mm.T, np.inf))
                err = float(np.linalg.norm(diff, np.inf)/((an+abs(pole)*mn)*np.linalg.norm(v, np.inf)))
                checks['backward'] = max(checks['backward'], err)
            nodes = mode['output']['nodes']
            displacement = np.array([np.asarray(n['displacement']['real'])+1j*np.asarray(n['displacement']['imag']) for n in nodes])
            rotation = np.array([np.asarray(n['rotation']['real'])+1j*np.asarray(n['rotation']['imag']) for n in nodes])
            axis = int(np.argmax(abs(displacement[-1])))
            assert axis in RIGIDITIES
            scale = displacement[-1, axis]
            assert abs(scale) > 1e-15
            ei = RIGIDITIES[axis]
            k = stiffness(load, ei, args.intervals)
            target = complex(-k/MASS)**.5
            error = min(abs(pole-target), abs(pole+target))/max(1., abs(target))
            checks['pole'] = max(checks['pole'], error)
            w, theta = shapes(load, ei, args.intervals)
            expected_d = np.zeros((args.intervals+1, 3))
            expected_r = np.zeros_like(expected_d)
            expected_d[:, axis] = w
            expected_r[:, 0 if axis == 2 else 2] = np.array(theta)*(1 if axis == 2 else -1)
            shape_error = max(float(np.max(abs(displacement/scale-expected_d))),
                              float(np.max(abs(rotation/scale-expected_r))))
            checks['shape'] = max(checks['shape'], shape_error)
            continuous = abs(complex(-stiffness(load, ei)/MASS)**.5)
            modes.append(dict(axis=axis, eigenvalue=mode['eigenvalue'], stability=mode['stability'],
                continuum_magnitude=continuous, continuum_relative_error=abs(abs(pole)-continuous)/continuous,
                discrete_pole_error=error, discrete_shape_error=shape_error))
        assert sorted(m['axis'] for m in modes) == [0, 0, 2, 2]
        for axis in RIGIDITIES:
            poles = [complex(*m['eigenvalue']) for m in modes if m['axis'] == axis]
            assert abs(sum(poles)) <= GATES['pole']*max(1., abs(poles[0]))
        assert any(m['stability'] == 'unstable' for m in modes) == (load > critical(count=args.intervals))
        for name, value in checks.items():
            assert math.isfinite(value) and value <= GATES[name], (name, value, GATES[name])
        assert all(sha(ROOT/p) == value for p, value in pins.items())
        report.update(status='PASS_DISCRETE_ANALYTICAL_CHECK', checks=checks, modes=modes,
            independent_pencil_checks=8, shape_components=4*6*(args.intervals+1),
            source_pins_unchanged=True, finite_dimension=result['diagnostics'].get('finite_dimension'))
    except BaseException as error:
        report.update(status='FAILURE_RETAINED', error=repr(error), traceback=traceback.format_exc())
        raise
    finally:
        report.update(seconds=time.monotonic()-started,
            peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        write(out/'report.json', report)
        print(json.dumps({k:v for k,v in report.items() if k not in ('traceback', 'modes')}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output')
    parser.add_argument('--intervals', type=int, required=True)
    parser.add_argument('--ratio', type=float, required=True)
    parser.add_argument('--grid-critical', action='store_true')
    parser.add_argument('--method', choices=('dense', 'full_shift_invert'), default='full_shift_invert')
    args = parser.parse_args()
    if args.intervals < 2 or not math.isfinite(args.ratio) or args.ratio < 0:
        parser.error('At least two intervals and a finite nonnegative load ratio are required.')
    run(args)
