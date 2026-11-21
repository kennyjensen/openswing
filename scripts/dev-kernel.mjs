import {readdir, readFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {readKernelSources} from './kernel-sources.mjs';

// Development must use the same sources as native checks. Production still
// packages its kernel through prepare.mjs; it never reads the working tree.
export function devKernel(sourceDirectory) {
  const root=sourceDirectory instanceof URL ? fileURLToPath(sourceDirectory) : path.resolve(sourceDirectory);
  return {
    name:'openswing-dev-kernel',
    apply:'serve',
    configureServer(server) {
      server.middlewares.use(async (request,response,next)=>{
        const pathname=new URL(request.url,'http://localhost').pathname;
        if(!pathname.startsWith('/kernel/'))return next();
        response.setHeader('Cache-Control','no-store');
        if(!['GET','HEAD'].includes(request.method)) {
          response.setHeader('Allow','GET, HEAD');response.statusCode=405;response.end();return;
        }
        const name=pathname.slice('/kernel/'.length);
        // An absent/invalid source must not fall through to an older public copy.
        if(!['manifest.json','sources.json'].includes(name)&&!/^[A-Za-z_]\w*\.py$/.test(name)) {
          response.statusCode=404;response.end();return;
        }
        try {
          const body=name==='sources.json' ? Buffer.from(JSON.stringify(await readKernelSources(root)))
            : name==='manifest.json'
            ? Buffer.from(JSON.stringify((await readdir(root,{withFileTypes:true}))
                .filter(entry=>entry.isFile()&&entry.name.endsWith('.py')).map(entry=>entry.name).sort()))
            : await readFile(path.join(root,name));
          response.setHeader('Content-Type',name.endsWith('.json')?'application/json':'text/plain; charset=utf-8');
          response.setHeader('Content-Length',body.length);
          response.end(request.method==='HEAD'?undefined:body);
        } catch(error) {
          response.statusCode=error.code==='ENOENT'?404:500;
          response.end('Could not load the current solver source.');
        }
      });
    },
  };
}
