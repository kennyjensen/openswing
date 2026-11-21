"""Analytic descriptor oracles for constrained versus physical weak inertia.

These pencils are specified directly from equations, without model assembly,
physical residuals, or archive-derived dimensions or eigenvalue targets.
"""
import numpy as np
import pytest

from openswing.linear_dynamics import eigensystem


def check_modes(a, m, modes, report, expected):
    """Check complete roots, original equations and the independent mass dual."""
    values = np.array([complex(*mode['eigenvalue']) for mode in modes])
    assert len(values) == report['finite_dimension'] == len(expected)
    packet = report['finite_spectrum']
    assert packet is not None
    census = np.array([complex(*value) for value in packet['eigenvalues']])
    for actual in (values, census):
        remaining = list(actual)
        assert len(remaining) == len(expected)
        for value in expected:
            nearest = int(np.argmin(abs(np.asarray(remaining) - value)))
            assert remaining.pop(nearest) == pytest.approx(value, rel=2e-8, abs=2e-10)

    right = np.column_stack([mode['right'] for mode in modes])
    left = np.column_stack([mode['left'] for mode in modes])
    pairings = left.conj().T @ m @ right
    diagonal = np.diag(pairings)
    assert np.all(np.isfinite(diagonal)) and np.all(abs(diagonal) > 0)
    # Independent rescaling also covers a reaction-dominated state chart for
    # which the solver legitimately declines unit-pairing normalization.
    np.testing.assert_allclose(pairings / diagonal[:, None], np.eye(len(expected)),
                               rtol=0, atol=2e-8)
    for index, mode in enumerate(modes):
        value = values[index]
        v, w = right[:, index], left[:, index]
        pencil_scale = np.linalg.norm(a) + abs(value) * np.linalg.norm(m)
        assert np.linalg.norm(a @ v - value * (m @ v)) < 2e-11 * pencil_scale * np.linalg.norm(v)
        assert np.linalg.norm(w.conj() @ a - value * (w.conj() @ m)) < 2e-11 * pencil_scale * np.linalg.norm(w)
        if mode['biorthogonal_normalized']:
            assert diagonal[index] == pytest.approx(1, rel=2e-10, abs=2e-10)


@pytest.mark.parametrize('change_chart', [False, True])
@pytest.mark.xfail(strict=True, raises=ValueError, reason=(
    'Known limitation: the conservative initial weak-inertia guard rejects '
    'a legitimate constrained-away derivative. A proposed delayed guard was '
    'rejected because it could hide finite poles; this desired success remains unresolved.'))
def test_weak_inertial_coordinate_removed_only_by_its_algebraic_constraint(change_chart):
    # xdot=-2x, epsilon*qdot=p, q=0. Consequently q=p=0 and
    # det(A-lambda*M)=lambda+2: there is precisely one finite root.
    a = np.array([[-2., 0., 0.], [0., 0., 1.], [0., 1., 0.]])
    m = np.diag([1., 1e-10, 0.])
    columns = np.ones(3)
    column_order = np.arange(3)
    if change_chart:
        rows, columns = np.array([.5, 2., 4.]), np.array([2., .25, 8.])
        row_order, column_order = [2, 0, 1], [1, 2, 0]
        a = (rows[:, None] * a * columns)[np.ix_(row_order, column_order)]
        m = (rows[:, None] * m * columns)[np.ix_(row_order, column_order)]
    modes, report = eigensystem(a, m, count=8, time_scale=3., rank_tolerance=1e-9)
    check_modes(a, m, modes, report, [-2.])
    v = np.empty(3, dtype=complex)
    v[column_order] = modes[0]['right']
    physical = columns * v
    np.testing.assert_allclose(physical[1:], 0, atol=2e-12 * abs(physical[0]))


@pytest.mark.parametrize('with_reaction', [False, True])
def test_true_finite_weak_inertia_is_rejected_after_constraint_elimination(with_reaction):
    # xdot=-2x, epsilon*qdot=-3q (+p), with p=0 when present.
    # Both exact roots -2 and -3/epsilon remain physical. An algebraic
    # reaction may not disguise the latter as an infinite eigenvalue.
    if with_reaction:
        a = np.array([[-2., 0., 0.], [0., -3., 1.], [0., 0., 1.]])
        m = np.diag([1., 1e-10, 0.])
    else:
        a, m = np.diag([-2., -3.]), np.diag([1., 1e-10])
    with pytest.raises(ValueError, match='weak inertia'):
        eigensystem(a, m, count=8, rank_tolerance=1e-9)


def test_roundoff_border_cluster_cannot_hide_a_finite_weak_root():
    # A final quotient check alone is insufficient. The 101*eps inertia is
    # constrained away, but the 99*eps inertia has the real root -3/(99*eps).
    # Deleting the latter at a hard 100*eps floor would leave the apparently
    # healthy finite quotient [-2] and silently lose a finite root.
    eps = np.finfo(float).eps
    a = np.array([[-2., 0., 0., 0.], [0., 0., 1., 0.],
                  [0., 1., 0., 0.], [0., 0., 0., -3.]])
    m = np.diag([1., 101 * eps, 0., 99 * eps])
    with pytest.raises(ValueError, match='ambiguous|weak inertia'):
        eigensystem(a, m, count=8, rank_tolerance=1e-9)


def test_initially_resolved_inertia_may_contract_in_a_reaction_dominated_chart():
    # xdot=v, vdot=p, x+delta*p=0 -> xddot=-x/delta.
    # Initial nonzero derivative singular values are both one. An orthonormal
    # finite state basis contracts M by about delta because p dominates the
    # coordinate norm. Applying a new unconditional final 1e-9 cutoff would
    # reject an existing resolved +/-i*1e5 pair, although no initial weak
    # derivative needed provisional retention.
    delta = 1e-10
    a = np.array([[0., 1., 0.], [0., 0., 1.], [1., 0., delta]])
    m = np.diag([1., 1., 0.])
    modes, report = eigensystem(a, m, count=8, rank_tolerance=1e-9)
    check_modes(a, m, modes, report, [1j / np.sqrt(delta), -1j / np.sqrt(delta)])
    for mode in modes:
        value = complex(*mode['eigenvalue'])
        x, velocity, reaction = mode['right']
        assert velocity == pytest.approx(value * x, rel=2e-8, abs=2e-12)
        assert reaction == pytest.approx(value * velocity, rel=2e-8, abs=2e-12)
        assert x + delta * reaction == pytest.approx(0, abs=2e-12 * abs(reaction))


def test_retained_weak_oscillator_cannot_disappear_at_a_later_constraint_stair():
    # xdot=-2x alongside epsilon*qdot=v, vdot=p, q+delta*p=0.
    # The exact finite roots are -2 and +/-i/sqrt(epsilon*delta).
    # Eliminating q contracts its retained inertia to epsilon*delta=1e-20.
    # Dropping that derivative at a later numerical floor could erase BOTH
    # oscillator roots, leaving a healthy-looking [-2] final mass quotient.
    # The unresolved full spectrum must be rejected, not silently shortened.
    epsilon = delta = 1e-10
    a = np.array([[-2., 0., 0., 0.], [0., 0., 1., 0.],
                  [0., 0., 0., 1.], [0., 1., 0., delta]])
    m = np.diag([1., epsilon, 1., 0.])
    with pytest.raises(ValueError, match='ambiguous|weak inertia|ill-conditioned'):
        eigensystem(a, m, count=8, rank_tolerance=1e-9)


def test_fixed_dense_orthogonal_chart_does_not_hide_the_contracted_weak_pair():
    # Prescribed once, without a rotation search: the exact dyadic Hadamard
    # matrix and independent fixed row/column permutations mix every state.
    # This is strictly equivalent to the preceding pencil, whose finite
    # roots are -2,+/-i1e10. Reliable rejection is acceptable; a successful
    # result must include the complete three-root spectrum and original
    # left/right equations, never just the well-scaled stable coordinate.
    epsilon = delta = 1e-10
    a = np.array([[-2., 0., 0., 0.], [0., 0., 1., 0.],
                  [0., 0., 0., 1.], [0., 1., 0., delta]])
    m = np.diag([1., epsilon, 1., 0.])
    h = np.array([[1., 1., 1., 1.], [1., -1., 1., -1.],
                  [1., 1., -1., -1.], [1., -1., -1., 1.]]) / 2
    left, right = h[[2, 0, 3, 1], :], h[:, [1, 3, 0, 2]]
    a, m = left @ a @ right, left @ m @ right
    try:
        modes, report = eigensystem(a, m, count=8, rank_tolerance=1e-9)
    except ValueError as exc:
        assert any(reason in str(exc).lower() for reason in (
            'weak inertia', 'ambiguous', 'ill-conditioned', 'underdetermined', 'residual'))
    else:
        frequency = 1 / np.sqrt(epsilon * delta)
        check_modes(a, m, modes, report, [-2., 1j * frequency, -1j * frequency])
