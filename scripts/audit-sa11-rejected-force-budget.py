"""Decompose formal force sums in saved, rejected SA-11 states; no solves.

All 21 report-minus4 states are retained. These algebraic sums do not bypass
the local-Mach guard or constitute accepted aerodynamic predictions.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from openswing.factored_influence import FactoredInfluence
from openswing.ground import GroundPlane

SPEC = importlib.util.spec_from_file_location('incidence', ROOT/'scripts/verify-sa11-winglet-incidence.py')
INC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INC)
BASE = ROOT/'artifacts/isae/sa11-winglet-polar-20261108'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_text())
utc = lambda: datetime.now(timezone.utc).isoformat()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def scalar_forces(v, gamma, span, ds, chord, cdf, cdp, tangency):
    """Independent scalar cross/projection and accurate reduction, no np.cross."""
    rows = []
    for velocity, circulation, s, width, c, cf, cp, vn in zip(v, gamma, span, ds, chord, cdf, cdp, tangency):
        dot = math.fsum(float(x)*float(y) for x, y in zip(velocity, s))
        vp = [float(x)-dot*float(y) for x, y in zip(velocity, s)]
        speed = math.hypot(*velocity); normal_speed = math.hypot(*vp)
        cross = [velocity[1]*s[2]-velocity[2]*s[1], velocity[2]*s[0]-velocity[0]*s[2], velocity[0]*s[1]-velocity[1]*s[0]]
        rows.append([[circulation*float(x)*width for x in cross],
                     [.5*speed*float(x)*c*cf*width for x in velocity],
                     [.5*normal_speed*x*c*cp*width for x in vp],
                     [2*x/normal_speed*vn**2*c*width for x in vp]])
    return np.asarray(rows)*1.2256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); out = args.output.resolve()
    if out.exists(): parser.error('Use a fresh output directory.')
    previous = read(BASE/'plan.json')
    changes = {}
    allowed = {'openswing/airflow_diagnostics.py', 'openswing/bridge.py',
               'docs/validation/ISAE_STATUS.md', 'docs/validation/isae-progress-scopes.json'}
    for name, old in previous['unchanged_pins'].items():
        current = sha(ROOT/name)
        if current != old:
            assert name in allowed, name
            changes[name] = dict(previous=old, current=current)
    catalog = read(ROOT/'docs/validation/aswing-authoritative-sources.json')
    for item in catalog['files']:
        assert sha(ROOT/item['local_pdf']) == item['sha256']
    cases = [c for c in previous['cases'] if c['twist'] == -4.]
    assert [c['row'] for c in cases] == list(range(21))
    current_pins = {str(p.relative_to(ROOT)): sha(p) for p in sorted((ROOT/'openswing').glob('*.py'))}
    current_pins.update({str(p.relative_to(ROOT)): sha(p) for p in [
        Path(__file__), ROOT/'scripts/verify-sa11-winglet-incidence.py',
        ROOT/'scripts/audit-sa11-avl-conversion.py', BASE/'plan.json', BASE/'analysis.json',
        ROOT/'examples/isae-sa11-wingtip-up.asw', ROOT/'docs/validation/aswing-authoritative-sources.json']})
    out.mkdir(parents=True)
    shutil.copyfile(__file__, out/'driver-used.py')
    write(out/'plan.json', dict(observed_utc=utc(), cases=cases, current_pins=current_pins,
        previous_pin_changes=changes,
        prior_changes_scope='Diagnostic observer/worker transport and tracked status/scope changed since saved fields; aerodynamic modules and original geometry remain pinned.',
        reference_equations='Drela steady Eqs.64-70, pp.15-16; bound-point velocity and beam span. AVL aero.f uses bound-segment vector.',
        scope='Formal force sums from all21 rejected report-minus4 fields, alpha0..5. No new circulation solve, accepted loads, intrinsic moment, parameter adjustment or primary pass.',
        partition='Whole aircraft, each logical beam, and all receivers with section-normal Mach >=1. No receiver is removed.'))
    model = INC.model_at(-4.)
    _, segments = INC.CONVERT.conversion(model, 1)
    table_path = INC.FOLDER/'Aswing_Simulations/Wing_tip_up/wingtip_up_Ma_0_70.txt'
    table = np.loadtxt(table_path)
    source_pins = {str(table_path.relative_to(ROOT)): sha(table_path)}
    rows = []; field_error = scalar_error = native_error = 0.
    for case in cases:
        rp = ROOT/case['reused_report'] if 'reused_report' in case else BASE/case['id']/'report.json'
        if 'reused_sha256' in case: assert sha(rp) == case['reused_sha256']
        report = read(rp); source_pins[str(rp.relative_to(ROOT))] = sha(rp)
        for name, digest in report['artifact_sha256'].items():
            assert sha(rp.parent/name) == digest, name
        assert report['production']['status'] == 'rejected'
        assert report['production']['details']['kind'] == 'section_normal_mach'
        assert report['production']['residual'] < 1e-8 and report['minimum_stall_margin_widths'] > 10
        with np.load(rp.parent/'native-fields.npz') as f:
            fields = {k: f[k].copy() for k in f.files}
        with np.load(rp.parent/'diagnostic-state.npz') as d:
            gamma, v = d['gamma'].copy(), d['velocity'].copy()
        meshes, g, errors, settings = INC.CONVERT.mapped_meshes(model, fields, segments)
        assert max(errors.values()) < 2e-11
        span = np.concatenate([m.frames[..., 1] for m in meshes])
        beam = np.concatenate([np.full(len(m.tm), m.beam.index) for m in meshes])
        sample = lambda name: np.concatenate([m.beam.value(name, m.tm) for m in meshes])
        chord, cdf, cdp = [sample(name) for name in ('chord', 'Cdf', 'Cdp')]
        normal = np.concatenate([np.sin(np.deg2rad(m.beam.value('alpha', m.tm)))[:, None]*m.frames[..., 0]
                    + np.cos(np.deg2rad(m.beam.value('alpha', m.tm)))[:, None]*m.frames[..., 2] for m in meshes])
        angle = np.deg2rad(case['alpha']); e = np.array([np.cos(angle), 0., np.sin(angle)])
        lift = np.array([-np.sin(angle), 0., np.cos(angle)])
        pg = np.diag([1/np.sqrt(1-(240/340.21)**2), 1., 1.])
        n = len(gamma); core = np.zeros((n, n)); direction = np.array([1., 0., 0.])
        hv_op = FactoredInfluence(g['hv'], g['a'], g['b'], direction, pg, core,
                                  GroundPlane(), exclude_bound=np.eye(n, dtype=bool))
        reconstructed = 240*e+hv_op.apply(gamma)
        discrepancy = float(np.max(abs(reconstructed-v))); field_error = max(field_error, discrepancy)
        assert discrepancy < 3e-9
        cp_op = FactoredInfluence(g['cp'], g['a'], g['b'], direction, pg, core, GroundPlane())
        tangency = np.sum((240*e+cp_op.apply(gamma))*normal, axis=1)
        vp = v-np.sum(v*span, axis=1)[:, None]*span
        speed, normal_speed = np.linalg.norm(v, axis=1), np.linalg.norm(vp, axis=1)
        mach = normal_speed/340.21; failed = mach >= 1
        assert failed.any()
        assert abs(mach.max()-report['production']['maximum_section_normal_mach']) < 1e-12
        rho = 1.2256; width = g['ds']; scale = .5*rho*240**2*float(model.reference[0, 0])
        forces = np.stack([
            rho*gamma[:, None]*np.cross(v, span)*width[:, None],
            .5*rho*speed[:, None]*v*(chord*cdf*width)[:, None],
            .5*rho*normal_speed[:, None]*vp*(chord*cdp*width)[:, None],
            2*rho*vp/normal_speed[:, None]*(tangency**2*chord*width)[:, None]], axis=1)
        independent = scalar_forces(v, gamma, span, width, chord, cdf, cdp, tangency)
        discrepancy = float(np.max(abs(forces-independent))/scale)
        scalar_error = max(scalar_error, discrepancy); assert discrepancy < 2e-14
        cd, cl = forces@e/scale, forces@lift/scale
        native_force = np.sum(2*fields['GAM']*np.cross(fields['VINF']+fields['VV'], fields['RV2']-fields['RV1']), axis=0)/model.reference[0, 0]
        discrepancy = max(abs(native_force@e-report['native']['CD_near']), abs(native_force@lift-report['native']['CL']))
        native_error = max(native_error, float(discrepancy)); assert discrepancy < 1e-12
        prod_bound_force = rho*np.sum(gamma[:, None]*np.cross(v, g['b']-g['a']), axis=0)/scale
        names = ['circulation', 'friction', 'pressure', 'stall']
        def budget(mask):
            return dict(strips=int(np.count_nonzero(mask)),
                area_fraction=float(np.sum((chord*width)[mask])/np.sum(chord*width)),
                CD={name:float(np.sum(cd[mask, k])) for k, name in enumerate(names)},
                CL={name:float(np.sum(cl[mask, k])) for k, name in enumerate(names)})
        ref = dict(CL=float(table[case['row'], 77]), CD=float(table[case['row'], 78]), CDi=float(table[case['row'], 79]))
        assert ref == report['reference']
        total = dict(CL=float(cl.sum()), CD=float(cd.sum()))
        rows.append(dict(case=case, status='REJECTED_STATE_FORMAL_FORCE_BUDGET', reference=ref,
            native=report['native'], formal_totals=total,
            formal_total_error_percent={k:100*(total[k]/ref[k]-1) for k in total},
            full_budget=budget(np.ones(n, dtype=bool)), mach_rejected_receivers=budget(failed),
            by_beam={str(i):budget(beam == i) for i in np.unique(beam)},
            maximum_local_mach=float(mach.max()),
            production_field_using_bound_segment=dict(CL=float(prod_bound_force@lift), CD_near=float(prod_bound_force@e)),
            minimum_stall_margin_widths=report['minimum_stall_margin_widths'],
            source_report=str(rp.relative_to(ROOT))))
        np.savez(out/f"row{case['row']:02d}.npz", beam=beam, gamma=gamma, velocity=v,
                 mach=mach, force_terms=forces, CD_terms=cd, CL_terms=cl, tangency=tangency)
    assert len(rows) == 21
    for name, pin in current_pins.items(): assert sha(ROOT/name) == pin, name
    summary = dict(cases=len(rows), new_solves=0, maximum_velocity_replay_error=field_error,
        maximum_scalar_force_coefficient_error=scalar_error, maximum_native_force_coefficient_error=native_error,
        formal_total_error_percent={key:[min(r['formal_total_error_percent'][key] for r in rows),
                                        max(r['formal_total_error_percent'][key] for r in rows)] for key in ('CL', 'CD')},
        rejected_receiver_count=[min(r['mach_rejected_receivers']['strips'] for r in rows),max(r['mach_rejected_receivers']['strips'] for r in rows)],
        rejected_receiver_area_fraction=[min(r['mach_rejected_receivers']['area_fraction'] for r in rows),max(r['mach_rejected_receivers']['area_fraction'] for r in rows)])
    write(out/'analysis.json', dict(observed_utc=utc(), summary=summary, cases=rows, source_pins=source_pins,
        validity='All states remain rejected. Formal force sums are algebraic diagnostics, not accepted loads; local PG moment is undefined and not evaluated.',
        artifacts={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()}))
    print(json.dumps(summary))


if __name__ == '__main__': main()
