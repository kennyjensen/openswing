import { defineConfig } from 'vite';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { devKernel } from './scripts/dev-kernel.mjs';
import { devIsaeProgress } from './scripts/dev-isae-progress.mjs';
import { readKernelSources } from './scripts/kernel-sources.mjs';

function buildCommit() {
  try {
    const hash = execFileSync('git', ['rev-parse', 'HEAD'], {
      cwd: fileURLToPath(new URL('./', import.meta.url)),
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    }).trim();
    return /^[0-9a-f]{40}$/.test(hash) ? hash : '';
  } catch {
    return '';
  }
}

export default defineConfig(async ({command}) => {
  const kernel = new URL('./openswing/', import.meta.url);
  const plugins = [devKernel(kernel), devIsaeProgress(new URL('./', import.meta.url))];
  let kernelURL = '/kernel/sources.json';
  if (command === 'build') {
    const source = JSON.stringify(await readKernelSources(fileURLToPath(kernel)));
    const hash = createHash('sha256').update(source).digest('hex');
    const fileName = `kernel/sources-${hash}.json`;
    kernelURL = '/' + fileName;
    plugins.push({
      name: 'openswing-versioned-kernel',
      generateBundle() { this.emitFile({type:'asset', fileName, source}); },
    });
  }
  return {
    // Custom-domain Pages hosting serves the app and numerical assets at /.
    base: '/',
    plugins,
    define: {
      __OPENSWING_KERNEL_URL__: JSON.stringify(kernelURL),
      __OPENSWING_BUILD_COMMIT__: JSON.stringify(buildCommit()),
    },
    // Crawl the workbench's imports, not every HTML file in retained evidence.
    optimizeDeps: { entries: ['index.html'] },
    server: {
      // A code edit must not reload the page and discard a running browser solve.
      // Refresh manually to load changes after an analysis has finished.
      hmr: false,
      watch: {
        // These reference, experiment and staging trees are not application code.
        ignored: [
          '**/artifacts/**',
          '**/.reference/**',
          '**/reference/**',
          '**/.venv/**',
          '**/third_party/**',
          '**/.release-*/**',
        ],
      },
    },
  };
});
