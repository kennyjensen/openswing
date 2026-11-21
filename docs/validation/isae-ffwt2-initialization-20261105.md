# FFWT-2 initialization and bounded time pilot

The first selected FFWT-2 case now initializes and advances in time. There are
still **0/4,005 comparisons available** for this selected table: its archived
history starts at two seconds, while the latest complete checkpoint is at
1.02 seconds. The remaining FFWT-2 histories are not yet registered. The native
reference allowance is 5%; no numerical convergence gate was loosened.

## Source and declared setup

The original ISAE revision is `f62943df20e9e4d7d9f50e070477b22426b5f865`.
The selected files are under `4 - Aeroelasticity/FFWT - Flared Folding Wingtips Cases/FFWT-2-D - Effect of FFWT on Rolling Performance/FFWT10`:

- `FFWT_REMOVED_V15_DF21.asw`
- `FFWT_REMOVED_V15_ROLL_DF21.sh`
- `FFWT_REMOVED_V15_DF21.txt`

Despite its basename, this literal model includes two folding tips. The driver
sets speed 15 and control F1 to 21, selects constraint cell `4 23` followed by
the `C` preset, and commands 200 warm-up steps followed by 800 saved steps,
all at 0.01 seconds. The 801 exported rows span 2–10 seconds and contain roll
acceleration, roll rate, continuous aircraft bank, and two sensor bank angles.
Control values retain the source's native units. No stiffness or sensor was
modified, and no startup state was inferred from these outputs.

The [later command review](isae-ffwt2-time-tangent-20261106.md) identifies `C`
as the guide's frequency-calculation preset. The pilot's free-roll constraint
interpretation is therefore declared, rather than fully recovered from the
driver's final constraint table.

The pilot declares cosine counts 16 on the main beam and 8 on each tip,
zero incidence/sideslip/initial frame rates, the literal density 1.2256 and
gravity 9.81, current aerodynamic influences, circulation lag, and source
moving-airflow equations with Euler BDF2. These defaults and the cold
zero-local-rate equilibrium are **not authenticated historical startup**.
The report describes a held wing followed by release; a separately computed
held equilibrium below is a diagnostic, not the free-roll starting state.

The source inventory has eight parsed model/driver/output triples for the
DF21 free-tip variants. Many other literal models reject out-of-domain sensor
anchors. Their physical and output compatibility remains unresolved; the pilot
does not silently move those sensors or discard their outputs.

## Solver correction and evidence

Hinged equilibria previously discarded their factored Newton matrix after every
accepted correction. They now reuse it while the full-equation correction
contracts strongly. New load levels, weak contraction, damped steps, the age
limit, and principal rotation-coordinate branch crossings still force a fresh
matrix. All physical residuals, hinge laws, five-degree rotation limits, and
final tolerances are unchanged.

| Diagnostic | Before | After |
|---|---:|---:|
| Held-wing initialization | 82.55 s | 57.53 s |
| Reported residual evaluations | 3,465 | 1,921 |
| Accepted load levels | 18 | 18 |
| Final maximum normalized residual | 6.01e-13 | 4.26e-14 |
| Free-roll initialization | No result before 90 s cap | 75.95 s; residual 2.92e-13 |

Timings are local measurements, not browser or ASWING timing claims. The held
baseline includes dispatch preparation; the instrumented run starts after
network construction. All 9,568 common numerical result fields pass the
unchanged `2e-8 * (1 + abs(reference))` parity gate. Node positions differ by
at most 3.06e-16 m; hinge angles by 3.73e-11 degrees. This is solver parity,
not a comparison to archived ASWING output.

The free-roll equilibrium is saved separately and checked again by the ordinary
time-launch path. Initial 0–0.02 s integration takes 8.10 s; the next 0.1 s
checkpoint continuation takes about 8 s. Forty-step segments then reach
0.52 s and 0.92 s in 25.5 s and 32.0 s. A larger following segment reaches
1.12 s internally but hits its 90-second cap before returning a checkpoint.
That incomplete segment earns no comparisons. A shorter run safely retains
the state at 1.02 s.

At approximately 1.11 s the structured Newton direction needs the complete
time Jacobian. Its current source-equation fallback differences all 713 columns;
one rebuild takes roughly 30 s. This is the next performance issue, separate
from the corrected equilibrium startup. The retained checkpoint avoids repeating
the cold solve.

## Verification and remaining work

All **11 focused tests pass**. They cover fresh-matrix parity, exact positive/negative 200-degree
hinge solutions, mandatory refresh at rotation-chart crossings, source moving
airflow under prescribed and mixed frames, and failed-factor recovery. A
saved-result assessor retains every native target, rejects gaps, checks units
and continuous bank, and applies the shared 5% policy only after numerical gates
pass. It uses no time interpolation, phase shift, or angle-wrap adjustment.

One additional Pyodide/WebAssembly case passes using the shipped kernel: a
200-degree hinge equilibrium, 45 load levels, 215 reused corrections, and
mandatory refresh at the principal rotation crossings. Its full residual is
1.11e-16 and its maximum position error is 2.22e-16 m. Development and built
kernel files have matching hashes. This checks the numerical WASM runtime,
not the full application UI or the archived FFWT-2 trajectory.

The evidence directory is `artifacts/isae/ffwt2-pilot-20261105/`. Completed runs,
the interrupted complete-matrix experiment, timeout logs, the initial test
fixture error (three intervals, below the supported minimum), and corrected
test results are retained separately. The [machine-readable receipt](isae-ffwt2-initialization-20261105.json)
records the completed checks and remaining scope.

Still required: efficient complete time tangents, the full 2–10 s comparison,
time-step and mesh refinement, independent trajectory replay, historical
initialization review, a shared family adapter, and the other source histories.
No whole-family validation or full-browser UI verification is claimed.
