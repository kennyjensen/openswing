"""The grouped tangent must retain the original scalar perturbation equations."""
from pathlib import Path
import numpy as np
import pytest
from openswing.aero import FlightCondition
from openswing.asw import parse_asw
from openswing.network import StaticNetwork
from test_network import beam, model


def dense_difference(net, x, factor, **options):
    base = net.residual(x, factor, **options)
    columns = []
    for j in range(net.size):
        h = 1e-6*max(1., abs(x[j]))
        trial = x.copy(); trial[j] += h
        columns.append((net.residual(trial, factor, **options)-base)/h)
    return np.array(columns).T


@pytest.mark.parametrize('joint', [0, 1, 2])
@pytest.mark.parametrize('dynamic', [False, True])
def test_grouped_wrenches_match_scalar_columns_on_offset_connected_beams(joint, dynamic):
    beams = beam()+beam(2,start=2.3,end=4.3,z=.2)
    beams = beams.replace('End', 't Cea Nea Cta Nta\n0 .12 -.07 -.03 .08\n2 .12 -.07 -.03 .08\nEnd')
    net = StaticNetwork(model(beams, f'Ground\n1 0 0\nEnd\nJoint\n1 2 2 0 {joint}\nEnd\n'), 4, None, [0,0,-9.8], [])
    rng = np.random.default_rng(137+joint)
    x = rng.normal(0,.03,net.size)
    options = {'elastic_motion':tuple(rng.normal(0,.1,(4,net.nn,3)))} if dynamic else {}
    before = net.nfev
    # Select the grouped finite-difference fallback explicitly; direct
    # mechanical/circulation blocks have separate physical derivative tests.
    actual = net.jacobian(x,.7,_direct_mechanics=False,_direct_circulation=False,**options)
    assert net.nfev-before == 1+net.size-6*net.ne+12
    np.testing.assert_array_equal(actual, dense_difference(net,x,.7,**options))


@pytest.mark.parametrize('example', ['rectangular','flexible','powered','wing-body','articulated'])
def test_coupled_tangent_matches_scalar_columns_at_non_equilibrium(example):
    model = parse_asw(Path(f'examples/{example}.asw').read_text())
    condition = FlightCondition(alpha=5, rates=[.01,-.02,.03], acceleration=[.2,-.1,.3])
    net = StaticNetwork(model,4,condition,None,[])
    rng = np.random.default_rng(931)
    x = rng.normal(0,.001,net.size)
    # A nonzero circulation and internal wrench ensure load sensitivities matter.
    x[net.gamma_start:net.operating_start] += .05
    before = net.nfev
    actual = net.jacobian(x,.6,_direct_mechanics=False,_direct_circulation=False)
    expected_calls = net.size+1 if net.hinges else 1+net.size-6*net.ne+12
    assert net.nfev-before == expected_calls
    np.testing.assert_array_equal(actual,dense_difference(net,x,.6))


def test_custom_structural_load_target_retains_general_tangent():
    model = parse_asw(Path('examples/instrumented-oscillator.asw').read_text())
    target = dict(variable='power.1',quantity='user.force',expression='sensor("1.force_local.s")',target=5,residual_scale=1,unit='input F')
    net = StaticNetwork(model,4,FlightCondition(speed=10,alpha=0,mach=0),[0,0,0],[],operating_constraints=[target])
    x = np.random.default_rng(44).normal(0,.001,net.size)
    before = net.nfev
    actual = net.jacobian(x,.8)
    assert net.nfev-before == net.size+1
    np.testing.assert_array_equal(actual,dense_difference(net,x,.8))
