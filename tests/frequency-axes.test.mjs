import test from 'node:test';
import assert from 'node:assert/strict';
import {plotAxis} from '../web/frequency-axes.js';

const near = (actual, expected, tolerance = 2e-14) =>
  assert.ok(Math.abs(actual - expected) <= tolerance, `${actual} != ${expected}`);

test('log axes enclose complete decades and place labeled majors and 2..9 minors', () => {
  const axis = plotAxis([.13, 8.2], {scale:'log'});
  assert.deepEqual(axis.domain, [.1, 10]);
  assert.deepEqual(axis.ticks.filter(t => t.major).map(t => t.label), ['0.1', '1', '10']);
  assert.equal(axis.ticks.length, 19);
  for (const value of [.1, 1, 10]) near(axis.position(value), (Math.log10(value) + 1) / 2);
  for (const decade of [.1, 1]) for (let multiplier = 2; multiplier <= 9; multiplier++) {
    const tick = axis.ticks.find(t => Math.abs(t.value - decade * multiplier) < 1e-14);
    assert.ok(tick && !tick.major && tick.label === '');
    near(tick.position, axis.position(decade * multiplier));
  }
  near(axis.position(Math.sqrt(.1)), .25);
});

test('log positions preserve decade spacing after explicit frequency-unit conversion', () => {
  const omega = [2 * Math.PI * .1, 2 * Math.PI, 2 * Math.PI * 10];
  const hz = omega.map(value => value / (2 * Math.PI));
  const axis = plotAxis(hz, {scale:'log'});
  assert.deepEqual(axis.ticks.filter(t => t.major).map(t => t.label), ['0.1', '1', '10']);
  hz.forEach((value, i) => near(axis.position(value), i / 2));
  assert.deepEqual(omega, [2 * Math.PI * .1, 2 * Math.PI, 2 * Math.PI * 10]);
});

test('roundoff at a decade boundary does not add a decade or change real range expansion', () => {
  const values = [.1 * (1 - Number.EPSILON), 10 * (1 + Number.EPSILON)];
  const axis = plotAxis(values, {scale:'log'});
  assert.deepEqual(axis.domain, [.1, 10]);
  assert.equal(axis.position(values[0]), 0);
  assert.equal(axis.position(values[1]), 1);
  assert.deepEqual(plotAxis([.1 * (1 - 1e-12), 10 * (1 + 1e-12)], {scale:'log'}).domain, [.01, 100]);
});

test('invalid and nonpositive logarithmic points stay gaps', () => {
  const values = [NaN, Infinity, -Infinity, 0, -1, null, .2, 4];
  const axis = plotAxis(values, {scale:'log'});
  assert.equal(axis.empty, false);
  for (const value of values.slice(0, 6)) assert.ok(Number.isNaN(axis.position(value)));
  assert.deepEqual(axis.domain, [.1, 10]);
  const empty = plotAxis([0, -2, NaN, Infinity], {scale:'log'});
  assert.equal(empty.empty, true); assert.deepEqual(empty.domain, [.1, 10]);
});

test('log singletons and narrow ranges stay finite with distinct decade ticks', () => {
  for (const values of [[1], [.2], [1, 1 + Number.EPSILON], [1e308]]) {
    const axis = plotAxis(values, {scale:'log'});
    assert.ok(axis.domain[0] > 0 && axis.domain[0] < axis.domain[1]);
    for (const value of values) assert.ok(axis.position(value) >= 0 && axis.position(value) <= 1);
    assert.ok(axis.ticks.some(t => t.major));
  }
  assert.deepEqual(plotAxis([1], {scale:'log'}).domain, [1, 10]);
});

test('subnormal and widest log ranges are bounded without dropping data', () => {
  for (const values of [[Number.MIN_VALUE], [1e-323, 1.7e308], [Number.MIN_VALUE, Number.MAX_VALUE]]) {
    const axis = plotAxis(values, {scale:'log'});
    assert.ok(axis.ticks.length <= 120 && axis.ticks.length > 0);
    assert.ok(axis.domain[0] <= Math.min(...values) && axis.domain[1] >= Math.max(...values));
    for (const value of values) assert.ok(Number.isFinite(axis.position(value)));
    for (const tick of axis.ticks) assert.ok(tick.value > 0 && Number.isFinite(tick.position));
    assert.equal(new Set(axis.ticks.map(t => t.value)).size, axis.ticks.length);
  }
});

test('linear axes retain signed phase and decibel values with sensible numeric ticks', () => {
  for (const values of [[-180, 180], [-60, 20], [0, 1], [-.003, .005]]) {
    const axis = plotAxis(values, {scale:'linear'});
    assert.ok(axis.domain[0] <= Math.min(...values) && axis.domain[1] >= Math.max(...values));
    assert.ok(axis.ticks.length >= 3 && axis.ticks.length <= 12);
    assert.ok(axis.ticks.every(t => t.major && t.label !== ''));
    const [a, b] = values;
    near(axis.position((a + b) / 2), (axis.position(a) + axis.position(b)) / 2);
  }
});

test('nearly constant linear physical gains do not magnify roundoff into visible motion', () => {
  for (const values of [[1, 1 + 1e-12], [-1, -1 + 1e-12], [1e-100, 1e-100 * (1 + 1e-12)]]) {
    const axis = plotAxis(values);
    assert.ok(Math.abs(axis.position(values[1]) - axis.position(values[0])) < 1e-8);
    assert.ok(axis.domain[0] < Math.min(...values) && axis.domain[1] > Math.max(...values));
  }
  assert.deepEqual(plotAxis([]).domain, [0, 1]);
});

test('linear zero, tiny, narrow and extreme ranges avoid collapsed coordinates or duplicate labels', () => {
  for (const values of [[], [NaN, Infinity], [0], [Number.MIN_VALUE], [-Number.MIN_VALUE],
    [1, 1 + Number.EPSILON], [Number.MAX_VALUE], [-Number.MAX_VALUE, Number.MAX_VALUE]]) {
    const axis = plotAxis(values);
    assert.ok(Number.isFinite(axis.domain[0]) && Number.isFinite(axis.domain[1]) && axis.domain[0] < axis.domain[1]);
    assert.ok(axis.ticks.length > 0 && axis.ticks.length <= 120);
    assert.equal(new Set(axis.ticks.map(t => t.value)).size, axis.ticks.length);
    assert.equal(new Set(axis.ticks.map(t => t.label)).size, axis.ticks.length);
    for (const value of values.filter(Number.isFinite)) assert.ok(Number.isFinite(axis.position(value)));
    for (const tick of axis.ticks) assert.ok(Number.isFinite(tick.position));
  }
  assert.equal(plotAxis([]).empty, true);
  assert.ok(Number.isNaN(plotAxis([0, 1]).position(NaN)));
  assert.throws(() => plotAxis([1], {scale:'other'}), RangeError);
});
