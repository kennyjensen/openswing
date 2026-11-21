"""Prove the source boundary of the modal staircase change, without rerun claims."""
from pathlib import Path
from zipfile import ZipFile
import ast,hashlib,json

ROOT=Path(__file__).resolve().parents[1]
def digest(data):return hashlib.sha256(data).hexdigest()
baseline=json.loads((ROOT/'docs/validation/isae-st3.json').read_text())['provenance']['modules']
current={p.name:digest(p.read_bytes()) for p in sorted((ROOT/'openswing').glob('*.py'))}
assert set(current)==set(baseline)
assert {n for n in current if current[n]!=baseline[n]}=={'linear_dynamics.py'}
archive=ROOT/'docs/validation/isae-st3-20261014-raw.zip'
with ZipFile(archive) as z:before=z.read('source/openswing/linear_dynamics.py')
after=(ROOT/'openswing/linear_dynamics.py').read_bytes()
assert digest(before)==baseline['linear_dynamics.py']
old,new=ast.parse(before),ast.parse(after)
changed=[]
assert len(old.body)==len(new.body)
for a,b in zip(old.body,new.body):
    if ast.dump(a)!=ast.dump(b):
        assert isinstance(a,ast.FunctionDef) and isinstance(b,ast.FunctionDef) and a.name==b.name
        changed.append(a.name)
assert changed==['finite_subspace']
report=dict(status='PASS_SOURCE_BOUNDARY_NOT_NUMERICAL_RERUN',baseline_modules=baseline,candidate_modules=current,
    changed_module='linear_dynamics.py',changed_functions=changed,unchanged_modules=len(current)-1,
    baseline_archive=dict(path=archive.relative_to(ROOT).as_posix(),sha256=digest(archive.read_bytes())),
    script_sha256=digest(Path(__file__).read_bytes()),
    interpretation='Only finite_subspace changed. Parser, residuals, equilibrium, A/M assembly and the full_shift_invert branch are unchanged. Earlier reports retain their own run provenance; this proof does not present them as fresh runs.')
(ROOT/'docs/validation/dense-staircase-transition.json').write_text(json.dumps(report,indent=2)+'\n')
print(report['status'],changed)
