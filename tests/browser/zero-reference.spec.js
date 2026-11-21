import {test,expect} from '@playwright/test';
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const sha=b=>createHash('sha256').update(b).digest('hex');
test.use({launchOptions:{executablePath:process.env.OPENSWING_CHROMIUM_EXECUTABLE,args:['--no-sandbox','--use-gl=angle','--use-angle=vulkan','--use-vulkan=native','--ignore-gpu-blocklist','--enable-features=Vulkan','--disable-gpu-compositing']}});
const ready=async p=>{await expect(p.locator('#solve')).toBeEnabled();await expect(p.locator('#error')).toBeHidden();};
async function downloaded(p,id){const event=p.waitForEvent('download');await p.locator(id).click();return readFile(await(await event).path(),'utf8');}
test('Literal zero-area ST4 inputs solve offline in the served browser',async({page,context},info)=>{
 test.setTimeout(600000);page.setDefaultTimeout(60000);
 const work=process.env.OPENSWING_ZERO_REFERENCE_WORK,root=process.env.OPENSWING_REFERENCE_ROOT;
 const bytes=await readFile(path.join(work,'st4-native.json')),native=JSON.parse(bytes),modules={},errors=[],runs=[];
 for(const name of(await readdir('openswing')).filter(n=>n.endsWith('.py')).sort())modules[name]=sha(await readFile('openswing/'+name));
 expect(modules).toEqual(native.modules);page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/');await ready(page);await context.setOffline(true);
 for(const [name,panels] of [['WING.asw',8],['7a_b11.asw',16],['7b_b11.asw',16]]){
  const entry=native.runs.find(r=>r.specification.panels===panels&&r.paths.some(p=>p.endsWith('/'+name)));
  const raw=await readFile(path.join(root,entry.cache));expect(sha(raw)).toBe(entry.sha256);const old=JSON.parse(raw);
  await page.locator('#file').setInputFiles({name,mimeType:'text/plain',buffer:Buffer.from(old.source)});await ready(page);
  await expect(page.locator('#editor')).toHaveValue(old.source);expect(await downloaded(page,'#save')).toBe(old.source);
  await page.locator('#panels').fill(String(panels));await page.locator('#panels').press('Tab');await ready(page);
  await page.locator('#mode').selectOption('rigid');await page.locator('#solve').click();
  await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});
  await expect(page.locator('#cl')).toHaveText('—');
  await expect(page.locator('#trefftz-note')).toContainText('Sref is zero');
  const aerodynamic_result=JSON.parse(await downloaded(page,'#export-json'));
  expect(aerodynamic_result.CL).toBeNull();expect(aerodynamic_result.coefficient_normalization.available).toBe(false);
  await page.locator('#mode').selectOption('modes');await page.locator('#modal-vacuum').check();
  await page.locator('#modal-frame').selectOption('fixed');await page.locator('#modal-count').fill('12');
  await page.locator('#modal-method').selectOption('dense');await page.locator('#modal-shift-real').fill('-.1');await page.locator('#modal-shift-imag').fill('0');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');
  const start=performance.now();await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});await ready(page);
  const seconds=(performance.now()-start)/1000,result=JSON.parse(await downloaded(page,'#export-json'));
  expect(result.request.source).toBe(old.source);expect(result.request.panels).toBe(panels);expect(result.software_provenance.modules).toEqual(modules);
  expect(result.vacuum).toBe(true);expect(result.base.gravity_body).toEqual([0,0,0]);expect(result.diagnostics.base_residual).toBeLessThan(1e-8);
  expect(result.diagnostics.finite_dimension).toBe(old.result.diagnostics.finite_dimension);
  const a=result.modes.filter(m=>m.eigenvalue[1]>0).sort((x,y)=>x.frequency-y.frequency),b=old.result.modes.filter(m=>m.eigenvalue[1]>0).sort((x,y)=>x.frequency-y.frequency),matches=[];
  expect(a.length).toBe(6);expect(b.length).toBe(6);
  for(let i=0;i<6;i++){
   const delta=Math.abs(a[i].frequency-b[i].frequency);expect(delta).toBeLessThan(2e-6);
   expect(a[i].left_backward_error).toBeLessThan(1e-9);expect(a[i].right_backward_error).toBeLessThan(1e-9);
   let re=0,im=0,aa=0,bb=0;
   for(let j=0;j<a[i].output.nodes.length;j++)for(const field of ['displacement','rotation'])for(let k=0;k<3;k++){
    const x=a[i].output.nodes[j][field],y=b[i].output.nodes[j][field];
    re+=x.real[k]*y.real[k]+x.imag[k]*y.imag[k];im+=x.real[k]*y.imag[k]-x.imag[k]*y.real[k];aa+=x.real[k]**2+x.imag[k]**2;bb+=y.real[k]**2+y.imag[k]**2;
   }
   const mac=(re*re+im*im)/(aa*bb);expect(mac).toBeGreaterThan(1-2e-8);matches.push({frequency_difference_Hz:delta,shape_assurance:mac});
  }
  const canvas=page.locator('canvas[data-renderer="webgl"]');await expect(canvas).toBeVisible();
  const rendering=await canvas.evaluate(e=>{const gl=e.getContext('webgl2');return{lost:gl.isContextLost(),width:gl.drawingBufferWidth,height:gl.drawingBufferHeight,error:gl.getError()};});
  expect(rendering.lost).toBe(false);expect(rendering.width).toBeGreaterThan(0);expect(rendering.error).toBe(0);
  runs.push({name,panels,seconds,aerodynamic_result,matches,rendering,result});console.log(name,panels,seconds.toFixed(3)+'s','PASS');
 }
 await page.screenshot({path:info.outputPath('zero-reference-desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});await page.locator('#workspace-tab-plots').click();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
 await page.screenshot({path:info.outputPath('zero-reference-mobile.png'),fullPage:true});expect(errors).toEqual([]);
 await writeFile(info.outputPath('zero-reference-browser.json'),JSON.stringify({status:'PASS_FRESH_ZERO_REFERENCE_BROWSER',offline:true,served_build:true,modules,native_report_sha256:sha(bytes),test_sha256:sha(await readFile(import.meta.filename)),runs,full_physical_validation:false},null,2)+'\n');
});
