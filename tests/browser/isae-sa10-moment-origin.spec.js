import {test,expect} from '@playwright/test';
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
const execute=promisify(execFile);
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const relativeDifference=(a,b)=>Math.max(...a.map((x,i)=>Math.abs(x-b[i])))/Math.max(1,...b.map(Math.abs));
const ready=async page=>{await expect(page.locator('#solve')).toBeEnabled();await expect(page.locator('#error')).toBeHidden();};

test('current kernel reports SA-10 origin moments offline and preserves reference translation',async({page,context},info)=>{
  test.setTimeout(180000);
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  // Numerical/report regression; keep it usable on hosts without a GPU.
  await page.addInitScript(()=>{
    const original=HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext=function(type,...args){
      return type==='webgl2'?null:original.call(this,type,...args);
    };
  });
  // Exercise the ordinary dev-server route: no kernel request interception.
  const modules={};
  for(const name of(await readdir('openswing')).filter(name=>name.endsWith('.py')))
    modules[name]=sha(await readFile('openswing/'+name));
  const sources=JSON.parse(await readFile('docs/validation/isae-sa10-sources.json'));
  const source=sources.models.find(model=>model.name==='wing_alone').source;
  const shifted=source.replace(/(#\s+Xmom\s+Ymom\s+Zmom[^\n]*\n)[^\n]+/,'$1    0.22    -0.08    0.13');
  expect(shifted).not.toBe(source);
  await page.goto('/');await ready(page);await context.setOffline(true);
  console.log('Current kernel initialized; browser is now offline.');
  const rows=[];
  for(const [name,asw,reference] of [['original',source,[.05,0,0]],['shifted',shifted,[.22,-.08,.13]]]){
    await page.locator('#file').setInputFiles({name:`SA10-${name}.asw`,mimeType:'text/plain',buffer:Buffer.from(asw)});
    await expect(page.locator('#editor')).toHaveValue(asw);await ready(page);
    await page.locator('#mode').selectOption('rigid');
    await page.locator('#panels').fill('16');await page.locator('#panels').press('Tab');await ready(page);
    await page.locator('#speed').fill('55');await page.locator('#alpha').fill('5');await page.locator('#beta').fill('0');
    await page.locator('#mach-mode').evaluate(el=>{for(let p=el.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;});
    await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
    await page.locator('#density-mode').selectOption('custom');await page.locator('#density').fill('1.2256');
    await page.locator('#solve').click();
    await expect(page.locator('#runtime-status')).toHaveText('Analysis converged');await ready(page);
    const download=page.waitForEvent('download');await page.locator('#export-json').click();
    const result=JSON.parse(await readFile(await(await download).path(),'utf8'));
    expect(result.software_provenance.modules).toEqual(modules);
    expect(result.request.source).toBe(asw);
    expect(result.moment_definitions.reference).toEqual(reference);
    expect(result.moment_definitions.axes).toBe('body');
    expect(result.residual).toBeLessThan(1e-8);
    const requestPath=info.outputPath(`${name}-request.json`);
    await writeFile(requestPath,JSON.stringify(result.request));
    const {stdout}=await execute(process.env.OPENSWING_PYTHON||'.venv/bin/python',[
      '-c','import sys; from openswing.bridge import run_json; print(run_json(open(sys.argv[1]).read()))',requestPath,
    ],{env:{...process.env,OPENBLAS_NUM_THREADS:'1',OMP_NUM_THREADS:'1',MKL_NUM_THREADS:'1',PYTHONDONTWRITEBYTECODE:'1'},maxBuffer:10*1024*1024,timeout:60000});
    const native=JSON.parse(stdout);
    console.log(`${name}: browser and native solves completed.`);
    const fields=['CL','CD','CDi','CDp','Cl','Cm','Cn','Cm_origin'];
    const coefficientDifference=Math.max(...fields.map(key=>Math.abs(result[key]-native[key])));
    expect(coefficientDifference).toBeLessThan(1e-9);
    for(const key of ['force','moment','moment_origin','distributed_aero_moment_origin'])
      expect(relativeDifference(result[key],native[key])).toBeLessThan(1e-9);
    const arm=cross(reference,result.force);
    expect(relativeDifference(result.moment_origin,result.moment.map((x,i)=>x+arm[i]))).toBeLessThan(1e-13);
    expect(Math.abs(result.Cm_origin-result.moment_origin[1]/(.5*1.2256*55**2*.199*.178))).toBeLessThan(1e-13);
    await page.locator('#tab-report').click();
    const report=page.locator('#pane-report');
    await expect(report).toContainText(`Cm about file reference: ${result.Cm.toPrecision(8)}`);
    await expect(report).toContainText(`Cm about body origin: ${result.Cm_origin.toPrecision(8)}`);
    await expect(report).toContainText(`File moment reference [input L]: ${reference.map(x=>x.toPrecision(7)).join(', ')}`);
    rows.push({name,coefficient_difference:coefficientDifference,native,result});
  }
  const [original,moved]=rows.map(row=>row.result);
  for(const key of ['force','moment_origin','distributed_aero_moment_origin'])
    expect(relativeDifference(moved[key],original[key])).toBeLessThan(1e-12);
  expect(Math.abs(moved.Cm_origin-original.Cm_origin)).toBeLessThan(1e-12);
  expect(Math.abs(moved.Cm-original.Cm)).toBeGreaterThan(.1);
  const shift=cross([.17,-.08,.13],original.force);
  expect(relativeDifference(moved.moment,original.moment.map((x,i)=>x-shift[i]))).toBeLessThan(1e-12);
  await page.screenshot({path:info.outputPath('origin-moment-desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.locator('#workspace-tab-output').click();
  await expect(page.locator('#pane-report')).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:info.outputPath('origin-moment-mobile.png'),fullPage:true});
  expect(errors).toEqual([]);
  await writeFile(info.outputPath('receipt.json'),JSON.stringify({status:'PASS',offline:true,modules,rows,
    test_sha256:sha(await readFile(import.meta.filename))},null,2)+'\n');
});
