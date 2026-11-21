"""Earth-coordinate BDF for selected origin-position histories.

The physical unknowns remain P, U, R and Omega. With selected target jets zero
outside their mask, E=P-G and W=R U-G' are complete Earth vectors. This changes
the finite-step BDF coordinates, not the continuous mechanics or actuator rows.
Accepted target samples keep their original physical time and forcing side.
"""
from dataclasses import dataclass
import hashlib
import json
import numpy as np
from .aero import AnalysisError
from .operating import TimeHistoryConstraint


@dataclass(frozen=True)
class PositionSample:
    time: float
    side: str
    signature: str
    value: tuple
    rate: tuple
    acceleration: tuple
    branch: str
    intervals: tuple = ()


class PositionHistoryLift:
    policy = 'earth-origin-position-defect-bdf-v1'

    def __init__(self, constraints, forcing, *, length_scale, velocity_scale):
        self.constraints = constraints
        self.length_scale = length_scale
        self.velocity_scale = velocity_scale
        self.tolerance = 1e-8
        self.rows = self._rows()
        self.mask = np.array([any(row.quantity == 'position_earth.'+axis for row in self.rows)
                              for axis in 'xyz'], dtype=bool)
        self.signature = self._signature(forcing)
        self._compiled_signature = self._compiled(forcing)

    def _rows(self):
        return tuple(row for row in self.constraints
                     if isinstance(row, TimeHistoryConstraint)
                     and row.quantity.startswith('position_earth.'))

    def definition(self, forcing):
        """Portable input identity; compiler last-bit differences are not inputs.

        Existing checkpoint model identity owns input units and frame references.
        Original effective offsets and parsed knots belong to this definition.
        """
        channels = []
        if forcing is not None:
            for channel in forcing.channels:
                if channel['group'] != 'targets' or channel['index'] not in {row.quantity for row in self.rows}:
                    continue
                distribution = channel['distribution']
                channels.append(dict(name=channel['name'],quantity=channel['index'],
                    relative=channel['relative'],offset=channel['initial'] if channel['relative'] else 0.,
                    factor=channel['factor'],unit=channel['unit'],
                    times=distribution.t.tolist(),values=distribution.values.tolist()))
        return dict(policy=self.policy,version=1,
            rows=[(row.variable, row.quantity, row.target) for row in self._rows()],
            mask=self.mask.tolist(),forcing=None if forcing is None else forcing.source,
            channels=channels,interpolation='piecewise natural cubic',derivative_time_unit='input T',
            support='first-left unspecified; exact-end physical interior; end-right jet zero')

    @staticmethod
    def _digest(values):
        return hashlib.sha256(json.dumps(values,sort_keys=True,allow_nan=False).encode()).hexdigest()

    def _signature(self, forcing):
        return self._digest(self.definition(forcing))

    def _compiled(self, forcing):
        # Detect mutation of live polynomial coefficients separately from the
        # portable identity, which is reconstructed from original input data.
        return self._digest([] if forcing is None else [
            [(spline.x.tolist(),spline.c.tolist()) for _,_,spline in channel['distribution']._segments]
            for channel in forcing.channels
            if channel['group']=='targets' and channel['index'] in {row.quantity for row in self.rows}])

    def _check_context(self, forcing):
        if self._signature(forcing) != self.signature or self._compiled(forcing) != self._compiled_signature:
            raise AnalysisError('Position-history definition changed: reset history and complete a compatible physical state; old BDF samples cannot be reinterpreted against replacement forcing.')

    def sample(self, time, forcing, side='right', *, physical=True):
        self._check_context(forcing)
        jet = None if forcing is None else forcing.local_jet(time, side)
        targets = [{} for _ in range(3)] if jet is None else [jet.targets(time, derivative=k) for k in range(3)]
        data = [np.zeros(3) for _ in range(3)]
        for row in self.rows:
            axis = 'xyz'.index(row.quantity[-1])
            for order in range(3):
                data[order][axis] = targets[order].get(row.quantity, row.target if order == 0 else 0.)
        if physical and forcing is not None:
            actual = forcing.targets(time, side)
            for row in self.rows:
                axis = 'xyz'.index(row.quantity[-1])
                expected = actual.get(row.quantity, row.target)
                if abs(data[0][axis]-expected) > 32*np.finfo(float).eps*max(1., abs(expected)):
                    raise AnalysisError('Position-history jet and physical target select different endpoint branches; complete explicit value/slope compatibility before changing sides.')
        return PositionSample(float(time), side, self.signature,
            *(tuple(float(value) for value in array) for array in data),
            'constant target' if jet is None else jet.branch,
            () if jet is None else tuple((c.index,c.interval) for c in jet.channels
                if c.group=='targets' and c.index in {row.quantity for row in self.rows}))

    def validate_sample(self, state, forcing, *, tolerance=None):
        """Check retained data against its original branch without replacing it.

        Sample roundoff permits portable spline reconstruction. Physical hidden
        constraints use fixed L/V scales, never absolute time or position.
        This checks accepted data, not compatibility with a future right branch.
        """
        self._check_context(forcing)
        saved=state.position_history
        if not isinstance(saved,PositionSample) or saved.signature!=self.signature or saved.time!=state.time:
            raise AnalysisError('Position-history continuation requires the original accepted time/side target samples; missing or mismatched history must not be regenerated from the current table.')
        # Accepted right states at cutoff own the explicit physical right limit.
        # Ordinary TimeForcing exact-end lookup keeps its legacy interior value.
        from .forcing import RightLimitForcing
        accepted_forcing=RightLimitForcing(forcing,saved.time) if forcing is not None and saved.side=='right' else forcing
        expected=self.sample(saved.time,accepted_forcing,saved.side)
        if saved.branch!=expected.branch or saved.intervals!=expected.intervals:
            raise AnalysisError('Checkpoint position-history branch or interval disagrees with the original table.')
        scales=(self.length_scale,self.velocity_scale,self.velocity_scale**2/self.length_scale)
        for name,scale in zip(('value','rate','acceleration'),scales):
            value=np.asarray(getattr(saved,name),dtype=float)
            reference=np.asarray(getattr(expected,name),dtype=float)
            if value.shape!=(3,) or not np.all(np.isfinite(value)) or np.any(abs(value-reference)>64*np.finfo(float).eps*np.maximum(scale,abs(reference))):
                raise AnalysisError('Checkpoint position-history '+name+' disagrees with the original table branch.')
        self._compatible(state,saved,tolerance=tolerance)
        return saved

    def bind_initial(self, state, forcing, tolerance):
        self.tolerance = tolerance
        state.position_history = self.sample(state.time, forcing, 'right')
        self._compatible(state, state.position_history)

    def _compatible(self, state, sample, *, tolerance=None):
        value = (state.position-np.asarray(sample.value))/self.length_scale
        rate = (state.orientation@state.U-np.asarray(sample.rate))/self.velocity_scale
        if max(np.max(abs(value[self.mask]), initial=0.),
               np.max(abs(rate[self.mask]), initial=0.)) > (self.tolerance if tolerance is None else tolerance):
            raise AnalysisError('Position-history branch is incompatible with the retained physical origin position or Earth velocity; an impulse or silent state projection is not supported.')

    def history(self, state, forcing):
        saved = self.validate_sample(state,forcing)
        if forcing is not None and state.time in forcing.breaks:
            # Preserve the accepted left sample. A next right-side branch must
            # be compatible with retained physical P and R U before it is used.
            self._compatible(state, self.sample(state.time, forcing, 'right', physical=False))
        return saved

    @staticmethod
    def coordinates(state, sample):
        return state.position-np.asarray(sample.value), state.orientation@state.U-np.asarray(sample.rate)

    def residuals(self, state, previous, older, coefficients, motion, acceleration_reference, forcing, side):
        current = self.sample(state.time, forcing, side)
        before = self.history(previous, forcing)
        past = None if older is None else self.history(older, forcing)
        E, W = self.coordinates(state, current)
        E0, W0 = self.coordinates(previous, before)
        DE = coefficients[0]*(E-E0)
        DW = coefficients[0]*(W-W0)
        if older is not None:
            E2, W2 = self.coordinates(older, past)
            DE += coefficients[2]*(E2-E0)
            DW += coefficients[2]*(W2-W0)
        # Motion.acceleration is at r_a. Convert to origin exactly once; the
        # Earth row contains no extra Omega cross U transport term. The original
        # Motion and r_a still enter all physical network/inertial load rows.
        origin_acceleration = motion.at(np.zeros(3), acceleration_reference)
        velocity_residual = DW-state.orientation@origin_acceleration+np.asarray(current.acceleration)
        position_residual = DE-W
        state.position_history = current
        return velocity_residual, position_residual


def position_history_lift(constraints, forcing, *, length_scale, velocity_scale):
    lift = PositionHistoryLift(constraints, forcing, length_scale=length_scale, velocity_scale=velocity_scale)
    return lift if np.any(lift.mask) else None
