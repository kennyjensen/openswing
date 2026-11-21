# SA-6: documented velocity-reference derivative bug

2026-10-31. Two independent coordinate-transformation regressions pass in
6.03 seconds, using one native process and one BLAS thread. No browser, Vite
server or background worker was started. No production equation or registered
ISAE result changes.

## Source evidence

Drela's [ASWING 5.85 version note](../../.reference/version_notes.txt) (9 December
2008, lines 903–913) describes missing origin-velocity contributions in some
rotation-rate derivatives when the velocity reference is displaced. Steady
equations 181–184 define the local reference air data; equations 218–219 define
the stability axes and normalized rate inputs. The retained
[technical description](../../.reference/asw_theory.txt) supplies both.

OpenSwing's `StateFlow.velocity` differentiates the local expression directly:

```
V(r) = V_ref - Omega × (r - r_ref) + V_induced
```

Moving `r_ref` by `d`, while holding the reference speed and angles fixed, adds
`Omega × d` to the origin airflow. Consequently each rate derivative acquires
a linear combination of the uniform-speed, alpha and beta derivatives.
This term is already present through `points - model.reference[3]`.

The four paired SA-6 input files all specify zero moment, acceleration and
velocity reference points. The original `Post_Stall_15c.sh` changes speed,
alpha and F1, with no velocity-reference override. All 44 paired native
exports print zero **moment** references; they do not print velocity references.
The version-note bug therefore does not explain the literal retained setup.
The exact historical executable and any unrecorded settings remain unknown;
zero native velocity references are not inferred from the moment headers.

## Independent verification

[The regression](../../tests/test_rigid_velocity_reference.py) tests a controlled
wing at 17° alpha and 3° beta, with unequal reference chord/span and a reference
displacement of `[1.7, -0.9, 0.6]` m. It runs both pointwise circulation and
four Fourier modes on six intervals.

For each representation it checks:

- All six force/moment derivative outputs and circulation responses against
  the independently assembled velocity-coordinate transformation, including
  reference and origin moment outputs. Tolerances: relative `2e-11`, absolute
  `2e-10`. Each derivative calculation retains one physical evaluation and
  one factorization.
- The same physical flow at finite body rates `[0.07, -0.13, 0.11]` rad/s,
  represented at the displaced reference by changing its speed and angles.
  Fresh nonlinear solutions preserve dimensional forces, moments and
  circulation within the same tolerances.
- Converged bases below `1e-8` and analytic linear residuals below `1e-12`.

The test deliberately uses frozen influences, prescribed PG Mach and no volume
sources. This isolates the kinematic identity from changes in the separately
assumed wake or uniform-flow volume model. It does not establish reference
invariance for those models or authenticate the historical ASWING version.
Existing state-derivative finite-difference tests separately exercise nonzero
velocity references, current influences, bodies and ground effects; those tests
were inspected, not rerun in this check.

Command (all thread variables set to one, automatic pytest plugins disabled):

```
.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_rigid_velocity_reference.py
```

Result: **2 passed in 6.03s**, exit 0. Four analytic base solves and four finite-rate
physical solves complete. [Receipt and source hashes](../../artifacts/isae/sa6-velocity-reference-20261031/receipt.json)
retain the exact command, original test output and literal-reference audit.

The SA-6 qualified state result remains **2,780/3,168**; the registered baseline
and 3% acceptance policy are unchanged. This closes one documented historical
bug hypothesis, without resolving the remaining local stall/rate differences.
