import test from 'node:test';
import assert from 'node:assert/strict';
import {parseSolverJSON, parseSolverReply, parseInitialProfiles, readSolverReply, solverBufferRange} from '../web/solver-json.js';

test('Bode wire replies retain results and structured rejection evidence', () => {
  for (const reply of [
    {result:{analysis:'frequency_response', samples:[{omega:1, converged:false}], name:'Γ rudder'}},
    {error:'Local section-normal Mach reached unity.', details:{maximum:{normal_mach:1.1}}},
  ]) assert.deepEqual(parseSolverReply(JSON.stringify(reply), 'frequency'), reply);
  const constraints={result:[{variable:'alpha', target:0}]};
  assert.deepEqual(parseSolverReply(JSON.stringify(constraints), 'steady_turn_constraints'), constraints);
});

test('malformed replies identify the calculation boundary and preserve the cause', () => {
  for (const text of ['\\m=', '', '{"result":', undefined]) {
    assert.throws(() => parseSolverReply(text, 'frequency'), e =>
      e.message.startsWith('Reading the Bode calculation result: invalid JSON.') && !!e.cause);
    assert.throws(() => parseSolverReply(text, 'extend_frequency'), /Bode calculation result/);
  }
  for (const reply of [null, [], {}, {result:null}, {result:[]}, {error:12}, {error:''}, {error:'failed',result:{}}])
    assert.throws(() => parseSolverReply(JSON.stringify(reply), 'frequency'), /incomplete solver response/);
  assert.throws(() => parseSolverJSON('<html>missing</html>', 'Loading the solver source bundle'),
    /Loading the solver source bundle: invalid JSON/);
});

test('invalid initial-profile settings point to the editable field without discarding valid profiles', () => {
  assert.deepEqual(parseInitialProfiles('[]'), []);
  const profiles=[{kind:'initial', name:'rudder offset', state:{}}];
  assert.deepEqual(parseInitialProfiles(JSON.stringify(profiles)), profiles);
  assert.throws(() => parseInitialProfiles('\\m='), e =>
    e.message.startsWith('Settings → Initial disturbances:') && !!e.cause);
  for (const value of [null, {}, [null], [{kind:'gust'}]])
    assert.throws(() => parseInitialProfiles(JSON.stringify(value)), /Initial disturbances/);
});

function byteRuntime(records, layout={}) {
  const events=[];let index=0;
  const py={_module:{},runPythonAsync:async code=>{
    events.push('compute');
    assert.equal(code, 'run_worker_parts(request_json, progress=time_progress)');
    return {
      part_count:records.length,
      next_part(){
        const data=records[index++];
        events.push('acquire');
        // Simulate memory growth on each record. The reader must acquire the
        // current heap after invoking Python, not cache its previous view.
        const heap=new Uint8Array(data.byteLength+16);heap.set(data,16);
        py._module.HEAPU8=heap;
        return {address:16,byte_length:data.byteLength,...layout,
          destroy(){events.push('release');heap.fill(0);}};
      },
      close(){events.push('close');},
      destroy(){events.push('destroy');},
    };
  }};
  return {py,events};
}
const bytes=value=>new TextEncoder().encode(JSON.stringify(value));

test('owned records decode before releasing their Python memory', async () => {
  const reply={result:{analysis:'frequency_response', label:'Γ · rudder', payload:'x'.repeat(2*1024*1024)}};
  const {py,events}=byteRuntime([bytes(reply)]);
  assert.deepEqual(await readSolverReply(py, 'frequency', ()=>events.push('computed')), reply);
  assert.deepEqual(events, ['compute','computed','acquire','release','close','destroy']);
});

test('41 Bode samples reconstruct exactly without a full-grid buffer or another calculation', async () => {
  const result={analysis:'frequency_response',label:'Γ · rudder',samples:Array.from({length:41},(_,i)=>({omega:i+.1,
    responses:[{output:{frame:{rates_body:{real:[-0,1e-100,i],imag:[0,-i,1e100]}}}}]})),frame_mode:'free'};
  const {py,events}=byteRuntime([bytes({result:{...result,samples:[]},sample_count:41}),...result.samples.map(sample=>bytes({sample}))]);
  const progress=[];
  assert.deepEqual(await readSolverReply(py,'frequency',()=>{},(done,total)=>progress.push([done,total])),JSON.parse(JSON.stringify({result})));
  assert.equal(events.filter(e=>e==='compute').length,1);
  assert.equal(events.filter(e=>e==='release').length,42);
  assert.deepEqual(progress.at(-1),[42,42]);
  assert.deepEqual(events.slice(-2),['close','destroy']);
});

test('unsigned byte ranges cross the wasm32 signed boundary without allocating gigabytes',()=>{
  const address=0x70000000,length=423290146;
  assert.equal(((address+length)|0)-(address|0),-3871677150);
  assert.deepEqual(solverBufferRange(address,length,0xc0000000),[address,length]);
  assert.deepEqual(solverBufferRange(0x90000000,1024,0xc0000000),[0x90000000,1024]);
  for(const range of [[-1,3,100],[0,-3871677150,100],[90,11,100],[2**32,1,2**32],[0,1.5,100],[0,NaN,100]])
    assert.throws(()=>solverBufferRange(...range),/buffer range/);
});

test('transfer failures release owned records and never repeat the calculation', async () => {
  for (const [data,layout,expected] of [
    [new Uint8Array([0xc3,0x28]), {}, /damaged UTF-8/],
    [new TextEncoder().encode('bad JSON'), {}, /Bode calculation result: invalid JSON/],
    [bytes({result:{}}), {address:-1}, /buffer range/],
    [bytes({result:{}}), {byte_length:1e9}, /buffer range/],
  ]) {
    const {py,events}=byteRuntime([data],layout);
    await assert.rejects(readSolverReply(py,'frequency'), expected);
    assert.deepEqual(events, ['compute','acquire','release','close','destroy']);
  }
  const {py,events}=byteRuntime([bytes({result:{}})]);
  await assert.rejects(readSolverReply(py,'frequency',()=>{throw new Error('status failed');}), /status failed/);
  assert.deepEqual(events, ['compute','close','destroy']);
  for(const header of [
    {result:{analysis:'frequency_response',samples:[]},sample_count:41},
    {result:{analysis:'frequency_response',samples:[{}]},sample_count:0},
    {result:{analysis:'other',samples:[]},sample_count:0},
  ]) {
    const {py}=byteRuntime([bytes(header)]);
    await assert.rejects(readSolverReply(py,'frequency'), /invalid sample header/);
  }
  const bad=byteRuntime([bytes({result:{analysis:'frequency_response',samples:[]},sample_count:1}),bytes({sample:null})]);
  await assert.rejects(readSolverReply(bad.py,'frequency'), /invalid sample record/);
  assert.deepEqual(bad.events.slice(-3),['release','close','destroy']);
});
