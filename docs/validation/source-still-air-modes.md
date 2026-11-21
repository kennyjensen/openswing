# Source still-air modal inertia

Updated 2026-10-26. The explicit `drela-fixed-still-air-v1` policy adds
thin-strip apparent inertia to the source structural modal equations at a
stationary fixed frame. It requires positive fluid density and no flight
condition. This is implementation verification, not an archived ASWING match.

The acceleration terms follow Drela's unsteady theory, Eqs. 41–44. With local
chord `c`, structural-axis fraction `Xax`, and density `rho`, each endpoint has
normal apparent mass per length `mu = pi*rho*c²/4`, midchord arm
`d = (0.5-Xax)*c`, and spanwise pitch inertia `j = mu*c²/32`.
In local `[v_c,v_s,v_n,w_c,w_s,w_n]` order its matrix is
`W = mu*v*vᵀ + j*e_s*e_sᵀ`, where `v = [0,0,1,0,-d,0]` and
`e_s = [0,0,0,0,1,0]`. The reaction is minus this matrix times acceleration.
The physical endpoint frame rotates this complete matrix into body axes.

Completed endpoint loads are averaged over the unloaded interval length, then
transferred equally to its endpoints. The interval matrix is
`h/4 * [[W_left,W_right],[W_left,W_right]]`; it need not be symmetric when
properties or frames vary. No artificial symmetrization or real-mass finite
segment correction is applied to fluid inertia. Normal/pitch coupling and
one-sided chord/axis jumps are retained. Real mass, gravity and inertia reports
remain separate from apparent inertia.

At zero mean flow and zero base rates, this fluid contribution changes only
the acceleration matrix. There is no fluid stiffness, damping, buoyancy,
circulation or chosen wind direction. Material damping remains available.
Quadratic fluid motion terms, moving frames, nonlinear time response, Bode
response and ROM generation are outside this policy. Nonlifting bodies,
stepped axes, engines, struts and point aerodynamic volumes remain unsupported.
Exact historical ASWING sampling and modal agreement are unverified.

## Reproduction

The [uniform normal-shear/torsion example](../../examples/source-still-air-check.asw)
uses four equal intervals and a midchord structural axis. All 16 finite roots
have closed-form source-grid references. Run:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  .venv/bin/python scripts/verify-source-still-air-modes.py /tmp/source-still-air-check
```

The output directory must not exist. The runner saves the request, kernel
hashes, expected complete spectrum, matrices, computed eigenpairs and report.
The recorded native run passed with maximum relative root error 1.12e-14,
full-pencil backward error 3.61e-17 and dispatch time 0.73 s on this machine.

All 23 independent tests pass. They cover endpoint and interval inertia blocks, signs,
rotated/tapered geometry, conservation, sided properties, real-mass cache
isolation and unchanged static gravity loads. Separate scalar mode tests use
both four and eight intervals: all 48 finite roots match within 5.49e-15
relative error. First-frequency continuum differences decrease from 1.305%
to 0.323% under refinement. Another 132 related Python tests and 49 JavaScript
boundary/project tests pass.

The offline built browser passes 829/829 checks. All 16,200 A/M entries agree
with native output within 1.11e-16 absolute difference; the complete spectrum
and left/right full-pencil equations pass. Startup took 26.99 s and the solve
5.28 s on this host. The new result/project reopen byte-exactly, while two
previous vacuum projects and one default-formulation project retain their
saved results without another solve. Desktop and mobile rendering were checked.

Choose **Coupled eigenmodes → ASWING fixed-frame still-air modes · experimental**
and supply density, or open the [checked project](../../examples/source-still-air-check-project.json).
The [machine report](source-still-air-modes.json) and
[evidence archive](source-still-air-modes-20261026-evidence.zip) retain requests,
source hashes, complete comparisons and execution receipts.

The [ASWING comparison status](isae-aswing-reference-status.md) retains the
existing case results. No archived case is newly declared passing by this work.
