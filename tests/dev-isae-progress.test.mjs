import {test} from 'node:test';
import assert from 'node:assert/strict';
import {EventEmitter} from 'node:events';
import {devIsaeProgress} from '../scripts/dev-isae-progress.mjs';

test('development watcher serializes plot updates and ignores unrelated files',async()=>{
  const watcher=new EventEmitter(),httpServer=new EventEmitter();watcher.add=()=>{};
  let active=0,maximum=0,calls=0;
  const run=async(command,args,options)=>{
    assert.match(command,/\.venv\/bin\/python$/);assert.deepEqual(args,['scripts/isae_progress.py']);
    assert.equal(options.env.OPENBLAS_NUM_THREADS,'1');calls++;maximum=Math.max(maximum,++active);
    await new Promise(resolve=>setTimeout(resolve,20));active--;return {stdout:'{"status": "UNCHANGED"}'};
  };
  let middleware;
  const server={watcher,httpServer,middlewares:{use(handler){middleware=handler;}},config:{logger:{info(){},error(message){throw Error(message);}}}};
  await devIsaeProgress('/tmp/project',run).configureServer(server);
  const request={url:'/isae-progress/?view=all'},response={setHeader(){}};
  let next=false;middleware(request,response,()=>next=true);
  assert(next);assert.equal(request.url,'/isae-progress/index.html?view=all');
  watcher.emit('change','/tmp/project/unrelated.md');
  await new Promise(resolve=>setTimeout(resolve,450));assert.equal(calls,1);
  watcher.emit('change','/tmp/project/docs/validation/ISAE_STATUS.md');watcher.emit('change','/tmp/project/docs/validation/ISAE_STATUS.md');
  await new Promise(resolve=>setTimeout(resolve,500));assert.equal(calls,2);assert.equal(maximum,1);
  httpServer.emit('close');watcher.emit('change','/tmp/project/docs/validation/ISAE_STATUS.md');
  await new Promise(resolve=>setTimeout(resolve,450));assert.equal(calls,2);
});
