import test from 'node:test';
import assert from 'node:assert/strict';
import {loadKernelDependencies} from '../web/kernel-startup.js';

const deferred=()=>{
  let resolve,reject;
  const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});
  return {promise,resolve,reject};
};
const stages=messages=>messages.map(message=>Number(message.match(/stage (\d)\/3/)[1]));

test('startup overlaps runtime and sources, and waits for libraries before preparation',async()=>{
  const runtimeLoad=deferred(),sourceLoad=deferred(),libraryLoad=deferred(),libraryStarted=deferred();
  const messages=[],started=[],sources=[['bridge.py','# exact source\n']];
  const runtime={loadPackage(names){
    assert.deepEqual(names,['numpy','scipy']);libraryStarted.resolve();return libraryLoad.promise;
  }};
  const boot=loadKernelDependencies({
    loadRuntime(){started.push('runtime');return runtimeLoad.promise;},
    loadSources(){started.push('sources');return sourceLoad.promise;},
    onStatus:message=>messages.push(message),
  });
  assert.deepEqual(started,['runtime','sources']);
  assert.deepEqual(stages(messages),[1]);
  sourceLoad.resolve(sources);runtimeLoad.resolve(runtime);
  await libraryStarted.promise;
  assert.deepEqual(stages(messages),[1,2]);
  libraryLoad.resolve();
  const result=await boot;
  assert.equal(result.py,runtime);assert.equal(result.sources,sources);
  assert.deepEqual(stages(messages),[1,2,3]);
});

test('source failure stays terminal when the runtime finishes later',async()=>{
  const runtimeLoad=deferred(),failure=new Error('Could not load solver sources (HTTP 404).');
  const messages=[];let libraryLoads=0;
  const boot=loadKernelDependencies({
    loadRuntime:()=>runtimeLoad.promise,
    loadSources(){throw failure;},
    onStatus:message=>messages.push(message),
  });
  await assert.rejects(boot,error=>error===failure);
  runtimeLoad.resolve({loadPackage(){libraryLoads++;}});
  // Let the already-running runtime branch settle after the caller saw error.
  await runtimeLoad.promise;
  assert.equal(libraryLoads,0);assert.deepEqual(stages(messages),[1]);
});

test('source failure during library loading never advances to solver preparation',async()=>{
  const sourceLoad=deferred(),libraryLoad=deferred(),libraryStarted=deferred();
  const messages=[],failure=new Error('Truncated source bundle');
  const boot=loadKernelDependencies({
    loadRuntime:async()=>({loadPackage(){libraryStarted.resolve();return libraryLoad.promise;}}),
    loadSources:()=>sourceLoad.promise,
    onStatus:message=>messages.push(message),
  });
  const rejected=assert.rejects(boot,error=>error===failure);
  await libraryStarted.promise;sourceLoad.reject(failure);await rejected;
  libraryLoad.resolve();await libraryLoad.promise;
  assert.deepEqual(stages(messages),[1,2]);
});

test('runtime and library failures preserve their original errors',async()=>{
  for(const phase of ['runtime','libraries']){
    const sourceLoad=deferred(),messages=[],failure=new Error(`${phase} unavailable`);
    const boot=loadKernelDependencies({
      loadRuntime(){
        if(phase==='runtime')throw failure;
        return {loadPackage(){throw failure;}};
      },
      loadSources:()=>sourceLoad.promise,
      onStatus:message=>messages.push(message),
    });
    await assert.rejects(boot,error=>error===failure);
    sourceLoad.resolve([]);await sourceLoad.promise;
    assert.deepEqual(stages(messages),phase==='runtime'?[1]:[1,2]);
  }
});

test('a late second failure does not replace the first error or emit progress',async()=>{
  const runtimeLoad=deferred(),failure=new Error('Source download failed'),messages=[];
  const boot=loadKernelDependencies({
    loadRuntime:()=>runtimeLoad.promise,
    loadSources:async()=>{throw failure;},
    onStatus:message=>messages.push(message),
  });
  await assert.rejects(boot,error=>error===failure);
  runtimeLoad.reject(new Error('Runtime download also failed'));
  // Promise.all must have a rejection handler on the late runtime branch.
  await new Promise(resolve=>setImmediate(resolve));
  assert.deepEqual(stages(messages),[1]);
});
