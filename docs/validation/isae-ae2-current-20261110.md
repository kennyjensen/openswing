# AE-2 current-code comparison

This is the initial six-state checkpoint. The [subsequent branch investigation](isae-ae2-branch-current-20261110.md)
extends the current count to 34/2,200 and retains six failures at 17 m/s.

Observed 2026-11-10 UTC. AE-2 is the current focus; AE-1 remains open and
deferred. The first six fresh states pass **24/24 native sensor comparisons
at 5%**, with **108/108 physical checks** and all six deflection/twist mesh
checks passing. No production solver equation or physical input changed.

## Current results

All three original layups are compared at commanded beta 5° and IAS 10 m/s,
using nominal 80 and 160 cosine meshes. Each state reports signed Earth-Y
position, heading, sensor speed and local flow angle. Maximum absolute relative
error over the two meshes:

| Original layup | Deflection | Heading / twist | Sensor speed | Sensor flow angle |
|---|---:|---:|---:|---:|
| Uncoupled `[03_90]` | 0.437% | 0.341% | 0.0243% | 2.192% |
| Negative coupling `[m15_02]_S` | 0.535% | 0.514% | 0.0388% | 1.989% |
| Positive coupling `[p15_02]_S` | 0.295% | 0.373% | 0.0203% | 2.264% |

Median error over all 24 comparisons is 0.404%; maximum error is 2.264%.
The maximum change between meshes is 0.03861%, below the original 1% mesh
gate. Cold solve times are 1.07–2.18 seconds. All six processes were reaped,
with no failed physical attempts or retries. The run used one worker and one
BLAS thread, 512 MiB address-space and 15 CPU-second limits, and a 25-second
worker deadline. Process startup, source inventory and report generation are
additional to the solve times.

Fresh residual, force/moment balance, root clamp, restored-state agreement,
sensor flow reconstruction and integrated aerodynamic loads pass the existing
checks. None of the 24 outputs matches half a printed unit; the unchanged 5%
allowance is the basis of these native passes.

## Scope and source evidence

The current primary scope retains all **2,200** registered scalar slots:
three layups, twelve sweeps, four sensor fields, both meshes, and all initial
NaNs. The new current-code count is **24/2,200**, comprising 24 passes,
2,080 unrun finite comparisons and 96 unavailable native values. The historical
strict baseline of 2/2,200 and the historical positive-branch sample of 24/24
remain separate; neither is pooled into the new current count. This is a fresh
replay checkpoint, not a claim that the remaining values fail or the whole
family is validated.

The checked primary source is Romain Jan, **Part IV**, §3.2, pp. 8–12,
Figure 3, with Table 10 supplying the material description. Its PDF and text
match the [authoritative catalog](aswing-authoritative-references.md).
The report attributes Figure 3 to ASWING 5.96. Native `.txt` outputs and their
literal model/driver pairings remain the targets; experimental curves are not
acceptance references.

The report specifies cosine clustering, a solid symmetry wall, section lift
slope 5.73/rad and limits ±1.1. Original model bytes, stiffness coupling and
offsets are unchanged. The report describes two edge sensors, while the
archived model and output driver use a midchord sensor: the raw-output
comparison retains the latter, rather than silently substituting the report's
measurement geometry. The 80/160 requests produce 81/161 intervals; they check
refinement and do not recover the report's historical 40-node array.

The existing declared reconstruction remains frozen influences, pointwise
circulation, PG Mach zero, density 1.23 kg/m³, IAS assigned to TAS, literal
gravity and the driver-commanded wall. Historical K/F, atmosphere, exact node
placement and initialization remain unknown. Local section Mach is distinct
from the PG setting. No parameter was fitted to improve agreement.

## Runner correction and next work

AE-2 planning had broken after reference files moved to the visible
`reference/` directory: historical `.reference/` pin paths were compared
literally with resolved paths. The adapter now verifies original byte counts
and SHA-256 hashes, resolves equivalent paths consistently, and emits canonical
pins. Archived catalogs are unchanged; modified source bytes are still rejected.
All **25 adapter tests pass**, including an alias/changed-byte regression.
The independent saved-data assessment rechecks raw evidence, current source
pins, native tokens and acceptance, and binds the six jobs to the complete
550-job scope without any additional physics calls.

Next, extend the current replay across the remaining speeds and incidences in
small serial jobs. Prioritize the negatively coupled wing near 17 m/s: earlier
work found multiple equilibria and a positive branch matching ASWING at 18–20
m/s, but did not reproduce its 17 m/s point. Retain cold-start and continuation
results separately, and do not select a branch solely because it matches the
reference. Branch stability, original initialization and supplemental span
exports remain open. Browser/build tests remain held.

[Current run](../../artifacts/isae/ae2-current-pilot-20261110/report.json) ·
[Independent assessment](../../artifacts/isae/ae2-current-pilot-20261110/assessment.json) ·
[Earlier branch investigation](isae-ae2-continuation-20261105.md) ·
[AE-1 final refinement checkpoint](isae-ae1-refinement-current-20261110.md)
