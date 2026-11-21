import {test,expect} from '@playwright/test';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';

// Exercise the actual Three.js WebGL path on machines without a physical GPU.
// A driver must execute shaders, not merely return a context object. Mesa's
// software Vulkan driver is an alternative for hosts where SwiftShader crashes.
const mesa=process.env.OPENSWING_WEBGL_DRIVER==='mesa';
test.use({launchOptions:{
  executablePath:process.env.OPENSWING_CHROMIUM_EXECUTABLE,
  args:mesa?['--no-sandbox','--use-gl=angle','--use-angle=vulkan','--use-vulkan=native',
    '--ignore-gpu-blocklist','--enable-features=Vulkan','--disable-gpu-compositing']:
    ['--no-sandbox','--use-gl=angle','--use-angle=swiftshader-webgl','--enable-unsafe-swiftshader'],
}});

async function capture(page,name){
  const bytes=await page.locator('#viewport canvas').screenshot({path:`test-results/webgl-${name}.png`});
  const pixels=await page.evaluate(async encoded=>{
    // Decode the compositor screenshot: reading an unpreserved WebGL drawing
    // buffer between animation frames can otherwise produce a blank image.
    const image=new Image();image.src=`data:image/png;base64,${encoded}`;await image.decode();
    const canvas=document.createElement('canvas');canvas.width=image.width;canvas.height=image.height;
    const context=canvas.getContext('2d');context.drawImage(image,0,0);
    const rgba=context.getImageData(0,0,canvas.width,canvas.height).data;let wing=0;
    for(let i=0;i<rgba.length;i+=4){const [r,g,b]=rgba.subarray(i,i+3);if(r>95&&r>1.4*g&&r>1.4*b)wing++;}
    return {width:canvas.width,height:canvas.height,wing_pixels:wing};
  },bytes.toString('base64'));
  expect(pixels.wing_pixels).toBeGreaterThan(200);
  return {...pixels,sha256:createHash('sha256').update(bytes).digest('hex')};
}

test('WebGL renders an offline computed deformation, camera changes and mobile resize',async({page,context})=>{
  test.setTimeout(360000);await mkdir('test-results',{recursive:true});
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  const canvas=page.locator('#viewport canvas');await expect(canvas).toHaveAttribute('data-renderer','webgl');
  const gpu=await canvas.evaluate(element=>{
    const gl=element.getContext('webgl2'),extension=gl.getExtension('WEBGL_debug_renderer_info');
    return {version:gl.getParameter(gl.VERSION),renderer:extension?gl.getParameter(extension.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER),lost:gl.isContextLost(),error:gl.getError()};
  });
  await writeFile('test-results/webgl-context.json',JSON.stringify(gpu,null,2)+'\n');
  expect(gpu.lost).toBe(false);expect(gpu.version).toContain('WebGL 2.0');expect(gpu.error).toBe(0);
  await page.locator('#example').selectOption('flexible');
  await expect(page.locator('#model-name')).toHaveText('Flexible high aspect ratio wing');
  await page.locator('#mode').selectOption('mounted');
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');
  await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#top-view').click();const jig=await capture(page,'jig');
  await context.setOffline(true);await page.locator('#solve').click();
  await expect(page.locator('#result-state')).toHaveText('Converged · mounted equilibrium',{timeout:180000});
  await expect(page.locator('#shape-label')).toHaveText('DEFORMED · 1×');
  expect(Number(await page.locator('#deflection').textContent())).toBeGreaterThan(1);
  const download=page.waitForEvent('download');await page.locator('#export-json').click();
  const result=JSON.parse(await readFile(await(await download).path(),'utf8'));
  expect(result.converged).toBe(true);expect(result.residual).toBeLessThan(1e-8);
  const scale=Math.max(1,...result.applied_force.map(Math.abs),...result.support_force.map(Math.abs));
  expect(Math.max(...result.force_balance.map(Math.abs))/scale).toBeLessThan(1e-8);
  const deformed=await capture(page,'deformed');
  await page.locator('#top-view').click();const top=await capture(page,'top');
  expect(top.sha256).not.toBe(deformed.sha256);
  await page.locator('#shape').click();await expect(page.locator('#shape-label')).toHaveText('JIG SHAPE');
  await page.locator('#shape').click();await expect(page.locator('#shape-label')).toHaveText('DEFORMED · 1×');
  await page.locator('#fit').click();
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  const mobile=await capture(page,'mobile');expect(mobile.width).toBeLessThan(top.width);
  await expect(canvas).toHaveAttribute('data-renderer','webgl');
  expect(await canvas.evaluate(element=>element.getContext('webgl2').isContextLost())).toBe(false);
  expect(errors).toEqual([]);
  await writeFile('test-results/webgl-values.json',JSON.stringify({gpu,jig,deformed,top,mobile,residual:result.residual,force_balance:result.force_balance,numerical_provenance:result.software_provenance,scope:'Actual packaged WebAssembly solve and Three.js WebGL rendering under a software graphics driver. This is not physical-GPU coverage.'},null,2)+'\n');
});
