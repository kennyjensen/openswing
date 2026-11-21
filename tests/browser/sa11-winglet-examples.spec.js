import {test,expect} from '@playwright/test';

const mesa=process.env.OPENSWING_WEBGL_DRIVER==='mesa';
test.use({launchOptions:{executablePath:process.env.OPENSWING_CHROMIUM_EXECUTABLE,
  args:mesa?['--no-sandbox','--use-gl=angle','--use-angle=vulkan','--use-vulkan=native',
    '--ignore-gpu-blocklist','--enable-features=Vulkan','--disable-gpu-compositing']:
    ['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--disable-webgl']}});

test('SA-11 winglet examples load and render every surface without solving',async({page})=>{
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.addInitScript(()=>{
    window.wingletRequests=[];
    const WorkerClass=window.Worker;
    window.Worker=class extends WorkerClass{
      constructor(...args){super(...args);this.addEventListener('message',event=>{
        if(event.data.result?.beams)window.wingletInspection=event.data.result;
      });}
      postMessage(message,...args){window.wingletRequests.push(message.request);return super.postMessage(message,...args);}
    };
  });
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#panels').fill('8');await page.locator('#panels').press('Tab');
  await expect(page.locator('#solve')).toBeEnabled();
  const renderer=mesa?'webgl':'canvas2d';
  await expect(page.locator('#viewport canvas')).toHaveAttribute('data-renderer',renderer);
  const palettePixels=()=>page.evaluate(async()=>{
    const {beamColor}=await import('/web/plot-colors.js');
    const {surfaceFillColor}=await import('/web/surface-shading.js');
    const c=document.querySelector('#viewport canvas'),rgba=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
    const palette=wingletInspection.beams.map(beam=>surfaceFillColor(beamColor(wingletInspection.beams,beam.index))
      .slice(1).match(/../g).map(channel=>parseInt(channel,16)));
    return palette.map(rgb=>{let count=0;for(let i=0;i<rgba.length;i+=4)if(rgb.every((v,j)=>rgba[i+j]===v))count++;return count;});
  });
  for(const [key,count] of [['isae-sa11-wingtip-up',3],['isae-sa11-wingtip-up-and-down',5]]){
    await page.locator('#example').selectOption(key);
    await expect(page.locator('#beam-count')).toHaveText(String(count));
    await expect(page.locator('#solve')).toBeEnabled();
    await expect(page.locator('#example-note')).toContainText('Joint-station scales corrected');
    await expect(page.locator('#model-name')).toHaveText(count===3?'SA-11 · Upper winglets':'SA-11 · Upper and lower winglets');
    await expect(page.locator('#beam-list .beam-row')).toHaveCount(count);
    const geometry=await page.evaluate(()=>wingletInspection.beams.map(b=>({index:b.index,
      quads:b.streamwise_quads.length,vertices:b.streamwise_quads.flat(2)})));
    expect(geometry).toHaveLength(count);
    expect(geometry.every(b=>b.quads>0&&b.vertices.every(Number.isFinite))).toBeTruthy();
    await page.locator('#viewport').screenshot({path:`test-results/${key}-${renderer}-perspective.png`});
    const first=mesa?null:await palettePixels();
    // A winglet can be hidden by the wing. Orbit to the opposite side and
    // require every surface to contribute visible face pixels across the pair.
    const box=await page.locator('#viewport canvas').boundingBox();
    await page.mouse.move(box.x+box.width/2+60,box.y+box.height/2);
    await page.mouse.down();
    await page.mouse.move(box.x+box.width/2-57,box.y+box.height/2,{steps:12});
    await page.mouse.up();
    await page.locator('#viewport').screenshot({path:`test-results/${key}-${renderer}-orbited.png`});
    if(!mesa){
      const second=await palettePixels();
      expect(first.slice(0,count).every((n,i)=>n+second[i]>3),
        `Visible surface pixels for ${key}: first ${first}, orbited ${second}`).toBeTruthy();
    }
    await page.locator('#front-view').click();
    await page.locator('#viewport').screenshot({path:`test-results/${key}-${renderer}-front.png`});
  }
  await page.setViewportSize({width:390,height:844});
  await page.getByRole('tab',{name:'Plots',exact:true}).click();
  await expect(page.locator('#viewport canvas')).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();
  await page.locator('#viewport').screenshot({path:`test-results/sa11-winglets-${renderer}-mobile.png`});
  await page.setViewportSize({width:1440,height:1000});
  await page.locator('#example').selectOption('isae-sa11-wing-alone');
  await expect(page.locator('#beam-count')).toHaveText('1');
  await expect(page.locator('#example-note')).toContainText('without winglets');
  expect(await page.evaluate(()=>wingletRequests.some(r=>r.action==='solve'))).toBeFalsy();
  expect(errors).toEqual([]);
});
