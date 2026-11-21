"""Acceptance must reject partial, substituted, or numerically failed recoveries."""
from copy import deepcopy
import unittest

from scripts.isae_ae2_saved_acceptance import validate_case
from scripts.recover_isae_ae2_saved import CHECK_NAMES


class SavedStateAcceptance(unittest.TestCase):
    def packet(self):
        job = dict(id='AE-2-control', case_id='AE-2', execution_route='worker', source='literal')
        original = dict(status='timeout', process_reaped=True, execution_completed=True, process_exit_code=-15)
        case = dict(id=job['id'], job=deepcopy(job), original_failed_result=deepcopy(original))
        values = dict(RY_m=.1, Psi_deg=2., sensor_V_m_s=10., sensor_beta_deg=3.)
        checked = dict(job_id=job['id'], status='VERIFIED_ORIGINAL_SAVED_EQUILIBRIUM',
            original_process_outcome=deepcopy(original), operations=dict(new_cold_solves=0, fresh_residuals=1),
            checks=[dict(name=k, passed=True) for k in CHECK_NAMES], fresh_residual=1e-13, values=values)
        terminal = dict(job_id=job['id'], returncode=0, process_reaped=True, supervisor_timeout=False)
        sources = dict(all_pins_checked_before_and_after=True)
        saved = dict(converged=True, residual=1e-13,
            sensors=[dict(position_earth=[0,.1,0], heading=2., speed=10., beta=3.)])
        request = dict(source='literal', condition=dict(beta=1), panels=80)
        return dict(job=job, original=original, case=case, checked=checked, terminal=terminal,
                    sources=sources, saved=saved, request=request, expected=deepcopy(request))

    def test_valid_completion_preserves_original_failure(self):
        p = self.packet(); before = deepcopy(p)
        self.assertEqual(validate_case(**p), p['checked']['values'])
        self.assertEqual(p, before)

    def test_summary_contract_is_derived_metadata(self):
        p = self.packet()
        p['job']['_summary_reference_contract'] = {'independently_checked': True}
        self.assertEqual(validate_case(**p), p['checked']['values'])
        p['job']['unexpected_execution_setting'] = 'changed'
        with self.assertRaises(AssertionError):
            validate_case(**p)

    def test_incomplete_or_substituted_evidence_is_rejected(self):
        mutations = [
            ('original still running', lambda p:p['original'].update(process_reaped=False)),
            ('already successful original', lambda p:p['original'].update(status='computed',process_exit_code=0)),
            ('wrong original identity', lambda p:p['case']['job'].update(source='different')),
            ('wrong verification identity', lambda p:p['checked'].update(job_id='different')),
            ('verification timeout', lambda p:p['terminal'].update(supervisor_timeout=True)),
            ('verification failure', lambda p:p['terminal'].update(returncode=1)),
            ('verification unreaped', lambda p:p['terminal'].update(process_reaped=False)),
            ('unverified source', lambda p:p['sources'].update(all_pins_checked_before_and_after=False)),
            ('new equilibrium solve', lambda p:p['checked']['operations'].update(new_cold_solves=1)),
            ('no fresh check', lambda p:p['checked']['operations'].update(fresh_residuals=0)),
            ('missing physical check', lambda p:p['checked']['checks'].pop()),
            ('duplicated physical check', lambda p:p['checked']['checks'].__setitem__(0,dict(p['checked']['checks'][1]))),
            ('failed physical check', lambda p:p['checked']['checks'][0].update(passed=False)),
            ('unfinished original', lambda p:p['saved'].update(converged=False)),
            ('large original residual', lambda p:p['saved'].update(residual=1e-6)),
            ('large fresh residual', lambda p:p['checked'].update(fresh_residual=1e-6)),
            ('nonfinite residual', lambda p:p['checked'].update(fresh_residual=float('nan'))),
            ('boolean residual', lambda p:p['checked'].update(fresh_residual=False)),
            ('different condition', lambda p:p['request']['condition'].update(beta=5)),
            ('warm start', lambda p:p['request'].update(initial_state='changed')),
            ('partial continuation', lambda p:p['request'].update(continuation={})),
            ('substituted sensor value', lambda p:p['checked']['values'].update(RY_m=.2)),
        ]
        for name, mutate in mutations:
            with self.subTest(name=name):
                p = self.packet(); mutate(p)
                with self.assertRaises(AssertionError):validate_case(**p)


if __name__ == '__main__':
    unittest.main()
