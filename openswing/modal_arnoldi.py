"""Full-pencil modal iteration, ASWING unsteady theory §13.3.1.

ARPACK sees the standard operator H=(A-mu M)^-1 M. Its generalized
B=M mode requires a Hermitian semidefinite metric, which an arbitrary
descriptor derivative matrix does not provide. No mass-rank reduction is
needed. See docs/validation/aswing-modal-method.md and third_party/arpack.
"""
import numpy as np
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import LinearOperator, eigs, splu, norm, ArpackNoConvergence

from .aero import AnalysisError


def shifted_modes(a, m, shift, count):
    """Eqs. 147–149: factor once, Arnoldi on H, transform eigenvalues once."""
    a, m = csc_matrix(a), csc_matrix(m)
    n = a.shape[0]
    if count >= n-1:
        raise AnalysisError('Full descriptor Arnoldi requires count below the pencil dimension minus one; reduce count or use the dense reduction.')
    matrix = (a-complex(shift)*m).tocsc()
    try:
        factor = splu(matrix)
    except RuntimeError as exc:
        raise AnalysisError('Mode shift is on a pole or the descriptor pencil is singular; choose a different shift (nonzero for rigid-body zero modes).') from exc
    matrix_norm = norm(matrix)
    settings = dict(factorizations=1, operator_applications=0,
        maximum_solve_backward_error=0., solve_backward_gate=1e-10,
        retained_dimension=n, arpack_mode=1, bmat='I', which='LM',
        tolerance=1e-11, subspace_dimension=min(n, max(2*count+1, 20)),
        maximum_iterations=max(500, 30*n), starting_vector='deterministic linspace(1,2)',
        factorization='sparse complex LU', mass_rank_reduction=False)

    def apply(vector):
        rhs = m@vector
        result = factor.solve(rhs)
        settings['operator_applications'] += 1
        denominator = matrix_norm*np.linalg.norm(result)+np.linalg.norm(rhs)
        backward = np.linalg.norm(matrix@result-rhs)/max(denominator, np.finfo(float).tiny)
        if not np.all(np.isfinite(result)) or not np.isfinite(backward) or backward > settings['solve_backward_gate']:
            raise AnalysisError('The shifted modal linear solve fails its original-matrix residual check; inspect the shift and scaling.')
        settings['maximum_solve_backward_error'] = max(settings['maximum_solve_backward_error'], float(backward))
        return result

    operator = LinearOperator(a.shape, matvec=apply, dtype=complex)
    try:
        inverse, vectors = eigs(operator, k=count, which=settings['which'],
            tol=settings['tolerance'], ncv=settings['subspace_dimension'],
            maxiter=settings['maximum_iterations'], v0=np.linspace(1., 2., n).astype(complex))
    except ArpackNoConvergence as exc:
        raise AnalysisError('Shift-and-invert modes did not converge; change shift/count or use the dense solve.') from exc
    if (not np.all(np.isfinite(inverse)) or
            np.any(abs(inverse) <= 100*np.finfo(float).eps*max(np.max(abs(inverse)), 1.))):
        raise AnalysisError('The Arnoldi search includes unresolved infinite or very distant roots; reduce count or move the shift.')
    values = shift+1/inverse
    order = np.argsort(abs(values-shift), kind='stable')
    return values[order], vectors[:, order], settings


def inverse_left(a, m, value, right, *, max_iterations=12):
    """Eqs. 150–152, with one LU per supplied pole and explicit failure.

The caller retains an original-pencil fallback for an exactly singular
factor or an unresolved mass pairing. A single-vector iteration cannot
establish a dual basis for repeated poles.
    """
    a, m = csc_matrix(a), csc_matrix(m)
    v = np.asarray(right, dtype=complex)
    n = len(v)
    report = dict(status='FAIL', reason=None, factorizations=0, linear_solves=0,
        iterations=0, left_backward_error=None, mass_pairing_error=None,
        backward_gate=1e-10, pairing_gate=1e-10,
        normalization='Divide by conjugate(wprime^H M v), enforcing Eq152.')

    def fail(reason):
        report['reason'] = reason
        return None, report

    pencil_norm = norm(a)+abs(value)*norm(m)
    mv = m@v
    mvnorm = np.linalg.norm(mv)
    if not pencil_norm or not np.linalg.norm(v) or not mvnorm:
        return fail('zero_right_vector_or_mass_pairing')
    right_error = np.linalg.norm(a@v-value*mv)/(pencil_norm*np.linalg.norm(v))
    if not np.isfinite(right_error) or right_error > report['backward_gate']:
        return fail('right_vector_fails_original_pencil')
    adjoint_a, adjoint_m = a.conj().T.tocsc(), m.conj().T.tocsc()
    report['factorizations'] = 1
    try:
        factor = splu((adjoint_a-np.conj(value)*adjoint_m).tocsc())
    except RuntimeError:
        return fail('singular_factor')
    # Deterministic, nonzero complex starting vector; no seed search.
    w = (1.+np.arange(n)/n)+1j*(.5+np.arange(n, 0, -1)/n)
    w /= np.linalg.norm(w)
    for iteration in range(1, max_iterations+1):
        trial = factor.solve(adjoint_m@w)
        report['linear_solves'] += 1
        if not np.all(np.isfinite(trial)):
            return fail('nonfinite_iterate')
        pairing = np.vdot(trial, mv)
        scale = np.linalg.norm(trial)*mvnorm
        if not np.isfinite(scale) or not scale or abs(pairing) <= 100*np.finfo(float).eps*scale:
            return fail('unresolved_mass_pairing')
        # The conjugate makes the printed Eq152 invariant hold for arbitrary
        # complex phase; literal division by pairing in Eq151 would not.
        w = trial/np.conj(pairing)
        if not np.all(np.isfinite(w)):
            return fail('nonfinite_normalized_iterate')
        backward = np.linalg.norm(adjoint_a@w-np.conj(value)*(adjoint_m@w))/(pencil_norm*np.linalg.norm(w))
        mass_error = abs(np.vdot(w, mv)-1.)
        report.update(iterations=iteration, left_backward_error=float(backward), mass_pairing_error=float(mass_error))
        if np.isfinite(backward) and backward <= report['backward_gate'] and mass_error <= report['pairing_gate']:
            report.update(status='PASS', reason='original_left_residual_and_mass_pairing')
            return w, report
    return fail('iteration_limit')


def conjugate_left(a, m, value, right, previous, basis):
    """Check a real pencil's conjugate adjoint against this actual Ritz pair.

    This uses conjugation symmetry, not a merged or rounded eigenvalue. The
    actual current pole and right vector must satisfy the same residual and
    Eq152 gates as inverse iteration. The caller excludes repeated poles.
    """
    a, m = csc_matrix(a), csc_matrix(m)
    report = dict(status='FAIL', reason=None, factorizations=0, linear_solves=0,
        iterations=0, left_backward_error=None, mass_pairing_error=None,
        backward_gate=1e-10, pairing_gate=1e-10,
        normalization='Checked conjugate adjoint, normalized to w^H M v = 1.')

    def fail(reason):
        report['reason'] = reason
        return None, report

    if not np.isrealobj(a.data) or not np.isrealobj(m.data):
        return fail('complex_pencil')
    if (previous.imag*value.imag >= 0 or
            abs(previous.conjugate()-value) > 1e-12*max(1.,abs(value))):
        return fail('not_a_conjugate_candidate')
    v = np.asarray(right,dtype=complex)
    w = np.asarray(basis,dtype=complex).conj().reshape(-1)
    mv = m@v
    pencil_norm = norm(a)+abs(value)*norm(m)
    vn,wn,mvn = np.linalg.norm(v),np.linalg.norm(w),np.linalg.norm(mv)
    if not pencil_norm or not vn or not wn or not mvn:
        return fail('zero_vector_or_mass_pairing')
    right_error = np.linalg.norm(a@v-value*mv)/(pencil_norm*vn)
    if not np.isfinite(right_error) or right_error > report['backward_gate']:
        return fail('right_vector_fails_original_pencil')
    pairing = np.vdot(w,mv)
    if not np.isfinite(pairing) or abs(pairing) <= 100*np.finfo(float).eps*wn*mvn:
        return fail('unresolved_mass_pairing')
    w = w/np.conj(pairing)
    if not np.all(np.isfinite(w)):
        return fail('nonfinite_normalized_vector')
    backward = np.linalg.norm(a.conj().T@w-np.conj(value)*(m.conj().T@w))/(pencil_norm*np.linalg.norm(w))
    mass_error = abs(np.vdot(w,mv)-1.)
    report.update(left_backward_error=float(backward),mass_pairing_error=float(mass_error))
    if (not np.isfinite(backward) or backward > report['backward_gate']
            or not np.isfinite(mass_error) or mass_error > report['pairing_gate']):
        return fail('conjugate_fails_original_equations_or_pairing')
    report.update(status='PASS',reason='checked_conjugate_original_equations_and_mass_pairing')
    return w,report


def selected_clusters(values):
    """Candidate pairing groups in physical eigenvalue units, not a root merge."""
    values = np.asarray(values, dtype=complex)
    remaining = set(range(len(values)))
    clusters = []
    while remaining:
        first = min(remaining)
        indices = sorted(i for i in remaining if abs(values[i]-values[first]) < 1e-7*max(1., abs(values[first])))
        remaining.difference_update(indices)
        clusters.append(indices)
    return clusters


def pair_selected_modes(modes, left_bases, a, m):
    """Enforce Eq152 in resolved repeated eigenspaces; measure every pairing.

For a selected right basis V and original left eigenspace U, W=U(G^+)^H,
G=U^H M V. This changes no right vector or eigenvalue. Close distinct poles
are never accepted as one eigenspace merely because they share a cluster:
each proposed left vector must satisfy its own original-pencil equation.
    """
    # These products involve only the selected vectors. Keep the original
    # physical matrices sparse so a real/complex multiplication cannot copy
    # the entire pencil to complex storage merely to check mass pairings.
    a, m = csc_matrix(a), csc_matrix(m)
    values = np.array([complex(*mode['eigenvalue']) for mode in modes])
    clusters = []
    anorm, mnorm = norm(a), norm(m)
    for indices in selected_clusters(values):
        if len(indices) == 1:
            continue
        v = np.column_stack([modes[i]['right'] for i in indices])
        # Each close pole can have its own one-dimensional left eigenspace.
        # Retain their complete union; using only the first pole's basis
        # would falsely reject distinct, individually resolved neighbours.
        u = np.column_stack([left_bases[i] for i in indices])
        g = u.conj().T@(m@v)
        left, singular, right = np.linalg.svd(g, full_matrices=False)
        rank_floor = 100*np.finfo(float).eps*max(g.shape)*(singular[0] if len(singular) else 0.)
        report = dict(indices=indices, status='UNRESOLVED', reason='singular_mass_pairing')
        if len(singular) == len(indices) and singular[-1] > rank_floor:
            w = u@((left/singular)@right)
            defects = [np.linalg.norm(a.conj().T@w[:,j]-values[i].conjugate()*(m.conj().T@w[:,j]))/
                max((anorm+abs(values[i])*mnorm)*np.linalg.norm(w[:,j]), np.finfo(float).tiny)
                for j,i in enumerate(indices)]
            pairing_error = np.max(abs(w.conj().T@(m@v)-np.eye(len(indices))))
            if np.all(np.isfinite(defects)) and max(defects) <= 1e-10 and pairing_error <= 1e-8:
                for j,i in enumerate(indices):
                    modes[i]['left'] = w[:,j]
                    modes[i]['biorthogonal_normalized'] = True
                    # This is checked in the original physical pencil.
                    modes[i]['left_backward_error'] = float(defects[j])
                    av, mv = w[:,j].conj()@a, w[:,j].conj()@m
                    modes[i]['left_relative_residual'] = float(np.linalg.norm(av-values[i]*mv)/
                        max(np.linalg.norm(av)+abs(values[i])*np.linalg.norm(mv), np.finfo(float).tiny))
                report.update(status='PASS', reason='original_left_equations_and_block_mass_pairing',
                    maximum_left_backward_error=float(max(defects)), maximum_pairing_error=float(pairing_error))
            else:
                report['reason'] = 'mixed_basis_fails_original_equations_or_pairing'
        if report['status'] != 'PASS':
            for i in indices:modes[i]['biorthogonal_normalized'] = False
        clusters.append(report)
    v = np.column_stack([mode['right'] for mode in modes])
    w = np.column_stack([mode['left'] for mode in modes])
    error = abs(w.conj().T@(m@v)-np.eye(len(modes)))
    diagonal = float(np.max(np.diag(error)))
    off_diagonal = float(np.max(error-np.diag(np.diag(error))))
    return dict(scope='Returned vectors only; no complete-spectrum or generalized-chain claim.',
        diagonal_error=diagonal, off_diagonal_error=off_diagonal, gate=1e-8,
        verified=bool(np.max(error) <= 1e-8 and all(mode['biorthogonal_normalized'] for mode in modes)),
        repeated_clusters=clusters)
