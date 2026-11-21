"""Repeated section-load transfers retain physical virtual power."""
import numpy as np
import pytest
from openswing.local_motion import NetworkMotion, rotation_matrix as exp
from test_local_motion import moving_network


@pytest.mark.parametrize('material',[False,True])
def test_repeated_loads_and_changed_arcs_preserve_virtual_power(material):
    net,r,q,values=moving_network()
    field=NetworkMotion(net,r,q,*values)
    rng=np.random.default_rng(5873)
    fractions=np.broadcast_to([.12,.5,.91],(net.ne,3)).copy()
    for stage in range(7):
        if stage==2:fractions[:,1]=.67
        if stage==3:fractions=fractions[:,:2]
        if stage==4:
            if material:field.rb[:]=exp([.07,-.04,.02])@field.rb
            else:field.q[:]=exp([.07,-.04,.02])@field.q
        if stage==5:material=not material
        if stage==6:fractions=np.full(net.ne,.36)
        force,moment=rng.normal(size=(2,)+fractions.shape+(3,))
        local,_,_=field.sample(1,fractions,material=material)
        transferred=field.nodal_wrenches(1,fractions,force,moment,material=material)
        section_power=np.sum(local.velocity*force+local.rates*moment)
        nodal_power=sum(np.sum(values[0,ids]*f+values[1,ids]*m) for ids,f,m in transferred)
        np.testing.assert_allclose(nodal_power,section_power,rtol=2e-14,atol=2e-14)
        # Returned forces/couples belong to this load, never to cached maps.
        before=[(f.copy(),m.copy()) for _,f,m in transferred]
        for _,f,m in transferred:f[:]=0.;m[:]=0.
        repeated=field.nodal_wrenches(1,fractions,force,moment,material=material)
        for (_,f,m),(ef,em) in zip(repeated,before):
            assert f.tobytes()==ef.tobytes()
            assert m.tobytes()==em.tobytes()
