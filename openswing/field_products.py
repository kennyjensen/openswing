"""Apply retained source Jacobians to all original stencil right-hand sides.

No geometric Taylor term is removed: all four physical geometry samples enter
this matrix product. Receiver terms, nonlinear physics and refinement retain
those original samples. Temporary packing belongs to the caller's field budget.
"""
import numpy as np


def source_product(first,second,scalar,d_first,d_second,d_scalar):
    receivers,sources,xyz,_=first.shape
    matrix=np.concatenate((first,second,scalar[...,None]),axis=-1)
    matrix=np.ascontiguousarray(matrix.transpose(0,2,1,3)).reshape(receivers*xyz,sources*7)
    values=np.concatenate((d_first,d_second,d_scalar[...,None]),axis=-1)
    values=values.reshape(len(d_first),sources*7)
    return (values@matrix.T).reshape(len(d_first),receivers,xyz)
