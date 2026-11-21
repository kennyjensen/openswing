// Focused native-packet portability checks; uses local runtime and current source.
import {loadPyodide} from 'pyodide';
import {readFile, readdir, writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';

const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const start = performance.now();
const fixture = 'tests/fixtures/mesh-recipe';
const receipt = {status: 'STARTED', scope: 'Native saved mesh equations and accepted-step replay in current-source WASM'};
try {
  receipt.script_sha256 = sha(await readFile(new URL(import.meta.url)));
  const provenanceBytes = await readFile(`${fixture}/PROVENANCE.json`);
  const provenance = JSON.parse(provenanceBytes);
  receipt.provenance_sha256 = sha(provenanceBytes);
  receipt.fixture_sha256 = {};
  for (const [name, expected] of Object.entries(provenance.files)) {
    const actual = sha(await readFile(`${fixture}/${name}`));
    if (actual !== expected.sha256) throw Error(`Frozen fixture changed: ${name}`);
    receipt.fixture_sha256[name] = actual;
  }
  const py = await loadPyodide({indexURL: path.resolve('public/runtime')});
  await py.loadPackage(['numpy', 'scipy']);
  receipt.pyodide = py.version;
  receipt.runtime_sha256 = Object.fromEntries(await Promise.all(
    ['pyodide.asm.wasm', 'pyodide-lock.json'].map(async name =>
      [name, sha(await readFile(`public/runtime/${name}`))])));
  py.FS.mkdirTree('/home/pyodide/openswing');
  receipt.modules = {};
  for (const name of (await readdir('openswing')).filter(name => name.endsWith('.py')).sort()) {
    const bytes = await readFile(`openswing/${name}`);
    receipt.modules[name] = sha(bytes);
    py.FS.writeFile(`/home/pyodide/openswing/${name}`, bytes);
  }
  py.globals.set('fixture_source', await readFile(`${fixture}/curved-shell.asw`, 'utf8'));
  py.globals.set('legacy_json', await readFile(`${fixture}/legacy.json`, 'utf8'));
  py.globals.set('current_json', await readFile(`${fixture}/current.json`, 'utf8'));
  receipt.result = JSON.parse(await py.runPythonAsync(`
from copy import deepcopy
import hashlib, json
import numpy as np
from openswing.asw import parse_asw
from openswing.aero import AnalysisError
from openswing.discretization import CURRENT_MESH_RECIPE, LEGACY_MESH_RECIPE
from openswing.equilibrium_state import capture, identity, matching_identity, recipe_from_identity, restore, warm_start_recipe
from openswing.geometry import model_meshes, undeformed_mesh
from openswing.network import StaticNetwork
from openswing.time_state import restore_checkpoint

checks = []
def checked(name, condition, **evidence):
    assert condition, (name, evidence)
    checks.append(dict(name=name, passed=True, **evidence))

def rejected(name, function):
    try:
        function()
    except AnalysisError as error:
        checks.append(dict(name=name, passed=True, rejection=str(error)))
    else:
        raise AssertionError(name+' accepted incompatible saved data')

payloads = [json.loads(legacy_json), json.loads(current_json)]
m = parse_asw(fixture_source)
assert not m.diagnostics
fields = ('t0', 't1', 'tm', 'ts', 'r0', 'r1', 'rm', 'frames', 'length', 'theta')
rows = []
for payload in payloads:
    recipe = payload['recipe']; saved = payload['equilibrium']; before = deepcopy(saved)
    prefix = recipe+': '
    assert payload['source_sha256'] == hashlib.sha256(fixture_source.encode()).hexdigest()
    if recipe == LEGACY_MESH_RECIPE:
        checked(prefix+'historical producer', payload['producer_kind']=='native frozen historical source')
    n = StaticNetwork(m, payload['panels'], None, [0,0,0], payload['loads'],
                      mesh_recipe=recipe_from_identity(saved['identity']))
    checked(prefix+'strict native identity', matching_identity(saved['identity'], identity(n)))
    errors = {}
    for field in fields:
        actual = getattr(n.meshes[0], field); expected = np.array(payload['mesh'][field])
        np.testing.assert_allclose(actual, expected, rtol=2e-14, atol=2e-14, err_msg=field)
        errors[field] = float(np.max(abs(actual-expected), initial=0.))
    checked(prefix+'all material mesh arrays', True, maximum_absolute_differences=errors)
    x = restore(n, saved)
    residual = float(np.max(abs(n.residual(x))))
    checked(prefix+'full steady residual', residual < 1e-10, residual=residual)
    recaptured = capture(n, x)
    checked(prefix+'recipe metadata',
        ('mesh_recipe' not in recaptured['identity'] if recipe == LEGACY_MESH_RECIPE
         else recaptured['identity']['mesh_recipe'] == recipe))
    checked(prefix+'source packet unchanged', saved == before)
    for method, case in payload['cases'].items():
        packet = case['checkpoint']; before_packet = deepcopy(packet)
        restored = restore_checkpoint(m, packet)
        net, _, state, _, _, _, physical_residual, validated = restored
        validation = validated['acceptance_validation']
        checked(prefix+method+' original mesh', net.mesh_recipe == recipe
                and matching_identity(packet['context']['identity'], identity(net)))
        checked(prefix+method+' accepted equations', validation['discrete_replayed']
                and validation['level']=='recorded_discrete_equations'
                and validation['residual'] <= validation['tolerance'], **validation)
        checked(prefix+method+' full physical residual', physical_residual < 1e-8,
                residual=physical_residual, native_residual=case['native_full_residual'])
        np.testing.assert_allclose(state.U, [0.,.004,0.], rtol=0, atol=2e-10)
        checked(prefix+method+' nonzero native frame motion', np.linalg.norm(state.U) > .003)
        checked(prefix+method+' input packet unchanged', packet == before_packet)
        if method == 'bdf2':
            checked(prefix+'BDF predecessor retained', packet['accepted_method']['effective_order']==2
                    and packet['older'] is not None)
        for location in ('context', 'accepted_inputs'):
            bad = deepcopy(packet)
            target = bad['context']['identity'] if location=='context' else bad['accepted_method']['accepted_inputs']['identity']
            target['mesh_recipe'] = 'unknown-future-recipe'
            rejected(prefix+method+' unknown '+location+' recipe', lambda: restore_checkpoint(m,bad))
        bad = deepcopy(packet);bad['context']['identity']['nodes'][-1][0] += 1e-8
        rejected(prefix+method+' changed material node', lambda: restore_checkpoint(m,bad))
        bad = deepcopy(packet);bad['context']['setup']['panels'] = 5
        rejected(prefix+method+' changed checkpoint count', lambda: restore_checkpoint(m,bad))
        bad = deepcopy(packet);bad['state']['network']['positions'][-1][0] += .001
        rejected(prefix+method+' changed physical endpoint', lambda: restore_checkpoint(m,bad))
    rows.append(dict(recipe=recipe, node_count=n.nn, full_steady_residual=residual,
                     mesh_maximum_absolute_differences=errors))

for old in payloads:
    checked(old['recipe']+' UI-equivalent old panel settings', warm_start_recipe(m, {'default':4,'beams':{}}, old['equilibrium'])==old['recipe'])
    for name, panels in [('count',5), ('spacing',{'default':4,'beams':{'1':{'count':4,'spacing':'uniform'}}}),
                         ('nodes',{'default':4,'beams':{'1':{'nodes':[0.,.4,.8,1.4,2.]}}})]:
        rejected(old['recipe']+' warm start rejects changed '+name, lambda: warm_start_recipe(m,panels,old['equilibrium']))
old = payloads[0]
bad_model = parse_asw(fixture_source.replace('.8 2 1.3','.8 2 1.31'))
rejected('old checkpoint rejects changed aircraft', lambda: restore_checkpoint(bad_model,old['cases']['bdf2']['checkpoint']))
for invalid in (None, [], 'legacy', {'mesh_recipe':'unknown'}):
    rejected('malformed recipe identity '+repr(invalid), lambda: recipe_from_identity(invalid))

shell = 't Cshell\\n0 .1\\n.43 .1\\n.43 .2\\n2 .2\\n'
assert shell in fixture_source
plain = parse_asw(fixture_source.replace(shell, ''))
base = model_meshes(plain, 4, old['loads'])[0]
for field in ('Cshell','Nshell','Atshell'):
    changed = parse_asw(fixture_source.replace(shell, 't '+field+'\\n0 .1\\n.73 .1\\n.73 .2\\n2 .2\\n'))
    current = model_meshes(changed,4,old['loads'])[0]
    for key in fields:
        np.testing.assert_array_equal(getattr(current,key),getattr(base,key),err_msg=field+': '+key)
    recovered = undeformed_mesh(current)
    checked(field+' fresh mesh unchanged', current.mesh_recipe==CURRENT_MESH_RECIPE
            and recovered.mesh_recipe==CURRENT_MESH_RECIPE)
fresh = StaticNetwork(plain,4,None,[0,0,0],old['loads'])
checked('fresh default capture is versioned', capture(fresh,np.zeros(fresh.size))['identity']['mesh_recipe']==CURRENT_MESH_RECIPE)
checked('historical and corrected topology differ', rows[0]['node_count'] > rows[1]['node_count'])
json.dumps(dict(status='PASS', checks_passed=len(checks), checks_total=len(checks), checks=checks, cases=rows,
    limits=['Strict identity uses the existing mesh-roundoff allowance; its gates are unchanged.',
            'Accepted method equations are replayed at fixed native states; this test performs no WASM time integration.',
            'Portability and saved-equation compatibility do not validate aircraft physics or the Drela reference.']))
`));
  for (const [name, expected] of Object.entries(receipt.modules)) {
    if (sha(await readFile(`openswing/${name}`)) !== expected) throw Error(`Source changed during test: ${name}`);
  }
  receipt.status = 'PASS';
  console.log(`PASS: ${receipt.result.checks_passed} focused native/WASM mesh-recipe checks`);
} catch (error) {
  receipt.status = 'FAIL';
  receipt.error = String(error.stack || error);
  console.error(receipt.error);
  process.exitCode = 1;
} finally {
  receipt.elapsed_seconds = (performance.now()-start)/1000;
  if (process.env.OPENSWING_RESULTS) {
    await writeFile(process.env.OPENSWING_RESULTS, JSON.stringify(receipt,null,2)+'\n');
  }
}
