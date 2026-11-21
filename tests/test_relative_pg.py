"""Physical PG translation precision against independent Decimal arithmetic."""
from decimal import Decimal, localcontext
import math
import numpy as np
import pytest
from openswing.aero import horseshoe_velocity
from openswing.vortex_tangent import horseshoe_velocity_partials, VortexFieldTangent, VortexDerivativeUnavailable


def dec(value): return Decimal.from_float(float(value))
def dot(a, b): return sum((x*y for x, y in zip(a, b)), Decimal(0))
def sub(a, b): return [x-y for x, y in zip(a, b)]
def cross(a, b): return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
def transform(P, x): return [dot(row, x) for row in P]


def decimal_physical(point, a, b, direction, pg, core, exclude=False):
    """General closed form in 100 digits; no production geometry/kernel calls."""
    def field(r, d, finite):
        length = dot(d, d).sqrt(); u = [x/length for x in d]
        z = dot(r, u); h = [x-z*y for x, y in zip(r, u)]
        den = dot(h, h)+core*core
        if den <= dec(1e-26): return [Decimal(0)]*3
        coefficient = z/(z*z+den).sqrt()
        coefficient = (coefficient-(z-length)/((z-length)**2+den).sqrt()) if finite else 1+coefficient
        coefficient /= den*4*dec(math.pi)
        return [x*coefficient for x in cross(u, r)]
    r1 = transform(pg, sub(point, a)); r2 = transform(pg, sub(point, b))
    segment = transform(pg, sub(b, a)); wind = transform(pg, direction)
    bound = [Decimal(0)]*3 if exclude else field(r1, segment, True)
    first, second = field(r1, wind, False), field(r2, wind, False)
    value = [z+x-y for z, x, y in zip(bound, second, first)]
    return [dot(column, value) for column in zip(*pg)]


def fixture(oblique, translated):
    # Dyadic geometry is exactly representable before/after this common shift.
    a = np.array([.125, -.5, .25]); b = np.array([.25, .5, .125])
    point = np.array([.1875+1/1024, 1/2048, .1875+1/4096])
    shift = np.array([2**20, -2**21, 2**19]) if translated else np.zeros(3)
    wind = np.array([1., .125, -.0625]) if oblique else np.array([1., 0., 0.])
    unit = wind/np.linalg.norm(wind); pg = np.eye(3)+.173*np.outer(unit, unit)
    return point+shift, a+shift, b+shift, wind, pg


@pytest.mark.parametrize('oblique', [False, True])
@pytest.mark.parametrize('core', [0., .03125])
@pytest.mark.parametrize('excluded', [False, True])
def test_pg_translation_preserves_precise_physical_velocity(oblique, core, excluded):
    base = fixture(oblique, False); moved = fixture(oblique, True)
    actual = horseshoe_velocity(*moved, core, exclude_bound=excluded)
    with localcontext() as context:
        context.prec = 100
        point, a, b, wind, pg = moved
        reference = decimal_physical(*[list(map(dec, x)) for x in [point, a, b, wind]],
                                     [list(map(dec, row)) for row in pg], dec(core), excluded)
    np.testing.assert_allclose(actual, list(map(float, reference)), rtol=5e-13, atol=5e-14)
    np.testing.assert_array_equal(actual, horseshoe_velocity(*base, core, exclude_bound=excluded))


@pytest.mark.parametrize('excluded', [False, True])
def test_pg_partials_retain_physical_chain_under_translation(excluded):
    base = fixture(True, False); moved = fixture(True, True); core = .03125
    actual = horseshoe_velocity_partials(*moved, core, exclude_bound=excluded)
    original = horseshoe_velocity_partials(*base, core, exclude_bound=excluded)
    for name in actual: np.testing.assert_array_equal(actual[name], original[name])
    with localcontext() as context:
        context.prec = 100
        point, a, b, wind, pg = moved
        inputs = [list(map(dec, x)) for x in [point, a, b, wind]]+[dec(core)]
        P = [list(map(dec, row)) for row in pg]
        for index, name in enumerate(['point', 'a', 'b', 'direction', 'core']):
            columns = []
            for axis in range(1 if name == 'core' else 3):
                step = Decimal('1e-25')
                values = []
                for sign in [1, -1]:
                    args = [list(x) if isinstance(x, list) else x for x in inputs]
                    if name == 'core': args[index] += sign*step
                    else: args[index][axis] += sign*step
                    values.append(decimal_physical(*args[:4], P, args[4], excluded))
                columns.append([float((x-y)/(2*step)) for x, y in zip(*values)])
            reference = np.array(columns)[0] if name == 'core' else np.array(columns).T
            np.testing.assert_allclose(actual[name], reference, rtol=3e-12,
                                       atol=3e-13*np.max(abs(reference)), err_msg=name)
    np.testing.assert_allclose(actual['point']+actual['a']+actual['b'], 0., atol=2e-13)


def test_retained_mask_guard_uses_relative_pg_geometry():
    shift = np.array([2**20, -2**21, 2**19], dtype=float)
    p = np.array([[.25, .5, .125]])+shift
    a = np.array([[.25, 0., .125]])+shift; b = np.array([[.25, 1., .125]])+shift
    wind = np.array([1., 0., 0.]); pg = np.diag([1.173, 1., 1.])
    with pytest.raises(VortexDerivativeUnavailable, match='principal-value mask'):
        VortexFieldTangent(p, a, b, wind, pg, 0., np.ones(1))
    # Excluding the bound does not exclude either trailing filament.
    field = VortexFieldTangent(p, a, b, wind, pg, 0., np.ones(1), exclude_bound=np.ones((1,1), dtype=bool))
    expected = horseshoe_velocity(p[:,None], a[None], b[None], wind, pg, 0., exclude_bound=True)[:,0]
    np.testing.assert_array_equal(field.value(p, a, b, 0.), expected)
