"""Parameterized UA-1 histories; independent equation targets and fixed gates.

Production receives prescribed acceleration and its own steady initial state.
The integrating-factor target is evaluated only on the comparison side.
"""
from dataclasses import dataclass
import math

import numpy as np

from isae_suite_unsteady import model_text
from isae_ua_incidence_periodic import GATES
from isae_ua_incidence_reference import fields, kinematics, steady_circulation, trajectory
from isae_ua_periodic import fourier, phase_difference

RESTART_SCALE_ULPS = 4


def check_restart_join(previous, current):
    """Exact state join except dimensional force/moment scale round trips.

    equilibrium_state.restore_physical_fields divides by F or F*L; capture
    reconstructs dimensional fields through network.unpack's multiplication.
    A division and up to two multiplications need not round back bit for bit.
    Only these fields allow four ULPs; positions, circulation, motion and the
    entire remaining state still require exact equality.
    """
    rounding = []
    prefixes = tuple('state/network/'+name+'/' for name in ('internal_force', 'internal_moment', 'reactions'))
    def visit(a, b, path):
        if isinstance(a, dict) and isinstance(b, dict):
            assert set(a) == set(b), path
            for key in a: visit(a[key], b[key], path+'/'+str(key))
        elif isinstance(a, list) and isinstance(b, list):
            assert len(a) == len(b), path
            for i, (x, y) in enumerate(zip(a, b)): visit(x, y, path+'/'+str(i))
        elif isinstance(a, (float, int)) and isinstance(b, (float, int)):
            assert math.isfinite(a) and math.isfinite(b), path
            if a == b:
                return
            assert path.startswith(prefixes), path
            ulps = abs(a-b)/max(math.ulp(float(a)), math.ulp(float(b)))
            assert ulps <= RESTART_SCALE_ULPS, (path, ulps)
            rounding.append(dict(path=path, before=a, after=b, difference_in_ulps=ulps))
        else:
            assert a == b, path
    visit(previous, current, 'state')
    return rounding


@dataclass(frozen=True)
class Case:
    alpha_deg: float
    k: float
    amplitude_ratio: float = .5
    speed: float = 10.
    cycles: int = 8

    def __post_init__(self):
        values = [self.alpha_deg, self.k, self.amplitude_ratio, self.speed]
        if not all(math.isfinite(x) for x in values):
            raise ValueError('Finite physical settings required')
        if not (abs(self.alpha_deg) < 80 and self.k > 0 and self.amplitude_ratio > 0
                and self.speed > 0 and self.cycles >= 2 and isinstance(self.cycles, int)):
            raise ValueError('Positive amplitude, speed, frequency and at least two cycles required')
        a = math.radians(self.alpha_deg)
        if math.cos(a) <= self.amplitude_ratio*self.k*abs(math.sin(a)):
            raise ValueError('Reference requires forward chordwise flow throughout')

    @property
    def period(self):
        return math.pi/(self.speed*self.k)

    @property
    def direction(self):
        a = math.radians(self.alpha_deg)
        return np.array([-math.sin(a), 0., math.cos(a)])

    @property
    def wind(self):
        a = math.radians(self.alpha_deg)
        return np.array([math.cos(a), 0., math.sin(a)])

    @property
    def settings(self):
        return dict(alpha_deg=self.alpha_deg, amplitude_ratio=self.amplitude_ratio,
                    k=self.k, speed=self.speed)


def request(case, steps):
    if not isinstance(steps, int) or steps < 8:
        raise ValueError('At least eight steps per cycle required')
    table = []
    for i in range(case.cycles*steps+1):
        t = case.period*i/steps
        acceleration = kinematics(t, amplitude_ratio=case.amplitude_ratio,
                                  k=case.k, speed=case.speed)[2]*case.direction
        table.append(f'{t:.17g} {acceleration[0]:.17g} {acceleration[2]:.17g}')
    return dict(action='time', mode='time', source=model_text(), panels=4,
        numerics=dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-moving-airflow-v1'),
        condition=dict(speed=case.speed, alpha=case.alpha_deg, mach=0., stall=False, aero_lag=True,
                       gravity_magnitude=0., position_earth=(case.amplitude_ratio/2*case.direction).tolist()),
        time=dict(frame='prescribed', duration=case.cycles*case.period, dt=case.period/steps,
                  order=2, tolerance=GATES['normalized_residual'], max_steps=4*case.cycles*steps,
                  forcing='time Ax Az\n'+'\n'.join(table)+'\n'))


def reference_history(case, steps):
    phase = [case.period*i/steps for i in range(steps+1)]
    periodic = trajectory(phase, **case.settings, boundary='periodic')
    initial = steady_circulation(alpha_deg=case.alpha_deg, speed=case.speed)
    transient = initial-periodic['initial_circulation']
    a = math.radians(case.alpha_deg)
    rows = []
    for i in range(case.cycles*steps+1):
        t = case.period*i/steps
        phase_index = (i-1)%steps+1 if i else 0
        z, w, acceleration = kinematics(t, amplitude_ratio=case.amplitude_ratio,
                                       k=case.k, speed=case.speed)
        primitive = (case.speed*math.cos(a)*t+math.sin(a)*(z-case.amplitude_ratio/2))/2
        gamma = periodic['rows'][phase_index]['circulation']+transient*math.exp(-primitive)
        rows.append(dict(time=t, displacement=z, velocity=w, acceleration=acceleration,
                         **fields(gamma, w, acceleration, alpha_deg=case.alpha_deg, speed=case.speed)))
    return dict(period=case.period, steps=steps, periodic=periodic, cold_rows=rows,
                steady_initial_circulation=initial)


def summarize_grid(case, steps, rows, reference, reference_steps):
    """Measure every strip against cold history and each periodic cycle."""
    assert reference_steps % steps == 0 and len(rows) == case.cycles*steps+1
    stride = reference_steps//steps
    targets = reference['cold_rows'][::stride]
    assert len(targets) == len(rows)
    assert max(abs(a['time']-b['time']) for a, b in zip(rows, targets)) < 1e-12
    keys = ('CL', 'circulation', 'circulation_rate')
    actual = {key: np.array([r[key] for r in rows]) for key in keys}
    cold = {key: np.array([r[key] for r in targets]) for key in keys}
    steady_gamma = reference['steady_initial_circulation']
    steady_cl = fields(steady_gamma, 0., 0., alpha_deg=case.alpha_deg, speed=case.speed)['CL']
    cold_scales = dict(CL=float(np.max(abs(cold['CL']-steady_cl))),
        circulation=float(np.max(abs(cold['circulation']-steady_gamma))),
        circulation_rate=float(np.max(abs(cold['circulation_rate']))))
    error = lambda measured, expected, scale, key: float(np.max(abs(measured-(expected if key == 'CL' else expected[:, None])))/scale)
    cold_errors = {key: error(actual[key], cold[key], cold_scales[key], key) for key in keys}
    phase_rows = reference['periodic']['rows'][::stride]
    times = [r['time'] for r in phase_rows]
    periodic = {key: np.array([r[key] for r in phase_rows]) for key in keys}
    means = {key: fourier(times, value, case.period)['mean'] for key, value in periodic.items()}
    scales = {key: float(np.max(abs(value-(means[key] if key != 'circulation_rate' else 0))))
              for key, value in periodic.items()}
    target_fourier = fourier(times, periodic['CL'], case.period)
    cycles = []
    for cycle in range(1, case.cycles+1):
        selected = slice((cycle-1)*steps, cycle*steps+1)
        errors = {key: error(actual[key][selected], periodic[key], scales[key], key) for key in keys}
        measured = fourier(times, actual['CL'][selected], case.period)
        harmonics = [dict(order=a['order'], amplitude_error_fraction=a['amplitude']/b['amplitude']-1,
                          phase_error_deg=phase_difference(a['phase_deg'], b['phase_deg']))
                     for a, b in zip(measured['harmonics'], target_fourier['harmonics'])]
        changes = None
        if cycle > 1:
            prior = slice((cycle-2)*steps, (cycle-1)*steps+1)
            changes = {key: float(np.max(abs(actual[key][selected]-actual[key][prior]))/scales[key]) for key in keys}
        cycles.append(dict(cycle=cycle, error_fractions=errors, measured=measured, harmonic_errors=harmonics,
            mean_CL_error_dynamic_fraction=(measured['mean']-target_fourier['mean'])/scales['CL'],
            cycle_change_fractions=changes))
    diagnostics = dict(maximum_residual=max(r['residual'] for r in rows),
        maximum_heave_velocity_error=max(abs(a['heave_velocity']-b['velocity']) for a, b in zip(rows, targets)),
        maximum_heave_position_error=max(abs(a['heave_position']-b['displacement']) for a, b in zip(rows, targets)),
        first_step_rate_relative_error=float(np.max(abs(actual['circulation_rate'][1]-cold['circulation_rate'][1]))/abs(cold['circulation_rate'][1])))
    return dict(samples=len(rows), cold_error_fractions=cold_errors, cold_scales=cold_scales,
                periodic_scales=scales, cycles=cycles, diagnostics=diagnostics)


def assess(coarse, fine):
    """The existing fourteen UA-1 accuracy/refinement gates, unchanged."""
    final = fine['cycles'][-1]
    ratios = dict(cold={key: fine['cold_error_fractions'][key]/coarse['cold_error_fractions'][key]
                       for key in fine['cold_error_fractions']},
                  periodic={key: final['error_fractions'][key]/coarse['cycles'][-1]['error_fractions'][key]
                            for key in final['error_fractions']})
    checks = {}
    for key, label in [('CL', 'CL'), ('circulation', 'circulation'), ('circulation_rate', 'rate')]:
        checks['cold_'+key] = fine['cold_error_fractions'][key] < GATES['cold_'+label+'_fraction']
        checks['periodic_'+key] = final['error_fractions'][key] < GATES['periodic_'+label+'_fraction']
        checks['last_cycle_change_'+key] = final['cycle_change_fractions'][key] < GATES['last_cycle_change_fraction']
    checks.update(refinement=all(value < GATES['fine_to_coarse_ratio'] for group in ratios.values() for value in group.values()),
        amplitude=abs(final['harmonic_errors'][0]['amplitude_error_fraction']) < GATES['amplitude_fraction'],
        phase=abs(final['harmonic_errors'][0]['phase_error_deg']) < GATES['phase_deg'],
        mean=abs(final['mean_CL_error_dynamic_fraction']) < GATES['mean_CL_dynamic_fraction'],
        residual=max(coarse['diagnostics']['maximum_residual'], fine['diagnostics']['maximum_residual']) < GATES['normalized_residual'])
    return dict(passed=all(checks.values()), checks=checks, fine_to_coarse_ratios=ratios)
