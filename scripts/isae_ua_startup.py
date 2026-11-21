"""Prescribed variable-step startup grid and local-rate accuracy diagnostics."""
import math


def heave_grid(period, steps, subdivisions=1, growth=1.5):
    if not math.isfinite(period) or period <= 0 or steps < 2 or subdivisions < 1:
        raise ValueError('Positive period, at least two steps and positive subdivisions required')
    if not math.isfinite(growth) or not 1 < growth <= 1.5:
        raise ValueError('Startup growth must be greater than 1 and at most 1.5')
    if subdivisions == 1:
        return [period*i/steps for i in range(steps+1)]
    phase, increment = 0., 1/(steps*subdivisions)
    times = [0.]
    while phase < 1.:
        target = min(1., phase+increment)
        used = target-phase
        times.append(period*target)
        phase = target
        increment = min(1/steps, growth*used)
    return times


def rate_metrics(samples, reference_rows):
    import numpy as np
    actual = np.asarray([s['circulation_rate'] for s in samples])
    expected = np.asarray([s['expected']['circulation_rate'] for s in reference_rows])
    assert actual.shape == expected.shape and len(actual) > 1
    peak = np.max(np.abs(expected),axis=0)
    assert np.all(peak > 0) and np.all(np.abs(expected[1]) > 1e-14)
    normalized = np.abs(actual-expected)/peak
    first_relative = np.abs(actual[1]-expected[1])/np.abs(expected[1])
    time_index,strip = np.unravel_index(np.argmax(normalized),normalized.shape)
    first_strip = int(np.argmax(first_relative))
    return dict(maximum_per_strip_rate_waveform_error_fraction=float(np.max(normalized)),
        maximum_first_step_relative_error_fraction=float(np.max(first_relative)),
        first_step_time=samples[1]['time'], first_step_strip=first_strip,
        first_step_predicted=float(actual[1,first_strip]),first_step_reference=float(expected[1,first_strip]),
        worst_waveform_rate_location=dict(snapshot=int(time_index),strip_index=int(strip),
            time=samples[time_index]['time'],predicted=float(actual[time_index,strip]),
            reference=float(expected[time_index,strip]),reference_strip_peak=float(peak[strip])))
