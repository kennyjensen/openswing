# AE-4: independent real-inertia audit at 96 m/s

**The checked real-mass and inertia terms agree with independently transcribed
Drela equations.** All 744 local-acceleration columns of the saved coupled
mass matrices agree after adding independently calculated apparent-fluid
loads. Gravity, centroid-offset, angular-acceleration and spin-load probes
also pass. This audit has not identified an inertia implementation error
that explains the 96 m/s damping discrepancy.

Two bounded serial workers pass **1,084 numerical checks**. No solver code,
physical parameter or acceptance gate changes, and no native-reference vote
is added. **AE-4 remains 357/1,200 at 5%.** The assessment was observed at
**2026-11-13T03:56:12.146404+00:00**.

## Equations and independent inputs

The [authoritative reference index](aswing-authoritative-references.md) and
checksummed source catalog were consulted. The source PDF equations were
visually inspected and retained in the diagnostic directory:

- Drela, unsteady description, **p.9, Eqs.37–40**: centroid acceleration,
  real-mass force, angular-inertia couple and precession.
- Drela, steady description, **p.17, Eq.80** and **p.18, Eqs.81–83**:
  section inertia and the finite-segment `μ Δs²/12` correction.
- Steady **pp.12–13, Eqs.50,55–56**: endpoint averaging and conservative
  distributed-load balance.
- Unsteady **p.9, Eqs.43–44**: apparent-fluid acceleration loads needed
  to complete the coupled mass-matrix comparison.

Jan Part IV §3.4, p.15 and the original Pazy model/driver remain the case
setup authority. The two states are the saved cosine40/80 equilibria from
the [96 m/s refinement audit](isae-ae4-high-mode96-20261113.md). Both retain
the original wall, fixed frame, zero incidence, density 1.23, circulation
lag and declared updated-influence setting. Fresh base residuals pass.

The independent calculation uses the original model's mass per length
**0.6787 kg/m**, centroid offset **−0.005 m along the chord**, and chord-axis
inertia per length **6.9567e−5 kg·m**. Normal-axis inertia is **4.2793e−4
kg·m** through `t=0.52`, increasing linearly to **0.0041 kg·m** at `t=0.55`.
Span-axis inertia is the sum of chord- and normal-axis inertias. The finite
segment correction is included once in each transverse axis.

These constants and linear tables are transcribed independently of production
section-property and inertia helpers. The audit also verifies their parsed
values, including zero additional mass and damping. It accounts for the
small distinction between the original root parameter `t=0.0001` and physical
root coordinate `z=0`. Body-axis orientation is explicitly `c=+x`, `s=+z`,
`n=−y`; the expected body inertia therefore has the appropriate axis ordering.

Expected real loads and nodal transfer do not call production inertia,
parallel-axis, rotary-correction or load-transfer helpers. The current
declared structural rule averages completed endpoint loads using unloaded
material lengths. The separate fluid calculation uses current Glauert
locations and current interval lengths. These disclosed conventions are
checked implementations of the selected formulation, not authentication of
the archived executable's exact quadrature or node placement.

## Results

| Mesh | Complete acceleration columns | Numerical checks | Relative error of complete mass block |
|---|---:|---:|---:|
| Cosine40: 42 nodes | 252 | 422 | 1.075e−15 |
| Cosine80: 82 nodes | 492 | 662 | 2.334e−15 |

Every translational- and angular-acceleration column is checked over **all
rows** of the full descriptor system, including the algebraic columns at the
clamped root. The largest individual column error is **1.305e−14 relative**,
below the unchanged **1e−10** gate. Independently assembled real and fluid
blocks are saved separately. No computed production load is substituted
into the expected complete acceleration block.

The **24 physical motion profiles** cover quadratic and sinusoidal fields
and the real/imaginary parts of the higher-frequency mode, for translational
acceleration, angular acceleration and angular velocity. They obey the root
clamp. Centered odd responses isolate acceleration loads; centered even
responses isolate centrifugal and precession loads. The actual quantities
come from fresh full residual evaluations and the separate real-load output.

Maximum real nodal-force discrepancy is **8.37e−16 N**, and maximum real
nodal-couple discrepancy is **4.24e−18 N·m**. Expected loads also reproduce
the element-end contributions, global moments about three origins, combined
solid/fluid acceleration loads, full physical residuals and saved M actions.
The load gate is **1e−12 absolute plus 1e−10 times the expected norm**. The
largest load discrepancy uses only **5.50e−5 of its allowed gate**; no gate
was relaxed after observing the results.

The source configuration contains no active point mass, so zero-mass Weight
placeholders are not turned into new masses. This audit does not validate
general point objects, nonzero aircraft-frame rotation, large deformation,
all kinematic-state derivatives, or arbitrary models. It does not check the
complete structural stiffness matrix or prove the archived ASWING setup.

## Interpretation and next work

The [refinement finding](isae-ae4-high-mode96-20261113.md) remains unchanged:
the higher pair's real part is **−0.137936/s native**, **−0.095961/s cosine40**,
**+0.023701/s cosine80**, and **+0.053766/s cosine160**. Native damping errors
and incomplete spatial convergence remain failures. Independent agreement
of the checked inertia equations is evidence about those terms, not a new
native pass or proof of the full aeroelastic model.

Next independently check the **elastic constitutive and structural balance
derivatives** at the same state: centroid/elastic-axis offsets, EI coupling,
the GJ discontinuity, endpoint averaging and equilibrium-load geometric
terms. Retain the original coefficients, constraints, full matrices and
native targets. Exact historical node placement, startup/restraint settings
and native mode identity remain open regardless of that check's outcome.

Both workers completed and were reaped. Maximum use was **0.961 CPU seconds,
1.081 supervised wall seconds and 91.5 MiB RSS**, with separately bounded
library preload. Limits remain one BLAS thread and **512 MiB address space
/15 CPU seconds /25 wall seconds**. No production source changed, and no
browser, build, WASM or background solver job ran.

Primary accounting remains **357 passes, 23 paired failures, 16 unmatched,
12 unknown initial values and 792 unrun**. Failed paired errors remain median
**9.017%**, range **5.498–117.182%**. These diagnostics do not change the
primary denominator, overlapping 86/108 sample or separate 9,480-component
historical modal archive. AE-4 and the project remain incomplete.

- [Prospective plan and source hashes](../../artifacts/isae/ae4-real-inertia96-20261113/plan.json)
- [Assessment and all checks](../../artifacts/isae/ae4-real-inertia96-20261113/assessment.json)
- [Independent oracle and probe implementation](../../artifacts/isae/ae4-real-inertia96-20261113/run.py)
- [Prior aerodynamic apparent-load audit](isae-ae4-apparent-load-audit-20261112.md)
