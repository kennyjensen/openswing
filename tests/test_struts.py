import numpy as np
import pytest
from scipy.spatial.transform import Rotation
from openswing.struts import strut_load
from openswing.network import solve_static
from test_network import model, beam, tip, balanced


def test_axial_energy_gradient_and_objectivity():
    row = np.array([1, 2, .4, 2, .1, -.3, 1, -2, -.15, 2400.])
    point = row[2:5]+[.3, -.1, .5]
    state = strut_load(row, point)
    h = 1e-6
    gradient = np.array([(strut_load(row, point+h*d)["energy"]-strut_load(row, point-h*d)["energy"])/(2*h) for d in np.eye(3)])
    np.testing.assert_allclose(state["force"], -gradient, rtol=2e-9)
    q = Rotation.from_rotvec([.2, -.7, .1]).as_matrix(); shift = np.array([2., -3., 4.])
    rotated = row.copy(); rotated[2:5] = q@row[2:5]+shift; rotated[5:8] = q@row[5:8]+shift
    other = strut_load(rotated, q@point+shift)
    np.testing.assert_allclose(other["force"], q@state["force"], atol=1e-10)
    assert other["energy"] == pytest.approx(state["energy"])


@pytest.mark.parametrize("mode,extension", [("bilateral", 10/1500), ("wire", 10/500)])
def test_compressive_strut_or_slack_wire_has_correct_parallel_stiffness(mode, extension):
    m = model(beam(stiffness="0 0 0 1000 0 0"), "Ground\n1 0 0\nEnd\nStrut\n1 2 0 2 0 0 4 0 0 2000\nEnd\n")
    result = solve_static(m, panels=4, loads=[dict(beam=1, t=2, force=[0, 10, 0])], strut_mode=mode)
    np.testing.assert_allclose(tip(result), [0, 2+extension, 0], atol=1e-10)
    assert result["struts"][0]["slack"] == (mode == "wire")
    balanced(result)


def test_preload_and_superimposed_struts_match_exact_axial_solution():
    strut = "1 2 0 2 0 0 4 0 -.1 1000\n"
    m = model(beam(stiffness="0 0 0 1000 0 0"), "Ground\n1 0 0\nEnd\nStrut\n"+strut*2+"End\n")
    result = solve_static(m, panels=4)
    np.testing.assert_allclose(tip(result), [0, 2+.1*2000/2950, 0], atol=1e-10)
    assert result["struts"][0]["tension"] > 0
    np.testing.assert_allclose(result["applied_force"], 0, atol=1e-12)
    balanced(result)


def test_braces_remove_translational_mechanism_at_zero_load():
    attachments = "Ground\n1 0 2\nEnd\nStrut\n"+"\n".join(
        f"1 0 0 0 0 {x} {y} {z} 0 1000" for x,y,z in [(2,0,0),(0,-2,0),(0,0,2)])+"\nEnd\n"
    result = solve_static(model(beam(stiffness="0 0 0 0 0 0"), attachments), panels=4,
                          loads=[dict(beam=1, t=2, force=[3, 2, 5])])
    assert result["max_displacement"] > .01
    balanced(result)


def test_offset_pylon_follows_rotation_and_preserves_total_moment():
    row = np.array([1, 2, .3, 2, -.4, .2, .1, -1, 0, 60])
    m = model(beam(), "Ground\n1 0 0\nEnd\nStrut\n"+" ".join(map(str,row))+"\nEnd\n")
    result = solve_static(m, panels=8, loads=[dict(beam=1, t=2, moment=[15, 5, 3])])
    node = result["nodes"][-1]
    expected = np.array(node["position"])+np.array(node["rotation"])@(row[2:5]-[0,2,0])
    np.testing.assert_allclose(result["struts"][0]["position"], expected, atol=1e-12)
    assert result["max_rotation_deg"] > 8
    balanced(result)


def test_invalid_rest_length_rejected_and_slack_wire_energy_zero():
    row = np.array([1, 2, 0, 2, 0, 0, 4, 0, .2, 2000.])
    state = strut_load(row, row[2:5], tension_only=True)
    assert state["energy"] == state["tension"] == 0
    row[8] = -2
    with pytest.raises(ValueError, match="positive unloaded length"):
        strut_load(row, row[2:5])
