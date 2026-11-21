/* Runs one scientific kernel in an isolated worker. No aircraft data is sent to a server. */
import { mountedProgress, timeProgress, progressBoundary } from './solve-progress.js';
import { unpackTimeResult } from './time-result-storage.js';
import { loadKernelSources } from './kernel-sources.js';
import { loadKernelDependencies } from './kernel-startup.js';
import { parseSolverJSON, readSolverReply } from './solver-json.js';
let ready;
let provenance;
async function initialize() {
  // An absolute URL prevents Vite's dev import helper from appending ?import
  // to a public runtime asset. Production uses the same origin and path.
  const runtimeURL = new URL('/runtime/pyodide.mjs', self.location.origin).href;
  // These small source files change between releases. The pinned runtime stays
  // cacheable, but a new UI must not combine with cached older Python modules.
  // Download sources while the larger runtime and libraries initialize.
  const {py,sources} = await loadKernelDependencies({
    loadRuntime: async (options) => {
      const { loadPyodide } = await import(/* @vite-ignore */ runtimeURL);
      return loadPyodide({ indexURL: '/runtime/', ...options });
    },
    loadSources: () => loadKernelSources(fetch, __OPENSWING_KERNEL_URL__),
    onStatus: message => self.postMessage({type:'status',message}),
  });
  py.FS.mkdirTree('/home/pyodide/openswing');
  for (const [name, source] of sources) py.FS.writeFile(`/home/pyodide/openswing/${name}`, source);
  await py.runPythonAsync('from openswing.bridge import run_worker_parts');
  // Fingerprint the exact source bytes loaded into this worker and the actual
  // numerical runtime. Archives retain this record with their computed values.
  py.globals.set('pyodide_version',py.version);
  provenance=parseSolverJSON(await py.runPythonAsync(`
import hashlib, json, sys, pathlib, numpy, scipy
_modules={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(pathlib.Path('/home/pyodide/openswing').glob('*.py'))}
_runtime=dict(pyodide=pyodide_version,python=sys.version.split()[0],numpy=numpy.__version__,scipy=scipy.__version__)
_fingerprint=hashlib.sha256(json.dumps(dict(modules=_modules,runtime=_runtime),sort_keys=True,separators=(',',':')).encode()).hexdigest()
json.dumps(dict(format='openswing-kernel-provenance',version=1,fingerprint=_fingerprint,modules=_modules,runtime=_runtime))
`), 'Reading the solver runtime identification');
  self.postMessage({ type: 'ready' });
  return py;
}
let queue = Promise.resolve();
self.onmessage = event => {
  if (event.data?.type === 'prewarm') {
    ready ??= initialize();
    // The first real request receives any initialization error.
    ready.catch(() => {});
    return;
  }
  queue = queue.then(() => handle(event));
};
async function handle(event) {
  const { id, request } = event.data;
  let phase = 'Loading the browser solver';
  try {
    ready ??= initialize();
    const py = await ready;
    phase = ['frequency', 'extend_frequency'].includes(request.action)
      ? 'Running the Bode calculation' : 'Running the solver request';
    const timeRequest=['time','launch_time','resume_time'].includes(request.action);
    if(timeRequest)phase='Finding the starting state for time response';
    py.globals.set('request_json', JSON.stringify(request));
    let lastProgress=-Infinity,lastStage;
    let trackMounted = mountedProgress();
    const trackTime = timeProgress();
    let point=0,totalPoints=0;
    py.globals.set('time_progress',(...args)=>{
      const [reportedStage,time,steps]=typeof args[0]==='string'?args:[null,...args];
      if(request.action==='operating_points'&&reportedStage==='operating_point'){
        point=time;totalPoints=steps;trackMounted=mountedProgress();
      }
      const stage=reportedStage?.startsWith('operating_point/')?reportedStage.slice('operating_point/'.length):reportedStage;
      if(timeRequest&&(stage===null||stage==='time_step'))phase=`Integrating time response after t = ${Number(time).toPrecision(6)}`;
      const mounted = trackMounted(stage,time,steps), timing = trackTime(stage,time,steps);
      const boundary = progressBoundary(stage,time,steps,lastStage);
      lastStage=stage;
      if(!boundary&&performance.now()-lastProgress<500)return;
      lastProgress=performance.now();
      self.postMessage({id,type:'progress',action:request.action,stage,time,steps,...mounted,...timing,
        ...(request.action==='operating_points'?{point,total_points:totalPoints}:{})});
    });
    const reply = await readSolverReply(py, request.action, () => {
      phase=timeRequest?'Reading the completed time-response history':'Reading the completed solver result';
      if (['frequency', 'extend_frequency'].includes(request.action))
        self.postMessage({type:'status', message:'Reading completed Bode response…'});
    }, (done,total) => {
      if (['frequency', 'extend_frequency'].includes(request.action) && total>1)
        self.postMessage({type:'status', message:`Reading completed Bode samples: ${done-1}/${total-1}…`});
      if(['time','launch_time','resume_time'].includes(request.action)&&total>1&&(done%25===0||done===total))
        self.postMessage({type:'status',message:`Preparing time-response plots: ${done-1}/${total-1} samples…`});
    });
    if(reply.error) self.postMessage({id,...reply,software_provenance:provenance});
    else self.postMessage({ id, result: {...unpackTimeResult(reply.result),software_provenance:provenance} });
  } catch (error) {
    console.error('OpenSwing solver request failed', error);
    // Runtime/package JSON parsing happens inside Pyodide. Give those errors
    // context too, while preserving its original stack in the console.
    const message = String(error.message || error);
    self.postMessage({ id, error: /MemoryError/.test(message)
      ? `${phase}: the browser solver ran out of memory.`
      : error instanceof SyntaxError ? `${phase}: ${message.replace(/\s+/g, ' ')}` : message });
  }
}
