# AE-4: numerical and mesh audit of the 79 m/s low-frequency mode

The low-frequency discrepancy persists under a nearby search shift and a
third cosine mesh. Its native frequency error is **7.870%, 8.288% and 8.394%**
on nominal 40, 80 and 160. **All 124 diagnostic checks pass** across 13 serial
stages. No production equation, parameter, native target or acceptance gate
changed, and no primary votes were added: AE-4 stays **227/1,200**.

The assessment was observed at
**2026-11-12T16:27:34.090497+00:00**. These results narrow the numerical
explanations; they do not identify the physical source of the mismatch or
validate the family.

## Reproduction and refinement

| Declared nominal count | Actual intervals | Re(λ), 1/s | Im(λ), rad/s | Native frequency error |
|---:|---:|---:|---:|---:|
| Archived ASWING | Unauthenticated `I 40` convention | −28.5658680 | 6.3190243 | — |
| 40 | 41 | −28.6882369 | 5.8217298 | 7.870% |
| 80 | 81 | −28.6929564 | 5.7952747 | 8.288% |
| 160 | 161 | −28.6941402 | 5.7885984 | 8.394% |

The required material station remains present. Both registered meshes
reproduce all four earlier roots within **2.65e−13** under the scaled root
comparison. Their earlier primary results retain their original evidence;
these fresh diagnostic runs do not replace them. Nominal 160 is an additional
convergence diagnostic, not a new primary comparison scope.

The low mode's frequency changes by **0.4565%** from 40→80 and **0.1153%**
from 80→160. Both exceed the existing **0.1%** mesh gate; the latter is close
but is still a failure. The real parts change by **0.01645% /0.00413%**,
passing that gate. Interpolated mechanical-shape MAC values are
**0.999999862 /0.999999991**, consistent with the same computed branch.
This does not authenticate the unavailable native eigenvector.

The finer cosine results approach a frequency further from the native value.
That trend argues against simply increasing this mesh count as a complete
repair, without establishing a continuum limit or the archived native mesh.

## Search and derivative checks

Drela's unsteady description, §13.3.1, Eqs. 147–152, pp. 28–29, explicitly
permits moving the complex shift to investigate nearby modes. On nominal 40
and 80, an additional two-mode search at **−28+6i /s** reproduces the low pair
found by the original four-mode **0+200i /s** search. Maximum scaled root
difference is **3.32e−13**. All retained left/right pencil residuals across
this study are at most **4.10e−16** under their normalized checks; mass
pairing, root clamps and fresh equilibrium checks also pass.

On each registered mesh, the real and imaginary parts of the low mode supply
independent directions for central differences of the full nonlinear
residual. State and rate actions are checked at amplitudes
**1e−4, 1e−5 and 1e−6**. The largest relative action difference from the
assembled matrices is **1.31e−9**, below the unchanged 5e−5 gate. This tests
the derivative assembly along this mode; agreement with the implemented
nonlinear residual does not independently validate every physical load law.

For pointwise circulation at the undeformed, zero-lift operating point,
Eq. 49's circulation-rate block is independently constructed as
`M_Gamma = (2/pi) * gamma_scale / V² * I` in the solver's residual/state
scaling. Its difference from the assembled block is zero at the reported
precision on both meshes. The published **2/pi** coefficient is present;
no empirical lag constant was adjusted.

## Which unsteady terms affect the pair

The left/right eigenvectors also give the following local sensitivities.
For `A r = lambda M r`, the reported derivative for `M + epsilon M_term` is
`d(lambda)/d(epsilon) = -lambda * l* M_term r / (l* M r)`.
Only the indicated mass-matrix contribution is scaled in this mathematical
derivative, with A held fixed. These are adjoint diagnostics, not fitted
parameters or independently rerun perturbed cases.

| Matrix contribution | Nominal 40 derivative, 1/s | Nominal 80 derivative, 1/s |
|---|---:|---:|
| Shed-vorticity lag, circulation-equation rows | −7.4834−17.0692i | −7.4895−17.1701i |
| Circulation-rate lift and moment, remaining circulation-rate column entries | +5.3342+12.3425i | +5.3392+12.4171i |

The contributions act in opposing directions on this pair. Drela gives the
rate-lift force and its quarter-chord moment in **Eqs. 35–36, p. 8**, and the
lagged tangency constraint in **Eq. 49, p. 10**. Their transfer into the beam
equations is therefore a useful next independent audit. The present
sensitivities do not establish that either implementation is wrong.

## Sources, execution and remaining work

The [authoritative index](aswing-authoritative-references.md), checksummed
catalog, Jan Part IV §3.4, original Pazy model, driver and modal output were
checked before the plan was recorded. The current declared fixed-frame,
solid-wall, zero-incidence setup, original material/mass data, pointwise
circulation, lag, updated influences and source structural operator remain
unchanged. The nominal 160 state changes only the mesh count. Native
startup/restraint settings and the precise `I 40` convention remain unknown.

Each cold base, matrix construction and original mode solve runs in its own
bounded stage. Focused searches and residual-action checks are separate
stages on the two registered meshes. All 13 children completed and were
reaped, with one BLAS thread and unchanged **512 MiB /15 CPU /25 wall-second**
caps. Maximum child CPU, supervised wall time and RSS were
**6.41 s, 9.20 s and 232.2 MiB**. No browser/build job ran. Production source
hashes and all dependency hashes were verified before and after execution.

The primary ledger remains **227/1,200**: 236 paired components, 9 mismatches,
16 unmatched, 12 unknown-initial values and 936 unrun. Failed paired errors
remain median 8.29%, range 5.91–48.81%. Its original targets, both meshes,
9,480 historical components, overlapping 86/108 sample, later operating
branches and time histories remain unchanged.

Next audit the **unsteady force/moment law and transfer at 79 m/s** independently
of the existing residual, beginning with Eqs. 35–36 and their circulation-rate
terms. Preserve the published coefficient and original model parameters.
Near-onset flutter damping, native setup, tiny-root identity around 103 m/s,
wall/frame capability and spatial convergence remain open.

Evidence: [prospective plan](../../artifacts/isae/ae4-low-mode-20261112/plan.json),
[complete assessment](../../artifacts/isae/ae4-low-mode-20261112/assessment.json),
[prior full native ledger and comparison figure](isae-ae4-flutter-band-20261112.md).
