import {parseSolverJSON} from './solver-json.js';

// The transport changes; the exact Python files and their provenance do not.
export function decodeKernelSources(bundle){
  if(bundle?.format!=='openswing-kernel-sources'||bundle.version!==1||!Array.isArray(bundle.sources))
    throw new Error('Invalid solver source bundle. Reload the application to retry.');
  const names=new Set();
  for(const entry of bundle.sources){
    if(!Array.isArray(entry)||entry.length!==2||typeof entry[0]!=='string'
        ||!/^[A-Za-z_]\w*\.py$/.test(entry[0])||typeof entry[1]!=='string'||names.has(entry[0]))
      throw new Error('Invalid or duplicate module in the solver source bundle.');
    names.add(entry[0]);
  }
  if(!names.has('__init__.py')||!names.has('bridge.py'))throw new Error('Incomplete solver source bundle.');
  return bundle.sources;
}

export async function loadKernelSources(fetcher=fetch){
  const response=await fetcher('/kernel/sources.json',{cache:'no-store'});
  if(!response.ok)throw new Error(`Could not load solver sources (HTTP ${response.status}). Reload the application to retry.`);
  return decodeKernelSources(parseSolverJSON(await response.text(), 'Loading the solver source bundle'));
}
