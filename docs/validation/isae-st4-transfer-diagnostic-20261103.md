# ST-4 independent discretization diagnosis

All **93/93 selected frequencies** from the five runnable original vacuum models
on 16/32/64 nominal intervals agree with a separate six-state transfer calculation.
The maximum relative difference is **3.2412e-12**, below the declared **1e-8** gate.
No new OpenSwing modal solves were needed. All original archived-ASWING counts
and mesh failures remain unchanged: this adds equation verification, not native validation.

## Method and input audit

The independent calculation specializes Drela's [Technical Description](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf)
Eqs. 48/50/54–56/80 to each straight, uniform, clamped beam in unloaded vacuum.
It propagates elastic-axis displacement, bending slope, torsion, bending moment,
shear and torque. Endpoint averaging gives the interval propagator
`solve(I - ds*G/2, I + ds*G/2)`. The bending rotary inertia includes
`mu*ds^2/12` exactly once; the torsional inertia retains the section polar value.
Exact point-mass jumps preserve both chordwise offsets and the small spanwise
pylon offsets implied by the original parameter coordinate.

The companion continuous solution uses matrix exponentials of the same beam
ODE, without a mesh correction. Neither calculation imports an OpenSwing
solver, residual, assembled matrix or parser. A restricted literal-table audit
checks original stiffness/mass scalers, offsets and point weights. All five model
hashes match the pinned upstream records. Independently generated uniform nodes
plus mandatory mass stations match the retained meshes. Twelve distinct closed-form
controls cover discrete torsion on three grids and continuous Euler bending.

Retained frequencies only identify isolated 1% root brackets. Determinants and
boundary singular-value checks determine the roots; no physical parameter is
fitted. This checks the selected ordinal frequencies, not the completeness or
mode shapes of the full spectrum. The six-state specialization is appropriate
for these uniform planar models, not a replacement for the full solver.

## Results

| Original variant | Frequencies checked | Largest discrete relative difference | Largest 64-interval error against continuum | Largest continuum difference from archive |
|---|---:|---:|---:|---:|
| Weight7a | 18 | 3.2125e-12 | 0.1228% | 0.4005% |
| Weight7c | 18 | 3.2412e-12 | 0.1364% | 0.4456% |
| Weight7d | 21 | 3.2214e-12 | 0.3023% | 0.8670% |
| Weight7e | 18 | 3.2383e-12 | 0.1532% | 0.4478% |
| Weight7f | 18 | 3.1932e-12 | 0.1514% | 0.4475% |

The largest earlier mesh failure is Weight7d's seventh frequency:

| Calculation | Frequency, Hz |
|---|---:|
| OpenSwing, 16 intervals | 177.307485 |
| OpenSwing, 32 intervals | 170.861634 |
| OpenSwing, 64 intervals | 169.314415 |
| Continuous beam limit | 168.804148 |
| Archived ASWING | 170.280462 |

Its error against the continuous beam falls by factors **4.133** and **4.032**
when the interval count doubles, consistent with second-order discretization.
The 32-to-64 change remains **0.9138%**, above the original **0.1%** mesh gate.
The 64-interval frequency is **0.3023%** above the continuous limit. The limit
is **0.8670%** below the archive, so further refinement alone moves this result
farther from the archived value. A closer intermediate mesh is not evidence
that it recovers the historical node distribution.

These results support the implemented linear beam equations, inertia and
point-mass coupling for this declared setup. They do not resolve the original
ASWING mesh, gravity/base state, vacuum toggle, or archived mode identity.
Those setup differences remain hypotheses; this audit does not identify their
historical values. There is no justification here for changing physical
parameters or replacing the published discretization to fit the archive.

## Reproduction and scope

Run `scripts/verify-isae-st4-transfer-current.py --case Weight7d` with the project
venv; use the other four variant names for their separate jobs. Runs use one
BLAS thread and a 60-second process cap, serially. The completed modal artifacts
must be available at their recorded paths. The machine report contains all
frequency results, analytic controls, root witnesses and source hashes.
The preliminary system-Python invocation failed before calculation because
NumPy was unavailable; that log is retained alongside successful venv runs.

Production equations and original accuracy gates are unchanged. This audit ran
in CPython; it adds no ST-specific browser solve. See the
[structural comparison report](isae-st1-st6-current-20261103.md) for all ST-1–ST-6
counts and unavailable references, and the
[machine report](isae-st4-transfer-diagnostic-20261103.json) for this diagnosis.
