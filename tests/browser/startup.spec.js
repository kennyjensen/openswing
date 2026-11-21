import {test,expect} from '@playwright/test';

async function useSoftwareViewer(page){
  await page.addInitScript(()=>{
    const original=HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext=function(type,...args){
      return type==='webgl2'?null:original.call(this,type,...args);
    };
  });
}

async function darkBackground(page){
  await expect(page.locator('html')).toHaveCSS('background-color','rgb(16, 23, 25)');
}

test('loading remains visible while the entry module waits, and a failed import offers a working retry',async({page},info)=>{
  test.setTimeout(60000);
  await useSoftwareViewer(page);
  let release,requests=0;
  const gate=new Promise(resolve=>{release=resolve;});
  await page.route('**/web/main.js*',async route=>{
    requests++;
    if(requests===1){await gate;await route.abort('failed');}
    else await route.continue();
  });
  try{
    await page.goto('/',{waitUntil:'domcontentloaded'});
    await expect(page.locator('#startup')).toBeVisible();
    await expect(page.locator('#startup-title')).toHaveText('Starting OpenSwing…');
    await expect(page.locator('#startup-detail')).toContainText('Loading the workbench');
    await expect(page.locator('#startup-retry')).toBeHidden();
    await expect.poll(()=>requests).toBe(1);
    await darkBackground(page);
    release();
    await expect(page.locator('#startup-title')).toHaveText('OpenSwing could not start');
    await expect(page.locator('#startup-detail')).toContainText(/module|fetch|load/i);
    await expect(page.locator('#startup-retry')).toBeVisible();
    await expect(page.locator('#startup-retry')).toBeEnabled();
    await darkBackground(page);
    await page.locator('#startup-retry').click();
    await expect(page.locator('#desktop-workbench')).toBeVisible();
    await expect(page.locator('#startup')).toHaveCount(0);
    expect(requests).toBeGreaterThanOrEqual(2);
  }finally{release();}
});

test('normal desktop and mobile workbenches replace the startup screen without a solve',async({page},info)=>{
  test.setTimeout(60000);
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await useSoftwareViewer(page);
  await page.addInitScript(()=>{
    const NativeWorker=window.Worker;window.__startupActions=[];
    window.Worker=class extends NativeWorker{
      postMessage(message,...args){window.__startupActions.push(message.request?.action);return super.postMessage(message,...args);}
    };
  });
  await page.goto('/',{waitUntil:'domcontentloaded'});
  await expect(page.locator('#desktop-workbench')).toBeVisible();
  await expect(page.locator('#startup')).toHaveCount(0);
  await expect(page.locator('#workspace-tabs')).toBeHidden();
  await expect(page.locator('#viewport canvas[data-renderer="canvas2d"]')).toBeVisible();
  await expect(page.locator('#runtime-status')).toHaveText('Configuration ready');
  await expect(page.locator('#solve')).toBeEnabled();
  await darkBackground(page);
  await page.setViewportSize({width:390,height:844});
  await expect(page.locator('#workspace-tabs')).toBeVisible();
  await expect(page.locator('#desktop-workbench')).toBeHidden();
  await expect(page.locator('#workspace-tabs button')).toHaveText(['Editor','Settings','Plots','Output']);
  for(const name of ['editor','settings','plots','output']){
    await page.locator('#workspace-tab-'+name).click();
    await expect(page.locator('#workspace-'+name)).toBeVisible();
    await expect(page.locator('#workspace-tab-'+name)).toHaveAttribute('aria-selected','true');
  }
  await page.locator('#workspace-tab-plots').click();
  await expect(page.locator('#viewport canvas[data-renderer="canvas2d"]')).toBeVisible();
  await expect(page.locator('#startup')).toHaveCount(0);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  expect(await page.evaluate(()=>window.__startupActions.filter(action=>!['inspect','distribution'].includes(action)))).toEqual([]);
  expect(errors).toEqual([]);
});


test('initialization failure after replacing app content restores the startup error screen',async({page})=>{
  test.setTimeout(30000);
  await page.route('**/web/main.js*',route=>route.fulfill({
    contentType:'text/javascript',
    body:"document.getElementById('app').innerHTML='<p id=partial-app>Partial interface</p>'; throw new Error('startup probe');",
  }));
  await page.goto('/',{waitUntil:'domcontentloaded'});
  await expect(page.locator('#startup')).toBeVisible();
  await expect(page.locator('#startup-title')).toHaveText('OpenSwing could not start');
  await expect(page.locator('#startup-detail')).toContainText('startup probe');
  await expect(page.locator('#startup-retry')).toBeVisible();
  await expect(page.locator('#startup-retry')).toBeEnabled();
  await expect(page.locator('#partial-app')).toHaveCount(0);
  await darkBackground(page);
});
