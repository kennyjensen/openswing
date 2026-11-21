# Original FFWT-1 archived-ASWING pilot

2026-10-26. The target is reproduction of the archived ASWING calculation.
Agreement with experiment is not an acceptance requirement. This pilot makes
the original Flare10 input usable and compares one archived operating point;
it does not establish a complete FFWT reference match.

## Original input and compatibility

The packaged [model](../../examples/isae-ffwt-flare10.asw) is byte-identical to
`FFWT_Flare10.asw` in the ISAE archive at commit
`f62943df20e9e4d7d9f50e070477b22426b5f865` (SHA-256
`f73fe93bebb9419f0d38d94dc9a365baac7e3437e2996473c72c3c1f459fbf13`).
No stiffness, mass, geometry, lift limit, reference dimension or output value
was adjusted. The two tips have different literal lift limits, which are retained.

Two narrow input extensions are now supported:

- A single-row table containing only zero-valued rigid stiffness fields
  (`EIcc`, `EInn`, `GJ`, `EA`, `GKc`, `GKn`) denotes constant rigidity.
  The original sample is retained, without inventing a material station or
  spline knot. Nonzero, geometric and mixed singleton tables remain invalid.
- A two-point Jangle table with decreasing moments is reversed as paired
  samples in its private compiled copy. Its affine law, sign, extrapolation
  and original record order are preserved. Arbitrary nonmonotone tables are
  still rejected.

The distribution editor displays constant rigidity across the actual beam
domain. Its raw singleton remains editable/exportable. Operations needing a
finite multipoint curve require an explicit replacement; they do not fabricate
stations. Existing spline policies and saved-state identities are unchanged.
The [ASWING guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt)
defines zero stiffness as rigid and two-point Jangle interpolation as linear.
The exact historical reader and executable revision remain unknown.

## Declared calculation

The selected archive row is number 4 in `FFWT_Flare10_A5.txt`: commanded IAS
20.941885325558797 m/s and incidence 5°. The mounted pilot declares sea-level
density 1.2256 kg/m³, equal to the literal rhoSL, so IAS=TAS in this pilot.
It uses gravity 9.81 m/s², zero sideslip/control/frame motion, zero PG
Mach, full sensor airflow, updated influences and no aerodynamic ground image.
It uses the opt-in `drela-steady-coupled-v1` operator and `drela-segspl-v1`
interpolation. The browser's default operator is unchanged.

The two independently cold meshes request 99/39/39 and 198/78/78 cosine
intervals on the center/right/left beams. Attachment stations produce actual
totals of **182 and 358 intervals**. These are declared comparison meshes;
the archive does not retain the exact original node arrays. Each hinge keeps
its literal very soft finite law, rather than being replaced with a free pin.

The historical script applies Anchored defaults after selecting the last of
eight operating points, without an explicit apply-to-all command. Complete
per-point constraints, startup files, aerodynamic options and branch history
are not archived. This is therefore a transparent mounted candidate at a
known commanded coordinate, not proof that every historical setting is known.

## Numerical and reference results

Both cold solves converge, in **46.50 and 49.40 seconds** on this host.
One fresh restored residual per mesh is 4.76×10⁻¹³ and 7.06×10⁻¹³.
All **78 physical/restoration checks** pass, including clamp pose, global
force/moment balance, finite hinge rotations and the literal moment–angle
laws. Hinge-law checks derive angles independently from node rotations and
saved winding. The source mass is 0.8959168 kg. No tolerance was relaxed.

The retained progress trace contains 29/28 rejected initial continuation
targets, matching the first-Newton rotation safeguard for these soft hinges.
About 86.4%/90.5% of runtime precedes the full-load target; the final target
through reporting takes 6.33/4.72 s. Final strips are unstalled. Intermediate
trial airflow was not saved, so that observation is limited to the final state.
An initial-step predictor is a concrete follow-up performance task; this
increment does not change continuation or its accuracy gates.

| Archived quantity | ASWING | OpenSwing, 358 intervals | Difference | 182→358 mesh change |
|---|---:|---:|---:|---:|
| Lift, N | 8.23892 | 8.28599214 | +0.5713% | 0.03138% |
| Root chordwise moment, N·m | 0.0505454 | 0.05622796 | +11.2425% | 0.73220% |
| Left-tip bank, degrees | 6.17936 | 6.37781691 | +0.198457° | 0.05448% |
| Left-tip airflow incidence, degrees | 4.59708 | 4.46587536 | −0.131205° | 0.01401% |

Three of four mesh comparisons pass the predeclared 0.1% gate. The root moment
does not. All eight coarse/fine printed-precision reference comparisons fail.
The root moment uses the preselected left trace at sensor 1; both traces are
retained. Lift excludes gravity and support reactions. Tip bank and incidence
are sensor outputs, not substitutions using the hinge angle or strip incidence.

Only this one operating coordinate has been solved in this pilot. All eight
archived rows and their raw tokens remain in the reference contract; the other
seven are untested here. Mesh refinement, complete historical settings and
the remaining output discrepancies are still open. Numerical convergence and
browser/native agreement do not by themselves establish ASWING reproduction.

## Offline browser check

The actual browser UI completes one cold solve of the 182-interval case in
**87.31 seconds**, after **55.26 seconds** runtime startup on this host.
All 50,303 compared numerical values agree with native execution; the largest
absolute difference is 4.97×10⁻¹¹. All 1,040 browser checks pass with no external
HTTP requests, page errors or failed network requests. The rendered aircraft
uses WebGL.

The checks include original-file import/export, the left-tip constant-rigidity
preview, raw singleton preservation, canonical reimport, and both unsolved and
solved project roundtrips. The saved result and project reopen byte-for-byte
without another solve. The [checked project](../../examples/isae-ffwt-source-coupled-project.json)
contains the original model, declared settings and browser result. Its stored
answer is a conditional comparison result, not an accepted ASWING match.

## Reproduction and evidence

The focused input suite passes 96 distinct tests, including the original file;
83 editor regressions also pass. Eight affected literal tests were rerun after
moving their fixture from the optional reference cache to the packaged example.
The initial test-only affine-curvature assertion used an unscaled absolute
tolerance on a derivative with a very small moment coordinate; its failure
is retained. The corrected assertion measures roundoff relative to the angle
span and does not change a physical acceptance gate.

`scripts/verify-isae-ffwt-reference.py` prepares exact requests, freezes inputs,
runs at most two cold solves, and permits refinement only after the first
passes its physical checks. Full states, mesh coordinates, progress events,
fresh field arrays, both root traces and reference differences are retained.
An independent saved-only completion passes 320 checks, including internal
force/moment parity and final verification of all 124 frozen inputs. It also
records the nonselected right root trace: 0.0562279164 N·m on the fine mesh,
which leaves essentially the same reference discrepancy. The executed runner
is retained; its later reporting changes add these checks directly and make a
final input-pin mismatch fatal. No physical solve was repeated for those changes.

The [reference contract](isae-ffwt-reference-contract.json) contains all eight
original rows, the two predeclared meshes, output mappings, physical gates and
historical uncertainties. Reproduce the bounded native pilot from the repository:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  .venv/bin/python scripts/verify-isae-ffwt-reference.py prepare /tmp/ffwt-new \
  --contract docs/validation/isae-ffwt-reference-contract.json
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  .venv/bin/python scripts/verify-isae-ffwt-reference.py run /tmp/ffwt-new
```

Use a new output directory for each explicitly planned run. The accompanying
[machine-readable report](isae-ffwt-original.json) records browser checks and
artifact pins separately from the native result and the remaining reference
failures. Full inputs, outputs and retained attempts are in the
[evidence archive](isae-ffwt-original-20261026-evidence.zip).
