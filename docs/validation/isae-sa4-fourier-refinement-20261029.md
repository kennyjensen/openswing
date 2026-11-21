# SA-4 Fourier representation sensitivity

Updated 2026-10-29. Changing to the documented Fourier representation recovers
some numerical solutions, but **does not resolve SA-4**. Twelve of 22
predeclared calculations pass numerical checks; none of their 84 archived
output comparisons matches printed precision. All four 320-interval checks
are rejected by the local subsonic validity check.

The ISAE aerodynamic report recommends roughly 20–40 circulation variables
following its elliptical-wing convergence study. A subsequent source check
also found an explicit 40-node statement for SA-2 and a statement that SA-3/4
use the same number (report text lines 1855 and 1900). This supports a reported
count of 40; its wording, "circulation nodes," does not independently establish
the Fourier mode count or settings of the particular archived exports.
This study therefore uses fixed counts 20, 40 and 80 as a prospective
discretization check. It does not choose a count by fitting the archived output.

The counts below retain this study's original printed-precision criteria.
[ISAE_STATUS.md](ISAE_STATUS.md) records the subsequent 3% policy and
fresh registered results; the saved 22-job evidence has not been rescored here.

All six previously failed 160-interval incidences are included: 4.06, 4.60,
5.13, 5.57, 6.10 and 6.55 degrees. Each is solved independently from the cold
initialization at all three mode counts. Four additional jobs use 320 intervals
at 4.06 and 4.60 degrees with 40 and 80 modes. Original geometry, speed,
atmosphere, aerodynamic options, target values and comparison tolerances are
unchanged. No supplied circulation guess or retry is used.

| Intervals | Fourier modes | Valid solves | Archived matches / required checks | Median failed CL error | Median failed CD error |
|---:|---:|---:|---:|---:|---:|
| 160 | 20 | 2/6 | 0/42 | 0.191% | 0.969% |
| 160 | 40 | 5/6 | 0/42 | 0.0931% | 0.757% |
| 160 | 80 | 5/6 | 0/42 | 0.0242% | 0.458% |
| 320 | 40 | 0/2 | 0/14 | — | — |
| 320 | 80 | 0/2 | 0/14 | — | — |

Percentages are median absolute errors over valid failed comparisons only.
The successful incidence sets differ, so these medians alone do not establish
convergence with mode count. The 154 comparison slots reuse 42 distinct
archived output cells. Seventy slots have no valid prediction. These are
separate diagnostic results; the registered SA-4 count remains **0/588**, with
its original full-scope error percentages retained in `ISAE_STATUS.md`.

All ten rejected calculations exceed local section-normal Mach one near a
wingtip. At 4.06 degrees on 160 intervals, maxima are 2.317 with 20 modes and
1.444 with 40 modes. The 80-mode solution passes the numerical and subsonic
checks but has maximum dimensionless local circulation residual **1.153**.
Across all twelve accepted solutions, maximum local residuals range from
**0.589 to 8.230**. Their projected residuals pass the unchanged `1e-8` gate.

This distinction follows the published Fourier equations: a finite series
enforces weighted residual constraints, rather than zero residual at every
interval. The script independently reconstructs that projection from the
saved sine modes and material-angle widths. Passing the projected equations
does not establish a small local defect, mesh convergence or historical ASWING
agreement. Refining the two selected incidences to 320 intervals produces
Mach maxima between **1.286 and 3.262**, so it does not supply a converged
subsonic reference result either.

The batch finishes in **133.96 seconds**. All 22 workers are reaped; there are
no timeouts or unattempted cases. All 156 numerical checks on the twelve
returned solutions pass, including finite fields, parser diagnostics,
coefficient normalization, total-load reconstruction, drag decomposition,
projected residual and local Mach checks. Raw solved outputs and error details
are retained; failed states are not assigned percentage errors.

The next unresolved issue is the wingtip velocity and its sensitivity to
discretization. These results do not justify changing the physical equations,
disabling the local Mach check, or selecting a mode count as the answer.

Evidence: [predeclared protocol and source locations](../../artifacts/isae/sa4-fourier-refinement-20261029/protocol.json),
[all 22 outcomes](../../artifacts/isae/sa4-fourier-refinement-20261029/report.json),
and the preceding [initialization diagnostic](isae-sa4-initialization-20261029.md).
