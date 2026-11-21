# Daedalus: full current-source mesh refinement

The freshly trimmed **211-node / 164-lifting-panel** aircraft still misses
Drela's yaw dip. At **1.157378 Hz**, yaw changes from **0.074218 to 0.074057
deg/s/F3**, a **−0.217% amplitude change**, against **0.033986** in the drawing.
This is a complete coupled response on the new equilibrium, extending the
earlier [fixed-motion aerodynamic study](daedalus-aero-resolution-20261113.md)
and [first-variation projection](daedalus-aero-feedback-20261113.md).

**Roll and bank remain mesh-sensitive.** At 1.5 Hz their amplitudes change by
−15.92% and −13.64%; their complex changes are 19.44% and 20.30%. Two grids
and six frequencies do not establish full-spectrum or asymptotic convergence.
The small yaw change therefore weakens a resolution explanation for the yaw
dip without validating the complete response.

The subsequent [cancellation analysis](daedalus-mesh-zeros-20261114.md)
locates the roll zero independently on both current matrices. Its movement
accounts for most of the 1.5 Hz roll difference, leaving 3.84% after an
unfitted zero-factor comparison. Bank follows the changed roll response.
This explanation does not replace the actual responses, establish a third
grid's convergence or resolve the combined discretization/trim contribution.

![Four-output comparison](../../artifacts/daedalus-structural-resolution-20261113/comparison/comparison.png)

[Vector figure](../../artifacts/daedalus-structural-resolution-20261113/comparison/comparison.svg),
[six-frequency data](../../artifacts/daedalus-structural-resolution-20261113/comparison/comparison.csv)
and [complete checks](../../artifacts/daedalus-structural-resolution-20261113/comparison/result.json).
The fine-grid circles are actual solved points, not an interpolated fine-grid
sweep. Curves use the application's VibeLattice color sequence and logarithmic
major/minor grids. Reference phase and operating-point settings remain unknown.

## Matched model and refinement

Both calculations use the literal public `dae.asw`, 6.7 m/s, PG Mach 0.1,
SEGSPL properties, `drela-moving-airflow-v1` source beam equations, moving
influences, aerodynamic lag, propeller plume, bilateral braces and the same
seven steady-level trim equations. Mass/stiffness distributions, control
derivatives, aerodynamic properties and attachment definitions are unchanged.
Gravity remains Earth-fixed; it is not replaced by a fixed body-axis vector.

Every original station survives. Lifting intervals are bisected in their
whole-beam Glauert angle; body intervals are bisected in material position.
The new beam network recomputes its properties and loads on those intervals.
Thus this is **combined structural, aerodynamic and body discretization
refinement**, not an isolated structural-only experiment. The prior
fixed-structure studies remain the separate aerodynamic controls.

| Quantity | Original | Refined |
| --- | ---: | ---: |
| Structural nodes | 108 | 211 |
| Beam intervals | 103 | 206 |
| Circulation unknowns | 82 | 164 |
| Full dynamic coordinates | 2,044 | 3,980 |
| Trim residual, maximum scaled component | 1.902e−10 | 8.562e−10 |
| Alpha | 3.05636° | 3.00735° |
| F2 | −10.03944 | −9.83339 |
| F3 | 0.092798 | 0.049377 |
| Engine input | 6.19950 | 6.12324 |

The initial interpolated pose and repeated internal loads/circulation were
explicitly provisional. Full residual corrections decreased
`0.735313 → 3.045e−4 → 2.118e−4 → 2.249e−5 → 3.279e−7 → 8.124e−9 → 8.562e−10`.
The unchanged trim acceptance threshold is 1e−9. The starting correction
matrix has a column-scaled reciprocal-condition **lower bound 4.149e−9**,
above the unchanged 1e−10 rank threshold. This certificate concerns that
starting tangent; the final state is separately accepted by its full residual.

The earlier [cruise-mesh study](daedalus-rudder-cruise-mesh.md) used the older
midpoint/natural formulation and different station rules. Its 32-panel result
is retained as historical evidence, not substituted for this fresh calculation.

The [authoritative index](aswing-authoritative-references.md) and source catalog
were consulted. Drela's steady Eqs. 48/51/54 and 150–161 govern the source
structural balances and lifting-line discretization; the unsteady extension
governs the moving loads, lag and full frequency-response pencil. No parameter
was fitted to the drawing and no physical equation or production default changed.

## Paired response values

Yaw magnitudes are deg/s per native F3 unit. Signed amplitude changes divide
by the original magnitude; complex mesh changes divide by the refined
magnitude and retain both amplitude and phase differences.

| Frequency, Hz | Original yaw | Refined yaw | Drela drawing | Yaw amplitude change | Yaw complex change |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0.1 | 0.121763 | 0.121697 | 0.118238 | −0.0538% | 2.0025% |
| 1.0 | 0.075499 | 0.075430 | 0.058746 | −0.0913% | 1.0441% |
| 1.1 | 0.073769 | 0.073598 | 0.038682 | −0.2312% | 0.8032% |
| 1.157378 | 0.074218 | 0.074057 | 0.033986 | −0.2169% | 0.6563% |
| 1.3 | 0.079649 | 0.079635 | 0.049032 | −0.0175% | 0.4539% |
| 1.5 | 0.094316 | 0.094416 | 0.081818 | +0.1056% | 0.6189% |

At the drawing's yaw minimum, refined roll/sideslip/bank magnitudes are
**0.0233734 deg/s/F3, 0.0304697 deg/F3 and 0.00300049 deg/F3**. Their amplitude
changes are **−3.490%, +0.506% and −2.957%**. The larger roll/bank changes at
1.3–1.5 Hz remain explicit in the machine-readable comparison and above.
The six points do not locate an exact refined minimum or check the 9 Hz peak.

Fresh original-grid solves reproduce the prior saved complex outputs within
**3.184e−13** at the five exactly shared frequencies; 1.5 Hz is an additional
fresh original-grid comparison. The final-code dip result is bit-identical to
the preceding successful sparse-LU observation at that frequency.

## Assembly, solve and code validation

Geometry assembly now accepts an optional ordered subset of nodal columns.
Each selected column still includes every aerodynamic source/receiver and the
full residual. The default remains all columns. A deliberately reordered
12-column selection reproduces the saved original full matrix exactly;
complete-residual probes and six invalid-subset checks also pass.

The refined trim and dynamic geometry blocks are assembled in small serial
jobs. Ordinary blocks contain 64 columns; a small fin-tip/propeller-attachment
range uses eight-column complete-residual jobs. A 1e−5 perturbation was too
large for some refined-tip derivatives, and the field decomposition also
rejected a jet-boundary crossing. The accepted complete-residual columns use
fourth-order widths **1e−6 / 5e−7** and the unchanged **2e−5** step-agreement
gate. No rejected derivative was accepted by loosening its tolerance.

After joining all columns, three independent full-residual directional checks
give maximum relative errors **1.906e−8** for the trim tangent,
**5.554e−8** for dynamic A and **3.644e−11** for dynamic M. The original gates
remain 2e−5 for state derivatives and 2e−6 for rate derivatives.

The production exact beam elimination removes 1,266 fixed equations from the
factorization, followed by 1,266 diagonal velocity definitions. A **1,448**
dimensional factor recovers all **3,980** coordinates; no mode or matrix entry
is discarded. At the dip, the full-pencil reciprocal-condition estimate is
**7.145e−9**, backward error **1.009e−20** and scaled residual **3.735e−18**.
Every frequency retains the original conditioning and full-equation gates.

The work also reduces temporary storage in the production Python solver:

- Release the row-only scaled pencil once its fully scaled counterpart exists.
- For exact beam elimination, retain the original pencil for the physical
  iterative-refinement defect and final residual checks, after obtaining the
  scaled norm, instead of keeping a second full scaled pencil through LU.
- Scale an owned reduced CSC matrix's data in place, preserving cached A/M.
- Release the pre-velocity-elimination matrix before factoring its complement.

All **23 existing harmonic-structure tests** pass in eight final serial jobs,
including independent inverse/transpose/adjoint comparisons, pole/fallback
gates, physical wing/body/engine/joint cases, controller/damping coupling and
factor reuse. An exploratory dense-LU fallback was tested during diagnosis
but **removed** after the native allocation cause was identified. Final solves
use sparse LU. Browser/WASM builds and tests remain held, so this is not a
browser memory or timing benchmark.

## Resource limits, retained attempts and reproduction

Every numerical child uses one BLAS thread, **512 MiB address space, 15 CPU
seconds and 25 wall seconds**, with a monitoring parent that reaps it.
The combined trim assembly/rank attempt exhausted its cap; separate assembly
and rank jobs pass unchanged gates. Initial harmonic attempts also exhausted
the cap and are retained with their terminal receipts.

The allocation profile found a pre-factorization **509,344 KiB virtual** size
despite only about **192.2 MiB resident memory after allocator trimming**.
Returning unused pages reduced resident memory but did not remove their
address-space mappings. Starting the native diagnostic with
`MALLOC_MMAP_THRESHOLD_=131072` allows large temporary allocations to release
their mappings; measured pre-factorization virtual size becomes **401,080 KiB**.
This is a process-local glibc setting, explicitly recorded in each new plan,
not a raised resource limit or a numerical approximation.

The final three-frequency response job uses **4.121 CPU seconds, 6.585 wall
seconds and 240.672 MiB peak resident memory**. The successful single dip solve
uses 3.181 CPU seconds. These are shared-host native observations. All attempted
jobs and parent sessions were reaped; no background solver was left running.

The first mesh-initialization attempt incorrectly passed the current body
gravity vector to the constructor, freezing its direction. `initial` and its
`trim-geometry-0` are **superseded**. `initial-v2` preserves the original null
gravity override and checks gravity, loads, constraints and brace mode against
the original launch packet. All accepted matrices derive from `initial-v2`.
The retained `trim-geometry-v2-768`, its `-small` retry and `trim-fd-v2-768`
record the jet-boundary/step-resolution failures; their corrected replacements
are explicitly selected in the accepted assembly plan. Failed response jobs
`response-dip` through `response-dip-v8` contain no accepted response.

The [bounded driver](../../scripts/check_daedalus_structural_resolution.py)
retains runner snapshots, input hashes, arrays, logs and terminal receipts.
Accepted anchors are the [trim](../../artifacts/daedalus-structural-resolution-20261113/trim-correct-v3/result.json),
[full matrices](../../artifacts/daedalus-structural-resolution-20261113/assembled/result.json),
[neighboring frequencies](../../artifacts/daedalus-structural-resolution-20261113/response-neighbors/result.json)
and [final response](../../artifacts/daedalus-structural-resolution-20261113/response-final/result.json).
The [final evidence audit](../../artifacts/daedalus-structural-resolution-20261113/comparison/verification.json)
checks retained job receipts, input hashes, complete column coverage and final
regression-test receipts without rerunning the numerical jobs.
Use a fresh tag, with the saved matrix and accepted state:

```sh
MALLOC_MMAP_THRESHOLD_=131072 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 .venv/bin/python \
  scripts/check_daedalus_structural_resolution.py response --tag fresh-dip \
  --seed artifacts/daedalus-structural-resolution-20261113/trim-correct-v3/state.json \
  --matrix artifacts/daedalus-structural-resolution-20261113/assembled \
  --frequencies 1.15737773741517
```

The next investigation should use this checked coupled operator to examine
the remaining dynamic/reference-setup differences. Increasing resolution
alone has not deepened yaw's dip materially. Roll/bank resolution, the original
2008 operating settings and native Bode agreement remain open. ISAE fractions,
scope denominators and progress history are unchanged.
