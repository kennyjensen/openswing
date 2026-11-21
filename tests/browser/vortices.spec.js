import {test,expect} from '@playwright/test';

test.use({launchOptions:{executablePath:process.env.OPENSWING_CHROMIUM_EXECUTABLE,
  args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--disable-webgl']}});

test('aircraft toolbar stays compact on desktop and mobile without preview solves',async({page})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
    window.viewerRequests=[];
    const W=window.Worker;
    window.Worker=class extends W {postMessage(message,...args){window.viewerRequests.push(message.request);return super.postMessage(message,...args);}};
  });
  await page.goto('/');
  await expect(page.locator('#solve')).toBeEnabled();
  await expect(page.locator('#example')).toHaveValue('dae');
  await expect(page.locator('#streamwise-chords')).toHaveCount(0);
  await expect(page.locator('#horseshoes')).toHaveCount(0);
  await expect(page.locator('#vortex-note')).toHaveCount(0);
  await page.locator('#top-view').click();
  await expect(page.locator('#viewport canvas')).toBeVisible();
  await page.setViewportSize({width:390,height:844});
  await page.getByRole('tab',{name:'Plots',exact:true}).click();
  for(const id of ['top-view','front-view','fit','grid'])await expect(page.locator('#'+id)).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();
  const actions=await page.evaluate(()=>viewerRequests.map(r=>r.action));
  expect(actions).not.toContain('vortex_preview');expect(actions).not.toContain('solve');
  expect(errors).toEqual([]);
});
