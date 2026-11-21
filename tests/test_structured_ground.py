"""Strict ground rejection must backtrack an invalid mounted Newton proposal."""
from pathlib import Path

import numpy as np
import pytest

from openswing.aero import FlightCondition
from openswing.asw import parse_asw
from openswing.ground import GroundIntersectionError, GroundPlane
from openswing.network import StaticNetwork
import openswing.structured_static as static


def mounted(height=2.):
    model = parse_asw(Path('examples/flexible.asw').read_text())
    condition = FlightCondition(speed=10., alpha=-3., beta=0., mach=0.,
                                ground_effect=1, position_earth=[0., 0., height])
    return StaticNetwork(model, 4, condition, None, [])


def test_crossing_newton_proposal_backtracks_to_same_physical_state(monkeypatch):
    reference = mounted()
    expected, _ = static.equilibrate(reference, tolerance=1e-8)
    net = mounted()
    root_z = 6*net.node(1, 0.)+2
    original_solve = static.block_solve
    original_clearance = GroundPlane.clearance
    proposals, rejected = [], []

    def oversized_once(*args, **kwargs):
        direction = original_solve(*args, **kwargs)
        if not proposals:
            # Keep the computed direction except one deliberately excessive
            # constrained-root translation. The ordinary step cap then moves
            # that root downward by L, across the unchanged ground plane.
            altered = direction.copy()
            scale = max(1., float(np.max(abs(direction[:net.operating_start]))))
            altered[root_z] = -scale
            assert net.L > net.condition.position_earth[2]
            proposals.append((direction.copy(), altered.copy()))
            return altered
        return direction

    def clearance(plane, *args, **kwargs):
        try:
            return original_clearance(plane, *args, **kwargs)
        except GroundIntersectionError as error:
            rejected.append(str(error))
            raise

    with monkeypatch.context() as patch:
        patch.setattr(static, 'block_solve', oversized_once)
        patch.setattr(GroundPlane, 'clearance', clearance)
        actual, _ = static.equilibrate(net, tolerance=1e-8)
    assert len(proposals) == 1
    assert rejected  # The physical guard ran; the test does not fabricate errors.
    original, altered = proposals[0]
    unchanged = np.arange(len(original)) != root_z
    np.testing.assert_array_equal(altered[unchanged], original[unchanged])
    assert net.iteration_fields is None and net.tangent_influences is None
    np.testing.assert_allclose(actual, expected, rtol=1e-8, atol=1e-8)

    # Fresh caches and the entire original equations, at full physical load.
    fresh = mounted()
    residual, data = fresh.residual(actual, factor=1., detail=True)
    assert np.isfinite(residual).all()
    assert np.max(abs(residual)) <= 1e-12
    assert data['aero']['ground_plane']['minimum_clearance'] > 0.


def test_initial_crossing_geometry_is_still_rejected_before_tangent(monkeypatch):
    def unexpected_tangent(*args, **kwargs):
        raise AssertionError('Invalid initial geometry reached the rank tangent')

    monkeypatch.setattr(static, 'check_initial_rank', unexpected_tangent)
    with pytest.raises(GroundIntersectionError, match='touches or crosses'):
        static.equilibrate(mounted(height=-1.), tolerance=1e-8)
