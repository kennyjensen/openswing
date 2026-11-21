"""Compare regrouped arithmetic without treating bitwise equality as physics.

These are supplemental comparisons with the old arithmetic, not physical
reference oracles. The complete nonlinear residual gate remains 2e-8 and the
independent 80-digit product tests bound dot-product rounding by contributions.
"""
import numpy as np


def operators_close(actual,expected,geometry_columns,*,mass=False):
    difference=actual-expected;difference.eliminate_zeros()
    if mass:
        assert difference.nnz==0
        return
    outside=difference[:,geometry_columns:].copy();outside.eliminate_zeros()
    assert outside.nnz==0,'Packing changed a non-geometric operator column'
    if difference.nnz==0:return
    changed=difference.tocoo();reference=np.asarray(expected[changed.row,changed.col]).ravel()
    error=np.max(abs(changed.data)/(1+abs(reference)),initial=0.)
    assert error<=2e-8,error
