"""Audit the retained compressible SA-11 baseline comparisons; no solves."""
from datetime import datetime, timezone
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'artifacts/isae/sa11-avl-baseline-r1-20261108'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    plan = json.loads((BASE/'plan.json').read_text())
    assert sha(BASE/'driver-used.py') == plan['driver_sha256']
    assert sha(ROOT/plan['binary']) == plan['binary_sha256']
    for name, pin in plan['unchanged_pins'].items(): assert sha(ROOT/name) == pin, name
    rows, pins = [], {}
    for case in plan['cases']:
        file = BASE/case['id']/'report.json'
        report = json.loads(file.read_text())
        pins[str(file.relative_to(ROOT))] = sha(file)
        for name, pin in report['artifact_sha256'].items(): assert sha(file.parent/name) == pin, name
        state = report['production']; values = report['values']
        assert state['status'] == 'computed' and state['stalled_strips'] == 0
        assert state['residual'] < 1e-8 and state['max_section_normal_mach'] < 1
        assert report['minimum_stall_limit_margin_widths'] > 40
        assert max(report['geometry_errors'].values()) < 2e-11
        row = dict(case=case, errors_to_reference_percent=report['errors_to_reference_percent'],
            production_total_CD_error_percent=100*(values['openswing_total']['CD']/values['reference']['CD']-1),
            native_vs_production_vortex_errors_percent={k:100*(values['openswing_vortex'][k]/values['native'][k]-1)
                                                       for k in ['CL','CD_near']},
            native_vs_production_trefftz_error_percent=100*(values['openswing_total']['CDi']/values['native']['CDi']-1),
            native_production_gamma_relative_linf=report['native_production_gamma_relative_linf'],
            gamma_operator_error=report['native_gamma_operator_reproduction_error'],
            field_operator_error=report['native_field_operator_reproduction_error'],
            geometry_error=max(report['geometry_errors'].values()),
            minimum_stall_limit_margin_widths=report['minimum_stall_limit_margin_widths'],
            maximum_section_normal_mach=state['max_section_normal_mach'],
            native_maximum_section_normal_mach=report['native_max_section_normal_mach_using_asw_axis'],
            native_seconds=report['native_seconds'], openswing_seconds=report['openswing_seconds'])
        rows.append(row)
    for alpha in (0,1):
        a,b=[(BASE/f'{s}-alpha{alpha}'/'model.avl').read_text().splitlines() for s in ['original','extension_slope']]
        assert len(a)==len(b)
        changed=[i for i,(x,y) in enumerate(zip(a,b)) if x!=y]
        assert len(changed)==16 and all(a[i-1]==b[i-1]=='CLAF' for i in changed)
    for name in ['verify-sa11-avl-baseline.py','analyze-sa11-avl-baseline.py']:
        ast.parse((ROOT/'scripts'/name).read_text())
    path=BASE/'analysis.json';assert not path.exists()
    analysis=dict(observed_utc=datetime.now(timezone.utc).isoformat(), cases=rows, report_sha256=pins,
        unchanged_pins=plan['unchanged_pins'], native_input_changes_limited_to_CLAF=True,
        interpretation='Independent native AVL reproduces the baseline loading bias and its reduction using the separately supplied extension slope. This supports an archived producing-input mismatch; it does not prove that input or change any registered comparison. Total drag and native discretization remain unresolved.',
        previous_goal_turn='progress: actual winglet conversion and field comparisons completed',
        primary_status='SA-11 remains 163/4592 at 5%; no production or comparison-scope changes.')
    path.write_text(json.dumps(analysis,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(cases=len(rows), unchanged_pins=len(plan['unchanged_pins']),
        maximum_geometry_error=max(r['geometry_error'] for r in rows),
        maximum_gamma_operator_error=max(r['gamma_operator_error'] for r in rows),
        maximum_vortex_CL_percent=max(abs(r['native_vs_production_vortex_errors_percent']['CL']) for r in rows),
        maximum_vortex_CD_percent=max(abs(r['native_vs_production_vortex_errors_percent']['CD_near']) for r in rows),
        maximum_trefftz_CD_percent=max(abs(r['native_vs_production_trefftz_error_percent']) for r in rows),
        native_seconds=sum(r['native_seconds'] for r in rows),openswing_seconds=sum(r['openswing_seconds'] for r in rows))))


if __name__=='__main__':main()
