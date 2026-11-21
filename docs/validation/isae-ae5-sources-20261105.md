# AE-5 source correspondence and literal-model diagnostic

AE-5 now retains **587 blocked scalar comparisons** in the shared runner:
532 eigenvalue components and 55 flutter/divergence boundary values. No native
comparison passes are claimed. A separate solve of the literal first driver
condition converges and passes numerical modal checks; it does not establish
the missing historical correspondence.

| Source | Required scalar comparisons | Current status |
|---|---:|---|
| `Flutter_Boundaries/eig.txt` | 532 | 266 complex rows at 29 indexed operating points; no authenticated speed mapping |
| `Flutter_Boundaries/Analysis.m` | 46 | Explicit ASWING speed/frequency arrays for three laminates; exact historical model/configuration unpaired |
| Report Tables 5 and 6 | 9 | Six flutter speed/frequency values and three divergence speeds; incidence/startup correspondence unresolved |
| Total | **0/587** | Source pairing blocked; no meaningful solver-error percentage yet |

All real and imaginary components remain required, including real poles and
tiny damping values. Experimental curves are not acceptance targets. Static
CSV/plot material remains in the complete source catalog but is outside this
modal/boundary denominator. The `Analysis.m` arrays and report tables are
distinct source datasets; no values are substituted or averaged to obtain a
match.

## Evidence that the inputs cannot yet be paired directly

The original shell script commands 22 operating points, IAS 9 through 30 m/s,
with sideslip 15 degrees, wall flag 1 and normal `[0,0,1]`, and requests 16 modes
around `0+200i`. The saved modal file contains 29 indexed points. It provides no
speeds or node arrays. Assigning a speed from its row index would therefore be
an unsupported reconstruction.

The literal model also differs materially from the report's Table 10:

| Property | Literal `[03_90].asw` | Report, `[0_3/90]_s` |
|---|---:|---:|
| GJ | 8000 | 1.2 |
| EInn | 2.5 | 18499 |
| EIcn | 0 | 0.0023 |

For GJ, the file's `0.8` scale multiplies `1.0E4` at both data stations. The
production parser confirms 8000; this is not a column-reading discrepancy.
The other model in `[0_3_90]_S` has different geometry/material inputs and an
unterminated `Engine` block. It is retained unchanged and rejected by the parser.

The repository's
[directory-renaming commit](https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation/commit/a58ec61bbafb22f9915ed4188b34bc35727e05bc)
and its parent were checked. The model, driver and modal output have identical
Git blob hashes before and after that rename. This review does not claim to
exhaust every historical branch. Raw API responses are retained under
`artifacts/isae/ae5-source-20261105/`.

The report's same-bench statement covers AE-2, AE-5 and AE-7, but the retained
models differ among those folders. For example AE-7 `wing1.asw` has GJ=1.2 and
EInn=18500, while other similarly named files have different coupling or
torsion-axis offsets. Selecting or modifying a model solely because it gives a
better frequency match would not authenticate the original case.

## Actual numerical diagnostic

The literal AE-5 model was solved at its first commanded condition: IAS 9 m/s,
beta 15 degrees, rho 1.23 kg/m³, gravity 9.81 m/s², wall normal +z. The current
comparison declares fixed frame, PG0, nominal cosine32, pointwise circulation,
current influence matrices, aerodynamic lag and the current documented stall
defaults. The complete source was passed unchanged to the production bridge.

The coupled equilibrium and full 645-state modal problem completed in **14.15
seconds** of solver time. All 16 selected modes satisfy independently recomputed
full A/M right and left equations (limit 1e-8), mass normalization (1e-6), and
clamp conditions (1e-8); the fresh base residual satisfies 1e-7. Full matrices,
vectors, inputs, source/kernel hashes and residual proofs are retained. There
is no eigenvalue-to-native assignment, so this contributes **zero** reference
passes. The model's mathematical consistency and historical validation remain
separate conclusions.

Reproduce the single bounded diagnostic with one BLAS thread and an external
time/address cap:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  timeout --kill-after=5s 90s prlimit --as=536870912 -- \
  .venv/bin/python scripts/verify-isae-ae5-source.py \
  --output-dir artifacts/isae/ae5-new-literal --nominal 32
```

The shared source ledger is selected with `--adapters ae5 --cases AE-5` in
`scripts/run-isae-suite.py`. Its blocked route imports no production/numerical
code and performs no physics. The 5% reference allowance cannot convert these
unavailable comparisons into passes. No kernel, browser bundle or distribution
archive was changed.

Verification completes with **39/39 AE-5/P-2 regression tests**, the shared
runner's two blocked source jobs, and an independent saved-result audit. The
latter reopens all 645-state matrices/vectors and recomputes 64 modal metrics;
it also verifies source/kernel hashes, all 587 unavailable comparisons, and the
42-row status file. All processes from this batch have exited.

- [Completion receipt](isae-ae5-sources-20261105.json)
- [Literal diagnostic](../../artifacts/isae/ae5-source-20261105/literal-n32/report.json)
- [Shared source ledger](../../artifacts/isae/ae5-source-20261105/shared/report.json)
- [Independent summary](../../artifacts/isae/ae5-source-20261105/summary/summary.md)
- [Regression log](../../artifacts/isae/ae5-source-20261105/tests.log)

Next steps are to recover an independently authenticated original model/speed
mapping, or to define a separate report-based bench with every reconstruction
explicit. The latter would remain conditional and must retain both original
boundary datasets rather than tuning a model to one set of outputs.
