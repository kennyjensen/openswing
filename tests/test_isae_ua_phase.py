"""Production phase comparison, mean response, and targeted omission checks."""
from copy import deepcopy
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import isae_ua_phase as phase


@pytest.fixture(scope='module')
def assembled():
    return phase.production_matrix(4)


def test_pinned_phase_sources_have_distinct_frequencies_and_no_native_outputs():
    binding = phase.source_binding()['phase_average']
    assert binding['reduced_frequencies'] == [.47, .94]
    assert not binding['native_solver_outputs']
    assert binding['phase_samples'] == 100


def test_actual_production_derivatives_match_all_six_linear_source_curves(assembled):
    actual = phase.predict(assembled['matrix'])
    checks = phase.assess(actual)
    assert len(checks) == 6 and all(c['passed'] for c in checks)
    assert sum(c['points_passed'] for c in checks) == 600
    assert actual['mean_incidence_slope_per_rad'] == pytest.approx(2*np.pi, rel=1e-4)
    assert actual['static_solves'] == 1 and actual['harmonic_solves'] == 2


def test_missing_mean_incidence_response_fails_only_nonzero_labels(assembled):
    matrix = assembled['matrix'].copy()
    matrix[:, -1] = 0
    checks = phase.assess(phase.predict(matrix))
    assert [c['passed'] for c in checks] == [True, False, False, True, False, False]


def test_missing_apparent_mass_fails_phase_curves(assembled):
    matrix = assembled['matrix'].copy()
    matrix[-1, -2] = 0
    assert not any(c['passed'] for c in phase.assess(phase.predict(matrix)))


def test_wrong_phase_origin_fails_complete_waveforms(assembled):
    actual = deepcopy(phase.predict(assembled['matrix']))
    for row in actual['responses']:
        row['CL'] = (2*row['mean']-np.asarray(row['CL'])).tolist()
    assert not any(c['passed'] for c in phase.assess(actual))


def test_physical_amplitude_cannot_be_doubled_to_match_a_peak_convention(assembled):
    actual = deepcopy(phase.predict(assembled['matrix']))
    for row in actual['responses']:
        row['CL'] = (2*np.asarray(row['CL'])-row['mean']).tolist()
        row['CL_real'] *= 2
        row['CL_imag'] *= 2
    assert not any(c['passed'] for c in phase.assess(actual))
