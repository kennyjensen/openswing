"""Static self-weight buckling with full source equations and an Airy reference.

Only the straight clamped/free uniform line-mass column is in scope. Reuse the
full zero-load and loaded static Jacobians after checking physical load scaling.
No degrees of freedom are truncated; this is not a dynamic-spectrum audit.
"""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run(args):
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    paths = [*sorted((ROOT/'openswing').glob('*.py')), Path(__file__),
        ROOT/'scripts/self_weight_column_reference.py', ROOT/'examples/self-weight-column.asw']
    pins = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    gates = dict(base=1e-9, straight=1e-10, preload=1e-10, backward=1e-8,
        action=1e-7, load_correction=1e-7, continuum_critical=.001, continuum_shape=.001)
    write(out/'plan.json', dict(arguments=vars(args), gates=gates, pins=pins,
        load_anchor=500., coordinate_scales='held at zero-load construction',
        native_ASWING_validation=False, scope=__doc__))
    started = time.monotonic()
    report = dict(status='RUNNING', native_ASWING_validation=False, goal_complete=False)
    try:
        import numpy as np
        from scipy.linalg import eig
        from scipy.sparse import save_npz
        from scipy.sparse.linalg import LinearOperator, eigs, splu, norm
        from openswing.asw import parse_asw
        from openswing.source_dynamics import SourceDynamicNetwork
        from openswing.structured_static import jacobian
        from self_weight_column_reference import critical, shapes
        model = parse_asw((ROOT/'examples/self-weight-column.asw').read_text(),
                          beam_interpolation='drela-segspl-v1')
        panels = dict(default=args.intervals, beams={'1': dict(count=args.intervals, spacing='uniform')})
        n = SourceDynamicNetwork(model, panels, None, [0., 0., 0.], [])
        assert n.ng == 0 and n.size == n.gamma_start
        zero = np.zeros(n.size)
        a0, setup0 = jacobian(n, zero, 1.)
        a0 = a0.mechanical
        factor = splu(a0)
        midpoint = (n.rj[n.a, 1]+n.rj[n.b, 1])/2
        bases = []

        def base(gravity):
            n.gravity = np.array([0., -gravity, 0.])
            n.aero_key = None
            # At the straight geometry, axial forces/reactions are exactly
            # linear in gravity. The full zero-load solve determines them;
            # fresh nonlinear residuals and physical preload verify the state.
            state = factor.solve(-n.residual(zero))
            residual, data = n.residual(state, detail=True)
            actual = data['source_discrete']['force_local']
            expected = np.zeros_like(actual)
            expected[:, 1] = -gravity*(1-midpoint)
            row = dict(gravity=gravity, residual=float(np.max(abs(residual))),
                straight=float(np.max(abs(data['r']-n.rj))),
                preload=float(np.max(abs(actual-expected)))/max(1., gravity))
            assert row['residual'] <= gates['base'] and row['straight'] <= gates['straight'] and row['preload'] <= gates['preload'], row
            bases.append(row)
            return state

        anchor = 500.
        state = base(anchor)
        ag, setupg = jacobian(n, state, 1.)
        kg = (ag.mechanical-a0)/anchor
        save_npz(out/'A0.npz', a0)
        save_npz(out/'gravity-tangent.npz', kg)
        if args.method == 'dense':
            values, lefts, rights = eig(a0.toarray(), -kg.toarray(), left=True, right=True)
            candidates = [i for i,z in enumerate(values) if np.isfinite(z) and z.real > 0
                          and abs(z.imag) < 1e-8*abs(z.real)]
            index = min(candidates, key=lambda i: values[i].real)
            gravity = float(values[index].real)
            right, left = rights[:, index], lefts[:, index]
        else:
            operator = LinearOperator(a0.shape, matvec=lambda x: -factor.solve(kg@x), dtype=float)
            values, vectors = eigs(operator, k=4, which='LR', tol=1e-12,
                                  v0=np.linspace(1., 2., n.size), maxiter=10000)
            candidates = [i for i,z in enumerate(values) if z.real > 0 and abs(z.imag) < 1e-8*abs(z.real)]
            index = max(candidates, key=lambda i: values[i].real)
            gravity = float(1/values[index].real)
            right = vectors[:, index]
            adjoint = LinearOperator(a0.shape, matvec=lambda x: -factor.solve(kg.T@x, trans='T'), dtype=float)
            lvalues, lvectors = eigs(adjoint, k=4, which='LR', tol=1e-12,
                                    v0=np.linspace(2., 1., n.size), maxiter=10000)
            left = lvectors[:, np.argmin(abs(lvalues-1/gravity))]
        right = right/right[6*(n.nn-1)+2]
        left = left/left[np.argmax(abs(left))]
        assert np.max(abs(right.imag)) <= 1e-8*max(1., np.max(abs(right.real)))
        right = right.real
        matrix = a0+gravity*kg
        backward = float(np.max(abs(matrix@right))/(norm(matrix,np.inf)*np.max(abs(right))))
        left_backward = float(np.max(abs(matrix.T@left))/(norm(matrix.T,np.inf)*np.max(abs(left))))
        assert max(backward,left_backward) <= gates['backward']
        sensitivity = kg@right
        den = np.vdot(left.astype(np.clongdouble), sensitivity.astype(np.clongdouble))
        assert np.isfinite(den) and abs(den)>0
        state = base(gravity)
        probes = []
        for h in (1e-3,3e-4,1e-4,3e-5,1e-5):
            action = (n.residual(state+h*right)-n.residual(state-h*right))/(2*h)
            correction = -np.vdot(left.astype(np.clongdouble),action.astype(np.clongdouble))/den
            probes.append(dict(step=h, equivalent_gravity_correction=float(correction.real),
                relative_gravity_correction=float(abs(correction)/gravity),
                normwise_error=float(np.max(abs(action))/(norm(matrix,np.inf)*np.max(abs(right))))))
        assert all(p['relative_gravity_correction'] <= gates['load_correction'] and p['normwise_error'] <= gates['backward'] for p in probes[-2:])
        scaling = []
        smooth = np.zeros(n.size)
        smooth[:6*n.nn].reshape(n.nn,6)[:,2] = n.rj[:,1]**2
        smooth[:6*n.nn].reshape(n.nn,6)[:,3] = .3*n.rj[:,1]
        for g in (.5*gravity,.9999*gravity,1.0001*gravity):
            state = base(g)
            for label,v in (('critical',right),('smooth',smooth)):
                h = 1e-7
                measured = (n.residual(state+h*v)-n.residual(state-h*v))/(2*h)
                expected = a0@v+g*(kg@v)
                error = float(np.max(abs(measured-expected))/max(1.,np.max(abs(expected))))
                assert error <= gates['action'], (g,label,error)
                scaling.append(dict(gravity=g,direction=label,error=error))
        w, theta = shapes(n.rj[:,1])
        expected = np.zeros((n.nn,6))
        expected[:,2],expected[:,3] = w,theta
        physical = right[:6*n.nn].reshape(n.nn,6).copy()
        physical[:,:3] *= n.L
        shape_error = float(np.max(abs(physical-expected))/max(1.,np.max(abs(expected))))
        root_error = abs(gravity/critical()-1)
        np.savez_compressed(out/'critical-mode.npz',right=right,left=left,reference_shape=expected,
                            physical_shape=physical,stations=n.rj[:,1])
        assert all(sha(ROOT/p) == value for p,value in pins.items())
        report.update(status='PASS_DISCRETE_STATIC_CHECK', gravity=gravity,
            continuum_gravity=critical(), continuum_relative_error=root_error,
            continuum_shape_error=shape_error,
            continuum_pass=root_error<=gates['continuum_critical'] and shape_error<=gates['continuum_shape'],
            right_backward=backward,left_backward=left_backward,base_checks=bases,
            directional_probes=probes,gravity_scaling=scaling,
            jacobian_evaluations=[setup0['evaluations'],setupg['evaluations']],
            residual_evaluations=n.nfev,force_scale=n.F,length_scale=n.L,
            method=args.method,static_unknowns=n.size)
    except BaseException as error:
        report.update(status='FAILURE_RETAINED',error=repr(error),traceback=traceback.format_exc())
        raise
    finally:
        report.update(seconds=time.monotonic()-started,
            peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        write(out/'report.json',report)
        print(json.dumps({k:v for k,v in report.items() if k not in ('traceback','base_checks','directional_probes','gravity_scaling')}),flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output')
    parser.add_argument('--intervals',type=int,required=True)
    parser.add_argument('--method',choices=['dense','sparse'],default='sparse')
    args=parser.parse_args()
    if args.intervals<4:parser.error('At least four intervals are required.')
    run(args)
