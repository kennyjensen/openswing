import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';

test('documented input compatibility notes allow solving and clear on reload',async({page})=>{
  const source=await readFile('examples/rectangular.asw','utf8');
  const jumped=source.replace('t Cdf','t mg\n0 1\n3 1\n3 2\n6 2\nt Cdf');
  await page.goto('/');
  await expect(page.locator('#solve')).toBeEnabled();
  await expect(page.locator('#input-compatibility')).toBeHidden();
  await page.locator('#file').setInputFiles({name:'mass-jump.asw',mimeType:'text/plain',buffer:Buffer.from(jumped)});
  await expect(page.locator('#input-compatibility')).toBeVisible();
  await page.locator('#input-compatibility summary').click();
  await expect(page.locator('#input-compatibility-list')).toHaveText('Beam 1 · mg · input t: 3');
  await expect(page.locator('#error')).toBeHidden();
  await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#solve').click();
  await expect(page.locator('#solve')).toBeEnabled();
  await expect(page.locator('#error')).toBeHidden();
  await expect(page.locator('#residual')).not.toHaveText('—');
  await page.locator('#file').setInputFiles({name:'smooth.asw',mimeType:'text/plain',buffer:Buffer.from(source)});
  await expect(page.locator('#input-compatibility')).toBeHidden();
  await expect(page.locator('#input-compatibility-list li')).toHaveCount(0);
});
