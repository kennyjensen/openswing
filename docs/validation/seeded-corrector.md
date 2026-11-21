# Sparse correction from a saved equilibrium

The final dense rank check described in this historical study is now replaced, on eligible paths, by a [guarded sparse check with full SVD fallback](final-equilibrium-rank.md). Its new evidence is separate; the original measurements below are retained.

The saved-equilibrium optimization is integrated and verified in native Python, WebAssembly and the application browser. The source and local public kernel contain 108 modules. This selected-path improvement does not complete ISAE validation or the full project goal. The [machine-readable summary](seeded-corrector.json) pins the supporting reports.

The corrector uses the existing complete sparse Newton matrix and beam elimination during eligible mounted corrections from a saved physical state. It retains every equation and unknown, the full physical residual acceptance checks, and the original final dense tangent and rank gate. No lagged iteration fields are installed. Supported structured build, factor, direction or line-search failures retain the original dense recovery; memory errors and interruptions propagate.

Eligibility requires an unmodified native `StaticNetwork`, a mounted aerodynamic condition and no operating/trim unknowns or constraints, custom allocation, feedback/controller seed, hinges, engines, struts, wires, residual overrides, custom final tangent or inherited iteration/tangent/load owners. Declined configurations keep their previous path. The default derivative step and scientific tolerances are unchanged.

| Evidence | Recorded outcome |
| --- | --- |
| Selected native regressions | 126 candidate tests counted after the verified stale-test repair; evidence qualifications below |
| Dedicated controls | 43/43 pytest tests passed; original recorder failure and saved-only correction retained |
| Matched small native cases | 2 pairs and 4,949 numeric comparisons pass with current/frozen influence examples; initial invalid mirrored-mesh setup retained |
| Node-hosted Pyodide | 33/33 checks; 2,236 numeric comparisons, eligible path and injected fallback |
| Large native replay | 49,176 numeric state/result comparisons pass; only top-level `evaluations` excluded |
| Original isolated application browser | 38/38 checks, 2,238 numeric comparisons, all 108 worker-source hashes and zero offline HTTP requests |
| Installed native source | 46/46 tests: 43 controls and 3 repaired hinge-guard tests; these are reruns, not added unique tests |
| Final installed-source browser | 38/38 checks, 2,238 numeric comparisons; exact installed worker sources and offline operation |
| Durable WASM regression | 27/27 checks, 2,240 numeric comparisons; structured solve and dense fallback, each with a fresh residual |

The regression count is **126**, comprising 83 first-run progress pass marks, 40 completed remaining tests and three replacement tests for one stale expectation. The first run reached its 360-second cap; its buffered recorder did not preserve detailed per-test reports, so those 83 progress marks are narrower evidence. The unchanged baseline and candidate both rejected the near-π hinge fixture earlier at the existing chart guard. The three repaired tests separately retain the slope-break check, earlier chart rejection and reachable static logarithm-branch guard; all three passed on each source. These six targeted passes are not six additional candidate tests. The separate 43-test controls suite exited pytest successfully, but its recorder sampled collection count too early and exited 1. A saved-only correction confirms all 43 unique tests and preserves the original failure; no tests were rerun for that correction.

The large AE-3 replay uses the saved zero-control seed and the same +0.05 control target on the 320-element, **4,172-unknown** mesh. The native Cl difference is **7.42e-19**, below **3.3513e-11** using the original qS=310.3461733031819 and Bref=1.2192. The fresh full residual is **1.4243e-11**, below 1e-8. The independent saved-output audit passes 460 checks; it was prepared after launch but before reading outcome contents. Original corrector residuals and final dense-rank results are source-owned scalar evidence; only the saved fresh full residual vector was independently norm-checked.

The candidate recorded **4,498 equilibrium residual calls versus 6,423** in the prior audited baseline, a **29.97%** reduction in this count. Its single native correction took **102.688 seconds**, including **56.595 seconds** in the unchanged final dense rank check. Process maximum RSS was **544,140 KiB**. One sparse iteration factor served two direction calls and was released before the final tangent; no dense iteration fallback was recorded. These are individual observations, not a controlled wall-time speedup or total-memory improvement claim. The factor payload budget is not a process peak-memory bound.

All **five** earlier 1% mesh failures remain: global changes **2.0773%** and **7.1435%**, and regional changes **3.4688%**, **4.1729%** and **6.3620%**. The [finest-mesh finite-control checks](isae-ae3-320-finite-control.md) do not resolve those failures. AE-3 remains pending; coverage stays **17 partial / 24 pending / 0 fully validated**. No original ASWING executable is available for parity checks. Experimental setup/observable matching remains unfinished.

The source and local `public/kernel` now contain 108 modules. The installed helper differs from the tested candidate only in its module docstring; executable AST is unchanged. The final-source isolated application build also contains 108 modules. The original isolated browser check verified warm offline operation after initial loading with SVG fallback; it does not cover cold startup, WebGL, a fresh browser-network residual, the whole UI suite or performance. Declared zero-gravity and omitted/zero-mode representation differences were retained explicitly; physical comparisons kept their original gates. The final installed-source browser replay and durable WASM regression both pass. Pyodide runtime binaries, hosted release and raw/download distributions are unchanged. The isolated test builds omit optional download ZIPs; they are not release packages.

Next work must address the remaining final-tangent/rank time and peak-memory limit before a larger full-mesh run, while retaining the existing acceptance criteria. Experimental matching and the five mesh failures need separate resolution.

Run the durable checks with `.venv/bin/python -m pytest -q tests/test_seeded_corrector.py`, `node scripts/test-seeded-corrector-wasm.mjs`, and `npx playwright test tests/browser/seeded-corrector.spec.js` against a prepared local app. The browser test uses the repository Playwright configuration.

[Evidence archive](seeded-corrector-20261024-evidence.zip)
