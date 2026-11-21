import {test,expect} from '@playwright/test';

test('unchanged and reverted mesh inputs remain runnable without losing editor drafts',async({page,context})=>{
  await page.addInitScript(()=>{
    const get=HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext=function(type,...args){return type==='webgl2'?null:get.call(this,type,...args);};
  });
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  await context.setOffline(true);
  const panels=page.locator('#panels'),solve=page.locator('#solve');
  const original=await panels.inputValue();
  await panels.fill(original);await panels.press('Tab');
  await expect(solve).toBeEnabled();
  // Restore before blur: browsers need not emit change when value equals the
  // value on focus, although both input events have already fired.
  await panels.fill('12');await expect(solve).toBeDisabled();
  await panels.fill(original);await panels.press('Tab');await expect(solve).toBeEnabled();
  await panels.fill('');await expect(solve).toBeDisabled();
  await panels.fill(original);await panels.press('Tab');await expect(solve).toBeEnabled();
  await page.locator('#tab-editor').click();
  const source=await page.locator('#editor').inputValue();
  await page.locator('#editor').fill(source+'\n! Retain this unapplied draft\n');
  await expect(solve).toBeDisabled();
  await panels.fill(original);await panels.press('Tab');await expect(solve).toBeDisabled();
  await expect(page.locator('#editor')).toHaveValue(source+'\n! Retain this unapplied draft\n');
  await page.locator('#apply').click();await expect(solve).toBeEnabled();
  await panels.fill('4');await panels.press('Tab');await expect(solve).toBeEnabled();
  await expect(page.locator('#panel-count')).toHaveText('6');
});
