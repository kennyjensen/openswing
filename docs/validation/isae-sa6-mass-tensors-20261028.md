# SA-6 mass and inertia tensors — 2026-10-28

Final evidence verification completed 2026-10-29; artifact names retain the
comparison's starting date.

This comparison covers all 33 dimensional mass/inertia entries in each of the
44 original chordwise SA-6 `.fmat` files. The four aileron variants and eleven
control states are retained on both declared meshes: 88 jobs, 2,904 comparison
slots and 1,452 distinct archived cells. It is a separate scope from the static,
F1-control and state-derivative comparisons. SA-1 remains paused.

The [source catalog](../../artifacts/isae/sa6-mass-tensors-20261028/tensor-source-catalog.json)
retains each original token, position, unit label and exact half-print interval.
Tiny nonzero values remain required targets. No experimental target, fitted
parameter, replacement source, or relaxed tolerance is used.

The final saved-evidence comparison matches **1,760/2,904** checks. Of these,
1,320 are zero real-mass/inertia entries and 440 are nonzero apparent entries.
The latter cover `Mxx`, `Mxz`, `Mzz`, and `Iyy` at both reported references.
All 2,904 values are numerically valid; no complete 33-entry row matches.
The score includes both meshes and duplicate origin/centroid entries, rather
than 1,760 distinct physical quantities. All four variants retain the same
physical chord, twist, mass and density; different control states do not change
these undeformed mass tensors.

The largest relative discrepancies in the nonzero span-dependent inertia
terms are below. The identical origin/centroid reference produces the same
errors in both sets of entries. Small relative error does not satisfy the
original printed-precision tests.

| Apparent inertia term | Nominal 64 intervals | Nominal 128 intervals |
|---|---:|---:|
| Ixx | 0.12448% | 0.10909% |
| Ixz | 0.07475% | 0.05937% |
| Izz | 0.10482% | 0.08943% |

## Execution and validation

The [original batch](../../artifacts/isae/sa6-mass-tensors-20261028/batch/report.json)
finishes all 88 workers in 382.60 seconds and retains all 2,904 finite values.
Its supervisor accepts 87 jobs and rejects one because it required exact
equality when recomputing a positive-semidefinite diagnostic. That original
report remains intact: 2,871 values accepted and 1,740 printed matches.
The discrepant diagnostic values differ by approximately 2.8e-20; both are
below the unchanged 2e-12 numerical gate. This is a result-checker defect,
not a failure to calculate the tensor.

The [separate validation replay](../../artifacts/isae/sa6-mass-tensors-20261028/validation-replay/report.json)
accepts all 88 saved packets after a narrow checker correction. Only equality
of positive-semidefinite diagnostic values allows an absolute difference of
64 binary64 epsilons (1.42e-14). Both values must remain finite, nonnegative
and below the unchanged 2e-12 gate; names, operators, limits, pass flags,
predictions and original-reference comparisons remain bound. The original
arrays and result files are retained verbatim. This replay makes no new
geometry, tensor, aerodynamic or nonlinear evaluations.

The corrected mass suite passes 52 cases, including rejection of diagnostic
changes beyond roundoff even when they remain below the physical gate.
Together with the 485 existing focused cases, this gives 537 distinct final
adapter/runner/summary cases. The earlier 531-case receipt and the original
test-fixture failure remain preserved. The 129 production kernel modules and
their browser mirrors are unchanged; this increment adds comparison coverage
and fixes result validation, without changing a physical equation.

The [independent saved-data analysis](../../artifacts/isae/sa6-mass-tensors-20261028/analysis/summary.json)
passes all 22,410 checks. It reconstructs the original decimal comparisons,
physical tensor identities, kinetic energy and reference shifts from saved
arrays; authenticates original and corrected code separately; and verifies
all workers are reaped. Its maximum kinetic-energy discrepancy is 4.16e-17.
Two analyzer bookkeeping errors (an accounting-key mismatch and historical
versus current source-pin selection) were corrected without changing any
physical/reference check; the failed attempts are retained. The
[terminal receipt](../../artifacts/isae/sa6-mass-tensors-20261028/analysis/terminal-receipt.json)
records all attempts and the completed verification.

The independent tensor-helper tests cover rotated plates, positive real mass,
body transverse added mass, reference changes and corrupted saved evidence:
[23 tests pass](../../artifacts/isae/sa6-mass-tensors-20261028/math-verification.json).
The initial synthetic fixture accidentally activated the documented symmetry
reflection; its correction and failed initial log remain recorded. The helper
and production kernel did not change to accommodate that fixture.

## Physical interpretation

All four literal models have a physical section twist of 4 degrees, chord
0.254 m, span 1.524 m and density 1.2256 kg/m³. Physical twist determines the
section normal used for apparent mass; zero-lift angle and control deflection
do not replace it. Real mass and real inertia are zero. The physical real
center of mass consequently remains undefined (`None`). The archive's
centroid-labelled tensors are evaluated at its explicitly reported coordinate
(0, 0, 0), qualified as a reporting reference rather than a physical centroid.

The existing implementation assembles apparent mass from
`dm = rho*pi*c²*ds/4`, its physical section normal, the physical midchord arm,
and the local pitch inertia `rho*pi*c⁴*ds/128`. The reference-shift blocks are
checked against an independent kinetic-energy calculation. These are
dimensional body-axis values; no coefficient normalization, stability-axis
rotation or off-diagonal sign reversal is applied. See the
[primary-source audit](../../artifacts/isae/sa6-mass-tensors-20261028/source-audit.json).

The declared 64/128 cosine meshes include the original control-table
discontinuities at ±0.253746 m and the center station, producing 66/130
intervals. Saved endpoint positions are bound to that declared construction.
The current tensor calculation uses the existing Glauert-angle sample points;
these are not recovered historical ASWING `NODE` coordinates. Geometry and
mass assembly suffice: this route makes no aerodynamic calls, nonlinear
solves or circulation factorizations.

## Source finding and next correction

The [quadrature review](../../artifacts/isae/sa6-mass-tensors-20261028/quadrature-source-review.json)
finds that the documented structural box equations imply arithmetic midpoint
sampling for the apparent-inertia derivative of a constant straight section.
Endpoint apparent forces are affine under rigid angular acceleration; their
arithmetic average, with the moment arm in Eq. 266, yields that result.
The theta-averaging rule is explicitly local to the vortex-influence section.

This identifies a restricted mathematical difference in the current
implementation. It does not establish the sampling used by the historical
tensor exporter: Section 8.7 leaves its element position unspecified, and the
printed Eq. 267 is inconsistent with the immediately preceding Eq. 266.
General varying-section quadrature remains unresolved. The present comparison
preserves the existing kernel as a baseline. The next implementation step is
an independent endpoint-acceleration check followed by consistent treatment
of tensor and acceleration-load consumers; changing only the reported matrix
would leave those operators inconsistent.
The [consumer map](../../artifacts/isae/sa6-mass-tensors-20261028/consumer-map.json)
also identifies local-motion interpolation and its transpose load transfer
as part of that change. Preserving the total rigid wrench alone would not
preserve elastic virtual power. The separate source-quiescent endpoint rule
must retain its explicit meaning.

The [independent literal-model calculation](../../artifacts/isae/sa6-mass-tensors-20261028/analytic-witness.json)
constrains the span second moment from the original nonzero inertia entries
without selecting a mesh to fit them. Its common allowed interval is
0.2947020821–0.2947351742 m³, while the continuous-strip value is 0.294967152 m³.
Some tiny native cross terms also imply incompatible first moments for an
exactly planar strip. They remain recorded discrepancies.
The saved current meshes give second moments of 0.2950275429 and
0.2949822078 m³, respectively; both lie above that native interval. These
values are observations from the declared meshes, not a search for a mesh
that matches the targets.

## Running this scope

```sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  .venv/bin/python scripts/run-isae-suite.py \
  --adapters sa6 --cases SA-6 --comparison-scope sa6-mass-rigid \
  --job-pattern '*:rigid-mass' --workers 2 --timeout-seconds 60 \
  --output-dir /tmp/openswing-sa6-mass
```

Default SA-6 planning remains 91 jobs and 528 static slots. The mass opt-in
adds 88 jobs and 2,904 slots; enabling all three supplemental scopes totals
355 jobs and 7,128 slots. The filtered command above selects only mass jobs.
The four scopes keep separate scores. The three unpaired spanwise models and
historical producer, mesh and startup settings remain unresolved; none of
the 41 ISAE families is fully validated.
