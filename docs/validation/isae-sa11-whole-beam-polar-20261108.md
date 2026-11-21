# SA-11: whole-beam sampling agrees in formal lift and drag across 0–5°

2026-11-08 UTC. The earlier two-angle result persists through **all 21 archived
rows from 0° to 5°, at 0.25° increments**. With the documented whole-beam
receiver sampling, formal drag error is **+0.043% to +0.241%**, compared with
**+12.63% to +44.13%** using the native AVL receiver positions. Formal lift
error is **−0.730% to −0.587%**. Vortex endpoints are unchanged.

**Every production state still rejects at exactly two winglet-root receivers.**
Their local Mach numbers invalidate the section-moment correction. These are
force sums from rejected states, not accepted predictions or new passes.
SA-11 remains **163/9,184 at 5%**, retaining all original angles, configurations,
outputs and unavailable targets. This study does not cover the remaining
5.25–10° rows or establish the archived generating setup.

## Controlled comparison

The [authoritative reference index](aswing-authoritative-references.md) and its
checksummed catalog were consulted. Drela's steady description, **Eqs. 150–157,
pp. 31–33**, defines whole-beam Glauert-angle sampling. **Eqs. 64–74, pp. 15–17**,
govern the velocity, forces and local-Mach section moment. Jan Part I, **p. 35
and Appendix D**, supplies the SA-11 case discussion and geometry evidence.
The User Guide's **Joint block** describes a rigid pylon retaining the offset
between beam attachment points; it does not authorize snapping vortex origins
together.

Conditions remain those disclosed in the [two-angle study](isae-sa11-winglet-receivers-20261108.md):
the report-derived −4° upper-winglet twist, bundled Joint correction, original
section properties, 240 m/s, density 1.2256, global PG Mach `240/340.21`, frozen
influences, and 64 native endpoint intervals. The source ASW files and primary
comparison are unchanged. Report-derived twist and native mesh choices remain
explicit alternatives, not authenticated producing settings.

Both receiver variants use OpenSwing's equations. “Native receivers” means
the earlier diagnostic override to use AVL's sampling positions; it does not
mean a new native AVL solve. The whole-beam rule is already OpenSwing's default.
The [location audit](isae-sa11-root-moment-envelope-20261108.md) identifies the
material movement on the main wing. Winglet-root receiver positions remain
essentially fixed; their flow changes through the re-solved circulation.

The new plan adds 19 serial calls and reuses the previously verified 0°/1°
states. Each call retains its 15-second limit, one BLAS thread and the original
Mach guard. Four later chunks share imports across three sequential calls each;
they introduce no concurrent solver work. No native AVL reruns are needed.

## Results

Errors below are `100 × (formal value / archived value − 1)`.

| Alpha | CD error with native receivers | CD error with whole-beam receivers | Whole-beam CL error | Whole-beam maximum local Mach |
|---:|---:|---:|---:|---:|
| 0° | +12.634% | +0.043% | −0.730% | 1.22339 |
| 1° | +20.369% | +0.065% | −0.692% | 1.53418 |
| 2° | +27.793% | +0.091% | −0.661% | 1.85625 |
| 3° | +34.310% | +0.128% | −0.635% | 2.18430 |
| 4° | +39.738% | +0.178% | −0.610% | 2.51568 |
| 5° | +44.126% | +0.241% | −0.587% | 2.84888 |

All intermediate quarter-degree rows are retained in the
[analysis](../../artifacts/isae/sa11-whole-beam-polar-20261108/analysis.json).
The maximum normalized circulation residual is **6.73e−15**. The nearest
section remains **11.30 stall-transition widths** inside its lift limits;
the largest formal stall-drag coefficient is **2.01e−13**. This discrepancy
is therefore separate from the deferred stall-region work.

![SA-11 receiver comparison over 0–5 degrees](../../artifacts/isae/sa11-whole-beam-polar-20261108/whole-beam-polar.png)

[Standalone SVG](../../artifacts/isae/sa11-whole-beam-polar-20261108/whole-beam-polar.svg).
The chart uses the application palette and labels the force sums as rejected
diagnostics; the rendered figure was visually checked. The root Mach range
grows from 1.223 to 2.849 even as integrated
force agreement remains close.

The four crossed receiver/circulation replays at each angle retain the exact
symmetric decomposition from the two-angle study. It assigns **94.50–94.68%**
of the formal drag change to receiver sampling, including section-property
resampling and half the interaction. Crossed fields are not equilibria; this
accounting identity does not justify keeping circulation fixed in a solve.

## Verification and remaining question

An independent checker reads the literal original 82-column output table,
reconstructs dimensional force sums and body-to-wind projections, and recomputes
local normal Mach with scalar arithmetic. Maximum coefficient differences are
**1.12e−16 for CL** and **1.05e−17 for CD**; local Mach agrees within
**4.45e−16**. All 21 frozen geometries are identical. Every saved rejection
identifies the same two root strips on beams 2 and 3. No complete moment or
accepted load record is generated.

The checker verifies **154 source pins**, all case artifacts, four serial-chunk
receipts, and the original table's SHA-256 and Git blob identity against the
repository manifest. Its first attempt expected the table hash directly in the
current plan; that terminal bookkeeping failure is retained. The corrected
check follows the already-pinned earlier polar plan to the table checksum and
checks the repository manifest independently. Scientific data and tolerances
are unchanged, and no solve is repeated for this correction.

Compensated force reductions agree within **1.12e−16** and the symmetric
decomposition closes exactly at recorded precision. Replaying the original
velocity fields agrees within **6.56e−10 m/s**. The 19 new physical calls took
**2.601 seconds combined**, excluding imports, source checks and postprocessing.
All jobs terminated normally apart from the retained first checker attempt.

The drag improvement is no longer supported only by two selected angles. Keep
the published sampling and force laws; this broad agreement is a constraint on
the remaining junction-flow investigation. A physical explanation must still
resolve the root velocities and section moment, and reconcile the archived
setup. The [moment-envelope audit](isae-sa11-root-moment-envelope-20261108.md)
already shows why fitting the aggregate moment at 5% cannot determine that
local correction. No parameter adjustment or primary-pass promotion follows
from these rejected-state force sums.

The subsequent [wake-output audit](isae-sa11-whole-beam-wake-20261108.md)
also checks formal CDi and efficiency on all 21 fields: error magnitudes remain
within 1.537% and 2.984%, respectively. Its analytic source decomposition
confirms that the offset root wake remains the local failure mechanism.
No full state becomes accepted and no primary pass is added.

- [Serial driver](../../scripts/verify-sa11-whole-beam-polar.py)
- [Bounded three-call runner](../../scripts/run-sa11-whole-beam-chunk.py)
- [Predeclared plan](../../artifacts/isae/sa11-whole-beam-polar-20261108/plan.json)
- [Independent checker](../../scripts/check-sa11-whole-beam-polar.py)
- [Verification receipt](../../artifacts/isae/sa11-whole-beam-polar-20261108/verification.json)
- [Retained first checker failure](../../artifacts/isae/sa11-whole-beam-polar-20261108/verification-attempt-1.json)
