import {test as base} from '@playwright/test';
import {createServer} from 'node:http';
import {createReadStream} from 'node:fs';
import {stat} from 'node:fs/promises';
import path from 'node:path';

// Optional isolated static application; the fixture owns its server lifetime.
export const test=base.extend({baseURL:async({baseURL},use)=>{
  if(!process.env.OPENSWING_STATIC_APP)return use(baseURL);
  const root=path.resolve(process.env.OPENSWING_STATIC_APP);
  const types={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript',
    '.css':'text/css','.json':'application/json','.wasm':'application/wasm',
    '.svg':'image/svg+xml','.woff2':'font/woff2','.ttf':'font/ttf','.py':'text/plain'};
  const server=createServer(async(req,res)=>{
    try{
      const name=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
      const file=path.resolve(root,'.'+(name==='/'?'/index.html':name));
      if(!file.startsWith(root+path.sep))throw new Error('Invalid path');
      const info=await stat(file);if(!info.isFile())throw new Error('Missing file');
      res.writeHead(200,{'Content-Type':types[path.extname(file)]||'application/octet-stream',
        'Content-Length':info.size,'Cache-Control':'no-store'});
      if(req.method==='HEAD')res.end();else createReadStream(file).pipe(res);
    }catch{res.writeHead(404);res.end();}
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  try{await use(`http://127.0.0.1:${server.address().port}`);}
  finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
}});
export {expect} from '@playwright/test';
