# Independent six-input loaded tip compliance

Twenty-four cases compare all six tip-force/moment inputs and their complete
nodal motion fields against an independently integrated continuum rod tangent.
The rod has fixed root position/orientation, finite diagonal stiffness and
coincident section axes. Three axial preloads, zero/nonzero uniform twist and
four meshes are specified before execution.

All twelve scoped gates pass. At 32 intervals, the largest relative differences
are 1.254e-4 for the complete tip-compliance matrix and 1.291e-4 across nodal
responses. Errors decrease approximately fourfold on each mesh doubling.
The continuum solution separately agrees with the untwisted closed form within
5.55e-14 in the stated dimensionless normalization. Both continuum integration
tolerances and production differentiation steps are checked.

A constant spatial end torque is not a conservative orientation potential.
The reference retains its physical stiffness asymmetry and separates it from
the additional, converging midpoint-discretization error. Raw nonsymmetry is
therefore not interpreted as a new physical defect. No production correction
is indicated by these cases.

This extends the [four-field energy check](loaded-structure-tangent.md) to six
complete boundary-driven responses. It does not prove the full distributed-load
operator, actual Durrant loading, offsets/rigid limits, aerodynamic tangent,
dynamic energy conservation, eigenmodes or flutter agreement.

The [summary](loaded-tip-compliance.json), [derivation and limits](loaded-tip-compliance-report.txt),
and [portable archive](loaded-tip-compliance-evidence.zip) retain all matrices,
the fixed plan, source snapshots, terminal records and the initial adapter
serialization failure. Only the adapter's list-to-array conversion changed
before the passing run; the plan, physics and gates remained unchanged.
After extraction:

```sh
python verify-bundle.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  PYTHONDONTWRITEBYTECODE=1 python run_compliance.py \
  --repo production --plan plan.json --output replay
```

The first command audits existing evidence. The second repeats the numerical
study with NumPy/SciPy and requires a new output directory.
