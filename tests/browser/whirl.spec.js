import {test,expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';
const I=.2,H=-1.8,K=21,D=.8886003431829957,A=.038783936329060977;
const add=(a,b)=>[a[0]+b[0],a[1]+b[1]],mul=(a,b)=>[a[0]*b[0]-a[1]*b[1],a[0]*b[1]+a[1]*b[0]],scale=(a,b)=>a.map(v=>v*b);
const div=(a,b)=>scale(mul(a,[b[0],-b[1]]),1/(b[0]**2+b[1]**2));
function roots(speed){
  const out=[];
  for(const sign of [-1,1]){
    const b=[D,-sign*H],c=[K,-sign*A*speed**2],z=add(mul(b,b),scale(c,-4*I)),r=Math.hypot(...z),sqrt=[Math.sqrt((r+z[0])/2),Math.sign(z[1])*Math.sqrt((r-z[0])/2)];
    for(const direction of [-1,1])out.push(scale(add(scale(b,-1),scale(sqrt,direction)),1/(2*I)));
  }
  return out;
}
function transfer(w,speed){const a=[K-I*w*w,D*w],b=[-A*speed**2,-H*w],den=add(mul(a,a),mul(b,b));return [[div(a,den),div(b,den)],[scale(div(b,den),-1),div(a,den)]];}
async function download(page,id='#export-json'){const event=page.waitForEvent('download');await page.locator(id).click();return JSON.parse(await readFile(await(await event).path(),'utf8'));}
async function done(page,status='Analysis converged'){await expect(page.locator('#runtime-status')).toHaveText(status,{timeout:360000});await expect(page.locator('#error')).toBeHidden();}
async function prepare(page){
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();await page.locator('#example').selectOption('whirl-flutter');await expect(page.locator('#model-name')).toHaveText('Elastic rotor mount - whirl flutter');
  await page.locator('#node-file').setInputFiles({name:'uniform.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({format:'openswing-mesh',version:1,panels:{default:4,beams:{'1':{count:4,spacing:'uniform'}}}}))});await expect(page.locator('#node-table tbody tr')).toHaveCount(5);await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#alpha').fill('0');await page.locator('#speed').fill('10');await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');await page.locator('#density-mode').selectOption('custom');await page.locator('#density').fill('1.225');await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
}
function checkModes(result,speed){
  expect(result.diagnostics.finite_dimension).toBe(4);expect(result.modes).toHaveLength(4);
  for(const mode of result.modes){const best=Math.min(...roots(speed).map(r=>Math.hypot(r[0]-mode.eigenvalue[0],r[1]-mode.eigenvalue[1])));expect(best).toBeLessThan(2e-7);}
}

test('offline elastic rotor modes, gyroscopic phase and refined whirl boundary match independent mechanics',async({page,context})=>{
  test.setTimeout(900000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{const original=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,...args){return type==='webgl2'?null:original.call(this,type,...args);};});
  await prepare(page);
  await page.locator('#mode').selectOption('modes');await page.locator('#modal-count').fill('4');await context.setOffline(true);await page.locator('#solve').click();await done(page);
  const stable=await download(page);checkModes(stable,10);expect(stable.modes.every(m=>m.eigenvalue[0]<0)).toBe(true);expect(stable.base.mass_properties.spin_angular_momentum[0]).toBeCloseTo(H,10);
  await page.locator('#modal-quantity').selectOption('nodes.rotation.1');await expect(page.locator('#modal-plot polyline')).toHaveCount(2);
  await page.locator('#modal-phase').fill('90');await page.locator('#modal-play').click();await expect.poll(()=>page.locator('#modal-phase').inputValue()).not.toBe('90');await page.locator('#modal-play').click();expect(await download(page)).toEqual(stable);
  await page.locator('#stability-settings').evaluate(e=>e.open=true);await page.locator('#stability-values').fill('10, 14');await page.locator('#stability-tolerance').fill('.00001');await page.locator('#stability-build').click();await done(page,'Stability sweep finished');
  const sweep=await download(page,'#stability-json');expect(sweep.tracking_complete).toBe(true);expect(sweep.spectrum_complete).toBe(true);expect(sweep.boundaries).toHaveLength(1);const boundary=sweep.boundaries[0];expect(boundary.status).toBe('resolved');expect(boundary.direction).toBe('destabilizing');
  const wc=(H+Math.sqrt(H*H+4*I*K))/(2*I),vc=Math.sqrt(D*wc/A);expect(Math.abs(boundary.value-vc)).toBeLessThan(2e-4);expect(Math.abs(Math.abs(boundary.eigenvalue[1])-wc)).toBeLessThan(2e-4);
  await page.locator('#stability-point').selectOption('1');await page.locator('#stability-inspect').click();const unstable=await download(page);checkModes(unstable,14);const index=unstable.modes.findIndex(m=>m.eigenvalue[0]>0&&m.eigenvalue[1]>0);expect(index).toBeGreaterThanOrEqual(0);await page.locator('#modal-select').selectOption(String(index));await expect(page.locator('#modal-detail')).toContainText('unstable');
  await page.locator('#stability-settings').screenshot({path:'test-results/whirl-boundary.png'});await page.locator('#viewport').scrollIntoViewIfNeeded();
  const drawing=await page.locator('#viewport canvas').evaluate(canvas=>{
    const pixels=canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data;let geometry=0;
    for(let i=0;i<pixels.length;i+=4)if(pixels[i+1]>130&&pixels[i+2]>100&&pixels[i+3]>200)geometry++;
    return {renderer:canvas.dataset.renderer,geometry,png:canvas.toDataURL()};
  });
  expect(drawing.renderer).toBe('canvas2d');expect(drawing.geometry).toBeGreaterThan(250);await writeFile('test-results/whirl-canvas.png',Buffer.from(drawing.png.split(',')[1],'base64'));
  await page.locator('#viewport').screenshot({path:'test-results/whirl-geometry.png'});await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);await page.locator('#stability-settings').screenshot({path:'test-results/whirl-mobile.png'});expect(errors).toEqual([]);
});

test('offline rotor torque response retains direct and cross-axis amplitude and phase',async({page,context})=>{
  test.setTimeout(480000);const errors=[];page.on('pageerror',e=>errors.push(e.message));await prepare(page);
  await page.locator('#mode').selectOption('frequency');await page.locator('#frequency-inputs').selectOption('controls');await page.locator('#frequency-spacing').selectOption('linear');await page.locator('#frequency-start').fill('0');await page.locator('#frequency-end').fill('20');await page.locator('#frequency-count').fill('5');await context.setOffline(true);await page.locator('#solve').click();await done(page);
  const result=await download(page);
  for(const p of result.samples){const exact=transfer(p.omega,10);for(const [j,name] of ['power.2','power.3'].entries()){const i=result.inputs.findIndex(c=>c.name===name),v=p.responses[i].output.nodes.at(-1).rotation;for(let axis=0;axis<2;axis++){expect(v.real[axis+1]).toBeCloseTo(exact[axis][j][0],7);expect(v.imag[axis+1]).toBeCloseTo(exact[axis][j][1],7);}}}
  await page.locator('#frequency-input').selectOption('1');await page.locator('#frequency-group').selectOption('nodes');await page.locator('#frequency-quantity').selectOption({label:'rotation y [rad]'});await page.locator('#frequency-comparison').evaluate(e=>e.open=true);await page.locator('#frequency-compare-current').click();await page.locator('#frequency-quantity').selectOption({label:'rotation z [rad]'});await page.locator('#frequency-compare-current').click();await expect(page.locator('.frequency-trace')).toHaveCount(2);
  await page.locator('#frequency-comparison').screenshot({path:'test-results/whirl-frequency.png'});expect(await download(page)).toEqual(result);expect(errors).toEqual([]);
});
