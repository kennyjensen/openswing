"""A retry can complete a failed execution, never select a better comparison."""
from copy import deepcopy
import unittest

from scripts.retry_isae_ae2_original import replacement
from scripts.recover_isae_ae2_saved import CHECK_NAMES
from scripts.reconcile_isae_ae2_retry_results import strict_for_view
from scripts.isae_acceptance import apply_reference_acceptance, reference_acceptance_policy


class OriginalRetryAcceptance(unittest.TestCase):
    def packet(self):
        policy = dict(relative_tolerance=.05, tiny_reference=1e-8)
        original = dict(id='AE-2-b01-ias004-m80', case_id='AE-2', execution_route='worker',
            condition=dict(beta=1, speed=4), panels=80, source='literal input',
            result=dict(status='timeout', process_exit_code=-9, process_reaped=True,
                        execution_completed=True, reference_acceptance_policy=policy))
        retry = deepcopy(original)
        checks = [dict(name=name, passed=True) for name in CHECK_NAMES]
        retry['result'] = dict(status='computed', process_exit_code=0, process_reaped=True,
            execution_completed=True, execution_kind='staged_subprocess', numerical_pass=True,
            reference_acceptance_policy=deepcopy(policy), reference_match=False,
            physical_checks=deepcopy(checks), worker_report=dict(checks=checks,
                operations=dict(cold_solves=1, fresh_residuals=1), fresh_residual=1e-13))
        return original, retry

    def test_reference_mismatch_is_kept_and_inputs_are_not_mutated(self):
        old, new = self.packet(); before = deepcopy((old, new))
        result = replacement(old, new, set())
        self.assertFalse(result['reference_match'])
        self.assertEqual(result, new['result'])
        result['reference_match'] = True
        self.assertEqual((old, new), before)

    def test_failed_retry_remains_an_execution_gap(self):
        old, new = self.packet()
        new['result'] = dict(status='timeout', process_exit_code=-9, process_reaped=True,
            execution_completed=True, execution_kind='staged_subprocess',
            reference_acceptance_policy=deepcopy(old['result']['reference_acceptance_policy']))
        self.assertEqual(replacement(old, new, set())['status'], 'timeout')

    def test_previously_accepted_state_cannot_be_replaced(self):
        old, new = self.packet()
        with self.assertRaises(AssertionError):
            replacement(old, new, {old['id']})

    def test_changed_or_incomplete_evidence_is_rejected(self):
        mutations = [
            ('computed original', lambda a,b:a['result'].update(status='computed', process_exit_code=0)),
            ('unreaped original', lambda a,b:a['result'].update(process_reaped=False)),
            ('unfinished original', lambda a,b:a['result'].update(execution_completed=False)),
            ('different incidence', lambda a,b:b['condition'].update(beta=5)),
            ('different mesh', lambda a,b:b.update(panels=160)),
            ('different source', lambda a,b:b.update(source='modified input')),
            ('warm initial guess', lambda a,b:b.update(initial_state='other branch')),
            ('weaker policy', lambda a,b:b['result']['reference_acceptance_policy'].update(relative_tolerance=.2)),
            ('unreaped retry', lambda a,b:b['result'].update(process_reaped=False)),
            ('unfinished retry', lambda a,b:b['result'].update(execution_completed=False)),
            ('failed computed process', lambda a,b:b['result'].update(process_exit_code=1)),
            ('numerical failure', lambda a,b:b['result'].update(numerical_pass=False)),
            ('missing physical check', lambda a,b:b['result']['worker_report']['checks'].pop()),
            ('failed physical check', lambda a,b:b['result']['worker_report']['checks'][0].update(passed=False)),
            ('incorrect solve count', lambda a,b:b['result']['worker_report']['operations'].update(cold_solves=2)),
            ('no fresh restore', lambda a,b:b['result']['worker_report']['operations'].update(fresh_residuals=0)),
            ('large residual', lambda a,b:b['result']['worker_report'].update(fresh_residual=1e-6)),
            ('nonfinite residual', lambda a,b:b['result']['worker_report'].update(fresh_residual=float('nan'))),
            ('boolean residual', lambda a,b:b['result']['worker_report'].update(fresh_residual=False)),
            ('success mislabeled failed', lambda a,b:b['result'].update(status='timeout')),
        ]
        for name, mutate in mutations:
            with self.subTest(name=name):
                old, new = self.packet(); mutate(old, new)
                with self.assertRaises(AssertionError):
                    replacement(old, new, set())


class StrictRetryReport(unittest.TestCase):
    def packet(self):
        raw = dict(status='computed', numerical_pass=True, reference_match=False,
            reference_checks=[dict(name='RY_m', predicted=.101, expected=.1,
                                   tolerance=1e-7, passed=False)],
            output_accounting=dict(required=1, reported=1, finite=1,
                                   numerically_valid=1, passed=0, missing=0))
        policy = reference_acceptance_policy(relative_tolerance=.05)
        return raw, apply_reference_acceptance(raw, relative_tolerance=.05), policy

    def test_original_strict_result_and_policy_view_stay_distinct(self):
        raw, view, policy = self.packet()
        self.assertFalse(strict_for_view(raw, view, policy)['reference_match'])
        self.assertTrue(view['reference_match'])
        with self.assertRaises(AssertionError):
            strict_for_view(view, view, policy)

    def test_different_raw_value_or_policy_is_rejected(self):
        raw, view, policy = self.packet()
        raw['reference_checks'][0]['predicted'] = .102
        with self.assertRaises(AssertionError):
            strict_for_view(raw, view, policy)
        raw, view, policy = self.packet()
        policy['relative_tolerance'] = .001
        with self.assertRaises(AssertionError):
            strict_for_view(raw, view, policy)


if __name__ == '__main__':
    unittest.main()
