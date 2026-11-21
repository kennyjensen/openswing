# SA-13: exact relation recovered for the discrete load curves

The [full JSON follow-up](isae-sa13-discrete-bridge-20261109.md) extends the
180-station kernel replay below through complete rigid aerodynamic requests,
public force/moment recovery and independent assembly checks. No original-case
pass or browser/WebAssembly execution is implied.

The subsequent [pressure-geometry audit](isae-sa13-pressure-geometry-20261109.md)
also identifies all 56 finite red pressure ordinates as shifted squared
backward radius slopes. This makes all 239 available red-curve values
algebraically reproducible, while retaining their separate physical-validation
limitations and all missing entries.

All **183 available ordinates** in the three red `Discrete ASWING 5.96`
load curves are reproduced to roundoff by a formula using the original plotted
radius samples. No scale or angle was fitted. A separate replay through the
unchanged OpenSwing body-force kernel reproduces **180 physically admissible
station values**, on an explicit piecewise-linear reconstruction.

This identifies the local force law, normalization and sampling relation in
those stored curves. It does not recover the original complete ASWING models,
the continuous-curve derivative input, or the pressure sensor/postprocessing
setup. The primary eight-series comparison remains **0/612**, with all 136
unavailable entries retained. SA-12 remains open.

## Recovered expression

Let `R_i` be half the difference between the upper and lower outline at stored
coordinate `x_i`, and let `D = 2 max(R_i)`. The discrete load curves use exactly
those same stored axial coordinates. Every available nonterminal value obeys

```text
C_i = f_z(x_i)/(q∞ D)
    = 2π sin(2α) R_i (R_(i+1) − R_i) / [(x_(i+1) − x_i) D].
```

This is Drela's steady **Eqs.68–69, p.16**, evaluated with the radius at the
current station and the slope to the next station. The angle is **10° for R33
and R101, 9° for RS1**. These are the primary-source angles already retained in
the source audit; the report's alternative 10° for RS1 does not reproduce the
values. It gives a maximum difference of 10.68% of that curve's peak on the
common interior rows.

| Stored discrete curve | Finite / retained values | Maximum absolute algebraic error |
|---|---:|---:|
| R33 | 64 / 64 | 5.56e-17 |
| R101 | 54 / 74 | 5.56e-17 |
| RS1 | 65 / 65 | 1.12e-16 |

The two terminal values in R33 and RS1 are stored zeros without a successor
radius. They require that explicit endpoint assignment; the slope expression
does not predict them. The R33 final interval also crosses a negative signed
outline radius. The algebra still reproduces its value, but that is not a
valid positive-radius physical interval. No reference value was clipped.

Jan Part I **§6.2, p.40**, describes the original implementation as using a
first-order backward difference. The exact relation here is to the *next*
station in increasing stored x. Original internal node ordering and output
indexing are unavailable, so this establishes the archived numerical relation
without claiming an error in the report's internal-order terminology. Using
the previous stored station instead fails by 36–69% of peak on common interior
rows; these alternatives are retained in the analysis.

For **R101**, the stored red curve therefore satisfies `f_z/(q∞ D_max)`.
The cited experimental NACA-TR-405 Figure 8 instead uses dimensional `f/q` in
feet. The earlier normalization lead is now an exact algebraic finding for
the red curve. It does not settle the continuous curve's normalization.

## Replay through the current force kernel

The diagnostic constructs separate two-point radius segments using the
existing `.asw` repeated-station syntax, with the original radius samples and
explicit original x stations. This selects piecewise-linear radius rather
than the earlier smooth outline spline. It is a disclosed reconstruction,
not a recovered original input. There is no parameter fit, cap extension or
change to production code.

`body_loads` evaluates uniform-flow forces at its Gauss points. For these
linear radius segments, the force density is affine. Recovering its value at
the left station from two computed Gauss densities gives the archived nodal
load. All remaining Gauss points independently check the affine relation.
The integrated loads separately agree with the exact endpoint-area formula.

| Hull | Replayed station values | Maximum absolute kernel error | Maximum interval-average versus archived-node difference, as % of curve peak |
|---|---:|---:|---:|
| R33 | 62 | 5.56e-17 | 30.24% |
| R101 | 54 | 1.12e-16 | 63.88% |
| RS1 | 64 | 2.78e-16 | 27.57% |

The last column is a **difference between two observables**, not a failed
5% accuracy gate. With linear radius and `ΔR = R_(i+1) − R_i`,

```text
C_average − C_i = π sin(2α) (ΔR)² / (D Δx).
```

Consequently, comparing an integrated strip force divided by strip length
directly with these station densities introduces a predictable bias. This
does not establish how historical ASWING integrated its loads. Replacing
OpenSwing's conservative interval integral with the left-station density
would not be justified by a pointwise plot comparison.

The replay excludes the two terminal zero assignments and the R33 interval
with negative terminal radius. R101's twenty missing entries also remain
unavailable. This preserves every original row while distinguishing the
algebraic identity from the physically admissible local-kernel test.

## Evidence and next action

- [Source-only audit](../../scripts/audit_sa13_discrete_loads.py) and
  [analysis](../../artifacts/isae/sa13-discrete-loads-20261109/analysis.json):
  twelve source pins, all rows and alternative angle/difference checks.
- [Independent verifier](../../scripts/verify_sa13_discrete_loads.py) and
  [receipt](../../artifacts/isae/sa13-discrete-loads-20261109/verification.json):
  reads all four original MAT files, confirms all 1,530 coordinate pairs,
  and independently checks the 183 load values with Decimal arithmetic.
  Maximum error is 1.09e-16; no OpenSwing import or solver call.
- [Kernel replay](../../scripts/check_sa13_discrete_kernel.py) and results for
  [R33](../../artifacts/isae/sa13-discrete-loads-20261109/kernel-r33.json),
  [R101](../../artifacts/isae/sa13-discrete-loads-20261109/kernel-r101.json),
  [RS1](../../artifacts/isae/sa13-discrete-loads-20261109/kernel-rs1.json).
  Each JSON pins its companion `.asw` and all 141 production modules.
  The serial jobs take 2.7–3.2 seconds and about 215–216 MiB peak RSS under
  512 MiB / 15 CPU-second / 25 wall-second limits with one BLAS thread.

The next comparison should explicitly distinguish station force density from
strip-average force and retain the identified radius-difference convention.
The current force law needs no alteration to reproduce the local red-curve
relation. A full native-case validation still needs a defensible complete
setup/output mapping, including endpoints; the modified continuous curves
and pressure curves retain their separate unresolved inputs and conventions.
No primary completion fraction or tracked scope changed. Browser, build and
kernel-loading checks remain under the existing UserLAnd hold.
