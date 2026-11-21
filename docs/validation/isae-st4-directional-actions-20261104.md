# ST-4 full-residual checks of the saved modal derivatives

The remaining sensitive ST-4 differences are much larger than the numerical
differentiation error found along the three examined modes. This rules against
derivative step size as their explanation; it does not establish native ASWING
agreement or independently validate the implemented physical equations.

Two retained 160-interval bases are restored into the current source airflow
operator. Their original mesh, physical fields and numerical coordinate scales
are checked before any perturbation. Fresh full residuals are 4.59e-16.
No equilibrium solve, Jacobian assembly or eigensolver is run.

With the unsteady convention `A = R_z`, `M = -R_zdot`, real centered probes
evaluate `A*v` and `M*v` directly from the nonlinear residual. Real and imaginary
parts of a complex mode are probed separately; aircraft states remain real.
Six dimensionless widths range from 1e-3 to 3e-6 after normalizing the largest
nodal translation/L or rotation component to one. Every equation is included.
The saved left and right vectors are separately checked against the original
pencil before use.

The left projection
`delta_lambda = left^H * (A_probe*v - lambda*M_probe*v) / (left^H*M_probe*v)`
estimates first-order pole sensitivity. It is not a new eigensolution or a
rigorous bound. Only vectors are promoted for extended-precision inner products,
avoiding another full matrix allocation. Coarse probe errors decrease roughly
quadratically, followed by a floating-point cancellation floor. The table uses
the larger absolute correction at the two smallest widths, 1e-5 and 3e-6.

| Speed, native ordinal | Quantity | OpenSwing | Archived ASWING | Native error | Estimated differentiation correction |
|---|---|---:|---:|---:|---:|
| 120.5 m/s, 1 | Im(lambda), rad/s | 1.913721198 | 3.3632329 | 43.10% | 9.32e-10 rad/s |
| 139.5 m/s, 3 | Re(lambda), 1/s | +0.034399706 | -0.088874035 | 138.71%, opposite sign | 5.24e-10 1/s |
| 139.5 m/s, 6 | Re(lambda), 1/s | -1.307094279 | -1.3368016 | 2.2223% | 2.70e-10 1/s |

The 139.5 slow pole differs from the finest independent reference by
9.65999e-4 1/s. Its other unresolved real component, ordinal 6, differs by
2.09537e-3 1/s. Both are many orders larger than these directional sensitivity
estimates. The existing 24/26 production mesh checks and 24/26 implementation/
reference checks remain unchanged and incomplete. The 120.5 imaginary component
also retains its native discrepancy. No value, tolerance or failed comparison
has been replaced by a corrected or extrapolated eigenvalue.

The two jobs use 146 fresh residual evaluations and take 19.21 and 10.53 seconds,
excluding initial evidence hashing. Peak RSS is below 164 MiB. They run serially
with one BLAS thread, a 90-second limit and a 512-MiB address-space cap. Maximum
mass-action relative difference across all widths is 1.13e-12. Cancellation in
the small slow-mode action gives a worst small-width relative action defect of
3.82e-8; the separate left projection above is more directly informative about
this eigenvalue's sensitivity.

Four formula tests pass. They check real probes of complex directions, the mass
sign, quadratic convergence with known nonlinear contamination, detection of a
deliberately incorrect saved tangent, complex scaling invariance, and rejection
of zero left/right mass pairing. The reusable helper is
`scripts/modal_directional_check.py`; the two-case runner is
`scripts/verify-isae-st4-mode-actions.py`.

Reproduce each job separately, using a new output directory:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  PYTHONDONTWRITEBYTECODE=1 nice -n 10 timeout --kill-after=5s 90s \
  prlimit --as=536870912 -- .venv/bin/python \
  scripts/verify-isae-st4-mode-actions.py /tmp/st4-actions-139p5 --speed 139.5
```

Use `--speed 120.5` and a different output directory for the other base.
[Portable results](isae-st4-directional-actions-20261104.json) retain the exact
native strings and both complex components. Raw action vectors, complete width
sequences and source/evidence hashes are in
`artifacts/isae/st4-directional-actions-20261104/`.

The next numerical investigation is spatial discretization and the zero-frequency
divergence condition. Any reuse of static blocks across speeds must first verify
their actual speed scaling against the full residual. As a preliminary check,
the two saved N160 static blocks agree with a speed-squared force/circulation
coupling and otherwise constant blocks to maximum-entry-scaled differences
below 2.37e-10. Exact elimination of all 1,944 mechanical unknowns, retaining
all 161 circulation coordinates, gives a zero-frequency speed candidate of
139.44477947957 m/s from both bases. This is a provisional matrix calculation,
not a validated divergence speed or an overall flutter boundary. Its full
physical residual and spatial refinement have not yet been checked. The first
attempt exceeded the existing memory cap while constructing an unnecessary
duplicate block matrix; direct block products and earlier object release let
the same calculation finish under the same cap. The failed source and receipt
are preserved with the candidate data.

Historical settings and
native mode identities remain unresolved. The scientific kernel and previously
verified browser build are unchanged; this validation-only increment does not
claim a fresh application build or full ST-4 validation.
