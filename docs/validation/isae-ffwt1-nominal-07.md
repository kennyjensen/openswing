# FFWT-1 nominal comparison after relative-coordinate repair

All three reconstructed folding-wing models now have full-load equilibria
that pass the original residual on the same 103-module source. Physical
agreement remains conditional: this is not an experimental validation pass.
The [previous comparison](isae-ffwt1-nominal.md), including its capped 30° run,
remains available with its original source and evidence.

The requested mesh remains 100/40/40 intervals, realized as 187 nodes and 184
elements. Speed is 22 m/s, incidence and sideslip are zero, the fixed body is
level, density is 1.2256 kg/m³ and gravity is 9.81 m/s². The explicit four-line
input reconstructions are unchanged. None of the five original FFWT-1 models
is newly accepted unchanged.

| Flare | Measured port fold at nominal zero | Computed physical port fold | Computed minus measured | Full residual |
|---|---:|---:|---:|---:|
| 10° | −29.06091° | −25.93771° | +3.12320° | 6.52e−13 |
| 20° | −17.89340° | −13.77296° | +4.12044° | 9.61e−13 |
| 30° | −12.56345° | −11.00380° | +1.55965° | 8.53e−13 |

The measurements retain their digitized incidence coordinates of −0.16932°,
−0.24291° and −0.10836°. Their assignment to nominal zero follows the primary
experimental protocol; it does not establish exact matched operating points.
No values were fitted or interpolated. The [CSV](isae-ffwt1-nominal-07.csv)
retains the original coordinates and comparison qualifications.

Physical port hinge rotation is independently recovered from the tip rotation
relative to its parent and checked against the hinge moment law. Sensor bank
is a distinct observable: −25.59452°, −12.97139° and −9.55874°, respectively.
Archived ASWING sensor-bank values remain contextual evidence.

## Initialization and timing

The three states have different initialization histories; these timings are
not three comparable cold runs. The 10° state is the unchanged previous
equilibrium, freshly evaluated with the new arithmetic. Its earlier cold solve
took 44.18 seconds; the current residual replay took 0.262 seconds.

The unchanged previous 20° state evaluates to 1.06077e−12 under the repaired
arithmetic, narrowly above the unchanged 1e−12 gate. It remains preserved.
A separate public warm-start correction takes one Newton iteration and one
tangent build, with a full Jacobian rank check. The correction and independent
exported-state replay pass at 9.60649e−13. The recorded 72.24 seconds includes
the correction, replay, result serialization and source verification; it is
neither a solve-only measurement nor a new cold-start timing.

The 30° case is a new cold continuation: 125.36 seconds, 8,404 residual
evaluations and nine accepted load levels. Its fresh-network replay reproduces
the full residual and force/moment balances. Earlier capped attempts and the
first new attempt's diagnostic-JSON logging failure are retained, together
with the warm-start harness's initial duplicated-motion failure.

The [numerical repair report](relative-pg.md) explains the arithmetic change,
native and browser checks, and remaining performance limits. No solver gate,
physical parameter, mesh or measured target changed.

## Remaining validation work

The primary tunnel record differs from the literal archive in hinge position,
tip mass/CG and local flow. Exact mounting alignment, friction, contact and
fixture properties remain unresolved. Jig-based continuation and the saved
20° branch do not establish equivalence to the author's hanging-wing launch
or demonstrate stability. Mesh refinement, matched operating curves,
sideslip/twist cases, dynamics and experimental uncertainty remain unfinished.
No original ASWING executable is available for direct reference runs.

Coverage remains 17 partial families, 24 pending and none fully validated.
FFWT-1 remains pending; three numerical roots do not complete that family.

## Reproduction

The [JSON report](isae-ffwt1-nominal-07.json) pins 592 input files. The
[selected evidence archive](isae-ffwt1-nominal-07-evidence.zip) contains the
inputs, source snapshots, scripts and results. From its extracted root:

```sh
python3 -B nominal-comparison-07/compare.py --work . --output-prefix reproduced
```

With Python 3 and NumPy installed, this command reproduces the JSON, CSV and
text reports; it does not rerun the solver. The [portable verification](isae-ffwt1-nominal-07-replay.json)
records byte-identical clean-copy reproduction and checks all 599 ZIP members.
The archive is 18,512,074 bytes, SHA-256
`6d328d0f35bc1019733d5b9f579cd8576e96392564387d6f6d33d1ccd284d482`.
Complete raw FFWT study packaging remains a separate unfinished task.
