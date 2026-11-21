This is a diagnostic iteration state, not a converged equilibrium checkpoint.
It retains the ISAE AE-1 conditional literal Pazy model at nominal 120 panels
(121 intervals), 5 degrees and 30 m/s, at load fraction 0.5. The accompanying
request contains the complete source and flight condition. Only two all-zero
out-of-range Weight rows were removed from the upstream model; derived source
SHA-256: `5519a34e309291ef93bd95cbf8c73daba96c41da26e5a34cc8998d120e1c6fad`.

The state was captured from the unmodified solver in Pyodide 314.0.7, NumPy
2.4.6 and SciPy 1.18.0. Its full residual maximum is 1.094600706403649e-12,
just above the unchanged internal target 1e-12. The NPZ contains `x` and the
original diagnostic `residual`; tests recompute every residual used for
acceptance. Neither a stored residual nor a circulation-only check certifies
convergence. Native and WASM regressions require a fresh full residual and
bitwise unchanged mechanical and operating state.

The fixture comes from the retained 2026-10-25 runtime diagnostic accompanying
the conditional ISAE literal-model curve comparison. It is separate from the
primary-property, zero-gravity experimental comparison.
