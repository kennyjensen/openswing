# SA-6: separating control-point and force-point rate sampling

The subsequent [common-location bound](isae-sa6-rate-location-bound-20261101.md)
rules out every common fixed x/z sampling pair within the retained formulation,
including choices beyond the two components below. Its exact certificate proves
that at least one pilot error must reach 4.234%, above the 3% gate. This does
not exclude changes to the equilibrium, induced operators or force/stall laws.

Separating the two parts of the earlier receiver-location diagnostic identifies
a useful clue, but no complete correction. Moving only the rotational-velocity
sample at the control point gives **38/48** pilot pitch-rate matches, versus
**24/48** for the retained calculation. All eight `CLq` and `Cmq` values then
pass. It also loses one previously passing `Clq`, and seven `CXq` values still
fail. Neither component satisfies the predeclared no-loss extension gate.

This is a decomposition of the
[previous both-receivers experiment](isae-sa6-frozen-derivatives-20261031.md),
not a new production option or an authenticated ASWING convention. The guide
describes freezing vortex-lattice influence matrices; it does not establish
the mixed sampling rule tested here. Production retains its existing equations,
and the qualified full state comparison remains **2,780/3,168**, with **282/528**
pitch-rate matches. Registered default counts are unchanged.

| Eight-state pilot | All state checks | Pitch-rate checks | Gains / losses versus retained calculation |
|---|---:|---:|---:|
| Retained frozen-influence calculation | 253/288 | 24/48 | — |
| Current-wind control-point sample only | 267/288 | 38/48 | 15 / 1 |
| Current-wind force-point sample only | 239/288 | 10/48 | 0 / 14 |
| Both current-wind samples, prior result | 247/288 | 18/48 | 6 / 12 |

The pilot uses the four paired aileron-chord models at 4° and 44° control,
on the existing 128-interval request. The base circulation, frozen influence
operators, strength 20, section properties and all other settings are retained.
At zero base rates, moving the rotational-velocity sample changes the rate
forcing without changing the static solution. No source location, induced
operator, physical load arm, section normal or production force law is moved.
The straight-wing geometry makes the non-pitch columns unchanged in this
particular experiment; the verifier checks that explicitly.

For each component, the changed velocity is
`delta V = (r_current_wind - r_frozen) cross Omega`. The locations come directly
from steady equations 155–157, without adjustable offsets. The residual and
wrench changes follow equations 64, 67, 70, 72 and 203–204. The saved circulation
Jacobian supplies the response to that new forcing. The two independently
computed coefficient corrections sum to the prior both-receivers correction
within **1.95e−16**, confirming the decomposition.

| Control-point-only pitch channel | Matches | Median / maximum failed error |
|---|---:|---:|
| CXq | 1/8 | 28.29% / 96.56% |
| CYq | 8/8 | — |
| CLq | 8/8 | — |
| Clq | 7/8 | 3.779% / 3.779% |
| Cmq | 8/8 | — |
| Cnq | 6/8 | 4.683% / 5.337% |

The lost check is `Clq` for the 35%-chord model at 44°: native −0.21315,
retained −0.21032656, control-point-only −0.22120391. The last value is 3.779%
from the reference. No mesh, input or tolerance is adjusted to recover it.

At the 15%-chord/4° point, the same diagnostic changes `CLq` from 2.09194628
to **1.99867291**, versus native 1.99878; `Cmq` changes from −0.48547065 to
**−0.46180813**, versus native −0.46228. However, `CXq` becomes −0.00033363
versus native −0.00969. Recovering the vertical-force and pitch-moment response
alone does not recover the complete aerodynamic wrench.

A separate source check compares the exact same effective control input:
15%-chord at 36° and 20%-chord at 32°, using their literal gains 0.040 and
0.045. After whitespace normalization, those models differ only in that gain.
All **48** archived scalar pairs agree within their combined printed rounding
intervals, with F1 derivatives divided by the corresponding gain. All six
pitch-rate values agree at printed precision. This supplies no evidence of
a simple file-pairing inconsistency at that shared input; it does not establish
the producing runtime settings at other states.

The matrix replay finishes in **0.39 seconds** after imports and input checks,
in one process with one BLAS thread. Both extension gates fail, so the other
80 retained states are not replayed. No aircraft solve or production field
evaluation runs, and neither diagnostic branch is promoted into acceptance.

An independent standard-library verifier reconstructs the straight-wing
velocity kernels, checks the complete linear residual, and evaluates centered
perturbations at normalized pitch-rate steps `2e-5` and `1e-5`. Circulation is
prescribed along the computed first-order response; these are equation checks,
not additional converged nonlinear operating points. Across 32 stencils and
192 coefficient comparisons, the maximum derivative discrepancy is **8.75e−10**,
well inside the existing derivative-check gate. The exact linear residual is
at most **2.23e−15**; the finite-stencil residual derivative, which includes
truncation error, is at most **1.86e−7**.

The verifier also checks all 1,152 baseline/variant acceptance decisions using
the native tokens and exact decimal arithmetic, both failed extension gates,
source/result hashes and all 42 unchanged registered rows. These calculations
confirm the diagnostic result; they do not validate the mixed receiver rule
as the documented physical model.

The remaining question is how the archived producer treated rotational
velocity in its tangency and force calculations when influences were frozen.
The partial matches narrow that investigation, but do not justify dropping
force terms, fitting a receiver offset, or changing the production equations.
The [complete qualified static roll/yaw table comparison](isae-sa6-span-native-20261101.md)
remains separate and unchanged at 616/616.

Evidence: [declared plan](../../artifacts/isae/sa6-rate-receiver-split-20261101/plan.json),
[matrix replay](../../artifacts/isae/sa6-rate-receiver-split-20261101/analysis.json),
[independent verification and source-pair checks](../../artifacts/isae/sa6-rate-receiver-split-20261101/verification.json),
[producer](../../artifacts/isae/sa6-rate-receiver-split-20261101/run.py),
[scalar verifier](../../artifacts/isae/sa6-rate-receiver-split-20261101/verify.py).
