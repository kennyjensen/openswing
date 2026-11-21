"""Continue the declared ST-5 grids after extending the application mesh limit.

Only discretization input limits change in the kernel. Verify that exact source
diff and identical normalization of every retained grid before reusing results.
No completed numerical solve is repeated, and no requested node is removed.
"""
from copy import deepcopy
import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
spec = importlib.util.spec_from_file_location('_st5_mesh_extension',ROOT/'scripts/extend-isae-st5-meshes.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
OLD = helper.BASE
BASE = OLD/'large-mesh'
helper.BASE = BASE


def prepare():
    assert not (BASE/'plan.json').exists()
    old = helper.read(OLD/'plan.json')
    name = 'openswing/discretization.py'
    frozen = OLD/'frozen-before-limit'/name
    assert helper.sha(frozen) == old['pins'][name]
    text = frozen.read_text()
    # Verify a complete, explicitly enumerated gate-only change. All numerical
    # expressions after successful validation must remain byte-identical.
    changes = [
        ("LEGACY_MESH_RECIPE = 'all-breaks-v0'", "LEGACY_MESH_RECIPE = 'all-breaks-v0'\nMAX_INTERVALS = 1024"),
        ('not 4 <= value <= 512:', 'not 4 <= value <= MAX_INTERVALS:'),
        ("raise ValueError('Use an integer from 4 to 512 panels per beam.')", "raise ValueError(f'Use an integer from 4 to {MAX_INTERVALS} panels per beam.')"),
        ('not 5 <= len(nodes) <= 513', 'not 5 <= len(nodes) <= MAX_INTERVALS+1'),
        ('use 5 to 513 finite,', 'use 5 to {MAX_INTERVALS+1} finite,'),
    ]
    for before,after in changes:
        assert text.count(before)==1
        text=text.replace(before,after)
    assert text==(ROOT/name).read_text()
    original_pins={key:value for key,value in old['pins'].items() if key!=name}
    helper.stable(original_pins)
    from openswing.discretization import normalize
    spec=importlib.util.spec_from_file_location('openswing._st5_old_discretization',frozen)
    previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
    checks=[]
    for case,row in old['cases'].items():
        folder=ROOT/row['original_folder']
        for mesh in helper.read(folder/'plan.json')['meshes']:
            assert previous.normalize(mesh['panels'])==normalize(mesh['panels'])
            checks.append(dict(case=case,level=mesh['level'],normalized_settings_identical=True))
    retained=OLD/'20lb_80_20/run-level3'
    receipt=helper.read(retained/'execution.json')
    assert receipt['exit_code']==0 and receipt['physical_checks_pass']
    helper.stable(receipt['output_sha256'])
    panels=helper.read(retained/'plan.json')['meshes'][0]['panels']
    assert previous.normalize(panels)==normalize(panels)
    checks.append(dict(case='20lb_80_20',level=3,normalized_settings_identical=True))
    for count in range(4,513):
        assert previous.normalize(count)==normalize(count)
    study=deepcopy(old)
    study['pins'][name]=helper.sha(ROOT/name)
    study['pins'].update([helper.pin(frozen),helper.pin(Path(__file__)),helper.pin(OLD/'plan.json')])
    for filename in ('web/main.js','web/node-editor.js','tests/test_discretization.py','docs/NUMERICS.md'):
        study['pins'].update([helper.pin(ROOT/filename)])
    study.update(expected_cold_solves=7,expected_fresh_residuals=7,
        retained_extension_solves=1,original_grid_request_preserved=True,
        mesh_limit_change=dict(from_intervals=512,to_intervals=1024,
            changed_kernel_module=name,exact_gate_only_diff_verified=True,retained_grid_checks=checks,
            accepted_integer_counts_unchanged=509),
        earlier_rejected_attempt=str((OLD/'20lb_80_20/run-level4/execution.json').relative_to(ROOT)),
        scope='Same predeclared two-level physical grids; gate-only application limit extension admits 608/512 intervals. Original failed mesh pairs and archive counts remain unchanged.')
    for row in study['cases'].values():
        for mesh in row['meshes']:
            assert normalize(mesh['panels'])==mesh['panels']
    BASE.mkdir()
    (BASE/'20lb_80_20').mkdir()
    (BASE/'20lb_80_20/run-level3').symlink_to(retained,target_is_directory=True)
    helper.write(BASE/'plan.json',study)
    print(json.dumps(dict(prepared=True,retained_grids_checked=len(checks),new_solves=7,
                          requested_meshes_preserved=True,physical_equations_changed=False)))


previous_prepare_child=helper.prepare_child
def prepare_child(study,case,level):
    stage,inputs=previous_prepare_child(study,case,level)
    plan=helper.read(stage/'plan.json')
    previous=deepcopy(plan['kernel_pins'])
    current={key:helper.sha(ROOT/key) for key in previous}
    assert {key for key in current if current[key]!=previous[key]}=={'openswing/discretization.py'}
    plan['retained_kernel_pins']=previous
    plan['kernel_pins']=current
    plan['mesh_limit_compatibility_study']=str((BASE/'plan.json').relative_to(ROOT))
    helper.write(stage/'plan.json',plan)
    inputs.update([helper.pin(stage/'plan.json')])
    helper.write(stage/'input-pins.json',inputs)
    return stage,inputs


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run'))
    parser.add_argument('--case',choices=helper.CASES)
    parser.add_argument('--level',type=int,choices=(3,4))
    args=parser.parse_args()
    if args.action=='prepare':
        prepare()
    else:
        assert args.case and args.level
        helper.prepare_child=prepare_child
        helper.run(args.case,args.level)
