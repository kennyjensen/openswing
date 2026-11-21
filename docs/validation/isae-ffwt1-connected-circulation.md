# FFWT-1 connected circulation reference

A single circulation series across the connected main wing and tips removes
the extreme total velocities seen in the preceding split-beam Fourier study
for the cases tested here. Independent aerodynamic replay confirms all twelve
connected-series results. Their total-force component differences from
matched pointwise results decrease as modes increase, but local equation
defects remain near the hinges.
This is useful evidence for a connected representation, not a completed
physical validation or proof of original ASWING's coordinate grouping.

Production source, defaults and the browser release are unchanged. ISAE
coverage remains **17 partial / 24 pending / 0 fully validated**.

## What changed in this reference

The same rigid reconstructed Flare30 model is held at the previously computed
11.923603° incidence and tip angles. Speed is 22 m/s; section properties,
stall law, body attitude and frozen jig influences retain the preceding
study's assumptions. No outer hinge equilibrium, sensor or root-section
comparison is computed in this increment.

The three serial beam pieces span material coordinate −0.5 to +0.5 m in
their straight jig configuration. A single sine series uses that whole span,
with zeros only at the outer tips and continuous circulation at the internal
hinges. This is an explicitly selected approximation space. Physical beam
index alone does not establish this grouping for a general aircraft.

The aerodynamic sample locations also change. Existing structural interval
endpoints and lengths are retained, while each sample moves to the midpoint
in the **global** Glauert angle. Its position, frame, section properties and
frozen influence coefficients are rebuilt consistently. This follows the
midpoint construction in the documented equations 150–154 on the chosen
intervals. Original ASWING's grouping of these particular beams is still
unproven; see the source assessment in the evidence archive.

Each mesh therefore has a new pointwise control on the same resampled
geometry. Comparisons with the preceding study change both the basis and
sample locations; they do not isolate the basis alone.

## Fifteen declared solve attempts

Three meshes request main/tip interval counts 100/40/40, 200/80/80 and
400/160/160, realizing 184, 364 and 724 total panels. Each has one pointwise
solve and four connected series with **8, 16, 32 and 64 total unknowns**.
All cases start from their own linear circulation estimate. There is no
parameter fitting or exchange of solved circulation seeds between cases.

All fifteen native attempts return states meeting their declared 1e−12
normalized residual requirements. Pointwise states require every local
equation to meet that bound. Truncated series require the projected equations
to meet it; their local defects are reported separately. The native solver's
ordinary 1e−8 convergence flag is not the study's acceptance test.

The native loop takes 30.165 seconds, including mesh and basis construction,
geometry exports and result recording, but excluding imports and initial
source checks. It is not a browser or coupled-equilibrium benchmark.

On the finest mesh:

| Representation | Lift, N | Maximum local residual | Weighted local residual L2 | Maximum normal Mach |
| --- | ---: | ---: | ---: | ---: |
| Connected, 8 modes | 17.633375 | 0.112222 | 0.029370 | 0.064803 |
| Connected, 16 modes | 17.716007 | 0.121152 | 0.020022 | 0.064892 |
| Connected, 32 modes | 17.717964 | 0.136202 | 0.014552 | 0.065006 |
| Connected, 64 modes | 17.715167 | 0.151340 | 0.010611 | 0.065081 |
| Matched pointwise, native result | 17.711849 | 3.57e−13 | 8.32e−15 | 0.065024 |

Residuals are normalized by freestream speed; L2 uses the global-angle
quadrature weights. The fine and finest pointwise controls fail strict
independent replay requirements, as detailed below, so comparisons to those
controls remain qualified.

The weighted circulation difference from the finest native pointwise state
decreases from 0.030914 to 0.001398 m²/s between 8 and 64 modes. The largest
total-force component difference falls from 0.073311 to 0.009230 N. However,
the maximum local residual **increases** with mode count. Its worst sample
lies immediately beside an internal hinge. Neither close lift nor a small
projected residual establishes uniform local convergence.

Mesh refinement at fixed mode count also has a measurable effect. For 16
modes, lift is 17.709764, 17.714132 and 17.716007 N on the three meshes.
Matched pointwise lift is 17.704379, 17.709228 and 17.711849 N. These sequences
do not establish a continuum limit. The earlier local-midpoint pointwise
coarse/fine values, 17.714542 and 17.714532 N, are a separate sampling control.

## Independent checks and retained failures

An independent implementation passes 105 operator controls, including global
interval coverage, positive weights, seam continuity, permutation and encoder
checks. The worst weighted sampling condition number is approximately 1.022;
the tested basis is not near its rank-rejection threshold.

Independent geometry, influence and section-law calculations replay all
fifteen saved circulation states without native solver imports or new roots.
All twelve connected cases and the coarse pointwise case meet the independent
declared gates and comparison bounds. The fine and finer pointwise cases
fail: their independent maximum normalized residuals are **2.50106e−12** and
**1.50556e−11**, respectively. Four of 357 arithmetic comparisons also fail,
all involving these residuals. No threshold is relaxed or state corrected.

All geometry, force and moment comparisons pass their separate bounds.
Maximum total-force disagreement is 4.00e−15 N; maximum local-velocity
disagreement is 1.69e−10 m/s. Such close load agreement does not waive an
equation requirement. This replay does not establish whether arithmetic,
rounded geometry or their combination causes the two residual discrepancies.
The selected-panel precision finding from the preceding study is not a
certificate for these new states.

A separate saved-data review passes 967 checks of the fifteen attempts,
thirty event records, operators, local/projected norms, seam values and
matched-reference differences. The initial superseded experiment plan and a
summary-file naming failure are retained; neither involved a discarded
scientific solve.

## Why the endpoint behavior improves

A saved-field decomposition independently checks six connected states using
the exact scalar reduction for their straight frozen vortex geometry. At the
first main-wing sample next to the port hinge, the 16-mode result has:

| Induced vertical velocity | Coarse, m/s | Fine, m/s | Finer, m/s |
| --- | ---: | ---: | ---: |
| Main wing contribution | −464.9952 | −1870.6230 | −7496.8149 |
| Adjacent tip contribution | +465.1106 | +1870.7360 | +7496.9259 |
| Total, including distant tip | +0.120169 | +0.117903 | +0.115831 |

The opposing contributions grow roughly fourfold with each refinement while
their small sum remains bounded over the tested meshes. The 64-mode totals
are 0.377469, 0.368138 and 0.360256 m/s. The decomposition passes 108 checks
and reproduces the saved velocity within 6.16e−12 m/s. This supports the
predicted cancellation mechanism and highlights the need for accurate
influence evaluation. It does not prove an asymptotic limit.

## Remaining work

The next numerical tasks are to resolve the two independent pointwise
residual discrepancies and establish local-flow convergence near the hinge
frame and section-property changes. A practical connected representation
must also define grouping for general geometry and integrate consistently
with structural, tangent and dynamic calculations before production use.

The physical fixture, archived producing configuration, flexible-wing
response, updated-influence limitations and remaining ISAE case families
remain unfinished. There is no original ASWING executable available for a
direct reference run.

The [recorded summary](isae-ffwt1-connected-circulation.json),
[selected evidence archive](isae-ffwt1-connected-circulation-evidence.zip)
and [archive verification](isae-ffwt1-connected-circulation-evidence.json)
retain all outcomes and their scope. Archive verification checks recorded
bytes; it is not a new scientific run or browser build.
