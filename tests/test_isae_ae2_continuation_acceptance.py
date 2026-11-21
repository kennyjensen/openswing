"""Incomplete attempts and changed inputs must not fill original native slots."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from scripts.isae_ae2_continuation_acceptance import validate
from scripts.recover_isae_ae2_saved import CHECK_NAMES, expected_request


class ContinuationAcceptance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name)/'literal.asw'
        self.source.write_text('unchanged source bytes')

    def packet(self):
        job = dict(id='AE-2-control',source=str(self.source),panels=80,
                   condition=dict(beta=1),settings={})
        original = dict(status='timeout',process_reaped=True,execution_completed=True,process_exit_code=-9)
        case = dict(name='cold16-m80',job=deepcopy(job),original_process_result=deepcopy(original))
        job['result'] = original
        values = dict(RY_m=.1,Psi_deg=2.,sensor_V_m_s=16.,sensor_beta_deg=3.)
        record = dict(job=job['id'],case=case['name'],status='computed',fresh_residual=1e-13,values=deepcopy(values))
        checked = dict(status='computed',fresh_residual=1e-13,values=deepcopy(values),
                       checks=[dict(name=k,passed=True) for k in CHECK_NAMES])
        terminal = dict(returncode=0,process_reaped=True,supervisor_timeout=False)
        saved = dict(continuation_status='complete',converged=True,residual=1e-13,
                     sensors=[dict(position_earth=[0,.1,0],heading=2.,speed=16.,beta=3.)])
        return dict(job=job,case=case,record=record,checked=checked,terminal=terminal,
                    saved=saved,request=expected_request(job))

    def test_completed_chain_keeps_failed_receipt_unchanged(self):
        p=self.packet(); before=deepcopy(p)
        self.assertEqual(validate(**p),p['checked']['values'])
        self.assertEqual(p,before)

    def test_partial_or_invalid_result_cannot_be_accepted(self):
        mutations = [
            lambda p:p['saved'].update(continuation_status='pending'),
            lambda p:p['saved'].update(converged=False),
            lambda p:p['saved'].update(residual=1e-8),
            lambda p:p['checked'].update(fresh_residual=float('nan')),
            lambda p:p['record'].update(fresh_residual=True),
            lambda p:p['checked']['checks'].pop(),
            lambda p:p['checked']['checks'][0].update(passed=False),
            lambda p:p['terminal'].update(process_reaped=False),
            lambda p:p['terminal'].update(supervisor_timeout=True),
        ]
        for i,mutate in enumerate(mutations):
            with self.subTest(i=i):
                p=self.packet();mutate(p)
                with self.assertRaises(AssertionError):validate(**p)

    def test_changed_input_or_substituted_sensor_is_rejected(self):
        mutations = [
            lambda p:p['request']['condition'].update(beta=5),
            lambda p:p['request'].update(initial_state='warm seed'),
            lambda p:p['request'].update(continuation={}),
            lambda p:p['case']['job'].update(panels=40),
            lambda p:p['record']['values'].update(RY_m=.2),
            lambda p:p['record'].update(job='another native slot'),
            lambda p:p['job']['result'].update(status='computed',process_exit_code=0),
        ]
        for i,mutate in enumerate(mutations):
            with self.subTest(i=i):
                p=self.packet();mutate(p)
                with self.assertRaises(AssertionError):validate(**p)


if __name__ == '__main__':
    unittest.main()
