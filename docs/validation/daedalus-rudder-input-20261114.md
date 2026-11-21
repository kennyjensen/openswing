# Daedalus rudder input: literal coefficients and a four-output constraint

The current F3 input agrees with an independent aerodynamic construction.
Replacing only the input column in a diagnostic full-system solve changes
the four outputs by at most **7.439e−11 relative**. This finds no input-unit,
rudder-distribution or input-column assembly correction.

More decisively, **a common rudder gain or scalar actuator filter cannot
explain the four published curves** for this otherwise unchanged aircraft.
At the reference dip, yaw requires attenuation while roll and bank require
amplification. Even allowing the original graphic envelope, at least one output
must remain **49.80% wrong** under any common gain. No gain or filter is fitted
or inserted into the model.

![Required gains and unavoidable residual error](../../artifacts/daedalus-rudder-input-20261114/report/input-invariant.png)

The original Bode discrepancy remains **0.074218 versus 0.033986 deg/s/F3** at
1.157378 Hz. Production equations, aircraft properties and ISAE fractions are
unchanged.

## Published input law and the literal file

The [authoritative index](aswing-authoritative-references.md) and
[source catalog](aswing-authoritative-sources.json) were consulted.
Drela's [steady technical description](../../reference/aswing-authoritative-20261108/drela-aswing-steady.pdf),
p. 33, Eqs. 158–159, defines the control-modified quasi-normal and incidence:

```
n_cp = sin(alpha_A) c_axis + cos(alpha_A) n_axis
alpha_A = alpha_A0 + sum[(dCL/dFk)/(dCL/dalpha) * Fk]
```

The [unsteady extension](../../reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf),
p. 24, Eq. 119, describes direct commanded-stick forcing. Its pp. 10–11,
Eqs. 48–56, provide the circulation lag and circulation-rate lift. Commanded
incidence is distinct from physical beam rotation or angular acceleration.
Neither the declared F3 mixing nor the direct-command equation specifies an
additional mechanical rudder-hinge motion or actuator lag.

The raw [dae.asw](../../examples/dae.asw) rudder, beam 3, specifies constant
`dCLda = 6.2` and a `dCLdF3` scale of **−0.01745** multiplying 6.2 from
t = −3.5 to +5 ft. Consequently one F3 unit changes aerodynamic incidence
by **−0.01745 rad** over the whole rudder. Other lifting beams have zero F3
incidence derivative; all direct F3 moment/profile-drag coefficient
derivatives are zero. The literal 0.01745 approximation differs from π/180
by **−0.018865%**; preserving it is correct file interpretation.

The current parser is checked at every interval endpoint and receiver:
246 samples across the four lifting beams, including 54 on the rudder.
No state-feedback controller is active. The input uses one native file-setting
unit, with no additional degree-to-radian conversion.

## Isolated complete input column

The earlier [aerodynamic phase comparison](daedalus-circulation-phase-20261114.md)
checked combined aircraft-motion/control directions. This check isolates F3
while holding all physical states and state rates fixed.

The [bounded driver](../../scripts/check_daedalus_rudder_input.py) makes 16
explicit full-residual evaluations: fourth-order centered input stencils at
two widths and two frequencies, 0.2 Hz and the reference dip. The resulting
input columns are bitwise identical between frequencies. Their width difference
is 1.911e−13, and their largest difference from the saved input is 8.820e−12.

Separately, the independent aerodynamic evaluator receives the **literal raw
control coefficients**, rather than trusting those captured coefficients.
It independently integrates vortex, volume and propeller flow, then applies
the published control-normal, tangency, load and lag equations. Two complex-step
widths differ by only 1.041e−17. Nodal force/couple transfer and whole-aircraft
wrenches construct all **2,044 rows** of the input column, including zero rows.

| Comparison | Maximum absolute difference |
| --- | ---: |
| Independent input versus fresh native derivative | 1.786e−13 |
| Independent input versus saved descriptor input | 8.958e−12 |
| Independent nodal/global wrench closure | 9.946e−27, respective native units |

The 18 rudder circulation rows carry the incidence forcing. Other circulation
rows are exactly zero. At fixed circulation and physical motion, ordinary
lift does not directly change; circulation subsequently responds through the
coupled equations. The small direct force/couple comes from the square of
the tangency defect in profile drag, retained rather than silently dropped.
Direct circulation-rate, apparent, body, point and engine input-load derivatives
are zero. This does not remove their **indirect** response after solving the
aircraft.

Two full descriptor factorizations compare the saved and independent input
columns as four right-hand sides. All eight output comparisons agree within
7.439e−11 relative. Scaled residuals are below 5.894e−18; reciprocal condition
estimates exceed 1.775e−8. The original exact beam elimination and numerical
gates remain active. No saved input matrix or equilibrium is replaced.

## A common input filter cannot reconcile the drawing

For unchanged aircraft and output definitions, a scalar filter `G(s)` ahead
of the F3 input multiplies every output transfer by the same number. At each
frequency, therefore, one common positive gain `g = |G|` must satisfy all four
magnitude comparisons. Unknown filter phase cannot change this requirement.

The [report script](../../scripts/report_daedalus_rudder_input.py) verifies the
four raw vector-graphic curves against their original PDF axes, then checks
the same 65 frequencies as the current full-system comparison. The original
±0.75 PDF-point envelope is retained. It conservatively permits independent
horizontal curve displacement and frequency-coordinate error, plus vertical
displacement; all intervening polyline vertices are included. This is graphic
uncertainty, not uncertainty in the aircraft's physical parameters.

At **1.1573777374 Hz**, including that envelope and an additional 5% comparison
tolerance, the allowed multiplicative input gains are:

| Output | Allowed gain interval |
| --- | ---: |
| Yaw rate | **0.42250–0.50778** |
| Roll rate | **1.35114–1.70393** |
| Sideslip | **0.74832–0.92451** |
| Bank angle | **1.37085–1.94635** |

These intervals do not intersect. Scaling the input to deepen the yaw dip
would further reduce the already-low roll/bank responses.

More generally, let `L = max(reference_min/current)` and
`U = min(reference_max/current)` over the four outputs. To place each output
within relative error E of some value in its graphic band, a common gain must
satisfy `(1−E)L <= g <= (1+E)U`. Thus the unavoidable worst-channel error is
at least `max(0, (L−U)/(L+U))`. This is a bound, not a fitted actuator model.

| Graphic coordinate half-width | Frequencies where a common gain cannot meet 5% | Error lower bound at the dip |
| --- | ---: | ---: |
| Central vector curves | 58 / 65 | 56.37% |
| Original ±0.75-point envelope | **34 / 65** | **49.80%** |
| Doubled ±1.5-point sensitivity envelope | 17 / 65 | 44.49% |

The remaining frequencies are only compatible with this **necessary**
magnitude condition. They are not validation passes and do not establish a
single causal filter, correct phase or correct aircraft. Allowing an arbitrary
gain independently at every frequency is already more permissive than fitting
a physical actuator.

## Consequence and scope

The isolated input check supports the documented incidence-mixing implementation.
The independent magnitude bound rules out input normalization or scalar actuator
lag **alone** as a cure for the current four-output discrepancy. It does not
rule out feedback, changed spatial control mixing, different historical aircraft
or trim, or changed output definitions. None is adopted without evidence.

The next useful distinction is between rigid-frame angular rate and the
absolute angular rate at an elastically moving aircraft attachment. The earlier
[output-convention bound](daedalus-reference-kinematics-20261114.md) considered
constant rotation of the roll/yaw axes, not added local elastic angular motion.
The literal file rigidly grounds beam 5 at t = −15.6, so the present frame
definition is fixed and must remain unchanged. A comparison at other documented
attachment stations would be a diagnostic of output-definition sensitivity,
not permission to relabel such a sensor response as the published frame Ωz.

## Evidence and execution

- [Input capture and parser checks](../../artifacts/daedalus-rudder-input-20261114/native/result.json)
- [Independent complete input column](../../artifacts/daedalus-rudder-input-20261114/reference/result.json)
- [Full-system response comparison](../../artifacts/daedalus-rudder-input-20261114/input-response/result.json)
- [Gain bound and all three graphic envelopes](../../artifacts/daedalus-rudder-input-20261114/report/result.json)
- [Per-output gain intervals](../../artifacts/daedalus-rudder-input-20261114/report/gain-intervals.csv)
- [Verification receipt](../../artifacts/daedalus-rudder-input-20261114/verification.json)

All **four small serial jobs** succeeded and were reaped, with one BLAS thread
and unchanged 512 MiB / 15 CPU-second / 25 wall-second limits. Observed maxima
were 2.266 CPU seconds, 4.550 wall seconds and 127,960 KiB RSS (124.96 MiB).
The plot was inspected. No browser/build job, background solver or native
ASWING executable was used. ISAE status/history and their comparison scopes
are unchanged.
