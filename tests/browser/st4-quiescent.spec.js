import {test,expect} from '@playwright/test';
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const sha=b=>createHash('sha256').update(b).digest('hex');
test.use({launchOptions:{executablePath:process.env.OPENSWING_CHROMIUM_EXECUTABLE,args:['--no-sandbox','--use-gl=angle','--use-angle=vulkan','--use-vulkan=native','--ignore-gpu-blocklist','--enable-features=Vulkan','--disable-gpu-compositing']}});
const ready=async (page,timeout=60000)=>{await expect(page.locator('#solve')).toBeEnabled({timeout});await expect(page.locator('#error')).toBeHidden();};
async function download(page,id){const event=page.waitForEvent('download');await page.locator(id).click();return readFile(await(await event).path(),'utf8');}
test('Primary ST4 still-air modes match native results in the offline served build',async({page,context},info)=>{
 test.setTimeout(600000);page.setDefaultTimeout(60000);
 const inputPath=process.env.OPENSWING_ST4_QUIESCENT_INPUTS;
 const bytes=await readFile(inputPath),inputs=JSON.parse(bytes),modules={},errors=[],runs=[];
 for(const name of(await readdir('openswing')).filter(n=>n.endsWith('.py')).sort())modules[name]=sha(await readFile('openswing/'+name));
 expect(modules).toEqual(inputs.modules);page.on('pageerror',e=>{errors.push(e.message);console.log('PAGE ERROR',e.message);});
 page.on('console',message=>{if(message.type()==='error')console.log('CONSOLE ERROR',message.text());});
 page.on('requestfailed',request=>console.log('REQUEST FAILED',request.url(),request.failure()?.errorText));
 await page.goto('/');await ready(page,180000);await context.setOffline(true);
 for(const old of inputs.requests){
  const spec=old.specification,name=`${spec.variant}-${spec.position_in??'bare'}-${spec.icc_endpoint}.asw`;
  expect(sha(await readFile(old.native_cache_path))).toBe(old.native_cache_sha256);
  await page.locator('#file').setInputFiles({name,mimeType:'text/plain',buffer:Buffer.from(old.source)});await ready(page);
  await expect(page.locator('#editor')).toHaveValue(old.source);expect(await download(page,'#save')).toBe(old.source);
  await page.locator('#panels').fill(String(spec.panels));await page.locator('#panels').press('Tab');await ready(page);
  await page.locator('#mode').selectOption('modes');await page.locator('#modal-quiescent').uncheck();await page.locator('#modal-vacuum').uncheck();
  await page.locator('#modal-frame').selectOption('mixed');await page.locator('#modal-quiescent').check();
  await expect(page.locator('#modal-frame')).toBeDisabled();
  await page.locator('#modal-quiescent-density').fill(String(old.settings.quiescent_density));
  await page.locator('#modal-count').fill('12');
  await page.locator('#modal-method').selectOption('dense');await page.locator('#modal-shift-real').fill('-.1');await page.locator('#modal-shift-imag').fill('0');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill(String(old.settings.gravity[2]));
  // A 180 degree bank expresses the report's tip-down mounting in the
  // existing Earth-gravity UI. Source geometry and material values stay fixed.
  await page.locator('#attitude-bank').evaluate(e=>{for(let p=e.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;});
  await page.locator('#attitude-bank').fill('180');await page.locator('#attitude-elevation').fill('0');await page.locator('#attitude-heading').fill('0');
  const start=performance.now();await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});await ready(page);
  const seconds=(performance.now()-start)/1000,result=JSON.parse(await download(page,'#export-json'));
  expect(result.request.source).toBe(old.source);expect(result.request.panels).toBe(spec.panels);expect(result.software_provenance.modules).toEqual(modules);
  expect(result.vacuum).toBe(false);expect(result.fluid.kind).toBe('quiescent');
  expect(result.fluid.density).toBe(old.settings.quiescent_density);expect(result.frame_mode).toBe('fixed');
  expect(result.request.modes.quiescent_density).toBe(old.settings.quiescent_density);
  expect(result.request.condition.speed).toBe(0);expect(result.fluid.mean_velocity_body).toEqual([0,0,0]);
  expect(result.fluid.circulatory).toBe(false);expect(result.base.CL).toBeUndefined();
  expect(result.rom_output_catalog).toEqual([]);expect(result.request.condition.attitude).toEqual([180,0,0]);
  for(let j=0;j<3;j++)expect(Math.abs(result.base.gravity_body[j]-(j===2?old.settings.gravity[2]:0))).toBeLessThan(1e-12);
  expect(result.diagnostics.base_residual).toBeLessThan(1e-8);expect(result.diagnostics.finite_dimension).toBe(old.result.diagnostics.finite_dimension);
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
  await expect(page.locator('#modal-roots svg')).toBeVisible();
  await expect(page.locator('#modal-plot polyline')).toHaveCount(2);
  await expect(page.locator('#modal-select option')).toHaveCount(result.modes.length);
  runs.push({specification:spec,seconds,matches,rendering,result});console.log(name,spec.panels,seconds.toFixed(3)+'s','PASS');
 }
 await page.screenshot({path:info.outputPath('st4-quiescent-desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});await page.locator('#workspace-tab-plots').click();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
 await expect(page.locator('#modal-roots svg')).toBeVisible();
 await expect(page.locator('#modal-plot polyline')).toHaveCount(2);
 await page.screenshot({path:info.outputPath('st4-quiescent-mobile.png'),fullPage:true});expect(errors).toEqual([]);
 await page.locator('#workspace-tab-settings').click();
 await page.locator('#modal-vacuum').check();
 await expect(page.locator('#modal-quiescent')).not.toBeChecked();
 await expect(page.locator('#modal-frame')).toBeEnabled();
 await expect(page.locator('#modal-frame')).toHaveValue('mixed');
 await page.locator('#modal-quiescent').check();
 await expect(page.locator('#modal-frame')).toHaveValue('fixed');

 await writeFile(info.outputPath('st4-quiescent-browser.json'),JSON.stringify({status:'PASS_PRIMARY_ST4_QUIESCENT_FRESH_OFFLINE_BROWSER',offline:true,served_build:true,modules,runtime_inputs_sha256:sha(bytes),test_sha256:sha(await readFile(import.meta.filename)),runs,full_physical_validation:false},null,2)+'\n');
});
