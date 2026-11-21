// Display coordinates only. Invalid/log-nonpositive values remain gaps.
const MAX_TICKS = 120;
const MAX_MAJOR_TICKS = 20;
const finite = value => typeof value === 'number' && Number.isFinite(value);
const clampFinite = value => Math.max(-Number.MAX_VALUE, Math.min(Number.MAX_VALUE, value));

function numberLabel(value) {
  return value === 0 ? '0' : Number(value.toPrecision(12)).toString();
}

function logLabel(exponent) {
  if (exponent >= 0 && exponent <= 6) return String(10 ** exponent);
  if (exponent < 0 && exponent >= -6) return (10 ** exponent).toFixed(-exponent);
  return `1e${exponent}`;
}

function decimalLog(value) {
  const exponent = Math.log10(value), nearest = Math.round(exponent);
  const decade = 10 ** nearest;
  // Unit conversions can land a few ulps either side of a decade. Only
  // snap that roundoff; a genuinely wider range still gets another decade.
  return finite(decade) && decade > 0 &&
    Math.abs(value - decade) <= 4 * Number.EPSILON * Math.max(value, decade)
    ? nearest : exponent;
}

function logarithmic(minimum, maximum, empty) {
  let first = Math.floor(decimalLog(minimum));
  let last = Math.ceil(decimalLog(maximum));
  if (first === last) {
    if (last < 308) last++;
    else first--;
  }
  // Complete decades except at the finite IEEE-754 limits, where a whole
  // enclosing decade cannot be represented as a positive finite number.
  const low = Math.max(Number.MIN_VALUE, 10 ** first);
  const high = Math.min(Number.MAX_VALUE, 10 ** last);
  const a = decimalLog(low), b = decimalLog(high);
  const position = value => finite(value) && value > 0 ? (decimalLog(value) - a) / (b - a) : NaN;
  const start = Math.ceil(a), end = Math.floor(b);
  const stride = Math.max(1, Math.ceil((end - start + 1) / MAX_MAJOR_TICKS));
  const exponents = new Set([start, end]);
  for (let exponent = Math.ceil(start / stride) * stride; exponent <= end; exponent += stride)
    exponents.add(exponent);
  const ticks = [];
  for (const exponent of [...exponents].sort((x, y) => x - y)) {
    const value = 10 ** exponent;
    if (finite(value) && value >= low && value <= high)
      ticks.push({value, position:position(value), major:true, label:logLabel(exponent)});
  }
  if (stride === 1 && 9 * (last - first + 1) <= MAX_TICKS) {
    for (let exponent = first; exponent < last; exponent++) {
      for (let multiplier = 2; multiplier <= 9; multiplier++) {
        // Decimal parsing avoids underflowing 10**-324 before multiplication.
        const value = Number(`${multiplier}e${exponent}`);
        if (finite(value) && value >= low && value <= high && !ticks.some(t => t.value === value))
          ticks.push({value, position:position(value), major:false, label:''});
      }
    }
  }
  ticks.sort((x, y) => x.value - y.value);
  return {scale:'log', domain:[low, high], position, ticks, empty};
}

function niceStep(value) {
  const power = 10 ** Math.floor(Math.log10(value));
  const fraction = value / power;
  return (fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 5 ? 5 : 10) * power;
}

function linear(minimum, maximum, empty) {
  const normalizer = Math.max(Math.abs(minimum), Math.abs(maximum)) || 1;
  const a = minimum / normalizer, b = maximum / normalizer;
  // Do not turn roundoff around a constant physical gain into a full-height
  // excursion. Scaling first also keeps the arithmetic finite at IEEE limits.
  const padding = empty ? 0 : .08 * Math.max(b - a, .1 * Math.max(Math.abs(a), Math.abs(b)), a === 0 && b === 0 ? 1 : 0);
  const step = niceStep((b - a + 2 * padding) / 5);
  const first = Math.floor((a - padding) / step);
  const last = Math.ceil((b + padding) / step);
  let low = clampFinite(first * step * normalizer);
  let high = clampFinite(last * step * normalizer);
  // Subnormal rounding can collapse a padded singleton onto itself.
  if (!(low < high)) {
    if (minimum >= 0) { low = 0; high = Math.max(Number.MIN_VALUE, 2 * maximum); }
    else { low = Math.min(-Number.MIN_VALUE, 2 * minimum); high = 0; }
  }
  const left = low / normalizer, right = high / normalizer;
  const position = value => finite(value) ? (value / normalizer - left) / (right - left) : NaN;
  const ticks = [];
  for (let i = 0; i <= Math.min(last - first, MAX_TICKS - 1); i++) {
    const value = clampFinite((first + i) * step * normalizer);
    if (value >= low && value <= high && !ticks.some(t => t.value === value))
      ticks.push({value:value === 0 ? 0 : value, position:position(value), major:true, label:numberLabel(value)});
  }
  // Preserve distinct labels when a narrow range needs all available digits.
  if (new Set(ticks.map(t => t.label)).size !== ticks.length)
    for (const tick of ticks) tick.label = String(tick.value);
  return {scale:'linear', domain:[low, high], position, ticks, empty};
}

/** Build a bounded axis. position(value) is normalized, not pixel-valued.
 * Log domains enclose whole decades; beyond the finite number limits their
 * endpoints are clipped. Roundoff-sized decade deviations are snapped.
 * Very wide log ranges omit minors and thin majors.
 */
export function plotAxis(values, {scale = 'linear'} = {}) {
  if (!['linear', 'log'].includes(scale)) throw new RangeError('Axis scale must be linear or log.');
  let minimum = Infinity, maximum = -Infinity;
  for (const value of values ?? []) {
    if (!finite(value) || (scale === 'log' && value <= 0)) continue;
    minimum = Math.min(minimum, value); maximum = Math.max(maximum, value);
  }
  const empty = minimum === Infinity;
  if (empty) [minimum, maximum] = scale === 'log' ? [.1, 10] : [0, 1];
  return scale === 'log' ? logarithmic(minimum, maximum, empty) : linear(minimum, maximum, empty);
}
