"""Fixed inputs and accuracy gates for repeated-cycle UA-1 stall verification."""
import numpy as np

from isae_ua_stall_production import request as cold_request
from isae_ua_periodic import fourier, phase_difference

KEYS = ('CL', 'circulation', 'circulation_rate', 'CDp_fixed')
GATES = dict(reference_fraction=1e-9, reference_settling_fraction=1e-8,
    waveform_fraction=.001, settling_fraction=.0001, refinement_ratio=.35,
    motion_fraction=.001, residual=1e-10, amplitude_fraction=.001,
    phase_degrees=.05, first_rate_fraction=.01)


def request(section, steps, cycles=4):
    if not isinstance(cycles, int) or cycles < 2:
        raise ValueError('At least two complete cycles required')
    result = cold_request(section, steps)
    table = []
    for index in range(cycles*steps+1):
        t = section.period*index/steps
        a = section.motion(t)[2]*section.heave
        table.append(f'{t:.17g} {a[0]:.17g} {a[2]:.17g}')
    result['time'].update(duration=cycles*section.period, max_steps=4*cycles*steps,
        forcing='time Ax Az\n'+'\n'.join(table)+'\n')
    return result


def arrays(rows):
    result = {key: np.asarray([r[key] for r in rows], dtype=float) for key in KEYS}
    assert all(np.isfinite(value).all() for value in result.values())
    return result


def error(actual, target, scale):
    assert scale > 0 and np.isfinite(scale)
    if actual.ndim == 2 and target.ndim == 1:
        target = target[:, None]
    return float(np.max(abs(actual-target))/scale)


def summarize(section, steps, cycles, rows, reference, reference_steps=640):
    assert reference_steps % steps == 0 and len(rows) == cycles*steps+1
    stride = reference_steps//steps
    cold_rows = reference['rows'][:cycles*reference_steps+1:stride]
    periodic_rows = reference['rows'][-reference_steps-1::stride]
    assert len(cold_rows) == len(rows) and len(periodic_rows) == steps+1
    assert max(abs(a['time']-b['time']) for a,b in zip(rows,cold_rows)) < 1e-12
    actual, cold, periodic = map(arrays, (rows,cold_rows,periodic_rows))
    initial = section.fields(reference['initial_circulation'], 0., 0., rate=0.)
    cold_scales = {key: float(np.max(abs(value-(initial[key] if key in ('CL','circulation') else 0.))))
                   for key,value in cold.items()}
    means = {key: float(np.mean(value[:-1])) for key,value in periodic.items()}
    scales = {key: float(np.max(abs(value-(means[key] if key in ('CL','circulation') else 0.))))
              for key,value in periodic.items()}
    cold_errors = {key:error(actual[key], cold[key], cold_scales[key]) for key in KEYS}
    phase = np.linspace(0.,section.period,steps+1)
    target_fourier = fourier(phase, periodic['CL'], section.period)
    history = []
    for cycle in range(1,cycles+1):
        selected = slice((cycle-1)*steps,cycle*steps+1)
        previous = slice((cycle-2)*steps,(cycle-1)*steps+1)
        measured = fourier(phase,actual['CL'][selected],section.period)
        a,b = measured['harmonics'][0], target_fourier['harmonics'][0]
        history.append(dict(cycle=cycle,
            error_fractions={key:error(actual[key][selected],periodic[key],scales[key]) for key in KEYS},
            change_fractions={key:error(actual[key][selected],actual[key][previous],scales[key]) for key in KEYS} if cycle>1 else None,
            mean_lift_error_fraction=abs(measured['mean']-target_fourier['mean'])/scales['CL'],
            amplitude_error_fraction=abs(a['amplitude']/b['amplitude']-1),
            phase_error_degrees=abs(phase_difference(a['phase_deg'],b['phase_deg'])),
            section_cl_range=[min(min(r['section_cl']) for r in rows[selected]), max(max(r['section_cl']) for r in rows[selected])]))
    return dict(samples=len(rows), cold_error_fractions=cold_errors, cycles=history,
        cold_scales=cold_scales, periodic_scales=scales,
        residual=max(r['residual'] for r in rows),
        first_rate_error_fraction=error(actual['circulation_rate'][1:2],cold['circulation_rate'][1:2],abs(cold['circulation_rate'][1])),
        velocity_fraction=max(abs(r['velocity']-t['velocity']) for r,t in zip(rows,cold_rows))/(section.speed*section.k*section.amplitude_ratio),
        position_fraction=max(abs(r['position']-t['displacement']) for r,t in zip(rows,cold_rows))/(section.amplitude_ratio*section.chord/2))


def checks(results, reference_passed, section):
    grids = sorted(int(key) for key in results)
    assert len(grids) == 2 and grids[1] == 2*grids[0]
    coarse,fine = [results[str(key)] for key in grids]
    last = fine['cycles'][-1]
    ratios = {name:{key:fine_values[key]/coarse_values[key] for key in KEYS}
        for name,fine_values,coarse_values in (
            ('cold',fine['cold_error_fractions'],coarse['cold_error_fractions']),
            ('periodic',last['error_fractions'],coarse['cycles'][-1]['error_fractions']))}
    gates = dict(reference=bool(reference_passed),
        cold_waveforms=max(fine['cold_error_fractions'].values()) < GATES['waveform_fraction'],
        periodic_waveforms=max(last['error_fractions'].values()) < GATES['waveform_fraction'],
        settling=max(last['change_fractions'].values()) < GATES['settling_fraction'],
        refinement=max(v for group in ratios.values() for v in group.values()) < GATES['refinement_ratio'],
        residual=max(r['residual'] for r in results.values()) < GATES['residual'],
        motion=max(fine['position_fraction'],fine['velocity_fraction']) < GATES['motion_fraction'],
        mean_lift=last['mean_lift_error_fraction'] < GATES['waveform_fraction'],
        lift_amplitude=last['amplitude_error_fraction'] < GATES['amplitude_fraction'],
        lift_phase=last['phase_error_degrees'] < GATES['phase_degrees'],
        first_rate=fine['first_rate_error_fraction'] < GATES['first_rate_fraction'],
        persistent_stall=last['section_cl_range'][0] < section.clmax-.1 and last['section_cl_range'][1] > section.clmax)
    return gates,ratios
