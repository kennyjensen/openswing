"""State columns against fresh physical fields; no circulation or aircraft solve."""
import numpy as np
import pytest
from openswing.factored_influence import FactoredInfluence
from openswing.ground import GroundPlane
from openswing.vortex_state_tangent import vortex_state_columns
from openswing.vortex_tangent import VortexDerivativeUnavailable


def fixture(flag=0):
    rng = np.random.default_rng(89213)
    points = rng.normal(size=(7, 3)); points[:, 2] += 1.4
    a = np.array([[0., -1., .2], [.1, 0., .1], [.1, 0., .1], [-.4, -.2, .6]])
    b = np.array([[.1, 0., .1], [.3, 1., .3], [-.2, .5, .8], [.1, 0., .1]])
    direction = np.array([1.7, .23, -.11])
    e = direction/np.linalg.norm(direction)
    pg = np.eye(3)+.31*np.outer(e, e)
    core = np.broadcast_to(np.array([0., .03, .08, .11, .04, .02, .07])[:, None], (7, 4)).copy()
    core[:, 2] += .025  # Coincident coordinates, different effective receiver cores.
    gamma = np.array([.8, .8, -.31, .25])
    mask = np.zeros((7, 4), dtype=bool); mask[1, 0] = True; mask[4, 2] = True
    ground = GroundPlane(flag, [0., 0., 3.], [7., -4., 12.], [.2, -.1, 1.])
    shapes = [points.shape, a.shape, b.shape, direction.shape, pg.shape]
    columns = [np.zeros(shape+(6,)) for shape in shapes]
    for k in range(5):columns[k][..., k] = rng.normal(size=shapes[k])*.13
    for shape, col in zip(shapes, columns):col[..., 5] = rng.normal(size=shape)*.09
    return (points, a, b, direction, pg, core, gamma), columns, ground, mask


def centered(args, columns, ground=None, mask=None, *, step):
    values = []
    for k in range(columns[0].shape[-1]):
        endpoints = []
        for sign in (-1., 1.):
            geometry = [value+sign*step*col[..., k] for value, col in zip(args[:5], columns)]
            operator = FactoredInfluence(*geometry, args[5], ground, exclude_bound=mask)
            endpoints.append(operator.apply(args[6]))
        values.append((endpoints[1]-endpoints[0])/(2*step))
    return np.stack(values, axis=-1)


@pytest.mark.parametrize('flag', [-1, 0, 1])
@pytest.mark.parametrize('retained', [False, True])
def test_all_state_columns_match_two_fresh_physical_stencils(flag, retained):
    args, cols, ground, mask = fixture(flag)
    baseline = FactoredInfluence(*args[:6], ground, exclude_bound=mask) if retained else None
    actual = vortex_state_columns(*args, *cols, ground, exclude_bound=mask, baseline=baseline)
    for step in (2e-5, 1e-5):
        expected = centered(args, cols, ground, mask, step=step)
        np.testing.assert_allclose(actual, expected, atol=2e-10, rtol=2e-7)


@pytest.mark.parametrize('flag', [-1, 1])
def test_real_own_bound_exclusion_preserves_image_bound_derivative(flag):
    a=np.array([[0., -1., .2]]);b=np.array([[0., 1., .2]])
    points=(a+b)/2
    args=(points,a,b,np.array([1., .1, 0.]),np.diag([1.2, 1., 1.]),0.,np.ones(1))
    cols=[np.zeros(v.shape+(2,)) for v in args[:5]]
    cols[0][0, :, 0]=[.2, -.1, .3];cols[1][0, :, 0]=[-.1, .03, -.2]
    cols[2][0, :, 0]=[.13, -.07, .11];cols[3][:, 1]=[.1, .2, .3]
    cols[4][:, :, 1]=np.array([[.1, .03, -.02], [.04, -.05, .07], [-.03, .01, .02]])
    mask=np.ones((1,1),dtype=bool)
    ground=GroundPlane(flag,[0.,0.,2.],[3.,-2.,5.])
    actual=vortex_state_columns(*args,*cols,ground,exclude_bound=mask)
    for step in (2e-5,1e-5):
        np.testing.assert_allclose(actual,centered(args,cols,ground,mask,step=step),atol=2e-10,rtol=2e-7)
    no_image=vortex_state_columns(*args,*cols,exclude_bound=mask)
    assert np.max(abs(actual-no_image))>1e-5


@pytest.mark.parametrize('flag', [-1, 0, 1])
def test_coincident_endpoints_keep_distinct_displacement_columns(flag):
    a=np.array([[0.,-1.,0.],[0.,0.,0.]])
    b=np.array([[0.,0.,0.],[0.,1.,0.]])
    points=np.array([[.7,.13,.2],[.9,-.17,.3]])
    args=(points,a,b,np.array([1.,.11,.04]),np.diag([1.21,1.,1.]),np.array([[0.,0.],[.07,.07]]),np.ones(2))
    cols=[np.zeros(v.shape+(3,)) for v in args[:5]]
    cols[1][1,:,0]=[.13,-.09,.07]
    cols[2][0,:,1]=[-.08,.12,.04]
    cols[1][1,:,2]=[.13,-.09,.07];cols[2][0,:,2]=[-.08,.12,.04]
    ground=GroundPlane(flag,[0.,0.,3.],[4.,2.,-3.])
    actual=vortex_state_columns(*args,*cols,ground)
    assert np.max(abs(actual[:,:,0]))>.01 and np.max(abs(actual[:,:,1]))>.01
    np.testing.assert_allclose(actual[:,:,2],actual[:,:,0]+actual[:,:,1],atol=2e-15,rtol=2e-14)
    for step in (2e-5,1e-5):
        np.testing.assert_allclose(actual,centered(args,cols,ground,step=step),atol=2e-9,rtol=2e-7)


@pytest.mark.parametrize('power', [8, 16, 22])
def test_cancelled_internal_wake_retains_outer_field_state_derivative(power):
    # A straight, equal-Gamma split has exactly the same physical field as its
    # unsplit bound leg. The internal ray approaches singularity but cancels.
    a=np.array([[0.,-1.,0.],[0.,0.,0.]])
    b=np.array([[0.,0.,0.],[0.,1.,0.]])
    points=np.array([[1.,2.**-power,2.**-power]])
    args=(points,a,b,np.array([1.,0.,0.]),np.diag([1.2,1.,1.]),0.,np.ones(2))
    cols=[np.zeros(v.shape+(3,)) for v in args[:5]]
    cols[0][0,:,0]=[.03,.04,-.02]
    cols[3][:,1]=[0.,.07,-.03]
    cols[4][:,:,2]=np.array([[.11,.03,-.02],[.01,.04,.05],[-.03,.02,.07]])
    actual=vortex_state_columns(*args,*cols)
    outer=(points,a[:1],b[-1:],args[3],args[4],0.,np.ones(1))
    outer_cols=[cols[0],cols[1][:1],cols[2][-1:],cols[3],cols[4]]
    for step in (2e-5,1e-5):
        expected=centered(outer,outer_cols,step=step)
        np.testing.assert_allclose(actual,expected,atol=2e-11,rtol=2e-8)
        # Fresh split physical evaluations also group the exactly shared ray.
        np.testing.assert_allclose(actual,centered(args,cols,step=step),atol=2e-11,rtol=2e-8)


def test_pg_homogeneity_direction_normalization_and_translation_invariants():
    args,_,_,_=fixture()
    args=(*args[:5],0.,args[6])
    cols=[np.zeros(v.shape+(3,)) for v in args[:5]]
    cols[4][:,:,0]=args[4]  # Zero-core inner 1/scale cancels outer PG scale.
    cols[3][:,1]=args[3]  # Multiplying the wake direction changes no ray.
    for col in cols[:3]:col[:,:,2]=[.21,-.13,.09]
    actual=vortex_state_columns(*args,*cols)
    np.testing.assert_allclose(actual,0.,atol=3e-14,rtol=0.)


def test_small_nonzero_shared_wake_strength_and_motion_survive_cancellation():
    a=np.array([[0.,-1.,0.],[0.,0.,0.]])
    b=np.array([[0.,0.,0.],[0.,1.,0.]])
    points=np.array([[1.,2.**-12,2.**-12]])
    args=(points,a,b,np.array([1.,0.,0.]),np.eye(3),0.,np.array([1.,1.+2.**-30]))
    cols=[np.zeros(v.shape+(2,)) for v in args[:5]]
    cols[1][1,:,0]=cols[2][0,:,0]=[.125,-.0625,.03125]
    cols[0][0,:,1]=[.0625,.03125,-.125]
    cols[3][:,1]=[0.,.0625,.03125]
    cols[4][:,:,1]=np.diag([.125,.0625,.03125])
    baseline=FactoredInfluence(*args[:6])
    assert min(abs(baseline.wake_strengths(args[6])))==2.**-30
    actual=vortex_state_columns(*args,*cols,baseline=baseline)
    for step in (2e-7,1e-7):
        np.testing.assert_allclose(actual,centered(args,cols,step=step),atol=3e-9,rtol=2e-6)


def test_receiver_blocking_does_not_change_columns(monkeypatch):
    import openswing.vortex_state_tangent as module
    args,cols,ground,mask=fixture(1)
    expected=vortex_state_columns(*args,*cols,ground,exclude_bound=mask)
    monkeypatch.setattr(module,'_PAIR_BLOCK',1)
    monkeypatch.setattr(module,'_RECEIVER_BLOCK',1)
    actual=vortex_state_columns(*args,*cols,ground,exclude_bound=mask)
    np.testing.assert_allclose(actual,expected,atol=2e-15,rtol=2e-14)


def test_invalid_inputs_and_incompatible_grouping_are_rejected(monkeypatch):
    import openswing.vortex_state_tangent as module
    args,cols,ground,mask=fixture()
    baseline=FactoredInfluence(*args[:6],ground,exclude_bound=mask)
    bad=list(cols);bad[4]=bad[4][:,:,:-1]
    with pytest.raises(VortexDerivativeUnavailable,match='layout'):vortex_state_columns(*args,*bad)
    bad=list(cols);bad[3]=bad[3].copy();bad[3][0,0]=np.nan
    with pytest.raises(VortexDerivativeUnavailable,match='Nonfinite'):vortex_state_columns(*args,*bad)
    bad=list(args);bad[5]=-.01
    with pytest.raises(VortexDerivativeUnavailable,match='nonnegative'):vortex_state_columns(*bad,*cols)
    bad=list(args);bad[1]=bad[1].copy();bad[1][1,0]+=.01
    with pytest.raises(VortexDerivativeUnavailable,match='endpoint grouping'):
        vortex_state_columns(*bad,*cols,baseline=baseline)
    bad=list(args);bad[5]=bad[5].copy();bad[5][0,1]+=.01
    with pytest.raises(VortexDerivativeUnavailable,match='core grouping'):
        vortex_state_columns(*bad,*cols,baseline=baseline)
    monkeypatch.setattr(module,'_STORAGE_LIMIT',1)
    with pytest.raises(VortexDerivativeUnavailable,match='budget'):vortex_state_columns(*args,*cols)


def test_zero_columns_and_empty_sources_have_explicit_shapes():
    args,cols,_,_=fixture()
    assert vortex_state_columns(*args,*[c[...,:0] for c in cols]).shape==(7,3,0)
    empty=(args[0],np.empty((0,3)),np.empty((0,3)),args[3],args[4],0.,np.empty(0))
    empty_cols=[cols[0],np.empty((0,3,6)),np.empty((0,3,6)),cols[3],cols[4]]
    np.testing.assert_array_equal(vortex_state_columns(*empty,*empty_cols),np.zeros((7,3,6)))
