"""Check saved SA-11/native AVL conversion evidence without new solves."""
from datetime import datetime, timezone
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p, x): p.write_text(json.dumps(x, indent=2, allow_nan=False)+'\n')


def main():
    directories = [ROOT/'artifacts/isae/sa11-avl-conversion-20261108',
                   ROOT/'artifacts/isae/sa11-avl-conversion-lower-20261108']
    out = ROOT/'artifacts/isae/sa11-avl-conversion-review-20261108'
    assert not out.exists(), out
    rows, inputs, pins = [], {}, {}
    for directory in directories:
        plan = json.loads((directory/'plan.json').read_text())
        assert sha(directory/'driver-used.py') == plan['driver_sha256']
        assert sha(ROOT/plan['binary']) == plan['binary_sha256']
        for name, pin in plan['unchanged_pins'].items():
            assert sha(ROOT/name) == pin, name
            pins[name] = pin
        for file in sorted(directory.glob('*/report.json')):
            report = json.loads(file.read_text())
            for name, pin in report['artifact_sha256'].items(): assert sha(file.parent/name) == pin, name
            inputs[str(file.relative_to(ROOT))] = sha(file)
            result = json.loads((file.parent/'openswing.json').read_text())
            assert result['converged'] and result['residual'] < 1e-8
            force = report['vortex_force_diagnostics']
            row = dict(case=report['case']['id'], vortices=report['vortices'],
                native_vortex_CL=force['native']['CL'], native_vortex_CD=force['native']['CD'],
                CL_difference_percent=100*(force['openswing']['CL']/force['native']['CL']-1),
                CD_difference_percent=100*(force['openswing']['CD']/force['native']['CD']-1),
                gamma_relative_linf_percent=100*report['production_native_gamma_relative_linf'],
                maximum_speed_ratio=report['maximum_bound_speed_over_freestream'],
                geometry_max_error=max(report['geometry_errors'].values()),
                max_normal_difference_deg=report['normal_angle_difference_deg']['maximum'],
                incidence_interpolation_difference_deg=report.get('native_vs_asw_incidence_interpolation_max_deg', 0.),
                native_gamma_reproduction_relative_error=report['native_gamma_reproduction_relative_error'],
                native_field_reproduction_max_error=report['native_field_reproduction_max_error'],
                production_gamma_reproduction_relative_error=report['production_gamma_reproduction_relative_error'],
                native_seconds=report['native_seconds'], openswing_seconds=report['openswing_seconds'],
                stalled_flag_count=sum(s['stalled'] for s in result['strips']),
                cl_range=[min(s['cl'] for s in result['strips']), max(s['cl'] for s in result['strips'])])
            rows.append(row)
    assert len(rows) == 4 and len({r['case'] for r in rows}) == 4
    failed = directories[0]/'isae-sa11-wingtip-up-and-down-r1'
    corrected = directories[1]/'isae-sa11-wingtip-up-and-down-r1'
    assert not (failed/'report.json').exists()
    identical = {name: sha(failed/name) == sha(corrected/name) for name in
                 ['model.avl', 'total.txt', 'strips.txt', 'body-strips.txt', 'elements.txt']}
    assert all(identical.values())
    for name in ['audit-sa11-avl-conversion.py', 'analyze-sa11-avl-conversion.py']:
        ast.parse((ROOT/'scripts'/name).read_text())
    out.mkdir(parents=True)
    write(out/'report.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(), cases=rows,
        input_sha256=inputs, unchanged_pins=pins,
        retained_analysis_failure=dict(directory=str(failed.relative_to(ROOT)),
            reason='The first normal reconstruction assumed incidence interpolation commuted with the ASW-to-AVL angle conversion. The lower winglet has varying twist and taper. Correct analysis uses AVL chord-weighted sine/cosine interpolation; native input/output unchanged.',
            native_outputs_identical_after_analysis_fix=identical,
            unused_original_refinement_case='Superseded by the lower-only follow-up; not run.'),
        zero_alpha_preflight=dict(model='upper/lower coarse geometry, linear field only', alpha=0.,
            cl_range=[-.3079428325546907, .980519860409254], sections_outside_cl_limits=16,
            meaning='Low aircraft incidence alone does not establish that every section is below its declared stall limit.'),
        primary_status='SA-11 remains 163/4592 at 5%; no registered scope, fraction, model, Mach guard or production equation changed.'))
    print(json.dumps(dict(cases=len(rows), unchanged_pins=len(pins),
        max_CL_difference_percent=max(abs(r['CL_difference_percent']) for r in rows),
        max_CD_difference_percent=max(abs(r['CD_difference_percent']) for r in rows),
        native_seconds=sum(r['native_seconds'] for r in rows), openswing_seconds=sum(r['openswing_seconds'] for r in rows))))


if __name__ == '__main__': main()
