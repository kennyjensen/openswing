import {indexTimeSnapshot} from './worker-time-history.js';
// Keep JSON failures attributable to the boundary that received the data.
// In particular, do not expose a bare SyntaxError after a long Bode solve.
export function parseSolverJSON(text, context) {
  try {
    if (typeof text !== 'string') throw new TypeError('Expected JSON text.');
    return JSON.parse(text);
  } catch (cause) {
    throw new Error(`${context}: invalid JSON. Reload the page and retry.`, {cause});
  }
}

export function parseSolverReply(text, action) {
  const frequency = ['frequency', 'extend_frequency'].includes(action);
  const label = frequency
    ? 'Reading the Bode calculation result' : 'Reading the solver result';
  const reply = parseSolverJSON(text, label);
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  if (!object(reply)
      || (Object.hasOwn(reply, 'error')
        ? typeof reply.error !== 'string' || !reply.error || Object.hasOwn(reply, 'result')
        : !(object(reply.result) || (!frequency && Array.isArray(reply.result))))) {
    throw new Error(`${label}: incomplete solver response. Reload the page and retry.`);
  }
  return reply;
}

export function solverBufferRange(address, length, heapLength) {
  // Addresses arrive as positive Python integers. Do not coerce them with
  // bitwise operators: wasm32 addresses above 2 GiB would become negative.
  if (![address,length,heapLength].every(Number.isSafeInteger)
      || address < 0 || length < 0 || address > 0xffffffff
      || address > heapLength || length > heapLength-address)
    throw new Error('Reading the solver result: invalid UTF-8 buffer range.');
  return [address,length];
}

export async function readSolverReply(py, action, onComputed = () => {}, onPart = () => {}) {
  // The pinned Pyodide getBuffer implementation subtracts signed pointers;
  // ranges crossing 2 GiB can acquire a negative length. Read the owned range
  // using unsigned integer metadata and a fresh Emscripten heap instead. This
  // deliberately uses _module (a pinned-runtime compatibility boundary).
  // Decode one frequency sample or copy one compressed time report at a time;
  // never allocate a full-history string or rerun a failed transfer.
  const packet = await py.runPythonAsync('run_worker_parts(request_json, progress=time_progress)');
  let reply,history;
  try {
    onComputed();
    const count=packet.part_count;
    if (!Number.isSafeInteger(count) || count < 1) throw new Error('Reading the solver result: invalid record count.');
    for (let i=0;i<count;i++) {
      const part=packet.next_part();
      if (!part) throw new Error('Reading the solver result: missing response record.');
      let text,blob;
      try {
        const address=part.address, length=part.byte_length;
        // Reading Python properties can grow memory. Acquire the heap last,
        // and make no Python calls while this view is being decoded.
        const heap=py._module?.HEAPU8;
        if (!heap) throw new Error('Reading the solver result: browser runtime memory is unavailable.');
        const range=solverBufferRange(address,length,heap.byteLength);
        try {
          const view=new Uint8Array(heap.buffer,...range);
          if(history&&i>0)blob=new Blob([view],{type:'application/gzip'});
          else text=new TextDecoder('utf-8',{fatal:true}).decode(view);
        }
        catch (cause) { throw new Error('Reading the solver result: damaged UTF-8 response.',{cause}); }
      } finally { part.destroy(); }
      if (i===0) {
        reply=parseSolverReply(text,action);
        if(Object.hasOwn(reply,'snapshot_count')){
          if(!Number.isSafeInteger(reply.snapshot_count)||reply.snapshot_count<1
              ||count!==reply.snapshot_count+1||reply.result?.analysis!=='time_response'
              ||Object.hasOwn(reply.result,'snapshots')||reply.snapshot_encoding!=='gzip-json-v1')
            throw new Error('Reading time response: invalid snapshot header.');
          delete reply.snapshot_count;delete reply.snapshot_encoding;
          history=reply.result.snapshot_storage={format:'openswing-worker-time-history',version:1,records:[],entries:[]};
        } else if (Object.hasOwn(reply,'sample_count')) {
          if (!Number.isSafeInteger(reply.sample_count) || reply.sample_count<0
              || count!==reply.sample_count+1 || reply.result?.analysis!=='frequency_response'
              || !Array.isArray(reply.result.samples) || reply.result.samples.length)
            throw new Error('Reading the Bode calculation result: invalid sample header.');
          delete reply.sample_count;
        } else if (count!==1) throw new Error('Reading the solver result: unexpected response records.');
      } else if(history){
        history.entries.push(await indexTimeSnapshot(blob));
        history.records.push(blob);
      } else {
        const row=parseSolverJSON(text,'Reading a completed Bode sample');
        if (!row?.sample || typeof row.sample!=='object' || Array.isArray(row.sample))
          throw new Error('Reading the Bode calculation result: invalid sample record.');
        reply.result.samples.push(row.sample);
      }
      onPart(i+1,count);
    }
  } finally {
    try { packet.close(); }
    finally { packet.destroy(); }
  }
  return reply;
}

export function parseInitialProfiles(text) {
  let profiles;
  try { profiles = JSON.parse(text); }
  catch (cause) {
    throw new Error('Settings → Initial disturbances: enter a JSON array of profiles, or [] for no initial disturbance.', {cause});
  }
  if (!Array.isArray(profiles) || profiles.some(p => !p || p.kind !== 'initial'))
    throw new Error('Settings → Initial disturbances: each profile must have kind: "initial". Use [] for no initial disturbance.');
  return profiles;
}
