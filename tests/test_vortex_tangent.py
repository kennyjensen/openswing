"""Independent quadrature and high-precision checks of full source motion."""
from decimal import Decimal, localcontext
import math
import numpy as np
import pytest
from scipy.integrate import quad_vec
from openswing.aero import finite_vortex, semi_infinite_vortex, horseshoe_velocity
from openswing.ground import GroundPlane
from openswing.vortex_tangent import (finite_partials, semi_infinite_partials,
    horseshoe_velocity_partials, VortexDerivativeUnavailable)


@pytest.mark.parametrize('receiver_y', [.5, 2.])
def test_retained_field_rejects_masked_bound_stencils_but_preserves_exclusions(receiver_y):
    from openswing.vortex_tangent import VortexFieldTangent
    points = np.array([[0., receiver_y, 0.]])
    a, b = np.array([[0., 0., 0.]]), np.array([[0., 1., 0.]])
    args = (points, a, b, np.array([1., 0., 0.]), np.eye(3), 0., np.ones(1))
    if receiver_y == .5:
        with pytest.raises(VortexDerivativeUnavailable, match='principal-value mask'):
            VortexFieldTangent(*args)
    else:
        # The exterior bound axis is regular, despite its zero base velocity.
        retained = VortexFieldTangent(*args)
        delta = np.array([[1e-6, 0., 0.]])
        expected = horseshoe_velocity((points+delta)[:, None, :], a[None, :, :],
            b[None, :, :], args[3], args[4], 0.)[:, 0]
        np.testing.assert_allclose(retained.value(points+delta, a, b, 0.), expected, atol=2e-12, rtol=2e-12)
    excluded = np.ones((1, 1), dtype=bool)
    retained = VortexFieldTangent(*args, exclude_bound=excluded)
    delta = np.array([[1e-6, 0., 0.]])
    expected = horseshoe_velocity((points+delta)[:, None, :], a[None, :, :],
        b[None, :, :], args[3], args[4], 0., exclude_bound=excluded)[:, 0]
    np.testing.assert_allclose(retained.value(points+delta, a, b, 0.), expected, atol=2e-12, rtol=2e-12)


def cross_matrix(v):
    return np.array([[0., -v[2], v[1]], [v[2], 0., -v[0]], [-v[1], v[0], 0.]])


def integrate_partials(p, a, d, core, finite):
    r = p-a
    length = np.linalg.norm(d)
    v = d if finite else d/length
    def integrand(t):
        delta = r-t*v
        square = delta@delta+core**2
        w = np.cross(v, r)
        point = cross_matrix(v)/square**1.5-3*np.outer(w, delta)/square**2.5
        source = -cross_matrix(r)/square**1.5+3*t*np.outer(w, delta)/square**2.5
        radius = -3*core*w/square**2.5
        return np.r_[point.ravel(), source.ravel(), radius]
    values = quad_vec(integrand, 0., 1. if finite else np.inf, epsabs=1e-12, epsrel=1e-12)[0]/(4*np.pi)
    p = values[:9].reshape(3, 3)
    q = values[9:18].reshape(3, 3)
    if finite:
        return dict(point=p, a=-p-q, b=q, core=values[18:])
    return dict(point=p, origin=-p, direction=q@(np.eye(3)-np.outer(v, v))/length, core=values[18:])


@pytest.mark.parametrize('finite', [False, True])
@pytest.mark.parametrize('core', [0., .13])
def test_direct_receiver_and_source_partials_match_integrated_physical_derivatives(finite, core):
    a = np.array([.1, -.2, .3]); d = np.array([.9, .7, -.5])
    for p in [np.array([-.7, .9, .4]), np.array([1.2, -.8, .5]), np.array([.5, .2, 1.4])]:
        reference = integrate_partials(p, a, d, core, finite)
        actual = finite_partials(p, a, a+d, core) if finite else semi_infinite_partials(p, a, d, core)
        for name in reference:
            np.testing.assert_allclose(actual[name], reference[name], atol=2e-13, rtol=2e-12)


def decimal_velocity(p, a, endpoint, core, finite):
    def dot(x, y): return sum((u*v for u, v in zip(x, y)), Decimal(0))
    def cross(x, y): return [x[1]*y[2]-x[2]*y[1], x[2]*y[0]-x[0]*y[2], x[0]*y[1]-x[1]*y[0]]
    d = [v-u for u, v in zip(a, endpoint)] if finite else endpoint
    length = dot(d, d).sqrt(); u = [v/length for v in d]
    r = [x-y for x, y in zip(p, a)]; z = dot(r, u)
    h = [v-z*w for v, w in zip(r, u)]; den = dot(h, h)+core**2
    outside = (z < 0 or z > length) if finite else z < 0
    if den == 0 or (den <= Decimal.from_float(1e-26) and not outside): return [Decimal(0)]*3
    value = z/(z*z+den).sqrt()
    value = value-(z-length)/((z-length)**2+den).sqrt() if finite else 1+value
    coefficient = value/den/(4*Decimal.from_float(math.pi))
    return [v*coefficient for v in cross(u, r)]


def decimal_partials(point, core, finite):
    with localcontext() as ctx:
        ctx.prec = 110
        zero = Decimal(0); one = Decimal(1)
        base = [list(map(lambda x:Decimal.from_float(float(x)), point)), [zero]*3, [one, zero, zero], Decimal.from_float(core)]
        result = {}
        names = ['point', 'a', 'b', 'core'] if finite else ['point', 'origin', 'direction', 'core']
        for index, name in enumerate(names):
            cols = []
            for axis in range(1 if name == 'core' else 3):
                value = base[index] if name == 'core' else base[index][axis]
                # A direction perturbation acts through the entire wake arm;
                # at x=1e6 and core=1e-12, 1e-24 still has visible O(h^2) error.
                step = Decimal('1e-28')*(1+abs(value))
                samples = []
                for sign in [1, -1]:
                    args = [list(v) if isinstance(v, list) else v for v in base]
                    if name == 'core': args[index] += sign*step
                    else: args[index][axis] += sign*step
                    samples.append(decimal_velocity(*args, finite))
                cols.append([float((a-b)/(2*step)) for a, b in zip(*samples)])
            result[name] = np.array(cols)[0] if name == 'core' else np.array(cols).T
        return result


@pytest.mark.parametrize('finite', [False, True])
def test_near_axis_and_far_field_partials_against_110_digit_reference(finite):
    for core in [0., 1e-12, .003]:
        for x in [-1e6, -2., -.1, .5, 1.1, 2., 1e6]:
            for y in [.01, 1e-6, 1e-12]:
                p = [x, y, -.3*y]
                reference = decimal_partials(p, core, finite)
                actual = (finite_partials(p, [0., 0., 0.], [1., 0., 0.], core) if finite else
                          semi_infinite_partials(p, [0., 0., 0.], [1., 0., 0.], core))
                for name in reference:
                    scale = np.max(abs(reference[name]))
                    np.testing.assert_allclose(actual[name], reference[name], atol=2e-13*scale, rtol=3e-12,
                        err_msg=str((finite, core, x, y, name)))


@pytest.mark.parametrize('flag', [-1, 0, 1])
def test_complete_horseshoe_pg_images_direction_and_bound_exclusion(flag):
    points = np.array([[.2, -.7, .5], [1.2, .8, .3]])[:, None, :]
    a = np.array([[0., -.4, -.1], [-.2, .5, .2], [.3, -.5, 1.]])[None, :, :]
    b = a+np.array([.1, 1.1, -.2])
    wind = np.array([2., .15, -.1]); wind_unit = wind/np.linalg.norm(wind)
    pg = np.eye(3)+.3*np.outer(wind_unit, wind_unit)
    ground = GroundPlane(flag, [0., 0., 4.], [10., -5., 13.], [0., .1, 1.])
    core = np.array([[0., .1, .05]])
    bound = np.array([[True, False, True], [False, False, True]])
    actual = horseshoe_velocity_partials(points, a, b, wind, pg, core, ground, exclude_bound=bound)
    base = dict(point=points, a=a, b=b, direction=wind, core=core)
    for name, argument in base.items():
        columns = []
        for axis in range(1 if name == 'core' else 3):
            delta = np.ones_like(argument)*1e-4 if name == 'core' else np.zeros_like(argument)
            if name != 'core': delta[..., axis] = 1e-4
            samples = []
            for factor in [1., -1., 2., -2.]:
                args = dict(base); args[name] = argument+factor*delta
                samples.append(horseshoe_velocity(args['point'], args['a'], args['b'], args['direction'], pg,
                    args['core'], ground, exclude_bound=bound))
            columns.append((8*(samples[0]-samples[1])-(samples[2]-samples[3]))/(12e-4))
        reference = columns[0] if name == 'core' else np.stack(columns, axis=-1)
        np.testing.assert_allclose(actual[name], reference, atol=8e-11, rtol=3e-8)


def test_translation_normalization_principal_value_and_switch_guards():
    p = np.array([[.3, .4, -.1], [-2., .1, .3]])
    a = np.array([.1, -.2, .3]); b = np.array([.9, .6, -.2]); wind = np.array([2., .3, -.1])
    first = finite_partials(p, a, b, .02)
    np.testing.assert_allclose(first['point']+first['a']+first['b'], 0., atol=1e-16)
    second = semi_infinite_partials(p, a, wind, .02)
    np.testing.assert_array_equal(second['point']+second['origin'], 0.)
    np.testing.assert_allclose(second['direction']@wind, 0., atol=1e-16)
    for function in [finite_partials, semi_infinite_partials]:
        result = function([.2, 1e-14, 0.], [0., 0., 0.], [1., 0., 0.])
        for value in result.values(): np.testing.assert_array_equal(value, 0.)
        with pytest.raises(VortexDerivativeUnavailable, match='switch'):
            function([.2, 0., 0.], [0., 0., 0.], [1., 0., 0.], core=1e-13)


@pytest.mark.parametrize('flag', [-1, 0, 1])
def test_retained_field_action_matches_full_moving_sources_receivers_and_cores(flag):
    from openswing.vortex_tangent import VortexFieldTangent
    from openswing.factored_influence import FactoredInfluence
    rng = np.random.default_rng(34519)
    points = rng.normal(size=(7, 3)); points[:, 2] += 2.
    a = rng.normal(size=(5, 3)); b = a+np.array([.2, 1.1, -.1])
    wind = np.array([1., .2, -.1]); pg = np.diag([1.3, 1., 1.])
    core = np.full((7, 5), .17); gamma = rng.normal(size=5)
    ground = GroundPlane(flag, [0., 0., 6.], [3., 2., -1.])
    mask = np.zeros((7, 5), dtype=bool); mask[1, 2] = True
    fields = VortexFieldTangent(points, a, b, wind, pg, core, gamma, ground, exclude_bound=mask)
    def physical(p, av, bv, c):
        return FactoredInfluence(p, av, bv, wind, pg, c, ground, exclude_bound=mask).apply(gamma)
    np.testing.assert_array_equal(fields.value(points, a, b, core), physical(points, a, b, core))
    for change in ['receiver', 'a', 'b', 'core', 'all']:
        directions = [np.zeros_like(v) for v in (points, a, b, core)]
        for index, name in enumerate(['receiver', 'a', 'b', 'core']):
            if change in (name, 'all'):
                if name == 'core': directions[index][:, 3] = .3
                else: directions[index][2] = rng.normal(size=3)
        step = 1e-4
        values = [physical(*[v+k*step*d for v, d in zip((points, a, b, core), directions)]) for k in [1., -1., 2., -2.]]
        expected = (8*(values[0]-values[1])-(values[2]-values[3]))/(12*step)
        actual = (fields.value(*[v+step*d for v, d in zip((points, a, b, core), directions)])-
                  fields.value(*[v-step*d for v, d in zip((points, a, b, core), directions)]))/(2*step)
        np.testing.assert_allclose(actual, expected, atol=2e-11, rtol=2e-9)
    assert fields.bytes < 128*1024**2
    with pytest.raises(ValueError): fields.source_a[0, 0, 0, 0] = 9.
    with pytest.raises(VortexDerivativeUnavailable, match='budget'):
        VortexFieldTangent(points, a, b, wind, pg, core, gamma, ground, limit=1)
    with pytest.raises(VortexDerivativeUnavailable, match='layout'):
        fields.value(points[:1], a, b, core)


def _coincident_wake_derivative_fixture(flag):
    points = np.array([[.4, -.12, .23], [.7, .15, .35]])
    a = np.array([[0., -1., 0.], [0., 0., 0.]])
    b = np.array([[0., 0., 0.], [0., 1., 0.]])
    direction = np.array([1., .12, .04]); direction /= np.linalg.norm(direction)
    pg = np.eye(3) + .1*np.outer(direction, direction)
    core = np.array([[0., 0.], [.07, .07]])
    gamma = np.array([.9, .9])
    ground = GroundPlane(flag, [0., 0., 2.], [3., 5., 7.])
    return points, a, b, direction, pg, core, gamma, ground


@pytest.mark.parametrize('flag', [-1, 0, 1])
@pytest.mark.parametrize('change', ['end_alone', 'start_alone', 'both', 'core_alone'])
def test_coincident_group_retains_independent_source_derivatives(flag, change):
    from openswing.factored_influence import FactoredInfluence
    from openswing.vortex_tangent import VortexFieldTangent
    points, a, b, direction, pg, core, gamma, ground = _coincident_wake_derivative_fixture(flag)
    tangent = VortexFieldTangent(points, a, b, direction, pg, core, gamma, ground)
    value = FactoredInfluence(points, a, b, direction, pg, core, ground)
    np.testing.assert_array_equal(tangent.base, value.apply(gamma))
    # The internal wake has zero net strength at the base but two independent
    # source coordinates. Its perturbations must not inherit that cancellation.
    assert np.count_nonzero(value.wake_strengths(gamma)) == 2
    da = np.zeros_like(a); db = np.zeros_like(b); dc = np.zeros_like(core)
    motion = np.array([.13, -.09, .07])
    if change in ('end_alone', 'both'): db[0] = motion
    if change in ('start_alone', 'both'): da[1] = motion
    if change == 'core_alone': dc[1, 0] = .11
    expanded = horseshoe_velocity_partials(points[:, None], a[None], b[None], direction, pg, core, ground)
    exact = (np.einsum('ijab,j,jb->ia', expanded['a'], gamma, da)
             + np.einsum('ijab,j,jb->ia', expanded['b'], gamma, db)
             + np.einsum('ija,j,ij->ia', expanded['core'], gamma, dc))
    assert np.max(np.abs(exact)) > 1e-5
    # The analytic geometry-column consumer must include the same independent
    # endpoint/core actions, with the zero-core receiver excluded explicitly.
    columns = tangent.source_columns(np.arange(len(a)), da[:, :, None], db[:, :, None],
        dc[-1, :, None], core_active=core != 0.)
    np.testing.assert_allclose(columns[:, :, 0], exact, rtol=2e-8, atol=2e-9)
    for h in (2e-5, 1e-5):
        plus = FactoredInfluence(points, a+h*da, b+h*db, direction, pg, core+h*dc, ground).apply(gamma)
        minus = FactoredInfluence(points, a-h*da, b-h*db, direction, pg, core-h*dc, ground).apply(gamma)
        np.testing.assert_allclose((plus-minus)/(2*h), exact, rtol=2e-8, atol=2e-9)
        # Retained evaluation applies the original a/b/core changes separately.
        np.testing.assert_allclose((tangent.value(points,a+h*da,b+h*db,core+h*dc)-tangent.base)/h,
                                   exact, rtol=2e-8, atol=2e-9)


@pytest.mark.parametrize('flag', [-1, 0, 1])
def test_one_receiver_retained_base_uses_same_value_arithmetic(flag):
    from openswing.factored_influence import FactoredInfluence
    from openswing.vortex_tangent import VortexFieldTangent
    points, a, b, direction, pg, core, gamma, ground = _coincident_wake_derivative_fixture(flag)
    points, core = points[:1], core[:1]
    expected = FactoredInfluence(points,a,b,direction,pg,core,ground).apply(gamma)
    for single_dot in (False, True):
        tangent = VortexFieldTangent(points,a,b,direction,pg,core,gamma,ground,single_dot=single_dot)
        np.testing.assert_array_equal(tangent.base, expected)


def test_shared_wake_receiver_partial_matches_unsplit_horseshoe():
    from openswing.factored_influence import FactoredInfluence
    from openswing.vortex_tangent import VortexFieldTangent
    a = np.array([[0., -1., 0.], [0., 0., 0.]])
    b = np.array([[0., 0., 0.], [0., 1., 0.]])
    direction = np.array([1., 0., 0.]); pg = np.eye(3); gamma = np.ones(2)
    for power in (8, 12, 16, 20):
        eps = 2.**(-power); points = np.array([[1., eps, eps]])
        tangent = VortexFieldTangent(points, a, b, direction, pg, 0., gamma)
        # An internal equal-strength wake cancels exactly. The outer-end
        # horseshoe has no near-singular internal ray and gives an analytic
        # receiver derivative for the same physical bound path and wakes.
        expected = horseshoe_velocity_partials(points[:, None], a[:1][None],
            b[-1:][None], direction, pg, 0.)['point'][:, 0]
        np.testing.assert_allclose(tangent.receiver, expected, rtol=0., atol=5e-14)
        outer = FactoredInfluence(points, a[:1], b[-1:], direction, pg).apply(gamma[:1])
        np.testing.assert_allclose(tangent.base, outer, rtol=0., atol=5e-15)
        # Moving the internal split along the straight bound line changes
        # neither its physical path nor either outer wake.
        av = a.copy(); bv = b.copy(); av[1, 1] += 2.**-20; bv[0, 1] += 2.**-20
        np.testing.assert_allclose(tangent.value(points, av, bv, 0.), tangent.base,
                                   rtol=0., atol=5e-15)
