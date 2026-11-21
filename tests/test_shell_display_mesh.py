"""Shell reporting tables must not change the physical aeroelastic model."""
from pathlib import Path

import numpy as np
import pytest

from openswing.aero import FlightCondition
from openswing.asw import parse_asw
from openswing.discretization import report
from openswing.geometry import model_meshes, undeformed_mesh
from openswing.network import solve_static
from test_network import model


@pytest.mark.parametrize('field', ['Cshell', 'Nshell', 'Atshell'])
@pytest.mark.parametrize('lifting', [False, True])
def test_shell_only_break_keeps_physical_breaks_attachments_and_arc_mesh(field, lifting):
    # The physical geometry, stiffness and control breaks must all survive.
    source = '''Beam 1
Display-independent mesh
t y z
0 0 0
.8 .8 .1
.8 .8 .1
2 2 .4
t EA
0 1000
.6 1000
.6 2000
2 2000
t dCLdF3
0 0
1.3 0
1.3 .1
2 .1
'''
    if lifting:
        source += 't chord\n0 .5\n2 .5\n'
    plain = model(source + f't {field}\n0 .1\n2 .1\nEnd\n')
    changed = model(source + f't {field}\n0 .1\n.43 .1\n.43 .2\n2 .2\nEnd\n')
    loads = [dict(beam=1, t=1.1, force=[0, 1, 0])]
    original_mesh = model_meshes(plain, 5, loads)[0]
    changed_mesh = model_meshes(changed, 5, loads)[0]
    restored_mesh = undeformed_mesh(changed_mesh)
    for key in ('t0', 't1', 'tm', 'ts', 'r0', 'r1', 'rm', 'frames', 'length', 'theta'):
        np.testing.assert_array_equal(getattr(changed_mesh, key), getattr(original_mesh, key))
    for key in ('r0', 'r1', 'rm', 'frames', 'length'):
        np.testing.assert_allclose(getattr(restored_mesh, key), getattr(original_mesh, key), atol=1e-14, rtol=0)
    nodes = np.r_[changed_mesh.t0, changed_mesh.t1[-1]]
    for station in (.6, .8, 1.1, 1.3):
        assert station in nodes
    assert .43 not in nodes
    if lifting:
        for station in (-.6, -.8, -1.3, 0):
            assert station in nodes
        assert -.43 not in nodes
    assert report(plain, [original_mesh], 5, loads) == report(changed, [changed_mesh], 5, loads)
    # Excluding a mesh station must not discard the data or its one-sided values.
    beam = changed.beams[0]
    np.testing.assert_array_equal(beam.distributions[field].breaks, [.43])
    assert beam.value(field, .43, side='left') == .1
    assert beam.value(field, .43, side='right') == .2
    if lifting:
        assert beam.value(field, -.43, side='left') == .2
        assert beam.value(field, -.43, side='right') == .1


def test_changed_shell_tables_preserve_coupled_equilibrium_but_change_strain_and_stress():
    source = Path('examples/stress-wing.asw').read_text()
    old_shell = 't Cshell Nshell Atshell\n0 .2 .06 .0002\n8 .1 .04 .00006'
    assert old_shell in source
    plain = parse_asw(source.replace(old_shell,
        't Cshell Nshell Atshell\n0 .2 .06 .0002\n8 .2 .06 .0002'))
    changed = parse_asw(source.replace(old_shell,
        't Cshell Nshell Atshell\n0 .2 .06 .0002\n3.7 .2 .06 .0002\n'
        '3.7 .4 .18 .0008\n8 .4 .18 .0008'))
    condition = FlightCondition(speed=30, alpha=5, mach=0)
    before, after = [solve_static(m, condition, panels=4, gravity=[0, 0, 0], tolerance=1e-10)
                     for m in (plain, changed)]
    assert before['converged'] and after['converged']
    assert before['residual'] < 1e-10 and after['residual'] < 1e-10
    assert before['max_displacement'] > .05  # Live aero and finite elastic deformation.
    assert before['CL'] > .1
    for key in ('mesh_discretization', 'nodes', 'strips', 'force', 'moment',
                'support_force', 'support_moment', 'force_balance', 'moment_balance'):
        assert before[key] == after[key]
    changed_strain = []
    for old, new in zip(before['elements'], after['elements'], strict=True):
        assert {k: v for k, v in old.items() if k != 'shell'} == {
            k: v for k, v in new.items() if k != 'shell'}
        if abs(new['t']) < 3.7:
            assert new['shell'] == old['shell']
        else:
            shell = new['shell']
            assert (shell['c'], shell['n'], shell['area_thickness']) == (.4, .18, .0008)
            curvature = new['curvature_change']
            expected = new['axial_strain_tension'] + .4*curvature[2] - .18*curvature[0]
            assert shell['axial_strain'] == pytest.approx(expected, abs=1e-14)
            assert shell['shear_stress'] == pytest.approx(old['shell']['shear_stress']/4, abs=1e-12)
            changed_strain.append(abs(shell['axial_strain'] - old['shell']['axial_strain']))
    assert changed_strain and max(changed_strain) > 1e-6
