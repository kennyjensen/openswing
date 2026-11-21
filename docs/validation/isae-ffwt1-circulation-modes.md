# FFWT-1 Fourier circulation diagnostic

This diagnostic finds severe mode sensitivity and large local flow defects in
the reconstructed Flare30 case. It does not reconcile the ISAE archive or
establish experimental validation. Production source, defaults and the app
release are unchanged. Coverage remains **17 partial / 24 pending / 0 fully
validated**; FFWT-1 remains pending.

## What was compared

Twelve native circulation solve attempts use the three previously computed pointwise
poses at 8.779176°, 11.923603° and 30.263890°. The physical model, level body,
22 m/s flow, stall parameters and frozen influence coefficients remain fixed.
Requested beam interval counts are 100/40/40; attachment insertion gives
102/41/41 actual panels. Four declared Fourier mode counts are tested per
logical main/starboard/port beam: 8/4/4, 16/8/8, 32/16/16 and 64/32/32.
The original ASWING mode settings are unknown. These choices are diagnostics,
not recovered defaults or settings selected to match archived lift.

Every call starts its own circulation solution. There are no outer hinge
solves. Eight returned circulation states receive an additional supplied-state
sensor evaluation, counted separately. The timed native pilot loop took
8.116 seconds, including postprocessing and recording but excluding imports
and provenance checks. This is not a browser benchmark or a coupled
equilibrium timing.

## Results at the fixed poses

The entries below are lift in newtons. They are **not new hinge equilibria**.

| Modes: main / starboard / port | 8.779176° | 11.923603° | 30.263890° |
| --- | ---: | ---: | ---: |
| Prior pointwise state | 14.415120 | 17.714542 | 19.902081 |
| 8 / 4 / 4 | 23.768148 | 29.245508 | 26.835086 |
| 16 / 8 / 8 | 41.805222 | 52.706854 | Rejected: local Mach 1.000214 |
| 32 / 16 / 16 | Rejected: local Mach 1.090262 | Rejected: local Mach 1.285557 | Rejected: local Mach 1.587177 |
| 64 / 32 / 32 | 10.925888 | 12.236489 | 8.658800 |

All eight returned states pass the unchanged **1e−12 projected residual**
requirement; the largest native value is 1.8402e−13. Their maximum local,
leakage-adjusted residuals are nevertheless **12.365–27.005**, normalized by
freestream speed. Their maximum hinge imbalances range from 0.000929 to
0.001908 N m. Neither local tangency nor hinge equilibrium is certified by
their projected convergence.

The other four attempts raise the existing local subsonic-validity guard.
Their exception records include locations and speeds, but no circulation or
residual arrays are returned. They must not be described as four measured
projected-residual failures. The raw report's broad
`COMPLETE_WITH_STRICT_FAILURES_RETAINED` label is preserved alongside this
more specific classification.

## Independent checks and load diagnosis

Independent operators pass 97 algebra checks. A separate aerodynamic
implementation replays all eight returned circulation vectors with 119
checks, reproducing the large local residuals and the small projected ones.
Maximum force-component disagreement is 1.42e−14 N. This checks the numerical
formulas under the shared assumptions; it does not validate the physical
predictions. A further 440 saved-data checks verify all twelve attempts,
24 event records, sensor replays and outcome accounting.

Sampling-basis condition numbers are only 1.00017–1.11229 in this ladder.
The large defects therefore cannot be attributed to a nearly singular
sampling basis. A separate full-basis arithmetic control using 102/41/41
modes reconstructs the prior pointwise circulation within 7.55e−15. That
control performs no circulation solve and makes no mesh-convergence claim.

Saved-load decomposition localizes extreme contributions near the internal
beam junctions. At 8.779176° with 8/4/4 modes, total lift is 23.768148 N,
including 14.480216 N from Kutta–Joukowski lift and 9.287933 N from the
remaining profile terms. The four panels nearest the two junctions contribute
8.629475 N of total lift, versus 0.009235 N in the prior pointwise state.
The squared local normal-velocity term amplifies these flow defects.

Drela's Eq. 70 explicitly uses the actual control-point normal velocity in
that force term. Replacing it with the section stall-leakage expression would
change the truncated Fourier formulation: those quantities are equal only
when the local Eq. 203 holds. Source review finds no justification for that
replacement. The sine sampling and weighted residual projection also agree
with Eqs. 63, 150 and 201. See the
[ASWING theory document](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf).

## What remains unresolved

This pilot does not establish the cause of the internal-junction behavior.
OpenSwing currently uses a separate sine series for each logical lifting
beam. Public documentation does not conclusively establish how original
ASWING assigned Fourier coordinates across joint-connected pieces sharing a
physical beam index. Shared physical identity alone cannot define a unique
serial span, as it also applies to branching configurations such as T-tails.

Mode count and structural quadrature require separate convergence studies;
the highest tested modes may be inadequately resolved. Further work must
establish local-flow and load convergence before interpreting new coupled
hinge equilibria. The physical fixture, archived producing configuration,
updated-influence limitations and dynamics also remain open. No original
ASWING executable is available for direct comparisons.

The [recorded-result index](isae-ffwt1-circulation-modes.json) retains the
outcomes and review evidence. The
[selected evidence archive](isae-ffwt1-circulation-modes-evidence.zip) and its
[verification receipt](isae-ffwt1-circulation-modes-evidence.json) preserve
the pilot, independent checks and rejected attempts. They do not claim a
rerun of historical science or a new app build.
