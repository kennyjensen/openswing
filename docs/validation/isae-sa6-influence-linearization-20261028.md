# SA-6 influence linearization and registered state comparisons

Updated 2026-10-28. SA-1 remains paused. This increment adds the completed
SA-6 state scope to the standard comparison runner and investigates its
sideslip discrepancy. It changes no production aerodynamic equations.

The [Technical Description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf),
§4.6, permits lagging induced-flow dependencies other than circulation during
isolated-wing Newton iteration. Section 8.3 obtains stability derivatives
through the same Newton system. The text does not explicitly establish whether
an exporter restores omitted influence derivatives. The separate K/F option
evaluates influences at jig geometry and zero wind angles; holding them at the
converged current operating point is a different approximation. The
[source audit](../../artifacts/isae/sa6-influence-linearization-20261028/source-audit.json)
retains the passages and all 264 native sideslip cells, including 125 negative
zeros. Every archived sideslip token prints zero, with a 5e-6 half-unit
rounding interval; this does not prove exact unrounded zeros.

The [bounded diagnostic](../../artifacts/isae/sa6-influence-linearization-20261028/diagnostic/report.json)
uses the original 15% and 35% chord models at F1=4 and 44, with nominal 64 and
128 intervals: eight cases, all at 12-degree incidence, zero sideslip, 20 m/s,
and explicitly zero Prandtl–Glauert Mach. Required stations make the actual lifting counts
66 and 130. Each case retains all 36 original state derivatives and their
printed precision. Both calculations use the same converged current base.
The conditional calculation holds the induced influences at that base while
retaining circulation response and the local nonlinear aerodynamic laws.

All eight workers complete in 31.94 seconds and are reaped, using 40 outer
aerodynamic calls and 16 derivative factorizations, with no retries. The four
coarser cases independently re-solve the held-influence nonlinear problem for
positive and negative incidence and sideslip perturbations at both prescribed
steps, 2e-5 and 1e-5 radians. All checks pass: maximum coefficient-derivative difference is 1.01e-8,
and maximum circulation-derivative difference is 7.92e-8. These check the
conditional derivative calculation, not historical ASWING identity.

| Selected scope | Finite valid values | Printed matches | Nonzero matches |
|---|---:|---:|---:|
| Full current operator | 288/288 | 48/288 | 0 |
| Current-base influence lagging | 288/288 | 88/288 | 0 |

The 40 additional matches are the five previously nonzero sideslip channels
in each of eight cases. All speed and rate columns remain unchanged within
the declared numerical gate. No complete 36-value state matches. The
conditional matches do not change any registered pass count.

Holding the influences fixed explains the zero pattern for these literal
inputs. At zero sideslip, its direct velocity derivative is purely spanwise.
The section normal and lift-generating velocity lie in the perpendicular
plane; zero skin friction removes the remaining spanwise force term.
The circulation residual therefore has zero first-order sideslip forcing,
and all six resulting coefficient derivatives vanish. This proof does not
identify the historical producer's chosen derivative convention.

Incidence derivatives still disagree. For example, the finer-mesh lift
derivative per radian is:

| Aileron chord | F1 | Archived ASWING | Full current operator | Current-base influence lagging |
|---|---:|---:|---:|---:|
| 15% | 4 | 1.26873 | 1.33734 | 1.08601 |
| 15% | 44 | 1.70769 | 1.79414 | 1.56821 |
| 35% | 4 | 1.32503 | 1.40010 | 1.14861 |
| 35% | 44 | 1.43585 | 1.64817 | 1.36115 |

The approximation makes some incidence comparisons worse and others closer;
none matches printed precision. It cannot resolve the unchanged speed/rate
differences or the static and F1 discrepancies. The production derivative
continues to use the full operator selected by its existing settings.

The [independent beta review](../../artifacts/isae/sa6-influence-linearization-20261028/beta-code-review.json)
also derives a closed-form wake-direction derivative for this straight,
constant-chord, zero-core geometry. After grouping coincident endpoints with
strengths +Gamma at each segment end and -Gamma at its start, the direct
induced-velocity derivative at a bound-vortex receiver, at fixed circulation, is

\[
\frac{\partial \mathbf V_{HV}}{\partial\beta}
=-\frac{\mathbf e\times\mathbf e_y}{4\pi}
\sum_j\frac{w_j}{|y-y_j|}.
\]

The independent formula agrees with the current direct HV induced-velocity
derivative within 1.09e-14 scaled error across all eight cases, against a 1e-10
gate. Total derivatives also include circulation response. The accompanying
source review finds no omitted beta term. In the 15%-chord, F1=4 pair, the current yaw/sideslip derivative
changes from 0.0397278 to 0.0466169 with refinement. Nearly all that change is
in the direct induced-load derivative; the circulation-response contribution
changes only from -0.00542550 to -0.00541496. The local inverse-distance term
explains a source of mesh sensitivity. It does not establish divergence of
the integrated coefficient or ASWING's historical wake treatment.

The [saved-data verification](../../artifacts/isae/sa6-influence-linearization-20261028/analysis/summary.json)
checks original tokens, tangent and wrench arithmetic, fixed-base coefficient
mapping, nonlinear perturbations and the closed-form wake identity without
new solves. Cache immutability and capture identity are runtime assertions
from the workers; before/after cache matrices were not separately serialized.
All 2,690 saved-data checks pass. The current matrices reproduce the earlier
comparison within 6.65e-16 scaled error. Speed/rate columns are exactly
unchanged in the retained arrays, and every conditional sideslip column is zero.

The standard runner now supports `--comparison-scope sa6-state-rigid`. Its
[implementation checks](../../artifacts/isae/sa6-influence-linearization-20261028/registration/implementation-receipt.json)
pass 485 distinct focused cases, including the existing static, F1, runner
and summary coverage. Default planning remains 91 jobs / 528 static slots.
The state option adds 88 jobs / 3,168 slots; both derivative options together
produce 267 jobs / 4,224 total slots. Each comparison scope is reported
separately, and original failures and missing outputs remain required.

One [fresh registered state job](../../artifacts/isae/sa6-influence-linearization-20261028/registration/smoke-execution-receipt.json)
returns 36 finite valid values, passes all 13 numerical checks, and matches
six zero side-force cells. It uses one base solve and one derivative
factorization. Its registered predictions exactly reproduce the previously
saved case on the unchanged kernel. The saved summary completes successfully;
the run's mismatch exit status is expected. The previous full 88-job state
comparison was not repeated for registration.

All 129 native and public kernel modules remain unchanged. The previous
native/WASM verification remains applicable to those identical bytes; this
increment adds no browser UI action. The full state comparison remains
528/3,168, the static scope 88/528, and F1 88/528, all exclusively zero
side-force matches. The 1,452 tensor entries, unpaired spanwise models,
historical derivative convention and nonzero discrepancies remain unresolved.
Whole-family acceptance remains 0/41.
