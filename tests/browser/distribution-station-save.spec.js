import {test,expect} from '@playwright/test';

test('Daedalus station buttons update the ASW editor and recover from an invalid deletion',async({page})=>{
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();
  const mobile=page.locator('#workspace-tab-editor');
  await (await mobile.isVisible()?mobile:page.locator('#tab-editor')).click();
  await page.locator('#properties-panel').evaluate(e=>e.open=true);
  await page.locator('#distribution-beam').selectOption('1');
  await expect(page.locator('#distribution-name')).toBeEnabled();
  await page.locator('#distribution-name').selectOption('chord');
  const editor=page.locator('#editor'),rows=page.locator('#distribution-table tbody tr');
  await expect(rows).toHaveCount(8);const original=await editor.inputValue();
  await page.getByRole('button',{name:'Insert after station 2',exact:true}).click();
  await expect(page.locator('#distribution-status')).toHaveText('ASW updated.');
  await expect(rows).toHaveCount(9);await expect(editor).not.toHaveValue(original);
  await page.getByRole('button',{name:'Delete station 4',exact:true}).click();
  await expect(rows).toHaveCount(8);await expect(editor).toHaveValue(original);
  await page.getByRole('button',{name:'Delete station 1',exact:true}).click();
  await expect(page.locator('#distribution-status')).toContainText('Edit not applied:');
  await expect(rows).toHaveCount(8);await expect(editor).toHaveValue(original);
  await page.getByRole('button',{name:'Insert after station 1',exact:true}).click();
  await expect(page.locator('#distribution-status')).toHaveText('ASW updated.');
  await expect(rows).toHaveCount(9);await expect(editor).not.toHaveValue(original);
  await page.locator('#distribution-undo').click();
  await expect(rows).toHaveCount(8);await expect(editor).toHaveValue(original);
});
