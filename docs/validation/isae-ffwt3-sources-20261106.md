# FFWT-3 source and attachment audit

FFWT-3 is now registered in the shared runner. All **27 jobs are blocked**:
**0/36,462 required scalar slots pass**. Of these, **35,256 values actually
exist in 26 archived histories**; the remaining **1,206 slots** belong to a
driver whose output is missing. No aerodynamic or structural solve was run for
this family, so a numerical error percentage is unavailable.

The 5% native-reference allowance is retained. It cannot make missing or
uncomputed results pass. The six channels are reference incidence, lift, CL,
sensor-1 normal force, sensor-1 local chordwise moment, and sensor-2 bank.
Every row, including startup and near-zero values, remains required. MATLAB
peak reductions and plots are derived evidence, not additional history values.

| Original history group | Files/jobs | Retained native values | Additional unavailable slots |
|---|---:|---:|---:|
| Ordinary 201-row histories | 24 | 28,944 | 0 |
| `Free_Sweep_10_A-10` | 1 | 4,206 | 0 |
| `Free_Sweep_10_A30` | 1 | 2,106 | 0 |
| `Free_Sweep_30_A-10` missing output | 1 | 0 | 1,206 |
| Total | 27 | **35,256** | **1,206** |

## Confirmed attachment incompatibility

All six `.asw` files parse with the current Drela interpolation policy. Their
literal joint records are identical:

```text
1 2   .6591   .001  3
1 3  -.6591  -.001  3
```

The chord distributions define these beam parameter ranges:

| Models | Main beam | Right tip | Left tip | Out-of-range joint attachments |
|---|---|---|---|---:|
| Free/Sprung/Stiff, 10° | −.6591 to .6591 | .6591 to .856 | −.856 to −.6591 | 2 per model |
| Free/Sprung/Stiff, 30° | −.5725 to .5725 | .5725 to .711 | −.711 to −.5725 | 4 per model |

Fresh meshing at nominal 8 and 16 confirms all twelve requests reject an
out-of-range attachment. The sensor stations themselves are **inside** their
beam ranges. Sensor 3 is requested by the drivers but is absent in both the
models and exports; it is not invented as another output channel.

The reviewed ASWING guide defines joints by their specified beam stations but
does not establish an endpoint-clamping or extrapolation convention for these
inputs. This is an unresolved native-compatibility/source-pairing issue, not
proof that native ASWING rejects the files. Automatically moving the stations
would change the model without evidence. Eight cached upstream history trees
contain identical blobs for the 58 selected models, shell drivers and tables;
no alternate joint definition was recovered in that inspected history.

## Additional source differences

`Free_Sweep_10_A-10.sh` commands .01 s × 200 steps, but its table has 701 rows
through 2.45 s. `Free_Sweep_10_A30.txt` has no matching driver.
`Free_Sweep_30_A-10.sh` has no matching table; its 201 × 6 unavailable slots
remain explicit rather than disappearing from coverage.

The drivers specify an initial steady solve, speed 20 m/s, and type-5 gust
parameters `-10 0 8 .75`. The documented gradient-length convention places
gust onset at .5 s and its peak at .9 s. The archived Stiff/10°/A0 lift peaks
at .91 s, consistent with that interpretation. No gust-length or phase change
is justified by this audit. Exact historical node spacing, operating defaults
and full constraints still need correspondence.

## Verification and reproduction

The focused adapter/acceptance run passes **78 tests**, including preservation
of missing values, source-coordinate checks, literal mesher rejection, and
rejection of fabricated predictions. The shared runner completes all 27
source-only jobs in 14.07 s. Its independent summary verifies zero computed
values and the full 36,462-slot denominator. Production kernels are unchanged.

A subsequent focused runner/summary/AE-5 regression selection passes 61 tests.
An earlier broader regression invocation reached its 60-second cap; it is not
counted as a passing suite. All completed and interrupted processes were reaped.

Evidence is under
[`artifacts/isae/ffwt3-source-audit-20261106/`](../../artifacts/isae/ffwt3-source-audit-20261106/):
`literal-model-audit.json`, `history.json`, `suite/`, and `summary/`.
The summary's other 40 families were not selected in this run; that does not
mean they all lack adapters.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  .venv/bin/python scripts/verify-isae-ffwt3-sources.py --output-dir NEW_AUDIT
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  .venv/bin/python scripts/run-isae-suite.py --adapters ffwt3 --cases FFWT-3 \
  --workers 1 --timeout-seconds 30 --output-dir NEW_RUN
.venv/bin/python scripts/summarize-isae-suite.py --run NEW_RUN --output-dir NEW_SUMMARY
```

The runner returns exit code 1 when comparisons remain open; the audit summary
returns 0 after successfully verifying that open status. No whole-family
validation claim follows from successful source accounting.
