# Independent loaded structural tangent check

Twenty-four exactly axial- and torsion-preloaded rod cases check the production
structural tangent against an independently derived Cosserat energy second
variation. The reference has finite extension and shear, coincident section
axes and diagonal stiffness. Four smooth virtual fields, tension/compression,
zero/nonzero twist and four meshes distinguish preload terms from material
stiffness and discretization error.

All seven scoped gates pass. The axial geometric stiffness matches its exact
finite-mesh formula within 1.80e-9 N m. At finite twist, the internal tangent is
slightly nonsymmetric after the SO(3) coordinate pullback; its asymmetry and its
error against the continuum energy Hessian decrease approximately fourfold on
each mesh doubling. The largest relative continuum difference at 32 intervals
is 3.54e-4. No missing axial prestress term or nonconvergent defect was identified
in these cases, and no production correction follows from this check.

These are internal elastic tangent checks. They do not verify the actual loaded
Durrant wing, its offsets/rigid limits, aerodynamic feedback, complete operators,
dynamic energy conservation, eigenvalues or flutter boundary. The existing
loaded-wing discrepancy remains unresolved.

The [summary and terminal record](loaded-structure-tangent.json),
[full derivation and limitations](loaded-structure-tangent-report.txt), and
[portable evidence archive](loaded-structure-evidence.zip) retain all matrices,
perturbation steps, source pins and the exact 58-module kernel. After extraction:

```sh
python verify-bundle.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  PYTHONDONTWRITEBYTECODE=1 python check_loaded_tangent.py \
  --repo production --output replay.json
```

The first command audits retained bytes; the second repeats the numerical check
with NumPy/SciPy. The archive also specifies an unexecuted continuum
tip-compliance comparison. That specification is not implementation or passing
evidence.
