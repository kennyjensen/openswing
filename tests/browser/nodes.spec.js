import {test,expect} from '@playwright/test';

async function ready(page){
  await expect(page.locator('#runtime-status')).toHaveText('Configuration ready');
  await expect(page.locator('#node-spacing')).toBeEnabled();
  await expect(page.locator('#solve')).toBeEnabled();
}
async function openNodes(page){
  const mobile=page.locator('#workspace-tab-editor');
  await (await mobile.isVisible()?mobile:page.locator('#tab-editor')).click();
  await page.locator('#nodes-panel').evaluate(e=>e.open=true);
}
async function spacing(page,value){await page.locator('#node-spacing').selectOption(value);await ready(page);}
async function edit(page,id,value){await page.locator(id).fill(value);await page.locator(id).press('Tab');await ready(page);}

test('node spacing applies automatically, preserves source, and resets per beam',async({page,context})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#file').setInputFiles('examples/wing-body.asw');
  await expect(page.locator('#filename')).toHaveText('wing-body.asw');await ready(page);
  await openNodes(page);await context.setOffline(true);
  const editor=page.locator('#editor'),original=await editor.inputValue();
  const rows=()=>page.locator('#node-table tbody tr').allTextContents(),defaults=await rows();
  await spacing(page,'cosine');await edit(page,'#node-count','8');const cosine=await rows();
  await spacing(page,'modified-cosine');expect(await rows()).not.toEqual(cosine);
  await expect(page.locator('#node-plot circle')).toHaveCount((await rows()).length);
  await expect(page.locator('#node-status')).toBeHidden();
  await expect(editor).toHaveValue(original);
  await page.locator('#node-beam').selectOption('2');await spacing(page,'uniform');
  await page.locator('#node-beam').selectOption('1');await spacing(page,'default');
  expect(await rows()).toEqual(defaults);
  await page.locator('#node-beam').selectOption('2');await expect(page.locator('#node-spacing')).toHaveValue('uniform');
  await expect(page.locator('#error')).toBeHidden();expect(errors).toEqual([]);
});

test('custom nodes apply on blur and invalid edits leave the displayed mesh intact',async({page,context})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#file').setInputFiles('examples/rectangular.asw');
  await expect(page.locator('#filename')).toHaveText('rectangular.asw');await ready(page);
  await openNodes(page);await context.setOffline(true);
  await spacing(page,'uniform');await edit(page,'#node-count','6');
  const rows=()=>page.locator('#node-table tbody tr').allTextContents(),uniform=await rows();
  await spacing(page,'custom');expect(await rows()).toEqual(uniform);
  await edit(page,'#node-stations','-6, -4.2, -1.1, 0, .8, 3.7, 6');
  await expect(page.locator('#node-table tbody tr')).toHaveCount(9);
  await expect(page.locator('#node-table')).toContainText('ground 1');
  const applied=await rows();
  await page.locator('#node-stations').fill('-6, -4.2, -4.2, 0, .8, 3.7, 6');
  await page.locator('#node-stations').press('Tab');
  await expect(page.locator('#node-status')).toContainText('Mesh not applied:');
  expect(await rows()).toEqual(applied);
  await page.locator('#close-error').click();
  await edit(page,'#node-stations','-6, -4, -1.1, 0, .8, 3.7, 6');
  expect(await rows()).not.toEqual(applied);await expect(page.locator('#node-status')).toBeHidden();
  await page.setViewportSize({width:390,height:844});await openNodes(page);
  await page.locator('#node-plot').scrollIntoViewIfNeeded();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  expect(errors).toEqual([]);
});
