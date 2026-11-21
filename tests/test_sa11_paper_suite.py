"""Scoring guards: a missing/invalid curve must never become a passing sample."""
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location('paper_suite', Path(__file__).resolve().parents[1] / 'scripts/sa11_paper_suite.py')
suite = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(suite)


def point(alpha, cl, cd, valid=True):
    return dict(alpha=alpha, CL=cl, CD=cd, valid=valid)


class PaperSuiteGuards(unittest.TestCase):
    def test_equal_lift_uses_each_curves_own_alpha(self):
        a = [point(1, .3, .01), point(1.25, .4, .02)]
        b = [point(2, .3, .02), point(2.25, .4, .04)]
        va, aa, _ = suite.interpolate(a, .35, 'CL', 'CD')
        vb, ab, _ = suite.interpolate(b, .35, 'CL', 'CD')
        self.assertAlmostEqual(va, .015)
        self.assertAlmostEqual(vb, .03)
        self.assertNotEqual(aa, ab)

    def test_missing_samples_cannot_be_interpolated_over(self):
        value, _, reason = suite.interpolate([point(0, .2, .01), point(1, .4, .02)], .3, 'CL', 'CD')
        self.assertIsNone(value)
        self.assertIn('Missing', reason)

    def test_rejected_middle_state_cannot_be_bridged(self):
        points = [point(0, .2, .01), point(.25, None, None, False), point(.5, .4, .02)]
        self.assertIsNone(suite.interpolate(points, .3, 'CL', 'CD')[0])

    def test_no_extrapolation(self):
        points = [point(0, .2, .01), point(.25, .3, .02)]
        self.assertIsNone(suite.interpolate(points, .4, 'CL', 'CD')[0])

    def test_no_implicit_branch_selection(self):
        points = [point(0, .2, .01), point(.25, .4, .02), point(.5, .3, .03)]
        self.assertIn('Nonmonotone', suite.interpolate(points, .25, 'CL', 'CD')[2])

    def test_missing_and_mismatch_are_distinct(self):
        self.assertEqual(suite.decision(None, .01, .05)[0], 'unavailable')
        self.assertEqual(suite.decision(.0104, .01, .05)[0], 'pass')
        self.assertEqual(suite.decision(.0106, .01, .05)[0], 'mismatch')

    def test_raw_drag_gate_is_not_diluted_by_plot_allowance(self):
        self.assertEqual(suite.decision(.0106, .01, .05)[0], 'mismatch')
        # Adding the paper's experimental plotting offset would incorrectly pass.
        self.assertEqual(suite.decision(.0106 + .0064, .01 + .0064, .05)[0], 'pass')


if __name__ == '__main__':
    unittest.main()
