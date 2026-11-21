import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile,readdir,mkdtemp,writeFile,rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {readKernelSources} from '../scripts/kernel-sources.mjs';
import {decodeKernelSources,loadKernelSources} from '../web/kernel-sources.js';

test('every production module survives the JSON transport byte for byte',async()=>{
  const bundle=await readKernelSources('openswing');
  const sources=decodeKernelSources(JSON.parse(JSON.stringify(bundle)));
  assert.deepEqual(sources.map(([name])=>name),(await readdir('openswing')).filter(name=>name.endsWith('.py')).sort());
  for(const [name,source] of sources)assert.deepEqual(Buffer.from(source),await readFile(`openswing/${name}`));
});

test('source capture preserves UTF-8 and rejects corrupt encoding',async t=>{
  const root=await mkdtemp(path.join(os.tmpdir(),'openswing-kernel-bundle-'));
  t.after(()=>rm(root,{recursive:true,force:true}));
  const original=Buffer.from('\ufeff# Γ, \\ and "quotes"\r\n\nx = "α"\n');
  await writeFile(path.join(root,'bridge.py'),original);
  const bundle=await readKernelSources(root);
  assert.deepEqual(Buffer.from(JSON.parse(JSON.stringify(bundle)).sources[0][1]),original);
  await writeFile(path.join(root,'bridge.py'),Buffer.from([0xc3,0x28]));
  await assert.rejects(readKernelSources(root),/not UTF-8/);
});

test('worker loads one fresh bundle and fails explicitly instead of mixing older files',async()=>{
  const bundle={format:'openswing-kernel-sources',version:1,sources:[['__init__.py',''],['bridge.py','# bridge\n']]};
  const calls=[];
  assert.deepEqual(await loadKernelSources(async(...args)=>{calls.push(args);return {ok:true,text:async()=>JSON.stringify(bundle)};}),bundle.sources);
  assert.deepEqual(calls,[['/kernel/sources.json',{cache:'no-store'}]]);
  await assert.rejects(loadKernelSources(async()=>({ok:false,status:404})),/HTTP 404/);
  await assert.rejects(loadKernelSources(async()=>({ok:true,text:async()=>'{truncated'})),/Loading the solver source bundle: invalid JSON/);
  for(const invalid of [null,{}, {...bundle,version:2}, {...bundle,sources:[]},
      {...bundle,sources:[['__init__.py','']]}, {...bundle,sources:[...bundle.sources,['bridge.py','duplicate']]},
      {...bundle,sources:[...bundle.sources,['../escape.py','bad']]},
      {...bundle,sources:[...bundle.sources,['new.py',12]]}])assert.throws(()=>decodeKernelSources(invalid),/solver|module/);
});
