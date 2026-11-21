# FFWT-4 complete source inventory and current coverage

The retained repository contains **40 native histories and 8,000 root-moment
values** for FFWT-4. Five shell drivers each export eight 200-row histories.
The previously tracked fixed-wing scope contains only 1,600 of those values.
The full archived scope now passes **200/8,000 at 5%**. All 200 existing,
qualified Fixed-1 matches remain; this audit adds no new prediction or pass.

| Driver/history group | Model explicitly loaded | Histories | Passing / required | Current limitation |
| --- | --- | ---: | ---: | --- |
| Fixed | `FFWT_Fixed.asw` | 8 | 200/1,600 | First complete history matches; seven other histories and full spatial accuracy remain open. |
| Removed | `FFWT_removed.asw` | 8 | 0/1,600 | Literal model meshes; histories are uncomputed. Driver/model capitalization differs. |
| Flare10 | `FFWT_Flare10_PM2.asw` | 8 | 0/1,600 | Two point-mass attachment stations are outside their tip-beam ranges. |
| Flare20 | `FFWT_Flare20_PM2.asw` | 8 | 0/1,600 | Same attachment issue; the driver also explicitly sets 16° sideslip. |
| Flare30 | `FFWT_Flare30_PM2.asw` | 8 | 0/1,600 | Same attachment issue. |
| **Total** | Five driver-selected models | **40** | **200/8,000** | **7,800 values remain uncomputed, including 4,800 with unresolved attachment compatibility.** |

The complete nominal32 Fixed-1 history has median/max native error
0.523%/0.681%. Errors are unavailable for uncomputed histories. Finer-mesh
repeats do not add targets or passes. The active refinement is documented
separately in [the spatial/time study](isae-ffwt4-spatial-time-20261106.md).

## Explicit source pairing

The audit follows each shell invocation and each output-writing command,
checks all source bytes against the retained repository manifest, and verifies
every exported row against its driver's time grid. Every output has 200 rows,
including t=0, and ends at 199 times the requested dt. The printed time
precision is retained when checking that correspondence. All files export
sensor-1 local chordwise moment, `Mc′`, with no missing output in this inventory.

The Flare10/20/30 drivers explicitly select their `PM2` models. The similarly
named base models are different inputs and are not replacements. Four other
retained models have no invocation in these five drivers:
`FFWT_Flare10.asw`, `FFWT_Flare20.asw`, `FFWT_Flare20_PM.asw`, and
`FFWT_Flare30.asw`. They remain part of model compatibility coverage but do
not create extra native-history targets without corresponding outputs.

Internal model titles are not unique. Fixed is titled `FFWT Removed`;
the selected Flare10 and Flare30 PM2 models are titled `FFWT Flare 20`.
The exported headers match those internal titles. The explicit driver paths
therefore determine pairing. The Removed invocation uses `FFWT_Removed`,
while its uniquely matching retained file is `FFWT_removed.asw`. This
case-only difference is recorded explicitly; no source bytes are changed.

All drivers command incidence 6° and speed 22 m/s. Only Flare20 includes
`!B 16`. The ASWING guide identifies key B as sideslip and Ex as bank
([cached guide](../../.reference/aswing_doc.txt), constraint table near line
2040). An omitted beta command in the other drivers is not evidence of a
recovered zero-beta default. Original node requests, startup commands and
operating-point resets are retained verbatim in the inventory. Exact node
spacing and complete historical operating constraints remain qualified.

`Analysis.m` reads these same tables and derives maximum/minimum increments
and plotting quantities. Those derived reductions do not add independent
history values to the denominator.

## Literal attachment compatibility

All nine retained models parse. Two small nominal meshes, 8 and 16, were
attempted for every model, with no aerodynamic or structural solve. Six
models mesh on both grids. Each of the three selected PM2 models is rejected
on both grids by the current OpenSwing attachment-range check.

The offending weight records are identical in their attachment coordinates:

| Weight record | Beam | Attachment station | Beam range |
| ---: | ---: | ---: | --- |
| 52 | Right tip, 2 | +0.3521 | +0.364 to +0.500 |
| 57 | Left tip, 3 | −0.3521 | −0.500 to −0.364 |

The joint and sensor stations are inside the corresponding beam ranges.
The main beam's negative side is supplied by the documented zero-start chord
symmetry convention; it is not missing. The guide describes that convention
near lines 1094–1126. Point masses are individually specified and are not
implicitly mirrored.

These are confirmed current OpenSwing rejections, not proof that native
ASWING rejected the original inputs. The native treatment of out-of-range
point-mass attachments, or a different historical model underlying the
exports, remains unresolved. No attachment is moved or clipped, and no
alternate model is substituted to obtain a match.

A subsequent [rigid-tip preflight](isae-ffwt4-rigid-attachments-20261106.md)
certifies exact rigidity of both tips in all three selected PM2 models.
The rigid-pylon identity preserves point kinematics and total wrench to
roundoff in 1,536 independent checks. This is a possible route to a physical
endpoint treatment, but it does not establish internal section-load
equivalence, production tangents or native out-of-range handling. The current
attachment rejection and all 4,800 affected required values remain unchanged.

## Evidence and reproduction

All **15 source-inventory tests pass**. They check driver-selected PM2 names,
explicit versus unspecified sideslip, later operating-point resets, complete
time grids, native channel identity, missing rows and ambiguous filenames.
The independent coverage reconciliation verifies **659 evidence pins** and
pairs each of the 200 existing predictions to its exact original source cell.
It retains all 8,000 required targets and counts repeated mesh/time studies
once. No production equation, physical parameter or tolerance changed.

Evidence is under `artifacts/isae/ffwt4-source-audit-20261106/`:

- `model-meshing.json`: all nine literal models and 18 small mesh checks.
- `source-inventory.json`: all five drivers, 40 histories and 8,000 values.
- `source-tests.xml`: 15 passing source-parser checks.
- `reconcile-coverage.py` and `coverage.json`: authenticated 200/8,000 coverage.
- `rigid-tip-preflight.py` and `.json`: literal stiffness certificates and
  independent rigid-body identities; no production attachment change.

The reusable helpers are `scripts/verify-isae-ffwt4-models.py` and
`scripts/assess-isae-ffwt4-sources.py`. The full-family shared execution adapter
is still absent. Matching the complete first Fixed history does not validate
the other histories, hinge dynamics, exact historical defaults or the whole
family. The progress history records this denominator expansion at the time
of observation; earlier 1,600-target observations are preserved.
