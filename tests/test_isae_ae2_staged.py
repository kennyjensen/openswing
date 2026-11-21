"""The staged collector must preserve original physical acceptance."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from scripts.execute_isae_ae2_staged import collect


class StagedAcceptance(unittest.TestCase):
    def packet(self):
        # Completed control from the original, unmodified adapter/worker.
        fixture=json.loads((Path(__file__).parent/'fixtures/isae_ae2_staged_control.json').read_text())
        return fixture['job'],fixture['original'],dict(returncode=0,supervisor_timeout=False,process_reaped=True)

    def test_original_adapter_parity(self):
        job,original,terminal=self.packet()
        actual=collect(job,original['worker_report'],terminal,True)
        self.assertTrue(actual)
        for key,value in actual.items():
            self.assertEqual(value,original[key],key)

    def test_partial_or_failed_evidence_rejected(self):
        job,original,terminal=self.packet()
        for change in ('missing','failed','duplicate','extra_solve','wrong_case','wrong_kernel'):
            with self.subTest(change=change):
                report=deepcopy(original['worker_report'])
                if change=='missing':report['checks'].pop()
                elif change=='failed':report['checks'][0]['passed']=False
                elif change=='duplicate':report['checks'][0]=report['checks'][1]
                elif change=='extra_solve':report['operations']['cold_solves']=2
                elif change=='wrong_case':report['case']='other'
                else:report['kernel_pins']={}
                with self.assertRaises(AssertionError):collect(job,report,terminal,True)
        with self.assertRaises(AssertionError):collect(job,original['worker_report'],terminal,False)
        with self.assertRaises(AssertionError):collect(job,original['worker_report'],dict(terminal,process_reaped=False),True)
        for failed in (dict(terminal,returncode=-9),dict(terminal,supervisor_timeout=True)):
            outcome=collect(job,original['worker_report'],failed,True)
            self.assertNotEqual(outcome['status'],'computed')
            self.assertFalse(outcome['reference_match'])
