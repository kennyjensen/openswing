# Free elastic wing–fin coupling

The combined distributed-elastic wing, fin, mutual-aerodynamic and six-free-frame
benchmark passes its fixed **1%** complete-output criterion. All **186** refined
comparisons pass, and every error decreases from 8 to 16 intervals per lifting
branch. The worst refined error is **0.5902%**.

This closes a controlled combined-component check. It does **not** resolve or
validate the [Daedalus Bode comparison](daedalus-shell-mesh.md), whose yaw at the
reference dip remains 2.172 times Drela's drawing. No production equation,
aircraft property, trim condition or numerical acceptance tolerance changed.

## Physical case and independent reference

The [literal fixture](../../tests/data/free-elastic-coupling/fixture.json) has a
4 kg carrier, a 2.4 m wing and a noncoplanar 1.6 m fin. Both lifting branches
have finite bending, torsional, axial and shear stiffness, distributed real
mass, offset centers of gravity and intrinsic section inertia. The wing carries
20 N axial tension and the fin 12 N. Their exact straight loaded geometry has
0.001 axial strain. A rigid carrier connects the offset roots.

At 10 m/s, both surfaces have nonzero steady circulation. The independent
32-point filament quadrature supplies circulation and nodal aerodynamic
counterloads once for each mesh. Constant body-coordinate counterloads cancel
the steady aerodynamic loading while preserving its full perturbation feedback.
Tensile tip loads and a separately balanced carrier wrench retain the preload.
The reference rotates these body-fixed loads into its inertial coordinates.
Each mesh is a separately balanced discrete aerodynamic model; this is not
convergence under a common set of fixed counterloads.

The independent mechanical reference integrates the continuous 12-state rod
tangent with distributed inertia, moving roots and the carrier's six balances.
It condenses the exact receiving-node compliance at each frequency, then closes
the circulation and aerodynamic-load feedback. There is no modal truncation.
Absolute Galilean node motions keep all frame/elastic inertia contributions
without adding a second frame mass to the distributed rods.

The aerodynamic reference numerically integrates the Biot–Savart law. It uses
zero cores within each physical surface and live `max(chord/4, interval length)`
cores between surfaces, following Drela's steady Eq. 161. Origin-relative wind
sets virtual points and wake direction; fixed Galilean atmospheric flow minus
absolute section velocity sets local relative flow. Circulation lag, rate lift,
profile force/couple and apparent force/couple remain active. Loads return to
nodes through the transpose of the motion interpolation.

These reference modules import no production physics. The separate native
adapter imports the same fixture and independently manufactured loads. Its full
initial residuals are `2.68e-15` and `2.04e-14`; equilibrium correction changes
neither base, and both retain exactly zero translational/angular acceleration.

## Results

Inputs are one radian of fin section incidence and a positive 1 N m carrier yaw
couple. Thirty-one groups retain every complex component: frame motion,
velocity/rates, absolute and relative node motions, circulation, local velocity,
strip force/couple families, and wing/fin/global wrenches. Translation is scaled
by 2.4 m when grouped with rotation; moment is divided by 2.4 m when grouped
with force. The error is the complete group's complex infinity-norm difference
divided by its reference infinity norm, separately for each input.

| Frequency | Largest 8-interval error | Largest 16-interval error |
| --- | ---: | ---: |
| 0.1 Hz | 1.8772% | 0.5064% |
| 1 Hz | 2.0423% | 0.5204% |
| 1.15737773741517 Hz | 2.3199% | 0.5902% |

The coarse mesh does not pass 1%; it supplies the refinement comparison.
All 186 refined criteria pass and all 186 errors decrease. The largest error
is wing relative motion under the physical yaw-couple input at 1.15738 Hz.

The independent aerodynamic preparation passes 200 checks. Its largest
normalized derivative change across quadrature orders 16/32 and complex-step
widths `1e-24`/`1e-20` is `1.07e-11`. Tightening continuous-rod integration from
`1e-9` to `1e-11` changes the final outputs by at most `3.67e-12` in the declared
normalized comparison. The largest independently integrated Green-map global
balance residual is `9.24e-14`.

The native systems have 448 and 752 coordinates. Each mesh uses one corrected
base, one full sparse matrix pair, one two-input matrix and three harmonic
solves. They require 409 and 521 full residual evaluations and take 7.23 and
16.63 seconds on the shared native host. These are component timings, not
browser or Daedalus performance measurements.

The independent saved-native audit passes 1,562 checks across all six harmonic
cases and 98 output snapshots, with no new physical evaluations or solves.
The separate saved-reference audit passes 5,648 checks, independently rebuilding
the Green and coupled equations, all output comparisons and 144 segment inertia
identities. Its largest normalized segment-identity error is `2.64e-14`.
The portable regression passes all 186 refined criteria; the two additional
reference-seam tests also pass.

## Reproduction and limits

Run the portable regression from the repository root:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest -q tests/test_free_elastic_coupling.py tests/test_free_elastic_aero_reference.py
```

To generate the independent reference and compare it with the current native
solver, use a new output directory:

```sh
.venv/bin/python -I -B scripts/free_elastic_reproduce.py --mesh 16 --output /tmp/free-elastic-check
```

This command retains the reference, native matrices, raw output snapshots,
source hashes and all 186 comparison criteria. It uses the accepted reference
resolution; the separate two-mesh study above supplies refinement evidence.
Selecting mesh 8 retains the same 1% gate and can therefore report a failure.
The mesh-16 command was run from the current repository and passed all 186
criteria, with unchanged source hashes and 49 retained output snapshots.

The [report](free-elastic-coupling.json), [complete comparison CSV](free-elastic-coupling.csv)
and [evidence archive](free-elastic-coupling-20261025-evidence.zip) retain frozen
sources, physical inputs, matrices, complex responses, original gates and
independent audits. The archive also retains a failed preflight before any
reference physics ran, and the subsequent corrected run. Omitted nested
transfer arrays were subsequently retained by exact reproduction of the six
accepted tight-tolerance Green maps; no aerodynamic or native solve was repeated
for that retention step.

Straight tensile preload does not exercise finite-curvature preload or
noncommuting loaded material interpolation. This case also has no live gravity,
propulsion, body-volume flow, strut or hinge. It supports the combined terms
present here; it does not identify the historical Daedalus trim or explain the
remaining aircraft-level yaw/roll disagreement.
