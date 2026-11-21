"""Repeat the extension comparison with the target lifting-surface chart."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isae_ffwt4_evidence import pin, read, require, write
from isae_ffwt4_rigid_extension_v2 import compare_loads, compare_tangent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'Preserve prior evidence')
    base = args.output.parent/'assessment.json'
    previous = read(base)
    for record in previous['source_kernel_pins']+previous['helper_pins']+[previous['helper']]:
        require(pin(record['path']) == record, 'Changed preceding assessment input')
    tests = args.output.parent/'surface-tests.xml'
    suite = ET.parse(tests).getroot().find('testsuite')
    require(int(suite.attrib['tests']) == len(suite.findall('testcase')) == 20
            and all(int(suite.attrib[k]) == 0 for k in ('failures', 'errors', 'skipped')), 'Surface tests failed')
    helpers = [pin(ROOT/p) for p in ('scripts/isae_ffwt4_rigid_extension_v2.py', 'tests/test_rigid_point_surface_extension.py')]
    loads = [compare_loads(upper=upper, panels=panels, tilted=True, local=True, lifting=True)
             for upper in (False, True) for panels in (4, 6)]
    matrices = [compare_tangent(upper=upper, tilted=tilted, lifting=True)
                for upper in (False, True) for tilted in (False, True)]
    for record in previous['source_kernel_pins']+helpers:
        require(pin(record['path']) == record, 'Sources changed during comparison')
    result = dict(status='LIFTING_SURFACE_RIGID_EXTENSION_ASSESSED',
        observed_at=datetime.now(timezone.utc).isoformat(), previous_body_and_bdf_assessment=pin(base),
        tests=dict(report=pin(tests), passed=20), accumulated_focused_tests_passed=44,
        loads=loads, steady_tangents=matrices,
        max_section_load_oracle_error=max(v['maximum_oracle_error'] for v in loads),
        max_section_load_pair_difference=max(v['maximum_pair_difference'] for v in loads),
        max_steady_schur_matrix_difference=max(v['maximum_scaled_difference'] for v in matrices),
        helper=pin(__file__), helper_pins=helpers, source_kernel_pins=previous['source_kernel_pins'],
        nonlinear_equilibrium_or_time_solves=0, native_predictions_added=0,
        original_isae_models_modified=False, production_attachment_rule_changed=False,
        native_attachment_semantics_established=False, exact_finite_BDF_equivalence=False,
        full_family_validated=False,
        qualifications=[
            'Retained lifting surface uses its own source material chart; the auxiliary extension is a massless nonlifting beam.',
            'No mean airflow is applied. This checks source point inertia, internal section loads and steady reduced Jacobians, not point drag/volume flow.',
            'Tilted cases prescribe a moved pose and solve nodal wrench balance only; they do not claim equilibrium with the original fixed clamp.',
            'The preceding prescribed-history BDF counterexample still applies. Local-rate/acceleration matrices and converged time trajectories remain required.',
            'Original source attachment semantics and native-ASWING agreement remain unproved.'])
    write(args.output, result)
    print(json.dumps({k: result[k] for k in ('status','accumulated_focused_tests_passed',
        'max_section_load_oracle_error','max_section_load_pair_difference','max_steady_schur_matrix_difference')}), flush=True)


if __name__ == '__main__':
    main()
