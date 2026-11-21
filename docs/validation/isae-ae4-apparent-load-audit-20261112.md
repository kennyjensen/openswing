# AE-4: independent apparent-mass force and moment audit

The apparent-mass terms agree with Drela's unsteady equations at the accepted
79 m/s Pazy state. **All 360 checks in two revised diagnostic jobs pass**,
covering 30 prescribed motion fields and 20 saved mass-matrix actions across
the nominal 40/80 meshes. This audit changes no production equation, physical
parameter or native acceptance gate and adds no primary comparison votes.

The assessment was observed at **2026-11-12T17:35:31.607969+00:00**. The primary
score at that observation remained **227/1,200**. The native frequency error
at 79 m/s is still unresolved; this is a check of the declared implementation,
not authentication of the missing historical discretization settings.

## Published equations and independent calculation

The [authoritative reference index](aswing-authoritative-references.md) and its
checksummed catalog retain Jan Part IV, §3.4, and Drela's technical descriptions.
Unsteady **Eqs. 41–44, p. 9**, place the normal apparent-mass acceleration at
midchord and include the velocity/angular-rate contribution to both force and
pitching moment. The aerodynamic sampling and source-resultant transfer remain
the explicitly declared current discretization.

For this straight vertical wing, chord is 0.1 m, density is 1.23 kg/m³,
freestream is 79 e_x, section span is e_z and normal is −e_y. The axis is at
midchord, so its arm to midchord is zero. With
`k = (pi/4) * rho * chord^2 * ds`, the integrated linear contributions are:

```
F_am,y = -k * (79 * omega_z + acceleration_y)
M_am,z = -k * (chord/4) * (79 * omega_z + chord/8 * angular_acceleration_z)
```

All other components vanish to first order under these conditions. The audit
checks the straight geometry, zero circulation, axis location and properties
against the pinned original model and saved equilibrium. It reconstructs
Glauert stations from material node coordinates and current strip lengths from
loaded coordinates. It independently interpolates nodal motion, computes the
above loads and transfers the section wrench symmetrically to both endpoints,
including the offset from the Glauert sample to the arithmetic midpoint.
Expected apparent loads do not call production inertia or transfer helpers.

Each mesh has five spatial fields—linear, quadratic, third sine and the real
and imaginary parts of the saved low-mode motion. Each is applied separately
as translational acceleration, angular acceleration and angular velocity.
All profiles retain an exactly fixed root. Positive/negative evaluations isolate
the odd response, removing quadratic transport terms. Section force and moment,
nodal loads, endpoint wrenches and moment conservation about three origins are
checked for every field. Acceleration fields also check the saved mass-matrix
and physical residual actions.

| Quantity | Largest absolute defect |
|---|---:|
| Eq. 43 section-force vectors | 1.55e−17 N |
| Eq. 44 section-moment vectors | 4.00e−19 N·m |

Each load comparison uses `1e-12 + 1e-10 * expected_norm` in that quantity's
units; moment conservation uses the sum of strip contribution magnitudes.
The largest load/conservation defect occupies **0.000480% of its allowed
diagnostic tolerance**. Including the preliminary modal-root check, the largest
fraction is **0.0667%**; the assessment's `maximum_load_gate_fraction` field
includes that root check despite its broad field name.
Native comparisons retain the user's 5% tolerance and existing near-zero gates.

Real inertia and other aerodynamic loads are measured production contributions
when isolating the apparent-mass transfer. They are not independently derived
by this audit. The mass-matrix checks therefore validate its apparent-load
action after accounting for measured real inertia; they are not a second
independent real-inertia validation. Historical native sampling and arbitrary
deformed geometry also remain outside this straight-wing oracle.

## Retained setup rejection

The first diagnostic used a uniform acceleration that moved the clamped wall
root. The solver correctly rejected it before completing numerical comparisons.
That process returned code 1, was reaped, and did not time out. Its original
script, plan, stderr and receipt remain intact in the
[first attempt](../../artifacts/isae/ae4-apparent-load-audit-20261112/).
The original nominal-80 job was not run.

A fresh plan replaces the uniform field with a quadratic field satisfying the
root constraint. Saved modal root roundoff is checked against the predeclared
1e−12 geometry gate before setting it exactly zero. The
[correction record](../../artifacts/isae/ae4-apparent-load-audit-r2-20261112/diagnostic-correction.json)
pins the first attempt. No solver boundary condition was relaxed.

## Evidence and next work

- [Revised plan and input hashes](../../artifacts/isae/ae4-apparent-load-audit-r2-20261112/plan.json)
- [Independent audit implementation](../../artifacts/isae/ae4-apparent-load-audit-r2-20261112/run.py)
- [Assessment, all checks and terminal receipts](../../artifacts/isae/ae4-apparent-load-audit-r2-20261112/assessment.json)
- [Earlier circulation-rate audit](isae-ae4-rate-load-audit-20261112.md)

Both revised children completed and were reaped within the unchanged one-thread
512 MiB address-space, 15 CPU-second and 25 wall-second limits. No browser or
build check ran. The next work is broader registered native sweep coverage;
retain the 79 m/s mismatch, near-onset damping errors, unresolved native setup,
mode identity and spatial-convergence gate.
