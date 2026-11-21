import {test,expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';
import {solutionChecksum,sealSolution} from '../../web/solution-data.js';
async function download(page,id,json=false){const event=page.waitForEvent('download');await page.locator(id).click();const text=await readFile(await(await event).path(),'utf8');return json?JSON.parse(text):text;}
const parse=text=>{const rows=text.trimEnd().split('\n').map(line=>[...line.matchAll(/"((?:[^"]|"")*)"(?:,|$)/g)].map(m=>m[1].replaceAll('""','"')));return rows.slice(1).map(row=>Object.fromEntries(rows[0].map((h,i)=>[h,row[i]])));};
const profile={beam_fields:[{beam:1,displacement:[[0,0,0,0],[2,0,.02,0]]}]};
const omega=Math.sqrt(243.75);
// The independent [2/3] Pade stability function of three-stage Radau IIA.
const cmul=(a,b)=>[a[0]*b[0]-a[1]*b[1],a[0]*b[1]+a[1]*b[0]];
function advance(amplitude,dt){
  const z=[-2.5*dt,omega*dt],z2=cmul(z,z),z3=cmul(z2,z);
  const numerator=[1+.4*z[0]+.05*z2[0],.4*z[1]+.05*z2[1]],denominator=[1-.6*z[0]+.15*z2[0]-z3[0]/60,-.6*z[1]+.15*z2[1]-z3[1]/60];
  const norm=denominator[0]**2+denominator[1]**2,quotient=cmul(numerator,[denominator[0],-denominator[1]]).map(v=>v/norm);
  return cmul(amplitude,quotient);
}
const exact=t=>{const e=Math.exp(-2.5*t),q=.02*e*(Math.cos(omega*t)+2.5/omega*Math.sin(omega*t)),v=-.02*250/omega*e*Math.sin(omega*t);return {q,v,strain:q/2,force:500*q+10*v};};

test('sampled section envelopes match damped spring mechanics, preserve histories and reopen without analysis',async({page,context})=>{
  const replay=process.env.OPENSWING_HISTORY_REPLAY?JSON.parse(await readFile(process.env.OPENSWING_HISTORY_REPLAY,'utf8')):null;
  test.setTimeout(1500000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await expect(page.locator('#solve')).toBeEnabled();await page.locator('#example').selectOption('instrumented-oscillator');await expect(page.locator('#model-name')).toHaveText('Instrumented spring-mass demonstrator');
  await page.locator('#panels').fill('4');await page.locator('#panels').press('Tab');await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#tab-editor').click();const source=(await page.locator('#editor').inputValue()).replace('t y EA tdeps','t y EA tdeps Cshell Nshell Atshell').replace('0 0 1000 .02','0 0 1000 .02 .1 .1 .001').replace('2 2 1000 .02','2 2 1000 .02 .1 .1 .001');
  await page.locator('#editor').fill(source);await page.locator('#apply').click();await expect(page.locator('#solve')).toBeEnabled();
  await page.locator('#mode').selectOption('mounted');await page.locator('#speed').fill('10');await page.locator('#alpha').fill('0');await page.locator('#atmosphere-settings').evaluate(e=>e.open=true);await page.locator('#gravity-mode').selectOption('custom');await page.locator('#gravity-magnitude').fill('0');await page.locator('#mach-mode').selectOption('fixed');await page.locator('#pg-mach').fill('0');
  await context.setOffline(true);await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Analysis converged',{timeout:180000});
  if(replay){
    expect(replay.format).toBe('openswing-distribution-history-numerical-fixture');expect(replay.histories).toHaveLength(2);
    const fresh=await download(page,'#export-json',true);
    for(const h of replay.histories){expect(h.request.source).toBe(source);expect(h.software_provenance).toEqual(fresh.software_provenance);expect(h.converged).toBe(true);}
  }
  await page.locator('#equilibrium-settings').evaluate(e=>e.open=true);await page.locator('#equilibrium-use').click();
  await page.locator('#mode').selectOption('time');await page.locator('#time-initial-settings').evaluate(e=>e.open=true);await page.locator('#time-initial-file').setInputFiles({name:'initial.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(profile))});
  await page.locator('#time-order').selectOption('5');await page.locator('#time-duration').fill('.4');
  const cases=[];let result;
  for(const dt of [.04,.02]){
    if(replay){result=replay.histories[cases.length];}
    else if(!cases.length){
      await page.locator('#time-step').fill(String(dt));await page.locator('#solve').click();await expect(page.locator('#runtime-status')).toHaveText('Time integration converged',{timeout:600000});
    }else{
      // Refine from the exact same owned initial checkpoint, without repeating
      // physical-state construction or perturbing its prescribed coordinates.
      await page.locator('#time-scrub').fill('0');await page.locator('#time-checkpoint-settings').evaluate(e=>e.open=true);await page.locator('#time-checkpoint-use').click();await page.locator('#time-continue-duration').fill('.4');await page.locator('#time-continue-step').fill(String(dt));await page.locator('#time-continue-order').selectOption('5');await page.locator('#time-continue').click();await expect(page.locator('#runtime-status')).toHaveText('Time continuation converged',{timeout:600000});
    }
    if(!replay)result=await download(page,'#export-json',true);const samples=result.snapshots;
    let displacementError=0,strainError=0,forceError=0,discreteDisplacementError=0,discreteStrainError=0,discreteForceError=0,expectedDisplacementError=0;
    let amplitude=[.02,-.02*2.5/omega],previousTime=0;
    for(const s of samples){
      amplitude=advance(amplitude,s.time-previousTime);previousTime=s.time;
      const discreteQ=amplitude[0],discreteV=cmul(amplitude,[-2.5,omega])[0],e=exact(s.time);
      expectedDisplacementError=Math.max(expectedDisplacementError,Math.abs(discreteQ-e.q));
      displacementError=Math.max(displacementError,Math.abs(s.nodes.at(-1).position[1]-2-e.q));
      discreteDisplacementError=Math.max(discreteDisplacementError,Math.abs(s.nodes.at(-1).position[1]-2-discreteQ));
      for(const row of s.elements){
        strainError=Math.max(strainError,Math.abs(row.shell.axial_strain-e.strain));forceError=Math.max(forceError,Math.abs(row.force_local[1]-e.force));
        discreteStrainError=Math.max(discreteStrainError,Math.abs(row.shell.axial_strain-discreteQ/2));discreteForceError=Math.max(discreteForceError,Math.abs(row.force_local[1]-(500*discreteQ+10*discreteV)));
      }
    }
    cases.push({dt,snapshots:samples.length,maximum_displacement_error:displacementError,maximum_strain_error:strainError,maximum_force_error:forceError,expected_displacement_error:expectedDisplacementError,maximum_discrete_displacement_error:discreteDisplacementError,maximum_discrete_strain_error:discreteStrainError,maximum_discrete_force_error:discreteForceError,sampled_expected_strain_min:Math.min(...samples.map(s=>exact(s.time).strain)),sampled_expected_strain_max:Math.max(...samples.map(s=>exact(s.time).strain))});
    await writeFile('test-results/distribution-history-computed.json',JSON.stringify({result,cases})+'\n');
    expect(discreteDisplacementError).toBeLessThan(1e-9);expect(discreteStrainError).toBeLessThan(1e-9);expect(discreteForceError).toBeLessThan(1e-6);
    expect(Math.abs(displacementError-expectedDisplacementError)).toBeLessThan(1e-9);
  }
  expect(cases[1].maximum_displacement_error).toBeLessThan(cases[0].maximum_displacement_error/20);
  await writeFile('test-results/distribution-history-oscillator.json',JSON.stringify({model:'m=2, k=500, c=10, L=2, q0=.02, v0=0',method:result.method,cases},null,2)+'\n');
  if(replay){
    // Replay the actual numerical history through the public archive importer.
    // All physical reference checks above still run on every retained sample.
    await page.locator('#time-step').fill('.04');await page.locator('#project-settings').evaluate(e=>e.open=true);
    const project=await download(page,'#project-export-current',true);
    const solution=await sealSolution({id:'numerical-fixture',name:'Verified numerical history',created_at:new Date().toISOString(),kind:'time',configuration:project.cases[0].configuration,data:result,auxiliary:{},view:{'time-scrub':'0',active_tab:'tab-structure'},provenance:result.software_provenance});
    project.solutions=[solution];project.selected_solution=solution.id;
    await page.locator('#project-file').setInputFiles({name:'numerical-history.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(project))});await expect(page.locator('#project-status')).toContainText('Project opened. Load a case to restore its inputs.');
    await page.locator('#project-load-solution').click();await expect(page.locator('#project-status')).toContainText('Displaying saved results without recomputation.');
    await page.locator('#project-delete-solution').click();await expect(page.locator('#project-status')).toContainText('Solution removed.');
  }
  const original=JSON.stringify(result);await page.locator('#tab-loading').click();if(!(await page.locator('#plot-quantity').inputValue()).startsWith('structure:'))await page.locator('#plot-quantity').selectOption('structure:shell.axial_strain_bound');await page.locator('#plot-quantity').selectOption('structure:shell.axial_strain');await page.locator('#plot-scope').selectOption('overlay');
  await expect(page.locator('#plot .distribution-trace')).toHaveCount(result.snapshots.length);await expect(page.locator('#plot .distribution-trace.selected')).toHaveAttribute('data-snapshot','0');
  await page.locator('#plot .distribution-trace[data-snapshot="3"]').focus();await page.keyboard.press('Enter');await expect(page.locator('#time-scrub')).toHaveValue('3');await expect(page.locator('#plot .selected')).toHaveAttribute('data-snapshot','3');
  await page.locator('#plot-scope').selectOption('envelope');await expect(page.locator('#plot-history-note')).toContainText('not bounds between time steps');
  const envelopeText=await download(page,'#plot-envelope-csv'),envelope=parse(envelopeText);
  expect(envelope).toHaveLength(result.snapshots[0].elements.length);
  for(let j=0;j<envelope.length;j++){
    const values=result.snapshots.map(s=>s.elements[j].shell.axial_strain*1e6),min=Math.min(...values),max=Math.max(...values);
    expect(Number(envelope[j].min_value)).toBe(min);expect(Number(envelope[j].max_value)).toBe(max);expect(Number(envelope[j]['min_snapshot_index (0-based)'])).toBe(values.indexOf(min));expect(envelope[j].unit).toBe('µε');
    expect(Number(envelope[j].min_value)/1e6).toBeCloseTo(cases[1].sampled_expected_strain_min,7);
  }
  const minIndex=Number(envelope[0]['min_snapshot_index (0-based)']);await page.locator('#plot circle.distribution-min').first().click();await expect(page.locator('#time-scrub')).toHaveValue(String(minIndex));await expect(page.locator('#time-current')).toContainText(result.snapshots[minIndex].time.toPrecision(5));
  const table=parse(await download(page,'#plot-history-csv'));expect(table).toHaveLength(result.snapshots.reduce((n,s)=>n+s.elements.length,0));
  for(const row of table){const s=result.snapshots[Number(row['snapshot_index (0-based)'])],r=s.elements[Number(row['beam_station_index (0-based)'])];expect(Number(row.shell_axial_strain)).toBe(r.shell.axial_strain);expect(Number(row['Fs [F]'])).toBe(r.force_local[1]);expect(row.forcing_side).toBe(s.forcing_side);}
  await page.locator('#plot-quantity').selectOption('structure:shell.shear_stress');await page.locator('#structure-stress-unit').selectOption('MPa');
  const stressEnvelope=parse(await download(page,'#plot-envelope-csv'));
  for(let j=0;j<stressEnvelope.length;j++){
    const raw=result.snapshots.map(s=>s.elements[j].shell.shear_stress);
    expect(Math.max(...raw.map(Math.abs))).toBeLessThan(1e-8); // Numerical residual in this axial-only SI model.
    expect(stressEnvelope[j].unit).toBe('MPa');expect(Number(stressEnvelope[j].min_value)).toBe(Math.min(...raw)/1e6);expect(Number(stressEnvelope[j].max_value)).toBe(Math.max(...raw)/1e6);
  }
  await page.locator('#plot-quantity').selectOption('structure:shell.axial_strain');expect(JSON.stringify(await download(page,'#export-json',true))).toBe(original);
  await page.locator('#pane-loading').screenshot({path:'test-results/distribution-history-desktop.png'});
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();await page.locator('#pane-loading').screenshot({path:'test-results/distribution-history-mobile.png'});
  await page.locator('#project-settings').evaluate(e=>e.open=true);await page.locator('#project-solution-name').fill('Sampled spring envelope');await page.locator('#project-save-solution').click();await expect(page.locator('#project-status')).toContainText('Computed solution saved.');
  const project=await download(page,'#project-export',true);
  await page.evaluate(()=>{window.historyRequests=[];const send=Worker.prototype.postMessage;Worker.prototype.postMessage=function(packet,...args){window.historyRequests.push(packet.request?.action);return send.call(this,packet,...args);};});
  await page.locator('#plot-scope').selectOption('current');await page.locator('#project-load-solution').click();await expect(page.locator('#project-status')).toContainText('Displaying saved results without recomputation.');await expect(page.locator('#plot-scope')).toHaveValue('envelope');expect(await download(page,'#plot-envelope-csv')).toBe(envelopeText);expect(JSON.stringify(await download(page,'#export-json',true))).toBe(original);
  // Missing material quantities stay gaps. A changed grid is explicitly rejected;
  // the complete raw history remains available for inspection/export.
  const modified=structuredClone(project),solution=modified.solutions[0];solution.data.snapshots[1].elements[0].shell.axial_strain=null;solution.checksum=await solutionChecksum(solution);
  await page.locator('#project-file').setInputFiles({name:'missing.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(modified))});await expect(page.locator('#project-status')).toContainText('Project opened. Load a case to restore its inputs.');await page.locator('#project-load-solution').click();await expect(page.locator('#project-status')).toContainText('Displaying saved results without recomputation.');await expect(page.locator('#plot-history-note')).toContainText('1 unavailable values');expect(Number(parse(await download(page,'#plot-envelope-csv'))[0].available_snapshots)).toBe(result.snapshots.length-1);
  solution.data.snapshots[1].elements[0].t0+=.01;solution.checksum=await solutionChecksum(solution);await page.locator('#project-file').setInputFiles({name:'changed-grid.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(modified))});await expect(page.locator('#project-status')).toContainText('Project opened. Load a case to restore its inputs.');await page.locator('#project-load-solution').click();await expect(page.locator('#project-status')).toContainText('Displaying saved results without recomputation.');await expect(page.locator('#plot')).toContainText('different material station grid');await expect(page.locator('#plot-envelope-csv')).toBeDisabled();await expect(page.locator('#plot-history-csv')).toBeEnabled();
  expect((await page.evaluate(()=>window.historyRequests)).filter(a=>!['inspect','distribution','discard_frequency'].includes(a))).toEqual([]);expect(errors).toEqual([]);
  await writeFile('test-results/distribution-history-oscillator.json',JSON.stringify({model:'m=2, k=500, c=10, L=2, q0=.02, v0=0',method:result.method,cases},null,2)+'\n');
});
