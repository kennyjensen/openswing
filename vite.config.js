import { defineConfig } from 'vite';
import { devKernel } from './scripts/dev-kernel.mjs';
import { devIsaeProgress } from './scripts/dev-isae-progress.mjs';

export default defineConfig({
  // Custom-domain Pages hosting serves the app and numerical assets at /.
  base: '/',
  plugins: [devKernel(new URL('./openswing/', import.meta.url)), devIsaeProgress(new URL('./', import.meta.url))],
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
});
