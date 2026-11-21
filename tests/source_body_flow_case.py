"""Portable whole-residual oracle for moving source wing/body flow columns."""
import numpy as np
from openswing.aero import FlightCondition
from openswing.asw import parse_asw
from openswing.circulation_tangent import circulation_columns
from openswing.operating import time_load_constraints
from openswing.source_airflow import SourceAirflowNetwork
from openswing.structured_static import IterationFields


def check_body_columns(source, lag_coefficient=0., frame='fixed', fourier=False):
    model=parse_asw(source,beam_interpolation='drela-segspl-v1')
    condition=FlightCondition(speed=23.,alpha=7.,beta=3.,mach=.1,
        rates=[.03,-.04,.02],ground_effect=1,position_earth=[0.,0.,30.],
        **(dict(circulation_modes={1:3}) if fourier else {}))
    n=SourceAirflowNetwork(model,4,condition,[.3,-.2,-9.],[],
        operating_constraints=[] if frame=='fixed' else time_load_constraints(frame))
    x=np.random.default_rng(729).normal(0.,.002,n.size);x[n.gamma_start:]+=.08
    factor=.6
    local=tuple(np.random.default_rng(410+k).normal(0.,.02,(n.nn,3)) for k in range(4))
    rate=np.full(n.circulation_basis.panels,.03)
    def full(values):
        change=n.circulation_basis.decode((values[n.gamma_start:n.operating_start]-x[n.gamma_start:n.operating_start])*n.gamma_scale)
        return n.residual(values,factor,elastic_motion=local,
            circulation_rate=rate+lag_coefficient*change)
    baseline=full(x).copy()
    fields=IterationFields();fields.capture_circulation=True
    n.iteration_fields=fields;n.aero_key=None
    try:
        full(x)
        direct=circulation_columns(n,fields,factor,circulation_rate_factor=lag_coefficient)
    finally:
        n.iteration_fields=None;n.aero_key=None
    checks=[]
    for width in (1e-5,3e-6):
        reference=[]
        for j in range(n.gamma_start,n.operating_start):
            delta=np.zeros(n.size);delta[j]=width
            reference.append((full(x+delta)-full(x-delta))/(2*width))
        reference=np.array(reference).T
        error=abs(direct-reference)/(1+abs(reference))
        row,column=np.unravel_index(error.argmax(),error.shape)
        checks.append(dict(width=width,maximum_scaled_error=float(error.max()),
            maximum_absolute_error=float(abs(direct-reference).max()),row=int(row),column=int(column)))
        assert error.max()<2e-8,checks[-1]
    np.testing.assert_array_equal(full(x),baseline)
    return dict(status='PASS_SOURCE_BODY_FLOW_COLUMNS',lag_coefficient=lag_coefficient,
        frame=frame,fourier=fourier,nodes=n.nn,intervals=n.ne,checks=checks,
        matrix=direct.tolist(),residual=baseline.tolist())
