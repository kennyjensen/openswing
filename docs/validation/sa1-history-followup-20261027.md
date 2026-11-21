# SA-1: accompanying papers and recovered source history

SA-1 remains **19/154 registered archived-output checks passing**, with all 22
baseline jobs completed. The accompanying papers supply useful settings and
equations, but several statements differ from the retained model and drivers.
This follow-up separates those sources and records the additional diagnostics.
The original native ASWING table remains the comparison target.

## What the papers establish

The [Part 1 aerodynamics report, pp22–26](https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation/blob/f62943df20e9e4d7d9f50e070477b22426b5f865/5%20-%20Technical%20Reports/Experimental_validation_of_ASWING_Part_1_Aerodynamics_V4.pdf)
describes the rigid NACA0012 straight-wing case and labels SA-1 fully repeatable.
Its p25 setup is not identical to the retained native-run inputs:

| Setting | Part 1, p25 | Retained SA-1 model or driver |
|---|---|---|
| Section lift slope | 6.26 | 6.2832 |
| Section lift limits | −1.5, +1.5 | −1.2, +1.2 |
| Skin-friction coefficient | 0 | 0.00352562 |
| Pressure-drag coefficient | 0.01 | 0.00771413 |
| Discretization | 40 nodes for circulation distribution | `NODE I200`; no explicit Fourier count |

The counts in the final row describe different quantities; the report does not
provide the missing mapping. Its numerical-method section distinguishes
structural nodes `I` from Fourier coefficients `K`. `OPER K I100` in the driver
sets the Newton iteration limit, not the circulation basis size. The saved model,
driver and output table retain their original values; report prose is not used to
replace them.

Part 1 p18 Eq18 defines continuous Fourier circulation. Pages19–20 describe
`I−1` horseshoes and circulation collocation, but do not uniquely specify the
load integration used by the archived executable. The printed p19 expression
for an “averaged position” uses half a coordinate difference, rather than an
average position; visual inspection confirms this is in the PDF. It is not a
sound basis for changing the implemented sample location.

Parts 2–4 were also checked. Part 3 p25 describes structural cosine clustering
without a node-generation formula. Its 40-node recommendation concerns the
tested structural cases. Part 4 p10 uses 40 structural nodes and 40 circulation
variables for AE-2, while p23 uses 40 structural nodes with pointwise circulation
for a limit-cycle case. These are case-specific settings, not shared SA-1
defaults. No SA-1 `.set` file or complete node/circulation listing was recovered
from these reports.

The cited [Drela 1999 paper](https://web.mit.edu/drela/Public/web/aswing/asw_aiaa.pdf)
was retrieved and reviewed as well. Printed p4 Eqs6–9 give conservative box
balances with arithmetic endpoint averages; p5 Eq14 gives Fourier and pointwise
circulation alternatives; p9 gives the Fourier-weighted circulation residual.
It does not supply the missing NODE-generation procedure or uniquely resolve
aerodynamic load transfer. Its p10 recommendations for stall factor 40 and
transition width .05 agree with the later descriptions. The ISAE bibliography
cites the 5.81/5.86 descriptions; the available MIT steady/unsteady descriptions
are 5.99. These versions must not be treated as the exact historical executable.

## What the repository history adds

The [source-history audit](../../.reference/sa1-public-history-20261027/report.md)
recovers the original files under their earlier `Single_Wing/CASE2` names. The
current SA-1 model and native polar are already byte-identical in the earliest
public data commit. The original driver differs only in model/output names.
There is no evidence here that the native table predates a later change to the
model bytes. Commit dates do not establish computation dates or executable
settings.

Earlier drivers also retain a separate `CASE10` run with `NODE I40`, angles
0–10 degrees and lift slope 6.28. Its model differs from original SA-1 only in
that slope. This is a distinct historical comparison, not grounds to replace the
registered SA-1 inputs.

The [recovered postprocessor](sa1-postprocessor-provenance-20261027.md) explains
the saved **ASWING-ISAE** figures. Its lift curve combines CSV comparison values
with two native endpoints. Its drag curve adds an external XFOIL polynomial
correction to native ASWING drag. Replaying the author's script expressions
reproduces the saved lift coordinates exactly and the drag coordinates within
1.57e−15. These figures are derived data, not a second native executable run.
The original ASWING coefficient table remains independent of that postprocessing.

The [recovered convergence scripts](../../.reference/sa1-public-history-20261027/scn-study/report.md)
vary `NODE I` through 8, 14, 26, 50 and 98,
while naming their distributions N=6, 12, 24, 48 and 96. They do not explicitly
set Fourier K. The retained distributions have N+2 rows, a duplicate root station
and N nonzero intervals. Their four-decimal coordinates establish that these
printed station sets are not plain full-span cosine grids. The scripts do not
set or echo display increment D, which controls whether actual computational
nodes are listed. These records do not uniquely determine the generation
algorithm or the SA-1 grid. The retained rectangular
model's dimensions conflict with its output headers, so that model/output pair
cannot establish an exact reconstruction.

The author's convergence postprocessor also reproduces Figure 9's slope and
R² annotations from successive-grid changes in hardcoded rectangular CL arrays.
This differs from the report's description of error against an elliptical-wing
Prandtl solution. That figure cannot establish an exact Fourier resolution or
an error-to-theory tolerance for SA-1.

A separate output-format detail is explicit in the
[ASWING manual](../../.reference/aswing_doc.txt), lines 2546–2599: coordinates and
state variables are node values; derived `cl` and `f_aero` values are interval
midpoint quantities printed on the preceding node line. The final row contains
dummy zeros. Thus a nonzero `cl` beside a tip coordinate is not a physical
endpoint value. This establishes how to associate the saved columns with
intervals, but does not alone establish the structural load-transfer rule.

The [saved-load check](sa1-scn-load-audit-20261027/report.md) confirms that all
seven headered distributions' root force jumps match their reported total
vertical force within printed precision. Multiplying displayed `f_aero` by
displayed parameter increments does not reproduce the local force balances.
Those columns omit the full force vector, local bases and exact physical span
metric; the output interpolation setting is also missing. The check resolves
the apparent tip-value asymmetry but does not identify a kernel correction.

## Additional numerical checks

The [startup-settings review](sa1-startup-settings-20261027.md) corrects an earlier
attribution: `fast = T` appears in a guide menu example, not an authenticated
startup-default statement. Because the driver toggles F once, both resulting
states had to remain possible. A predeclared frozen-influence diagnostic tested
three original incidences on both existing grids:

| Incidence | Frozen-influence CL error, 400 intervals | Frozen-influence CDi error |
|---:|---:|---:|
| 0.029369° | +0.05787% | +0.000163% |
| 1.9971° | −0.03033% | −0.12115% |
| 18.091° | −6.63044% | −9.75311% |

All six solves completed. They match 3/42 diagnostic outputs, compared with 7/42
in the same current-influence baseline subset. Freezing does not remove the
low-angle slope bias and increases the stalled discrepancy. An
[independent scalar replay](sa1-frozen-influence-20261027/report.md) reproduces the
six saved states to roundoff. No switch setting was selected by closeness.

The [historical CASE10 diagnostic](sa1-historical-case10-oracle-20261027/report.md)
completed all 22 states on declared 40/80-interval reconstructions. Its attached
circulation-lift bias is approximately +0.302%, versus +0.058% for original
SA-1. Induced drag is much closer. This supports investigating historical
discretization and load integration, but does not identify an error law or a
correction factor. An independent replay matches all saved states to roundoff.

The historical diagnostic has 12/154 matches, 140 finite failures and two
undefined efficiencies under the retained-scalar comparison. Two zero-incidence
CD values lie on a printed rounding boundary; the independent floating-point
summation gives 10 matches solely because of those last bits. Both outcomes are
recorded. No tolerance was expanded. Twenty nonzero records were reused after a
diagnostic writer failed to serialize the two undefined efficiencies; only those
two rows were rerun, for 24 physical calls and 22 final records.

Neither diagnostic is added to the registered SA-1 denominator. The 123 recorded
production kernel modules, original models and acceptance gates remain unchanged.
The mathematical review and its 145 passing focused tests remain applicable;
these additional investigations do not establish ASWING equivalence.

## Remaining question

The papers support the implemented steady lifting-line equations, but their
setup discrepancies prevent treating their prose as an exact reconstruction of
the saved run. The larger bias in the recovered lower-resolution run makes
historical node placement, circulation sampling and force integration the most
useful next investigation. Changes must follow a demonstrated discrete rule,
with the original native outputs retained as tests.
