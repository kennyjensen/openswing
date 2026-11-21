import {execFile} from 'node:child_process';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {promisify} from 'node:util';

const execute=promisify(execFile);

// Reuse Vite's existing file watcher. Only a status/scope change starts the
// plotting process, and all updates are serialized. No validation solve runs.
export function devIsaeProgress(directory, run=execute) {
  const root=directory instanceof URL?fileURLToPath(directory):path.resolve(directory);
  const files=['docs/validation/ISAE_STATUS.md','docs/validation/isae-progress-scopes.json','scripts/isae_progress.py','web/plot-colors.js']
    .map(name=>path.resolve(root,name));
  return {
    name:'openswing-isae-progress',
    apply:'serve',
    configureServer(server) {
      server.middlewares.use((request,response,next)=>{
        const url=new URL(request.url,'http://localhost');
        if(url.pathname==='/isae-progress') {
          response.writeHead(302,{Location:'/isae-progress/'+url.search});response.end();return;
        }
        if(url.pathname.startsWith('/isae-progress/'))response.setHeader('Cache-Control','no-cache');
        // Vite's public-file lookup uses exact filenames, not directory indexes.
        if(url.pathname==='/isae-progress/')request.url='/isae-progress/index.html'+url.search;
        next();
      });
      let timer,closed=false,queue=Promise.resolve();
      function regenerate() {
        queue=queue.then(async()=>{
          if(closed)return;
          try {
            const {stdout}=await run(path.join(root,'.venv/bin/python'),['scripts/isae_progress.py'],{
              cwd:root,timeout:60000,maxBuffer:1024*1024,
              env:{...process.env,OPENBLAS_NUM_THREADS:'1',OMP_NUM_THREADS:'1',MKL_NUM_THREADS:'1',PYTHONDONTWRITEBYTECODE:'1'},
            });
            if(stdout.includes('"status": "RECORDED"'))server.config.logger.info('ISAE progress plots updated: /isae-progress/');
          } catch(error) {
            server.config.logger.error('ISAE progress update failed: '+(error.stderr||error.message));
          }
        });
        return queue;
      }
      function changed(file) {
        if(!files.includes(path.resolve(file)))return;
        clearTimeout(timer);timer=setTimeout(regenerate,400);
      }
      server.watcher.add(files);server.watcher.on('change',changed);server.watcher.on('add',changed);
      server.httpServer?.once('close',()=>{
        closed=true;clearTimeout(timer);server.watcher.off('change',changed);server.watcher.off('add',changed);
      });
      // Also catch a status edit made while the server was stopped.
      return regenerate();
    },
  };
}
