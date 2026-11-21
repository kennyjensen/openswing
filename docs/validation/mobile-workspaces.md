# Mobile workspaces

The mobile workbench now uses Editor, Settings, Plots, and Output tabs, following the requested [VibeLattice](https://avl.vibefoil.com/) navigation pattern. At widths of 720 pixels or less, Plots stacks the existing 3D aircraft view, span loading, eigenmodes, structure, time history, Bode response, and flow field. Available playback controls follow the aircraft view. Run, Cancel, and progress remain accessible across workspaces.

Editor contains model files, examples, projects, the ASW text editor, beam properties, and nodes. Settings contains the analysis and physical inputs. Output contains coefficients, exports, solver diagnostics, derivatives, sensor/controller tables, and ROM files. Responsive transitions move the original DOM nodes; they preserve controls, their event handlers, the existing canvas, and desktop detail-tab selection. Mobile workspace selection is also stored with computed-solution views. Leaving Plots pauses playback. Keyboard navigation uses arrow keys, Home, and End, with focus transferred to visible controls when the layout changes.

Two related ownership issues were fixed: case capture now finds inputs through stable configuration containers, and Run validates active numerical settings even while their workspace is hidden. Unrelated result/sweep controls no longer participate in that validation. Report headings live outside replaceable report content.

## Verification

The complete standalone JavaScript collection passed: 52 tests, no failures or skips. The first development browser pass completed two tests, but main.js changed during it; it is retained as development feedback rather than final-source acceptance.

The final production browser pass completed both declared cases, with no skipped, unexpected, or flaky results. All 128 recorded source/distribution hashes remained unchanged. The first case imports and edits a real ASW model, preserves saved-case numerical settings, rejects invalid hidden operating inputs before any solve request, performs an actual offline rigid solve, checks the loading chart and exports, and exercises every mobile workspace at 390 and 320 pixels. Repeated transitions to 1024/1440-pixel desktop layouts preserve the same controls and canvas, keyboard focus, and numerical results. It also verifies that an invalid auxiliary sweep input cannot block an unrelated rigid solve.

The second case computes the independent 2 kg, 500 N/m damped vacuum oscillator and checks its two eigenvalues against -2.5 ± i sqrt(243.75), using the existing six-decimal acceptance. It verifies stacked modal plots, phase playback, pausing when leaving Plots, report replacement, CSV/JSON exports, and healthy drawing after resize. Both cases inspect compositor pixels and renderer state; no solver or graphics context is mocked.

The four mobile screens and desktop restoration were also visually inspected. Test inputs, terminal records, exact sources, hashes, renderer artifacts, and the retained development attempt are in [the portable evidence archive](mobile-workspaces-evidence.zip). Machine-readable scope and source hashes are in [mobile-workspaces.json](mobile-workspaces.json).

These checks use the local production build, packaged WebAssembly runtime, and Chromium with a Mesa software graphics driver. They do not establish physical-device or broad browser coverage. Numerical modules are unchanged; no new full numerical regression or full ASWING feature-parity claim is made. Final source/offline packaging is audited separately to avoid self-referential archive checksums. No hosted deployment was performed.
