"""Audit sparse adjoint recovery without relabelling historical physical runs."""
from pathlib import Path
import argparse
import ast
import hashlib
import json
import statistics
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_boundary(before, after):
    trees = [ast.parse(p.read_text()) for p in [before, after]]
    functions = [{n.name: ast.dump(n, include_attributes=False) for n in t.body
                  if isinstance(n, (ast.FunctionDef, ast.ClassDef))} for t in trees]
    a, b = functions
    assert b.keys() - a.keys() == {'_sparse_adjoint'} and not a.keys() - b.keys()
    assert [n for n in a if a[n] != b[n]] == ['eigensystem']
    # Outside these two functions only the sparse solver imports may change.
    def outside(tree):
        return [ast.dump(n, include_attributes=False) for n in tree.body
                if not isinstance(n, (ast.Import, ast.ImportFrom))
                and getattr(n, 'name', '') not in ['eigensystem', '_sparse_adjoint']]
    assert outside(trees[0]) == outside(trees[1])
    imports = [{ast.dump(n, include_attributes=False) for n in t.body
                if isinstance(n, (ast.Import, ast.ImportFrom))} for t in trees]
    assert not imports[0] - imports[1]
    expected = ast.parse('from scipy.sparse import csc_matrix, bmat\nfrom scipy.sparse.linalg import splu')
    assert imports[1] - imports[0] == {ast.dump(n, include_attributes=False) for n in expected.body}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    w = args.work.resolve()
    pins = {side: {p.name: sha(p) for p in sorted((w/side/'openswing').glob('*.py'))}
            for side in ['baseline', 'candidate']}
    a, b = pins['baseline'], pins['candidate']
    assert len(a) == len(b) == 97 and a.keys() == b.keys()
    assert [n for n in a if a[n] != b[n]] == ['linear_dynamics.py']
    source_boundary(w/'baseline/openswing/linear_dynamics.py', w/'candidate/openswing/linear_dynamics.py')
    replay = json.loads((w/'pencil-replay.json').read_text())
    assert replay['status'] == 'PASS_UNCHANGED_PENCIL_SPECTRA_ADJOINTS_AND_RESIDUES'
    assert replay['modules'] == pins and replay['requested'] == len(replay['rows']) == 26
    assert replay['script_sha256'] == sha(ROOT/'scripts/verify-modal-adjoint.py')
    for name, pin in replay['native_reports'].items():
        assert sha(ROOT/'docs/validation'/name) == pin
    for row in replay['rows']:
        assert row['compared_modes'] == len(row['comparisons']) == 16
        assert sha(ROOT/row['source_cache']) == row['source_cache_sha256']
        assert sha(ROOT/row['pencil']['path']) == row['pencil']['sha256']
        assert sha(w/row['arrays']['path']) == row['arrays']['sha256']
        assert row['diagnostics']['candidate']['left_recovery_counts'] == dict(
            sparse_adjoint=8, conjugate_reuse=8, sparse_rejected=0, schur_pencils=0,
            schur_vectors=0, nullspace_fallback=0, exact_kernel=0)
        for m in row['comparisons']:
            assert m['relative_eigenvalue_difference'] < 2e-8
            assert m['relative_residue_error_bound'] < 2e-8
            assert min(m['left_assurance'], m['right_assurance']) > 1-2e-8
            assert max(m['baseline_left_backward_error'], m['candidate_left_backward_error']) < 1e-9
    wasm = json.loads((w/'wasm.json').read_text())
    assert wasm['status'] == 'PASS_WASM_PENCIL_ADJOINTS_AND_REPEATED_POLE_FALLBACK'
    assert wasm['modules'] == pins and len(wasm['rows']) == 3
    assert wasm['test_sha256'] == sha(ROOT/'scripts/test-modal-adjoint-wasm.mjs')
    browser_paths = list((w/'browser').rglob('modal-adjoint-browser.json'))
    assert len(browser_paths) == 1
    browser = json.loads(browser_paths[0].read_text())
    assert browser['status'] == 'PASS_FRESH_BROWSER_MODAL_ADJOINTS'
    assert browser['modules'] == b and browser['baseline_modules'] == a
    assert browser['offline'] and browser['served_build'] and len(browser['modes']) == 3
    assert browser['test_sha256'] == sha(w/'candidate/tests/browser/modal-adjoint.spec.js')
    for row in browser['modes']:
        assert row['result']['software_provenance']['modules'] == b
    display_paths = list((w/'display').rglob('modal-adjoint-display.json'))
    assert len(display_paths) == 1
    display = json.loads(display_paths[0].read_text())
    assert display['status'] == 'PASS_SAVED_MODAL_DISPLAY_WITHOUT_RECOMPUTATION'
    assert display['modules'] == b and display['backend'] == 'Vulkan' and not display['fresh_solve']
    assert display['test_sha256'] == sha(w/'candidate/tests/browser/modal-adjoint-display.spec.js')
    suites = {}
    test_pins = {}
    for name in ['targeted', 'physical', 'response']:
        path = w/(name+'-tests.xml')
        tree = ET.parse(path)
        rows = tree.findall('.//testcase')
        assert rows and not tree.findall('.//failure') and not tree.findall('.//error') and not tree.findall('.//skipped')
        for row in rows:
            source = row.attrib['classname'].replace('.', '/')+'.py'
            test_pins[source] = sha(w/'candidate'/source)
        suites[name] = dict(passed=len(rows), seconds=sum(float(r.attrib['time']) for r in rows),
                            junit_sha256=sha(path), log_sha256=sha(w/(name+'-tests.log')))
    assert suites['targeted']['passed'] == 49
    assert suites['physical']['passed'] >= 180 and suites['response']['passed'] >= 20
    comparisons = [m for row in replay['rows'] for m in row['comparisons']]
    speedups = [row['cpu_speedup'] for row in replay['rows']]
    result = dict(status='PASS_SPARSE_ADJOINT_SOURCE_AND_NUMERICAL_CONTINUITY',
        baseline_modules=a, candidate_modules=b, unchanged_modules=96,
        changed_functions={'linear_dynamics.py': ['eigensystem']}, added_functions=['_sparse_adjoint'],
        script_sha256=sha(__file__), tests=suites, test_source_sha256=test_pins,
        native_pencils=26, native_eigenpairs=len(comparisons), wasm_pencils=3, fresh_browser_cases=3,
        saved_result_display_cases=1,
        maximum_relative_eigenvalue_difference=max(r['relative_eigenvalue_difference'] for r in comparisons),
        maximum_relative_residue_error_bound=max(r['relative_residue_error_bound'] for r in comparisons),
        minimum_left_assurance=min(r['left_assurance'] for r in comparisons),
        minimum_right_assurance=min(r['right_assurance'] for r in comparisons),
        observed_native_cpu_speedup=dict(minimum=min(speedups), median=statistics.median(speedups), maximum=max(speedups)),
        native_reports=replay['native_reports'],
        evidence_sha256={'modal-adjoint-native.json':sha(w/'pencil-replay.json'),
                         'modal-adjoint-wasm.json':sha(w/'wasm.json'),
                         'modal-adjoint-browser.json':sha(browser_paths[0]),
                         'modal-adjoint-display.json':sha(display_paths[0])},
        full_suite_rerun=False, full_physical_validation=False,
        limitations=[
            'Only left-vector recovery changes. Finite-subspace classification, physical matrices, right-vector solution and acceptance criteria remain unchanged.',
            'Repeated or weakly paired poles and rejected sparse solves retain generalized-Schur/null-space recovery. Direct and shift-invert searches retain their original recovery.',
            'Twenty-six native checks reuse saved Pazy A/M matrices. Three browser checks rebuild and linearize the physical model while offline.',
            'Timings are observations on this host, with concurrent verification workloads, not portable performance guarantees or end-to-end speedup measurements.',
            'Selected modal, descriptor, response and control regressions passed; this increment does not claim a fresh full-repository test run.',
            'The numerical browser run produced blank SwiftShader screenshots. A separate saved-result Vulkan display check verifies rendering without claiming another solve; the blank captures remain archived.',
            'Earlier ISAE studies retain their original source hashes. They are not relabelled as new physical runs. No additional ISAE family is fully validated.'])
    destination = args.output or ROOT/'docs/validation/modal-adjoint-transition.json'
    destination.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['status','native_pencils','native_eigenpairs',
        'maximum_relative_eigenvalue_difference','maximum_relative_residue_error_bound','observed_native_cpu_speedup','tests']},indent=2))


if __name__ == '__main__':
    main()
