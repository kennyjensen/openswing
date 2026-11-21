# AE-1: source-based node-spacing diagnostics

Observed 2026-11-10 UTC. Node placement changes the three vertical sensor outputs
by **11.08–73.97 µm** at the failing 5°/17 m/s operating point, enough to matter
against the current **31–35 µm** discrepancies. At the known 1 m/s control point,
the same changes move those outputs by at most **0.243 µm**. This supports a
load-dependent spatial-discretization explanation, rather than a constant
gravity-sag offset. It does not identify the original ASWING mesh or distinguish
aerodynamic discretization from structural response to the changed loading.

All eight new states pass **232 physical checks**. These are unscored alternative
grids: the primary AE-1 count remains **1,170/1,200**, including its six failures
and 24 unknown-start outputs. No production equation, default, model property,
reference value, acceptance threshold or primary comparison scope changed.

## Source and controlled changes

Drela's [1989 paper](../../reference/st4-node-placement-20261109/drela-1989-wing-loads.pdf),
printed pp.326–327, Eqs.37–38, gives

```
u = j/J
theta = (pi/2) * (1 - u*(1 + abs(u))/2)
s/(b/2) = cos(theta) = sin(pi*u*(1 + abs(u))/4)
```

The author describes a compromise between aerodynamic tip clustering and more
uniform structural spacing. The [checksummed source catalog](isae-st4-node-placement-sources-20261109.json)
and original manual identify this with ASWING 3.x; it does not establish the
later 5.x default. The paper's local point-load adjustments are unspecified.

Two explicit mappings were declared before running the probes, each with 40
and 80 nominal intervals:

- **Whole mapping:** map the full symmetric distribution across the physical
  beam, using `u = 2*j/N - 1` and `y = 0.55*(1 + cos(theta))/2`.
- **Mirror half:** use the positive half for the wall-symmetric Pazy wing,
  using `u = j/N` and `y = 0.55*cos(theta)`.

These are disclosed mapping hypotheses. Neither is asserted to reproduce the
archived NODE I40 command. The existing cosine results are reused unchanged.
The current exact stiffness-break insertion at `t=0.52` is retained, giving
41/81 physical intervals and 42/82 unique structural nodes. Native coincident
node counting remains unknown.

Spacing is imposed in physical span, not the arbitrary material parameter.
The literal straight beam has `y=0` at `t=0.0001`, `y=0.52` at `t=0.52`, and
`y=0.55` at `t=0.55`; its two linear inverse maps are used explicitly. Each
worker checks these positions before solving.

The current Glauert-angle receiver interpolation is retained and independently
checked against [Drela 2015, pp.31–32, Eqs.150–154](../../reference/aswing-authoritative-20261108/drela-aswing-steady.pdf).
This isolates node placement from a change in force sampling or force/couple
transfer. The literal file, null weights, stiffnesses, sensors, clamping,
gravity, density, pointwise circulation and frozen influences are unchanged.

## Results

Signed errors below are OpenSwing minus archived ASWING for sensor-3 Earth Z.
The response-increment error uses the two **known positive speeds**, 1 and
17 m/s. The native increment is 16.999982 mm. No unknown startup value is inferred
or subtracted, and this diagnostic does not replace absolute-coordinate acceptance.

| Node rule | Nominal intervals | Z error at 17 m/s (µm) | Z error at 1 m/s (µm) | 1→17 m/s increment error (%) |
|---|---:|---:|---:|---:|
| Current cosine | 40 | +34.802 | +0.105 | 0.20410 |
| Current cosine | 80 | +31.683 | +0.090 | 0.18584 |
| 1989 whole mapping | 40 | −38.614 | −0.136 | 0.22634 |
| 1989 whole mapping | 80 | −5.161 | −0.031 | 0.03018 |
| 1989 mirror half | 40 | +12.118 | +0.031 | 0.07110 |
| 1989 mirror half | 80 | +20.518 | +0.054 | 0.12038 |

![Signed errors for all three Z sensors](../../artifacts/isae/ae1-spacing-current-20261110/spacing-errors.png)

The whole mapping comes close on the finer grid but still misses sensor 1's
original 5% band. The mirror-half result moves away from the reference when
refined. Neither alternative passes all three Z comparisons on both grids.
Selecting whichever grid happens to be closest would not establish a correct
ASWING default or a converged result.

For every changed-grid Z output, its low-speed shift is at most **0.329%** of
its 17 m/s shift. Most of the spacing sensitivity therefore occurs in the loaded
response. The two resolutions do not establish an asymptotic convergence order
or a continuum value; no extrapolated correction is applied.

## Verification and next step

Each numerical worker used one BLAS thread, a 512 MiB address-space limit,
15 CPU seconds, a 25-second elapsed timer and a 30-second supervisor timeout.
All eight terminated normally, with no retries. Worker times were 3.59–5.23 s;
peak RSS was 102.2 MiB. Maximum fresh residual was **1.85e−14**.

The same 29 physical requirements used in the primary sweep are checked for
each state: cold/fresh convergence, saved operator identity, literal source,
settings and sensors, root clamp, force/moment balance, independently rebuilt
strip wrenches, and sensor geometry. Separate saved-data audits bind those
checks to the raw cold/restored snapshots and import no production solver.

The next useful test is a bounded third-resolution check of the three grids at
this single operating point, to distinguish convergence toward a common value
from accidental agreement on one grid. Original node arrays and circulation
settings remain unrecovered. These results justify further discretization
investigation; they do not justify changing a physical parameter or default.

Evidence: [17 m/s plan](../../artifacts/isae/ae1-spacing-current-20261110/plan.json),
[17 m/s audit](../../artifacts/isae/ae1-spacing-current-20261110/assessment.json),
[known-1 m/s plan](../../artifacts/isae/ae1-spacing-current-20261110/low-speed/plan.json),
[1 m/s audit](../../artifacts/isae/ae1-spacing-current-20261110/low-speed/assessment.json),
[combined metrics](../../artifacts/isae/ae1-spacing-current-20261110/sensitivity.json).
The [bounded probe](../../scripts/probe_isae_ae1_spacing.py) and
[control-plan builder](../../scripts/prepare_isae_ae1_spacing_low_speed.py) retain
every request, raw result and terminal receipt. The complete primary sweep is
documented [separately](isae-ae1-full-current-20261110.md).
