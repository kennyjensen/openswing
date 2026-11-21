"""Record explicit rigid-extension load, tangent and BDF comparisons."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isae_ffwt4_evidence import pin, read, require, write
from isae_ffwt4_rigid_extension import compare_loads, compare_tangent
from isae_ffwt4_rigid_bdf import refinement


def passing_tests(path, count):
    suite = ET.parse(path).getroot().find('testsuite')
    require(int(suite.attrib['tests']) == len(suite.findall('testcase')) == count
            and all(int(suite.attrib[k]) == 0 for k in ('failures', 'errors', 'skipped')), 'Tests did not pass')
    return dict(report=pin(path), passed=count)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'Preserve previous evidence')
    root = args.output.parent
    kernels = [pin(p) for p in sorted((ROOT/'openswing').glob('*.py'))]
    helpers = [pin(ROOT/p) for p in ('scripts/isae_ffwt4_rigid_extension.py', 'scripts/isae_ffwt4_rigid_bdf.py',
                                    'tests/test_rigid_point_extension.py', 'tests/test_rigid_point_bdf.py')]
    tests = [passing_tests(root/'test-attempt-02.xml', 20), passing_tests(root/'bdf-tests.xml', 4)]
    first = ET.parse(root/'test-attempt-01.xml').getroot().find('testsuite')
    require(int(first.attrib['failures']) == 1, 'Original fixture failure was not preserved')
    preflight = ROOT/'artifacts/isae/ffwt4-source-audit-20261106/rigid-tip-preflight.json'
    original = read(preflight)
    require(len(original['certificates']) == 6 and original['kernel_pins'] == kernels, 'Preflight uses a different kernel')
    for certificate in original['certificates']:
        require(pin(certificate['source']['path']) == certificate['source'], 'Literal PM2 model changed')
    loads = [compare_loads(upper=upper, panels=panels, tilted=True, local=True)
             for upper in (False, True) for panels in (4, 6)]
    matrices = [compare_tangent(upper=upper, tilted=tilted) for upper in (False, True) for tilted in (False, True)]
    bdf = [refinement(order) for order in (1, 2)]
    require(kernels == [pin(p['path']) for p in kernels] and helpers == [pin(p['path']) for p in helpers],
            'Sources changed during comparison')
    result = dict(status='EXPLICIT_RIGID_EXTENSION_ASSESSED_WITH_BDF_LIMIT',
        observed_at=datetime.now(timezone.utc).isoformat(), literal_rigidity_preflight=pin(preflight),
        tests=tests, tested_checks=24, loads=loads, steady_tangents=matrices, bdf=bdf,
        max_section_load_oracle_error=max(v['maximum_oracle_error'] for v in loads),
        max_section_load_pair_difference=max(v['maximum_pair_difference'] for v in loads),
        max_steady_schur_matrix_difference=max(v['maximum_scaled_difference'] for v in matrices),
        source_kernel_pins=kernels, helper_pins=helpers, helper=pin(__file__),
        first_attempt=dict(report=pin(root/'test-attempt-01.xml'),
            preserved_sources=[pin(root/'helper-attempt-01.py'), pin(root/'tests-attempt-01.py')],
            reason='The synthetic fixture requested fewer than the production minimum of four intervals; corrected to valid explicit grids without changing a production gate.'),
        nonlinear_equilibrium_or_time_solves=0, native_predictions_added=0,
        source_models_modified=False, production_attachment_rule_changed=False,
        native_attachment_semantics_established=False, exact_finite_BDF_equivalence=False,
        full_family_validated=False,
        qualifications=[
            'Explicit synthetic massless rigid extension versus endpoint pylon; neither fixture rewrites an original ISAE model.',
            'Every inward retained endpoint force/moment trace is compared with an independent moving-point balance, including full tensor inertia and spin.',
            'Steady production Jacobians are compared after a dimensional Schur elimination of extension poses, internal forces and joint reactions.',
            'No point CDA/volume flow, local-rate/acceleration matrix columns, integrated BDF trajectory or built browser comparison is covered.',
            'Prescribed rotating histories expose nonzero anchor-dependent BDF velocity/acceleration errors; they decrease with order but prohibit an exact finite-step equivalence claim.',
            'The native out-of-range input convention remains unknown; no blocked reference value is promoted to a pass.'])
    write(args.output, result)
    print(json.dumps({k: result[k] for k in ('status','tested_checks','max_section_load_oracle_error',
          'max_section_load_pair_difference','max_steady_schur_matrix_difference','exact_finite_BDF_equivalence')}), flush=True)


if __name__ == '__main__':
    main()
