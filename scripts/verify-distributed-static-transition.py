"""Identify the exact source boundary; this is not a numerical rerun."""
from pathlib import Path
import argparse,ast,copy,hashlib,json

ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
ALLOWED={'inertia.py':['InertiaModel.__init__','InertiaModel.summary'],
         'network.py':['StaticNetwork.__init__','StaticNetwork.residual','solve_static'],
         'bridge.py':['dispatch']}

def functions(tree):
    result={}
    for n in tree.body:
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):result[n.name]=ast.dump(n,include_attributes=False)
        elif isinstance(n,ast.ClassDef):
            for f in n.body:
                if isinstance(f,(ast.FunctionDef,ast.AsyncFunctionDef)):result[n.name+'.'+f.name]=ast.dump(f,include_attributes=False)
    return result

def outside(tree,allowed):
    tree=copy.deepcopy(tree)
    for n in tree.body:
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in allowed:
            n.args=ast.arguments(posonlyargs=[],args=[],kwonlyargs=[],kw_defaults=[],defaults=[]);n.body=[ast.Pass()];n.returns=None
        elif isinstance(n,ast.ClassDef):
            for f in n.body:
                if isinstance(f,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name+'.'+f.name in allowed:
                    f.args=ast.arguments(posonlyargs=[],args=[],kwonlyargs=[],kw_defaults=[],defaults=[]);f.body=[ast.Pass()];f.returns=None
    return ast.dump(tree,include_attributes=False)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--baseline',type=Path,required=True);args=parser.parse_args()
    old={p.name:sha(p) for p in sorted(args.baseline.glob('*.py'))};new={p.name:sha(p) for p in sorted((ROOT/'openswing').glob('*.py'))}
    assert len(old)==len(new)==97 and set(old)==set(new)
    changes={name for name in old if old[name]!=new[name]};assert changes==set(ALLOWED)
    changed={}
    for name in changes:
        a=ast.parse((args.baseline/name).read_text());b=ast.parse((ROOT/'openswing'/name).read_text())
        before,after=functions(a),functions(b);assert before.keys()==after.keys()
        found=sorted(k for k in before if before[k]!=after[k]);assert found==sorted(ALLOWED[name]),(name,found)
        assert outside(a,ALLOWED[name])==outside(b,ALLOWED[name]),name
        changed[name]=found
    result=dict(status='PASS_SOURCE_BOUNDARY_NOT_NUMERICAL_RERUN',baseline_modules=old,candidate_modules=new,
                changed_functions=changed,unchanged_modules=94,unchanged_asw_parser=True,script_sha256=sha(Path(__file__)),
                scope=['Explicit signed mg/Dmg option preserves separate rotating centroids in zero-motion static calculations.',
                       'Default physical mass checks and all centroidal inertia checks remain; raw negative weight knots are now classified even when missed by a coarse sample.',
                       'Inspection/browser structural mode permits both signed point and distributed loads.',
                       'Signed distributed loads do not export a physical time-launch setup and reject dynamic evaluation.',
                       'No physical assembly, tangent, interpolation, quadrature or convergence tolerance changes. Prior studies retain original source pins.'])
    (ROOT/'docs/validation/distributed-static-transition.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(changed,indent=2))

if __name__=='__main__':main()
