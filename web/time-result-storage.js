// Private worker wire format. The UI, exports and standalone checkpoints keep
// their existing shape. Shared values survive structuredClone/postMessage.
const format = 'openswing-time-result';
const plain = value => value !== null && typeof value === 'object' && !Array.isArray(value)
  && Object.getPrototypeOf(value) === Object.prototype;

export function unpackTimeResult(packet) {
  if (!plain(packet) || packet.format !== format) return packet;
  const fail = () => { throw new Error('Invalid compact time result.'); };
  if (packet.version !== 1 || !plain(packet.result) || packet.result.analysis !== 'time_response'
      || !Array.isArray(packet.result.snapshots) || !Array.isArray(packet.values)
      || !Array.isArray(packet.references)) fail();
  const {result, values, references} = packet, seen = new Set(), writes = [];
  for (const ref of references) {
    if (!Array.isArray(ref) || ref.length !== 2) fail();
    const [path, index] = ref;
    if (!Array.isArray(path) || path.length < 1 || path.length > 6
        || !Number.isSafeInteger(index) || index < 0 || index >= values.length
        || !(plain(values[index]) || Array.isArray(values[index]))) fail();
    let parent = result;
    for (let i = 0; i < path.length; i++) {
      const key = path[i];
      if (Array.isArray(parent)) {
        if (!Number.isSafeInteger(key) || key < 0 || key >= parent.length) fail();
      } else if (plain(parent)) {
        if (typeof key !== 'string' || ['__proto__', 'constructor', 'prototype'].includes(key)
            || !Object.hasOwn(parent, key)) fail();
      } else fail();
      if (i === path.length - 1) {
        const name = JSON.stringify(path);
        if (seen.has(name) || parent[key] !== null) fail();
        seen.add(name);
        writes.push([parent, key, values[index]]);
      } else parent = parent[key];
    }
  }
  // Validate all targets first; nested refs cannot traverse a null target.
  for (const [parent, key, value] of writes) parent[key] = value;
  return result;
}
