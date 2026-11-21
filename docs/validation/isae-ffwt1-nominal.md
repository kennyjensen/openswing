# FFWT-1 conditional nominal comparison

This is the preserved integrated-06 comparison. The
[integrated-07 comparison](isae-ffwt1-nominal-07.md) supersedes its current-status
claims and adds the 30° equilibrium while retaining these original artifacts.

Two of the three reconstructed folding-wing models now reach full-load
equilibrium on the same frozen 103-module solver. This is a conditional
comparison with the nominal experimental protocol, not a physical validation
pass. FFWT-1 remains pending in the coverage ledger.

The requested discretization is the original 100/40/40 intervals, realized as
187 nodes and 184 elements. Both cases use uniform speed 22 m/s, incidence and
sideslip zero, a level fixed body, density 1.2256 kg/m³ and gravity 9.81 m/s².
The four-line input reconstructions and all historical failed attempts remain
explicit in the pinned evidence; none of the five original FFWT-1 files is
newly accepted unchanged.

| Flare | Measured port fold at nominal zero | Computed physical port fold | Computed minus measured | Current result |
|---|---:|---:|---:|---|
| 10° | −29.06091° | −25.93771° | +3.12320° | Full load, residual 6.52e−13 |
| 20° | −17.89340° | −13.77296° | +4.12044° | Full load, residual 6.70e−13 |
| 30° | −12.56345° | — | — | Six-minute cap; no full-load prediction |

The measured values are the seventh points of the thesis Figure 7.13 incidence
protocol. Their original digitized abscissae remain −0.16932°, −0.24291° and
−0.10836°; they have not been shifted or interpolated to zero. Protocol-zero
assignment does not establish an exact matched experimental operating point.
The [CSV](isae-ffwt1-nominal.csv) retains these coordinates alongside the results.

The observable is physical hinge rotation. It is recovered independently from
the parent-relative tip rotation and checked against the hinge moment law,
including its sign and branch. Port sensor bank is a different quantity:
−25.59452° and −12.97139° for the computed 10° and 20° cases. Archived ASWING
bank values remain contextual evidence, not substitute hinge-angle references.

## Numerical checks and timing

Both saved states pass the original full residual on freshly constructed
networks at the unchanged 1e−12 acceptance threshold. Force/moment balances and
hinge observables also reproduce. The new 10° physical fold agrees with the
historical 99-module result within 7.5e−11 degrees; its current solve took
44.18 seconds and 13 accepted continuation levels. The 20° solve took
164.93 seconds and 11 accepted levels. These are native observations under
concurrent machine load; the 20° run also writes extensive diagnostics, so
they are not controlled performance comparisons.

The 20° process encountered a terminal logging exception after saving its
complete result and state. That exit code is retained, alongside the passing
fresh-network replay. The 30° process stopped cleanly at its 360-second cap;
its last accepted load fraction was only 0.00037312. A residual near the
acceptance threshold at an attempted higher load is not a solved prediction.

## Remaining physical work

The primary tunnel record and literal archive differ in hinge station, tip
mass/CG and local flow. Actual mounting alignment, local flow histories,
friction, contact and some fixture properties are not reconstructed. The
current cold continuation also differs from the author's hanging-wing launch;
a converged root does not prove branch stability or equivalence. Mesh
refinement, matched operating curves, the 30° equilibrium and experimental
uncertainty remain unfinished. No parameters were fitted and no experimental
acceptance threshold was invented.

## Reproduction

The [machine-readable report](isae-ffwt1-nominal.json) pins 436 input files.
The [selected comparison archive](isae-ffwt1-nominal-evidence.zip) includes those
inputs, all three referenced solver versions, scripts and report artifacts.
From its extracted root, run:

```sh
python3 -B nominal-comparison-06/compare.py --work . --output-prefix reproduced
```

This standard-library-only command reproduces the JSON, CSV and text reports;
it does not run the solver. A clean-copy replay produced byte-identical
artifacts and verified every archive member, recorded in the
[portable replay result](isae-ffwt1-nominal-replay.json).
The archive is 16,823,516 bytes, SHA-256
`b7bc340a1684fae344638e33e64e58f0550a29b996eb650c0d7acf730458c88b`.
It contains selected comparison evidence; the complete raw FFWT diagnostic
archive remains a separate task.
