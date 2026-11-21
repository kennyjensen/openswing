# Accepted inverse roots and checkpoint frame consistency

The two corrections are integrated in `openswing/time_integration.py` and
`openswing/time_state.py`. They close independently reproduced acceptance gaps;
they do not add general velocity or pose inverse histories.

## Behavior

When an inverse actuator solve requests a locally unique root, Newton now checks
the tangent at a successful correction before returning. Previously, convergence
at loop entry checked the tangent, while convergence immediately after a
correction could accept a continuum of roots. A smooth scalar counterexample
reproduces that distinction. Ordinary solves that do not request this check keep
their existing behavior. This is a local numerical rank check, not a proof of
global branch uniqueness or general implicit-controller uniqueness.

A restored time checkpoint must describe one physical frame. Its stored origin
velocity, angular velocity, position, orientation and time are compared with the
redundant residual inputs before accepting the common physical residual. Motion
rates and gravity are also checked. Comparisons use physical vectors, rotation
matrices and the existing physical scales. Equivalent periodic angles remain
valid; a large absolute time does not permit a larger time mismatch. Invalid
cached speed or vector shapes are rejected before rebuilding kinematic fields.

Cached actuator settings, accelerations and operating targets are preserved.
Restoration does not apply a future forcing command: a saved launch can represent
the physical snapshot before that command. Vacuum checkpoints have no duplicated
flight condition, so their redundant rate and gravity fields are checked. This
does not authenticate a predecessor trajectory or prove hidden inverse-history
constraints that are not yet implemented.

## Evidence and scope

| Stage | Result | Scope |
|---|---|---|
| Full native baseline | 1,221 passed in 73 terminal file subprocesses; no failures, errors or skips | Apparent-rate-corrected kernel **before these two changes**; all 392 frozen inputs matched at recording |
| Newton counterexample | Original 1 failed / 4 passed; corrected 5 passed | Both convergence routes, regular roots and explicitly optional rank checks |
| Newton production selection | 31 existing tests passed | Complete inverse-actuator file plus mixed constraints, saved launch, forcing cutoff and Radau restart |
| Checkpoint final candidate | 21 focused and 20 existing tests passed | Frame/cache inconsistencies, representation guards, valid restorations, ordinary and controller/forcing restart |
| Combined native interaction | 2 existing tests passed | Fixed and accuracy-checked inverse actuator checkpoint continuation on the combined kernel |
| Integrated focused regression | 26 new tests passed | Actual main checkout, relocated repository fixture and combined production sources |
| Actual packaged WebAssembly | 15 declared checks passed in one attempt | Exact combined 58-module kernel, eight runtime assets, actual rigid-body step, root checks and checkpoint restores/rejections |

The existing-test selections overlap; their counts must not be added as unique
coverage. The integrated collection adds 26 cases to the preceding 1,221-case
baseline. A complete 1,247-case run has not been claimed.

The original checkpoint run had 14 failures and two passes. Twelve mismatches
were incorrectly accepted; the other two were already rejected by the common
residual but lacked the new frame-specific diagnostic. An initial candidate
passed those 16 tests, then failed all five independent review cases. The final
candidate corrects the large-time, negative-speed and malformed-vector cases.
All these failures and candidate sources remain in the evidence archive.

The WebAssembly check used the packaged Pyodide runtime directly under Node,
with an actual step to construct its checkpoint. It verifies runtime behavior,
not a new browser or UI acceptance run. The repaired viewer's historical browser
evidence retains its original kernel fingerprints. The UI is unchanged in this
increment. Final build/archive matching is a separate release audit.

## Records and reproduction

- [Combined record](solver-consistency.json)
- [Full preceding baseline](native-regression-apparent-rate-20261010.json)
- [Original Newton counterexample](newton-rank-review.json) and
  [production selection archive](newton-production-regression-evidence.zip)
- [Checkpoint before/review/final evidence](checkpoint-frame-evidence.zip)
- [Combined native continuation evidence](combined-rank-checkpoint-evidence.zip)
- [Integrated focused tests and sources](solver-consistency-integrated-evidence.zip)
- [Packaged WebAssembly sources, runtime and results](combined-rank-checkpoint-wasm-evidence.zip)

Run the integrated focused cases with:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest -q tests/test_newton_rank.py tests/test_checkpoint_frame.py
```

The archives retain source hashes, exact selections, terminal records and the
failed attempts. Native reproduction requires compatible external Python,
NumPy, SciPy and pytest installations. The WebAssembly archive includes the
tested runtime assets and its replay script. Historical paths are provenance,
not a promise that every original orchestration script is location independent.

The full ASWING goal remains incomplete, with all 40 broad requirements Partial.
General inverse motion histories, their initialization/events/restarts and time
accuracy, loaded flutter, swept-wing convergence, legacy interoperability and
broader physical validation remain open.
