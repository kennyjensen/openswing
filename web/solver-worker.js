let warmedWorker;
let claimed = false;

function createWorker() {
  return new Worker(new URL('./worker.js', import.meta.url), {type:'module'});
}

export function prewarmSolver() {
  if (claimed || warmedWorker) return;
  const worker = createWorker();
  warmedWorker = worker;
  worker.addEventListener('error', () => {
    if (warmedWorker === worker) discardPrewarmedSolver();
  }, {once:true});
  worker.postMessage({type:'prewarm'});
}

export function takeSolverWorker() {
  claimed = true;
  const worker = warmedWorker;
  warmedWorker = undefined;
  return worker ?? createWorker();
}

export function discardPrewarmedSolver() {
  warmedWorker?.terminate();
  warmedWorker = undefined;
}
