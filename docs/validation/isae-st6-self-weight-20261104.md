# ST-6 distributed self-weight and modal refinement

Two fine-grid static cases, two public modal cases bracketing instability, and
the independent local growth-rate check pass their unchanged gates. Both real
offline browser cases pass **430/430 checks**,
including physical outputs, both eigenvector sides and project save/reopen.
This is analytical validation of a distributed-mass column. Original ISAE
fixtures and native ASWING agreement remain unverified.

The [literal example](../../examples/self-weight-column.asw) is a uniform 1 m
clamped/free column with EIcc=100 N m² and line mass 1 kg/m. Extension, shear
and the other rotation directions are exactly rigid. There is no tip mass,
airflow or intrinsic section rotary inertia. Compression varies with height:
`N(s)=-mu*g*(L-s)`, reaching zero at the free tip.

An independent continuous reference solves
`EI theta'' + mu*g*(L-s)*theta = 0`, with `theta(0)=0`, `theta'(L)=0`,
and `w'=theta`. Its Airy determinant gives
`gcr=7.83734743894349*EI/(mu*L³)`, or **783.73474389 m/s²** here.
The existing two reference tests independently shoot the differential equation
and check its scaling. They are retained without rerunning the unchanged formula.

| Static calculation | Critical gravity (m/s²) | Error versus continuum | Shape error |
|---|---:|---:|---:|
| n32 | 784.05034276 | 0.04027% | 0.05150% |
| n64 | 783.81370283 | 0.01007% | 0.01287% |

Both cases pass the 0.1% continuum gates. N32→N64 changes critical gravity by
0.03019% and shape by
0.03862%. The earlier N8 errors of 0.63453%
and 0.82574% remain failures. Full source Jacobians retain every mechanical
unknown; fresh physical residuals verify the straight base, varying compression,
load scaling and left/right null vectors.

At N32, loads ±0.01% around its discrete threshold give a lowest pair
`±0.35243225 i` below and `±0.35243242` per second above. The upper case has
one growing mode. Critical shapes agree within 0.000241%, and all 16 independent
left/right full-pencil checks pass. The energy identity
`d(lambda²)/dg = integral(mu*(L-s)*theta² ds) / integral(mu*w² ds)`
predicts 1.5844896136 per metre, compared with
1.5841909934 from the bracket: an error of
**0.01885%** at the unchanged 0.1% gate.
Higher distributed-mass modal frequencies are not independently validated.

The initial browser attempt failed its existing per-component comparison:
an imaginary applied-force component differed by 5.70e-8 against an allowance
near 2e-8. The force recovery was correct; the higher Ritz vectors were less
accurate because those modes lay far from the search shift.

The full-descriptor eigensolver now applies up to two checked bordered Newton
corrections to inaccurate simple Ritz pairs. It retains all coordinates and
does not change A or M. Corrections must improve the residual and remain local;
repeated selected poles keep their existing recovery route. The bordered
factorization also supplies the adjoint when its residual and mass-pairing
checks pass. Already accurate pairs need no extra factorization. Diagnostics
record corrections and factor counts explicitly.

On the saved physical pencil, one correction reduces the affected relative
residuals from roughly 5e-13 to 1e-16 and the spurious imaginary normalized
force from roughly 1e-7 to 3e-17. The entire four-mode replay takes
0.061 seconds in this observation. **All eight fresh static
and dynamic matrices are exactly equal to their pre-fix versions.** All
28 focused regression tests pass. Browser comparison tolerances remain
`2e-8 + 2e-8*abs(reference)`; no damping or force component is rounded to zero.

All 137 kernel modules agree between source, public and built copies. The
actual offline WASM worker passes both cases, including desktop/mobile plots
and byte-exact saved-project restoration. Numerical cases run serially with
one BLAS thread and a 512 MiB address-space limit. Sharing Python imports
between four small cases avoids repeated startup work.

The first browser rerun passes both physical cases but fails the separate
network check when a bundled font weight is first used after disconnection.
The harness now loads every CSS font face before disconnecting, in addition
to waiting for the numerical runtime. No later request is exempted. The full
rerun passes with this explicit resource-ready precondition; the original
network failure remains in `browser/report.json`.

The original invalid fixture, coarse continuum failures, failed browser
attempts and timed-out initial regression batch remain recorded. Current raw
evidence is in `artifacts/isae/modal-ritz-refinement-20261104/`; earlier failed
attempts are in `artifacts/isae/st6-self-weight-20261104/`.
[Portable numerical results](isae-st6-self-weight-20261104.json) include source
hashes and the browser summary. Post-buckling, original fixtures, higher-mode
frequency validation and native ASWING comparison remain open.
