#!/usr/bin/env python3
"""Isolated, explicitly experimental ST-5 replay with Drela segmented splines.

Generate a pinned copy of the existing full-output verifier, replacing only its
model construction with the diagnostic beam-table adapter and direct static
solve. The production parser, bridge and defaults remain unchanged. All saved
candidate states are marked diagnostic-only and cannot be opened as app states.
"""
import argparse
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
BASE = ROOT/'scripts/verify-isae-st5-archived-output.py'
HELPER = ROOT/'scripts/isae_drela_spline_diagnostic.py'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def generated_source():
    original = BASE.read_text()
    modified = original
    def replace(old, new, count=1):
        nonlocal modified
        assert modified.count(old) == count, (old, modified.count(old))
        modified = modified.replace(old, new)
    replace("ROOT = Path(__file__).resolve().parents[1]", f"ROOT = Path({str(ROOT)!r})")
    replace("sys.path.insert(0, str(ROOT))", "sys.path.insert(0, str(ROOT))\nsys.path.insert(0, str(ROOT/'scripts'))")
    replace('for level in range(3):', 'for level in range(4):')
    replace('cold_solves=3', 'cold_solves=5', 2)
    replace('fresh_residuals=3', 'fresh_residuals=5', 2)
    replace('from openswing.asw import parse_asw', '''from openswing.asw import parse_asw as parse_original
    from copy import deepcopy
    from isae_drela_spline_diagnostic import adapt_beam_tables, coefficient_signature, seal_diagnostic_result
    def parse_asw(source):
        return adapt_beam_tables(parse_original(source))''')
    replace('from openswing.bridge import dispatch', '''from openswing.network import solve_static
    def dispatch(request, progress=None):
        assert request['action'] == 'solve' and request['mode'] == 'structural'
        model = parse_asw(request['source'])
        before = coefficient_signature(model)
        result = solve_static(model, None, request['panels'], progress=progress,
            allow_signed_point_weights=True, allow_signed_distributed_weights=True)
        assert coefficient_signature(model) == before
        assert model.dumps() == request['source']
        result.update(analysis='structural_static', structural_only=True, strips=[],
            diagnostic_source_metadata=model._diagnostic_spline)
        return result''')
    replace("        model = parse_asw(source)\n        network = StaticNetwork", "        model = parse_asw(source)\n        assert coefficient_signature(model) == result['diagnostic_source_metadata']['candidate_coefficients_sha256']\n        network = StaticNetwork")
    replace("        write(out/'result.json', result)", "        write(out/'result.json', seal_diagnostic_result(deepcopy(result)))")
    replace("        write(out/'comparison.json', packet)", "        write(out/'comparison.json', packet)\n        write(out/'result.json', seal_diagnostic_result(result))")
    return original, modified


def load(stage):
    spec = importlib.util.spec_from_file_location('frozen_st5_candidate_verifier', stage/'candidate-verifier.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare(stage):
    original, modified = generated_source()
    generated = stage/'candidate-verifier.py'
    assert not generated.exists()
    generated.write_text(modified)
    (stage/'adapter.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True), modified.splitlines(True),
        fromfile=str(BASE), tofile=str(generated))))
    module = load(stage)
    module.prepare(stage)
    plan = json.loads((stage/'plan.json').read_text())
    # The native/browser API caps each beam at 512 intervals. Retain a fifth
    # nested grid by bisecting the widest parameter intervals of the fourth
    # grid until each beam reaches that cap; tie-break by original index.
    # This fixed rule uses no solved deformation or reference error.
    beams = {}
    for key, settings in plan['meshes'][-1]['panels']['beams'].items():
        nodes = settings['nodes']
        remaining = 512-(len(nodes)-1)
        assert 0 <= remaining <= len(nodes)-1
        selected = sorted(range(len(nodes)-1), key=lambda i: (-(nodes[i+1]-nodes[i]), i))[:remaining]
        refined = sorted(nodes+[(nodes[i]+nodes[i+1])/2 for i in selected])
        assert len(refined) == 513
        beams[key] = {'nodes': refined}
    plan['meshes'].append(dict(level=4, intervals_by_beam={k: 512 for k in beams},
        panels=dict(default=512, beams=beams)))
    plan.update(status='PREDECLARED_EXPERIMENTAL_CANDIDATE_NOT_PRODUCTION',
        candidate_scope='Compiled beam splines only; original tables, source, static laws, physical tolerances and output decoder unchanged.',
        production_default_changed=False, app_restart_compatible=False,
        baseline_script_sha256=sha(BASE), adapter_sha256=sha(__file__), helper_sha256=sha(HELPER),
        diagnostic_model_policy='Drela SEGSPL/SPLIND zero-third-derivative end intervals; two-point segments linear.',
        source_equation_support='Official XFOIL6.97 src/spline.f SPLIND63-137 and SEGSPL533-558; ASWING caller is not available.',
        baseline_comparison='/tmp/openswing-isae-st5-reference-run-20261025',
        new_physical_solves=5, new_fresh_residuals=5, browser_solves=0,
        fifth_grid_rule='Retain level3 and bisect its widest parameter intervals, ordered by width then original index, until each beam has512 intervals. No response-based adaptation.',
        state_policy='Every candidate equilibrium is sealed with format openswing-diagnostic-only-equilibrium; ordinary saved identity cannot express this interpolation policy.',
        interpretation='Agreement is evidence for a candidate; physical/mesh/reference failures remain explicit. No default or input parameter will be adjusted from one error metric.')
    write(stage/'plan.json', plan)
    print(json.dumps(dict(prepared=str(stage/'plan.json'), meshes=[m['intervals_by_beam'] for m in plan['meshes']])), flush=True)


def run(stage):
    from isae_drela_spline_diagnostic import seal_diagnostic_result
    plan = json.loads((stage/'plan.json').read_text())
    assert sha(BASE) == plan['baseline_script_sha256'] and sha(__file__) == plan['adapter_sha256']
    assert sha(HELPER) == plan['helper_sha256']
    try:
        load(stage).run(stage)
    finally:
        # Retain incomplete attempts too, but never as an ordinary app restart.
        for path in stage.glob('level*/result.json'):
            write(path, seal_diagnostic_result(json.loads(path.read_text())))
    summary = json.loads((stage/'summary.json').read_text())
    summary.update(status='EXPERIMENTAL_SPLINE_COMPARISON_COMPLETE_NOT_A_PRODUCTION_RELEASE',
        diagnostic_model_policy=plan['diagnostic_model_policy'], production_default_changed=False,
        app_restart_compatible=False, candidate_helper_sha256=sha(HELPER), candidate_adapter_sha256=sha(__file__))
    write(stage/'summary.json', summary)
    print(json.dumps(dict(status=summary['status'], fine_mesh_pass=summary['all_fine_mesh_gates_pass'],
        finest_structural_matches=summary['meshes'][-1]['structural_matches'])), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'run'])
    parser.add_argument('--stage', type=Path, required=True)
    args = parser.parse_args()
    args.stage.mkdir(parents=True, exist_ok=True)
    (prepare if args.action == 'prepare' else run)(args.stage)
