# P-2 forward-flow input recovery

The four declared input reconstructions reproduce **312/312 archived CT and
efficiency values at the provisional 5% tolerance**. The largest discrepancy is
0.633%. No production equation or physical parameter was tuned to an ASWING
acceptance curve. This is a conditional reconstruction of the report's driving
inputs, not a claim that the missing original driver has been recovered.

| Configuration | Archived comparisons at 5% | Largest relative error |
|---|---:|---:|
| Two blades, nominal 2000 RPM | 48/48 | 0.05166% |
| Two blades, nominal 4000 RPM | 108/108 | 0.02009% |
| Four blades, nominal 2000 RPM | 48/48 | 0.63226% |
| Four blades, nominal 4000 RPM | 108/108 | 0.04080% |

Each configuration includes three blade-drag choices (constant at zero advance,
constant at maximum advance, and the report's quadratic extension), both CT and
efficiency, and every stored coordinate. Exact duplicate graphics in the
two-blade 2000-RPM figures count once. Experiments identify input rows and supply
the report's original calibration inputs; they are not acceptance targets.

## Recovered sources

The [official UIUC Volume 2 database](https://m-selig.ae.illinois.edu/props/volume-2/propDB-volume-2.html)
provides all 48 forward-flow power-coefficient rows. Their J/CT coordinates equal
the original figures' experimental coordinates exactly. Four additional J=0
rows are identified in the already pinned P-1 static tables by exact CT values:

| Configuration | Static table RPM | Static CP | Forward-flow source |
|---|---:|---:|---|
| 2B / 2000 | 1953.333 | 0.083298 | 0769rd / 2018 RPM |
| 2B / 4000 | 3950.000 | 0.077088 | 0771rd / 4042 RPM |
| 4B / 2000 | 1958.333 | 0.154376 | 1087ga / 2034 RPM |
| 4B / 4000 | 3938.333 | 0.147676 | 1089ga / 4036 RPM |

[The source manifest](isae-p2-sources.json) pins downloaded bytes and SHA-256
hashes. Run `scripts/fetch-isae-p2.py` after the existing P-1/reference fetches to
restore the local tables. All eight original FIG hashes and decoded-series
hashes are checked. The identity `eta = J CT / CP` binds every otherwise unlabeled
CT curve to its labeled efficiency curve; no series is selected by agreement.

## Drag-input reconstruction

Part 2, pages 13–16, describes reverse actuator-disk calibration from measured
CT/CP and a quadratic CdA model. The precise fitting program is absent. We
declare unweighted quadratic least squares on the original **forward-flow rows
only**, using nominal diameter D=0.2286 m. The static row supplies only the
zero-advance power input; it does not participate in the advance-flow fit.

For each measured pair, use Drela's Technical Description equations 109 and
111–114, with `J = V/(nD)`, `lambda = J/pi`, and `d = delta_V/(nD)`:

```
d = -J + sqrt(J² + 8 CT / pi)
CP_i = (pi/4) [J + (1 + 5(J/pi)²)d/2] [J + d/2] d
CdA = 8 D² (CP - CP_i) / [sqrt(J² + pi²) (J² + 3 pi²)]
```

The recovered coefficients round to **all twelve printed coefficients** in the
four figure legends. The source-input function accepts measured J/CT/CP and
diameter only; it has no archived model-target argument. The constant choices
use the resulting quadratic at J=0 and the final measured J, as indicated by
the source labels and coincident endpoints. Their historical exact values
remain qualified. A separate diagnostic retains predictions from the literal,
rounded legend coefficients without substituting them into the primary count.

The adapter calls the existing production `engine_load` with `V=J n D` and
`P=CP rho n³ D⁵`. It preserves negative thrust/efficiency, and independently
recomputes thrust momentum, power balance, viscous/inviscid power, torque,
requested power, force direction and clipping from each saved production state.
Those numerical gates retain 2e-12; only reference-output acceptance uses 5%.

## Verification and reproduction

The focused P-2, P-1 and reference-policy regression run passes **85 tests**.
It covers all 312 output checks, density/RPM normalization invariance, complete
input/target accounting, exclusion of model targets from calibration, and
rejection of altered sources, coefficients, physical states, gates and results.
The normal suite run completes all four jobs serially with a 60-second worker
cap and one BLAS thread. Worker times are 13.56–19.53 seconds including imports
and source verification; these are not isolated engine-solve timings.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  .venv/bin/python scripts/run-isae-suite.py --adapters p2 --cases P-2 \
  --workers 1 --timeout-seconds 60 --output-dir artifacts/isae/p2-new-run
.venv/bin/python scripts/summarize-isae-suite.py \
  --run artifacts/isae/p2-new-run --output-dir artifacts/isae/p2-new-summary
```

The runner retains a nonzero exit status while other suite scopes remain open;
the saved P-2 jobs are all `computed` with 312/312 numerically valid matches.
[Shared run](../../artifacts/isae/p2-recovery-20261105/shared/report.json),
[independent summary](../../artifacts/isae/p2-recovery-20261105/summary/summary.md),
and [focused test log](../../artifacts/isae/p2-recovery-20261105/tests-fixed.log)
are retained. Production kernels, browser builds and distribution archives are
unchanged by this validation work.

The [completion receipt](isae-p2-recovery-20261105.json) confirms all 312 accepted
scalars, 12 strict matches, 1,248 physical checks and four reaped workers. The
saved-result audit verifies source/kernel hashes, recomputes scalar acceptance,
and checks all 42 status rows and their links. Nine families remain without
shared adapters. No solver or test process remains running from this batch.

## Scope and remaining uncertainty

All 24 archived model curves and 52 input coordinates are included. There are
156 distinct production states because CT and efficiency share a state. Another
156 states retain the rounded-input diagnostic. Counts are output comparisons,
not independent experiments. Twelve zero-efficiency comparisons meet the strict
2e-12 absolute gate; nonzero differences remain explicitly recorded.

The variable-CdA curve is the report authors' extension of ASWING; the constant
curves exercise its documented engine model directly. This does not validate
independent power prediction, aircraft coupling, propeller wakes, P-factor or
browser behavior. The primary UIUC coefficients use the measured diameter;
nominal diameter is the declared report/P-1 reconstruction convention, not an
assertion that these are identical. The exact upstream regression, rounding and
solver settings remain unavailable. No whole-family validation is declared.

The retained preliminary experiment in
`artifacts/isae/p2-recovery-20261105/pilot.json` included the static row in the fit
and did not reproduce the printed coefficients. Its `literal_rounded` label
means the rounded coefficients of that trial, not the literal figure legends.
It is exploratory evidence only and supplies no accepted comparisons. The
registered adapter instead binds the actual figure labels and excludes the
static calibration row; the independent input-recovery receipt is retained.
