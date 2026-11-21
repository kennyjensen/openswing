# SA-1: exporter interpretation and earlier primary sources

SA-1 remains **19/154 registered checks passing**, with all 22 baseline jobs
complete. The follow-up tests a specific ambiguity left by the
[printed-rounding analysis](sa1-printed-rounding-followup-20261027.md). It does not
establish a production solver correction.

## Settings recovered from the accompanying papers

All four ISAE reports were reviewed in the earlier
[paper and history audit](sa1-history-followup-20261027.md). Part 1, printed p25,
does give SA-1 setup information, but it conflicts with the retained native-run
inputs:

| Setting | Paper | Retained model or driver |
|---|---|---|
| Section lift slope | 6.26 | 6.2832 |
| Section lift limits | −1.5, +1.5 | −1.2, +1.2 |
| Skin-friction coefficient | 0 | 0.00352562 |
| Pressure-drag coefficient | 0.01 | 0.00771413 |
| Discretization description | 40 circulation nodes | `NODE I200`; Fourier count not explicitly set |

Structural node count and circulation basis size are separate quantities. The
paper does not provide their missing mapping for the archived run. Neither the
reports nor the recovered driver supplies its exact node coordinates or saved
settings. These differences prevent replacing the archived inputs with the
paper's values and calling that a reproduction of the same ASWING run.

## Separating output sampling from force sampling

Drela's theory specifies a Glauert-angle midpoint for the aerodynamic force
location. The guide describes native `cl` output as an interval-derived value
between nodes without explicitly naming its recovery location. The new
[predeclared diagnostic](../../artifacts/isae/sa1-arithmetic-export-20261027/protocol.json)
therefore changes only the assumed native coefficient location to the arithmetic
span midpoint. The documented force location remains fixed.

Two distinct influence matrices are retained: the arithmetic-point matrix enters
the inverse `cl` relation, while the Glauert-point matrix supplies velocities for
circulation and profile forces. The reconstruction assumes piecewise-constant
circulation per interval, as in Eq153. A native exporter that separately samples
a continuous Fourier circulation would require additional information and is
not covered by this hypothesis.

Both current and frozen zero-angle conventions were kept, without choosing one
by agreement. Both numerical inversions and all 42 continuation stages completed.
Two subsequent interval enclosures propagated the specified printed coordinate,
`cl`, incidence, force and dynamic-pressure bounds. Their global contraction
upper bound is 0.154786, below one, giving a unique inverse fixed point for each
permitted parameter set under the declared geometry.

| Assumed native `cl` location | Current-influence lower-direction margin | Frozen-influence lower-direction margin |
|---|---:|---:|
| Glauert midpoint, preceding study | [−0.0146005, −0.00170277] N | [−0.00145969, +0.0112474] N |
| Arithmetic midpoint, this study | [−0.0144854, −0.00159498] N | [−0.00199271, +0.0107276] N |

A compatible nonnegative profile-force residual requires a nonnegative margin.
Thus **the arithmetic-midpoint interpretation also fails to resolve the
current-influence diagnostic discrepancy**, even after the specified print
rounding. The frozen bounds are inconclusive; crossing zero does not prove a
compatible physical solution. Neither comparison identifies the archived F
setting, and neither is an additional registered acceptance check.

The [independent scalar replay](../../artifacts/isae/sa1-arithmetic-export-20261027/root-replay.json)
recomputes both operators from the original coordinates, using an algebraic
radical expression for the force midpoint. It reproduces forces within
1.78e-15 N and checks all 42 saved nominal stages. It also verifies all 60 interval
iterations and uses a second exact summation identity for the force bound. That
identity gives a current-influence upper margin of −0.001594975 N. The interval
checker shares the previously reviewed directed-decimal arithmetic primitives.

Both circulation-integral enclosures overlap the independent bounds from native
span efficiency and induced drag. This is a consistency condition, not strict
parity or evidence that all native outputs can be satisfied simultaneously.

The local chord of 0.2 m, straight untwisted geometry, zero spanwise flow and
zero PG Mach remain conditions of these reconstructions. The source for the
chord is the author's postprocessor, not an authenticated producing model. The
profile-direction test also assumes that the entire noncirculation force is
nonnegative profile drag at the same force samples. Unsupported geometry,
exporter or integration assumptions can therefore still invalidate that
interpretation. No coefficient, weight or input setting has been fitted.

## Earlier primary documents

The [archive search](../../artifacts/isae/sa1-arithmetic-export-20261027/older-primary-sources/report.md)
recovered three older MIT documents, identified by their internal version text:

| Document | Internal version/date | Archive capture |
|---|---|---|
| Steady theory | 5.60, July 2005 | March 2007 |
| Unsteady theory | 5.64, September 2006 | March 2007 |
| User guide | 5.82, September 2008 | October 2011 |

Their bytes are pinned by SHA256 and match the Internet Archive CDX payload
digests. The older steady theory already contains the same Glauert sampling,
bound-vortex force location, and structural endpoint-average notation. The
guide's entire discrete-variable-location section is text-identical to the
retained 5.97 guide after trimming outer whitespace. It does not resolve
arithmetic versus Glauert recovery of native `cl`.

The exact 5.81/5.86 theory revisions cited by ISAE were not recovered. One legacy
host query timed out, so the bounded search does not establish their absence.
The inspected release notes also do not state a steady sampling change between
5.96 and 5.99; that silence does not prove executable equivalence. These older
sources confirm that the relevant wording predates 5.99, without identifying a
replacement integration formula.

## Historical model evidence

The [historical model audit](../../artifacts/isae/sa1-arithmetic-export-20261027/historical-models/report.md)
recovered all 15 `Single_Wing` models in the earliest inspected public data
commit. Each file matches its recorded Git blob hash. The archived `ellip.asw`
has reference area and chord 0.154606, reference span 1, mirrored tips at
±0.5 m and root chord 0.2 m. Its references round to the values in the auxiliary
rect-labelled convergence outputs. However, its chord tapers to zero. That is a
partial source match, not evidence for the constant-chord geometry assumed in
the inverse diagnostics or a verified association with those native outputs.

The `ellipN6` through `ellipN100` files contain explicit geometry/property
stations. Changing those files also changes their reference area and sampled
shape; their names do not identify computational NODE settings. None of the 15
models establishes the full constant-chord geometry/reference combination used
in the conditional diagnostic. The scripts still invoke `rectangular` for the
rectangular study and `CASEI` for the elliptical study. The available
`rectangular.asw` has incompatible dimensions and nonzero distributed mass.

These are auxiliary convergence-study sources, distinct from the registered
SA-1 model and polar. They leave the original producing geometry unbound and do
not justify substituting another model or changing the solver by matching
integrated forces.

The original SA-1 model, native table, acceptance gates and production solver
remain unchanged. This turn adds two nominal inverse reconstructions and two
interval-enclosure calculations, with no forward aerodynamic solves or ASWING
executions. A demonstrated historical setup or discrete algorithm is still
needed before a numerical correction is justified.
