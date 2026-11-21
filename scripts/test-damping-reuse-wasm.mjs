import {loadPyodide} from '../node_modules/pyodide/pyodide.mjs';
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const root=process.cwd(),kernel=process.env.OPENSWING_KERNEL||root;
const py=await loadPyodide({indexURL:path.resolve('public/runtime')});
await py.loadPackage(['numpy','scipy']);
for(const name of ['openswing','examples'])py.FS.mkdirTree('/home/pyodide/'+name);
const modules={};
for(const name of (await readdir(kernel+'/openswing')).filter(n=>n.endsWith('.py'))){
 const bytes=await readFile(kernel+'/openswing/'+name);
 modules[name]=createHash('sha256').update(bytes).digest('hex');
 py.FS.writeFile('/home/pyodide/openswing/'+name,bytes);
}
py.FS.writeFile('/home/pyodide/examples/flexible.asw',await readFile('examples/flexible.asw'));
await py.runPythonAsync(await readFile('tests/test_damping_reuse.py','utf8'));
const count=await py.runPythonAsync(`
checks=sorted(name for name,value in list(globals().items()) if name.startswith('test_') and callable(value))
for name in checks:
 globals()[name]()
 print('PASS',name,flush=True)
len(checks)
`);
if(count!==4)throw new Error('Expected four cache contract checks');
await writeFile(process.env.OPENSWING_REPORT||'/tmp/openswing-damping-reuse-wasm.json',
 JSON.stringify({status:'PASS',cases:count,pyodide:py.version,modules},null,2)+'\n');
console.log('PASS',count,'material-damping reuse WebAssembly checks');
