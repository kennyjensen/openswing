"""Original independent controller-authority cases on the source equations."""
import pytest
import test_feedback_time_rank as original
from test_feedback_time_rank import (
    observed,
    test_cold_rejects_unowned_actuator,
    test_valid_cold_rejects_lost_step_authority,
    test_regular_controller_has_independent_force_and_trajectory,
    test_nonzero_custom_initial_value_and_rate_are_preserved,
    test_steady_helper_keeps_existing_neutral_state_family,
)
from openswing.source_airflow import AIRFLOW_POLICY


@pytest.fixture(autouse=True)
def source_operator(monkeypatch):
    parse = original.parse_asw
    solve = original.api.solve_time
    monkeypatch.setattr(original, 'parse_asw', lambda text:parse(
        text, beam_interpolation='drela-segspl-v1'))
    def run(*args, **kwargs):
        return solve(*args, **kwargs, structural_operator=AIRFLOW_POLICY)
    monkeypatch.setattr(original.api, 'solve_time', run)
