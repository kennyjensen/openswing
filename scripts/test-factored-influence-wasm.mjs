// Run the same independent coefficient controls in the locally hosted WASM runtime.
import {loadPyodide} from '../node_modules/pyodide/pyodide.mjs';
import {readFile, readdir, writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';

const py = await loadPyodide({indexURL: path.resolve('public/runtime')});
await py.loadPackage(['numpy', 'scipy']);
for (const dir of ['openswing', 'scripts', 'tests']) py.FS.mkdirTree('/home/pyodide/' + dir);
const modules = {};
for (const name of (await readdir('openswing')).filter(name => name.endsWith('.py'))) {
  const bytes = await readFile('openswing/' + name);
  modules[name] = createHash('sha256').update(bytes).digest('hex');
  py.FS.writeFile('/home/pyodide/openswing/' + name, bytes);
}
const inputHashes = {};
for (const name of ['tests/test_factored_influence.py', 'scripts/verify-frozen-influences.py', 'scripts/verify-wake-core.py']) {
  const bytes = await readFile(name);
  inputHashes[name] = createHash('sha256').update(bytes).digest('hex');
  py.FS.writeFile('/home/pyodide/' + name, bytes);
}
const report = JSON.parse(await py.runPythonAsync(`
import inspect, itertools, json, runpy, sys, types
from contextlib import contextmanager
from time import perf_counter
import numpy as np

class Patch:
    def __init__(self): self.saved=[]
    def setattr(self, obj, name, value):
        self.saved.append((obj,name,getattr(obj,name)))
        setattr(obj,name,value)
    def undo(self):
        for obj,name,value in reversed(self.saved): setattr(obj,name,value)

def parametrize(names, values):
    def decorate(function):
        function.parameters=getattr(function,'parameters',[])+[(names.split(','),values)]
        return function
    return decorate

def fail(message): raise AssertionError(message)

@contextmanager
def raises(kind):
    try: yield
    except kind: pass
    else: raise AssertionError('Expected exception was not raised')

# The tests use fixture/parameter expansion, raises and monkeypatch; assertions
# remain their original NumPy/Decimal comparisons, with unchanged thresholds.
sys.modules['pytest']=types.SimpleNamespace(
    fixture=lambda function:function, fail=fail, raises=raises,
    mark=types.SimpleNamespace(parametrize=parametrize))
tests=runpy.run_path('/home/pyodide/tests/test_factored_influence.py')
cases=[]
for name,function in tests.items():
    if not name.startswith('test_'): continue
    parameter_sets=[{}]
    for names,values in getattr(function,'parameters',[]):
        parameter_sets=[dict(old,**dict(zip(names, (value,) if len(names)==1 else value)))
                        for old in parameter_sets for value in values]
    for values in parameter_sets:
        patch=Patch()
        arguments={key: values[key] if key in values else patch if key=='monkeypatch' else tests[key]()
                   for key in inspect.signature(function).parameters}
        start=perf_counter()
        try: function(**arguments)
        finally: patch.undo()
        cases.append(dict(name=name,parameters=values,seconds=perf_counter()-start))
        print('WASM',len(cases),name,values,flush=True)
assert len(cases)>=41

study=runpy.run_path('/home/pyodide/scripts/verify-frozen-influences.py')
physical=[]
for specification in [dict(panels=4),dict(panels=8,mach=.6,ground=1),
    dict(panels=8,alpha=-12,beta=-9,rotations=[[.12,-.18,.06],[-.15,.11,-.04]],stretches=[1.2,.9])]:
    expected=study['physical'](study['reference'](specification))
    actual=study['physical'](study['compute'](specification))
    np.testing.assert_allclose(actual,expected,rtol=3e-10,atol=3e-10)
    physical.append(dict(specification=specification,values_compared=actual.size,
                         max_absolute_error=float(np.max(abs(actual-expected)))))
    print('WASM independent frozen physical fields',specification,flush=True)
json.dumps(dict(status='PASS',coefficient_cases=cases,independent_physical_cases=physical))
`));
// A source mutation during execution invalidates this report's attribution.
for (const [name, digest] of Object.entries(modules)) {
  if (createHash('sha256').update(await readFile('openswing/' + name)).digest('hex') !== digest)
    throw new Error('Module changed during WASM checks: ' + name);
}
for (const [name, digest] of Object.entries(inputHashes)) {
  if (createHash('sha256').update(await readFile(name)).digest('hex') !== digest)
    throw new Error('Test input changed during WASM checks: ' + name);
}
if (process.env.OPENSWING_REPORT) await writeFile(process.env.OPENSWING_REPORT,
  JSON.stringify({...report, pyodide: py.version, modules, inputHashes}, null, 2) + '\n');
console.log(`${report.coefficient_cases.length} coefficient and ${report.independent_physical_cases.length} physical WASM cases passed.`);
