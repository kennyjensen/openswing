# ST-5: original archived ASWING comparison

Updated 2026-10-25. **The selected case is not yet a reference match.** This
comparison targets the original `JW_1_20lb_80_20` rigid-joint ASWING output,
using the unchanged `.asw` file. Experimental agreement is optional and is
not a completion condition. No material property, load, attachment, solver
tolerance or geometry was adjusted to improve agreement.

The subsequent [isolated interpolation diagnostic](isae-st5-spline-diagnostic.md)
reduces the geometric discrepancy and reaches the mesh gate, but still does
not match the archived solution. The baseline results below and its app
project retain the original production interpolation.

The three cold native solves take 0.85, 1.09 and 1.77 seconds on the test
machine. All pass equilibrium, support force/moment balance, clamped-root and
rigid-joint checks. These numerical checks do not establish ASWING agreement.

## Reference interpretation

The original table has 80 rows and 28 columns, including its station coordinate.
All raw tokens, duplicate rows and printed exponents are preserved. The
historical MATLAB loader applies the exponents to every column, but this
conflicts with the original grounded geometry and scalar section properties.

For this specific export, independent checks support applying the printed
exponents to the six forces/moments and to EPS/tau, while retaining the other
raw values. This reproduces the archived total force of 38.58 lb and total
pitching moment of −41.45 lb·ft **about the body origin**. The coefficient
reference point at x = 1.09 ft is not the origin of that displayed moment.
The rear shell strain and stress can also be reconstructed at all 36 printed
nodes from the original linear material distributions and archived wrenches.
Rear tau uses a multiplier of 100; forward tau uses 1000.

This is a case-specific, physically checked decoder. The original exporter
implementation is unavailable, so it is not a proposed universal ASWING
header rule. The [target manifest](isae-st5-reference-target.json) retains
the source pins, raw values, selective scaling and remaining qualifications.
The earlier [ST-5 study](isae-st5.md) and [literal load study](distributed-static.md)
remain historical records; their MATLAB-reduced moment agreement is not a
substitute for this comparison.

## Current comparison

The three nested meshes contain 38/32, 76/64 and 152/128 intervals in the
forward/rear beams. They retain every original output station, replacing
known endpoints and attachment stations with their exact model coordinates.
The positive forward joint prints 2.000999 although its original input station
is 2.001; both facts are retained. These meshes are not claimed to reconstruct
the unknown historical ASWING mesh.

| Positive tip quantity | Archived ASWING | OpenSwing, finest mesh |
|---|---:|---:|
| Forward vertical displacement, ft | 0.012013 | 0.011765082 |
| Forward twist, degrees | −0.060040 | −0.057367917 |
| Rear vertical displacement, ft | 0.006272 | 0.006175774 |
| Rear twist, degrees | −0.059695 | −0.058348458 |

The forward vertical displacement differs by about 2.06%; the rear differs
by about 1.53%. The forward clamped dihedral is 4.886146° in OpenSwing versus
4.777737° in the archive, and the corresponding sweep angles are −30.851727°
and −30.687611°. Those root orientations are fixed by the undeformed geometry,
so their discrepancy cannot be removed by further structural mesh refinement.
The straight rear root agrees within about 0.000008°.

Every archived column is accounted for separately:

- 1,120 computed structural entries: position, surface Euler angles, one-sided
  force/moment traces and nodal shell strain/stress. On the finest mesh, 70 are
  inside the original output half-last-place intervals; no complete structural
  row meets that strict criterion. Unknown unrounded coordinates remain a
  separate qualification, not a fitted correction.
- 800 prescribed-motion, zero-airflow or zero-control entries. They reproduce
  the table's zeros but provide no dynamic or aerodynamic validation.
- 160 chord/cm display entries reconstructed from the original material
  distributions at successive output-row midpoints, including zero-width
  display intervals and the final dummy zeros. These are input echoes.
- 80 `f_reac` entries retained as a scalar signed-weight diagnostic. Their
  general nonflat normal-force definition is not established by this export,
  so these are not accepted as a validated prediction.

Maximum fresh equilibrium residual is 7.90×10⁻¹⁵, force imbalance is
1.43×10⁻¹⁴ lb and moment imbalance is 3.07×10⁻¹² lb·ft. All clamps and rigid
offset joints satisfy the predeclared 10⁻¹⁰ position/rotation check.

Only 7 of 14 structural field measures pass the predeclared 0.1% mesh-change
gate between the middle and finest grids. The largest change is 0.582% of
the twist-deformation envelope. The mesh failures are retained; a small
equilibrium residual does not establish spatial convergence.

The [offline browser replay](isae-st5-reference-browser.json) passes all 699
checks using the middle grid. Its solve takes 3.32 s after 25.97 s startup;
all 15,275 numerical result values agree with native output within the
predeclared comparison limits, with maximum absolute difference 2.81×10⁻¹¹.
The saved result restores byte-for-byte without another solve, and desktop
and mobile plotting checks pass. The [saved project](../../examples/isae-st5-reference-project.json)
can be imported into the app. Two initial UI test-harness failures occurred
before any solve request; both attempts are preserved in the evidence.
The completed browser run performs exactly one cold solve. No production
kernel or app behavior was changed in this validation increment.

## Remaining work and reproduction

First resolve the source-supported geometry/property interpolation convention,
then repeat the comparison on an adequately converged mesh. Historical NODE
and automatic startup settings remain unknown. The filename's nominal load
is not used to renormalize its original mirrored signed-weight distributions.
No experimental-property reconstruction is required for this work.

The [summary](isae-st5-reference-summary.json) contains every per-column metric
and mesh check. The [evidence archive](isae-st5-reference-20261025-evidence.zip)
preserves the original input/driver/output, all raw and alternate decodings,
the frozen plan, three results, fresh physical fields and independent reviews.

```sh
.venv/bin/python scripts/verify-isae-st5-archived-output.py prepare --stage /tmp/st5-reference-new
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  .venv/bin/python scripts/verify-isae-st5-archived-output.py run --stage /tmp/st5-reference-new
```

The original reference comes from the pinned
[ISAE repository](https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation/tree/f62943df20e9e4d7d9f50e070477b22426b5f865/3%20-%20Structure/CASE%20-%20ST5%20Joined%20Wing/Rigid_Joint).
The full ST-5 family and the full OpenSwing feature goal remain incomplete.
