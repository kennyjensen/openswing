# Packaged browser check for analytic circulation derivatives

The corrected derivative path passes in the actual packaged browser worker with both current and frozen aerodynamic influences. The browser computes offline after initialization. The exported derivative values agree with the saved native replay: **1,570 numeric values** pass the existing absolute/relative comparison, with maximum scaled error **0.0008536** against a limit of one.

The fixture is the original four-panel, unpowered regression wing at speed 30, zero incidence/sideslip and fixed Mach 0.1. Two mounted analyses include fixed-acceleration derivatives for alpha, roll rate and control 1, using the unchanged default step 1e-5. Both exports identify the analytic circulation method and fingerprint all 107 expected modules. There are no new native solves in this check.

Both physical residuals are zero. Maximum linear residuals are 7.074e-16 and 6.331e-16, below the unchanged 1e-8 gate; reciprocal condition estimates exceed the unchanged 1e-10 threshold. The comparison tolerance is 2e-8 + 3e-6 times the absolute native value. Parameter columns are reordered by name for comparison. Linear residual values are gated separately, and residual-evaluation counts are excluded from cross-runtime numerical parity.

The offline UI regression checks the coefficient table, section-curvature plot, CSV/JSON downloads and a 390-by-844 mobile output view without horizontal overflow. It exercises the SVG fallback with WebGL2 disabled. The screenshot and raw exports are retained. These checks do not establish large-model browser performance or experimental agreement.

A separate source-only checkout completed the normal build. Its source and local-app archives passed CRC checks and contain byte-identical solver modules. Optional raw validation archives were omitted from this checkout. ROOT runtime bundles and the hosted release were not updated. One durable Playwright regression was added; no numerical source or production tolerance changed.

The comparison and browser processes completed, and the owned preview was stopped and reaped. The elapsed run includes browser startup, UI actions and exports; it is not a solve benchmark. AE-3 mesh convergence and experimental validation remain separate work. ISAE coverage stays **17 partial / 24 pending / 0 fully validated**.

[Machine-readable record](analytic-gamma-browser.json) · [Derivative correction](isae-ae3-analytic-gamma.md) · [Evidence archive](analytic-gamma-browser-20261024-evidence.zip)
