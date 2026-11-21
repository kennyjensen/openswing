import {test,expect} from './static-app.js';
import {readFile,writeFile,readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';

test.use({launchOptions:{executablePath:process.env.OPENSWING_CHROMIUM_EXECUTABLE,
  args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--disable-webgl','--js-flags=--max-old-space-size=192']}});

test('cold local kernel loads complete sources and preserves an offline aerodynamic result',async({page,context,baseURL},info)=>{
  const requests=[],blocked=[],errors=[];
  context.on('request',r=>requests.push(r.url()));page.on('pageerror',e=>errors.push(e.message));
  await context.route('**/*',route=>{
    if(new URL(route.request().url()).origin===baseURL)return route.continue();
    blocked.push(route.request().url());return route.abort();
  });
  await page.addInitScript(()=>{
    window.kernelBoots=[];const Native=window.Worker;
    window.Worker=class extends Native{
      constructor(...args){
        super(...args);const boot={started:performance.now(),stages:[]};window.kernelBoots.push(boot);
        this.addEventListener('message',({data})=>{
          if(data.type==='status')boot.stages.push({ms:performance.now()-boot.started,text:data.message});
          if(data.type==='ready')boot.ready_ms=performance.now()-boot.started;
        });
      }
    };
  });
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#example').selectOption('rectangular');
  await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');
  await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#mode').selectOption('rigid');
  await page.locator('#speed').fill('30');await page.locator('#alpha').fill('5');
  await context.setOffline(true);
  await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Analysis converged');
  const pending=page.waitForEvent('download');await page.locator('#export-json').click();
  const result=JSON.parse(await readFile(await(await pending).path(),'utf8'));
  expect(result.CL).toBeGreaterThan(.3);expect(result.CL).toBeLessThan(.6);
  expect(result.residual).toBeLessThan(1e-8);
  const modules={};
  for(const name of (await readdir('openswing')).filter(n=>n.endsWith('.py'))){
    modules[name]=createHash('sha256').update(await readFile(`openswing/${name}`)).digest('hex');
  }
  expect(result.software_provenance.modules).toEqual(modules);
  const kernelRequests=requests.filter(url=>new URL(url).pathname.startsWith('/kernel/'));
  if(process.env.OPENSWING_LEGACY_KERNEL==='1')expect(kernelRequests).toHaveLength(Object.keys(modules).length+1);
  else {
    expect(kernelRequests).toHaveLength(1);
    expect(new URL(kernelRequests[0]).pathname).toMatch(/^\/kernel\/sources(?:-[0-9a-f]{64})?\.json$/);
  }
  const boots=await page.evaluate(()=>window.kernelBoots);
  expect(boots).toHaveLength(1);expect(boots[0].ready_ms).toBeGreaterThan(0);
  expect(errors).toEqual([]);expect(blocked).toEqual([]);
  await writeFile(info.outputPath('kernel-loading.json'),JSON.stringify({boots,kernelRequests,requests,blocked,errors,result},null,2)+'\n');
});
