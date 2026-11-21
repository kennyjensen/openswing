"""Small output-format check; no numerical solver or scientific runtime."""
from copy import deepcopy
from pathlib import Path
import runpy
import unittest

add_span_outputs = runpy.run_path(str(Path(__file__).resolve().parents[1] /
    'openswing/span_output_derivatives.py'))['add_span_outputs']


class SpanOutputTests(unittest.TestCase):
    def test_existing_stencil_supplies_lengths_flow_axis_moments_and_impulses(self):
        # Four physical snapshots, with independent real/imaginary excursions.
        def sample(x):
            return dict(strips=[dict(length=3 + x / 2, normal_speed=10 + x,
                normal_mach=.1 + x / 100, relative_velocity=[10 + x, 0, 2 * x])],
                elements=[dict(moment_axes=[1 + 2 * x, 3, -x])],
                body_shoulders=[dict(beam=2, t=4, force=[0, x, 4 + 3 * x])])
        snapshots = [sample(x) for x in (1, -1, 2, -2)]
        before = deepcopy(snapshots)
        section = dict(shell_strain=dict(real=7, imag=9))
        output = dict(strips=[dict(beam=1, t=3)], sections=[section])

        def delta(values):
            if any(v is None for v in values):
                return None
            def difference(a, b):
                return [difference(x, y) for x, y in zip(a, b)] if isinstance(a, list) else (a - b) / 2
            return dict(real=difference(values[0], values[1]), imag=difference(values[2], values[3]))

        add_span_outputs(output, snapshots, delta)
        self.assertEqual(output['strips'][0]['length'], dict(real=.5, imag=1))
        self.assertEqual(output['strips'][0]['relative_velocity'], dict(real=[1, 0, 2], imag=[2, 0, 4]))
        self.assertEqual(section['moment_axes'], dict(real=[2, 0, -1], imag=[4, 0, -2]))
        self.assertEqual(section['shell_strain'], dict(real=7, imag=9))
        self.assertIsNone(section['distributed_gravity_normal'])
        self.assertEqual(output['body_shoulders'][0], dict(beam=2, t=4, force=dict(real=[0, 1, 3], imag=[0, 2, 6])))
        self.assertEqual(snapshots, before)

    def test_structural_only_results_have_no_invented_aerodynamics(self):
        output = dict(strips=[], sections=[])
        add_span_outputs(output, [dict(elements=[]) for _ in range(4)], lambda v: self.fail('No stencil needed'))
        self.assertEqual(output, dict(strips=[], sections=[], body_shoulders=[]))


if __name__ == '__main__':
    unittest.main()
