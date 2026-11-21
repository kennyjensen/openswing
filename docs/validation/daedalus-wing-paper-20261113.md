# Daedalus: comparison with Drela's wing-load paper

The paper provides a useful independent check of the **steady loaded wing**.
The current wing shape closely follows its Figure 8, with broadly similar
section-lift and bending-moment distributions. This does not yet validate the
later full-aircraft rudder Bode response. No production parameter was changed.

![Current wing over Figure 8 and extracted deflection profile](../../artifacts/daedalus-wing-paper-20261113/paper-comparison-v2/paper-comparison.png)

## Reference and version

Mark Drela, *Method for Simultaneous Wing Aerodynamic and Structural Load
Prediction*, AIAA-89-2200 (1989), is already retained as a
[local PDF](../../reference/st4-node-placement-20261109/drela-1989-wing-loads.pdf)
with a [checksummed source record](isae-st4-node-placement-sources-20261109.json).
The journal version appeared in *Journal of Aircraft* 27(8), 1990. This review
uses the retained conference version, PDF pages 3–4 and 8–9, printed pages
324–325 and 329–330. The official manual identifies it with ASWING 3.x;
the later steady/unsteady descriptions remain the implementation references.

Section 5.2 specifies **22 ft/s, 240 lb**, 51 points per wing half and 11
circulation harmonics. Figure 8 contains the Daedalus steady loads and shape;
Figure 9's strain-gauge comparison concerns **Light Eagle**, a different aircraft.
The formulation is structurally static apart from rigid-body accelerations,
so it does not supply the later aircraft's harmonic phase response.

## Current model comparison

The accepted source-equation/SEGSPL case uses the literal public `dae.asw`,
**21.9816273 ft/s** (6.7 m/s), and **233.3019332 lb**. The latter is integrated
from every distributed and point-mass record and independently checked against
the net gravity force. The paper's gross weight is 2.87% greater. Its original
input deck and complete property tables are unavailable; Figure 7 supplies
graphical property information rather than an identical modern input file.

The overlay uses the paper's visible load-plot axes, without fitting any
deflection scale or physical parameter. The front-view sketch is assumed to
share their horizontal scale and to have equal vertical scale; its root sets
only the vertical origin. Under that rendering assumption:

| Diagnostic | Current result |
| --- | ---: |
| Wing-tip height above loaded root | 8.0485 / 8.0532 ft |
| Extracted wing-profile RMS image difference | 0.884 px |
| Maximum image difference | 1.963 px |
| Maximum section CL | 1.29879 |
| Maximum element-center bending moment magnitude | 381.998 lb ft |

The shape agreement supports the static deformation mechanism. It is **not a
sub-percent physical validation**: the scan, chord outline, assumed drawing
scale, differing inputs and finite mesh limit that interpretation. Bending
moments in the overlay are element-center values; endpoint load jumps and
their peaks are not reconstructed. The machine field `current_root_Mx_lbft`
likewise means the two root-adjacent element values, not a root trace.

[Extracted state and mass audit](../../artifacts/daedalus-wing-paper-20261113/static-and-pages-v3/result.json)
and [pixel calibration and comparison](../../artifacts/daedalus-wing-paper-20261113/paper-comparison-v2/result.json)
retain the complete numbers.

## A concrete joint difference, tested conditionally

PDF page 4 describes the Daedalus wing mount as **pinned in roll**. The public
`dae.asw` wing/boom joint omits `KJtype`; the official manual's Joint section
explicitly makes that a **rigid** joint. OpenSwing follows that file correctly.
This is a historical setup distinction, not evidence of a parser error.

A small full-matrix diagnostic replaces only the incremental roll compatibility
row with zero incremental joint roll couple. It holds the accepted equilibrium
and its **−0.025576 lb ft** static couple as a constant preload. All other rows,
mass terms, input/output maps and physical parameters are unchanged. This is
not a retrimmed hinged-aircraft solution.

| Frequency, Hz | Literal rigid: yaw | Incremental roll release: yaw |
| --- | ---: | ---: |
| 0.1 | 0.121763 | 0.121761 |
| 0.2 | 0.172164 | 0.171724 |
| 1.0 | 0.075499 | 0.084362 |
| 1.157378 | 0.074218 | 0.086946 |
| 1.5 | 0.094316 | 0.108451 |
| 2.0 | 0.124678 | 0.134411 |

Units are deg/s per native F3 unit. The Bode drawing's value at 1.157378 Hz is
0.033986, so this release **worsens** the discrepancy. The 12 direct full-state
solves satisfy the numerical gates; the released incremental couple is below
8.4e−14 lb ft/F3. These are diagnostics, not new native-reference passes.
[All four complex outputs and checks](../../artifacts/daedalus-wing-paper-20261113/roll-release/result.json)
are retained.

## Consequence for the investigation

Use Figure 8 as a steady-wing benchmark, with its input differences explicit.
It supports the modeled static bending and gives a better reference than
extrapolating a small-fuselage camera fit to the animated wing tip. A matched
240 lb reconstruction would need a disclosed mass distribution and root
constraint treatment; gross weight alone does not specify either.

The [load sensitivity study](daedalus-load-sensitivity-20261113.md) still points
to the distributed wing/fin aerodynamic response near the Bode dip. The paper
does not establish the operating point, settings or version of that later plot.
Continue checking those dynamic terms against the later source equations and
controlled numerical resolution, preserving this independent steady evidence.

The subsequent [native AVL rate comparison](daedalus-loaded-avl-20261113.md)
checks the actual loaded wing and fin as isolated rigid surfaces. Wing vertical
force agrees within 0.556%; lateral moment derivatives differ by up to 8.423%
for the wing and 5.213% for the fin, with receiver and force conventions kept
explicit. This adds an independent aerodynamic diagnostic without validating
the full dynamic response or changing the paper comparison above.

Reproduce with [the bounded driver](../../scripts/check_daedalus_wing_paper.py),
one fresh tag at a time. All jobs use one BLAS thread, 512 MiB address space,
15 CPU seconds and 25 wall seconds; every child was reaped. The initial
`static-and-pages` attempt failed JSON serialization. The `v2` extraction and
first `paper-comparison` also contain an incorrect **225.8069 lb** summary:
the new diagnostic zipped multiple mass records to one record per beam. They
are retained as superseded evidence. `v3` fixes the accounting and checks it
against gravity; neither the solver's mass nor any solved response changed.
ISAE completion fractions and progress history are unchanged.
