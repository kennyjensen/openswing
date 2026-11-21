import {readdir,readFile} from 'node:fs/promises';
import path from 'node:path';

// Capture each source once so individual files and the browser bundle agree.
export async function readKernelSources(directory){
  const names=(await readdir(directory,{withFileTypes:true}))
    .filter(entry=>entry.isFile()&&entry.name.endsWith('.py')).map(entry=>entry.name).sort();
  const sources=[];
  for(const name of names){
    if(!/^[A-Za-z_]\w*\.py$/.test(name))throw new Error(`Invalid solver module name: ${name}`);
    const bytes=await readFile(path.join(directory,name)),source=bytes.toString('utf8');
    if(!Buffer.from(source,'utf8').equals(bytes))throw new Error(`Solver module is not UTF-8: ${name}`);
    sources.push([name,source]);
  }
  return {format:'openswing-kernel-sources',version:1,sources};
}
