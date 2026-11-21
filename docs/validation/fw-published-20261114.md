# Current FW comparison with Drela's published result

**Subsequent setup correction:** these runs used current physics but retained
the saved state's legacy `all-breaks-v0` mesh. They do not establish fresh
browser-default mesh agreement. See the
[fresh-mesh verification](fw-current-mesh-20261114.md). Numerical values and
the original immutable receipts below are unchanged.

The user requested an FW comparison after confirming that the repaired browser
Bode calculation runs. Drela's [FW example](https://web.mit.edu/drela/Public/web/aswing/)
links a [flutter root map](https://web.mit.edu/drela/Public/web/aswing/root_map_fw.pdf),
not a frequency-response gain/phase plot. This study therefore checks the
current equations against the published trim and flutter branch first. It
does not claim agreement with an unavailable native FW Bode curve.

At 64 ft/s, the current 42-panel model predicts **2.69366 Hz**, versus published
**2.70232 Hz**, a **−0.3203%** frequency difference. Growth is **−0.00198/s**,
versus digitized **+0.00579/s**: both are nearly neutral. The figure explicitly
annotates flutter onset at 64 ft/s. The current branch decays at 62 ft/s and
grows at 66 ft/s, agreeing with the published trend. No aircraft properties
or governing equations were changed or fitted to obtain these results.

![Current FW flutter comparison](../../artifacts/fw-published-20261114/report-fixed/comparison.png)

[SVG](../../artifacts/fw-published-20261114/report-fixed/comparison.svg) ·
[Numerical comparison](../../artifacts/fw-published-20261114/report-fixed/result.json)

## Reference and setup

Fresh official downloads are retained in
[`reference/fw-published-20261114/`](../../reference/fw-published-20261114/sources.json).
The aircraft exactly matches `examples/fw.asw`, and the root-map PDF exactly
matches the previous reference used by
[`fw-reference.json`](fw-reference.json). The PDF was visually inspected again,
including its twelve operating-point rows and the 64 ft/s onset annotation.
The extraction records estimated root-coordinate uncertainty of 0.01/s and
rounding in the printed trim table. The original mesh, executable version and
some numerical settings are not specified.

The [authoritative index](aswing-authoritative-references.md) and checksummed
catalog were consulted. The extended manual's displayed Bode example is
Daedalus (Figure 1.10); the checked FW website example supplies modes rather
than a forced-response reference.

Settings are literal `fw.asw`, free flight, the file's atmosphere and
gravity, midpoint structural equations, natural beam interpolation, the
preserved legacy mesh recipe, frozen
influence coefficients, aerodynamic lag, and the default 0.25 wake-core ratio.
The equilibrium solves for angle of attack, elevation and control F2 to zero
the x/z force and pitching-moment residuals. Straight, unpowered glide is
**inferred** from the printed attitude, incidence and drag/lift values; the
original constraint file is unavailable.

Previously saved physical fields were used only as initial guesses. Every
case was corrected using the current equations, with residual below 3.13e−11
and a kinematically steady base. No prior eigenvalue or transfer-function
result is counted as a current result.

## Mesh refinement at 64 ft/s

| Requested mesh setting | Actual lifting panels | Frequency, Hz | Frequency error | Growth, 1/s | Growth difference, 1/s |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 8 | 18 | 2.61545 | −3.2146% | +0.41442 | +0.40863 |
| 16 | 26 | 2.67122 | −1.1509% | +0.17638 | +0.17059 |
| 32 | 42 | 2.69366 | −0.3203% | −0.00198 | −0.00776 |
| Published ASWING | Unspecified | 2.70232 | — | +0.00579 | — |

Coarse meshes overpredict this mode's growth substantially. Refinement brings
both parts of the eigenvalue toward the published value. This is evidence of
mesh sensitivity, not proof that 42 panels is the asymptotic solution. Growth
near zero is reported as an absolute difference; a relative percentage there
would misrepresent the practical discrepancy.

The 42-panel trim at 64 ft/s is:

| Quantity | Current OpenSwing | Printed ASWING |
| --- | ---: | ---: |
| Angle of attack, deg | −1.86021 | −1.85 |
| Elevation, deg | −4.64656 | −4.64 |
| F2 | −1.59745 | −1.6 |
| CL | 0.336804 | 0.337 |
| CD | 0.0163921 | 0.0164 |

Lift differs by −0.0581% and drag by −0.0483%. Some angles differ by more than
the table's half-rounding interval; the reconstructed trim is close, not an
exact recovery of the original operating-point file.

## Flutter branch on either side of onset

All rows below use the current 42-panel, 834-state model.

| Speed, ft/s | Current frequency, Hz | Published frequency, Hz | Frequency error | Current growth, 1/s | Published growth, 1/s |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 62 | 2.75981 | 2.76955 | −0.3519% | −0.42252 | −0.41088 |
| 64 | 2.69366 | 2.70232 | −0.3203% | −0.00198 | +0.00579 |
| 66 | 2.64019 | 2.64798 | −0.2940% | +0.44422 | +0.45139 |

Linear interpolation of the nearest sampled growth-sign bracket gives
64.009 ft/s for OpenSwing, versus 63.972 ft/s from the digitized reference
points and the figure's rounded 64 ft/s annotation. These are interpolated
estimates, not separately solved flutter boundaries. Growth differences over
the three speeds are 0.0072–0.0116/s.

The full descriptor matrices were assembled with a 1e−5 linearization step.
A local full-pencil shift-and-invert search near −0.1 + 17i/s finds the
flutter branch without modal reduction. Maximum left/right pencil backward
error is 6.35e−16 across these searches. This checks the eigenvalue solution
against the assembled equations; it does not independently validate every
Jacobian entry. Derivative-width refinement and finer meshes have not been
rerun in this current study.

## Reproduction and limits

[`check_fw_published_20261114.py`](../../scripts/check_fw_published_20261114.py)
separates trim, matrix assembly and roots into small serial jobs. For example,
using a fresh tag for each immutable output:

```sh
MALLOC_MMAP_THRESHOLD_=131072 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  .venv/bin/python scripts/check_fw_published_20261114.py trim \
  --tag new-trim-32-64 --panels 32 --speed 64
```

The `matrices` mode takes that job's `state.json` with `--seed`. The `roots`
mode takes the matrix job's `pencil.npz` with `--pencil`. Saved runner copies,
input hashes, outputs and reaped-process receipts are in
[`artifacts/fw-published-20261114/`](../../artifacts/fw-published-20261114/).
All 15 solver jobs completed under 512 MiB address space, 15 CPU seconds and
25 wall seconds per job, using one BLAS thread. Maximum observed CPU time was
6.79 s, wall time 15.73 s and peak RSS 100,248 KiB. No background solver was
started.

The bounded plotting job verifies current production/source pins and saved
results. Its initial check rejected the first trim's earlier CLI script;
that script predates addition of the matrix/root commands. After confirming
that all its calculation definitions are unchanged, the report verifies each
immutable runner separately. The failed receipt is retained; no solver result
was replaced. Both plotting processes were reaped, and the final plot was
visually inspected.

This is a comparison of one mode at three of the twelve published speeds,
plus three meshes at 64 ft/s. Other mode families and the rest of the speed
range remain unchecked by the current study. FW Bode magnitude, phase,
control forcing and output recovery need their own reference; root agreement
alone cannot validate them. It also does not resolve the Daedalus dip.
Browser/build checks remain on hold. ISAE fractions and comparison scopes
are unchanged.
