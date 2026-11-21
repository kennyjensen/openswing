import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import { mountedProgress, mountedStatus, progressBoundary } from '../web/solve-progress.js';

test('real default Daedalus cold-start events expose initial matrix progress',()=>{
  const receipt=JSON.parse(readFileSync(new URL('./fixtures/default-trim-progress.json',import.meta.url),'utf8'));
  assert.equal(receipt.saved_equilibrium_used,false);
  assert.equal(receipt.solve_completed,false);
  const track=mountedProgress(),messages=[];
  for(const event of receipt.events){
    const data={stage:event.stage,time:event.current,steps:event.total,...track(event.stage,event.current,event.total)};
    const status=mountedStatus(data);
    assert.ok(status);
    if(event.stage==='static_tangent'){
      assert.match(status.message,new RegExp(`${event.current}/${event.total} columns`));
      assert.match(status.detail,/not overall solve completion/);
      assert.doesNotMatch(status.message,/Converged|applied load 100%/);
      messages.push(status.message);
    }
  }
  assert.ok(new Set(messages).size>2,'Initial progress must visibly advance.');
  const last=receipt.events.at(-1);
  assert.match(mountedStatus({stage:'static_tangent',time:last.total,steps:last.total,load:0}).message,/Checking initial constraint independence/);
});

test('repeated assemblies identify their update, including events hidden by throttling', () => {
  const track = mountedProgress();
  function event(stage, time, steps) { return { stage, time, steps, ...track(stage, time, steps) }; }
  assert.match(mountedStatus(event('static_load', 0, 1)).message, /Checking model constraints/);
  event('static_tangent', 0, 229);
  event('static_tangent', 229, 229);
  event('static_load', .25, 1);
  event('static_tangent', 0, 43);
  // The worker may throttle intermediate events, but still tracks them.
  event('static_tangent', 14, 43);
  event('static_tangent', 43, 43);
  const next = mountedStatus(event('static_tangent', 0, 43));
  assert.match(next.message, /applied load 25% · update 2 · assembling 0%/);
  assert.match(next.detail, /not overall completion/);
  assert.match(mountedStatus(event('static_tangent', 43, 43)).message, /solving equations/);
  // Continuation can reduce the target after a failed attempt.
  event('static_load', .125, 1);
  assert.match(mountedStatus(event('static_tangent', 0, 43)).message, /applied load 13% · update 1/);
  event('static_load', 1, 1);
  assert.match(mountedStatus(event('static_tangent', 0, 43)).message, /applied load 100% · update 1/);
});

test('each request starts independently and other analyses keep their own labels', () => {
  const track = mountedProgress();
  assert.deepEqual(track('static_tangent', 0, 43), { load: null, update: 1 });
  assert.equal(mountedStatus({ stage: 'linearizing', time: 10, steps: 300 }), null);
});

test('time startup, matrix rebuilds and retries are distinct from accepted physical time', async () => {
  const {timeProgress,timeStatus}=await import('../web/solve-progress.js');
  const track=timeProgress();
  const event=(stage,time,steps)=>({action:'time',stage,time,steps,...track(stage,time,steps)});
  assert.match(timeStatus({...event('static_load',.25,1),load:.25}).message,/Finding starting equilibrium/);
  event(null,.1,10);event('time_step',.1,.11);
  const assembly=timeStatus(event('time_tangent',0,400));
  assert.match(assembly.message,/t = 0.11000 T.*update 1.*0%/);
  assert.match(assembly.detail,/Accepted through t = 0.10000 T/);
  event('time_tangent',400,400);
  assert.match(timeStatus(event('time_tangent',0,400)).message,/update 2/);
  assert.match(timeStatus(event('time_retry',.1,.005)).message,/Retrying.*0.005000/);
  event('time_step',.1,.105);
  assert.match(timeStatus(event('time_tangent',0,400)).message,/0.10500.*update 1/);
  assert.match(timeStatus(event('time_rank',100,400)).message,/constraint independence/);
  assert.equal(timeStatus({action:'modes',stage:'time_tangent'}),null);
});

test('Bode separates base work, tangent, inertia, samples and output transfer',async()=>{
  const {frequencyStatus}=await import('../web/solve-progress.js');
  const event=(stage,time=0,steps=50)=>({action:'frequency',stage,time,steps});
  assert.match(frequencyStatus(event('base')).message,/finding loaded equilibrium/);
  assert.match(frequencyStatus(event('equilibrium_tangent',35)).message,/retaining derivatives.*35\/50/);
  assert.match(frequencyStatus(event('equilibrium_rank',35)).message,/constraint independence.*35\/50/);
  assert.match(frequencyStatus(event('equilibrium_rank_svd')).message,/full constraint check/);
  assert.match(frequencyStatus(event('equilibrium_reuse',35)).message,/reusing 35 equilibrium derivative columns/);
  assert.match(frequencyStatus({...event('static_tangent'),load:.5,update:2}).message,/Bode.*50%.*update 2/);
  assert.match(frequencyStatus(event('linearizing',35)).message,/building response model.*35\/50/);
  assert.match(frequencyStatus(event('inertia',15)).message,/inertia and damping.*15\/50/);
  assert.match(frequencyStatus(event('frequency',5,21)).message,/5\/21 frequencies completed/);
  assert.match(frequencyStatus(event('reporting',21,21)).message,/preparing plots and output/);
  assert.equal(frequencyStatus({action:'time',stage:'linearizing'}),null);
});

test('mounted final checks take priority over absent, zero and completed load counters', () => {
  for (const load of [undefined, null, 0, 1]) {
    for (const [stage, label] of [
      ['equilibrium_tangent', 'Preparing final equilibrium check'],
      ['equilibrium_rank', 'Checking equilibrium equations'],
    ]) {
      for (const time of [0, 32, 64]) {
        const result = mountedStatus({action:'solve', stage, time, steps:64, load, update:3});
        assert.equal(result.message, `${label} · ${time}/64 columns…`);
        assert.match(result.detail, /corrected state/);
        assert.match(result.detail, /not overall solve completion/);
        assert.doesNotMatch(result.message, /Integrating|applied load|update|%/);
      }
    }
  }
});

test('full equilibrium fallback stays indeterminate at every reported counter', () => {
  const first = mountedStatus({stage:'equilibrium_rank_svd', time:0, steps:64, load:0});
  assert.equal(first.message, 'Completing the full equilibrium check…');
  assert.match(first.detail, /accepted only after this check passes/);
  for (const time of [32, 64]) {
    assert.deepEqual(mountedStatus({stage:'equilibrium_rank_svd', time, steps:64, load:1}), first);
  }
  assert.doesNotMatch(first.message + first.detail, /\d|%|columns|Integrating/);
});

test('both Bode actions retain their explicit final-check labels before generic mounted labels', async () => {
  const {frequencyStatus} = await import('../web/solve-progress.js');
  for (const action of ['frequency', 'extend_frequency']) {
    for (const [stage, expected] of [
      ['equilibrium_tangent', 'Bode · checking equilibrium and retaining derivatives · 32/64 columns…'],
      ['equilibrium_rank', 'Bode · checking constraint independence · 32/64 columns…'],
      ['equilibrium_rank_svd', 'Bode · completing the full constraint check…'],
    ]) {
      const event = {action, stage, time:32, steps:64, load:0};
      const result = frequencyStatus(event);
      assert.equal(result.message, expected);
      assert.notEqual(result.message, mountedStatus(event).message);
      assert.doesNotMatch(result.message, /finding loaded equilibrium/);
    }
    assert.match(frequencyStatus({action, stage:'static_tangent', time:0, steps:64, load:.5, update:2}).message,
      /Bode · finding loaded equilibrium.*applied load 50%.*update 2/);
  }
});

test('time-start equilibrium checks leave accepted time and trial counters unchanged', async () => {
  const {timeProgress,timeStatus} = await import('../web/solve-progress.js');
  for (const action of ['time', 'launch_time', 'resume_time']) {
    const track = timeProgress();
    track(null, .1, 10);
    track('time_step', .1, .11);
    const before = track('time_tangent', 0, 64);
    for (const stage of ['equilibrium_tangent', 'equilibrium_rank', 'equilibrium_rank_svd']) {
      const counters = track(stage, 32, 64);
      assert.deepEqual(counters, before);
      const result = timeStatus({action, stage, time:32, steps:64, load:0, ...counters});
      assert.match(result.message, /^Finding starting equilibrium · /);
      assert.match(result.detail, /^Time integration begins after the initial forces balance/);
      assert.doesNotMatch(result.message, /Integrating|Advancing|t = /);
    }
  }
});

test('final checks do not fabricate mounted load or update progress', () => {
  const track = mountedProgress();
  const before = track('static_load', 0, 1);
  for (const stage of ['equilibrium_tangent', 'equilibrium_rank', 'equilibrium_rank_svd']) {
    for (const current of [0, 32, 64]) assert.deepEqual(track(stage, current, 64), before);
  }
  assert.deepEqual(before, {load:0, update:0});
});

test('main-handler dispatch recognizes mounted final stages without a time-integration fallback', async () => {
  const {frequencyStatus,timeStatus} = await import('../web/solve-progress.js');
  for (const stage of ['equilibrium_tangent', 'equilibrium_rank', 'equilibrium_rank_svd']) {
    const event = {action:'solve', stage, time:0, steps:64, load:0};
    assert.equal(frequencyStatus(event), null);
    assert.equal(timeStatus(event), null);
    const dispatched = frequencyStatus(event) || timeStatus(event) || mountedStatus(event);
    assert.deepEqual(dispatched, mountedStatus(event));
    assert.ok(dispatched);
    assert.doesNotMatch(dispatched.message, /Integrating/);
  }
});

test('warm correction reports iterations and rebuilding columns despite stale load counters', async () => {
  const {frequencyStatus, timeStatus, timeProgress} = await import('../web/solve-progress.js');
  const mounted = mountedProgress(), timing = timeProgress();
  const beforeMounted = mounted('static_load', 0, 1);
  timing(null, .1, 1); timing('time_step', .1, .2);
  const beforeTime = timing('time_tangent', 0, 30);
  for (const load of [null, 0, 1]) {
    const iteration = {stage:'equilibrium_iteration', time:2, steps:1.25e-5, load};
    assert.match(mountedStatus(iteration).message, /iteration 3 · residual 1.25e-5/);
    assert.doesNotMatch(mountedStatus(iteration).message, /applied load|%/);
    for (const current of [0, 15, 30]) {
      const assembly = {stage:'equilibrium_iteration_tangent', time:current, steps:30, load};
      assert.match(mountedStatus(assembly).message, current === 30 ? /solving equations/ : new RegExp(`${current}/30 columns`));
      const final = {stage:'equilibrium_final_tangent', time:current, steps:30, load};
      assert.match(mountedStatus(final).message, /Preparing final equilibrium check/);
      for (const event of [iteration, assembly, final]) {
        assert.deepEqual(mounted(event.stage, event.time, event.steps), beforeMounted);
        assert.deepEqual(timing(event.stage, event.time, event.steps), beforeTime);
        for (const action of ['frequency', 'extend_frequency']) {
          const label = frequencyStatus({...event, action});
          assert.match(label.message, /^Bode · finding loaded equilibrium/);
          assert.doesNotMatch(label.message, /retaining|reusing|applied load|t = /);
        }
        for (const action of ['time', 'launch_time', 'resume_time']) {
          const label = timeStatus({...event, action});
          assert.match(label.message, /^Finding starting equilibrium/);
          assert.doesNotMatch(label.message, /Advancing|t = /);
        }
      }
    }
  }
});

test('worker boundaries retain every assembly start and completion under throttling', () => {
  for (const stage of ['static_tangent','time_tangent','time_rank','equilibrium_tangent','equilibrium_rank',
    'equilibrium_iteration_tangent','equilibrium_final_tangent','linearizing','inertia','frequency']) {
    assert.equal(progressBoundary(stage, 0, 30, stage), true);
    assert.equal(progressBoundary(stage, 30, 30, stage), true);
    assert.equal(progressBoundary(stage, 15, 30, stage), false);
    assert.equal(progressBoundary(stage, 15, 30, 'different_stage'), true);
  }
  for (const stage of ['static_load','time_step','time_retry'])
    assert.equal(progressBoundary(stage, 15, 30, stage), true);
  assert.equal(progressBoundary('equilibrium_iteration', 2, .001, 'equilibrium_iteration'), false);
  assert.equal(progressBoundary('equilibrium_iteration', 2, .001, 'equilibrium_iteration_tangent'), true);
});
