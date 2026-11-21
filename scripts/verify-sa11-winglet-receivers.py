"""Isolate whole-beam receiver sampling on the saved SA-11 winglet endpoints.

One bounded production call per --case. Four saved-Gamma force replays separate
receiver and circulation effects without clipping Mach or accepting bad loads.
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location('force_budget', ROOT/'scripts/audit-sa11-rejected-force-budget.py')
BUDGET = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUDGET)
INC = BUDGET.INC
from openswing.aero import AnalysisError, FlightCondition, evaluate_aerodynamics
from openswing.factored_influence import FactoredInfluence
from openswing.frozen_influence import lifting_geometry
from openswing.geometry import model_meshes
from openswing.ground import GroundPlane

PRIOR = ROOT/'artifacts/isae/sa11-rejected-force-budget-20261108'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_text())
utc = lambda: datetime.now(timezone.utc).isoformat()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def check(pins):
    for name, value in pins.items(): assert sha(ROOT/name) == value, name


def prepare(out):
    assert not out.exists(), out
    prior = read(PRIOR/'analysis.json'); previous = read(PRIOR/'plan.json')
    check(previous['current_pins']); check(prior['source_pins'])
    for name, value in prior['artifacts'].items(): assert sha(PRIOR/name) == value, name
    catalog = read(ROOT/'docs/validation/aswing-authoritative-sources.json')
    for item in catalog['files']: assert sha(ROOT/item['local_pdf']) == item['sha256']
    pins = dict(previous['current_pins'])
    for p in [Path(__file__), PRIOR/'analysis.json', PRIOR/'plan.json', PRIOR/'verification.json']:
        pins[str(p.relative_to(ROOT))] = sha(p)
    cases = [dict(id=f'whole-beam-a{angle}', alpha=float(angle), row=4*angle,
                  source_report=prior['cases'][4*angle]['source_report']) for angle in (0, 1)]
    out.mkdir(parents=True)
    write(out/'plan.json', dict(observed_utc=utc(), cases=cases, pins=pins,
        previous_turn='Progress: all21 saved force budgets show drag error beyond the local moment guard.',
        protocol='Keep original native64 endpoint grid, report-minus4 upper twist, original sections, speed240, PG240/340.21, frozen influences and stall40/.05. Change receivers to documented whole-beam Glauert sampling. Two fresh calls with unchanged Mach guard; no native AVL rerun.',
        reference='Drela steady Eqs.150-157, pp.31-33; full velocity/force laws Eqs.64-73, pp.15-17.',
        replay='Cross old/new receiver rules with old/new Gamma. Exact symmetric two-factor force difference partitions receiver and circulation effects, including the interaction equally.',
        limits='Native endpoints and report-derived input alternative are not authenticated archived settings. Rejected states supply only formal force diagnostics; no intrinsic moment or accepted loads. No primary count or original input changes.'))
    shutil.copyfile(__file__, out/'driver-used.py')
    print(json.dumps(dict(prepared=True, planned_physical_calls=2)), flush=True)


def replay(model, meshes, condition, gamma):
    """Reconstruct Eqs.64-70 independently from a prescribed discrete field."""
    g = lifting_geometry(meshes, np.array([1., 0., 0.]))
    span = np.concatenate([m.frames[..., 1] for m in meshes])
    normal = np.concatenate([np.sin(np.deg2rad(m.beam.value('alpha', m.tm)))[:, None]*m.frames[..., 0]
                 + np.cos(np.deg2rad(m.beam.value('alpha', m.tm)))[:, None]*m.frames[..., 2] for m in meshes])
    sample = lambda name: np.concatenate([m.beam.value(name, m.tm) for m in meshes])
    chord, cdf, cdp = [sample(name) for name in ('chord', 'Cdf', 'Cdp')]
    pg = np.diag([1/np.sqrt(1-condition.mach**2), 1., 1.]); n = len(gamma)
    direction = np.array([1., 0., 0.]); core = np.zeros((n, n))
    assert all(m.beam.physical_index == 1 for m in meshes)
    hv = FactoredInfluence(g['hv'], g['a'], g['b'], direction, pg, core, GroundPlane(), exclude_bound=np.eye(n, dtype=bool))
    cp = FactoredInfluence(g['cp'], g['a'], g['b'], direction, pg, core, GroundPlane())
    e, _, lift = condition.vectors()
    v = condition.speed*e+hv.apply(gamma)
    cp_velocity = condition.speed*e+cp.apply(gamma)
    vn = np.sum(cp_velocity*normal, axis=1)
    vp = v-np.sum(v*span, axis=1)[:, None]*span
    speed = np.linalg.norm(v, axis=1); normal_speed = np.linalg.norm(vp, axis=1)
    rho = 1.2256; width = g['ds']; scale = .5*rho*condition.speed**2*model.reference[0, 0]
    terms = np.stack([
        rho*gamma[:, None]*np.cross(v, span)*width[:, None],
        .5*rho*speed[:, None]*v*(chord*cdf*width)[:, None],
        .5*rho*normal_speed[:, None]*vp*(chord*cdp*width)[:, None],
        2*rho*vp/normal_speed[:, None]*(vn**2*chord*width)[:, None]], axis=1)
    scalar = BUDGET.scalar_forces(v, gamma, span, width, chord, cdf, cdp, vn)
    scalar_error = float(np.max(abs(scalar-terms))/scale)
    assert scalar_error < 2e-14
    cd, cl = terms@e/scale, terms@lift/scale
    mach = normal_speed/340.21
    rows = np.argmax(mach)
    beam = np.concatenate([np.full(len(m.tm), m.beam.index) for m in meshes])
    t = np.concatenate([m.tm for m in meshes])
    margin = np.minimum(sample('CLmax')-2*gamma/(chord*normal_speed), 2*gamma/(chord*normal_speed)-sample('CLmin'))
    record = dict(status='PRESCRIBED_FIELD_DIAGNOSTIC_NOT_AN_EQUILIBRIUM_ACCEPTANCE',
        formal_CL=float(cl.sum()), formal_CD=float(cd.sum()),
        CD_terms=dict(zip(['circulation','friction','pressure','stall'], map(float, cd.sum(axis=0)))),
        maximum_mach=float(mach.max()), mach_rejected_receivers=int(np.count_nonzero(mach >= 1)),
        maximum=dict(beam=int(beam[rows]), t=float(t[rows]), position=g['hv'][rows].tolist()),
        minimum_stall_margin_widths=float(margin.min()/condition.stall_width),
        maximum_tangency_over_freestream=float(np.max(abs(vn))/condition.speed),
        scalar_force_coefficient_error=scalar_error)
    arrays = dict(gamma=gamma, velocity=v, mach=mach, tangency=vn, force_terms=terms,
                  CL_terms=cl, CD_terms=cd, beam=beam, t=t, span=span, chord=chord, ds=width)
    return record, arrays


def run(out, index):
    plan = read(out/'plan.json'); check(plan['pins'])
    case = plan['cases'][index]; folder = out/case['id']; assert not folder.exists()
    old_report = read(ROOT/case['source_report']); old = (ROOT/case['source_report']).parent
    for name, pin in old_report['artifact_sha256'].items(): assert sha(old/name) == pin, name
    model = INC.model_at(-4.)
    with np.load(old/'native-fields.npz') as f: native = {k:f[k].copy() for k in f.files}
    with np.load(old/'diagnostic-state.npz') as d:
        old_gamma, old_velocity = d['gamma'].copy(), d['velocity'].copy()
    _, segments = INC.CONVERT.conversion(model, 1)
    old_meshes, old_geometry, _, settings = INC.CONVERT.mapped_meshes(model, native, segments)
    meshes = model_meshes(model, dict(default=16, beams=settings))
    g = lifting_geometry(meshes, np.array([1., 0., 0.]))
    assert len(g['hv']) == len(old_gamma) == 64
    endpoints = max(float(np.max(abs(g[k]-old_geometry[k]))) for k in ('a','b'))
    assert endpoints < 2e-14
    displacement = {k:float(np.max(np.linalg.norm(g[k]-old_geometry[k], axis=1))) for k in ('hv','cp')}
    condition = FlightCondition(speed=240., alpha=case['alpha'], mach=240/340.21, freeze_influences=True)
    folder.mkdir()
    write(folder/'condition.json', asdict(condition)); write(folder/'mesh-settings.json', settings)
    np.savez(folder/'geometry.npz', **g)
    def timeout(*_): raise TimeoutError('SA11 winglet receiver call exceeded15 seconds')
    old_alarm = signal.signal(signal.SIGALRM, timeout); signal.alarm(15)
    start = time.monotonic()
    try:
        try:
            result = evaluate_aerodynamics(model, condition, meshes)
        except AnalysisError as exc:
            assert exc.details and exc.details['kind'] == 'section_normal_mach', str(exc)
            tb = exc.__traceback__
            while tb and tb.tb_frame.f_code.co_name != 'evaluate_aerodynamics': tb = tb.tb_next
            assert tb is not None
            local = tb.tb_frame.f_locals
            gamma, v, cl = [local[k].copy() for k in ('gamma','v','cl')]
            state = dict(status='rejected', error=str(exc), details=exc.details,
                         residual=exc.details['circulation_residual'])
            write(folder/'openswing-rejected.json', state)
        else:
            write(folder/'openswing.json', result)
            gamma, v, cl = [np.array([s[k] for s in result['strips']]) for k in ('circulation','relative_velocity','cl')]
            state = dict(status='computed', residual=result['residual'],
                         result={k:result[k] for k in ('CL','CD','CDi','CDp','CDi_near','Cm_origin')})
        seconds = time.monotonic()-start
    finally:
        signal.alarm(0); signal.signal(signal.SIGALRM, old_alarm)
    assert state['residual'] < 1e-8
    np.savez(folder/'state.npz', gamma=gamma, velocity=v, cl=cl)
    cross_replay = {}; data = {}
    for receiver_name, receiver_meshes in [('native', old_meshes), ('whole', meshes)]:
        for gamma_name, value in [('old', old_gamma), ('new', gamma)]:
            label = f'{receiver_name}-{gamma_name}'
            cross_replay[label], data[label] = replay(model, receiver_meshes, condition, value)
            np.savez(folder/f'{label}.npz', **data[label])
    old_error = float(np.max(abs(data['native-old']['velocity']-old_velocity)))
    new_error = float(np.max(abs(data['whole-new']['velocity']-v)))
    assert max(old_error, new_error) < 3e-9
    assert cross_replay['whole-new']['minimum_stall_margin_widths'] > 0
    baseline = read(PRIOR/'analysis.json')['cases'][case['row']]
    for key in ('CL','CD'):
        assert abs(cross_replay['native-old'][f'formal_{key}']-baseline['formal_totals'][key]) < 2e-12
        if state['status'] == 'computed':
            assert abs(cross_replay['whole-new'][f'formal_{key}']-state['result'][key]) < 2e-12
    decomposition = {}
    for key in ('formal_CL', 'formal_CD'):
        a, b, c, d = [cross_replay[k][key] for k in ('native-old','whole-old','native-new','whole-new')]
        receiver = .5*((b-a)+(d-c)); circulation = .5*((c-a)+(d-b))
        assert abs(receiver+circulation-(d-a)) < 2e-16
        decomposition[key] = dict(change=d-a, receiver=receiver, circulation=circulation,
            receiver_share_percent=100*receiver/(d-a) if d != a else None)
    reference = baseline['reference']
    report = dict(observed_utc=utc(), case=case, production=state, physical_seconds=seconds,
        source_report=case['source_report'], source_report_sha256=sha(ROOT/case['source_report']),
        endpoint_max_error=endpoints, receiver_displacement=displacement,
        old_velocity_replay_error=old_error, new_velocity_replay_error=new_error,
        gamma_change_relative_linf=float(np.max(abs(gamma-old_gamma))/np.max(abs(old_gamma))),
        old_reference_error_percent=baseline['formal_total_error_percent'],
        new_formal_reference_error_percent={k:100*(cross_replay['whole-new'][f'formal_{k}']/reference[k]-1) for k in ('CL','CD')},
        reference=reference, replays=cross_replay, symmetric_decomposition=decomposition,
        warning='Formal forces for rejected states are diagnostic only. Cross-replays are not new equilibrium solves. No undefined local PG moment is evaluated.',
        artifact_sha256={p.name:sha(p) for p in sorted(folder.iterdir()) if p.is_file()})
    check(plan['pins']); write(folder/'report.json', report)
    print(json.dumps({k:report[k] for k in ('case','physical_seconds','endpoint_max_error','receiver_displacement','gamma_change_relative_linf','old_reference_error_percent','new_formal_reference_error_percent','symmetric_decomposition')}), flush=True)
    print(json.dumps(dict(status=state['status'], whole_receiver_field=cross_replay['whole-new'])), flush=True)


def summarize(out):
    plan = read(out/'plan.json'); check(plan['pins'])
    assert sha(out/'driver-used.py') == sha(Path(__file__))
    rows = []
    for case in plan['cases']:
        folder = out/case['id']; r = read(folder/'report.json')
        assert r['case'] == case
        for name, value in r['artifact_sha256'].items(): assert sha(folder/name) == value, name
        assert sha(ROOT/r['source_report']) == r['source_report_sha256']
        for label, record in r['replays'].items():
            with np.load(folder/f'{label}.npz') as data:
                for key in ('CL','CD'):
                    assert abs(float(data[f'{key}_terms'].sum())-record[f'formal_{key}']) < 1e-14
                assert float(data['mach'].max()) == record['maximum_mach']
        rows.append(r)
    assert not (out/'analysis.json').exists()
    result = dict(observed_utc=utc(), cases=rows, physical_calls=2,
        physical_seconds=sum(r['physical_seconds'] for r in rows),
        report_pins={str((out/r['case']['id']/'report.json').relative_to(ROOT)):sha(out/r['case']['id']/'report.json') for r in rows},
        scope='Two report-derived diagnostic states on native endpoint grid. No original input, production law, guard, primary pass or scope change.')
    write(out/'analysis.json', result)
    print(json.dumps(dict(physical_calls=2, physical_seconds=result['physical_seconds'],
        statuses=[r['production']['status'] for r in rows],
        whole_receiver_mach=[r['replays']['whole-new']['maximum_mach'] for r in rows],
        whole_receiver_formal_errors=[r['new_formal_reference_error_percent'] for r in rows])), flush=True)


def main():
    assert all(os.environ.get(k) == '1' for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'))
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output', type=Path, required=True)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--prepare', action='store_true'); g.add_argument('--case', type=int, choices=[0,1]); g.add_argument('--summarize', action='store_true')
    a = p.parse_args(); out = a.output.resolve()
    if a.prepare: prepare(out)
    elif a.summarize: summarize(out)
    else: run(out, a.case)


if __name__ == '__main__': main()
