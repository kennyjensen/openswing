import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const root=process.cwd(),sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const {loadPyodide}=await import(root+'/node_modules/pyodide/pyodide.mjs');
try {
 const py=await loadPyodide({indexURL:root+'/public/runtime'});await py.loadPackage(['numpy','scipy']);
 py.FS.mkdirTree('/home/pyodide/openswing');py.FS.mkdirTree('/home/pyodide/examples');
 const modules={};
 for(const name of (await readdir(root+'/openswing')).filter(n=>n.endsWith('.py'))){
  const bytes=await readFile(root+'/openswing/'+name);modules[name]=sha(bytes);
  py.FS.writeFile('/home/pyodide/openswing/'+name,bytes);
 }
 const audit=JSON.parse(await readFile('docs/validation/reference-compatibility.json','utf8'));
 const manifest=JSON.parse(await readFile('.reference/isae-validation/manifest.json','utf8'));
 const inputs=[];
 for(const row of audit.candidate_snapshot.records){
  const path=row.path.startsWith('isae/')?`.reference/isae-validation/${manifest.revision}/${row.path.slice(5)}`:row.path;
  const bytes=await readFile(path);if(sha(bytes)!==row.source_sha256)throw Error('Changed source '+path);
  inputs.push({...row,text:bytes.toString('utf8').replace(/^\uFEFF/,'')});
 }
 py.FS.writeFile('/home/pyodide/examples/rectangular.asw',await readFile('examples/rectangular.asw'));
 py.globals.set('inputs_json',JSON.stringify(inputs));
 py.globals.set('source',await readFile('tests/test_asw_reference_syntax.py','utf8'));
 py.globals.set('pins_json',JSON.stringify({modules,expected:audit.candidate_modules}));
 py.globals.set('setup_json',await readFile('docs/validation/reference-setup.json','utf8'));
 py.globals.set('probe_json',await readFile('docs/validation/reference-browser-probe.json','utf8'));
 const result=JSON.parse(await py.runPythonAsync(`
import ast,types,re,json,hashlib
from openswing.asw import parse_asw
from openswing.asw_edit import model_data
pins=json.loads(pins_json);assert pins['modules']==pins['expected']
counts={'parsed':0,'rejected':0}
for row in json.loads(inputs_json):
 expected=row['literal']
 try:model=parse_asw(row['text'])
 except ValueError as exc:
  assert expected==dict(status='rejected',error=type(exc).__name__+': '+str(exc)),row['path']
  counts['rejected']+=1
 else:
  assert expected['status']=='parsed',row['path']
  assert model.dumps()==row['text']
  data=model_data(model)
  assert hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()==expected['model_sha256'],row['path']
  assert model.diagnostics==expected['diagnostics']
  assert model_data(parse_asw(model.dumps(canonical=True)))==data,row['path']
  counts['parsed']+=1
class Raises:
 def __init__(self,expected,match=None):self.expected=expected;self.match=match
 def __enter__(self):return self
 def __exit__(self,kind,value,tb):
  assert kind is not None
  if not issubclass(kind,self.expected):return False
  assert self.match is None or re.search(self.match,str(value))
  return True
pytest=types.SimpleNamespace(raises=Raises)
tree=ast.parse(source);calls=[]
tree.body=[n for n in tree.body if not isinstance(n,ast.Import) or all(a.name!='pytest' for a in n.names)]
for node in tree.body:
 if isinstance(node,ast.FunctionDef) and node.name.startswith('test_'):
  if node.decorator_list:
   assert len(node.decorator_list)==1
   decorator=node.decorator_list[0];assert ast.unparse(decorator.func)=='pytest.mark.parametrize'
   assert ast.literal_eval(decorator.args[0])=='rows'
   calls.extend((node.name,(rows,)) for rows in ast.literal_eval(decorator.args[1]))
  else:calls.append((node.name,()))
  node.decorator_list=[]
exec(compile(ast.fix_missing_locations(tree),'test_asw_reference_syntax.py','exec'))
for name,args in calls:globals()[name](*args)
from openswing.network import StaticNetwork
setup=json.loads(setup_json);assert setup['modules']==pins['modules']
inputs={r['path'][5:]:r for r in json.loads(inputs_json) if r['path'].startswith('isae/')}
for expected in setup['cases']:
 row=inputs[expected['path']];assert row['source_sha256']==expected['source_sha256']
 model=parse_asw(row['text'])
 try:network=StaticNetwork(model,8,None,None,[])
 except ValueError as exc:
  assert expected['status']=='rejected' and expected['error']==type(exc).__name__+': '+str(exc),expected['path']
 else:assert expected['status']=='constructed_not_solved',expected['path']
probe=json.loads(probe_json);assert probe['modules']==pins['modules']
settings=dict(probe['settings']);panels=settings.pop('panels')
actual=solve_rigid(parse_asw(inputs[probe['source']]['text']),FlightCondition(**settings),panels=panels)
error=max(abs(actual[k]-probe['result'][k]) for k in ['CL','CD','CY','Cm','Cl','Cn','CDi','CDp'])
assert actual['converged'] and actual['residual']<1e-8 and error<2e-12
json.dumps(dict(status='PASS',native_input_outcomes=counts,input_count=sum(counts.values()),
 fixture_checks=len(calls),fixtures=[name for name,args in calls],
 network_setups=len(setup['cases']),rigid_probe_maximum_native_difference=error,
 meaning='Literal imports, complete parsed data, diagnostics, lossless/canonical save and nonzero-rate rigid loads agree. No experimental agreement claim.'))
`));
 Object.assign(result,{modules,pyodide:py.version,
  script_sha256:sha(await readFile(new URL(import.meta.url))),
  fixture_sha256:sha(await readFile('tests/test_asw_reference_syntax.py')),
  native_audit_sha256:sha(await readFile('docs/validation/reference-compatibility.json')),
  setup_sha256:sha(await readFile('docs/validation/reference-setup.json')),
  rigid_probe_sha256:sha(await readFile('docs/validation/reference-browser-probe.json')),
  runtime_sha256:Object.fromEntries(await Promise.all(['pyodide.asm.wasm','pyodide-lock.json'].map(async name=>[name,sha(await readFile(root+'/public/runtime/'+name))])))});
 await writeFile(process.env.OPENSWING_RESULTS||'docs/validation/reference-compatibility-wasm.json',JSON.stringify(result,null,2)+'\n');
 console.log('PASS',result.input_count,'native/WASM input outcomes;',result.fixture_checks,'Reference checks');
}catch(error){console.error(String(error));process.exitCode=1;}
