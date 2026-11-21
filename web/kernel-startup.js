// Pyodide downloads the packages during bootstrap. Load source files in
// parallel with both, and prepare the solver only when every dependency is ready.
export async function loadKernelDependencies({loadRuntime,loadSources,onStatus}) {
  onStatus('Loading browser runtime and numerical libraries…');
  const [py,sources]=await Promise.all([
    Promise.resolve().then(()=>loadRuntime({packages:['numpy','scipy']})),
    Promise.resolve().then(loadSources),
  ]);
  onStatus('Preparing solver…');
  return {py,sources};
}
