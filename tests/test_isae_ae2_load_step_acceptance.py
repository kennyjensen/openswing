"""A completed diagnostic must retain its entire original cold path."""
from copy import deepcopy
import unittest

from scripts.isae_ae2_load_step_acceptance import validate_stage
from scripts.recover_isae_ae2_saved import CHECK_NAMES


class LoadStepAcceptance(unittest.TestCase):
    def packet(self, *, final=False):
        original = dict(action='solve', condition=dict(speed=18, beta=5), source='literal model')
        checkpoint = dict(load_fraction=.25, physical_residual=1e-13,
                          coordinates=[1, 2, 3], accepted_load_steps=1,
                          context=dict(solver=dict(physical_residual_target=1e-12,
                              continuation_steps=4, reuse_matrices=True, full_structure=True)))
        previous = dict(continuation_status='pending', checkpoint=deepcopy(checkpoint))
        request = deepcopy(original)
        request['continuation'] = dict(max_load_steps=1, checkpoint=deepcopy(checkpoint))
        if final:
            saved = dict(continuation_status='complete', converged=True, residual=1e-13)
            report = dict(status='computed', fresh_residual=1e-13,
                          checks=[dict(name=name, passed=True) for name in CHECK_NAMES])
        else:
            checkpoint.update(load_fraction=.5, accepted_load_steps=2)
            saved = dict(continuation_status='pending', checkpoint=checkpoint, load_fraction=.5)
            report = dict(status='pending', accepted=False, boundary_residual=1e-13, load_fraction=.5)
        return dict(original=original, request=request, previous=previous, saved=saved,
                    report=report, terminal=dict(returncode=0, process_reaped=True, supervisor_timeout=False), final=final)

    def test_exact_chain_is_accepted_without_mutating_evidence(self):
        for final in (False, True):
            p = self.packet(final=final); before = deepcopy(p)
            validate_stage(**p)
            self.assertEqual(p, before)

    def test_restart_cannot_change_inputs_skip_steps_or_replace_coordinates(self):
        mutations = [
            lambda p:p['request']['condition'].update(speed=19),
            lambda p:p['request'].update(initial_state='alternate branch'),
            lambda p:p['request']['continuation']['checkpoint']['coordinates'].__setitem__(0, 99),
            lambda p:p['request']['continuation'].update(max_load_steps=2),
            lambda p:p.update(previous=None),
            lambda p:p['saved']['checkpoint'].update(accepted_load_steps=3),
            lambda p:p['saved']['checkpoint'].update(physical_residual=float('nan')),
            lambda p:p['saved']['checkpoint']['context']['solver'].update(physical_residual_target=1e-8),
            lambda p:p['terminal'].update(supervisor_timeout=True),
            lambda p:p['terminal'].update(returncode=-9),
            lambda p:p['terminal'].update(process_reaped=False),
        ]
        for i, mutate in enumerate(mutations):
            with self.subTest(i=i):
                p = self.packet(); mutate(p)
                with self.assertRaises(AssertionError): validate_stage(**p)

    def test_incomplete_or_unverified_final_state_is_rejected(self):
        mutations = [
            lambda p:p['saved'].update(continuation_status='pending'),
            lambda p:p['saved'].update(converged=False),
            lambda p:p['saved'].update(residual=1e-8),
            lambda p:p['report'].update(fresh_residual=float('nan')),
            lambda p:p['report'].update(fresh_residual=True),
            lambda p:p['report']['checks'].pop(),
            lambda p:p['report']['checks'][0].update(passed=False),
        ]
        for i, mutate in enumerate(mutations):
            with self.subTest(i=i):
                p = self.packet(final=True); mutate(p)
                with self.assertRaises(AssertionError): validate_stage(**p)


if __name__ == '__main__':
    unittest.main()
