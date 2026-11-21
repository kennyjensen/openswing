#!/usr/bin/env python3
"""Frozen three-mesh ST5 replay using the isolated source discrete operator."""
import argparse
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
BASE=ROOT/'scripts/verify-isae-st5-archived-output.py'
HELPERS=[ROOT/'scripts'/n for n in ['isae_drela_spline_diagnostic.py','isae_drela_discrete_diagnostic.py','isae_st5_discrete_solver.py']]


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')


def source():
    original=BASE.read_text();text=original
    def replace(old,new):
        nonlocal text
        assert text.count(old)==1,(old,text.count(old));text=text.replace(old,new)
    replace('ROOT = Path(__file__).resolve().parents[1]',f'ROOT = Path({str(ROOT)!r})')
    replace('sys.path.insert(0, str(ROOT))',"sys.path.insert(0, str(ROOT))\nsys.path.insert(0,str(ROOT/'scripts'))")
    replace('from openswing.asw import parse_asw', '''from openswing.asw import parse_asw as parse_original
    from copy import deepcopy
    from isae_drela_spline_diagnostic import adapt_beam_tables, coefficient_signature, seal_diagnostic_result
    def parse_asw(source):
        return adapt_beam_tables(parse_original(source))''')
    replace('from openswing.bridge import dispatch', '''from isae_st5_discrete_solver import solve_candidate
    def dispatch(request, progress=None):
        assert request['action']=='solve' and request['mode']=='structural'
        model=parse_asw(request['source']);before=coefficient_signature(model)
        result=solve_candidate(model,request['panels'],progress=progress)
        assert coefficient_signature(model)==before and model.dumps()==request['source']
        result.update(analysis='structural_static',structural_only=True,strips=[],diagnostic_source_metadata=model._diagnostic_spline)
        return result''')
    replace('from openswing.network import StaticNetwork','from isae_st5_discrete_solver import DiscreteNetwork as StaticNetwork')
    replace('        model = parse_asw(source)\n        network = StaticNetwork',"        model = parse_asw(source)\n        assert coefficient_signature(model)==result['diagnostic_source_metadata']['candidate_coefficients_sha256']\n        network = StaticNetwork")
    replace("        write(out/'result.json', result)","        write(out/'result.json', seal_diagnostic_result(deepcopy(result)))")
    replace("        write(out/'comparison.json', packet)","        write(out/'comparison.json', packet)\n        write(out/'result.json', seal_diagnostic_result(result))")
    return original,text


def load(stage):
    spec=importlib.util.spec_from_file_location('st5_source_discrete_frozen',stage/'candidate-verifier.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def prepare(stage):
    assert not (stage/'plan.json').exists()
    before,after=source();(stage/'candidate-verifier.py').write_text(after)
    (stage/'adapter.diff').write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile=str(BASE),tofile=str(stage/'candidate-verifier.py'))))
    load(stage).prepare(stage)
    plan=json.loads((stage/'plan.json').read_text())
    plan.update(status='PREDECLARED_DIAGNOSTIC_SOURCE_DISCRETE_NOT_PRODUCTION',
        wrapper_sha256=sha(__file__),baseline_sha256=sha(BASE),helper_pins={str(p):sha(p) for p in HELPERS},
        production_default_changed=False,app_restart_compatible=False,new_physical_solves=3,new_fresh_residuals=3,
        operator='Absolute Eq48; Eq54 preferred Euler K endpoint average; inverse of endpoint-average stiffness; Eq55/56 endpoint-average gravity force with symmetric split and zero distributed couple.',
        source_preserved='Original source/tables, stiffnesses, loads, ground and rigid offset joints unchanged; no parameter fitting.',
        qualifications=['Historical ASWING spline caller and exact unrounded NODE coordinates unknown.','Eq48 scalar axial compliance uses Fs_a/EA_a, not explicitly printed separately.','Set ds=ds0=unloaded spline arc. Historical finite-strain ds convention unavailable.','Absolute Eq48 may move sampled curved jig at zero load; retain that source discrete effect, no silent exact-jig subtraction.','Mesh refinement tests continuum sensitivity; archived ASWING likely uses a finite grid. No reference pass implied by convergence.'],
        newton='Original sparse structure with complete finite differences of new residual in both structured and full paths; old analytic mechanics explicitly disabled.',
        first_write_sealed=True,browser_solves=0)
    write(stage/'plan.json',plan)


def run(stage):
    from isae_drela_spline_diagnostic import seal_diagnostic_result
    plan=json.loads((stage/'plan.json').read_text())
    assert sha(__file__)==plan['wrapper_sha256'] and sha(BASE)==plan['baseline_sha256']
    assert all(sha(p)==h for p,h in plan['helper_pins'].items())
    try:load(stage).run(stage)
    finally:
        for p in stage.glob('level*/result.json'):write(p,seal_diagnostic_result(json.loads(p.read_text())))
    summary=json.loads((stage/'summary.json').read_text())
    summary.update(status='DIAGNOSTIC_SOURCE_DISCRETE_COMPARISON_COMPLETE',production_default_changed=False,app_restart_compatible=False,operator=plan['operator'],operator_qualifications=plan['qualifications'])
    write(stage/'summary.json',summary)
    print(json.dumps(dict(status=summary['status'],strict_matches=[m['structural_matches'] for m in summary['meshes']])) )


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','run']);p.add_argument('--stage',type=Path,required=True)
    args=p.parse_args();args.stage.mkdir(parents=True,exist_ok=True);(prepare if args.action=='prepare' else run)(args.stage)
