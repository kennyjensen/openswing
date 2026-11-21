"""Cheap full-residual differentiation checks at retained ST-4 eigenvectors.

No equilibrium solve, Jacobian assembly or eigensolver is run. Historical
matrices/vectors are source-pinned evidence; current equations are evaluated
fresh at restored physical bases and along each real modal direction.
"""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]


def run(args):
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    folder = ROOT/'artifacts/isae/st4-critical-refinement-20261104'/f'public{args.speed.replace(".","p")}_n160'
    paths = [folder/p for p in ['request.json','result.json','A.npz','M.npz','job.json','execution.json']]
    paths += [*sorted((ROOT/'openswing').glob('*.py')),Path(__file__),ROOT/'scripts/modal_directional_check.py']
    def sha(p):
        with p.open('rb') as f:
            return hashlib.file_digest(f,'sha256').hexdigest()
    pins = {str(p.relative_to(ROOT)):sha(p) for p in paths}
    steps = [1e-3,3e-4,1e-4,3e-5,1e-5,3e-6]
    selected = [4,1] if args.speed == '139.5' else [4]
    (out/'plan.json').write_text(json.dumps(dict(pins=pins,steps=steps,modes=selected,
        interpretation='Directional and first-order eigenvalue sensitivity diagnostics, not replacement eigenvalues or native validation.'),indent=2)+'\n')
    start = time.monotonic()
    import numpy as np
    from scipy.sparse import load_npz
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition
    from openswing.source_airflow import SourceAirflowNetwork
    from openswing.equilibrium_state import restore, warm_start_recipe
    from openswing.linear_dynamics import DynamicSystem
    from modal_directional_check import actions, projected_correction
    request, result = [json.loads((folder/p).read_text()) for p in ('request.json','result.json')]
    saved = result['base']['equilibrium_state']
    model = parse_asw(request['source'],beam_interpolation=request['numerics']['beam_interpolation'])
    condition = FlightCondition(**request['condition'])
    net = SourceAirflowNetwork(model,request['panels'],condition,None,[],
                              mesh_recipe=warm_start_recipe(model,request['panels'],saved))
    state = restore(net,saved)
    assert net.nfev == 0
    system = DynamicSystem(net,state,frame=request['modes']['frame'])
    layout = result['diagnostics']['state_layout']
    assert net.size == layout['network_size'] and net.nn == layout['nodes']
    assert net.F == layout['internal_loads']['force_scale']
    assert net.L == layout['node_coordinates']['translation_scale']
    assert system.V == layout['local_velocity']['scale'] and system.W == layout['local_rates']['scale']
    def forbidden(*a,**kw):
        raise AssertionError('Directional verification must not assemble a Jacobian or solve equilibrium.')
    net.jacobian = forbidden
    zero = np.zeros(system.size)
    base_residual = float(np.max(abs(system.residual(zero,zero))))
    assert base_residual <= 1e-9
    a,m = [load_npz(folder/(key+'.npz')) for key in ('A','M')]
    assert a.shape == m.shape == (system.size,system.size)
    report = dict(status='RUNNING',native_ASWING_validation=False,goal_complete=False,
                  speed=float(args.speed),base_residual=base_residual,modes=[])
    for index in selected:
        mode = result['modes'][index]
        pole = complex(*mode['eigenvalue'])
        v = np.asarray(mode['right']['real'])+1j*np.asarray(mode['right']['imag'])
        w = np.asarray(mode['left']['real'])+1j*np.asarray(mode['left']['imag'])
        pivot = int(np.argmax(abs(v[:6*net.nn])))
        v /= v[pivot]
        w /= np.max(abs(w))
        av,mv = a@v,m@v
        backward = float(np.linalg.norm(av-pole*mv)/(np.linalg.norm(av)+abs(pole)*np.linalg.norm(mv)))
        assert backward < 1e-8
        left_error = np.linalg.norm(a.T@w-pole.conjugate()*(m.T@w))/(np.linalg.norm(a.T@w)+abs(pole)*np.linalg.norm(m.T@w))
        assert left_error < 1e-8
        record = dict(index=index,pole=[pole.real,pole.imag],pivot=pivot,
            saved_right_action_error=backward,saved_left_action_error=float(left_error),samples=[])
        aa,mm = [],[]
        for h in steps:
            ap,mp = actions(system.residual,v,h)
            defect = ap-pole*mp
            correction = projected_correction(w,mp,defect)
            sample = dict(step=h,A_action_relative_error=float(np.linalg.norm(ap-av)/np.linalg.norm(av)),
                M_action_relative_error=float(np.linalg.norm(mp-mv)/np.linalg.norm(mv)),
                nonlinear_mode_action_error=float(np.linalg.norm(defect)/(np.linalg.norm(ap)+abs(pole)*np.linalg.norm(mp))),
                first_order_pole_correction=[correction.real,correction.imag])
            record['samples'].append(sample);aa.append(ap);mm.append(mp)
            print(json.dumps(dict(mode=index,**sample)),flush=True)
        report['modes'].append(record)
        np.savez_compressed(out/f'mode-{index}-actions.npz',right=v,left=w,steps=steps,
                            A_actions=np.asarray(aa),M_actions=np.asarray(mm),saved_A_action=av,saved_M_action=mv)
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    assert all(sha(ROOT/p)==digest for p,digest in pins.items())
    report.update(status='COMPLETE_DIRECTIONAL_DIAGNOSTIC',evaluations=net.nfev,
        seconds=time.monotonic()-start,peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='modes'}),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output')
    parser.add_argument('--speed',choices=['120.5','139.5'],required=True)
    run(parser.parse_args())
