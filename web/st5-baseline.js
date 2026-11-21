import {st5Examples} from './st5-baselines.js';
import {SECTION_NUMERICS} from './numerical-policy.js';

export {st5Examples};
export const isST5Example = key => Object.hasOwn(st5Examples, key);

// Applying a comparison is explicit. Ordinary geometry loading and existing
// saved projects keep their own numerical settings and node distributions.
export async function st5BaselineConfiguration(configuration, key) {
  if (!isST5Example(key) || configuration.filename !== `${key}.asw`)
    throw new Error('Load an original ST-5 example before applying its comparison setup.');
  const next = structuredClone(configuration), preset = st5Examples[key];
  const bytes = new TextEncoder().encode(next.source);
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  const hash = [...new Uint8Array(digest)].map(v => v.toString(16).padStart(2, '0')).join('');
  if (hash !== preset.source_sha256)
    throw new Error('This ST-5 source has changed. Reload the original example to apply its comparison setup.');
  next.numerics = {...SECTION_NUMERICS};
  next.mesh = structuredClone(preset.mesh);
  Object.assign(next.fields, {
    mode: 'structural', 'static-gravity-mode': 'file', 'strut-mode': 'bilateral',
    'derivatives-enable': false, 'feedback-enabled': false,
  });
  for (const name of ['controls', 'powers', 'circulation'])
    for (const id of Object.keys(next[name])) next[name][id] = '0';
  next.constraints = [];
  next.derivative_parameters = [];
  next.equilibrium = {state: null, enabled: false, label: ''};
  return next;
}
