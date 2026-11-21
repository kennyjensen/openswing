"""Analytic checks of the paper's full-pencil modal route.

These tests assemble only small exact descriptor pencils. They do not create
aircraft, equilibria, physical residuals, or fitted reference frequencies.
"""
import numpy as np
import pytest
from scipy.linalg import block_diag

from openswing.linear_dynamics import eigensystem


def _roots(modes):
    return np.asarray([complex(*mode['eigenvalue']) for mode in modes])


def _match(actual, expected, *, atol=2e-9, rtol=2e-9):
    remaining = list(actual)
    assert len(remaining) == len(expected)
    for wanted in expected:
        index = int(np.argmin(abs(np.asarray(remaining)-wanted)))
        assert remaining.pop(index) == pytest.approx(wanted, abs=atol, rel=rtol)


def _paper_metadata(report, dimension, count):
    assert report['method'] == 'full_shift_invert'
    assert report['full_dimension'] == dimension
    assert report['requested_count'] == count
    assert report['finite_dimension'] is None
    assert report['eliminated_dimension'] is None
    assert report['finite_spectrum'] is None
    assert report['rank_tolerance'] is None
    assert report['right_reduction'] == []
    assert report['integrator_deflation']['count'] == 0
    assert report['arnoldi']['factorizations'] == 1
    assert report['arnoldi']['operator_applications'] >= count
    recovery = report['left_recovery_counts']
    assert (recovery['inverse_iteration']+recovery['inverse_iteration_failed']+recovery['conjugate_reuse']
            +recovery['repeated_pole_fallback']+recovery['bordered_refinement']) == count
    assert recovery['schur_pencils'] in (0, 1)
    if recovery['inverse_iteration_failed'] or recovery['repeated_pole_fallback']:
        assert recovery['schur_pencils'] == 1


def _original_equations(a, m, modes, *, cross_pairing=True):
    left, right = [], []
    for mode in modes:
        lam = complex(*mode['eigenvalue'])
        v, w = np.asarray(mode['right']), np.asarray(mode['left'])
        scale = np.linalg.norm(a)+abs(lam)*np.linalg.norm(m)
        right_error = np.linalg.norm(a@v-lam*(m@v))/(scale*np.linalg.norm(v))
        left_error = np.linalg.norm(w.conj()@a-lam*(w.conj()@m))/(scale*np.linalg.norm(w))
        assert right_error < 2e-10
        assert left_error < 2e-10
        assert np.vdot(w, m@v) == pytest.approx(1., abs=2e-9)
        assert mode['biorthogonal_normalized']
        left.append(w)
        right.append(v)
    if cross_pairing:
        np.testing.assert_allclose(np.asarray(left).conj()@m@np.asarray(right).T,
                                   np.eye(len(modes)), atol=2e-8, rtol=0)


def _constrained_masses():
    # q1=q2=q. Adding both force equations gives
    # 5 qdd + 1.2 qd + 28 q = 0. The reaction is not zero:
    # r=(2 lambda^2+.4 lambda+11) q.
    a = np.array([[0., 0., 1., 0., 0.],
                  [0., 0., 0., 1., 0.],
                  [-18., 7., -.4, 0., 1.],
                  [7., -24., 0., -.8, -1.],
                  [1., -1., 0., 0., 0.]])
    m = np.diag([1., 1., 2., 3., 0.])
    # Remote poles keep a legal Arnoldi search dimension; they are not used to
    # supply eigenvalues or expected counts to the implementation.
    return block_diag(a, -np.diag([20., 30., 40.])), block_diag(m, np.eye(3))


@pytest.mark.parametrize('format', ['csc', 'csr'])
def test_sparse_input_keeps_physical_pencil_without_dense_conversion(format, monkeypatch):
    from scipy.sparse import csc_matrix, csr_matrix

    a0, m0 = _constrained_masses()
    constructor = csc_matrix if format == 'csc' else csr_matrix
    a, m = constructor(a0), constructor(m0)
    original = [(x.data.copy(), x.indices.copy(), x.indptr.copy()) for x in (a, m)]

    def forbidden(*args, **kwargs):
        raise AssertionError('A resolved full-pencil search must not densify its sparse matrices')

    for cls in (csc_matrix, csr_matrix):
        monkeypatch.setattr(cls, 'toarray', forbidden)
        monkeypatch.setattr(cls, 'todense', forbidden)
    modes, report = eigensystem(a, m, count=2, shift=(-.12, 0.),
                                time_scale=3.25, method='full_shift_invert')
    _match(_roots(modes), np.roots([5., 1.2, 28.]))
    _original_equations(a0, m0, modes)
    assert report['pencil_storage'] == 'sparse'
    assert report['left_recovery_counts']['schur_pencils'] == 0
    for matrix, before in zip((a, m), original):
        for actual, expected in zip((matrix.data, matrix.indices, matrix.indptr), before):
            np.testing.assert_array_equal(actual, expected)


@pytest.mark.parametrize('time_scale', [.001, 3.25, 1000.])
@pytest.mark.parametrize('changed_chart', [False, True])
def test_constrained_nonsymmetric_pencil_retains_reactions_and_physical_time(time_scale, changed_chart):
    a, m = _constrained_masses()
    rows = np.array([.5, 3., 2., .25, 4., 1., 2., .5]) if changed_chart else np.ones(8)
    columns = np.array([2., .25, 1., 3., .5, 2., .5, 1.]) if changed_chart else np.ones(8)
    aa, mm = rows[:, None]*a*columns, rows[:, None]*m*columns
    modes, report = eigensystem(aa, mm, count=2, shift=(-.12, 0.),
                               time_scale=time_scale, method='full_shift_invert')
    _match(_roots(modes), np.roots([5., 1.2, 28.]))
    _paper_metadata(report, 8, 2)
    _original_equations(aa, mm, modes)
    for mode in modes:
        lam = complex(*mode['eigenvalue'])
        v = columns*np.asarray(mode['right'])
        w = rows*np.asarray(mode['left'])
        q = v[0]
        assert abs(q) > 1e-4
        expected_v = q*np.array([1., 1., lam, lam, 2*lam**2+.4*lam+11, 0., 0., 0.])
        np.testing.assert_allclose(v, expected_v, atol=2e-9, rtol=2e-9)
        # Independent adjoint from reaction balance w_force1=w_force2=u.
        # Its normalization is conj(u)*(10 lambda+1.2)*q = 1.
        u = 1/np.conj((10*lam+1.2)*q)
        lc = np.conj(lam)
        expected_w = u*np.array([2*lc+.4, 3*lc+.8, 1., 1.,
                                 2*lc**2+.4*lc+11, 0., 0., 0.])
        np.testing.assert_allclose(w, expected_w, atol=2e-8, rtol=2e-8)
        assert abs(w[4]) > 1e-3


def test_resolved_weak_inertia_is_searched_as_a_finite_pole_without_rank_truncation():
    # m0 zdot=-z has the genuine finite root -1e10. Algebraic rows have
    # exactly zero mass and must remain distinct from this weak inertia.
    a = np.diag([-1., -2., -3., -4., -5., -6., 1., 2.])
    m = np.diag([1e-10, 1., 1., 1., 1., 1., 0., 0.])
    modes, report = eigensystem(a, m, count=1, shift=(-.9e10, 0.),
                               time_scale=1e10, method='full_shift_invert')
    _match(_roots(modes), [-1e10], atol=1e-3, rtol=2e-10)
    _paper_metadata(report, 8, 1)
    _original_equations(a, m, modes)
    v, w = np.asarray(modes[0]['right']), np.asarray(modes[0]['left'])
    assert abs(v[0]) > .9
    np.testing.assert_allclose(v[1:], 0, atol=2e-8, rtol=0)
    assert np.vdot(w, m@v) == pytest.approx(1., abs=2e-9)


def test_exact_zero_is_found_numerically_without_deflation_or_complete_census_claim():
    a = np.diag([0., -2., -4., -6., 1., 2.])
    m = np.diag([1., 1., 1., 1., 0., 0.])
    modes, report = eigensystem(a, m, count=2, shift=(-.1, .1),
                               method='full_shift_invert')
    _match(_roots(modes), [0., -2.])
    _paper_metadata(report, 6, 2)
    _original_equations(a, m, modes)
    assert all(not mode['exact_integrator'] for mode in modes)


def test_repeated_semisimple_roots_keep_full_equations_and_claimed_block_pairing():
    # The implementation now explicitly claims checked block dual recovery;
    # diagonal-only normalization is insufficient for that claim.
    a = np.diag([-2., -2., -4., -6., -8., -10.])
    m = np.eye(6)
    modes, report = eigensystem(a, m, count=2, shift=(-2.2, .03),
                               method='full_shift_invert')
    _match(_roots(modes), [-2., -2.])
    _paper_metadata(report, 6, 2)
    _original_equations(a, m, modes)
    assert report['left_recovery_counts']['repeated_pole_fallback'] == 2
    assert report['biorthogonality']['verified']
    assert all(x['status']=='PASS' for x in report['biorthogonality']['repeated_clusters'])


def test_near_distinct_nonsymmetric_roots_keep_each_original_adjoint_equation():
    # This fixed separation lies inside the selected-root cluster criterion,
    # but the two poles are genuinely distinct. No averaged pole is valid.
    a = np.diag([-2., -2.-4e-8, -4., -6., -8., -10.])
    a[0,1] = 2e-8
    m = np.eye(6)
    modes, report = eigensystem(a, m, count=2, shift=(-2.2, .03),
                               method='full_shift_invert')
    _match(_roots(modes), [-2., -2.-4e-8], atol=2e-11, rtol=2e-11)
    _paper_metadata(report, 6, 2)
    _original_equations(a, m, modes)
    assert report['biorthogonality']['verified']


def test_exact_singular_paper_left_factor_is_an_explicit_failure():
    from openswing.modal_arnoldi import inverse_left
    a = np.array([[0.,1.],[-1.,0.]])
    left, report = inverse_left(a, np.eye(2), 1j, np.array([1.,1j]))
    assert left is None
    assert report['status']=='FAIL' and report['reason']=='singular_factor'
    assert report['factorizations']==1 and report['linear_solves']==0


def test_recorded_left_fallback_preserves_supplied_ritz_pairs(monkeypatch):
    # Controlled helper failure tests caller recovery without relying on an
    # Arnoldi approximation landing exactly on a floating singular factor.
    from openswing import modal_arnoldi
    calls = []
    def unavailable_left(a, m, value, right):
        calls.append((complex(value),np.asarray(right).copy()))
        return None, dict(status='FAIL',reason='singular_factor',
                          factorizations=1,linear_solves=0)
    monkeypatch.setattr(modal_arnoldi,'inverse_left',unavailable_left)
    a, m = _constrained_masses()
    modes, report = eigensystem(a, m, count=2, shift=(-.12,0.),
                               method='full_shift_invert')
    _match(_roots(modes),np.roots([5.,1.2,28.]))
    _paper_metadata(report,8,2)
    _original_equations(a,m,modes)
    assert len(calls)==2
    for mode,(value,right) in zip(modes,calls):
        assert complex(*mode['eigenvalue'])==value
        np.testing.assert_array_equal(mode['right'],right)
    assert report['left_recovery_counts']['inverse_iteration_failed']==2
    assert report['left_recovery_counts']['schur_pencils']==1
    assert all(x['reason']=='singular_factor' for x in report['inverse_iteration'])


def test_checked_conjugate_adjoint_preserves_constrained_transfer_and_saves_a_factor(monkeypatch):
    from openswing import modal_arnoldi
    a,m=_constrained_masses()
    original=modal_arnoldi.splu;calls=[]
    def counted(*args,**kwargs):
        calls.append(1)
        return original(*args,**kwargs)
    monkeypatch.setattr(modal_arnoldi,'splu',counted)
    modes,report=eigensystem(a,m,count=2,shift=(-.12,0.),method='full_shift_invert')
    assert len(calls)==2  # One Arnoldi factor and one adjoint factor.
    assert report['left_recovery_counts']['inverse_iteration']==1
    assert report['left_recovery_counts']['conjugate_reuse']==1
    assert report['left_recovery_counts']['conjugate_rejected']==0
    reused=[r for r in report['inverse_iteration'] if r['factorizations']==0]
    assert len(reused)==1 and reused[0]['status']=='PASS'
    assert reused[0]['left_backward_error']<=1e-10 and reused[0]['mass_pairing_error']<=1e-10
    _original_equations(a,m,modes)
    # Original reaction-constrained two-mass transfer, independently reduced
    # by adding its two physical force equations.
    b=np.zeros(len(a));b[2]=1.
    for s in [.3+2j,.1+5j,3j]:
        actual=sum(mode['right'][0]*np.vdot(mode['left'],b)/(s-complex(*mode['eigenvalue'])) for mode in modes)
        assert actual==pytest.approx(1/(5*s*s+1.2*s+28),rel=2e-10,abs=2e-12)


def test_rejected_conjugate_candidate_returns_to_original_inverse_iteration(monkeypatch):
    from openswing import modal_arnoldi
    a,m=_constrained_masses()
    expected,_=eigensystem(a,m,count=2,shift=(-.12,0.),method='full_shift_invert')
    original=modal_arnoldi.conjugate_left;checks=[]
    def wrong_basis(a,m,value,right,previous,basis):
        wrong=np.zeros_like(basis);wrong[-1]=1.
        result,record=original(a,m,value,right,previous,wrong)
        assert result is None and record['status']=='FAIL'
        checks.append(record)
        return result,record
    monkeypatch.setattr(modal_arnoldi,'conjugate_left',wrong_basis)
    actual,report=eigensystem(a,m,count=2,shift=(-.12,0.),method='full_shift_invert')
    assert len(checks)==1
    assert report['left_recovery_counts']['conjugate_reuse']==0
    assert report['left_recovery_counts']['conjugate_rejected']==1
    assert report['left_recovery_counts']['inverse_iteration']==2
    assert report['left_recovery_counts']['schur_pencils']==0
    np.testing.assert_array_equal(_roots(actual),_roots(expected))
    for before,after in zip(expected,actual):
        np.testing.assert_array_equal(before['right'],after['right'])
        np.testing.assert_allclose(before['left'],after['left'],rtol=2e-10,atol=2e-10)
    _original_equations(a,m,actual)


def test_complex_pencil_does_not_assume_conjugate_adjoint_symmetry():
    a,m=_constrained_masses()
    chart=np.array([1+2j,2-1j,.5+1j,3-2j,1j,1,1,1])
    a=a*chart[None,:]/chart[:,None];m=m*chart[None,:]/chart[:,None]
    modes,report=eigensystem(a,m,count=2,shift=(-.12,0.),method='full_shift_invert')
    _match(_roots(modes),np.roots([5.,1.2,28.]))
    _original_equations(a,m,modes)
    assert report['left_recovery_counts']['conjugate_reuse']==0
    assert report['left_recovery_counts']['inverse_iteration']==2


def test_repeated_complex_pairs_keep_complete_left_eigenspaces():
    oscillator=np.array([[-.2,-3.],[3.,-.2]])
    a=block_diag(oscillator,oscillator,-np.diag([20.,30.,40.]))
    m=np.eye(len(a))
    modes,report=eigensystem(a,m,count=4,shift=(-.1,0.),method='full_shift_invert')
    _match(_roots(modes),[-.2+3j,-.2-3j,-.2+3j,-.2-3j])
    _original_equations(a,m,modes)
    assert report['left_recovery_counts']['conjugate_reuse']==0
    assert report['left_recovery_counts']['inverse_iteration']==0
    assert report['left_recovery_counts']['repeated_pole_fallback']==4
    assert report['biorthogonality']['verified']


def test_singular_shift_and_excess_arnoldi_request_fail_explicitly():
    a, m = -np.diag(np.arange(1., 9.)), np.eye(8)
    with pytest.raises(ValueError, match='shift'):
        eigensystem(a, m, count=2, shift=(-4., 0.), method='full_shift_invert')
    with pytest.raises(ValueError, match='count'):
        eigensystem(a, m, count=7, shift=(-4.1, .1), method='full_shift_invert')
