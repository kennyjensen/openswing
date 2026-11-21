# Curved rigid geometry and the source interval-length correction

The SA-3/SA-4 investigation exposed a specific inconsistency in the optional
source-equation structural path: a curved beam could satisfy its complete
zero-load, zero-strain equations while reporting changed aerodynamic interval
lengths. The inherited chord-ratio calculation confounded discrete bending
geometry with physical stretch. The ordinary rigid aerodynamic path and the
default structural operator are separate from this issue.

## Equation and implementation

Drela's [steady technical description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf),
p.12, Eqs.48/50, writes the interval displacement as

```text
delta_r = R_average q_average ds0
R_average = (R_left + R_right)/2
q_average = [gamma_c, 1 + epsilon_s, gamma_n]_average
```

The `R` matrices map physical local components into body coordinates. Their
arithmetic average is generally not a rotation. At zero axial and shear strain,
the equation reduces to the endpoint-tangent trapezoid,
`delta_r = (span_left + span_right) ds0/2`. The original endpoint jig frames
satisfy the rigid curvature equation. Integrating from a fixed root therefore
constructs a prescribed zero-strain state without an equilibrium solve.

The existing source residual implements that equation without a jig-position
subtraction. Its inherited mesh update nevertheless used
`ds0 * current_chord_length / original_chord_length`. For a curved rigid beam,
the trapezoidal node positions can differ from the original spline node
positions even at zero strain; the chord ratio then changes the reported arc.

The source-specific correction uses

```text
ds = norm(solve(R_average, delta_r))
```

At a converged source state this equals `ds0 * norm(q_average)`. It preserves
material arc under zero-strain bending and gives the expected uniform axial
and shear stretch. It does not replace the average matrix by an orthogonal
midpoint frame. Positions, frames, circulation samples and material Glauert
coordinates retain their existing construction.

For nonuniform endpoint strains, this is a declared **constant-average-strain
metric**. The norm of an average generally differs from an average of norms;
the paper does not authenticate a unique nonlinear endpoint quadrature for
the historical executable. Numerical checks reject nonfinite, singular or
ill-conditioned mean transforms rather than applying a pseudoinverse.

The correction is implemented only in `SourceDiscreteNetwork` and its source
subclasses. `StaticNetwork` retains its previous measure. Source output metadata
declares the convention, and source equilibrium/checkpoint identities include
`deformed_interval_measure=drela-eq48-average-strain-norm-v1`. Saved source states
from the earlier method must be recomputed; ordinary saved-state identities are
unchanged. A relative singular-value cutoff of `1e-10` is a numerical-rank check,
not a physical bend-angle limit.

Verification covers **500 distinct targeted tests**: the broad 465-test run
passed 464 and found one error-message mismatch, which was corrected. The final
96-test run passes all affected identity/time tests and the 35 new analytic
tests. The remaining 404 previously passing tests were not repeated. Coverage
includes curved zero-strain geometry, finite bending, axial/shear stretch,
observer rotation/translation, source subclasses, nonfinite/singular inputs,
unchanged ordinary behavior and old-state/checkpoint rejection. The
[implementation receipt](../../artifacts/isae/source-rigid-arc-measure-20261029/implementation/terminal-receipt.json)
retains commands, earlier failures, final source hashes and outcomes.

The six retained before-change fields also pass **940 length checks** in native
Python and the offline WASM kernel. Maximum relative length error is `1.23e-12`
and maximum scaled length error is `4.44e-16`; full zero-load residuals stay below
`3.03e-16`. Native/WASM length differences are at most `1.33e-17` scaled, with
zero network fetches. All 130 native, public and built kernel modules match.
These checks evaluate prescribed kinematics, with no airflow or nonlinear
solve. The [runtime receipt](../../artifacts/isae/source-rigid-arc-measure-20261029/runtime-terminal-receipt.json)
also confirms that only the two source-policy/identity modules changed from the
frozen kernel; ordinary rigid SA-1–SA-5 scores are unaffected.

A geometry-only timing sample at 160/400 intervals measures about 0.73/1.25 ms
per corrected update, versus 0.36/0.56 ms previously. This is a shared-machine
microbenchmark, not whole-solver timing; finite-difference source tangents can
multiply the per-update cost. No new caching was introduced in this correction.

## Before-change evidence

Six prescribed fields were evaluated in the full source residual, with no
airflow, gravity or nonlinear solve. Every reconstructed rigid field satisfies
the residual within **1.07e-16**. The old interval measure gives:

| Model | Intervals | Largest node displacement from input spline | Largest spurious interval-length change |
|---|---:|---:|---:|
| SA-1 | 200 | 8.88e-16 m | Roundoff |
| SA-3 | 100 | 0.000275527 m | 3.33681% |
| SA-3 | 200 | 0.000093484 m | 1.06513% |
| SA-4 | 80 | 0.000348801 m | 0.0592816% |
| SA-4 | 160 | 0.000226951 m | 0.0311563% |
| SA-5 | 200 | 6.22e-15 m | Roundoff |

The straight and piecewise-straight controls preserve length to roundoff.
These are per-interval metric errors, not aircraft lift/drag errors. The
[before-change witness](../../artifacts/isae/source-rigid-arc-measure-20261029/report.json)
retains all positions and interval lengths, and its
[receipt](../../artifacts/isae/source-rigid-arc-measure-20261029/terminal-receipt.json)
records the source pins and archived 130-module kernel.

## Separate rigid-aerodynamic geometry test

A predeclared ten-call study isolates the Eq.48 node-position change while
holding material lengths, physical inputs, all section samples, solver policy
and gates fixed. It does not include the inherited source length error. Nine
box-geometry cases use eight saved same-mesh baselines and one fresh N320
original-geometry control. Each call is a cold solve with no retry.

| Case | Intervals | Incidence | Baseline → diagnostic at 3% | Diagnostic maximum output error |
|---|---:|---:|---:|---:|
| SA-3 | 100 | 7.04348° | 7/7 → 6/7 | 5.426% |
| SA-3 | 200 | 7.04348° | 7/7 → 7/7 | 1.392% |
| SA-4 | 80 | 0.29° | 7/7 → 7/7 | 0.3516% |
| SA-4 | 160 | 0.29° | 7/7 → 7/7 | 0.1052% |
| SA-4 | 80 | 4.06° | 7/7 → 7/7 | 0.5553% |
| SA-4 | 160 | 4.06° | 0/7 → 7/7 | 0.4344% |
| SA-4 | 80 | 7.06° | 3/7 → 3/7 | 7.257% |
| SA-4 | 160 | 7.06° | 3/7 → 3/7 | 7.838% |
| SA-4 | 320 | 4.06° | 0/7 → 0/7 | Solve failed |

Eight calls return valid fields; both N320 calls fail their original residual
gate (0.209292 original, 0.181346 with box positions). All ten processes exited
and were reaped, with no timeout. The recovered N160 SA-4 state reaches normal
Mach **0.973614**; refinement has not established convergence. The lost SA-3
Cm check has an absolute difference of **3.392e-5** against a **6.25139e-4**
reference. SA-4's 7.06° drag/CDi/efficiency differences remain approximately
6–8%.

The nine candidate comparisons yield **47/63**, versus **41/63** for their
paired originals. These are diagnostic comparisons only. The
[complete interpretation](../../artifacts/isae/sa34-rigid-box-geometry-20261029/interpretation.md)
retains all outcomes and qualifications, including the older saved baselines.
This does not justify replacing ordinary rigid geometry globally. Registered
SA-1–SA-5 counts and production spacing defaults remain unchanged.

## Circulation-count source check

The newly retrieved [Romain Jan thesis](https://theses.fr/2023ESAE0046/document),
pp.77–80, explicitly distinguishes Fourier coefficients `K`, structural nodes
`I` and the `I−1` horseshoes. It recommends roughly 20–40 circulation variables,
but its case descriptions also use inconsistent node/piecewise terminology.
The archived drivers select `NODE/I`, not an explicit Fourier count; their
`OPER/K/I` commands set Newton iteration limits.

Consequently the thesis does not authenticate `K=40` for the particular archived
outputs. Current sine sampling and `sin(k theta) delta_theta` projection agree
with the documented equations. Earlier SA-1/SA-4 Fourier studies already test
the relevant count sensitivity; no additional count sweep was launched.
The [source audit](../../artifacts/isae/circulation-count-source-review-20261029/report.json)
retains the official thesis, exact page/equation references and driver evidence.
