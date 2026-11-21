# Daedalus: why roll and bank change near the cancellation

Most of the current roll-response mesh difference near 1.5 Hz is associated
with movement of a cancellation zero. Its real part changes from **1.045600
to 0.902300 s⁻¹** while its imaginary frequency changes only from **1.444559
to 1.450193 Hz**. Accounting for that independently calculated zero pair
reduces the 1.5 Hz complex roll difference from **19.44% to 3.84%**.
The bank difference follows mainly from the changed roll response.

This explains a difference between two computed meshes; it does **not**
establish mesh convergence, native ASWING agreement or the cause of the zero's
movement. Production physics, aircraft inputs and accepted defaults are
unchanged. The yaw dip remains approximately **0.074 versus 0.034 deg/s/F3**.

![Mesh comparison and zero-factor accounting](../../artifacts/daedalus-mesh-zeros-20261114/report/roll-mesh-cancellation.png)

[SVG](../../artifacts/daedalus-mesh-zeros-20261114/report/roll-mesh-cancellation.svg).
Markers are the eight computed frequencies. Connecting lines are guides,
not a newly calculated continuous sweep. The yellow reconstruction changes
only an algebraic factor of the plotted response; it is not a modified
aircraft or an accepted replacement solution.

## Cases and equation checks

The [earlier refinement](daedalus-structural-resolution-20261113.md) supplies
two converged equilibria and their complete current-source descriptors:
108/211 structural nodes, 82/164 circulation coordinates and 2,044/3,980 total
coordinates. Both use the literal public aircraft at 6.7 m/s, PG Mach 0.1,
SEGSPL properties, moving influences, lag and plume. The refinement changes
structural, aerodynamic and body discretization together and retrims the
aircraft. It does not isolate one discretization or the equilibrium effect.

The [authoritative index](aswing-authoritative-references.md) and catalog
were consulted. Drela's unsteady description, printed pp. 26–27,
Eqs. 131–136, gives `H(s) = C (sM − A)⁻¹ B` for these frame rates, with no
direct input or rate-output term. Its derivative is
`H′(s) = −C (sM − A)⁻¹ M (sM − A)⁻¹ B`.

Newton iteration tracks the refined zero starting from the previously
[verified original-grid zero](daedalus-transmission-zeros-20261114.md).
Each step reuses one exact structured factor for the response and derivative,
while recovering all 3,980 coordinates. No mode, matrix entry or input is
truncated. The original full-equation residual gates and a conservative
reciprocal-condition gate remain active.

| Channel | Original zero, s⁻¹ | Refined zero, s⁻¹ | Refined output at zero |
| --- | --- | --- | ---: |
| Roll rate | +1.045600 + 9.076432i | +0.902300 + 9.111829i | 1.532e−13 deg/s/F3 |
| Yaw rate | −2.868194 + 7.418277i | −2.834464 + 7.318134i | 2.589e−11 deg/s/F3 |

The positive real roll zero is a nonminimum-phase cancellation, **not an
unstable natural mode**. These are locally tracked zeros, not a complete
zero-spectrum search. The magnitude-only reference drawing cannot identify
native ASWING zero locations or which half-plane they occupy.

Independent symmetric derivatives along the imaginary-s direction, at two
widths, agree with the analytic derivative within **3.77e−9 relative** across
both channels. The saved zero states satisfy the complete equations within
**8.63e−16 relative**. The original six refined frequency states are reused;
two new refined solves at 1.4 and 1.6 Hz and eight original-grid solves supply
common samples and complete states. Existing shared outputs are checked.

## Factor accounting, without fitting

For a zero `z`, define the monic real quadratic
`q(s) = (s − z)(s − conjugate(z))`. Compare the actual refined response with
`H_original(s) × q_refined(s)/q_original(s)`. Both zeros come from independent
complex-s solves, not a fit to these eight frequency samples. No gain factor
is fitted either.

| Frequency, Hz | Original complex roll difference | Remaining after zero-factor change |
| --- | ---: | ---: |
| 1.4 | 17.06% | 3.78% |
| 1.5 | 19.44% | 3.84% |
| 1.6 | 15.81% | 3.84% |

Both percentages divide by the actual refined response magnitude. The
maximum remaining roll difference over all eight samples is **3.837%**.
The factor accounting improves the neighborhood of the cancellation; it does
not improve every lower-frequency point. These numbers are not reference
pass counts or a new acceptance criterion.

Yaw is a useful contrast: its real zero displacement is only **1.176%**,
and its original 1.5 Hz complex mesh difference is **0.619%**. Changing only
its zero factor increases that difference to **3.585%**, because changes in
the rest of its transfer function compensate. Zero movement is therefore
not a universal explanation of all response changes.

## Bank conversion and equilibrium changes

The saved frame rates reconstruct bank through the published Euler-rate
relation. Holding the rates fixed and exchanging only the equilibrium-angle
conversion changes bank by at most **1.211%** over these samples. At 1.5 Hz
the changes are **0.765% /0.886%** using original/refined rates, much smaller
than the complete **20.30%** complex bank difference.

An exact decomposition of the complex bank change at 1.5 Hz gives the
following projections onto the net complex change. Projections can exceed
100% or be negative when contributions partly cancel; they are not sums of
positive amplitude fractions.

| Contribution | Projection onto net bank change |
| --- | ---: |
| Changed roll rate | +100.807% |
| Changed pitch rate | +0.000005% |
| Changed yaw rate | +1.526% |
| Changed equilibrium-angle conversion | −2.333% |

This isolates the **output conversion**, not the effect of equilibrium on
the aerodynamic and structural matrices. All 108 original material nodes
are present on the refined mesh. At those common nodes, maximum position
changes are 0.06186 ft on the wing, 0.03481 ft on the stabilizer and at most
0.001044 ft on each other beam; maximum wing/stabilizer orientation changes
are 0.3153°/0.4459°. Those physical equilibrium differences remain part of
the matrix comparison and must not be dismissed from size alone.

## Remaining work and evidence

The roll cancellation is now a specific refinement target. The next useful
check is the aerodynamic-refinement contribution at **1.5 Hz**, using the
newly saved full response, analogous to the earlier
[dip-frequency aerodynamic projection](daedalus-aero-feedback-20261113.md).
This can distinguish an aerodynamic discretization contribution from the
remaining structural/equilibrium effects before committing to a larger
whole-aircraft mesh. A third converged grid or independently verified
component correction is still needed to establish convergence.

[Bounded driver](../../scripts/check_daedalus_mesh_zeros.py),
[report generator](../../scripts/report_daedalus_mesh_zeros.py),
[complete results](../../artifacts/daedalus-mesh-zeros-20261114/report/result.json),
[zero-factor CSV](../../artifacts/daedalus-mesh-zeros-20261114/report/zero-factor-comparison.csv),
[bank component CSV](../../artifacts/daedalus-mesh-zeros-20261114/report/bank-change-components.csv)
and [verification receipt](../../artifacts/daedalus-mesh-zeros-20261114/verification.json)
retain the numerical evidence. Eleven bounded serial jobs completed
successfully. Each used less than 6 CPU seconds, 19 wall seconds and 241 MiB
RSS. No ISAE completion fraction, scope or progress event changed.
