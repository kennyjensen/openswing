"""Independent still-air energy reference for the literal Pazy modal section."""
from pathlib import Path
import importlib.util
import numpy as np
import pytest

path = Path(__file__).resolve().parents[1]/'scripts/isae_st2_modal_reference.py'
spec = importlib.util.spec_from_file_location('pazy_independent_reference',path)
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)


@pytest.mark.parametrize('elements',[5,17,31])
def test_fluid_matrix_reproduces_integrated_rigid_wrenches(elements):
    nodes,k0,m0 = reference.matrices(elements,9.81)
    _,k,m = reference.matrices(elements,9.81,density=1.23)
    np.testing.assert_array_equal(k,k0)
    # Columns: normal translation, rigid rotation about the root chord axis,
    # spanwise pitch at the elastic/CG axis, and chordwise translation.
    rigid = np.zeros((5*len(nodes),4))
    rigid[0::5,0] = 1.
    rigid[0::5,1] = nodes;rigid[1::5,1] = 1.
    rigid[4::5,2] = 1.;rigid[2::5,3] = 1.
    length = reference.LENGTH; arm = .005; chord = .1
    mu = 1.23*np.pi*chord**2/4
    expected = mu*np.array([[length,length**2/2,-arm*length,0.],
        [length**2/2,length**3/3,-arm*length**2/2,0.],
        [-arm*length,-arm*length**2/2,(arm**2+chord**2/32)*length,0.],
        [0.,0.,0.,0.]])
    np.testing.assert_allclose(rigid.T@(m-m0)@rigid,expected,rtol=2e-12,atol=2e-16)
    np.testing.assert_allclose(m,m.T,rtol=0.,atol=2e-18)


def test_still_air_frequencies_converge_to_vacuum_at_zero_density():
    vacuum = reference.modes(12,9.81,count=7)
    dilute = reference.modes(12,9.81,count=7,density=1e-8)
    fluid = reference.modes(12,9.81,count=7,density=1.23)
    np.testing.assert_allclose(dilute['frequencies_Hz'],vacuum['frequencies_Hz'],rtol=2e-9,atol=1e-9)
    assert np.all(np.array(fluid['frequencies_Hz'])<=np.array(vacuum['frequencies_Hz'])*(1+1e-10))


@pytest.mark.parametrize('density',[-1.,np.nan,np.inf])
def test_invalid_fluid_density_is_rejected(density):
    with pytest.raises(ValueError,match='density'):
        reference.matrices(4,density=density)
