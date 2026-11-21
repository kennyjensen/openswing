"""Independent composed aerodynamic, real-mass and balance directional map.

The raw descriptor chart, Earth-to-body gravity, circulation and control input
are reconstructed before independently evaluating aerodynamic loads, nodal
virtual-work transfer, real-mass loads and balance/kinematic/constraint rows.
No native observed velocity, load, residual or tangent is used as an expected
physics input. There are no production imports or aircraft/linear solves.

Input seams remain the saved loaded operating point, topology, literal material
samples and this implementation's declared spatial discretization. Constitutive
beam compatibility is outside this composer. The mass/aerodynamic evaluators
are first-order maps about the stationary loaded base, not finite-motion time
integrators. Their documented body apparent-mass, aerodynamic-point, self-field
and angular-transport conventions remain explicit; this is not a claim of
historical ASWING executable parity or matched Daedalus Bode response.

API: CoupledBalanceReference(fixture,base_packet,*,aero_quadrature=32,
mass_quadrature=16).evaluate(z,zdot,control3_delta=0.). The fixture must explicitly
declare gravity_override=False and applied_loads=[]; no gravity-vector override
is inferred from a missing field. Arrays are returned in one flat dictionary:
aero__, transfer__, mass__, balance__, physical__ and external__ prefixes.
Nested balance component dictionaries/list records use further double
underscores. All wrenches use physical ASW units and body axes; nodal moments
are couples about the current node, while global moments use reference[1].
"""

import numpy as np

from daedalus_balance_reference import BalanceReference
from daedalus_full_aero_reference import FullAeroReference
from daedalus_aero_transfer_reference import AeroTransferReference
from daedalus_real_inertia_reference import RealInertiaReference


def _flatten(prefix, value, result):
    """Retain numeric leaves without invoking a native serializer or evaluator."""
    if isinstance(value, dict):
        for key, child in value.items():
            _flatten(prefix+'__'+str(key), child, result)
    elif isinstance(value, (tuple, list)):
        for index, child in enumerate(value):
            _flatten(prefix+'__'+str(index), child, result)
    else:
        array = np.asarray(value)
        if array.dtype.kind not in 'biufc' or not np.all(np.isfinite(array)):
            raise ValueError('Expected finite numeric output at '+prefix)
        if prefix in result:
            raise ValueError('Duplicate composed output '+prefix)
        result[prefix] = array


class CoupledBalanceReference:
    """Actual corrected-C16 composition with independently decoded raw inputs."""

    def __init__(self, fixture, base_packet, *, aero_quadrature=32, mass_quadrature=16):
        if fixture.get('gravity_override') is not False:
            raise ValueError('Independent gravity chart requires explicit gravity_override=False')
        if 'applied_loads' not in fixture or len(fixture['applied_loads']) != 0:
            raise ValueError('This actual-case composition requires no prescribed applied loads')
        self.fixture = fixture
        base_inputs = base_packet['inputs']
        self.condition = base_inputs['condition']
        self.balance = BalanceReference(fixture, base_inputs)
        self.size = self.balance.size
        self.control_ids = sorted(map(int, self.condition['controls']))
        self.power_ids = sorted(map(int, self.condition['powers']))
        if 3 not in self.control_ids:
            raise ValueError('The actual case must explicitly declare rudder control 3')
        self.control3_index = self.control_ids.index(3)

        def setting(values, key):
            return values[key] if key in values else values[str(key)]

        self.controls0 = np.asarray([setting(self.condition['controls'], key) for key in self.control_ids], dtype=float)
        self.powers0 = np.asarray([setting(self.condition['powers'], key) for key in self.power_ids], dtype=float)
        if not np.isfinite(self.controls0).all() or not np.isfinite(self.powers0).all():
            raise ValueError('Base control and power settings must be finite')
        circulation = fixture['layout']['circulation']
        start, width = int(circulation['start']), int(circulation['width'])
        self.gamma_slice = slice(start, start+width)
        self.gamma_scale = float(fixture['scales']['Gamma_scale'])
        if (not np.isfinite(self.gamma_scale) or self.gamma_scale <= 0
                or self.gamma_scale != circulation['scale']
                or width != 82 or start+width != self.balance.operating_start):
            raise ValueError('Expected the literal 82-component pointwise circulation chart')
        self.gamma0 = np.asarray(fixture['loaded_base']['x'])[self.gamma_slice]*self.gamma_scale
        if self.gamma0.shape != (width,) or not np.isfinite(self.gamma0).all():
            raise ValueError('Loaded raw circulation coordinates must be finite')
        explicit_g = self.condition['gravity_magnitude']
        self.gravity_magnitude = float(fixture['constants'][0] if explicit_g is None else explicit_g)
        if not np.isfinite(self.gravity_magnitude) or self.gravity_magnitude < 0:
            raise ValueError('Earth gravity magnitude must be finite and nonnegative')

        self.aero = FullAeroReference(fixture, base_packet, quadrature=aero_quadrature)
        if self.aero.control_ids != self.control_ids or self.aero.power_ids != self.power_ids:
            raise ValueError('Control/power ordering must agree across independent components')
        self.transfer = AeroTransferReference(fixture)
        zero = np.zeros(self.size)
        self.base = self.physical_from_raw(zero, zero)
        self.mass = RealInertiaReference(fixture, self.base, quadrature=mass_quadrature)
        self.evaluations = 0

    def physical_from_raw(self, z, zdot, control3_delta=0.):
        """Decode physical inputs without using native chart-stencil values."""
        z, zdot = np.asarray(z), np.asarray(zdot)
        delta = np.asarray(control3_delta)
        if (z.shape != (self.size,) or zdot.shape != z.shape or delta.shape != ()
                or not np.isfinite(z).all() or not np.isfinite(zdot).all() or not np.isfinite(delta)):
            raise ValueError('Finite complete state/rate vectors and scalar rudder increment are required')
        p = self.balance.physical_from_raw(z, zdot)
        controls = self.controls0.astype(np.result_type(z, zdot, delta, float))
        controls[self.control3_index] += delta
        p.update(
            angular_acceleration=p['alpha'],
            gamma=self.gamma0+self.gamma_scale*z[self.gamma_slice],
            gamma_dot=self.gamma_scale*zdot[self.gamma_slice],
            controls=controls, powers=self.powers0.copy(),
            gravity=p['orientation'].T@np.array([0., 0., -self.gravity_magnitude]),
        )
        return p

    def evaluate(self, z, zdot, control3_delta=0.):
        """Evaluate the full declared composition once at a prescribed raw state."""
        self.evaluations += 1
        physical = self.physical_from_raw(z, zdot, control3_delta)
        aero = self.aero.evaluate(physical)
        transfer = self.transfer.evaluate(physical, aero)
        mass = self.mass.evaluate(physical)
        external_force = transfer['nodal_force']+mass['nodal_force']
        external_moment = transfer['nodal_moment']+mass['nodal_moment']
        balance = self.balance.evaluate(physical, z, zdot, external_force, external_moment)
        result = {}
        for name, values in (
            ('aero', aero), ('transfer', transfer), ('mass', mass), ('balance', balance),
            ('physical', physical),
            ('external', dict(nodal_force=external_force, nodal_moment=external_moment)),
        ):
            _flatten(name, values, result)
        return result
