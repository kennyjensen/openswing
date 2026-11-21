"""Indirect steady operating constraints for the common aeroelastic system.

Each constraint replaces one prescribed operating variable with an unknown and
one target equation. Force/moment targets include gravity and inertial reaction;
zero targets on all six components implement the free-flight load constraints.
"""
from dataclasses import dataclass, replace
import numpy as np
from .inertia import Motion
from .reference_flow import QUANTITIES as REFERENCE_QUANTITIES, validate_reference_target
from .time_history import TARGETS as HISTORY_TARGETS, validate_history_target, validate_history_actual, history_error, PeriodicStencilContext


@dataclass
class OperatingConstraint:
    variable: str
    quantity: str
    target: float = 0.
    weight: float = 1.
    preferred: float = 0.
    expression: str | None = None
    residual_scale: float | None = None
    unit: str | None = None


class TimeHistoryConstraint(OperatingConstraint):
    """Internal time-row marker; serialized fields remain the existing schema.

    time_operating_constraints reconstructs this marker from canonical records.
    Ordinary steady OperatingConstraint objects retain their original meaning.
    """


def free_flight_constraints():
    return [OperatingConstraint(f"acceleration.{axis}", f"force.{axis}") for axis in "xyz"] + [
        OperatingConstraint(f"angular_acceleration.{axis}", f"moment.{axis}") for axis in "xyz"]


def time_load_constraints(frame, load_targets=None):
    """Select frame accelerations determined by net-load equations in time.

    Unselected components retain prescribed acceleration. Net loads include
    inertial reaction, and moments use the ASW moment reference point.
    """
    pairs={f'{group}.{a}':f'{variable}.{a}' for group,variable in
           [('force','acceleration'),('moment','angular_acceleration')] for a in 'xyz'}
    targets={} if load_targets is None else load_targets
    if not isinstance(targets,dict) or set(targets)-set(pairs):
        raise ValueError('Time load targets must map force.x/y/z or moment.x/y/z to finite values.')
    if any(isinstance(v,(bool,np.bool_)) or not isinstance(v,(int,float,np.integer,np.floating)) or not np.isfinite(v) for v in targets.values()):
        raise ValueError('Time load targets must contain finite numeric values.')
    if frame=='prescribed':
        if targets:raise ValueError('Prescribed motion has no load targets; select mixed or free motion.')
    elif frame=='free':targets={**dict.fromkeys(pairs,0.),**targets}
    elif frame=='mixed':
        if not targets:raise ValueError('Mixed motion requires at least one force or moment target.')
    else:raise ValueError('Time frame must be prescribed, free or mixed.')
    return [OperatingConstraint(variable,quantity,float(targets[quantity]))
            for quantity,variable in pairs.items() if quantity in targets]


def time_operating_constraints(frame, load_targets=None, actuator_constraints=None):
    """Combine frame equations with implicit flap/engine target equations.

    The unsteady kinematic equations still determine velocity and pose. These
    additional algebraic equations determine actuators from loads or frame
    accelerations, using the same instantaneous residual as the time solver.
    Angular rate/acceleration targets use radians/input T or T²; angle targets
    remain degree-valued. Kinematic rows retain the trajectory equations and
    require consistent hidden-constraint initialization; saved launches support
    a guarded subset of these histories.
    """
    constraints = time_load_constraints(frame, load_targets)
    if actuator_constraints is None:
        return constraints
    if not isinstance(actuator_constraints, (list, tuple)):
        raise ValueError('Time actuator constraints must be a list of variable, quantity and target records.')
    allowed = {f'{kind}.{a}' for kind in ('force', 'moment', 'acceleration', 'angular_acceleration') for a in 'xyz'}
    allowed.update(('lift', 'radial_acceleration'))
    allowed.update(HISTORY_TARGETS)
    variables = {c.variable for c in constraints}
    quantities = {c.quantity for c in constraints}
    for row in actuator_constraints:
        if isinstance(row, dict):
            if set(row) - {'variable', 'quantity', 'target'} or not {'variable', 'quantity'} <= set(row):
                raise ValueError('Time actuator constraints accept only variable, quantity and target.')
            row = OperatingConstraint(**row)
        if not isinstance(row, OperatingConstraint):
            raise ValueError('Time actuator constraints require variable, quantity and target.')
        if not isinstance(row.variable, str) or not row.variable.startswith(('control.', 'power.')):
            raise ValueError('A time actuator constraint must solve a declared flap control.# or engine power.#.')
        if not isinstance(row.quantity, str) or row.quantity not in allowed:
            raise ValueError('Time actuator targets require a supported canonical quantity; velocity and pose use explicit inverse-history quantities and retain their time equations.')
        if (row.weight != 1 or row.preferred != 0 or any(getattr(row, name) is not None for name in ('expression', 'residual_scale', 'unit'))):
            raise ValueError('Time actuator constraints do not support allocation or custom-equation fields.')
        if isinstance(row.target, (bool, np.bool_)) or not isinstance(row.target, (int, float, np.integer, np.floating)) or not np.isfinite(row.target):
            raise ValueError('Time actuator target must be a finite number.')
        if row.quantity in HISTORY_TARGETS:
            validate_history_target(row.quantity, row.target)
        if row.variable in variables or row.quantity in quantities:
            raise ValueError('Duplicate time actuator or target; each variable and quantity may be selected only once.')
        if row.quantity.startswith(('acceleration.', 'angular_acceleration.')) and row.quantity not in variables:
            raise ValueError('An inverse acceleration target requires its frame component to be solved from a net load, not prescribed.')
        variables.add(row.variable)
        quantities.add(row.quantity)
        kind = TimeHistoryConstraint if row.quantity in HISTORY_TARGETS else OperatingConstraint
        constraints.append(kind(row.variable, row.quantity, float(row.target)))
    return constraints


def time_constraint_data(constraints):
    """Separate frame targets from actuator equations for portable time setup."""
    return dict(load_targets={c.quantity:c.target for c in constraints if c.variable.startswith(('acceleration.', 'angular_acceleration.'))},
                actuator_constraints=[dict(variable=c.variable, quantity=c.quantity, target=c.target)
                    for c in constraints if c.variable.startswith(('control.', 'power.'))])


def steady_turn_constraints(heading_rate=0., flight_path=0., *, trim_controls=None, engine_control=None):
    """Constant body velocity and attitude bank/elevation; uniform Earth turn.

    heading_rate uses radians/input T; flight_path uses degrees. With three
    distinct flap IDs (roll, pitch, yaw) and an engine ID, additionally solve
    alpha, bank and these four controls for zero net force and moment. Speed
    and sideslip remain prescribed (beta=0 gives coordinated-flight trim).
    """
    if not np.isfinite(heading_rate) or not np.isfinite(flight_path) or abs(flight_path) >= 90:
        raise ValueError("Steady-turn heading rate must be finite and flight path strictly between -90 and 90 degrees.")
    out = [OperatingConstraint(f"rates.{axis}", f"rates_earth.{axis}", -heading_rate if axis == "z" else 0.) for axis in "xyz"]
    out += [OperatingConstraint(f"acceleration.{axis}", f"velocity_derivative_body.{axis}") for axis in "xyz"]
    out += [OperatingConstraint(f"angular_acceleration.{axis}", f"angular_acceleration.{axis}") for axis in "xyz"]
    out.append(OperatingConstraint("attitude.elevation", "flight_path", flight_path))
    if trim_controls is not None or engine_control is not None:
        if (trim_controls is None or len(trim_controls) != 3 or len(set(trim_controls)) != 3
                or any(not isinstance(k, int) or isinstance(k, bool) or k <= 0 for k in trim_controls)
                or not isinstance(engine_control, int) or isinstance(engine_control, bool) or engine_control <= 0):
            raise ValueError("Flight trim needs three distinct positive flap IDs (roll, pitch, yaw) and an engine ID.")
        out += [OperatingConstraint("alpha", "force.z"), OperatingConstraint("attitude.bank", "force.y"),
                OperatingConstraint(f"power.{engine_control}", "force.x")]
        out += [OperatingConstraint(f"control.{k}", f"moment.{axis}") for k, axis in zip(trim_controls, "xyz")]
    return out


class OperatingSystem:
    def __init__(self, model, condition, motion, constraints, length, force, *, additional_variables=None):
        self.condition, self.motion = condition, motion
        self.base, self.scale = {}, {}
        self.force, self.length = force, length
        self.additional_variables = additional_variables or {}
        self.constraints = [OperatingConstraint(**c) if isinstance(c, dict) else c for c in constraints]
        speed = 1. if condition is None else condition.speed
        for name, factor in [("rates", speed/length), ("acceleration", model.constants[0]),
                             ("angular_acceleration", model.constants[0]/length)]:
            for axis, value in zip("xyz", getattr(motion, name)):
                self.base[f"{name}.{axis}"] = float(value)
                self.scale[f"{name}.{axis}"] = factor
        if condition is not None:
            for name in ("speed", "alpha", "beta"):
                self.base[name] = float(getattr(condition, name))
                self.scale[name] = speed if name == "speed" else 10.
            for group,axes,factor in [('position_earth','xyz',length),('attitude',('bank','elevation','heading'),10.)]:
                for axis,value in zip(axes,getattr(condition,group)):
                    self.base[f'{group}.{axis}']=float(value)
                    self.scale[f'{group}.{axis}']=factor
            for control in model.controls:
                self.base[f"control.{control}"] = float(condition.controls.get(control, 0.))
                self.scale[f"control.{control}"] = 1.
            for control in model.engine_controls:
                self.base[f"power.{control}"] = float(condition.powers.get(control, 0.))
                rows = [r for r in model.records["engine"] if int(r[0]) == control]
                gains = [abs(r[10])+abs(r[11])/length for r in rows if int(r[1]) == 0]
                self.scale[f"power.{control}"] = max(1., abs(self.base[f"power.{control}"]),
                                                       force/max(sum(gains), 1e-30) if len(gains) == len(rows) and sum(gains) else force*speed)
        for name, (value, scale) in self.additional_variables.items():
            if name in self.base or not name.startswith('command.') or not np.isfinite(value) or not np.isfinite(scale) or scale <= 0:
                raise ValueError('Additional operating variables must be finite controller commands with positive scales.')
            self.base[name], self.scale[name] = float(value), float(scale)
        quantities = {f"{name}.{axis}" for name in ("force", "moment") for axis in "xyz"}
        quantities.update(self.base)
        quantities.add('minimum_control')
        if condition is not None:
            quantities.update(["lift", "equivalent_airspeed", "dynamic_pressure", "CL", "CY", "CD", "Cl", "Cm", "Cn"])
            quantities.update('reference.'+name for name in REFERENCE_QUANTITIES)
            quantities.update(f'{group}.{axis}' for group in ('velocity_earth','rates_earth','acceleration_earth','angular_acceleration_earth') for axis in 'xyz')
            quantities.add('flight_path')
            quantities.update(f'velocity_derivative_body.{axis}' for axis in 'xyz')
            quantities.update(['radial_acceleration', 'speed_rate'])
        variables, selected_quantities = set(), set()
        self.custom = {}
        for constraint in self.constraints:
            if not isinstance(constraint, OperatingConstraint):
                raise ValueError("Operating constraints must specify variable, quantity and target.")
            if constraint.variable not in self.base:
                raise ValueError(f"Unsupported operating variable {constraint.variable!r} for this model.")
            if constraint.variable in variables:
                raise ValueError(f"Operating variable {constraint.variable!r} is selected more than once.")
            variables.add(constraint.variable)
            if not isinstance(constraint.quantity,str):
                raise ValueError('Operating quantity must be a string.')
            if constraint.quantity.startswith('user.'):
                from .custom_constraints import CustomEquation
                self.custom[constraint.quantity]=CustomEquation(constraint,model,self.base,condition)
                quantities.add(constraint.quantity)
            elif any(getattr(constraint,k) is not None for k in ('expression','residual_scale','unit')):
                raise ValueError('Expression, residual_scale and unit apply only to user.<name> constraints.')
            for name in ('weight', 'preferred'):
                value = getattr(constraint, name)
                if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.integer, np.floating)) or not np.isfinite(value):
                    raise ValueError('Control-allocation weights and preferred settings must be finite numbers.')
            if constraint.weight <= 0:
                raise ValueError('Control-allocation weights must be positive.')
            if (constraint.weight != 1 or constraint.preferred != 0) and not constraint.variable.startswith(('control.', 'power.')):
                raise ValueError('Only solved flap and engine variables accept allocation weights and preferred settings.')
            if constraint.quantity == 'minimum_control' and not constraint.variable.startswith(('control.', 'power.')):
                raise ValueError('Minimum-control slots require a flap or engine variable.')
            if constraint.quantity == 'minimum_control' and constraint.target != 0:
                raise ValueError('Minimum-control slots use preferred settings, not a physical target value.')
            if constraint.quantity.startswith('reference.'):
                validate_reference_target(constraint.quantity, constraint.target)
            if isinstance(constraint, TimeHistoryConstraint):
                validate_history_target(constraint.quantity, constraint.target)
            if constraint.quantity not in quantities or not np.isfinite(constraint.target):
                raise ValueError("Operating constraint needs a supported quantity and finite target.")
            if constraint.quantity in selected_quantities and constraint.quantity != 'minimum_control':
                raise ValueError("Duplicate operating targets are dependent; select each quantity at most once.")
            selected_quantities.add(constraint.quantity)
            if constraint.quantity in ("equivalent_airspeed", "dynamic_pressure") and constraint.target <= 0:
                raise ValueError("Equivalent-airspeed and dynamic-pressure targets must be positive.")
        self.count = len(self.constraints)
        self.minimum_indices = [i for i, c in enumerate(self.constraints) if c.quantity == 'minimum_control']
        if not self.minimum_indices and any(c.weight != 1 or c.preferred != 0 for c in self.constraints):
            raise ValueError('Control-allocation weights and preferred settings require a minimum-control slot.')
        self.initial_values = None

    def apply(self, unknowns, *, condition_override=None, motion_override=None):
        values = self.base.copy()
        prescribed = self.condition if condition_override is None else condition_override
        prescribed_motion = motion_override
        if prescribed_motion is None and condition_override is not None:
            prescribed_motion = condition_override.motion()
        if prescribed_motion is not None:
            for group in ('rates','acceleration','angular_acceleration'):
                values.update({f'{group}.{axis}':float(value) for axis,value in zip('xyz',getattr(prescribed_motion,group))})
        if condition_override is not None:
            values.update({name:float(getattr(prescribed,name)) for name in ('speed','alpha','beta')})
            for group,axes in [('position_earth','xyz'),('attitude',('bank','elevation','heading'))]:
                values.update({f'{group}.{axis}':float(value) for axis,value in zip(axes,getattr(prescribed,group))})
            for prefix,settings in [('control',prescribed.controls),('power',prescribed.powers)]:
                for name in values:
                    if name.startswith(prefix+'.'):
                        values[name]=float(settings.get(int(name.split('.')[1]),0.))
        for constraint, value in zip(self.constraints, unknowns):
            name = constraint.variable
            if name == "speed":
                values[name] = self.base[name]*float(np.exp(value))
            else:
                values[name] = self.base[name]+self.scale[name]*float(value)
        motion = Motion(*[[values[f"{name}.{a}"] for a in "xyz"] for name in ("rates", "acceleration", "angular_acceleration")])
        condition = None
        if prescribed is not None:
            controls = dict(prescribed.controls)
            controls.update({int(k.split(".")[1]): v for k, v in values.items() if k.startswith("control.")})
            powers = dict(prescribed.powers)
            powers.update({int(k.split(".")[1]): v for k, v in values.items() if k.startswith("power.")})
            condition = replace(prescribed, speed=values["speed"], alpha=values["alpha"], beta=values["beta"],
                                rates=motion.rates.tolist(), acceleration=motion.acceleration.tolist(),
                                angular_acceleration=motion.angular_acceleration.tolist(), controls=controls, powers=powers)
            condition=replace(condition,position_earth=[values[f'position_earth.{a}'] for a in 'xyz'],
                              attitude=[values[f'attitude.{a}'] for a in ('bank','elevation','heading')])
        return condition, motion, values

    def evaluate(self, force, moment, aero, condition, factor=1., motion=None, values=None, targets=None, custom_values=None, history_context=None):
        targets={} if targets is None else targets
        if history_context is not None:
            if not isinstance(history_context, PeriodicStencilContext) or factor != 1.:
                raise ValueError('Periodic stencil context requires full physical inverse rows, not a continuation homotopy.')
            history_context.validate_rows([c for c in self.constraints if isinstance(c, TimeHistoryConstraint)])
        if isinstance(targets,dict) and 'minimum_control' in targets:
            raise ValueError('Minimum-control slots have no physical target override.')
        if not isinstance(targets,dict) or set(targets)-{c.quantity for c in self.constraints} or any(isinstance(v,(bool,np.bool_)) or not isinstance(v,(int,float,np.integer,np.floating)) or not np.isfinite(v) for v in targets.values()):
            raise ValueError('Operating target overrides require finite values for active constraints.')
        residual, report = [], []
        starting_values = []
        for i, c in enumerate(self.constraints):
            if c.quantity == 'minimum_control':
                # This slot adds an actuator unknown, not a soft physical target.
                # The constrained allocation solver removes this zero row and
                # minimizes weighted control effort subject to all other rows.
                actual = (self.base if values is None else values)[c.variable]
                residual.append(0.)
                starting_values.append(float(actual))
                report.append(dict(variable=c.variable, quantity=c.quantity, target=float(c.preferred),
                    specified_target=float(c.preferred), actual=float(actual), normalized_residual=0.,
                    kind='minimum_control', weight=float(c.weight), preferred=float(c.preferred)))
                continue
            specified_target=targets.get(c.quantity,c.target)
            time_history = isinstance(c, TimeHistoryConstraint)
            local_periodic = time_history and history_context is not None and HISTORY_TARGETS[c.quantity].periodic
            if time_history and not local_periodic:
                validate_history_target(c.quantity, specified_target)
            target = specified_target*(condition.load_factor if c.quantity == "lift" else 1.)
            if c.quantity in self.custom:
                actual,scale=custom_values[c.quantity],c.residual_scale
            elif c.quantity.startswith('reference.'):
                if not local_periodic:
                    validate_reference_target(c.quantity, target)
                key = c.quantity.removeprefix('reference.')
                actual = aero['reference_flow'][key]
                if actual is None:
                    raise ValueError(f'{c.quantity} is undefined at the current reference airflow; select a nonsingular air-data state.')
                scale = 10. if key in ('alpha', 'beta') else self.force/self.length**2 if key == 'dynamic_pressure' else self.condition.speed
            elif c.quantity.startswith("force."):
                actual, scale = force["xyz".index(c.quantity[-1])], self.force
            elif c.quantity.startswith("moment."):
                actual, scale = moment["xyz".index(c.quantity[-1])], self.force*self.length
            elif c.quantity == "lift":
                # The specified-lift constraint (eq. 185) uses circulation and
                # profile loads. Instantaneous apparent mass is a separate term.
                actual = (np.asarray(aero["surface_force"])-aero["surface_apparent_force"])@condition.vectors()[2]
                scale = self.force
            elif c.quantity == 'flight_path':
                actual,scale=aero['earth_state']['flight_path'],10.
            elif c.quantity in ('radial_acceleration', 'speed_rate'):
                actual, scale = aero['earth_state'][c.quantity], self.scale['acceleration.x']
            elif c.quantity.startswith('velocity_derivative_body.'):
                actual = aero['earth_state']['velocity_derivative_body']['xyz'.index(c.quantity[-1])]
                scale = self.scale['acceleration.x']
            elif c.quantity in self.additional_variables:
                actual, scale = (self.base if values is None else values)[c.quantity], self.scale[c.quantity]
            elif c.quantity in self.base:
                group, _, axis = c.quantity.partition('.')
                if group in ('rates', 'acceleration', 'angular_acceleration'):
                    actual = getattr(motion if motion is not None else self.motion, group)['xyz'.index(axis)]
                elif group in ('control', 'power'):
                    actual = getattr(condition, 'controls' if group == 'control' else 'powers').get(int(axis), 0.)
                elif group in ('position_earth', 'attitude'):
                    actual = getattr(condition, group)[('xyz' if group == 'position_earth' else ('bank','elevation','heading')).index(axis)]
                else:
                    actual = getattr(condition, group)
                scale = self.scale[c.quantity]
            elif c.quantity in ('equivalent_airspeed', 'dynamic_pressure'):
                actual = aero['atmosphere'][c.quantity]
                scale = self.condition.speed if c.quantity == 'equivalent_airspeed' else self.force/self.length**2
            elif '_earth.' in c.quantity:
                name,axis=c.quantity.split('.')
                actual=aero['earth_state'][name]['xyz'.index(axis)]
                scale={'velocity_earth':condition.speed,'rates_earth':condition.speed/self.length,
                       'acceleration_earth':self.scale['acceleration.x'],
                       'angular_acceleration_earth':self.scale['angular_acceleration.x']}[name]
            else:
                actual, scale = aero[c.quantity], 1.
            if time_history:
                validate_history_actual(c.quantity, actual, condition, aero)
            starting_values.append(float(actual))
            initial = float(actual) if self.initial_values is None else self.initial_values[i]
            periodic = c.quantity == 'reference.alpha' or (time_history and HISTORY_TARGETS[c.quantity].periodic)
            if time_history and factor == 1.:
                # A time trajectory may have moved far from its original
                # continuation origin; only the current physical error matters.
                path_target = target
            else:
                change = target-initial
                if periodic:
                    change = history_error(c.quantity, target, initial) if time_history else (change+180.) % 360.-180.
                path_target = initial+change*factor
            difference = actual-path_target
            if local_periodic:
                difference = history_context.error(c.variable, c.quantity, actual, path_target)
            elif periodic:
                difference = history_error(c.quantity, actual, path_target) if time_history else (difference+180.) % 360.-180.
            error = float(difference/scale)
            residual.append(error)
            report.append(dict(variable=c.variable, quantity=c.quantity, target=float(target), specified_target=float(specified_target),
                               actual=float(actual), normalized_residual=error))
            if c.quantity in self.custom:
                report[-1].update(expression=c.expression,residual_scale=float(c.residual_scale),unit=c.unit,
                    references=self.custom[c.quantity].references)
        if self.initial_values is None:
            self.initial_values = starting_values
        return residual, report
