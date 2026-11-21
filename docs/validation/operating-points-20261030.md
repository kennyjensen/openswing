# Steady operating-point sequences

OpenSwing now exposes ordered steady sequences through the JSON kernel and a
**Steady polars** tab. ASWING's [public user guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt),
“Defining multiple operating points on stack,” describes inheriting specified
settings when inserting a point and computing the sequence with `XX`.

The new route shares the existing single-point solve dispatch. It does not
change physical equations, tolerances, wake geometry, stall parameters, or
ISAE acceptance policy. No modes or linearization are needed to compute a
steady sequence. The source text is parsed once. Independent starts remain the
default; optional previous-point initialization reuses the preceding converged
circulation or physical mounted state through the existing checked solvers.

```json
{
  "action": "operating_points",
  "mode": "rigid",
  "source": "...literal ASW text...",
  "panels": 40,
  "condition": {"speed": 30, "mach": 0},
  "operating_points": {
    "initialization": "previous",
    "points": [
      {"name": "First", "condition": {"alpha": 2}},
      {"name": "Second", "condition": {"alpha": 4}},
      {"name": "Repeat", "condition": {"alpha": 4}}
    ]
  }
}
```

Each specification inherits the previous **specified** condition, including
control/power channel values. An explicit `operating_constraints` list replaces
the previous list; omission inherits it. Solved trim variables never overwrite
later specifications. Each returned row retains both the specified `condition`
and the successful `actual_condition`, or a typed error with available details.
Failed physical solves do not prevent subsequent points from running.

`initialization` may be `cold` (the backward-compatible default) or `previous`.
The latter starts the first point independently and then corrects each preceding
converged solution at the newly specified conditions. It preserves entered
order, including reversals and repeated points. Each row has an `initialization`
record identifying the source index or the reason for a cold start. An unsuccessful
point is never propagated: the next point starts independently. Changes to the
circulation discretization also require a cold start; no state interpolation is
performed. Mounted correction keeps its full residual and tangent-rank gates.

Rigid `auto` retains the existing documented cold retry if its supplied seed
fails, with the attempt and `cold_fallback` recorded. `direct` keeps only the
seeded attempt; explicit circulation `continuation` cannot accompany previous-
point initialization. Mounted correction failures remain failed rows without
an automatic cold retry. This option does not authenticate native ASWING's
initial guesses, branch choice, or ability to cross a fold.

Controller measurement commands that are not specified numerically acquire
their default values during an independent solve. Such points start cold so a
saved command cannot silently change the new problem. Releasing a controller
command from trim also starts cold to restore its prescribed value. Controllers
with explicit measurement commands and unchanged trim variables can continue.

The browser accepts up to 200 explicit angles in entered order, including
negative, repeated, and nonmonotone values. It plots CL, total CD, Trefftz CDi,
and Cm against solved angle, and retains failure gaps. CSV includes requested
and solved angles, coefficient availability, status, errors, and settings.
JSON includes the complete source, mesh, request, results, and worker provenance.
Progress displays the current point and total separately from solver iterations.
Editing aircraft settings invalidates results; cancelled or stale workers cannot
replace current results. Mobile plots use the existing Plots workspace.

Inspect selects a successful point's alpha, aircraft loads, geometry, and
report. Projects retain the angle list and starting-solution choice and can save the selected single-point
solution. Complete sequences are exported through Polar JSON; they are not
automatically stored as project solutions.

The implementation supports ordinary rigid/mounted equations and the existing
source-coupled mounted policy with its restrictions unchanged. Unsupported
options are rejected explicitly. Externally loaded initial states,
interactive arbitrary per-point settings in the browser, and legacy `.pnt` or
`.set` interchange remain outside this addition. This workflow is not evidence
of native ASWING branch selection or general feature parity.

Verification records are retained in
[the operating-point artifact directory](../../artifacts/isae/operating-points-20261030/).

## Executed verification

- 181 native tests pass: 38 new cases and 143 existing bridge regressions.
  Real rigid and source-coupled points match separate calls; a mounted trim
  sequence checks inherited specifications, solved alpha, and clearing targets.
  A physical local-Mach failure is retained and a later valid point recovers.
- 41 JavaScript tests pass across the new view, numerical-policy routing,
  projects, and axes. Exports preserve failed/missing values and nested Trefftz
  lift, while plot paths break at unavailable points.
- The final packaged WASM modules reproduce nine converged native points and
  one physical rejection. All 457 numerical comparisons pass at a scaled
  tolerance of `2e-8`; the maximum observed difference is `5.18e-12`.
  The first pass covered 207 comparisons. A saved-output audit adds explicit
  circulation, local section moment, and strip-force comparisons, bringing the
  total to 457 without repeating physical solves. The audit corrected an
  optional-field check that looked for the internal name `gamma` instead of
  the exported `circulation`; the final checker requires the actual fields.
- Two production-browser workflows pass. They exercise offline calculations,
  repeated points, CSV/JSON, inspected-point solution saving, case restoration,
  source-coupled mounted solves, mobile rendering, failure rows, stale results,
  cancellation, and solving again after cancellation. The cancellation test
  reconnects to the local static server to reload the terminated runtime.
- All 131 native/public/production Python modules match. The 129 existing
  modules outside the bridge are byte-identical to the preceding implementation;
  the bridge extracts the shared dispatch, and `operating_points.py` is new.
  The complete build succeeds. The existing large-bundle warning remains.

The first native test run had three fixture mistakes (178 passed, three failed);
the corrected fixtures passed without changing physics. An earlier successful
native/WASM replay is retained separately because final mesh preflight was
added afterward; the final replay uses the current source hashes. Visual
inspection also shortened chart tick labels; exported numerical precision is
unchanged. The full offline/mobile workflow passes again with these final
labels. Independent backend review records all resolved findings and pins.

These are implementation/portability checks. The 42-row ISAE ledger and every
registered reference count remain unchanged. SA-1–SA-5 parity and broader
ASWING functional equivalence remain incomplete.

## Previous-point continuation verification

The [continuation evidence](../../artifacts/isae/operating-point-continuation-20261030/)
retains preparation, full outputs and tests. The focused regression run passes
272 native tests, including real rigid, flexible mounted, source-coupled,
changed-trim and controller cases, failures and changed circulation bases.
The original cold results remain covered. JavaScript checks pass 33/33.
Nine converged points and one physical rejection replay through packaged WASM:
764 numerical comparisons pass at `2e-8` scaled tolerance, maximum difference
`4.09e-9`, including mounted positions, rotations, internal loads, reactions and
circulation. Seed provenance matches across runtimes.

Both production-browser workflows pass: offline continuation, actual rigid
seed reuse and a reported cold retry, source-coupled mounted continuation,
CSV/JSON, inspection with a reproducible seed in its single-point request,
project restoration, migration of older projects to independent starts,
mobile rendering, failed rows, cancellation and stale-result rejection.
Desktop/mobile screenshots were inspected. The first browser run's continuation
assertion incorrectly required every seed to succeed; it was corrected to check
both accepted seeds and the explicitly supported cold retry. That run's separate
failure/cancellation workflow passed, and the corrected continuation workflow
passed on its subsequent run. The production build completes; the existing
large-chunk warning remains.

The first native run had three fixture failures: two used a nonexistent example
path and one omitted a zero-gain sensor's explicit controller command. Those
fixtures were corrected; the physical equations and acceptance gates were not
changed. The earlier verification counts above describe the original cold-only
workflow and are not added to this continuation run.

A separate 24-panel flexible-wing timing/accuracy study retains a useful
limitation. For the five-point 2°–4° sequence, two cold runs took 5.03/5.24 s
and two continued runs took 9.08/9.96 s on this host. Continuation is not a
demonstrated speed improvement here; its mounted path retains a final
tangent/rank check. Both paths passed the unchanged `1e-8` residual gate, but
the cold solutions reached about `1e-13` while warm corrections stopped near
`1e-9`. Three of six field comparisons failed the prospective `2e-7` scaled
state gate: internal force (`1.07e-5`), internal moment (`5.03e-6`), and support
reactions (`1.88e-6`). These are componentwise scaled differences, not native
ASWING percentage errors, and the failed checks remain in the record.

A predeclared follow-up used the native single-point API with tolerance
`1e-11` for both complete sequences, retaining the same comparison gate.
All six fields then pass; the largest scaled difference is `4.08e-9`. This
supports unequal residual termination as the cause in this example. Production
tolerances were not changed. The stack remains an optional way to carry
physical solutions through settings, with independent starts as the default;
neither branch uniqueness nor a general speed benefit is established.

The browser retry also supplies a focused numerical witness for the next solver
investigation. Its nominal zero-lift state has a maximum circulation magnitude
of `2.87e-322`. Replaying that literal seed natively at 5° with `direct` fails
at residual `0.0872`, while an exact-zero seed converges to `2.36e-17`.
[Both requests and outcomes](../../artifacts/isae/operating-point-continuation-20261030/subnormal-seed-witness.json)
are retained. The subsequent [seed-coordinate correction](rigid-seed-increments-20261030.md)
confirms MINPACK's initial trust-region scaling as the cause, including for
ordinary small nonzero seeds. Dimensionless increments followed by a checked
local absolute-coordinate correction now solve that witness directly and
preserve tiny nonzero roots. The original `auto` retry remains available for
other failures. No arbitrary circulation threshold or residual relaxation was
introduced; the recorded before-fix outputs above remain unchanged.
