"""Small real networks and an exact zero-load baseline; no equilibrium solver."""
from pathlib import Path
import numpy as np
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork

FIXTURE = Path(__file__).with_name('data')/'derivative-quiet-wing.asw'

def make_network(*, panels=4, condition=None):
    model = parse_asw(FIXTURE.read_text())
    condition = FlightCondition(alpha=0, beta=0, mach=0, stall=False) if condition is None else condition
    return StaticNetwork(model, panels, condition, None, [])

def zero_state(network):
    return np.zeros(network.size)

def displaced_state(network):
    """Deterministic off-equilibrium state for direct-column differentiation only."""
    x = np.random.default_rng(1729).normal(0, .001, network.size)
    x[network.gamma_start:network.operating_start] += .08
    return x

def centered_gamma_columns(network, x, step=1e-6):
    columns = []
    for j in range(network.gamma_start, network.operating_start):
        h = step * max(1., abs(x[j]))
        plus, minus = x.copy(), x.copy()
        plus[j] += h
        minus[j] -= h
        columns.append((network.residual(plus) - network.residual(minus)) / (2*h))
    return np.stack(columns, axis=1)

def collect_audit():
    values = {}
    def collect(payload):
        values.update({key: value.copy() if isinstance(value, np.ndarray) else value
                       for key, value in payload.items()})
    return values, collect
