"""Certify numerical real poles without changing or matching eigenvalues.

Complex shift-invert solves of a real descriptor can leave roundoff in a real
pole's imaginary component. Sign alone is therefore not a frequency selector.
This assessment uses no reference outputs: a near-real candidate also needs
phase-real left/right vectors and independently checked real-pencil equations.
The original roots, vectors and all native targets must remain in the report.
"""
from __future__ import annotations

import numpy as np
from scipy.sparse import issparse


def classify_modes(modes, a, m, *, shift, characteristic_rate):
    """Return one audit per input mode; ambiguous candidates stay unresolved.

    The candidate window is the existing stability.representatives real-pole
    convention, not an eigenvalue error estimate. Real projections must pass both
    action-relative pencil residuals at 1e-8 and a phase-reality gate at 1e-10.
    This does not authenticate native real-pole branch identities.
    """
    a, m = (v if issparse(v) else np.asarray(v) for v in (a,m))
    av,mv=(v.data if issparse(v) else v for v in (a,m))
    if (a.ndim != 2 or a.shape[0] != a.shape[1] or a.shape != m.shape
            or np.iscomplexobj(av) or np.iscomplexobj(mv)
            or not np.all(np.isfinite(av)) or not np.all(np.isfinite(mv))):
        raise ValueError('Real, finite, equally sized square pencil matrices are required.')
    shift = complex(*shift)
    if not np.isfinite(shift) or not np.isfinite(characteristic_rate) or characteristic_rate <= 0:
        raise ValueError('Finite shift and positive characteristic rate are required.')
    audits = []
    for index, mode in enumerate(modes):
        root = complex(*mode['eigenvalue'])
        if not np.isfinite(root):
            raise ValueError('Finite eigenvalues are required.')
        # Keep the existing production tracking convention; it is only a
        # prerequisite. The extra vector and full-pencil certificates below
        # prevent this display/selection threshold from hiding real dynamics.
        window = 1e-9 * max(abs(root), characteristic_rate*1e-6)
        audit = dict(mode_index=index, eigenvalue=list(mode['eigenvalue']),
                     imaginary_candidate_window=float(window),
                     classification='positive_frequency' if root.imag > 0 else 'negative_frequency')
        if abs(root.imag) <= window:
            audit['classification'] = 'unresolved_near_real'
            projections = []
            for side in ('right', 'left'):
                vector = np.asarray(mode[side]['real']) + 1j*np.asarray(mode[side]['imag'])
                if vector.shape != (a.shape[0],) or not np.all(np.isfinite(vector)):
                    raise ValueError('Complete finite left/right vectors are required.')
                norm = np.linalg.norm(vector)
                if not np.isfinite(norm) or norm == 0:
                    raise ValueError('Nonzero finite left/right vectors are required.')
                vector = vector/norm
                pivot = vector[np.argmax(abs(vector))]
                phased = vector * (pivot.conjugate()/abs(pivot))
                phase_defect = float(np.linalg.norm(phased.imag))
                real = phased.real
                av, mv = (a@real, m@real) if side == 'right' else (real@a, real@m)
                residual = np.linalg.norm(av-root.real*mv)
                denominator = np.linalg.norm(av)+abs(root.real)*np.linalg.norm(mv)
                relative = float(residual/max(denominator, np.finfo(float).tiny))
                audit[side] = dict(phase_defect=phase_defect, phase_gate=1e-10,
                                   real_pencil_relative_residual=relative, residual_gate=1e-8,
                                   passed=bool(phase_defect <= 1e-10 and relative <= 1e-8))
                projections.append(real)
            # A finite simple pole must have nonzero left/right mass pairing.
            pairing = float(abs(projections[1]@m@projections[0]))
            audit['projected_mass_pairing'] = pairing
            if (audit['right']['passed'] and audit['left']['passed']
                    and np.isfinite(pairing) and pairing > 0):
                audit['classification'] = 'certified_real'
        audits.append(audit)
    return audits
