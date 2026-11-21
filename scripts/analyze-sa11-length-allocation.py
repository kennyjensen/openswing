"""Verify the six predeclared SA-11 length-allocation diagnostics."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import re

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/isae/sa11-length-allocation-20261108'


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


driver = module('allocation_driver', 'verify-sa11-length-allocation.py')
field = module('field_quadrature', 'analyze-sa11-winglet-current-wind.py')


def main():
    plan = driver.read(OUT / 'plan.json')
    driver.check(plan)
    rows, pins = [], {}
    alpha = np.deg2rad(1.)
    ambient = 240 * np.array([np.cos(alpha), 0., np.sin(alpha)])
    for case in plan['cases']:
        folder = OUT / case['id']
        report = driver.read(folder / 'report.json')
        setup = driver.read(folder / 'setup.json')
        assert report['case'] == case and setup['twist'] == -4.
        for name, digest in report['artifact_sha256'].items():
            assert driver.sha(folder / name) == digest, (case['id'], name)
        pins[str((folder / 'report.json').relative_to(ROOT))] = driver.sha(folder / 'report.json')
        with np.load(folder / 'state.npz') as archive:
            state = {key: archive[key].copy() for key in archive.files}
        count = len(state['gamma'])
        assert count == report['intervals'] == report['circulation_unknowns']
        assert count == sum(m['intervals'] for m in setup['meshes'])
        assert setup['condition']['stall'] and setup['condition']['freeze_influences'] == case['frozen']
        assert setup['condition']['speed'] == 240 and setup['condition']['alpha'] == 1
        residual = float(np.max(abs(state['local_residual'])))
        assert residual < 1e-8 and abs(residual-report['production']['residual']) < 1e-12
        velocity, span = state['velocity'], state['tangent']
        normal = velocity - np.sum(velocity*span, axis=1)[:, None]*span
        mach = np.linalg.norm(normal, axis=1)/340.21
        worst = int(np.argmax(mach))
        assert abs(float(mach[worst])-report['production']['maximum_section_normal_mach']) < 1e-12
        bound, wake = field.independent_field(state, state['gamma'], state['wind'], worst, 96)
        finer, _ = field.independent_field(state, state['gamma'], state['wind'], worst, 192)
        refinement_error = float(np.max(abs(bound-finer)))
        velocity_error = float(np.max(abs(ambient+bound+wake-velocity[worst])))
        assert refinement_error < 1e-7, (case['id'], refinement_error)
        assert velocity_error < 1e-6, (case['id'], velocity_error)
        production = report['production']
        values = None
        if production['status'] == 'computed':
            result = driver.read(folder / 'openswing.json')
            values = {key: result[key] for key in ('CL', 'CD', 'CDi', 'efficiency')}
            # The archived CM is about the body origin, as in the primary adapter.
            values['Cm'] = result['Cm_origin']
            assert mach[worst] < 1
        else:
            assert production['status'] == 'rejected'
            assert production['details']['kind'] == 'section_normal_mach'
            assert report['values'] is None and not (folder / 'openswing.json').exists()
            assert mach[worst] >= 1
        rows.append(dict(case=case, intervals=count, status=production['status'],
                         maximum_mach=float(mach[worst]), maximum=production['maximum'],
                         residual=residual, minimum_stall_margin_widths=float(state['stall_margin'].min()/.05),
                         stalled_strips=int(np.sum(state['stall_margin'] < 0)),
                         bound_velocity=bound.tolist(), wake_velocity=wake.tolist(),
                         bound_speed=float(np.linalg.norm(bound)), wake_speed=float(np.linalg.norm(wake)),
                         velocity_reconstruction_error=velocity_error,
                         quadrature_refinement_error=refinement_error,
                         values=values, reference=report['reference'],
                         error_percent=None if values is None else {
                             k: 100*(v/report['reference'][k]-1) for k, v in values.items()},
                         seconds=report['seconds']))
    assert len(rows) == 6
    driver.check(plan)
    result = dict(observed_utc=datetime.now(timezone.utc).isoformat(), cases=rows,
                  pinned_sources=plan['pins'], result_sha256=pins,
                  analyzer_sha256=driver.sha(Path(__file__)),
                  independent_field_source_sha256=driver.sha(Path(field.__file__)),
                  production_calls=6, production_seconds=sum(r['seconds'] for r in rows),
                  maximum_independent_velocity_error=max(r['velocity_reconstruction_error'] for r in rows),
                  maximum_quadrature_refinement_error=max(r['quadrature_refinement_error'] for r in rows),
                  production_equations_changed=False, primary_scope_changed=False,
                  native_default_allocation_recovered=False, full_family_validated=False)
    driver.write(OUT / 'analysis.json', result)
    print(json.dumps({k: v for k, v in result.items() if k not in ('pinned_sources', 'result_sha256')}), flush=True)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import ScalarFormatter
    colors = re.findall(r"'(#\w+)'", (ROOT / 'web/plot-colors.js').read_text().split('export const plotColors')[1].split(']);')[0])
    fig, ax = plt.subplots(figsize=(8.3, 4.6))
    for frozen, color, label in zip((True, False), colors, ('Frozen influences', 'Current-wind influences')):
        values = [r for r in rows if r['case']['frozen'] == frozen]
        ax.plot([r['case']['main_intervals'] for r in values], [r['maximum_mach'] for r in values],
                'o-', color=color, label=label)
    ax.axhline(1., color='#555555', linestyle=':', label='Local section Mach limit')
    ax.set_xscale('log', base=2)
    ax.set_yscale('log')
    ax.set_xticks([64, 128, 256])
    ax.xaxis.set_major_formatter(ScalarFormatter())
    ax.set_xlabel('Requested main-wing intervals (winglet intervals: 6, 11, 22)')
    ax.set_ylabel('Maximum section-normal Mach')
    ax.set_title('SA-11: intervals allocated by beam length\nDiagnostic report −4° twist; α = 1°, U = 240 m/s')
    ax.grid(True, which='both', alpha=.2)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / 'length-allocation.png', dpi=150)
    fig.savefig(OUT / 'length-allocation.svg')
    plt.close(fig)


if __name__ == '__main__':
    main()
