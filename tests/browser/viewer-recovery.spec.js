import {test,expect} from '@playwright/test';
import {writeFile} from 'node:fs/promises';

const mesa=process.env.OPENSWING_WEBGL_DRIVER==='mesa';
test.use({launchOptions:{executablePath:process.env.OPENSWING_CHROMIUM_EXECUTABLE,
  args:mesa?['--no-sandbox','--use-gl=angle','--use-angle=vulkan','--use-vulkan=native',
    '--ignore-gpu-blocklist','--enable-features=Vulkan','--disable-gpu-compositing']:
    ['--no-sandbox','--use-gl=angle','--use-angle=swiftshader-webgl','--enable-unsafe-swiftshader']}});

async function mount(page,{failInitial=false,failPartial=false}={}) {
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(({failInitial,failPartial})=>{
    window.workerAttempts=0;
    window.Worker=class{constructor(){window.workerAttempts++;throw Error('No solver in viewer regression.');}};
    window.observers=[];
    const NativeObserver=window.ResizeObserver;
    window.ResizeObserver=class extends NativeObserver{
      constructor(callback){
        if(failPartial&&!window.injectedSetupFailure){window.injectedSetupFailure=true;throw Error('Injected partial viewer setup failure.');}
        super(callback);window.observers.push(this);this.targets=[];this.disconnected=false;
      }
      observe(target,...args){this.targets.push(target);return super.observe(target,...args);}
      disconnect(){this.disconnected=true;return super.disconnect();}
    };
    if(failInitial){const original=HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext=function(kind,...args){return kind.startsWith('webgl')?null:original.call(this,kind,...args);};}
  },{failInitial,failPartial});
  await page.route('**/viewer-recovery-fixture',route=>route.fulfill({contentType:'text/html',body:`<!doctype html>
    <html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>
      body{margin:0;background:#131d20;color:white;font:14px sans-serif}button{padding:8px}
      [hidden]{display:none!important}.viewport-container{position:relative;width:100%;height:420px}
      #viewport{position:absolute;inset:0}canvas{display:block}#desktop-workbench{max-width:900px;margin:auto}
      @media(max-width:720px){.viewport-container{height:340px}}
    </style></head><body><script type="module">
    import {createViewer} from '/web/viewer.js';
    import {createSoftwareViewer} from '/web/software-viewer.js';
    import {createResponsiveWorkbench} from '/web/responsive-workbench.js';
    const groups={editor:['editor','distributions','nodes'],plots:['loading','modes','structure','time','frequency','flow'],output:['report','derivatives','sensors','feedback','romfiles']};
    const details=Object.values(groups).flat();
    document.body.innerHTML='<nav id="workspace-tabs" hidden>'+['editor','settings','plots','output'].map(n=>'<button id="workspace-tab-'+n+'" data-workspace="'+n+'" aria-controls="workspace-'+n+'">'+n+'</button>').join('')+'</nav>'+ 
      '<main id="desktop-workbench"><div id="model-configuration"></div><div id="analysis-settings"></div><p class="scope-note"></p>'+ 
      '<div class="viewport-header"><button id="top">Top</button><button id="front">Front</button><button id="fit">Fit</button><button id="grid">Grid</button></div>'+ 
      '<div class="viewport-container"><div id="viewport"></div></div>'+ 
      ['time-transport','mode-transport','frequency-transport','solution-provenance'].map(id=>'<div id="'+id+'"></div>').join('')+
      '<div class="results-panel"></div><div class="tabbar">'+details.map(n=>'<button id="tab-'+n+'" data-tab="'+n+'" aria-selected="'+(n==='loading')+'">'+n+'</button>').join('')+'</div>'+ 
      details.map(n=>'<div class="tab-pane" id="pane-'+n+'"></div>').join('')+'<div id="analysis-actions"></div></main>'+ 
      '<div id="mobile-workbench" hidden>'+['editor','settings','plots','output'].map(n=>'<section id="workspace-'+n+'"></section>').join('')+'</div><div id="mobile-action-bar"></div>';
    const freeze=value=>{if(value&&typeof value==='object'){Object.values(value).forEach(freeze);Object.freeze(value);}return value;};
    // Chosen display coordinates, not new aerodynamic/structural solutions.
    window.scenes=[0,.6,1.1].map(z=>freeze({beams:[{index:1,quads:[[[0,0,0],[1,0,0],[.8,2,z],[.1,2,z]]],axis:[[[.25,0,0],[.3,2,z]]]}],
      attachments:[{kind:'engine',segments:[[[.5,.6,z/4],[.5,.6,z/4+.5]]]}],ground:{flag:1,normal_body:[0,1,0],offset:0}}));
    window.original=JSON.stringify(scenes);window.viewer=createViewer(document.querySelector('#viewport'));
    window.workbench=createResponsiveWorkbench();window.current=0;
    window.showScene=(index,refit=true)=>{current=index;const s=scenes[index];viewer.update(s.beams,s.attachments,s.ground,{fit:refit});};
    showScene(0);document.querySelector('#top').onclick=()=>viewer.fit('top');document.querySelector('#front').onclick=()=>viewer.fit('front');
    document.querySelector('#fit').onclick=()=>viewer.fit();document.querySelector('#grid').onclick=()=>viewer.toggleGrid();
    window.referenceImage=async(preset,grid,framing=current)=>{
      const box=document.querySelector('#viewport').getBoundingClientRect(),element=document.createElement('div');
      element.style.cssText='position:fixed;left:-10000px;width:'+box.width+'px;height:'+box.height+'px';document.body.append(element);
      const reference=createSoftwareViewer(element),s=scenes[framing];reference.update(s.beams,s.attachments,s.ground);reference.fit(preset);reference.setGridVisible(grid);
      if(framing!==current){const next=scenes[current];reference.update(next.beams,next.attachments,next.ground,{fit:false});}
      await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
      const png=element.querySelector('canvas').toDataURL();reference.dispose();element.remove();return png;
    };
    window.ready=true;
    </script></body></html>`}));
  await page.goto('/viewer-recovery-fixture');await page.waitForFunction(()=>window.ready);
  return errors;
}
const canvas=page=>page.locator('#viewport canvas');
async function pixels(page){return canvas(page).evaluate(c=>{
  const rgba=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let painted=0;
  for(let i=0;i<rgba.length;i+=4)if(rgba[i]>80||rgba[i+1]>80||rgba[i+2]>80)painted++;
  return {width:c.width,height:c.height,painted,png:c.toDataURL()};
});}
async function sameAsReference(page,preset,grid,framing){
  const expected=await page.evaluate(({preset,grid,framing})=>referenceImage(preset,grid,framing),{preset,grid,framing});
  const actual=await pixels(page);expect(actual.painted).toBeGreaterThan(100);expect(actual.png).toBe(expected);return actual;
}
async function lose(page){return page.evaluate(()=>{
  const c=document.querySelector('#viewport canvas'),gl=c.getContext('webgl2');
  if(!gl||gl.isContextLost())throw Error('A live WebGL2 renderer is required before forcing loss.');
  const ext=gl.getExtension('WEBGL_lose_context');if(!ext)throw Error('WEBGL_lose_context unavailable.');
  const debug=gl.getExtension('WEBGL_debug_renderer_info');
  const renderer=debug?gl.getParameter(debug.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER);
  window.oldCanvas=c;ext.loseContext();return {renderer,forced:true};
});}
async function recovered(page){
  await expect(canvas(page)).toHaveCount(1);await expect(canvas(page)).toHaveAttribute('data-renderer','canvas2d');
  await page.waitForFunction(()=>{const c=document.querySelector('#viewport canvas');return c.width>1&&c.height>1;});
}
async function unchanged(page,errors){
  expect(await page.evaluate(()=>JSON.stringify(scenes))).toBe(await page.evaluate(()=>original));
  expect(await page.evaluate(()=>workerAttempts)).toBe(0);expect(errors).toEqual([]);
}

test('context loss retains scene, attachments, wall, preset and grid; controls and disposal remain live',async({page},info)=>{
  const errors=await mount(page);await expect(canvas(page)).toHaveAttribute('data-renderer','webgl');
  await page.locator('#top').click();await page.locator('#grid').click();await page.evaluate(()=>showScene(1,false));
  const gpu=await lose(page);await recovered(page);await sameAsReference(page,'top',false);
  await page.evaluate(()=>showScene(2,false));await sameAsReference(page,'top',false,1);
  await page.locator('#top').click();
  expect(await page.evaluate(()=>observers.filter(o=>o.targets.some(t=>t.id==='viewport')&&!o.disconnected).length)).toBe(1);
  await page.locator('#grid').click();await sameAsReference(page,'top',true);
  await page.locator('#front').click();const front=await sameAsReference(page,'front',true);
  await page.locator('#fit').click();const perspective=await sameAsReference(page,'perspective',true);expect(front.png).not.toBe(perspective.png);
  const box=await canvas(page).boundingBox();await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();
  await page.mouse.move(box.x+box.width/2+50,box.y+box.height/2+25,{steps:4});await page.mouse.up();
  const orbit=await pixels(page);expect(orbit.png).not.toBe(perspective.png);await canvas(page).dispatchEvent('wheel',{deltaY:-150});
  expect((await pixels(page)).png).not.toBe(orbit.png);
  // Late events from the detached GPU canvas cannot resurrect it.
  await page.evaluate(()=>{oldCanvas.dispatchEvent(new Event('webglcontextrestored'));oldCanvas.dispatchEvent(new Event('webglcontextlost'));document.dispatchEvent(new Event('visibilitychange'));});
  await recovered(page);await page.locator('#fit').click();await sameAsReference(page,'perspective',true);
  await canvas(page).screenshot({path:info.outputPath('recovered-desktop.png')});await unchanged(page,errors);
  await page.evaluate(()=>{viewer.dispose();viewer.dispose();viewer.update(scenes[2].beams);});
  await expect(canvas(page)).toHaveCount(0);
  expect(await page.evaluate(()=>observers.filter(o=>o.targets.some(t=>t.id==='viewport')&&!o.disconnected).length)).toBe(0);
  await writeFile(info.outputPath('receipt.json'),JSON.stringify({status:'PASS',gpu,worker_attempts:0,scope:'Rendering only; synthetic geometry, actual context loss, no solver.'},null,2)+'\n');
});

test('context loss while mobile Plots is hidden replays latest scene and survives desktop return',async({page},info)=>{
  const errors=await mount(page);await page.setViewportSize({width:390,height:844});
  await expect(page.locator('#workspace-plots #viewport')).toBeVisible();await page.locator('#front').click();
  await page.locator('#workspace-tab-editor').click();await expect(page.locator('#viewport')).toBeHidden();
  await page.evaluate(()=>{showScene(1,false);showScene(2,false);});const gpu=await lose(page);
  await expect(canvas(page)).toHaveAttribute('data-renderer','canvas2d');await page.evaluate(()=>showScene(2,false));
  await page.locator('#workspace-tab-plots').click();await recovered(page);await sameAsReference(page,'front',true);
  await canvas(page).screenshot({path:info.outputPath('recovered-mobile.png')});
  await page.setViewportSize({width:1440,height:1000});await expect(page.locator('#desktop-workbench #viewport')).toBeVisible();
  await sameAsReference(page,'front',true);await expect(canvas(page)).toHaveCount(1);await unchanged(page,errors);
  await writeFile(info.outputPath('receipt.json'),JSON.stringify({status:'PASS',gpu,worker_attempts:0,scope:'Actual responsive-workbench reparenting with rendering only.'},null,2)+'\n');
});

test('initial WebGL creation failure uses the same live software viewer API',async({page})=>{
  const errors=await mount(page,{failInitial:true});await recovered(page);await sameAsReference(page,'perspective',true);
  await page.evaluate(()=>showScene(2));await page.locator('#top').click();await page.locator('#grid').click();
  await sameAsReference(page,'top',false);await page.setViewportSize({width:390,height:844});
  await sameAsReference(page,'top',false);await expect(canvas(page)).toHaveCount(1);await unchanged(page,errors);
});

test('streamwise chord selection survives WebGL loss without changing raw geometry',async({page})=>{
  const errors=await mount(page);
  expect(await canvas(page).getAttribute('data-renderer')).toBe('webgl');
  await page.evaluate(()=>{
    const c=Math.SQRT1_2;
    window.projectionBeam={index:1,lifting:true,
      axis:[[[0,0,0],[1,1,0]]],
      quads:[[[0,0,0],[1,1,0],[1+c,1-c,0],[c,-c,0]]],
      streamwise_quads:[[[0,0,0],[1,1,0],[1+Math.SQRT2,1,0],[Math.SQRT2,0,0]]]};
    window.projectionOriginal=JSON.stringify(projectionBeam);
    viewer.update([projectionBeam]);viewer.fit('top');
  });
  const projected=await canvas(page).screenshot();
  await page.evaluate(()=>viewer.setChordProjection(false));
  expect(Buffer.compare(projected,await canvas(page).screenshot())).not.toBe(0);
  await lose(page);await recovered(page);
  const actual=await pixels(page);
  const expected=await page.evaluate(async()=>{
    const {createSoftwareViewer}=await import('/web/software-viewer.js');
    const box=document.querySelector('#viewport').getBoundingClientRect(),element=document.createElement('div');
    element.style.cssText=`position:fixed;left:-10000px;width:${box.width}px;height:${box.height}px`;
    document.body.append(element);
    const reference=createSoftwareViewer(element);
    reference.update([projectionBeam],[],null,{streamwiseChords:false});reference.fit('top');
    await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
    const png=element.querySelector('canvas').toDataURL();reference.dispose();element.remove();return png;
  });
  expect(actual.png).toBe(expected);
  await page.evaluate(()=>viewer.setChordProjection(true));
  expect((await pixels(page)).png).not.toBe(actual.png);
  expect(await page.evaluate(()=>JSON.stringify(projectionBeam))).toBe(await page.evaluate(()=>projectionOriginal));
  expect(await page.evaluate(()=>workerAttempts)).toBe(0);expect(errors).toEqual([]);
});

test('partial WebGL setup failure retires its canvas before software recovery',async({page})=>{
  const errors=await mount(page,{failPartial:true});await recovered(page);
  expect(await page.evaluate(()=>injectedSetupFailure)).toBe(true);await sameAsReference(page,'perspective',true);
  await page.locator('#front').click();await sameAsReference(page,'front',true);await expect(canvas(page)).toHaveCount(1);
  expect(await page.evaluate(()=>observers.filter(o=>o.targets.some(t=>t.id==='viewport')&&!o.disconnected).length)).toBe(1);
  await unchanged(page,errors);
});
