import {test,expect} from '@playwright/test';
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const sha=b=>createHash('sha256').update(b).digest('hex');
const ready=async page=>{
 await expect(page.locator('#solve')).toBeEnabled();
 await expect(page.locator('#error')).toBeHidden();
};

test('SA-13 outline imports and body loads reproduce offline, with endpoint failures retained',async({page,context},info)=>{
 test.setTimeout(600000);
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const bytes=await readFile('docs/validation/isae-sa13.json'),study=JSON.parse(bytes);
 const sourceBytes=await readFile('docs/validation/isae-sa13-sources.json'),sources=JSON.parse(sourceBytes);
 const wasmBytes=await readFile('docs/validation/isae-sa13-wasm.json'),wasm=JSON.parse(wasmBytes);
 const modules={};
 for(const n of(await readdir('openswing')).filter(n=>n.endsWith('.py')))modules[n]=sha(await readFile('openswing/'+n));
 expect(modules).toEqual(study.provenance.modules);
 expect(sha(sourceBytes)).toBe(study.provenance.source_report_sha256);
 const candidatePath=process.env.OPENSWING_ENDPOINT_CANDIDATE;
 let candidate=null;
 if(candidatePath){
  candidate=await readFile(candidatePath);modules['asw.py']=sha(candidate);
  await context.route('**/kernel/asw.py',route=>route.fulfill({status:200,contentType:'text/plain',body:candidate}));
  await context.route('**/kernel/sources.json',async route=>{
    const response=await route.fetch(),bundle=await response.json();
    const entry=bundle.sources.find(([name])=>name==='asw.py');
    expect(entry).toBeDefined();entry[1]=candidate.toString('utf8');
    await route.fulfill({response,json:bundle});
  });
 }
 await page.goto('/');await ready(page);await context.setOffline(true);
 await page.locator('#panels').fill('32');await page.locator('#panels').press('Tab');await ready(page);
 const rejections=[];
 const negativeBase='Name\nNegative radius control\nEnd\nUnit\nL 1 m\nT 1 s\nF 1 N\nEnd\nConstant\n9.80665 1 340.21\nEnd\nReference\n1 1 1\n0 0 0\nEnd\nBeam 1\nBody\nt x\n0 0\n3 3\nt radius\n';
 if(candidate){
  for(const [name,table] of [['negative_endpoint','0 0\n1 1\n3 -1e-12\n'],['negative_interpolant','0 0\n1 0\n2 0\n3 1\n']]){
   const source=negativeBase+table+'End\n';
   await page.locator('#file').setInputFiles({name:name+'.asw',mimeType:'text/plain',buffer:Buffer.from(source)});
   await expect(page.locator('#editor')).toHaveValue(source);
   await expect(page.locator('#error')).toContainText('body radius must be nonnegative');
   await expect(page.locator('#solve')).toBeDisabled();
   rejections.push({case:name,status:'matching_rejection',error:await page.locator('#error').innerText()});
  }
 }
 const rows=[],display=[];
 for(const c of sources.cases){
  await page.locator('#file').setInputFiles({name:c.name+'_outline.asw',mimeType:'text/plain',buffer:Buffer.from(c.derived_source)});
  await expect(page.locator('#editor')).toHaveValue(c.derived_source);
  const expectedDisplay=wasm.display.find(d=>d.case===c.name).result;
  if(!candidate&&expectedDisplay.status==='rejected'){
   await expect(page.locator('#runtime-status')).toHaveText('Configuration needs attention');
   await expect(page.locator('#error')).toContainText(expectedDisplay.error);
   await expect(page.locator('#solve')).toBeDisabled();await expect(page.locator('#export-json')).toBeDisabled();
   display.push({case:c.name,status:'matching_rejection',error:await page.locator('#error').innerText()});
   await page.screenshot({path:info.outputPath(c.name+'-endpoint-rejection.png'),fullPage:true});
   continue;
  }
  await ready(page);display.push({case:c.name,status:'constructed'});
  await page.locator('#mode').selectOption('rigid');await page.locator('#speed').fill('10');await page.locator('#beta').fill('0');
  for(const id of ['mach-mode','ground-effect'])await page.locator('#'+id).evaluate(el=>{
   for(let p=el.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;
  });
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await page.locator('#ground-effect').selectOption('0');await page.locator('#freeze-influences').uncheck();
  for(const n of [32,128]){
   await page.locator('#panels').fill(String(n));await page.locator('#panels').press('Tab');await ready(page);
   const sample=study.rows.filter(r=>r.specification.case===c.name&&r.specification.panels===n&&r.specification.length===1&&r.specification.surface_offset===1e-6);
   for(const expected of sample){
    const q=expected.specification,r=expected.result;
    expect(sha(await readFile(expected.cache_path))).toBe(expected.cache_sha256);
    await page.locator('#alpha').fill(String(q.alpha));await page.locator('#solve').click();
    await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});await ready(page);
    const event=page.waitForEvent('download');await page.locator('#export-json').click();
    const result=JSON.parse(await readFile(await(await event).path(),'utf8'));
    expect(result.software_provenance.modules).toEqual(modules);expect(result.request.source).toBe(c.derived_source);
    expect(result.request.condition.mach).toBe(0);expect(result.request.condition.ground_effect).toBe(0);
    expect(result.request.panels).toBe(n);expect(result.lifting_panels).toBe(0);expect(result.residual).toBeLessThan(1e-8);
    const differences={};
    for(const [k,v] of Object.entries(r.coefficients)){
     if(v===null)expect(result[k]).toBe(null);else differences[k]=Math.abs(result[k]-v);
    }
    const coefficient=Math.max(...Object.values(differences));expect(coefficient).toBeLessThan(2e-10);
    expect(result.strips.length).toBe(r.profiles.length);
    const profile=Math.max(...result.strips.flatMap((s,i)=>s.force.map((v,j)=>Math.abs(v-r.profiles[i].force[j]))));
    expect(profile).toBeLessThan(2e-9);
    rows.push({specification:q,status:'matching_solution',maximum_coefficient_difference:coefficient,
     maximum_strip_force_difference:profile,result});
   }
  }
 }
 expect(rows).toHaveLength(candidate?16:8);expect(display).toHaveLength(4);expect(errors).toEqual([]);
 await page.screenshot({path:info.outputPath('isae-sa13-desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});await page.locator('#workspace-tab-plots').click();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:info.outputPath('isae-sa13-mobile.png'),fullPage:true});
 const name=candidate?'isae-sa13-endpoint-candidate-browser.json':'isae-sa13-browser.json';
 await writeFile(info.outputPath(name),JSON.stringify({status:'PASS_EXPECTED_OUTCOMES',offline:true,
  candidate_only:!!candidate,candidate_sha256:candidate?sha(candidate):null,
  scope:'Body load exports and display outcomes. Browser pressure-plane UI does not provide these exact measurement stations; pressure replay is covered separately in Pyodide.',
  rows,display,rejections,modules,native_sha256:sha(bytes),wasm_sha256:sha(wasmBytes),sources_sha256:sha(sourceBytes),
  test_sha256:sha(await readFile(import.meta.filename)),web_main_sha256:sha(await readFile('web/main.js'))},null,2)+'\n');
});
