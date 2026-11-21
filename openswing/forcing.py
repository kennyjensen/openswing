"""Documented ASWING open-loop time tables, with explicit supported channels.

The public user guide's “Open-Loop forcing during time march” specifies cubic
interpolation, doubled-time breaks, column scaling and +initial-value offsets.
Natural endpoint conditions are provisional, as for the .asw distributions.
"""
import re
from dataclasses import asdict, dataclass, replace
from numbers import Integral, Real
import numpy as np
from .asw import AswError, Distribution, numbers
from .aero import AnalysisError
from .inertia import Motion
from .operating import time_operating_constraints
from .time_history import TARGETS as HISTORY_TARGETS, history_channel


def _query(time, side='right', derivative=0):
    if isinstance(time, (bool, np.bool_)) or not isinstance(time, Real):
        raise AnalysisError('Forcing evaluation needs a finite real scalar time.')
    try:
        time = float(time)
    except (ValueError, OverflowError) as exc:
        raise AnalysisError('Forcing evaluation needs a finite real scalar time.') from exc
    if not np.isfinite(time):
        raise AnalysisError('Forcing evaluation needs a finite real scalar time.')
    if not isinstance(side, str) or side not in ('left', 'right'):
        raise AnalysisError('Forcing evaluation needs a left/right side.')
    if (isinstance(derivative, (bool, np.bool_))
            or not isinstance(derivative, Integral) or derivative < 0):
        raise AnalysisError('Forcing derivative order must be a nonnegative integer.')
    return time, int(derivative)


def _branch(distribution, time, side):
    """Copy derivatives of the selected single cubic, including ordinary knots."""
    segments = distribution._segments
    starts = [segment[0] for segment in segments[1:]]
    segment = np.searchsorted(starts, time, side=side)
    spline = segments[segment][2]
    interval = np.searchsorted(spline.x, time, side=side)-1
    interval = int(np.clip(interval, 0, len(spline.x)-2))
    a, b, c, d = (float(v) for v in spline.c[:, interval])
    x = time-float(spline.x[interval])
    derivatives = (((a*x+b)*x+c)*x+d, (3*a*x+2*b)*x+c, 6*a*x+2*b, 6*a)
    return derivatives, (float(spline.x[interval]), float(spline.x[interval+1]))


def _apply_values(channels, values, condition, motion):
    settings = dict(acceleration=motion.acceleration.copy(),
                    angular_acceleration=motion.angular_acceleration.copy())
    if condition is not None:
        settings.update(controls=dict(condition.controls), powers=dict(condition.powers))
    for channel in channels:
        if channel['group'] in ('commands', 'targets'):
            continue
        settings[channel['group']][channel['index']] = values[channel['name']]*channel['factor']
    motion = Motion(motion.rates, settings['acceleration'], settings['angular_acceleration'])
    if condition is not None:
        condition = replace(condition, **settings)
    return condition, motion


@dataclass(frozen=True)
class _JetChannel:
    name: str
    group: str
    index: str | int
    factor: float
    unit: str
    relative: bool
    initial: float
    derivatives: tuple
    interval: tuple | None


@dataclass(frozen=True)
class ForcingJet:
    """Frozen branch polynomial for explicit local stencil continuation.

    Queries may leave the recorded polynomial interval. They are *not* physical
    forcing queries: ordinary TimeForcing still rejects prehistory and returns
    zero after cutoff. The anchor's side is fixed; there is no query-side switch.
    An end-right jet is zero, unlike legacy exact-end TimeForcing.values.
    """
    anchor: float
    side: str
    branch: str
    source: str
    first_time: float | None
    end_time: float | None
    channels: tuple

    def values(self, time, *, derivative=0):
        """Evaluate the frozen Taylor polynomial, in table channel units."""
        time, derivative = _query(time, derivative=derivative)
        x = time-self.anchor
        result = {}
        for c in self.channels:
            if derivative > 3:
                value = 0.
            else:
                value = c.derivatives[3]
                for k in range(2, derivative-1, -1):
                    value = c.derivatives[k]+x*value/(k+1-derivative)
            result[c.name] = float(value)
        return result

    def targets(self, time, *, derivative=0):
        """Evaluate canonical target derivatives; angle quantities stay degrees."""
        values = self.values(time, derivative=derivative)
        return {c.index: values[c.name]*c.factor for c in self.channels if c.group == 'targets'}

    def apply(self, time, condition, motion):
        """Apply this local continuation deliberately; never reselect a side."""
        channels = ({'name': c.name, 'group': c.group, 'index': c.index,
                     'factor': c.factor} for c in self.channels)
        return _apply_values(channels, self.values(time), condition, motion)

    def for_stencil(self):
        """Adapt call signatures for an explicitly separate InitialSystem."""
        return StencilForcing(self)

    def report(self):
        return dict(kind='frozen branch polynomial continuation', source=self.source,
                    anchor=self.anchor, side=self.side, branch=self.branch,
                    first_time=self.first_time, end_time=self.end_time,
                    derivative_time_unit='input T',
                    physical_lookup=False,
                    channels=[dict(name=c.name, group=c.group, index=c.index,
                                   factor=c.factor, unit=c.unit, relative=c.relative,
                                   initial=c.initial, derivatives=list(c.derivatives),
                                   interval=None if c.interval is None else list(c.interval))
                              for c in self.channels])


@dataclass(frozen=True)
class StencilForcing:
    """TimeSystem.options interface for a frozen branch, never a time march.

    A query's side is validated but cannot change the captured anchor side.
    This object intentionally has no event schedule or physical-time support.
    Construct a separate initialization system; do not replace a live march's
    forcing with this local polynomial continuation.
    """
    jet: ForcingJet

    def values(self, time, side='right', *, derivative=0):
        _query(time, side, derivative)
        return self.jet.values(time, derivative=derivative)

    def targets(self, time, side='right', *, derivative=0):
        _query(time, side, derivative)
        return self.jet.targets(time, derivative=derivative)

    def apply(self, time, condition, motion, side='right'):
        _query(time, side)
        return self.jet.apply(time, condition, motion)

    def report(self):
        return {**self.jet.report(), 'adapter': 'InitialSystem stencil only; query side cannot change the frozen branch'}


class RightLimitForcing:
    """Physical right limit at one anchor, with ordinary support everywhere else.

    This is distinct from a stencil extension: queries away from the anchor
    still use the original physical table, including prehistory rejection and
    zero after cutoff. The explicit end-right value is zero; legacy ordinary
    TimeForcing exact-end lookup remains unchanged.
    """
    def __init__(self,forcing,anchor):
        self.forcing=forcing
        self.jet=forcing.local_jet(anchor,'right')

    def __getattr__(self,name):
        return getattr(self.forcing,name)

    def values(self,time,side='right',*,derivative=0):
        time,derivative=_query(time,side,derivative)
        if time==self.jet.anchor and side=='right':
            return self.jet.values(time,derivative=derivative)
        return self.forcing.values(time,side,derivative=derivative)

    def targets(self,time,side='right',*,derivative=0):
        values=self.values(time,side,derivative=derivative)
        return {c['index']:values[c['name']]*c['factor'] for c in self.channels if c['group']=='targets'}

    def apply(self,time,condition,motion,side='right'):
        return _apply_values(self.channels,self.values(time,side),condition,motion)

    def report(self):
        return {**self.forcing.report(),'explicit_right_limit_time':self.jet.anchor}


class TimeForcing:
    def __init__(self, source, model, condition, motion, duration, frame, controller=None, *, start_time=0., load_targets=None, actuator_constraints=None):
        if not isinstance(source, str):
            raise AnalysisError('Time forcing must be an ASWING text table.')
        self.source = source
        self.channels = []
        self.events = np.array([])
        self.breaks = np.array([])
        self.end_time = None
        self.first_time = None
        constraints=time_operating_constraints(frame,load_targets,actuator_constraints)
        targets={c.quantity:c.target for c in constraints}
        unknowns={c.variable for c in constraints}
        if controller is not None:
            for output in getattr(controller, 'outputs', ()):
                variable=('control.' if output['attribute']=='controls' else 'power.')+str(output['index'])
                if variable in unknowns:
                    raise AnalysisError('An actuator cannot be solved by both a time target and a controller.')
        lines = []
        for number, raw in enumerate(source.splitlines(), 1):
            text = re.split(r'[#!%]', raw, maxsplit=1)[0].strip()
            if text:
                lines.append((number, text))
        if not lines:
            return
        first, header = lines.pop(0)
        labels = header.split()
        if len(labels) < 2 or labels[0].lower() != 'time':
            raise AswError('Forcing header must start with time followed by channel names.', first)
        names = set()
        for label in labels[1:]:
            relative = label.startswith('+')
            name = label[1:] if relative else label
            indexed = re.fullmatch(r'([FE])([1-9]\d*)', name, re.I)
            acceleration = re.fullmatch(r'([AG])([xyz])', name, re.I)
            load = re.fullmatch(r'([FM])([xyz])', name, re.I)
            extra_target = {'l':('L','lift','input F'), 'ar':('Ar','radial_acceleration','input L/T^2')}.get(name.lower())
            history = history_channel(name)
            if controller is not None and (acceleration or history):
                canonical=history.label if history else acceleration[1].upper()+acceleration[2].lower()
                target=history.quantity if history else ('acceleration' if acceleration[1].upper()=='A' else 'angular_acceleration')+'.'+acceleration[2].lower()
                if canonical in controller.signals and target in targets:
                    raise AswError(f'Forcing {canonical} is both an inverse target and a controller command; choose one owner for the channel.', first)
            if controller is not None and name in controller.signals:
                from .feedback import CHANNELS, channel
                key,_=channel(name,model)
                group,index='commands',name
                initial=controller.commands.get(name,0.)
                factor,unit=1.,CHANNELS[key][2]
            elif indexed:
                kind, index = indexed[1].upper(), int(indexed[2])
                group = 'controls' if kind == 'F' else 'powers'
                available = model.controls if kind == 'F' else model.engine_controls
                if condition is None or index not in available:
                    raise AswError(f'Forcing {name} requires a declared {"flap" if kind == "F" else "engine"} and aerodynamic condition.', first)
                name = f'{kind}{index}'
                if ('control.' if kind=='F' else 'power.')+str(index) in unknowns:
                    raise AswError(f'Forcing {name} conflicts with its solved actuator constraint; force the target instead.', first)
                initial = getattr(condition, group).get(index, 0.)
                factor, unit = 1., 'flap setting' if kind == 'F' else 'engine setting'
            elif acceleration:
                kind, axis = acceleration[1].upper(), acceleration[2].lower()
                group = 'acceleration' if kind == 'A' else 'angular_acceleration'
                target=f'{group}.{axis}'
                if target in unknowns and target not in targets:
                    raise AswError(f'Forcing {name} conflicts with a free-flight acceleration equation; prescribe that component or force its active load target.', first)
                index = 'xyz'.index(axis)
                name = kind+axis
                factor = 1. if kind == 'A' else np.pi/180
                unit = 'input L/T^2' if kind == 'A' else 'deg/input T^2'
                initial = getattr(motion, group)[index]/factor
                if target in targets:
                    group,index,initial='targets',target,targets[target]/factor
            elif load:
                kind,axis=load[1].upper(),load[2].lower()
                name=kind+axis;group='targets';index=('force' if kind=='F' else 'moment')+'.'+axis
                if index not in targets:raise AswError(f'Forcing {name} requires its active frame load or actuator constraint.', first)
                initial=targets[index];factor=1.;unit='input F' if kind=='F' else 'input F L'
            elif extra_target:
                name,index,unit=extra_target
                if index not in targets:
                    raise AswError(f'Forcing {name} requires an active actuator target constraint.', first)
                group,initial,factor='targets',targets[index],1.
            elif history:
                if history.quantity not in targets:
                    raise AswError(f'Unsupported time-forcing channel {name!r} without its active inverse actuator target {history.quantity}.', first)
                name,index,unit=history.label,history.quantity,history.table_unit
                group,factor='targets',history.factor
                initial=targets[index]/factor
            else:
                raise AswError(f'Unsupported time-forcing channel {name!r}; use declared actuator, acceleration, active inverse-target or selected controller channels.', first)
            if name in names:
                raise AswError(f'Duplicate time-forcing channel {name}.', first)
            names.add(name)
            self.channels.append(dict(name=name, relative=relative, group=group, index=index,
                                      initial=float(initial), factor=factor, unit=unit))
        width = len(labels)
        multiplier, adder = np.ones(width), np.zeros(width)
        data = []
        for line, text in lines:
            if text[0] in '*+':
                values = numbers(text[1:], line)
                if len(values) > width or not values:
                    raise AswError('Forcing scale line has an invalid column count.', line)
                target = multiplier if text[0] == '*' else adder
                target[:] = 1. if text[0] == '*' else 0.
                target[:len(values)] = values
            else:
                values = numbers(text, line)
                if len(values) != width:
                    raise AswError(f'Forcing table requires exactly {width} columns.', line)
                data.append(np.asarray(values)*multiplier+adder)
        if len(data) < 2:
            raise AswError('Forcing table requires at least two time samples.', first)
        data = np.asarray(data)
        t = data[:, 0]
        if not np.all(np.isfinite(data)) or np.any(np.diff(t) < 0):
            raise AswError('Scaled forcing data must be finite with nondecreasing times.', first)
        if t[0] > start_time:
            raise AswError(f'Forcing table must start at or before {start_time:g}; behavior before the first sample is unspecified.', first)
        for i, channel in enumerate(self.channels):
            values = data[:, i+1]
            channel['distribution'] = Distribution(channel['name'], t, values, first)
        # A resumed interval's start + duration can round one ulp below its
        # intended table endpoint. Retain nearby terminal knots so the time
        # integrators' existing event snap can land on the exact table time.
        # Otherwise the next continuation attempts an almost zero-length step.
        endpoint_margin = 8*np.finfo(float).eps*max(abs(duration), abs(start_time))
        self.events = np.unique(t[(t > start_time) & (t <= duration+endpoint_margin)])
        self.end_time=float(t[-1])
        self.first_time=float(t[0])
        # The final data point is reached on the interior (left) side. Beyond
        # it, specified parameters are zero, including relative channels.
        self.breaks = np.unique(np.r_[t[:-1][np.diff(t) == 0],t[-1]])

    def values(self, time, side='right', *, derivative=0):
        """Physical table lookup or its selected polynomial derivative.

        Derivatives use scaled input time; initial offsets affect only order 0.
        Preserve exact-end compatibility: both sides use the interior table,
        for every order. Strictly after end every order is zero. Use local_jet
        for an explicit right cutoff branch or branch-local stencil extension.
        At ordinary knots, side also chooses the third-derivative branch.
        """
        time, derivative = _query(time, side, derivative)
        if self.first_time is not None and time<self.first_time:raise AnalysisError('Forcing values before the first table sample are unspecified.')
        if self.end_time is not None and time>self.end_time:return {c['name']:0. for c in self.channels}
        if derivative == 0:
            return {c['name']: float(c['distribution'].evaluate(time, side=side))+(c['initial'] if c['relative'] else 0.) for c in self.channels}
        return {c['name']: _branch(c['distribution'], time, side)[0][derivative]
                if derivative <= 3 else 0. for c in self.channels}

    def targets(self,time,side='right', *, derivative=0):
        """Canonical target derivatives: rates use radians, angles use degrees."""
        values=self.values(time,side,derivative=derivative)
        return {c['index']:values[c['name']]*c['factor'] for c in self.channels if c['group']=='targets'}

    def local_jet(self, anchor, side='right'):
        """Freeze one sided polynomial for explicit stencil continuation.

        First-left is undefined; first-right selects the first table interval.
        End-left selects the last interval; end-right selects the zero cutoff
        branch (unlike an ordinary exact-end value). No query changes physical
        support rules. Copy all coefficients and offsets now, so later command
        binding or table changes cannot alter a captured jet.
        """
        anchor, _ = _query(anchor, side)
        if self.first_time is not None and (anchor < self.first_time or
                (anchor == self.first_time and side == 'left')):
            raise AnalysisError('A forcing jet before the first sample or on its left has unspecified prehistory.')
        after = self.end_time is not None and (anchor > self.end_time or
                (anchor == self.end_time and side == 'right'))
        channels = []
        for c in self.channels:
            derivatives, interval = ((0.,)*4, None) if after else _branch(c['distribution'], anchor, side)
            if c['relative'] and not after:
                derivatives = (derivatives[0]+c['initial'], *derivatives[1:])
            channels.append(_JetChannel(c['name'], c['group'], c['index'],
                                        float(c['factor']), c['unit'], c['relative'],
                                        float(c['initial']), tuple(derivatives), interval))
        return ForcingJet(anchor, side, 'zero cutoff' if after else 'table' if channels else 'empty',
                          self.source, self.first_time, self.end_time, tuple(channels))

    def stencil_forcing(self, anchor, side='right'):
        """Explicit local adapter; never installed into physical time lookup."""
        return self.local_jet(anchor, side).for_stencil()

    def bind_commands(self, commands):
        for c in self.channels:
            if c['group']!='targets' and c['name'] in commands:c['initial']=float(commands[c['name']])

    def apply(self, time, condition, motion, side='right'):
        return _apply_values(self.channels, self.values(time, side), condition, motion)

    def report(self):
        return dict(source=self.source, interpolation='piecewise natural cubic',
                    time_unit='input T', events=self.events.tolist(), breaks=self.breaks.tolist(),
                    first_time=self.first_time,end_time=self.end_time,after_end='zero applied specified value (also for + channels); final sample uses its table value',
                    derivatives='with respect to scaled input T; +initial offset only at order zero; exact endpoints use the interior table polynomial on either side',
                    local_jet='explicit frozen branch continuation; first-left undefined; end-right is zero rather than the legacy exact-end table value',
                    channels=[{**{k: c[k] for k in ('name', 'relative', 'initial', 'unit')},
                               **({'owner': 'inverse actuator target', 'inverse_history': asdict(HISTORY_TARGETS[c['index']])}
                                  if c['group']=='targets' and c['index'] in HISTORY_TARGETS else {})}
                              for c in self.channels],
                    limitations=['ASWING spline endpoint conditions are unverified; natural cubic segments are used.',
                                 'Zero-after-end applies to complete specified values; relative-channel cutoff still needs an ASWING executable comparison.',
                                 'Inverse histories retain the trajectory equations and require consistent initialization. Cold initialization and a guarded saved Earth-velocity history launch are available; general saved transitions and compatible discontinuous events remain unfinished.',
                                 'Periodic targets use the stated local principal chart. Table samples are not automatically unwrapped; multi-turn and branch-crossing initialization require explicit validation.'])
