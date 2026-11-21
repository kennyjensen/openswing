# ISAE AE-1 browser comparison — 2026-10-25

The actual Chromium interface and Pyodide worker reproduced the [native AE-1 pilot](isae-ae1-pilot.md) at 5° and 7° incidence, both at 30 m/s, using the same full mirrored wing and 60 intervals per half. The accepted comparison passed **464/464 checks across 43,446 native numerical values**. The largest absolute difference was **5.83 × 10⁻¹³**. This establishes browser/native agreement for these cases; the pilot's experimental discrepancies and measurement-axis uncertainty still apply.

The test used the existing local `dist` application, including its UI controls, structured mounted solver, progress display and JSON export. All **110 kernel modules** matched the working source, `public/kernel`, `dist/kernel`, native pilot and actual worker provenance. No rebuild or source substitution was needed. Chromium 145.0.7632.0 ran Pyodide 314.0.7, Python 3.14.2, NumPy 2.4.6 and SciPy 1.18.0. After runtime startup the browser was offline: no further HTTP requests, page errors or network failures were recorded. Desktop and mobile screenshots are retained with the evidence.

| Case | UI analysis interval | Native numerical values compared | Largest absolute difference | Worker progress events |
| --- | ---: | ---: | ---: | ---: |
| Zero-flow baseline | 2.17 s | 10,462 | 4.45 × 10⁻¹⁶ | 7 |
| 5°, 30 m/s | 26.89 s | 16,492 | 3.85 × 10⁻¹³ | 39 |
| 7°, 30 m/s | 31.65 s | 16,492 | 5.83 × 10⁻¹³ | 44 |

These intervals run from immediately before clicking **Run analysis** until the interface reports convergence and re-enables the button; they exclude JSON export. They include UI overhead, and a native sweep was running concurrently. They are observations from this local machine, not an isolated performance comparison or hosted-browser benchmark. The accepted harness took 138.38 s overall, including startup, file checks and output capture.

Every native result field was traversed, including state, mesh, circulation, forces, moments and wake outputs. The fixed numerical gate was `2e-8 + 2e-8 * abs(native)`. Only the two evaluation counters and the gravity-source label were excluded. Both paths had exactly zero body gravity; the UI's explicit pointwise-circulation selection also matched the native default. The two coupled residuals were 2.82 × 10⁻¹⁴ and 2.79 × 10⁻¹³, below the declared `1e-8` gate. Progress showed the four load stages and tangent assembly, with the displayed distinction between stage progress and overall completion.

The first browser attempt completed and exported the zero-flow baseline, then failed on a metadata comparison: the direct native constructor reported `analysis="mounted_static"`, while the structural UI API correctly reported `analysis="structural_static"`. All 10,462 numerical values agreed. That raw output and failed report were retained; the next attempt normalized only that label and **reused the saved baseline without solving it again**. Total execution was one zero-flow and two coupled worker solves, with no new native solves. An earlier draft syntax error was caught before browser startup and retained separately. Sessions 65649 (first attempt, exit 1), 66088 (accepted attempt, exit 0), and 99990 (project check, exit 0) all terminated and were reaped.

The [combined receipt](isae-ae1-browser.json) preserves exact errors, commands, gates, counts, source hashes and references to the raw browser evidence. The runnable harness is [test-isae-ae1-browser.mjs](../../scripts/test-isae-ae1-browser.mjs). The complete evidence lives under the recorded `browser` study directory; this comparison does not claim a full browser test suite or validation of untested operating points.

To open the verified example:

1. Download [pazy-isae-ae1-project.json](../../examples/pazy-isae-ae1-project.json).
2. In OpenSwing, open **Settings → Project & saved cases → Open project** and choose that file. On mobile, use the **Settings** tab.
3. Select **Skin-on 5deg 30m-s 60-half loaded**, then click **Load case**. Opening the project populates the saved list; loading the case restores the workbench.
4. Confirm mounted mode, 5°, 30 m/s and **Start from loaded equilibrium** enabled. Click **Run analysis** when you want computed results.

This project contains the editable model, exact mesh, density 1.23 kg/m³, Mach 0, gravity 0, and the enabled loaded equilibrium. **It contains no saved computed solution** (`solutions=[]`). A real UI export/import/load/re-export check passed **335/335 checks**, restoring the complete configuration and equilibrium without another solve; its eight worker requests were only model inspection and mesh distribution. The example has not been added to the default catalogue, and this work did not publish a hosted release.
