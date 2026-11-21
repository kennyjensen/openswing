# Daedalus mounting span: independent continuous-beam comparison

The short wing–fairing boom span reproduces an independent continuous beam
closely under the **actual supplied aircraft loads**. At the reference yaw dip,
the original two-element span differs by **0.11345% in rotation relative to the
fairing** and **0.75236% in combined wing-end motion**. Refining to four/eight
elements reduces those errors to 0.02843/0.00711% and 0.18849/0.04715%.

This supports the modeled mounting mechanics. It does **not** recompute the
coupled aircraft or resolve its Bode discrepancy: yaw remains 0.074218 versus
0.033986 deg/s/F3. No stiffness, production equation, default or ISAE fraction
was changed.

![Actual forcing replay](../../artifacts/daedalus-mount-continuum-20261114/report-v3/actual-forcing.png)

## Why this check

The preceding [transmission-zero study](daedalus-transmission-zeros-20261114.md)
found that this span strongly affects the wing–tail cancellation. Its yaw-zero
real-part sensitivity to EInn is about 52 times the aft-boom sensitivity.
That identifies an influential component; it does not establish an error in it.

The older [mounting-path audit](daedalus-wing-mount-20261113.md) checked supplied
moment/compliance integrals and a mechanical reconstruction using source
equations. The present comparison independently solves a continuous spatial
rod and its dynamic boundary problem. The earlier
[half-wing continuum calculation](daedalus-wing-root-20261114.md) covered a
different component.

## Reference equations and preserved inputs

The [authoritative index](aswing-authoritative-references.md) and
[checksummed catalog](aswing-authoritative-sources.json) were consulted.
Drela's [steady technical description](../../reference/aswing-authoritative-20261108/drela-aswing-steady.pdf)
provides section compatibility/constitutive relations, force and moment balance
on p. 12, Eqs. 46–47, and the discrete source equations on pp. 12–14,
Eqs. 48–56. The body-beam Euler chart is retained in the compact source adapter.
The independent continuous calculation uses spatial rotations instead.

Real inertia follows steady pp. 17–18, Eqs. 78–83, and the local-rate definitions
in the [unsteady extension](../../reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf),
p. 4, Eqs. 1–4. The source adapter retains the Eq. 80 finite-interval rotary
term. The continuous reference has zero intrinsic section rotary inertia, as
specified in the file; the additional interval term vanishes under refinement.
This distinction is deliberate and is included in the convergence comparison.

The literal `dae.asw` beam 4 span is **t = 0…2.5 ft**, with original stations
0, 1.67944452116 and 2.5. Its properties are independently constructed from
the raw table:

```
EIcc(t) = EInn(t) = 5000 [10 + 10 (t + 6.5)/10.5] lb ft²
GJ = 25000 lb ft²
weight/length = 0.15 lb/ft
```

The bending stiffness therefore varies from **80,952.38 to 92,857.14 lb ft²**.
The capture checks these against the parser and confirms rigid extension/shear,
zero cross-stiffness, zero reference-axis/CG offsets, zero material damping,
and zero intrinsic section inertia. No material parameter is fitted.

The fairing-end position/orientation are prescribed from the accepted 6.7 m/s
loaded equilibrium. The wing-end wrench and original interior nodal dead load
are also prescribed. Each refined discrete component and the continuous rod
is equilibrated under these same loads. Added nodes carry no new static load.
Real local mass stays distributed. Airflow, gravity-direction and free-aircraft
frame derivatives are excluded from this component operator; their actual
effects enter as prescribed forcing in the replay below.

## Independent boundary calculation and checks

[Independent spatial rod](../../scripts/daedalus_mount_reference.py) imports no
OpenSwing routines. It integrates position, section rotation, internal force
and moment backward from the fairing, then solves for the end wrench that
matches the prescribed wing-end wrench. Its tangent retains the loaded force
and moment, including the moving material compliance. Dynamic terms use the
complex exponential `exp(s time)`; `s = i 2πf` gives sinusoidal response.

The independent reference is checked in three ways:

- Tightening integration tolerance from 1e−10 to 1e−12 changes the tested
  wing-end motion norms by at most **9.431e−12 relative**.
- A separate zero-preload, variable-EI cantilever compliance is obtained by
  direct quadrature of `1/EI`, `t/EI` and `t²/EI`. Its maximum difference from
  the spatial-ODE reference is **2.486e−16** in the physical compliance entries.
- The compact two-element source adapter matches the extracted production
  mechanical tangent within **8.538e−14**; its mass matrix matches exactly.
  Fourth-order derivative step comparisons are below 3.146e−11.

The component has 24/48/96 unknowns on the 2/4/8-element grids. Its steady
residuals are below 2e−12. Dynamic solves retain the residual/conditioning
gates; their scaled residuals are below 3.65e−16 and reciprocal condition
estimates exceed 0.018. The continuous boundary residual is below 5.69e−15.

## Unit-load comparison, including its less favorable components

Each mesh tests six independent wing-end wrench inputs and six fairing-end
motion inputs at five preselected values: static, 0.2 Hz, 1.1573777374 Hz,
and the previously verified complex yaw/roll transmission zeros. The latter
are forced exponential responses, not sinusoidal frequencies or natural modes.

The combined motion norm is `||(translation/2.5 ft, spatial rotation)||`.
Each input is compared separately; no fitted weighting or average across
inputs is used. The full componentwise and absolute differences are retained
in the [CSV](../../artifacts/daedalus-mount-continuum-20261114/report-v3/comparison.csv).

| Metric | 2 elements | 4 elements | 8 elements |
| --- | ---: | ---: | ---: |
| Largest combined-motion error, all 60 input/value pairs | 5.2781% | 1.3149% | 0.32844% |
| Yaw-couple rotation error at the dip | 0.05288% | 0.01325% | 0.003315% |
| Largest separately measured rotation error, nonzero reference rotations | 22.8667% | 5.7334% | 1.4344% |

The last row must not be hidden by the combined norm. Prescribed cut translation
can create a very small inertial rotation even while the translation itself
agrees closely. Its largest percentage occurs for streamwise cut translation;
at the dip the two-element rotation-vector error is approximately 5.62e−9 rad
per foot of imposed translation. Similarly, the largest combined-motion error
comes from a small deformation induced by axial force on the preloaded bent
span. Transverse-force combined-motion errors are about 4.44% on the coarse
mesh. All these comparisons converge with refinement; they are not all claimed
to pass 5% on the original mesh.

![Unit-input comparison](../../artifacts/daedalus-mount-continuum-20261114/report-v3/mount-comparison.png)

## Actual aircraft forcing replay

The [replay adapter](../../scripts/check_daedalus_mount_projection.py) takes
the saved full aircraft states at 0.2 Hz, the reference dip, and the selected
yaw/roll zeros. Applying the extracted mechanical operator, including its real
mass term, identifies the required external nodal wrenches. The interior
wrench and fairing motion remain present. These **same physical forcing
amplitudes** are applied to all three discrete grids and the continuous rod.

The coarse component reproduces the supplied aircraft's local motion within
**3.356e−15** physical units. The independent continuous calculation then gives:

| Supplied aircraft response | Relative mounting-rotation error, 2 / 4 / 8 elements |
| --- | ---: |
| 0.2 Hz | 0.11361% / 0.02847% / 0.00712% |
| Reference yaw dip, 1.157378 Hz | 0.11345% / 0.02843% / 0.00711% |
| Selected yaw transmission zero | 0.11134% / 0.02790% / 0.00698% |
| Selected roll transmission zero | 0.11173% / 0.02800% / 0.00700% |

Here the rotation error is divided by the continuous wing-minus-fairing
rotation-vector magnitude, rather than the larger absolute rigid motion.
At the dip, the maximum coarse rotation-component difference is
**0.00002021°/F3**. The tolerance comparison for these replays is below
3.112e−13 relative. The [complete complex results](../../artifacts/daedalus-mount-continuum-20261114/actual-forcing/result.json)
retain every input and output.

This weakens a mounting-mechanics discretization error as the explanation for
the deep Bode discrepancy. A conditional component replay is not an estimate
of the change in the fully recoupled aircraft: its external loads are supplied,
and those loads could change when the component changes. The existing full
aircraft refinement and equation audits remain separate evidence. The
historical ASWING run settings remain unresolved.

## Evidence and execution

All **11 small serial jobs** have terminal records and are reaped. Ten returned
success; one reporting attempt rejected a new diagnostic's array slice before
writing a result. Its log is retained. The first capture was superseded by
`prepare-v2`: code review identified the adjacent nose interval's moving-arm
term at the cut. All comparisons use the corrected isolated cut; no production
operator was changed. Earlier report versions are retained.

Per-job limits remained 512 MiB address space, 15 CPU seconds and 25 wall
seconds, with one BLAS thread. Observed maxima were **3.701 CPU seconds,
6.835 wall seconds and 133,188 KiB RSS** (130.07 MiB). No browser, build,
background solver or native ASWING executable was used.

The [verification receipt](../../artifacts/daedalus-mount-continuum-20261114/verification.json)
checks input hashes, archived runners, unchanged production modules,
unchanged literal model/catalog/ISAE status, and terminal records. Both plots
were inspected. This is supplementary mechanics evidence, not a new ISAE
completion fraction or a native-ASWING Bode pass.
