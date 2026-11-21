import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
async function download(page,id){const event=page.waitForEvent('download');await page.locator(id).click();return JSON.parse(await readFile(await(await event).path(),'utf8'));}

test('offline mixed motion follows net-load and acceleration tables through cutoff and restart',async({page,context})=>{
 test.setTimeout(300000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();await page.locator('#example').selectOption('guided-body');await expect(page.locator('#model-name')).toHaveText('Guided rigid-body demonstrator');
 await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled();
 await page.locator('#mode').selectOption('time');await page.locator('#speed').fill('10');await page.locator('#alpha').fill('0');
 await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
 await page.locator('#time-frame').selectOption('mixed');await expect(page.locator('#time-load-settings')).toBeVisible();await page.getByRole('spinbutton',{name:'Net Fx target',exact:true}).fill('1');
 await page.locator('#time-duration').fill('.08');await page.locator('#time-step').fill('.02');await page.locator('#forcing-settings').evaluate(e=>e.open=true);await page.locator('#time-forcing').fill('time +Fx Ay\n0 1 1\n.04 1 1');
 await context.setOffline(true);await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Time integration converged',{timeout:180000});
 const result=await download(page,'#export-json');expect(result.frame_mode).toBe('mixed');expect(result.frame_load_targets).toEqual({'force.x':1});expect(result.snapshots).toHaveLength(5);
 for(const s of result.snapshots){const t=s.time,tau=Math.min(t,.04);expect(s.frame.velocity_origin_body[0]).toBeCloseTo(-10-2*tau,7);expect(s.frame.velocity_origin_body[1]).toBeCloseTo(tau,7);expect(s.frame.acceleration_reference_body[0]).toBeCloseTo(t<=.04?-2:0,7);expect(s.frame.acceleration_reference_body[1]).toBeCloseTo(t<=.04?1:0,7);expect(s.operating_constraints[0].target).toBe(t<=.04?2:0);}
 expect(result.forcing.breaks).toEqual([.04]);expect(result.snapshots[2].forcing_side).toBe('left');expect(result.snapshots[3].order).toBe(1);
 await page.locator('#time-quantity').selectOption('applied_force.0');await expect(page.locator('#time-unit')).toContainText('input F');await expect(page.locator('#time-plot svg')).toBeVisible();
 const event=page.waitForEvent('download');await page.locator('#time-csv').click();const csv=await readFile(await(await event).path(),'utf8');expect(csv).toContain('Net body force x [input F]');expect(csv).toContain('Support moment z about reference [input F L]');
 for(const s of result.snapshots)expect(s.support_force[0]).toBeCloseTo(-s.applied_force[0],7);
 await page.locator('#time-scrub').fill('2');await page.locator('#time-checkpoint-settings').evaluate(e=>e.open=true);const saved=await download(page,'#time-checkpoint-save');expect(saved.older).toBeNull();expect(saved.options.operating_targets).toEqual({'force.x':2});
 await page.locator('#time-checkpoint-use').click();await page.locator('#time-continue-duration').fill('.04');await page.locator('#time-continue').click();await expect(page.locator('#runtime-status')).toHaveText('Time continuation converged',{timeout:180000});
 const appended=await download(page,'#export-json');expect(appended.history_breaks).toEqual([.04]);expect(appended.snapshots).toHaveLength(5);expect(appended.snapshots[2].restart).toEqual(result.snapshots[2].restart);
 await page.locator('#time-checkpoint-file').setInputFiles({name:'mixed.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(saved))});await page.locator('#time-continue-duration').fill('.04');await page.locator('#time-continue').click();await expect(page.locator('#runtime-status')).toHaveText('Time continuation converged',{timeout:180000});
 const resumed=await download(page,'#export-json');expect(resumed.snapshots[1].order).toBe(1);expect(resumed.frame_mode).toBe('mixed');for(let i=0;i<3;i++)expect(resumed.snapshots[i].frame.velocity_origin_body[0]).toBeCloseTo(result.snapshots[i+2].frame.velocity_origin_body[0],8);
 await page.locator('#time-settings').screenshot({path:'test-results/time-constraints.png'});await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();await page.locator('#time-settings').screenshot({path:'test-results/time-constraints-mobile.png'});
 // Incompatible acceleration forcing and inactive force targets fail explicitly.
 await page.locator('#time-forcing').fill('time Ax\n0 0\n.04 0');await page.locator('#solve').click();await expect(page.locator('#error p')).toContainText('conflicts');await expect(page.locator('#export-json')).toBeDisabled();
 await page.locator('#time-forcing').fill('time My\n0 0\n.04 0');await page.locator('#solve').click();await expect(page.locator('#error p')).toContainText('active frame load');
 expect(errors).toEqual([]);
});
