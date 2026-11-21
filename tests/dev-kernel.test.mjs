import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,readFile,writeFile,rm} from 'node:fs/promises';
import {createServer} from 'node:http';
import path from 'node:path';
import os from 'node:os';
import {devKernel} from '../scripts/dev-kernel.mjs';

test('development kernel follows native source changes instead of stale public copies',async t=>{
  const root=await mkdtemp(path.join(os.tmpdir(),'openswing-dev-kernel-'));
  let server;
  t.after(async()=>{
    if(server?.listening) {
      server.closeAllConnections();
      await new Promise((resolve,reject)=>server.close(error=>error?reject(error):resolve()));
    }
    await rm(root,{recursive:true,force:true});
  });
  const source=path.join(root,'openswing');await mkdir(source);
  await mkdir(path.join(root,'public/kernel'),{recursive:true});
  await writeFile(path.join(source,'aero.py'),'# current Γ\n');
  await writeFile(path.join(source,'private.txt'),'not a module');
  await writeFile(path.join(root,'public/kernel/aero.py'),'# stale\n');
  await writeFile(path.join(root,'public/kernel/manifest.json'),'["stale.py"]');
  await writeFile(path.join(root,'public/kernel/sources.json'),'{"stale":true}');
  await writeFile(path.join(root,'public/passthrough.txt'),'public fallback');
  // Exercise the real HTTP middleware without loading Vite's native bundler
  // or file watchers. Full Vite/browser integration is a separate check.
  let middleware;
  const plugin=devKernel(source);
  assert.equal(plugin.apply,'serve');
  plugin.configureServer({middlewares:{use(handler){
    assert.equal(middleware,undefined);middleware=handler;
  }}});
  assert.equal(typeof middleware,'function');
  const fallthroughs=[];
  server=createServer(async(request,response)=>{
    try {
      await middleware(request,response,async()=>{
        fallthroughs.push(request.url);
        try {
          const pathname=new URL(request.url,'http://localhost').pathname;
          response.end(await readFile(path.join(root,'public',pathname.slice(1))));
        } catch {
          response.statusCode=404;response.end();
        }
      });
    } catch(error) {
      response.statusCode=500;response.end(String(error));
    }
  });
  await new Promise((resolve,reject)=>{
    server.once('error',reject);server.listen(0,'127.0.0.1',resolve);
  });
  const base=`http://127.0.0.1:${server.address().port}`;
  const get=name=>fetch(`${base}/kernel/${name}`);
  assert.deepEqual(await(await get('manifest.json')).json(),['aero.py']);
  const bundled=await get('sources.json');
  assert.equal(bundled.headers.get('cache-control'),'no-store');
  assert.deepEqual(await bundled.json(),{format:'openswing-kernel-sources',version:1,sources:[['aero.py','# current Γ\n']]});
  let response=await get('aero.py');assert.equal(response.headers.get('cache-control'),'no-store');
  assert.equal(await response.text(),'# current Γ\n');
  await writeFile(path.join(source,'aero.py'),'# edited\n');
  await writeFile(path.join(source,'outputs.py'),'# new module\n');
  assert.equal(await(await get('aero.py')).text(),'# edited\n');
  assert.deepEqual(await(await get('manifest.json')).json(),['aero.py','outputs.py']);
  assert.deepEqual((await(await get('sources.json')).json()).sources,[['aero.py','# edited\n'],['outputs.py','# new module\n']]);
  response=await fetch(`${base}/kernel/aero.py`,{method:'HEAD'});
  assert.equal(response.headers.get('content-length'),String(Buffer.byteLength('# edited\n')));
  assert.equal(await response.text(),'');
  assert.equal((await get('private.txt')).status,404);
  assert.equal((await get('nested/aero.py')).status,404);
  await rm(path.join(source,'aero.py'));
  assert.equal((await get('aero.py')).status,404);
  assert.deepEqual(await(await get('manifest.json')).json(),['outputs.py']);
  assert.deepEqual((await(await get('sources.json')).json()).sources,[['outputs.py','# new module\n']]);
  assert.deepEqual(fallthroughs,[],'kernel requests must never reach stale public copies');
  assert.equal(await(await fetch(`${base}/passthrough.txt`)).text(),'public fallback');
  assert.deepEqual(fallthroughs,['/passthrough.txt']);
});
