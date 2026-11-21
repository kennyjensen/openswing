"""Four isolated zero-angle SA-14 setup diagnostics; no primary pass updates."""
import argparse
import json
from pathlib import Path
import resource
import time

import verify_sa14_defaults as common

ROOT = common.ROOT


def run(out, variant):
    plan_path = ROOT / 'artifacts/isae/sa14-current-polar-20261109/plan.json'
    plan = common.read(plan_path)
    common.authenticate(plan['pins'])
    job = plan['jobs'][0]
    source = (ROOT / job['model_path']).read_text()
    sources_path = ROOT / 'docs/validation/isae-sa14-sources.json'
    exports_path = ROOT / 'docs/validation/isae-sa14-load-exports.json'
    sources, exports = common.read(sources_path), common.read(exports_path)
    export = next(e for e in exports['exports']
                  if e['case'] == 'wing_body' and e['parameters']['alpha']['value'] == 4.7)
    original = ROOT / 'reference/isae-validation' / sources['revision'] / export['source_path']
    assert common.sha(original) == export['source_sha256'] == sources['files'][export['source_path']]['sha256']
    lines = original.read_text().splitlines()
    for table in export['tables']:
        for row in table['rows']:
            assert lines[row['source_line'] - 1].split() == [row['fields'][k]['token'] for k in ('t', 'y', 'chord', 'cl')]

    # Limits have already been installed before production/scientific imports.
    import numpy as np
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition, solve_rigid
    from openswing.geometry import model_meshes
    from scripts.isae_suite_polars import reconstructed_wrench

    policy = 'drela-segspl-v1' if variant == 'segspl' else 'natural-v1'
    if variant == 'flat-middle':
        # A disclosed alternative geometry, not a parser correction. Duplicate
        # the two plateau ends to separate cubic segments; retain every value.
        selected = ('31.04306820194863', '83.66803070563921')
        in_radius = False
        changed = []
        count = 0
        for line in source.splitlines(keepends=True):
            if 'radius' in line and not line.lstrip().startswith('#'):
                in_radius = True
            if line.strip().lower() == 'end':
                in_radius = False
            changed.append(line)
            if in_radius and line.split() and line.split()[0] in selected:
                changed.append(line)
                count += 1
        assert count == 2
        source = ''.join(changed)
    model = parse_asw(source, beam_interpolation=policy)
    body = next(b for b in model.beams if not b.lifting)
    joint = float(model.records['joint'][0][2])
    assert joint == 1.07
    body_nodes = np.r_[np.linspace(body.domain[0], joint, 7),
                       np.linspace(joint, body.domain[1], 13)[1:]]
    body_printed = np.insert(body_nodes, 7, joint)
    body_matches = [abs(x - r['fields']['t']['value']) <= r['fields']['t']['half_last_place']
                    for x, r in zip(body_printed, export['tables'][0]['rows'], strict=True)]
    assert all(body_matches)
    mesh_spec = dict(default=64, beams={'1': dict(nodes=body_nodes.tolist()),
                                     '2': dict(count=78, spacing='modified-cosine')})
    wing = next(m for m in model_meshes(model, mesh_spec) if m.beam.lifting)
    wing_printed = np.insert(np.r_[wing.t0, wing.t1[-1]], 40, 0.)
    wing_differences = [dict(row=i, predicted=float(x), token=r['fields']['t']['token'],
        excess=float(abs(x-r['fields']['t']['value'])-r['fields']['t']['half_last_place']))
        for i, (x, r) in enumerate(zip(wing_printed, export['tables'][1]['rows'], strict=True))
        if abs(x-r['fields']['t']['value']) > r['fields']['t']['half_last_place'] + 1e-12]
    assert [r['row'] for r in wing_differences] == [39, 40]
    assert max(r['excess'] for r in wing_differences) < 2.18e-7
    panels = mesh_spec if variant == 'export-mesh' else (
        dict(default=64, beams={'1': dict(nodes=body_nodes.tolist())}) if variant == 'body-mesh' else 64)
    grid = np.linspace(31.04306820194863*.0254, 83.66803070563921*.0254, 1001)
    radii = body.value('radius', grid)
    s = job['settings']
    condition = FlightCondition(**{k: s[k] for k in ('speed', 'alpha', 'beta', 'density', 'mach',
        'freeze_influences', 'stall', 'stall_factor', 'stall_width', 'wake_core_ratio', 'aero_lag', 'body_added_mass_factor')})
    started = time.monotonic()
    result = solve_rigid(model, condition, panels=panels)
    force, moment, _ = reconstructed_wrench(model, result)
    assert not model.diagnostics and result['converged'] and result['residual'] < 1e-8
    assert max(abs(force-result['force'])) < 2e-10
    assert max(abs(moment-result['moment'])) < 2e-10
    assert abs(force[2]/(.5*s['density']*s['speed']**2*model.reference[0,0])-result['CL']) < 2e-12
    folder = out / variant
    folder.mkdir()
    (folder / 'model.asw').write_text(source)
    common.write(folder / 'physical-result.json', result)
    baseline_path = ROOT / 'artifacts/isae/sa14-current-polar-20261109/job-00/physical-result.json'
    baseline = common.read(baseline_path)
    expected = job['reference_row']['fields']['CL']['value']
    report = dict(observed_utc=common.utc(), variant=variant, policy=policy, panels=panels,
        baseline_cl=baseline['CL'], current_cl=result['CL'], archived_cl=expected,
        delta_from_baseline=result['CL']-baseline['CL'], absolute_error=result['CL']-expected,
        residual=result['residual'], numerical_force_checks=True,
        actual_mesh={str(b['beam']):b['panels'] for b in result['mesh_discretization']['beams']},
        radius_plateau=dict(tabulated_radius=6.352488928255092*.0254,
            minimum=float(radii.min()), maximum=float(radii.max())),
        source_coordinate_checks=dict(body_rows_matched=int(sum(body_matches)), body_rows=20,
            wing_nonroot_rows_matched=78, wing_rows=80, root_discrepancies=wing_differences),
        source_model_modified=variant == 'flat-middle', physical_calls=1, primary_passes_added=0,
        seconds=time.monotonic()-started, peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        pins={p.relative_to(ROOT).as_posix():common.sha(p) for p in (
            Path(__file__), plan_path, sources_path, exports_path, original, baseline_path)},
        production_pins_verified=len(plan['pins']),
        artifacts={p.name:common.sha(p) for p in folder.iterdir()},
        qualification='Diagnostic only. Coarse body/modified-cosine wing nodes are inferred from a different-angle local export, not authenticated polar nodes. '
            'The flat-middle case deliberately changes radius slope breaks to enforce the reported cylindrical middle; original geometry and primary comparisons remain unchanged.')
    common.write(folder / 'report.json', report)
    print(json.dumps({k: report[k] for k in ('variant', 'baseline_cl', 'current_cl', 'archived_cl',
        'delta_from_baseline', 'absolute_error', 'radius_plateau', 'actual_mesh', 'seconds', 'peak_rss_kib')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant', choices=('segspl', 'body-mesh', 'export-mesh', 'flat-middle'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    common.bounded()
    run(args.output.resolve(), args.variant)
