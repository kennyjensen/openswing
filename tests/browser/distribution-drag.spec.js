import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';

async function openEditor(page){
  const mobile=page.locator('#workspace-tab-editor');
  await (await mobile.isVisible()?mobile:page.locator('#tab-editor')).click();
  const panel=page.locator('#properties-panel');
  if(!await panel.evaluate(e=>e.open))await panel.locator('summary').click();
}
async function load(page){
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled({timeout:120000});
  await openEditor(page);
  const source=await readFile('examples/rectangular.asw','utf8');
  await page.locator('#file').setInputFiles({name:'wing.asw',mimeType:'text/plain',buffer:Buffer.from(source)});
  await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#distribution-name').selectOption('chord');
  await expect(page.locator('#distribution-edit')).toBeEnabled();
  return source;
}
async function savedSource(page){
  const event=page.waitForEvent('download');await page.locator('#save').click();
  return readFile(await(await event).path(),'utf8');
}

test('point dragging moves the curve live, applies on release, saves and undoes',async({page})=>{
  const errors=[];page.on('pageerror',error=>errors.push(error.message));const source=await load(page);
  await expect(page.locator('#distribution-graft')).toHaveCount(0);
  await expect(page.locator('#distribution-preview')).toHaveCount(0);await expect(page.locator('#distribution-apply')).toHaveCount(0);
  const value=page.getByRole('spinbutton',{name:'Value 1',exact:true}),before=await value.inputValue();
  await page.getByRole('button',{name:'Edit points',exact:true}).click();
  const point=page.locator('.distribution-point-handle').first();await point.scrollIntoViewIfNeeded();
  const box=await point.boundingBox(),x=box.x+box.width/2,y=box.y+box.height/2;
  const curve=page.locator('.distribution-curve').first(),path=await curve.getAttribute('d');
  await page.mouse.move(x,y);await page.mouse.down();await page.mouse.move(x,y-12,{steps:5});
  await expect(curve).not.toHaveAttribute('d',path);await page.mouse.up();
  await expect(page.locator('#distribution-undo')).toBeEnabled();
  await expect(page.locator('#distribution-edit')).toHaveAttribute('aria-pressed','true');
  await expect(value).not.toHaveValue(before);expect(await savedSource(page)).not.toBe(source);
  await expect(page.locator('#distribution-undo')).toBeEnabled();await page.locator('#distribution-undo').click();
  await expect(value).toHaveValue(before);expect(await savedSource(page)).toBe(source);expect(errors).toEqual([]);
});

test('mobile touch moves the point without scrolling while Edit is on',async({page,context,browserName})=>{
  test.skip(browserName!=='chromium','Native touch injection uses Chromium CDP.');
  await page.setViewportSize({width:390,height:844});await load(page);
  await page.locator('#distribution-edit').click();const plot=page.locator('#distribution-plot');
  await expect(plot).toHaveCSS('touch-action','none');
  const point=page.locator('.distribution-point-handle').first();await point.scrollIntoViewIfNeeded();
  const box=await point.boundingBox(),x=box.x+box.width/2,y=box.y+box.height/2;
  const value=page.getByRole('spinbutton',{name:'Value 1',exact:true}),before=await value.inputValue();
  const scroll=await page.evaluate(()=>scrollY),cdp=await context.newCDPSession(page);
  try{
    await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x,y,id:1}]});
    for(let step=1;step<=4;step++)await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x,y:y-step*3,id:1}]});
    await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
  }finally{await cdp.detach();}
  await expect(value).not.toHaveValue(before);expect(await page.evaluate(()=>scrollY)).toBe(scroll);
  await page.locator('#distribution-edit').click();await expect(plot).not.toHaveCSS('touch-action','none');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
});
