# FFWT startup and remaining ASWING difference

The unchanged original FFWT-1 Flare10 case now reaches the same equilibrium
with fewer startup attempts. Both native meshes pass physical and saved-output
checks; the offline browser result agrees with native execution. **Archived
ASWING reproduction remains incomplete.** Experimental agreement is optional.

## Measured performance

| Quantity | Original, 182 intervals | Current, 182 intervals | Original, 358 intervals | Current, 358 intervals |
|---|---:|---:|---:|---:|
| Cold solve, seconds | 46.50 | 20.58 | 49.40 | 34.65 |
| Rejected initial targets | 29 | 0 | 28 | 0 |
| Residual evaluations | 2,979 | 1,996 | 2,717 | 1,731 |
| Fresh restored residual maximum | 4.76×10⁻¹³ | 3.71×10⁻¹³ | 7.06×10⁻¹³ | 6.83×10⁻¹³ |

These are single-run measurements of the two original requests on this host,
not a general speed guarantee. All 82 physical/restoration checks pass. Across
148,124 numerical outputs, the maximum difference from the prior solutions is
7.45×10⁻¹¹, within the predeclared `2e-8 + 2e-8*abs(reference)` gate. Prior
metadata remains checked. Only residual-evaluation and accepted-stage counters
are excluded: the accepted stage count changes from six to seven. Each new run
uses one fresh zero-load residual for its startup estimate.

The solver reuses the matrix already assembled for its zero-load rank check to
estimate a smaller first load target. The explicit load derivative includes
the finite hinge law and distributed endpoint couple. Its backward-checked
linear direction predicts physical nodal and relative-hinge rotation; the
first increment is at most the original increment and 90% of the existing
rotation limit divided by that rate.

This estimate accepts no physical state. Each target receives a fresh Newton
matrix and retains the line search, 5° Newton rotation safeguard, chart
rollback, rank checks and final residual gate. Unsupported contexts,
nonconverged zero-load states, ambiguous hinge slopes and failed predictions
retain the previous startup. Warm starts and models without hinges retain
their original path. Later-stage increment growth is unchanged.

All 33 focused tests and 172 distinct existing regressions pass. Two test-only
failures and their corrections remain in the evidence: a NumPy/Python boolean
identity assertion, and an older failure injector that patched an unused
solver entry point. Neither correction relaxes a physical acceptance gate.

## Reference status

The comparison retains the original [pilot](isae-ffwt-original.md) and
[declared setup](isae-ffwt-reference-contract.json): archived row 4, commanded
IAS 20.941885325558797 m/s and 5° incidence. Density 1.2256 kg/m³ equals the
literal sea-level reference density, so IAS equals TAS for this candidate.
Updated influences and zero PG Mach remain declared settings, not recovered
historical defaults.

The fine result still differs by +0.5713% in lift, +11.2425% in root chordwise
moment, +0.19846° in left-tip bank and −0.13120° in left-tip airflow incidence.
All eight coarse/fine printed-precision comparisons fail. Three of four 0.1%
mesh gates pass; root moment changes 0.7322%. Seven other archived coordinates
remain untested in this pilot. Historical per-point constraints, startup state,
frozen/updated influence selection and exact node placement remain unresolved.

## Saved hinge-field diagnosis

The fine root moment is a small remainder: +0.91853060675 N·m aerodynamic
moment and −0.86230264305 N·m gravity moment give 0.05622796370 N·m.
Aerodynamics accounts for 99.933% of its coarse-to-fine change. Two cells
immediately beside the left hinge contribute 114.665% of that aerodynamic
change, partly cancelled elsewhere. The independent
[saved free-body reduction](isae-ffwt-startup-reference-audit.json) passes
292 checks. This explains sensitivity of the relative error; it does not
waive the reference or mesh gate.

An independent 80-digit scalar Biot–Savart calculation checked four fine
receivers in those cells and two coarse counterparts. All 3,670 numerical
checks pass, with a maximum factored-velocity difference of 1.193×10⁻¹² m/s.
The six reconstructed velocities equal their saved values. No equilibrium
or residual was evaluated for this diagnosis.

At the fine center-side receiver, bound and trailing-wake normal velocities
are −64.1293 and +130.7173 m/s; their sum is +66.5880 m/s. The coarse sum is
+4.06489 m/s. Large opposing contributions persist at high precision. The
current construction places the two bound endpoints at the hinge about
0.720 μm apart along the wind; they remain separate.

No arithmetic, grouping or own-bound exclusion defect was found at these
six points. The [velocity audit](isae-ffwt-startup-velocity-audit.json) and
[summary](isae-ffwt-startup-velocity-summary.json) support sensitivity to
the zero-core vortex geometry near the deformed hinge. They do not establish
ASWING's historical endpoint placement or force quadrature. The two meshes
also have different circulation and hinge pose. No core, model parameter or
circulation was adjusted to improve agreement.

## Browser and reproducibility

The sole new offline browser solve takes **44.57 seconds**, versus the prior
87.31 seconds. Runtime initialization takes a separate 26.86 seconds; its
change is not attributed to the solver predictor. All 1,060 browser checks
pass, including 50,308 numerical comparisons with native execution under
the same absolute-plus-relative gate. The maximum absolute difference is
2.96×10⁻⁹, including predictor diagnostics. The browser comparison also
requires the native accepted-stage count to match. No page errors or offline
HTTP requests occur.

The [new checked project](../../examples/isae-ffwt-fast-start-project.json)
restores its result exactly without solving. The earlier project and original
pilot report remain byte-identical historical records.
The [machine report](isae-ffwt-startup.json) and
[evidence archive](isae-ffwt-startup-20261026-evidence.zip) retain old/new states,
executed sources, physical gates, saved-field operands, test failures and
corrections, and terminal process receipts. Timings cover two new native FFWT
cold solves and one browser cold solve; there are no automatic retries.
