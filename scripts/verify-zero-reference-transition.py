"""Audit literal zero-area support without relabelling earlier physical runs."""
from pathlib import Path
import argparse
import ast
import hashlib
import json
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def source_boundary(work):
    old=(work/'baseline/openswing/asw.py').read_text()
    expected=old.replace('if reference is None or np.any(reference[0] <= 0):',
        'if reference is None or reference[0, 0] < 0 or np.any(reference[0, 1:] <= 0):').replace(
        'Reference requires positive area, chord, and span.',
        'Reference requires nonnegative area and positive chord and span.')
    assert expected!=old and expected==(work/'candidate/openswing/asw.py').read_text()
    before=ast.parse((work/'baseline/openswing/aero.py').read_text())
    after=ast.parse((work/'candidate/openswing/aero.py').read_text())
    added=[n for n in after.body if getattr(n,'name',None)=='_reference_area'];assert len(added)==1
    assert ast.dump(added[0],include_attributes=False)==ast.dump(ast.parse('''
def _reference_area(model):
    """Structural inputs may omit aerodynamic normalization by specifying zero."""
    if not np.isfinite(model.reference[0, 0]) or model.reference[0, 0] <= 0:
        raise AnalysisError('Aerodynamic analyses require a positive Reference area for coefficient normalization. Zero-area inputs can be used for structural and vacuum analyses.')
''').body[0],include_attributes=False)
    after.body.remove(added[0]);call=ast.dump(ast.parse('_reference_area(model)').body[0],include_attributes=False)
    for name in ['_validate','evaluate_aerodynamics']:
        function=next(n for n in after.body if getattr(n,'name',None)==name)
        nodes=[n for n in function.body if ast.dump(n,include_attributes=False)==call];assert len(nodes)==1
        assert function.body.index(nodes[0])==(1 if name=='evaluate_aerodynamics' else 0)
        function.body.remove(nodes[0])
    assert ast.dump(before,include_attributes=False)==ast.dump(after,include_attributes=False)


def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();w=a.work.resolve()
    pins={side:{p.name:sha(p) for p in sorted((w/side/'openswing').glob('*.py'))} for side in ['baseline','candidate']}
    assert len(pins['baseline'])==len(pins['candidate'])==97
    assert [n for n in pins['baseline'] if pins['baseline'][n]!=pins['candidate'][n]]==['aero.py','asw.py']
    source_boundary(w)
    parsed=json.loads((w/'parse-checks.json').read_text())
    assert parsed['status']=='PASS_ZERO_AREA_LITERAL_IMPORT_AND_COMPLETE_MODEL_CONTINUITY'
    assert parsed['baseline_modules']==pins['baseline'] and parsed['candidate_modules']==pins['candidate']
    assert parsed['new_literal_imports']==64 and parsed['unchanged_inputs']==256 and parsed['inputs']==320
    assert parsed['script_sha256']==sha(ROOT/'scripts/verify-zero-reference.py')
    for side,pin in parsed['snapshots'].items():assert sha(w/(side+'-parse.json'))==pin
    native=json.loads((w/'st4-native.json').read_text());reference=json.loads((w/'st4-reference.json').read_text())
    assert native['modules']==reference['native_modules']==pins['candidate']
    assert native['status']=='COMPARISONS_COMPUTED_NOT_PHYSICALLY_VALIDATED' and len(native['runs'])==81
    for report,script in [(native,'verify-isae-st4.py'),(reference,'verify-isae-st4-reference.py')]:
        assert report['script_sha256']==sha(ROOT/'scripts'/script)
        for row in report['runs']:
            path=ROOT/row['cache'];assert sha(path)==row['sha256']
            cached=json.loads(path.read_text())
            if 'matrices' in cached:assert sha(ROOT/cached['matrices']['path'])==cached['matrices']['sha256']
    check=json.loads((w/'structural-checks.json').read_text())
    assert check['status']=='PASS_LITERAL_ST4_NUMERICAL_REFERENCE_AND_MESH_CHECKS_NOT_EXPERIMENTAL_VALIDATION'
    assert check['modules']==pins['candidate'] and check['native_states']==check['independent_states']==81
    assert check['unique_models']==check['continuous_models']==27 and check['matched_modes']==486
    assert check['script_sha256']==sha(ROOT/'scripts/summarize-zero-reference-structure.py')
    for field,name in [('native_report_sha256','st4-native.json'),('independent_report_sha256','st4-reference.json'),('transfer_report_sha256','transfer.json')]:assert check[field]==sha(w/name)
    transfer=json.loads((w/'transfer.json').read_text())
    assert transfer['status']=='PASS_CONTINUOUS_TRANSFER_REFERENCE'
    assert transfer['reference_sha256']==sha(ROOT/'scripts/isae_st4_transfer.py')
    assert transfer['script_sha256']==sha(ROOT/'scripts/verify-isae-st4-transfer.py')
    assert reference['reference_sha256']==sha(ROOT/'scripts/isae_st4_reference.py')
    assert transfer['energy_reference_sha256']==sha(w/'st4-reference.json')
    wasm=json.loads((w/'wasm.json').read_text())
    assert wasm['status']=='PASS_ZERO_REFERENCE_WASM_PHYSICAL_MATRICES_AND_GUARDS' and len(wasm['rows'])==3
    assert wasm['modules']==pins['candidate'] and wasm['native_report_sha256']==sha(w/'st4-native.json')
    assert wasm['script_sha256']==sha(ROOT/'scripts/test-zero-reference-wasm.mjs')
    paths=list((w/'browser-results').rglob('zero-reference-browser.json'));assert len(paths)==1
    browser=json.loads(paths[0].read_text());assert browser['status']=='PASS_FRESH_ZERO_REFERENCE_BROWSER'
    assert browser['offline'] and browser['served_build'] and len(browser['runs'])==3
    assert browser['modules']==pins['candidate'] and browser['native_report_sha256']==sha(w/'st4-native.json')
    assert browser['test_sha256']==sha(w/'candidate/tests/browser/zero-reference.spec.js')
    for row in browser['runs']:assert row['result']['software_provenance']['modules']==pins['candidate']
    tree=ET.parse(w/'tests.xml');tests=tree.findall('.//testcase')
    assert len(tests)==129 and not any(tree.findall('.//'+tag) for tag in ['failure','error','skipped'])
    test_pins={r.attrib['classname'].replace('.','/')+'.py':sha(w/'candidate'/(r.attrib['classname'].replace('.','/')+'.py')) for r in tests}
    test_pins['tests/fixtures/isae-zero-area.asw']=sha(w/'candidate/tests/fixtures/isae-zero-area.asw')
    inventory=json.loads((w/'candidate-inventory.json').read_text())
    assert inventory['kernel_modules']==pins['candidate'] and inventory['parse_counts']==dict(parsed=177,rejected=102)
    evidence={
        'zero-reference-imports.json':w/'parse-checks.json','zero-reference-native.json':w/'st4-native.json',
        'zero-reference-energy.json':w/'st4-reference.json','zero-reference-transfer.json':w/'transfer.json',
        'zero-reference-structure.json':w/'structural-checks.json','zero-reference-wasm.json':w/'wasm.json',
        'zero-reference-browser.json':paths[0]}
    out=dict(status='PASS_ZERO_REFERENCE_SOURCE_AND_NUMERICAL_CONTINUITY',baseline_modules=pins['baseline'],candidate_modules=pins['candidate'],
        unchanged_modules=95,changed_functions={'asw.py':['parse_asw'],'aero.py':['_validate','evaluate_aerodynamics']},added_functions=['_reference_area'],
        script_sha256=sha(__file__),selected_tests=129,test_source_sha256=test_pins,
        tests=dict(junit_sha256=sha(w/'tests.xml'),log_sha256=sha(w/'tests.log')),
        new_literal_imports=64,unchanged_parser_controls=256,native_states=81,independent_energy_states=81,continuous_models=27,matched_modes=486,
        wasm_cases=3,offline_browser_cases=3,maximum_N32_frequency_error=check['maximum_N32_frequency_error'],
        minimum_N32_kinetic_shape_assurance=check['minimum_N32_kinetic_shape_assurance'],maximum_energy_reference_error=check['maximum_energy_reference_error'],
        evidence_sha256={name:sha(path) for name,path in evidence.items()},full_suite_rerun=False,full_physical_validation=False,
        limitations=[
            'Literal zero reference area is preserved for structural and vacuum calculations. Aerodynamic normalization requires a positive area; no replacement area is inferred.',
            'Only parsing and early aerodynamic eligibility checks changed. All physical assembly, interpolation, constraints and eigensolvers are unchanged.',
            'Independent energy and continuous-transfer references use the literal model properties; agreement is numerical verification, not an independent reconstruction of the experiment.',
            'Gravity and aerodynamic/apparent-mass loads are omitted in this ST-4 modal study. Hanging still-air experimental setup, source inertia conflicts and table/CSV discrepancies remain unresolved.',
            'The maximum frequency error and minimum shape correlation at 32 intervals remain explicit. No exact coarse-mesh agreement or experimental pass is asserted.',
            'Initial reference meshes created tiny intervals at nearly coincident attachment stations and corrupted low eigenvalues. Failed calculations are retained; corrected energy meshes are checked against continuous roots.',
            'Selected regressions and three fresh offline browser cases pass; no fresh full-repository regression is claimed. Earlier physical studies retain their original source hashes.',
            'Coverage stays 16 partial families, 25 pending, zero fully validated. ST-4 numerical evidence is supplemental; experimental comparisons are pending.'])
    a.output.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({k:v for k,v in out.items() if k not in ['baseline_modules','candidate_modules','test_source_sha256','evidence_sha256','limitations']},indent=2))


if __name__=='__main__':main()
