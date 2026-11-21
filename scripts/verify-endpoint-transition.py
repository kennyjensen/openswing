"""Verify the exact endpoint source transition and preserve historical evidence."""
from pathlib import Path
import argparse,ast,copy,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from openswing.asw import parse_asw
from openswing.geometry import geometry_summary
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def methods(tree):
    result={}
    for n in tree.body:
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):result[n.name]=ast.dump(n,include_attributes=False)
        elif isinstance(n,ast.ClassDef):
            for f in n.body:
                if isinstance(f,(ast.FunctionDef,ast.AsyncFunctionDef)):result[n.name+'.'+f.name]=ast.dump(f,include_attributes=False)
    return result


def outside(tree):
    tree=copy.deepcopy(tree)
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Distribution')
    f=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='evaluate')
    f.body=[ast.Pass()]
    return ast.dump(tree,include_attributes=False)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--regression',type=Path,required=True);args=parser.parse_args();D=ROOT/'docs/validation'
    old={p.name:sha(p) for p in args.baseline.glob('*.py')};new={p.name:sha(p) for p in(ROOT/'openswing').glob('*.py')}
    assert len(old)==len(new)==97 and set(old)==set(new) and {n for n in old if old[n]!=new[n]}=={'asw.py'}
    a=ast.parse((args.baseline/'asw.py').read_text());b=ast.parse((ROOT/'openswing/asw.py').read_text())
    aa,bb=methods(a),methods(b);assert aa.keys()==bb.keys()
    assert [n for n in aa if aa[n]!=bb[n]]==['Distribution.evaluate'] and outside(a)==outside(b)
    acceptance=json.loads(args.regression.read_text())
    assert acceptance['status']=='PASS_ALL_FULL_SUITE_FAILURES_REPRODUCED_AND_REPAIRED'
    assert acceptance['baseline_modules']==old and acceptance['candidate_modules']==new
    assert acceptance['full_cases']==2989 and acceptance['original_failures']==24 and acceptance['repaired_checks']==36
    audit=json.loads((D/'isae-sa13-endpoint-candidate-native.json').read_text())
    assert audit['pins']['baseline']==old['asw.py'] and audit['pins']['candidate']==new['asw.py']
    assert audit['literal_models']==279 and audit['distributions_checked']==4767
    assert audit['derivatives_orders_1_to_3_bitwise_unchanged']
    wasm=json.loads((D/'isae-sa13-endpoint-candidate-wasm.json').read_text())
    browser=json.loads((D/'isae-sa13-endpoint-candidate-browser.json').read_text())
    assert wasm['modules']==browser['modules']==new
    # An actual current-source display check supplements the earlier candidate
    # checks. Keep the original standalone body's12x geometry untouched.
    sources=json.loads((D/'isae-sa14-sources.json').read_text())
    displays=[]
    for model in sources['models']:
        geometry_summary(parse_asw(model['source']),50)
        displays.append(dict(case=model['name'],source_sha256=model['sha256'],status='constructed_on_current_source'))
    out=dict(status='PASS_ENDPOINT_SOURCE_BOUNDARY_AND_FULL_REGRESSION_ACCOUNTING',
        baseline_modules=old,candidate_modules=new,changed_functions={'asw.py':['Distribution.evaluate']},unchanged_modules=96,
        script_sha256=sha(Path(__file__)),regression_acceptance_sha256=sha(args.regression),
        regression=dict(full_cases=2989,original_passed=2965,original_baseline_failures=24,repaired_checks_passed=36,
            result='All original failed IDs map to passing repaired checks; original full-run failure record is retained.',
            original_wrapper_exit_code=acceptance['wrapper_reap_exit_code'],
            original_process_note=acceptance['process_result_note']),
        previous_candidate_evidence={n:sha(D/n) for n in ['isae-sa13-endpoint-candidate-native.json',
            'isae-sa13-endpoint-candidate-wasm.json','isae-sa13-endpoint-candidate-browser.json']},
        literal_parse_outcomes=dict(parsed=audit['parsed'],rejected=audit['rejected']),
        checked_distributions=4767,maximum_scaled_distribution_change=audit['maximum_scaled_change'],
        derivatives_orders_1_to_3_bitwise_unchanged=True,current_source_displays=displays,
        scope=['Only exact segment terminal value queries now return the stored knot value; no nearby sample or derivative is clipped.',
            'The complete production module tree matches the exercised endpoint candidate. Earlier candidate numerical/runtime records retain their original pins.',
            'Historical validation studies are not rerun by this source audit and must remain labelled with their original solver hashes.',
            'This fixes false negative zero-radius display rejection. It does not change natural spline end conditions or resolve physical validation gaps.',
            'The packaged application requires a separate build and actual runtime validation.'])
    (D/'endpoint-source-transition.json').write_text(json.dumps(out,indent=2)+'\n')
    print(out['status'],out['changed_functions'],'SA14 displays',len(displays),flush=True)


if __name__=='__main__':main()
