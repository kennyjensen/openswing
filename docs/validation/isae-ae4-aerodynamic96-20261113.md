# AE-4: independent aerodynamic and complete-pencil check at 96 m/s

The independent assembly passes **5,196 numerical checks** on cosine40 and
cosine80. All **4,708 columns of the complete A/M matrices** agree with the
saved production matrices. All eight saved eigenvectors satisfy the independent
pencil, with maximum normalized left/right residual **2.774e−14**.

This finds no assembly discrepancy in the checked straight, fixed-frame state.
It does **not** resolve the disagreement with archived ASWING damping, establish
spatial convergence, authenticate historical settings, or validate general
deformed-wing and moving-frame states. No production code or setting changed.

The observation was recorded at **2026-11-13T04:22:39.927299+00:00**. At this
observation, the native-reference count remained **357/1,200**. This diagnostic
adds **zero native votes**.

## Independent construction

The authoritative sources are Jan Part IV §3.4, p. 15, the pinned original Pazy
model and driver, Drela's steady description §§4.2/4.5 and Eqs. 150–160,
169/173,204–206, and the unsteady description Eqs. 31–36,43–44,49. See the
[reference index](aswing-authoritative-references.md) and checksummed catalog.

Expected geometry uses chord 0.1 m, Xax 0.5, lift slope 6.1185/rad and the analytic
self-weight axis from the [elastic audit](isae-ae4-elastic96-20261113.md).
Glauert-angle section locations are reconstructed from material node stations.
The quarter-chord force point and control-point offset follow steady
Eqs. 154–157. The selected cosine grids retain the required material node at
t = 0.52. Their exact historical correspondence remains unknown.

An independent closed-form Biot–Savart calculation supplies each unit
circulation field. It uses endpoint-vector finite segments and semi-infinite
straight rays, with opposite-circulation reflected horseshoes at the z=0 wall.
It does not call production vortex, ground-reflection or geometry helpers to
form expected values. Production helpers supply measured values only.

Every source column is checked at the control points, bound-vortex receivers
and nine off-wing wall probes: **366 field columns** in total. Same-component
cores are zero, and the own physical bound segment uses the principal-value
omission. Image bound segments remain present. The wall probes verify zero
normal flow. Maximum relative field difference is **9.578e−12**.

At this zero-lift base, the independent aerodynamic derivatives retain:

- Circulation-induced control-point flow and the original stall law's small,
  nonzero derivative at cl=0, including factor 40, width 0.05 and limits ±1.1.
- Normal rotation, local translational velocity and rotational velocity at
  the control point, sampled at the Glauert station.
- Steady and circulation-rate lift and their quarter-chord moments,
  unsteady Eqs. 34–36, plus the Eq. 49 circulation lag.
- The apparent-fluid force and moment proportional to freestream velocity
  crossed with section angular velocity, Eqs. 43–44.
- Conservative transfer into nodal force/moment balances and all kinematic
  rows, including clamped-root columns.

The previous independently constructed mechanical A block and
[real/apparent inertia M blocks](isae-ae4-real-inertia96-20261113.md) complete
the pencil. No measured production matrix entry supplies an expected entry.
Their source evidence is pinned in the prospective plan. At the base, geometry
derivatives of aerodynamic wrenches vanish because circulation, profile drag
and profile moment are zero; the flow-normal derivatives remain present.

## Results

| Nominal mesh | Matrix size | Checks | Complete A relative error | Complete M relative error |
|---:|---:|---:|---:|---:|
| 40 | 797×797 | 1,778 | 4.783e−12 | 2.468e−16 |
| 80 | 1,557×1,557 | 3,418 | 4.718e−12 | 2.770e−16 |

Maximum individual nonzero-column relative errors are **8.311e−12 for A**
and **1.305e−14 for M**. Every column is checked, including expected-zero
columns, with the prospectively declared absolute-plus-relative gate.

All **48 centered physical actions** pass: circulation, prescribed wing
motion, and real/imaginary higher-mode directions; state/rate perturbations;
steps 1e−4,1e−5,1e−6 on both meshes. Root pose and motion remain clamped.
Maximum action error is **1.661e−9 relative** against a 5e−5 gate.

The original four-mode result on each mesh is checked against the entire
independent pencil, without deleting algebraic rows or changing modal vectors.
Both left/right equations and the mass-pair normalization pass. This uses the
previously solved modes; it is not a new native comparison or eigenvalue fit.

The higher-frequency real parts remain **−0.13793642/s native**,
**−0.09596129/s cosine40**, and **+0.02370068/s cosine80**. The prior
cosine160 diagnostic is **+0.05376579/s**. The independent assembly therefore
supports the implemented operator at this state while leaving the
[native and spatial damping discrepancy](isae-ae4-high-mode96-20261113.md)
open. Historical quadrature, node positions and circulation settings remain
separate setup questions.

## Evidence and execution

- [Prospective plan](../../artifacts/isae/ae4-aerodynamic96-20261113/plan.json)
- [Assessment](../../artifacts/isae/ae4-aerodynamic96-20261113/assessment.json)
- [Independent assembly script](../../artifacts/isae/ae4-aerodynamic96-20261113/run.py)
- [Cosine40 full matrices and receipts](../../artifacts/isae/ae4-aerodynamic96-20261113/cases/n40-aerodynamic/)
- [Cosine80 full matrices and receipts](../../artifacts/isae/ae4-aerodynamic96-20261113/cases/n80-aerodynamic/)

Both numerical children completed and were reaped. Maximum use was
**1.275 CPU seconds, 1.400 wall seconds and 146.9 MiB RSS**. Library preload
was bounded separately. One BLAS thread and the unchanged **512 MiB address
space /15 CPU-second /25 wall-second** limits were retained. All pinned sources
were checked before and after execution. Browser/build/WASM checks remain held.

With this state independently checked, resume the unrun native sweep points
without changing model settings or acceptance gates. Retain the 79 m/s frequency
error, 96 m/s damping sign discrepancy and incomplete spatial convergence.
