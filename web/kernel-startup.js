// Keep the two downloads concurrent, but never report new startup progress
// after either dependency has failed. The caller reports the original error.
export async function loadKernelDependencies({loadRuntime,loadSources,onStatus}) {
  let failed=false;
  onStatus('Starting browser runtime · stage 1/3…');
  try {
    const [py,sources]=await Promise.all([
      (async()=>{
        const runtime=await loadRuntime();
        // A failed source download may finish before the larger runtime load.
        // Avoid starting numerical-library loading after that known failure.
        if(failed)return;
        onStatus('Loading numerical libraries · stage 2/3…');
        await runtime.loadPackage(['numpy','scipy']);
        return runtime;
      })(),
      (async()=>loadSources())(),
    ]);
    onStatus('Preparing solver · stage 3/3…');
    return {py,sources};
  } catch(error) {
    failed=true;
    throw error;
  }
}
