"""Source body-load derivatives against complete physical residual columns."""
from pathlib import Path
import numpy as np
import pytest
from source_body_flow_case import check_body_columns


@pytest.mark.parametrize('lag_coefficient,frame,fourier',[
    (0.,'fixed',False),(17.,'fixed',False),(17.,'free',False),(17.,'free',True)])
def test_wing_body_circulation_columns_preserve_source_endpoint_loads(lag_coefficient,frame,fourier):
    check_body_columns(Path('examples/wing-body.asw').read_text(),lag_coefficient,frame,fourier)


def test_complete_source_wing_body_pencil_matches_physical_directions():
    from openswing.aero import FlightCondition
    from openswing.asw import parse_asw
    from openswing.linear_dynamics import make_system,linearize
    from openswing.source_airflow import AIRFLOW_POLICY
    from test_source_moving_system import directional
    model=parse_asw(Path('examples/wing-body.asw').read_text(),beam_interpolation='drela-segspl-v1')
    system,_=make_system(model,FlightCondition(speed=10.,alpha=2.,beta=1.,mach=.1),
        4,gravity=[0.,0.,0.],structural_operator=AIRFLOW_POLICY,tolerance=1e-10)
    a,m=linearize(system,sparse=True)
    zero=np.zeros(system.size);rng=np.random.default_rng(5213)
    for _ in range(3):
        q=rng.normal(size=system.size);q/=np.linalg.norm(q)
        rate=zero.copy();rate[system.dynamic_indices]=rng.normal(size=len(system.dynamic_indices));rate/=np.linalg.norm(rate)
        np.testing.assert_allclose(a@q,directional(lambda z:system.residual(z,zero),q),rtol=3e-7,atol=3e-8)
        np.testing.assert_allclose(m@rate,-directional(lambda z:system.residual(zero,z),rate,h=.1),rtol=3e-9,atol=3e-10)
