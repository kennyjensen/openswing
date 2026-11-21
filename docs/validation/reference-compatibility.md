# Published zero-origin Reference compatibility

OpenSwing now imports 113 of the ISAE repository's 279 literal models, up from
83. The other 166 remain rejected. This is an input-compatibility result, not
experimental validation: all 41 families remain incompletely validated.

The change accepts a single six-column `Reference` row only when its final
three coordinates are zero after the normal table multipliers/adders. The
leading values remain Sref, Cref and Bref; moment, acceleration and velocity
reference points are all zero. Original input text is preserved on save.
Edited reference coordinates serialize using the documented separate rows.
Nonzero legacy coordinates are explicitly rejected rather than assigned an
unverified meaning. Reference dimensions must still be positive.

The [current MIT input guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt)
documents three-column rows and zero defaults for omitted reference points.
The pinned ISAE inputs and the Durrant thesis appendices contain the six-column
zero-origin form. This establishes a uniquely equivalent modern state for
these zero-only fixtures; it does not establish a general legacy coordinate map.
Kepler's [2002 MIT thesis](https://dspace.mit.edu/entities/publication/70449227-7f0d-485f-9875-32195341cb88)
contains nonzero reference coordinates in separate three-column rows, so it
does not supply the missing six-column nonzero interpretation.

## Verification

- 97 native parser/editing tests pass, including 18 new Reference checks.
- An isolated old/new parser comparison covers all 279 ISAE models and 27
  shipped examples. All 110 previously accepted inputs retain identical
  complete parsed model data and diagnostics. Lossless saves and canonical
  roundtrips pass for every accepted input.
- All 111 published zero-origin shorthand fixtures match the isolated old
  parser's result on their explicit three-column equivalent. Only 30 become
  newly accepted; independent errors remain errors.
- Only `asw.py` changes among 97 kernel modules. The other 96, including every
  physical solver module, are byte-identical to the preceding release.
- Actual WebAssembly reproduces all 306 native input outcomes and complete
  accepted model-data hashes, all 18 new checks, and all 30 new setup outcomes.
  A literal ST-3 rigid-load portability probe agrees within 1.4e-17 in its
  checked force/moment coefficients. It is not an ST-3 structural validation.
- The offline browser imports and saves the literal ST-3 input unchanged, solves
  it with the same coefficient gate, and reports the Pazy attachment rejection
  during geometry inspection. Fresh SA-3/4 browser solves and exports also pass.
  The initial panel-count assertion and later test that incorrectly waited for
  an enabled Run button are retained as failed harness attempts.
- A fresh P-1 WebAssembly replay reproduces all 220 original component outputs
  exactly, with the independent hover checks retained.

Among the 30 newly imported models, 15 construct an eight-interval structural
network without solving. Twelve reject attachment stations outside the beam
range; three reject negative point weights. In the affected Pazy inputs, the
beam ends at 0.55 m while a point-weight record specifies 0.558 m. Records are
not deleted or moved to obtain a successful solve. Browser geometry inspection
also validates attachments and can reject such a model before enabling analysis.
Thus 113 successful parses do not mean 113 successful browser loads. These failures are distinct
from file parsing and from disagreement with experimental measurements.

Earlier quantitative studies keep their original source hashes. The coverage
generator verifies their exact input hashes and unchanged parsed data or
rejection outcomes against both parser snapshots. It also verifies that all
other modules are unchanged. These earlier studies are not relabeled as new
numerical runs. The isolated P-1 study does not invoke the ASW parser.

Evidence: [native parser transition](reference-compatibility.json),
[setup outcomes](reference-setup.json),
[WebAssembly checks](reference-compatibility-wasm.json),
[offline browser result](reference-browser.json),
[current imports and propeller replay](isae-wasm-reference-imports-p1.json),
and [full coverage ledger](isae-coverage.md).

## Reproduce

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest -q tests/test_asw_reference_syntax.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/verify-reference-compatibility.py --baseline-kernel /path/to/extracted/baseline
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/verify-reference-setup.py
.venv/bin/python scripts/inventory-isae-validation.py
.venv/bin/python scripts/summarize-isae-validation.py
node scripts/test-reference-compatibility-wasm.mjs
OPENSWING_RESULTS=docs/validation/isae-wasm-reference-imports-p1.json node scripts/test-isae-validation-wasm.mjs imports p1
npm run build
npm run test:browser -- tests/browser/legacy-reference.spec.js tests/browser/isae-sa34.spec.js
```

The baseline is the unchanged 97-module source in the preceding ST-5 evidence
archive, or the `baseline` directory in this study's raw archive. Reconstruct
upstream inputs using the pinned fetch script; no upstream executable scripts
are run. The report and comparison data never substitute a repaired file for
a literal imported model.
