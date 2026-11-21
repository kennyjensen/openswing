import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {acceptedTimeSteps,timePhase,timePlotSegments} from '../web/time-timeline.js';

test('actual input-change snapshots count physical steps and keep separate plot branches',async()=>{
  const result=JSON.parse(await readFile(new URL('./fixtures/history-event-timeline.json',import.meta.url),'utf8'));
  const snapshots=result.snapshots;
  assert.equal(acceptedTimeSteps(snapshots),2);
  assert.deepEqual(snapshots.map(timePhase),['Saved state before next inputs','After input change','Before input change','After input change','Computed state']);
  const force=snapshots.map(s=>s.operating_values['power.1']);
  const segments=timePlotSegments(snapshots,force,[.06,1]);
  assert.deepEqual(segments.map(s=>s.map(p=>p[0])),[[.04],[.04,.06],[.06,.08]]);
  assert.equal(segments[1][1][1],force[2]);
  assert.equal(segments[2][0][1],force[3]);
  assert.ok(Math.abs(segments[1][1][1]-segments[2][0][1])>.99);
});

test('ordinary breaks and missing quantities leave visible gaps',()=>{
  const snapshots=[{time:0,step:0},{time:1,step:1,forcing_side:'left'},
    {time:2,step:1,forcing_side:'right'},{time:3,step:1},{time:4,step:1}];
  assert.deepEqual(timePlotSegments(snapshots,[0,1,2,NaN,4],[1]),[[[0,0],[1,1]],[[2,2]],[[4,4]]]);
  assert.equal(timePhase(snapshots[0]),'Initial state');
  assert.equal(acceptedTimeSteps(snapshots),4);
});
