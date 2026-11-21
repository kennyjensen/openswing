"""Analytical source load/reaction columns in complete time-system tangents.

At fixed geometry and motion these coordinates enter the source beam equations
linearly. They do not enter the time kinematics or circulation equations. Force
and moment measurements need a controller chain rule and retain full stencils.
"""
import numpy as np
from scipy.sparse import block_diag
from .mechanical_tangent import (source_network_mechanical_columns,
                                 MechanicalDerivativeUnavailable)


def attach_mechanical_columns(system, function, capture, *, stages=1):
    """Attach full physical columns; capture supplies each stage's actual data.

    The state coordinate ordering/scaling is shared by cold feedback, BDF and
    the ordinary continuous Radau chart. Stage force/reaction rates do not
    enter any equation, so these Radau columns have only diagonal stage blocks.
    """
    from .source_discrete import SourceDiscreteNetwork
    from .source_dynamics import SourceDynamicNetwork
    n = system.network
    if not isinstance(n, SourceDiscreteNetwork) or n.operating.custom:
        return
    if getattr(n.constitutive_motion, '__func__', None) not in (
            SourceDiscreteNetwork.constitutive_motion, SourceDynamicNetwork.constitutive_motion):
        return
    if system.feedback is not None and any(
            signal.startswith(('F', 'M')) for signal in system.feedback.signals):
        return

    def columns(x):
        if len(x) % stages:
            raise MechanicalDerivativeUnavailable('Invalid source time-stage coordinates.')
        size = len(x) // stages
        data = [{} for _ in range(stages)]
        capture(x, data)
        blocks = []
        for values, state in zip(x.reshape(stages, size), data):
            matrix, _ = source_network_mechanical_columns(n, state,
                np.maximum(1., abs(values)), 1e-6, row_count=size)
            blocks.append(matrix)
        indices = np.concatenate([stage*size+np.arange(6*n.nn, n.gamma_start)
                                  for stage in range(stages)])
        return indices, block_diag(blocks, format='csc') if stages > 1 else blocks[0]

    function.direct_mechanical_columns = columns
