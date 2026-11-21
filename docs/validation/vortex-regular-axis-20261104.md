# Regular-axis vortex derivatives

The analytic vortex derivative now retains the nonsingular extended axis of
a finite segment and the upstream axis of a semi-infinite ray. These regions
already use the regular Biot–Savart velocity in the physical evaluator; the
derivative previously applied the self-influence mask to them and returned zero.
The geometry assembler consequently rejected these cases and used full physical
differences. The correction also applies to the shared flight-state derivative.

ASWING Technical Description §4.2, equations (160)–(161), defines the transformed
Biot–Savart integrals and cross-surface core. At a point on the axis beyond the
vortex's extent, no integration element coincides with the receiver. The
velocity is zero there, but transverse displacement has a finite derivative.
For a unit-direction upstream ray at axial coordinate `z < 0`, the receiver
derivative is `[u]cross/(8*pi*z²)`. Direct quadrature and 110-digit physical
differences independently verify the full receiver/source derivatives.

The implementation evaluates the rationalized expressions at the actual radial
distance, including zero, instead of applying an artificial radial floor in
these regular regions. Actual filament masks, permanent own-bound exclusions,
core radii, Prandtl–Glauert maps, ground images and independently moving endpoints
are retained. No circulation is rounded away, and the physical velocity
evaluator is unchanged. Truly masked filament stencils still use complete
physical differences.

| ST-4 N160 full matrix assembly | Previous path | Corrected derivative |
|---|---:|---:|
| Elapsed assembly time | 48.48 s | 9.09 s |
| CPU assembly time | 44.33 s | 8.24 s |
| Induced-field evaluations | 3,890 | 2 |
| Direct geometry columns | 0 | 972 |
| Peak process resident memory | 155.0 MiB | 316.9 MiB |

The saved physical equilibrium, original source, operating point and mesh are
identical. All 3,077 coordinates remain. The mass matrix is **exactly unchanged**;
the largest A-matrix difference is **2.96e-16** on the existing per-entry
`abs(delta)/(1+abs(reference))` scale. All 32 original left/right vector checks
pass, with maximum backward error **1.65e-15**. Neither equilibrium nor eigenvalue
search is repeated for this comparison.

These single-run measurements give a 5.34-fold reduction in assembly elapsed
time and a 5.38-fold reduction in CPU time. They do not establish an end-to-end
solve speedup. Retaining derivatives uses more memory; the measured process
still fits the same 512 MiB address-space cap. Existing derivative-storage
budgets and full-residual fallbacks remain in place.

All **169 tests pass** in two serial batches: 59 derivative/formula tests and
110 state, shared-source, grouped-ray and physical-velocity tests. The added
cases cover zero/tiny cores, both exterior segment axes, upstream rays, the
former switch radius in regular regions, scales from 1e-16 to 1e8, PG and
ground-image transformations, independent endpoint motion and retained true
filament rejection. The high-precision oracle's mask now follows the existing
physical velocity rule; its tolerances are unchanged.

A cold public N16/four-mode ST-4 request passes its complete equilibrium and
eigenvector gates and exercises all 108 direct geometry columns with two field
evaluations. This smaller case checks runtime behavior, not mesh convergence
or native ASWING agreement. The actual built offline browser passes all **21
comparison groups**, including complete A/M matrices, physical base, four modes,
both vector sides, complete modal outputs and independent original-pencil
residuals. The cold browser solve takes **10.12 s** in this observation. There
are no page errors, failed requests, external requests or requests after
disconnection. The exact posted request is recorded, and all 137 kernel hashes
are checked before and after the run. This is a worker check, not a new UI or
saved-project verification. Browser evidence is included in the accompanying
[portable results](vortex-regular-axis-20261104.json).

Recorded ISAE scores and thresholds are retained without new native comparison
credit. ST-4's outstanding slow-pole mesh/reference error and historical native
setup discrepancies remain open. Raw scripts, original kernel snapshot, full
matrices and execution receipts are in
`artifacts/isae/vortex-regular-axis-20261104/`.
