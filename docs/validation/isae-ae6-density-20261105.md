# AE-6 source-density correction and five-configuration comparison

The shared AE-6 adapter incorrectly reused Weight7a's density for every model.
Reading each original `Constant` block fixes that setup error. Eight fresh,
serial solves now pass **116/118 computed native components at 5%** across all
five runnable configurations. The only failed components are Weight7a's lowest
frequency on the two meshes. No production solver equations changed.

| Configuration | Declared IAS (m/s), native point 2 | Meshes | Passing components | Largest native error |
|---|---:|---|---:|---|
| Weight7a | 120.5 | 32/64 | 22/24 | Lowest frequency 39.54% / 42.40% low |
| Weight7c | 95.5 | 32/64 | 28/28 | 1.1942% coarse; 0.4672% fine |
| Weight7d | 130.5 | 32/64 | 36/36 | 3.2764% coarse; 3.8555% fine |
| Weight7e | 110.5 | 32 | 14/14 | 0.9187% |
| Weight7f | 90.5 | 32 | 16/16 | 3.9756% |

The failed-component median is **40.97%**, maximum **42.40%**. These are sampled
operating points, with repeated native cells on different meshes. Complete
flutter boundaries and whole-family validation remain unfinished.

## What was wrong

The original files specify these sea-level densities in their SI `Constant`
blocks, alongside gravity9.81 and sound speed340.21:

| Original configuration | Density (kg/m³) |
|---|---:|
| Weight0, Weight7a, Weight7c | 1.0771417304 |
| Weight7d | 1.1369256734 |
| Weight7e | 1.1956788587 |
| Weight7f | 1.1338334005 |

The [ASWING guide](../../.reference/aswing_doc.txt), lines394–406, defines the
`Constant` block and its sea-level atmosphere scaling. Lines2015–2025 identify
`!V` as indicated airspeed. At the declared zero altitude, each model's own
sea-level density makes true and indicated speed equal. The previous Weight7d
request used speed130.5 with density1.0771417304, giving indicated speed
**127.0226 m/s** and dynamic pressure **5.2584% below** the value implied by
its model and commanded indicated speed.

Only `condition.density` changes in the corrected Weight7d numerical request.
All source geometry, masses, stiffnesses, gravity, speed, aerodynamic settings,
shift, mode count, mesh and acceptance gates remain identical. Its five coarse
failures disappear:

| Native component | Archived ASWING | Previous wrong-density result | Corrected coarse result | Corrected error |
|---|---:|---:|---:|---:|
| Line12 real | −3.9954214 | −8.2295308 | −3.8645168 | 3.2764% |
| Line13 real | −32.303726 | −21.007619 | −32.807740 | 1.5603% |
| Line14 real | −7.6692107 | −9.1199465 | −7.5957982 | 0.9573% |
| Line14 imaginary | 68.45226 | 73.432933 | 68.232777 | 0.3207% |
| Line18 real | −14.187365 | −13.404803 | −14.156511 | 0.2175% |

The earlier **13/18 Weight7d result** remains a wrong-density diagnostic and
is superseded for native comparisons. Weight7a's two spectra and Weight7c's
coarse spectrum reproduce the earlier results exactly. Weight7e and Weight7f
are new sampled comparisons; their previously unrun jobs are not relabelled
as earlier failed solves.

The adapter now binds gravity, density and sound speed to original file lines
and tokens. Returned density, density ratio, altitude, sound speed, gravity,
indicated speed and dynamic pressure must satisfy the source-bound setup.
The numerical kernel already reads model atmosphere correctly; this correction
is in the validation adapter that constructed an overriding condition.

## Evidence and remaining scope

Six new configuration regressions first produced **three failures** for
Weight7d/e/f and three passes for the unaffected inputs. After the correction,
**41 focused tests pass**, including original parser/atmosphere agreement,
indicated-speed and dynamic-pressure checks, source integrity, blocked routes,
full-matrix artifact validation and corrupt-result rejection.

All eight fresh jobs pass the unchanged numerical gates. The independent
summary reopens full matrices and left/right vectors and rechecks **256 pencil
residuals, 128 mass pairings and 128 root-clamp checks**, plus source and code
hashes. A separate saved-data audit reconstructs all **118 native scalar
comparisons** from the original decimal tokens. No summary or completion audit
starts another physical solve.

The separate 0.1% component mesh criterion is still incomplete:

| Configuration | Passing mesh components |
|---|---:|
| Weight7a | 5/12 |
| Weight7c | 7/14 |
| Weight7d | 6/18 |
| Weight7e, Weight7f | Fine meshes not yet run |

Thus native agreement within 5% does not establish spatial convergence. Both
the original native tolerance and these stricter numerical gates remain visible.

The six historical modal ledgers retain **3,348 original scalar cells**. The
declared scope remains **446 jobs / 6,696 components**. Current fresh evidence
is **116/132 selected slots** including fourteen blocked Weight0 components,
or **116/6,696 so far**, with **6,564 further slots unrun**. Weight0's original
missing final `End` blocks 1,200 planned slots. The eight computations cover
**74 distinct native cells**, leaving 3,274 without predictions in this scope.
Historical and mesh-repeat ledgers are not independent observations; all six
model/driver/export triples also duplicate ST-4 files.

Historical startup, altitude, aerodynamic flags, node arrays and native mode
identity remain qualified. Fixed frame, zero-altitude source air, PG0, lag,
current influences and cosine32/64 are declared choices. Other positions,
complete speed sweeps, aggregate outputs, vacuum exports and exact flutter
onsets remain open. Ten families still lack shared comparison adapters.

The initially queued fine batch was cancelled after the density error was
identified. Its supervisor and worker terminated with no completed solve and
no adapter solve-request artifact. Its original interrupted report and last
progress snapshot remain retained. Corrected runs use separate directories.
All completed numerical jobs ran serially, with one BLAS thread, 90-second
worker limits and 512/768-MiB address caps for coarse/fine jobs. All workers
are reaped. No production module, browser build or distribution archive changed.

- [Independent shared summary](../../artifacts/isae/ae6-refinement-20261105/summary/summary.md)
- [Exact correction, errors and completion audit](isae-ae6-density-20261105.json)
- [Adapter](../../scripts/isae_suite_ae6.py)
- [Regression tests](../../tests/test_isae_suite_ae6.py)
- [Saved-data verifier](../../artifacts/isae/ae6-refinement-20261105/verify-refinement.py)
- [Earlier shared comparison, retained as historical evidence](isae-ae6-suite-20261105.md)
