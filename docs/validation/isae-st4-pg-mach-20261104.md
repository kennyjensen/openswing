# ST-4 documented PG Mach diagnostic

2026-11-04. The documented `M = V/a` Prandtl–Glauert option does **not** resolve
either sensitive native ST4 discrepancy on the declared 64-interval grid.
Both alternatives retain the original model, density, gravity, zero incidence,
fixed frame, aerodynamic lag, 16-root request and original shift.

The [ASWING user guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt)
describes fixed PG Mach and `V/a` choices. The original driver does not select
between them. This diagnostic uses the literal sound speed 340.21 m/s; the
resulting Mach numbers are 0.354193 at 120.5 m/s and 0.410041 at 139.5 m/s.
For these fixed-frame perturbations, the base `V/a` value is held fixed.
Neither choice is claimed to recover the historical startup.

| Speed | Archived quantity, 1/s | Fixed M=0 | M=V/a |
|---:|---|---|---|
| 120.5 m/s | Low pair −25.040334 ± 3.363233i | −25.109615 ± 1.937084i | Two real poles: −39.611778 and −14.422597 |
| 139.5 m/s | Slow real root −0.088874 | +0.028922 | +2.427810 |

At 120.5, the nonzero Mach survey contains two real poles in the low-frequency
sector, without an oscillating pole near the archived frequency. Both real
poles are retained. At 139.5, the slow real-component error increases from
132.54% to 2,831.74%. No intermediate Mach value or other parameter is fitted.

These are four fresh **64-interval** diagnostic solves. They do not replace
the finer N160 results or establish separate mesh convergence. In particular,
the small positive baseline root at 139.5 still changes appreciably under
refinement; the [critical-region report](isae-st4-critical-refinement-20261104.md)
retains its failed production refinement checks. The archive's unidentified
tiny complex roots remain unclassified. The negative archived slow branch is
not sufficient evidence of overall native stability.

Every job completed within its 90-second, 512-MiB limit, serially with one BLAS
thread. Full bridge dispatch took 29.14–32.43 s per job, totaling 120.96 s.
Four fresh evaluations of the full dynamic residual at the base pass, with
maximum 3.23e-16. All **128** saved left/right eigenvector checks against the
original unscaled sparse A/M pass; maximum backward error is **9.74e-16**.
Complete matrices, modes, requests, process receipts and source pins are retained.

Production equations, application assets and registered comparison scores are
unchanged. This narrows one documented setup hypothesis; it does not prove the
archive wrong, authenticate native mode identity or validate ST4.

[Predeclared jobs and sources](../../artifacts/isae/st4-pg-mach-20261104/plan.json),
[results](../../artifacts/isae/st4-pg-mach-20261104/assessment.json).
