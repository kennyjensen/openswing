import test from 'node:test';
import assert from 'node:assert/strict';
import {MAX_OPERATING_POINTS, parseOperatingPointAngles, operatingPointRows,
  operatingPointSegments, operatingPointsCSV, operatingPointsJSON, operatingPointStart} from '../web/operating-points.js';

const successful = (index, alpha, values = {}, actual = alpha) => ({
  index, name:`Point ${index}`, condition:{alpha, speed:30},
  actual_condition:actual == null ? null : {alpha:actual, speed:30},
  operating_constraints:[], converged:true,
  result:{CL:.1 * index, CD:.01 * index, CDi:.002 * index, Cm:index === 0 ? 0 : -.01 * index, residual:1e-12, ...values}, error:null,
});
const failed = (index, alpha) => ({index, name:'Failed, "point"', condition:{alpha, speed:30},
  operating_constraints:[{variable:'alpha', target:0}], converged:false, result:null,
  error:{type:'ConvergenceError', message:'No root, after 20 iterations\nResidual too large.', details:{residual:.2}}});

// Parse CSV independently, including embedded commas, escaped quotes and newlines.
function csvRows(text) {
  const rows = []; let row = [], cell = '', quoted = false;
  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    if (char === '"') {
      if (quoted && text[i + 1] === '"') { cell += '"'; i++; } else quoted = !quoted;
    } else if (!quoted && char === ',') { row.push(cell); cell = ''; }
    else if (!quoted && char === '\r' && text[i + 1] === '\n') { row.push(cell); rows.push(row); row = []; cell = ''; i++; }
    else cell += char;
  }
  assert.equal(quoted, false); assert.equal(cell, ''); assert.deepEqual(row, []);
  return rows;
}

test('angle list preserves negatives, scientific notation, repeats and nonmonotone input', () => {
  assert.deepEqual(parseOperatingPointAngles(' 4, -2  +.5\n4\t1e-2, 0. '), [4, -2, .5, 4, .01, 0]);
  assert.equal(parseOperatingPointAngles(Array(MAX_OPERATING_POINTS).fill('1').join(' ')).length, MAX_OPERATING_POINTS);
});

test('angle list rejects empty, missing, nonnumeric, nonfinite and excessive entries', () => {
  for (const text of ['', '  ', ',', '1,,2', '1, ,2', ',1', '1,', '1 NaN', 'Infinity', '-Infinity',
    '1e309', '0x10', '2deg', '1:5', '1;2', '--2'])
    assert.throws(() => parseOperatingPointAngles(text), Error, text);
  assert.throws(() => parseOperatingPointAngles(Array(MAX_OPERATING_POINTS + 1).fill('0').join(',')), /at most 200/);
});

test('plot paths use solved alpha, retain entry order and break across failures or missing values', () => {
  const sweep = {points:[successful(0, 5, {CL:.2}, 4.8), successful(1, 3, {CL:.1}), failed(2, 4),
    successful(3, 3, {CL:.3}), successful(4, 3, {CL:.35}), successful(5, 7, {CL:null}),
    successful(6, 8, {CL:.5}, null), successful(7, 9, {CL:Infinity}), successful(8, 10, {CL:0})]};
  assert.deepEqual(operatingPointSegments(sweep, 'CL'), [
    [{alpha:4.8, value:.2, index:0}, {alpha:3, value:.1, index:1}],
    [{alpha:3, value:.3, index:3}, {alpha:3, value:.35, index:4}],
    [{alpha:8, value:.5, index:6}], [{alpha:10, value:0, index:8}],
  ]);
  assert.equal(operatingPointRows(sweep)[6].actualAlpha, null);
});

test('failed rows and unavailable results cannot masquerade as valid zeros', () => {
  const diagnostic = {...failed(4, 3), result:{CL:5, CD:6}};
  const absent = {...successful(7, 4), result:null};
  const sweep = {points:[diagnostic, absent, successful(8, 5, {CDi:null})]};
  const rows = operatingPointRows(sweep);
  assert.equal(rows.length, 3); assert.equal(rows[0].values.CL, null);
  assert.equal(rows[1].success, false); assert.match(rows[1].error, /No converged/);
  assert.equal(rows[2].values.CDi, null);
  assert.deepEqual(operatingPointSegments(sweep, 'CDi'), []);
  assert.deepEqual(operatingPointRows(null), []);
});

test('CSV retains every failure, exact requested/actual angles, settings, and quoted error text', () => {
  const request = {action:'operating_points', mode:'mounted', panels:80,
    condition:{speed:30}, operating_points:{points:[{name:'A', condition:{alpha:2}}, {name:'B', condition:{alpha:5}}]}};
  const sweep = {analysis:'operating_points', mode:'mounted', converged:false, request,
    points:[successful(0, 2, {CL:0, CDi:null}, 2.3), failed(1, 5)]};
  const [header, ...rows] = csvRows(operatingPointsCSV(sweep));
  const value = (row, key) => row[header.indexOf(key)];
  assert.equal(rows.length, 2); assert.ok(rows.every(row => row.length === header.length));
  assert.equal(value(rows[0], 'requested_alpha_deg'), '2');
  assert.equal(value(rows[0], 'actual_alpha_deg'), '2.3');
  assert.equal(value(rows[0], 'plot_alpha_deg'), '2.3');
  assert.equal(value(rows[0], 'CL'), '0'); assert.equal(value(rows[0], 'CDi'), '');
  assert.equal(value(rows[1], 'status'), 'failed'); assert.equal(value(rows[1], 'CL'), '');
  assert.equal(value(rows[1], 'actual_alpha_deg'), '');
  assert.equal(value(rows[1], 'error'), sweep.points[1].error.message);
  assert.equal(value(rows[1], 'name'), sweep.points[1].name);
  assert.deepEqual(JSON.parse(value(rows[1], 'condition_json')), sweep.points[1].condition);
  assert.deepEqual(JSON.parse(value(rows[1], 'operating_constraints_json')), sweep.points[1].operating_constraints);
  assert.deepEqual(JSON.parse(value(rows[0], 'request_json')), request);
  assert.equal(value(rows[1], 'mode'), 'mounted');
});

test('JSON exports full provenance and diagnostic payloads without changing the sweep', () => {
  const sweep = {analysis:'operating_points', request:{model:'raw ASW text', panels:80},
    points:[successful(0, -2), failed(1, 0), successful(2, -2)], extra:{solver:'analytic'}};
  const before = structuredClone(sweep);
  assert.deepEqual(JSON.parse(operatingPointsJSON(sweep)), sweep);
  operatingPointRows(sweep); operatingPointSegments(sweep, 'CD'); operatingPointsCSV(sweep);
  assert.deepEqual(sweep, before);
});

test('seed origin and cold retry remain visible and survive CSV export', () => {
  const point = {...successful(1, 3), initialization:{kind:'previous_point', source_index:0, cold_fallback:true}};
  assert.equal(operatingPointStart(point), 'Point 1 → independent retry');
  assert.equal(operatingPointStart({...point, initialization:{...point.initialization, cold_fallback:false}}), 'Point 1');
  assert.equal(operatingPointStart({...point, initialization:{kind:'cold', reason:'Previous point failed.'}}), 'Independent');
  assert.equal(operatingPointStart(successful(0, 1)), 'Independent');
  const [header, row] = csvRows(operatingPointsCSV({points:[point]}));
  assert.deepEqual(JSON.parse(row[header.indexOf('initialization_json')]), point.initialization);
});

test('CSV reads Trefftz lift and side force from nested results without overriding supplied top-level zeros', () => {
  const sweep = {points:[successful(0, 2, {trefftz:{CLi:.24, CYi:-.02}}),
    successful(1, 3, {CLi:0, CYi:0, trefftz:{CLi:.8, CYi:.1}}),
    {...failed(2, 4), result:{trefftz:{CLi:.9, CYi:.2}}}]};
  const [header, ...rows] = csvRows(operatingPointsCSV(sweep));
  const values = key => rows.map(row => row[header.indexOf(key)]);
  assert.deepEqual(values('CLi'), ['0.24', '0', '']);
  assert.deepEqual(values('CYi'), ['-0.02', '0', '']);
});
