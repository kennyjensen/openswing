# AE-4: later modal branches and real-pole classification

The original undeformed, zero-incidence sweep now has **31/32 conditional
eigenvalue-component matches at 5%** at commanded IAS 80, 90, 100 and 108 m/s,
on both nominal 40- and 80-interval meshes. Every solve passes its original
physical/source checks. The full matrices and all four selected roots remain
retained. No production equation, eigenvalue, tolerance or model input changed.

Together with the retained [40 m/s anchors](isae-ae4-refinement-20261105.md)
and [69–70 m/s crossing](isae-ae4-crossing-20261105.md), this gives **63/68**
across seven speeds and two meshes: 34 distinct native scalar targets repeated
on two meshes. These are conditional component matches, not whole-family
validation, a completed speed sweep, or shared-runner registration.

The eight new jobs were specified before execution. They retain the literal
`2-Flutter_Undeformed/Pazy_wing.asw`, solid wall, fixed frame, alpha/beta zero,
file sea-level density 1.23, Mach zero, lag enabled, updated influences,
pointwise circulation and moving-airflow structural equations. Nominal cosine
intervals 40/80 give 41/81 elements because the material boundary is retained.
The original `NN 4`, shift `0 + 200i`, full constraint equations and derivative
step `1e-5` remain unchanged. Historical flags and exact node placement remain
unknown. The literal insertion stack maps IAS to native index `IAS + 1`; the
author's plotting helper instead labels the operating index itself as speed.
This correspondence is declared, not chosen by agreement.

| IAS (m/s) | Native index | Nominal 40 intervals | Nominal 80 intervals | Largest frequency error | Largest real-component error |
|---:|---:|---:|---:|---:|---:|
| 80 | 81 | 4/4 | 4/4 | 0.2962% | 1.5835% |
| 90 | 91 | 4/4 | 4/4 | 0.3713% | 4.4451% |
| 100 | 101 | 4/4 | 3/4 | 0.3012% | 5.9134% |
| 108 | 109 | 4/4 | 4/4 | 0.3218% | 1.7987% |

The new failure is the 81-element, 100 m/s high-frequency mode's real part:
**−2.122517385 versus native −2.2559182 1/s**, an absolute difference of
0.133400815 1/s (5.9134%). Its frequency differs by 0.1577%. The coarse-mesh
real component passes at 1.9777%; refinement does not remove this discrepancy.
The new comparisons all fail the original printed-precision criterion, which
is retained separately from the user-approved 5% allowance.

The four near-onset damping failures remain. Across all seven sampled speeds,
the five failed components have median error 13.9149% and maximum 48.8086%.
All sampled frequencies pass, with maximum error 0.3713%. The earlier first
69–70 m/s flutter bracket is unchanged. Later neutral crossings, native real
branches and mode-shape identities have not been established by these samples.

The comparison helper had counted every positive imaginary component as an
oscillating mode. The complex shift-invert solve leaves very small signed
imaginary remainders on real poles, so a real pole could incorrectly increase
that count. In five of the eight jobs this prevented any ordinal pairing with
the two positive-frequency native rows.

The corrected assessment first uses the existing production tracking convention
for a near-real candidate, `abs(imag) <= 1e-9 * max(abs(pole), time_scale*1e-6)`.
That threshold is **not an eigenvalue error bound or sufficient proof**. Each
candidate must also have phase-real left and right vectors (imaginary norm
ratio at most `1e-10`), satisfy both independent real-pencil equations with
action-relative residual at most `1e-8`, and have nonzero projected mass pairing.
Any unresolved candidate blocks ordinal pairing. No eigenvalue is rounded,
overwritten or removed from the saved selected spectrum. Genuine small
oscillations with complex vectors are not certified real.

All sixteen candidate real poles pass those additional certificates: maximum
phase defect 1.835e-13 and maximum real-pencil residual 9.159e-12. Only the
remaining complete positive-frequency sets are compared in ascending frequency
order. No nearest-reference matching or fitted threshold is used. Native real
poles still remain required and unavailable without authenticated branch
identity; this correction does not claim to explain ASWING's export filtering.

The original helper, prospective plans, raw matrices and original reports are
preserved. A separate assessment recovers twenty previously unavailable
components: nineteen pass and the 100 m/s damping failure remains. A preliminary,
unexecuted 128-machine-epsilon classification proposal is also retained; the
implemented policy uses the existing production convention plus independent
certificates instead of introducing another candidate threshold.

Verification covers 112 original physical/source checks, 32 independent
full-pencil/mass/clamp audits, and all sixteen real-pole certificates. Maximum
scaled clamp defect is 7.106e-17 against `1e-8`. A ninth solve repeats the coarse
80 m/s case through the corrected helper: all fifteen physical/source checks
pass, and all four roots, classifications and native comparisons reproduce the
saved-result assessment exactly. This repeat adds no native targets. All
**96 focused Python tests pass**, including true low-frequency complex modes,
incorrect left/right vectors, invalid matrices, singular mass nullspaces,
time-unit changes and incomplete native spectra.

The eight planned solves and one repeat ran serially with one BLAS thread.
Coarse jobs used a 512 MiB address cap; fine full-matrix exports used the
previously established 768 MiB cap. The correction changes validation helpers
only. The unchanged production kernels retain the prior offline-worker evidence;
these later states were not separately run in the browser or selected in the UI.

With the original cache present, an individual fresh request is reproducible:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
.venv/bin/python scripts/verify-isae-ae4-wall-modes.py NEW_FOLDER \
  --panels 40 --speed 80
```

The full saved study is reassessed without new physical solves using
`scripts/assess-isae-ae4-later.py STUDY_FOLDER NEW_REPORT.json`.
The damping differences, full original speed/incidence coverage, later
crossings, real-pole pairing, historical setup and shared-runner registration
remain open. SA-13 and native UA-2 retain their separate reference-evidence
blockers; no absent or unsupported target gains a pass from the 5% policy.

- [Machine-readable evidence](isae-ae4-later-20261105.json)
- [Original eight-job plan](../../artifacts/isae/ae4-later-20261105/plan.json)
- [Corrected saved-result assessment](../../artifacts/isae/ae4-later-20261105/assessment.json)
- [Fresh-helper verification](../../artifacts/isae/ae4-later-20261105/fresh-helper-verification.json)
