import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
import {existsSync} from 'node:fs';
const file=(text,name='field.gust')=>({name,mimeType:'text/plain',buffer:Buffer.from(text)});
async function open(page){await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();await page.locator('#gust-settings').evaluate(e=>e.open=true);}
async function download(page,button){const event=page.waitForEvent('download');await page.locator(button).click();return readFile(await(await event).path(),'utf8');}

test('public type-5 import, analytic loads, legacy export and saved case restoration work offline',async({page,context})=>{
  test.skip(!existsSync('.reference/legacy-gust/wingloop.gust'),'Run scripts/fetch-legacy-gust.py first.');
  test.setTimeout(180000);const errors=[];page.on('pageerror',e=>errors.push(e.message));await open(page);
  await page.locator('#file').setInputFiles('examples/gust-probe.asw');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#speed').fill('10');await page.locator('#alpha').fill('0');
  await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);
  await page.locator('#density-mode').selectOption('custom');await page.locator('#density').fill('1.2');
  await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await context.setOffline(true);
  await page.locator('#gust-file').setInputFiles('.reference/legacy-gust/wingloop.gust');
  await expect(page.locator('#gust-import-note')).toContainText('ASWING type 5');
  await expect(page.locator('#gust-kind')).toHaveValue('cosine');
  const spec=JSON.parse(await download(page,'#gust-save'));
  expect(spec).toEqual({type:'cosine',amplitude:[0,0,3],origin:[-15,0,0],normal:[-1,0,0],length:15,speed:0});
  await page.locator('#gust-preview-settings').evaluate(e=>e.open=true);
  await page.locator('#gust-xmin').fill('-50');await page.locator('#gust-xmax').fill('-10');
  await page.locator('#gust-preview').click();await expect(page.locator('#gust-preview-note')).toContainText('0.0000 to 3.0000');
  await page.locator('#ground-settings').evaluate(e=>e.open=true);await page.locator('#position-earth-x').fill('-30');
  await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged');
  let result=JSON.parse(await download(page,'#export-json'));
  const scale=.5*1.2*.4*Math.sqrt(109);for(let i=0;i<3;i++)expect(result.force[i]).toBeCloseTo(scale*[10,0,3][i],9);
  expect(result.condition.gust).toEqual(spec);
  const legacy=await download(page,'#gust-save-legacy');
  expect(legacy.split('\n').filter(Boolean).map(s=>Number(s.split('!')[0]))).toEqual([5,-15,0,15,3,0]);
  expect(JSON.parse(await download(page,'#gust-save'))).toEqual(spec);
  // Saving uses the existing gust JSON fields, so old project schemas remain valid.
  await page.locator('#project-settings').evaluate(e=>e.open=true);
  await page.locator('#project-case-name').fill('Imported legacy pulse');await page.locator('#project-add').click();
  await expect(page.locator('#project-status')).toContainText('New case saved');
  await page.locator('#gust-kind').selectOption('none');await page.locator('#position-earth-x').fill('0');
  await page.locator('#project-load').click();await expect(page.locator('#project-status')).toContainText('Loaded Imported legacy pulse');
  await expect(page.locator('#gust-kind')).toHaveValue('cosine');expect(JSON.parse(await download(page,'#gust-save'))).toEqual(spec);
  await expect(page.locator('#position-earth-x')).toHaveValue('-30');
  await expect(page.locator('#export-json')).toBeDisabled();
  await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged');
  result=JSON.parse(await download(page,'#export-json'));expect(result.force[2]).toBeCloseTo(scale*3,9);
  await page.locator('#gust-file').setInputFiles(file(legacy));await expect(page.locator('#gust-import-note')).toContainText('Imported field.gust');
  await expect(page.locator('#export-json')).toBeDisabled();
  await page.locator('#gust-preview').click();await expect(page.locator('#gust-plot svg')).toBeVisible();
  await page.locator('#gust-settings').screenshot({path:'test-results/legacy-gust-panel.png'});
  await page.setViewportSize({width:390,height:844});await page.locator('#gust-open').scrollIntoViewIfNeeded();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.screenshot({path:'test-results/legacy-gust-mobile.png'});expect(errors).toEqual([]);
});

test('unverified legacy parameters and unrepresentable exports preserve the current field',async({page,context})=>{
  await open(page);await context.setOffline(true);
  const good='5\n-3\n0\n3\n1\n0\n';await page.locator('#gust-file').setInputFiles(file(good));
  await expect(page.locator('#gust-import-note')).toContainText('ASWING type 5');
  const original=await download(page,'#gust-save');
  for(const [text,message] of [[good.replace('5\n','8\n'),'type 8'],[good.replace('-3\n0\n','-3\n.2\n'),'nonzero y slope'],[good+'1\n','trailing type-5']]){
    await page.locator('#gust-file').setInputFiles(file(text));await expect(page.locator('#error')).toContainText(message);
    await page.locator('#close-error').click();expect(await download(page,'#gust-save')).toBe(original);
  }
  // A dimensional UI cutoff must not reject a valid field in scaled input units.
  await page.locator('#gust-file').setInputFiles(file('5\n0\n0\n1e-15\n1\n0\n','small-unit.gust'));
  await expect(page.locator('#gust-import-note')).toContainText('small-unit.gust');
  expect(JSON.parse(await download(page,'#gust-save')).length).toBe(1e-15);
  const small=await download(page,'#gust-save-legacy');
  expect(small.split('\n').filter(Boolean).map(s=>Number(s.split('!')[0]))).toEqual([5,0,0,1e-15,1,0]);
  await page.locator('#gust-length').fill('0');await page.locator('#gust-save').click();
  await expect(page.locator('#error')).toContainText('gradient length must be positive');
  await page.locator('#close-error').click();await page.locator('#gust-length').fill('1e-15');
  await page.locator('#gust-kind').selectOption('cosine');await page.locator('#gust-speed').fill('1');
  await page.locator('#gust-save-legacy').click();await expect(page.locator('#error')).toContainText('zero propagation speed');
  await page.locator('#close-error').click();expect(JSON.parse(await download(page,'#gust-save')).speed).toBe(1);
});

test('delayed gust imports cannot overwrite edits or a newer import',async({page})=>{
  await open(page);
  await page.evaluate(()=>{
    const send=Worker.prototype.postMessage;
    Worker.prototype.postMessage=function(data,...rest){
      if(data.request?.action==='gust_import'&&window.holdGust){
        window.holdGust=false;window.gustReply=false;
        const listener=e=>{if(e.data.id===data.id){window.gustReply=true;this.removeEventListener('message',listener);}};
        this.addEventListener('message',listener);window.releaseGust=()=>send.call(this,data,...rest);
      }else send.call(this,data,...rest);
    };
  });
  const a='5\n-3\n0\n3\n1\n0\n',b='5\n-8\n0\n4\n2\n0\n';
  await page.evaluate(()=>{window.holdGust=true;window.releaseGust=null;});
  await page.locator('#gust-file').setInputFiles(file(a));await expect.poll(()=>page.evaluate(()=>!!window.releaseGust)).toBe(true);
  await page.locator('#speed').fill('41');await page.evaluate(()=>window.releaseGust());
  await expect.poll(()=>page.evaluate(()=>window.gustReply)).toBe(true);
  await expect(page.locator('#gust-kind')).toHaveValue('none');await expect(page.locator('#speed')).toHaveValue('41');
  await page.evaluate(()=>{window.holdGust=true;window.releaseGust=null;});
  await page.locator('#gust-file').setInputFiles(file(a));await expect.poll(()=>page.evaluate(()=>!!window.releaseGust)).toBe(true);
  await page.locator('#gust-file').setInputFiles(file(b,'newer.gust'));await expect(page.locator('#gust-import-note')).toContainText('newer.gust');
  await page.evaluate(()=>window.releaseGust());await expect.poll(()=>page.evaluate(()=>window.gustReply)).toBe(true);
  await expect(page.locator('#gust-kind')).toHaveValue('cosine');await expect(page.locator('#gust-origin-x')).toHaveValue('-8');
  await expect(page.locator('#gust-import-note')).toContainText('newer.gust');await expect(page.locator('#error')).toBeHidden();
});
