import { mkdir, copyFile, readdir, readFile, writeFile, stat } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { readKernelSources } from './kernel-sources.mjs';

const options = process.argv.slice(2);
if (options.some(option => option !== '--include-validation')) {
  throw new Error('Usage: node scripts/prepare.mjs [--include-validation]');
}

// Ship the same Python sources used by pytest, without a second JS physics port.
await mkdir('public/kernel', { recursive: true });
const bundle = await readKernelSources('openswing');
const modules = bundle.sources.map(([name]) => name);
for (const [name, source] of bundle.sources) await writeFile(`public/kernel/${name}`, source);
await writeFile('public/kernel/sources.json', JSON.stringify(bundle));
// Preserve the single-line manifest format used by the offline tested build.
await writeFile('public/kernel/manifest.json', `[${modules.map(name => JSON.stringify(name)).join(', ')}]`);
await mkdir('public/examples', { recursive: true });
for (const name of await readdir('examples')) await copyFile(`examples/${name}`, `public/examples/${name}`);

// Self-host the runtime and wheels: user configurations never leave the browser.
const runtime = 'public/runtime';
await mkdir(runtime, { recursive: true });
for (const name of ['pyodide.js', 'pyodide.mjs', 'pyodide.asm.mjs', 'pyodide.asm.wasm', 'python_stdlib.zip', 'pyodide-lock.json']) {
  await copyFile(path.join('node_modules/pyodide', name), path.join(runtime, name));
}
const lock = JSON.parse(await readFile('node_modules/pyodide/pyodide-lock.json', 'utf8'));
const version = JSON.parse(await readFile('node_modules/pyodide/package.json', 'utf8')).version;
const packages = new Set();
function include(name) { if (packages.has(name)) return; packages.add(name); lock.packages[name].depends.forEach(include); }
['numpy', 'scipy'].forEach(include);
for (const name of packages) {
  const info = lock.packages[name];
  const file = path.join(runtime, info.file_name);
  let data;
  try { data = await readFile(file); } catch {}
  if (!data || createHash('sha256').update(data).digest('hex') !== info.sha256) {
    const response = await fetch(`https://cdn.jsdelivr.net/pyodide/v${version}/full/${info.file_name}`);
    if (!response.ok) throw new Error(`Cannot download ${name}: ${response.status}`);
    data = Buffer.from(await response.arrayBuffer());
    if (createHash('sha256').update(data).digest('hex') !== info.sha256) throw new Error(`Checksum failed for ${name}`);
    await writeFile(file, data);
  }
  console.log(`Runtime package verified: ${name} ${info.version} (${(data.length/1048576).toFixed(1)} MiB)`);
}

// Ship implementation/tests/summaries separately from optional raw validation.
// package-source.py also records which downloads this build actually contains.
await mkdir('public/licenses', { recursive: true });
await copyFile('THIRD_PARTY.md', 'public/licenses/README.txt');
const { execFileSync } = await import('node:child_process');
execFileSync('python3', ['scripts/restore-validation-data.py'], { stdio: 'inherit' });
execFileSync('python3', ['scripts/package-source.py', ...options], { stdio: 'inherit' });
