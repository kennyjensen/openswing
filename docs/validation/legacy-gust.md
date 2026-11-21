# Legacy straight type-5 gust files

OpenSwing now imports and canonically exports the straight type-5 numeric
one-minus-cosine layout established by pinned public ASWING examples. It converts
these files into the existing Earth-coordinate cosine field used by the numerical
solver. No gust-force or time-integration equation changes.

This is partial catalog interoperability. Other numeric types, nonzero spanwise
slopes and nonzero trailing parameters remain unsupported until their meanings
are verified. The public [ASWING guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt)
delegates the catalog to configurable routines; the [5.77 version notes](https://web.mit.edu/drela/Public/web/aswing/version_notes.txt)
identify the vertical cosine type without giving every positional convention.
The [WingLoop example and scenario](https://github.com/LeonardoAVONI/WingLoop/tree/23b3a685bbfd282cda1996011b6a94aad020311a)
supply an independently documented onset, gradient length and amplitude.

## Use

In **Earth-coordinate gust field**, choose **Import field** and open a supported
`.gust` file or an OpenSwing JSON field. Imported type-5 values populate the
cosine controls, and the import note describes the convention. The values use the current
`.asw` input length and time units; importing does not convert units automatically.
The field can be previewed, used in steady/time calculations, and saved with a
named project case. Applying an import invalidates an old analysis result.
An invalid or superseded import leaves the existing field in place.

**Export .gust** writes a canonical numeric type-5 file only for a frozen vertical
cosine field directed along negative Earth X. Use **Export JSON** for moving
pulses, slanted fields, other velocity components and general field types. Legacy
export preserves the physical field and parameter precision; it does not preserve
original comments or whitespace.

The records are:

| Record | Meaning |
|---|---|
| 1 | Integer gust type, 5 |
| 2 | Onset Earth X, x0 |
| 3 | Spanwise slope, verified only for zero |
| 4 | Positive onset-to-peak gradient length H |
| 5 | Signed peak Earth-Z velocity W |
| 6, optionally 7 | Unused zero parameters in the public example layouts |

The peak occurs at **x0-H**, and the end at **x0-2H**. The original
`examples/vertical-pulse.gust` provides a runnable example with x0=-3, H=3 and
W=1. The frozen pulse does not move with time; the aircraft flies toward negative
Earth X and samples it at its current posed and deformed locations.

## Evidence and limits

The native regression passed 79 tests across gust files, existing gust physics,
reference-airflow targets and the JSON bridge. Six project data tests also passed.
The independent study contains 14 cases: profiles and quarter-turn-bank point
loads for two pinned public inputs, followed by steady and narrow-pulse transient
checks in three consistent length/time/force systems. Independent references use
phase values, integrated area W*H and point-drag forces from the known local
velocity. The transient check deliberately requests a step spanning the complete
pulse; the existing phase guard must refine it and resolve the encounter.

`legacy-gust-sources.json` pins the two original files by revision, Git blob,
SHA-256 and size. Source comments are kept outside the distributed reports and
archives. The old Avoni input's numeric amplitude is 3 even though a comment
contains inconsistent arithmetic; no data value has been corrected to match it.

`legacy-gust.json` records 14 native cases and 60 source hashes. The packaged
replay passed all 14 cases and 2,435 physical-value comparisons, with a maximum
scaled native/WASM difference of 3.71992e-16 (limit 2e-9).
`legacy-gust-wasm.json` pins 55 kernel modules, 61 source hashes and the runtime,
and separately checks import/export of both original public input files.
The final UI browser verification passed all five workflows in 2.5 minutes:
offline import/export, analytical
loads, project restoration, invalid records, unsupported exports and late-import
races, alongside the existing JSON gust workflows. A scaled-input check imports
and exports H=1e-15 without a dimensional browser cutoff, while H=0 is rejected.
Desktop/mobile captures were visually reviewed, and the mobile overflow check
passed. This targeted verification does not constitute a full-repository rerun.

These checks establish the supported conversion and its use in the implemented
physics. Complete catalog/sign conventions, original ASWING executable agreement
and aircraft/experimental gust-response validation remain open. Earlier numerical
reports retain their original source hashes and remain historical when those
hashes differ from the current kernel.

```sh
.venv/bin/python scripts/fetch-legacy-gust.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/verify-legacy-gust.py
npm run build
node scripts/test-legacy-gust-wasm.mjs
npm run test:browser -- tests/browser/legacy-gust.spec.js tests/browser/gust.spec.js
```
