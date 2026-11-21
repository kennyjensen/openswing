import assert from 'node:assert/strict';
import test from 'node:test';

class WorkerStub extends EventTarget {
  static last;
  constructor() { super(); WorkerStub.last=this; }
  messages=[];
  terminated=false;
  postMessage(message) { this.messages.push(message); }
  terminate() { this.terminated=true; }
}

async function setup(t) {
  const descriptor=Object.getOwnPropertyDescriptor(globalThis,'Worker');
  Object.defineProperty(globalThis,'Worker',{configurable:true,value:WorkerStub});
  t.after(()=>{
    if(descriptor)Object.defineProperty(globalThis,'Worker',descriptor);
    else delete globalThis.Worker;
  });
  return import(`../web/solver-worker.js?${encodeURIComponent(t.name)}`);
}

test('the workbench takes the prewarmed worker once',async t=>{
  const {prewarmSolver,takeSolverWorker}=await setup(t);
  prewarmSolver();
  prewarmSolver();
  const worker=takeSolverWorker();
  assert.deepEqual(worker.messages,[{type:'prewarm'}]);
  prewarmSolver();
  assert.deepEqual(takeSolverWorker().messages,[]);
});

for(const reason of ['cancelled','failed']) {
  test(`a ${reason} warmup leaves a fresh worker for inspection`,async t=>{
    const {prewarmSolver,takeSolverWorker,discardPrewarmedSolver}=await setup(t);
    prewarmSolver();
    const worker=WorkerStub.last;
    if(reason==='cancelled')discardPrewarmedSolver();
    else worker.dispatchEvent(new Event('error'));
    assert.equal(worker.terminated,true);
    assert.deepEqual(takeSolverWorker().messages,[]);
  });
}
