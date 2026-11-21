import test from 'node:test';
import assert from 'node:assert/strict';
import {loadKernelDependencies} from '../web/kernel-startup.js';

const deferred=()=>{
  let resolve,reject;
  const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});
  return {promise,resolve,reject};
};

test('startup overlaps the package-enabled runtime with source loading',async()=>{
  const runtimeLoad=deferred(),sourceLoad=deferred();
  const runtime={},sources=[['bridge.py','# exact source\n']];
  const messages=[],started=[];
  const boot=loadKernelDependencies({
    loadRuntime({packages}){
      assert.deepEqual(packages,['numpy','scipy']);
      started.push('runtime');
      return runtimeLoad.promise;
    },
    loadSources(){started.push('sources');return sourceLoad.promise;},
    onStatus:message=>messages.push(message),
  });
  await Promise.resolve();
  assert.deepEqual(started,['runtime','sources']);
  assert.equal(messages.length,1);
  sourceLoad.resolve(sources);
  await sourceLoad.promise;
  assert.equal(messages.length,1);
  runtimeLoad.resolve(runtime);
  assert.deepEqual(await boot,{py:runtime,sources});
  assert.equal(messages.at(-1),'Preparing solver…');
});

for(const failed of ['runtime','sources']) {
  test(`${failed} failure preserves the original error and stops startup progress`,async()=>{
    const runtimeLoad=deferred(),sourceLoad=deferred();
    const error=new Error(`${failed} unavailable`),messages=[];
    const boot=loadKernelDependencies({
      loadRuntime:()=>runtimeLoad.promise,
      loadSources:()=>sourceLoad.promise,
      onStatus:message=>messages.push(message),
    });
    const first=failed==='runtime'?runtimeLoad:sourceLoad;
    const second=failed==='runtime'?sourceLoad:runtimeLoad;
    first.reject(error);
    await assert.rejects(boot,cause=>cause===error);
    second.reject(new Error('Late dependency failure'));
    await new Promise(resolve=>setImmediate(resolve));
    assert.equal(messages.length,1);
  });
}
