// Bounded UI check: no physics, runtime libraries, or external requests.
import {chromium} from 'playwright';
import {createServer} from 'vite';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import assert from 'node:assert/strict';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const output=path.resolve(process.argv[2]||'artifacts/isae/progress-dashboard-20261106');
await mkdir(output,{recursive:true});
const history=path.join(root,'docs/validation/isae-progress/history.json');
const hash=async()=>createHash('sha256').update(await readFile(history)).digest('hex');
const before=await hash();
const audit={checks:[],page_errors:[],external_requests:[]};
let server,browser;
function check(name,value){audit.checks.push({name,passed:!!value});assert(value,name);}
try {
  server=await createServer({root,server:{host:'127.0.0.1',port:0},logLevel:'warn'});
  await server.listen();
  const origin=`http://127.0.0.1:${server.httpServer.address().port}`;
  const html=await (await fetch(origin+'/isae-progress/')).text();
  check('directory_route_is_dashboard',html.includes('<h1>ISAE validation progress</h1>'));
  browser=await chromium.launch({headless:true,timeout:30000,
    executablePath:process.env.OPENSWING_CHROMIUM_EXECUTABLE||path.join(root,'artifacts/isae/browser-libs-20261101/chromium/chrome-linux/chrome'),
    env:{...process.env,LP_NUM_THREADS:'1',LD_LIBRARY_PATH:[path.join(root,'artifacts/isae/browser-libs-20261101/lib'),process.env.LD_LIBRARY_PATH].filter(Boolean).join(':')},
    args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--disable-webgl','--js-flags=--max-old-space-size=192']});
  const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});
  await context.route(/^https?:/,route=>{
    if(new URL(route.request().url()).origin===origin)return route.continue();
    audit.external_requests.push(route.request().url());return route.abort();
  });
  const page=await context.newPage();page.setDefaultTimeout(15000);
  page.on('pageerror',error=>audit.page_errors.push(error.message));
  await page.goto(origin+'/isae-progress/');
  check('page_title',await page.title()==='ISAE validation progress · OpenSwing');
  check('all_41_case_cards',await page.locator('article').count()===41);
  await page.evaluate(async()=>{
    const images=[...document.images];images.forEach(image=>image.loading='eager');
    await Promise.all(images.map(image=>image.decode()));
  });
  check('every_chart_loaded',await page.locator('img').evaluateAll(images=>images.every(i=>i.complete&&i.naturalWidth>0)));
  check('desktop_fits',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:path.join(output,'desktop.png')});
  const data=await (await fetch(origin+'/isae-progress/data.json')).json();
  check('history_served',data.events.length>0&&data.events.at(-1).cases.length===41);
  const csv=await (await fetch(origin+'/isae-progress/history.csv')).text();
  check('csv_all_case_observations',csv.trim().split('\n').length===1+41*data.events.length);
  await page.setViewportSize({width:390,height:844});
  await page.selectOption('#family','FFWT');
  check('family_filter',await page.locator('article:visible').count()===5);
  check('mobile_fits',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:path.join(output,'mobile.png'),fullPage:true});
  await page.reload();
  check('filter_survives_refresh',await page.locator('article:visible').count()===5);
  const downloadEvent=page.waitForEvent('download');
  await page.getByRole('link',{name:'Timestamped CSV'}).click();
  const download=await downloadEvent;await download.saveAs(path.join(output,'download.csv'));
  check('csv_download',await readFile(path.join(output,'download.csv'),'utf8')===csv);
  check('no_page_errors',audit.page_errors.length===0);
  check('no_external_requests',audit.external_requests.length===0);
  check('opening_dashboard_does_not_add_history',await hash()===before);
  audit.status='PASS';
} catch(error) {
  audit.status='FAIL';audit.error=error.stack;process.exitCode=1;
} finally {
  await browser?.close();await server?.close();
  await writeFile(path.join(output,'report.json'),JSON.stringify(audit,null,2)+'\n');
  console.log(JSON.stringify(audit));
}
