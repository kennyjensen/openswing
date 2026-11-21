const finite = value => typeof value === 'number' && Number.isFinite(value);
const number = value => finite(value) ? Number(value.toPrecision(7)).toString() : 'unavailable';

export function fourierWakeOptions(mode, enabled) {
  if (typeof enabled !== 'boolean') throw new Error('The continuous wake check must be on or off.');
  return enabled && mode === 'rigid' ? {fourier_wake_diagnostic:true} : {};
}

export function fourierWakeSummary(trefftz, requested = false) {
  const reference = trefftz?.continuous_fourier;
  if (!reference) return requested ? 'Continuous Fourier wake check was not returned. Reload the app to load the current solver.' : '';
  if (!reference.available) return `Continuous Fourier wake unavailable: ${reference.reason || 'No supported reference calculation was returned.'}`;
  let difference = '';
  if (finite(reference.CDi) && finite(trefftz.CDi)) {
    const delta = reference.CDi - trefftz.CDi;
    const percent = trefftz.CDi === 0 ? null : 100 * delta / Math.abs(trefftz.CDi);
    difference = finite(percent) ? ` (${percent >= 0 ? '+' : ''}${number(percent)}% from discrete CDi)` : ` (difference ${number(delta)})`;
  }
  return `Continuous Fourier wake: CDi = ${number(reference.CDi)}${difference}; span efficiency = ${number(reference.efficiency)}. The main coefficients retain the discrete wake calculation.`;
}
