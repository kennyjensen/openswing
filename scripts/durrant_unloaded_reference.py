"""Unloaded Durrant wing: independent Rayleigh beam and planar horseshoes.

Only NumPy/SciPy and the transcribed material table are used. There are no
OpenSwing geometry, beam, load, circulation, linearization or modal imports.
Physical coordinates are SI; positive h is section-normal, phi is span twist.
The small-motion reference has zero incidence, camber, Cm and gravity.
"""
import json
from pathlib import Path

import numpy as np
from scipy.linalg import eigh, eig

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT/'docs/validation/durrant-reference.json'

# Explicit diagnostic discretizations; no material or physical-model fitting.
SAMPLING = {
    'arithmetic_integrated': dict(collocation='arithmetic', circulation='integrated', fluid='integrated'),
    'glauert_cp': dict(collocation='glauert', circulation='integrated', fluid='integrated'),
    'glauert_circulation': dict(collocation='glauert', circulation='glauert', fluid='integrated'),
    'glauert_all': dict(collocation='glauert', circulation='glauert', fluid='glauert'),
}
EIGENSYSTEM_SCALINGS = ('unscaled', 'energy_convective')


def sampling_options(name):
    if name not in SAMPLING:
        raise ValueError('Unknown aerodynamic sampling: '+str(name))
    return SAMPLING[name]


def collocation_points(edges, sampling):
    if sampling_options(sampling)['collocation'] == 'arithmetic':
        return (edges[:-1]+edges[1:])/2
    # ASWING steady equations63,151-154: the angle is global to the beam;
    # it is not reset at material interfaces. Coordinates are independently
    # derived from reference-grid edges, never read from production.
    span = edges[-1]-edges[0]
    center = (edges[0]+edges[-1])/2
    theta = np.arccos(np.clip(2*(edges-center)/span, -1., 1.))
    return center+span/2*np.cos((theta[:-1]+theta[1:])/2)


def properties(wing):
    source = json.loads(REFERENCE.read_text())
    return source['common'], source['wings'][str(wing)]['tables']


def grid(count, common):
    """Uniform spacing plus exact material interfaces and the clamped root."""
    return np.unique(np.r_[np.linspace(0., common['length_m'], count+1),
                           np.cumsum(common['segment_lengths_m'])])


def fields(nodes, s):
    """Cubic Hermite bending / linear twist interpolation, clamped at s=0.

    Five nodal coordinates are [w_c, w_c', h, h', phi], with translations of
    the elastic axis in c,n and twist about s. Cta=Nta=0 gives zero reference
    axis axial displacement, as opposed to zero elastic-axis axial motion.
    """
    j = min(max(np.searchsorted(nodes, s, side='right')-1, 0), len(nodes)-2)
    length = nodes[j+1]-nodes[j]
    xi = (s-nodes[j])/length
    h = np.array([1-3*xi**2+2*xi**3, length*(xi-2*xi**2+xi**3),
                  3*xi**2-2*xi**3, length*(-xi**2+xi**3)])
    d = np.array([(-6*xi+6*xi**2)/length, 1-4*xi+3*xi**2,
                  (6*xi-6*xi**2)/length, -2*xi+3*xi**2])
    b = np.array([(-6+12*xi)/length**2, (-4+6*xi)/length,
                  (6-12*xi)/length**2, (-2+6*xi)/length])
    out = np.zeros((8, 5*len(nodes)))
    ci = 5*j+np.array([0, 1, 5, 6])
    ni = 5*j+np.array([2, 3, 7, 8])
    out[0, ci], out[1, ci], out[2, ci] = h, d, b
    out[3, ni], out[4, ni], out[5, ni] = h, d, b
    out[6, [5*j+4, 5*j+9]] = [1-xi, xi]
    out[7, [5*j+4, 5*j+9]] = [-1/length, 1/length]
    return out[:, 5:]


def mechanics(wing, elements=24, density=1.225, material=None, *,
              sampling='arithmetic_integrated', panels=None):
    options = sampling_options(sampling)
    common, table = properties(wing)
    if material is not None:
        table = material
    nodes = grid(elements, common)
    dimension = 5*(len(nodes)-1)
    K, M, Ma, D = [np.zeros((dimension, dimension)) for _ in range(4)]
    cea, nea = table['Cea_m'], table['Nea_m']
    EIcc, EInn, EIcn, GJ = table['stiffness']
    chord = common['chord_m']
    ma = density*np.pi*chord**2/4
    # d: elastic axis to midchord in the positive chord direction.
    d = (.5-table['Xax'])*chord-cea
    boundaries = np.r_[0., np.cumsum(common['segment_lengths_m'])]
    xg, wg = np.polynomial.legendre.leggauss(6)
    for left, right in zip(nodes[:-1], nodes[1:]):
        k = min(np.searchsorted(boundaries, (left+right)/2, side='right')-1, 2)
        mass, ccg, ncg, icc, inn = np.array(table['inertia'][k])/[common['gravity_m_s2'], 1, 1, common['gravity_m_s2'], common['gravity_m_s2']]
        for s, weight in zip((left+right)/2+xg*(right-left)/2, wg*(right-left)/2):
            wc, dc, bc, h, dh, bh, phi, dp = fields(nodes, s)
            translation = np.array([wc+(ncg-nea)*phi, -ccg*dc-ncg*dh,
                                    h+(cea-ccg)*phi])
            rotation = np.array([dh, phi, -dc])
            M += weight*(mass*translation.T@translation+
                         rotation.T@np.diag([icc, icc+inn, inn])@rotation)
            K += weight*(EIcc*np.outer(bh, bh)+EInn*np.outer(bc, bc)
                         -EIcn*(np.outer(bh, bc)+np.outer(bc, bh))+GJ*np.outer(dp, dp))
            if options['fluid'] == 'integrated':
                midchord = h-d*phi
                Ma += weight*ma*(np.outer(midchord, midchord)+chord**2/32*np.outer(phi, phi))
                # Apparent-mass pitch-rate force/moment; multiply by speed U.
                D += weight*ma*np.outer(h-(d+chord/4)*phi, phi)
    if options['fluid'] == 'glauert':
        edges = grid(elements if panels is None else panels, common)
        for s, weight in zip(collocation_points(edges, sampling), np.diff(edges)):
            f = fields(nodes, s)
            h, phi = f[3], f[6]
            midchord = h-d*phi
            Ma += weight*ma*(np.outer(midchord, midchord)+chord**2/32*np.outer(phi, phi))
            D += weight*ma*np.outer(h-(d+chord/4)*phi, phi)
    return dict(nodes=nodes, K=K, M=M, Ma=Ma, D_per_speed=D,
                common=common, table=table)


def horseshoe_influence(edges, chord, sampling='arithmetic_integrated'):
    """Closed Biot-Savart integrals at 3/4 chord for quarter-chord horseshoes.

    Positive circulation produces positive section-normal lift and negative
    section-normal self-induced velocity. Wake legs extend to +infinity in x.
    No regularizing core, image surface, lifting-line approximation or library
    vortex routine is used. The independent beam is a single unsymmetrized wing.
    """
    point = collocation_points(edges, sampling)
    dx = chord/2
    da, db = point[:, None]-edges[:-1], point[:, None]-edges[1:]
    ra, rb = np.sqrt(dx*dx+da*da), np.sqrt(dx*dx+db*db)
    bound = -(da/ra-db/rb)/(4*np.pi*dx)
    wake = ((1+dx/rb)/db-(1+dx/ra)/da)/(4*np.pi)
    return bound+wake


def aerodynamics(beam, panels, sampling='arithmetic_integrated'):
    common, table, nodes = beam['common'], beam['table'], beam['nodes']
    chord = common['chord_m']
    edges = grid(panels, common)
    points = collocation_points(edges, sampling)
    nq = beam['K'].shape[0]
    H, P = np.zeros((2, len(points), nq))
    for i, s in enumerate(points):
        f = fields(nodes, s)
        H[i], P[i] = f[3], f[6]
    # Virtual work: force acts at quarter chord. Integrate FE shape over each
    # constant-circulation panel exactly, splitting at mechanical interfaces.
    arm = (.25-table['Xax'])*chord-table['Cea_m']
    if sampling_options(sampling)['circulation'] == 'integrated':
        L = np.zeros((nq, len(points)))
        xg, wg = np.polynomial.legendre.leggauss(3)
        for i, (a, b) in enumerate(zip(edges[:-1], edges[1:])):
            cuts = np.r_[a, nodes[(nodes>a)&(nodes<b)], b]
            for left, right in zip(cuts[:-1], cuts[1:]):
                for s, weight in zip((left+right)/2+xg*(right-left)/2, wg*(right-left)/2):
                    f = fields(nodes, s)
                    L[:, i] += weight*(f[3]-arm*f[6])
    else:
        L = (H-arm*P).T*np.diff(edges)[None, :]
    d3 = (.75-table['Xax'])*chord-table['Cea_m']
    return dict(edges=edges, W=horseshoe_influence(edges, chord, sampling),
                P=P, V=-H+d3*P, L=L)


def modal_pencil(beam, aero, basis, values, speed, density, lag):
    """Original mass-normalized physical pencil before numerical scaling."""
    Gq, Gv, L = speed*aero['P']@basis, aero['V']@basis, basis.T@aero['L']
    D = speed*basis.T@beam['D_per_speed']@basis
    W = aero['W']
    nq, ng = len(values), len(W)
    chord = beam['common']['chord_m']
    if lag:
        A, B = [np.zeros((2*nq+ng, 2*nq+ng)) for _ in range(2)]
        B[:nq, :nq] = np.eye(nq)
        A[:nq, nq:2*nq] = np.eye(nq)
        B[nq:2*nq, nq:2*nq] = np.eye(nq)
        B[nq:2*nq, 2*nq:] = -density*chord*L
        A[nq:2*nq, :nq] = -np.diag(values)
        A[nq:2*nq, nq:2*nq] = D
        A[nq:2*nq, 2*nq:] = density*speed*L
        B[2*nq:, 2*nq:] = 2/(np.pi*speed)*np.eye(ng)
        A[2*nq:, :nq], A[2*nq:, nq:2*nq], A[2*nq:, 2*nq:] = Gq, Gv, W
    else:
        force_q = -density*speed*L@np.linalg.solve(W, Gq)
        force_v = -density*speed*L@np.linalg.solve(W, Gv)
        A = np.block([[np.zeros((nq,nq)), np.eye(nq)],
                      [-np.diag(values)+force_q, D+force_v]])
        B = np.eye(2*nq)
    return A, B


def eigensystem_coordinates(values, speed, chord, density, panel_widths, *,
                           scaling='energy_convective'):
    """Return state/row/time scales for z=R*x, As=E*A*R/w0, Bs=E*B*R.

    z is the original [q,v,Gamma] state; x contains Omega*q, v, and
    sqrt(rho*ds)*Gamma. The last is a dimensional energy-like scale, not
    an assumed exact fluid energy. Empty panel_widths means lag is off.
    Every row is transformed in full; circulation-rate B couplings remain.
    The zero-speed still-air solution does not use this finite-speed pencil.
    """
    if scaling not in EIGENSYSTEM_SCALINGS:
        raise ValueError('Unknown eigensystem scaling: '+str(scaling))
    nq, ng = len(values), len(panel_widths)
    R, E = np.ones(2*nq+ng), np.ones(2*nq+ng)
    if scaling == 'unscaled':
        return R, E, 1.
    omega = np.sqrt(values)
    if not np.all(np.isfinite(omega) & (omega > 0)) or speed == 0 or chord <= 0:
        raise ValueError('Energy scaling requires positive mechanical frequencies and finite-speed geometry')
    R[:nq], E[:nq] = 1/omega, omega
    if ng:
        if np.any(np.asarray(panel_widths) <= 0):
            raise ValueError('Aerodynamic panel widths must be positive')
        # With zero density the circulation state still exists but has no
        # fluid-energy scale. Keeping its units is an invertible fallback.
        if density > 0:
            R[2*nq:] = 1/np.sqrt(density*np.asarray(panel_widths))
        tau = 2/(np.pi*speed)
        E[2*nq:] = 1/(tau*R[2*nq:])
    return R, E, abs(speed)/chord


def pencil_eigensystem(A, B, values, speed, chord, density, panel_widths, *,
                      scaling='energy_convective'):
    """Solve the same finite pencil with an explicit, reversible scaling.

    The unscaled choice uses the historical SciPy call unchanged. The
    default recovers original coordinates before any physical output or
    original-pencil residual is computed. No rank reduction is performed.
    """
    R, E, w0 = eigensystem_coordinates(values, speed, chord, density, panel_widths, scaling=scaling)
    if A.shape != B.shape or A.shape != (len(R), len(R)):
        raise ValueError('Pencil dimensions do not match the retained mechanical/aerodynamic states')
    if scaling == 'unscaled':
        roots, vectors = eig(A, B)
        return roots, vectors, dict(scaling=scaling, frequency_scale_per_s=1.,
            coordinates='Historical unscaled mass-normalized displacement/velocity pencil.')
    As, Bs = E[:, None]*A*R[None, :]/w0, E[:, None]*B*R[None, :]
    mu, left, right = eig(As, Bs, left=True, right=True)
    normA, normB = np.linalg.norm(As, 2), np.linalg.norm(Bs, 2)
    scale = normA+abs(mu)*normB
    right_error = np.linalg.norm(As@right-(Bs@right)*mu, axis=0)/(scale*np.linalg.norm(right, axis=0))
    left_error = np.linalg.norm(As.T@left-(Bs.T@left)*mu.conj(), axis=0)/(scale*np.linalg.norm(left, axis=0))
    sensitivity = (w0*scale*np.linalg.norm(left, axis=0)*np.linalg.norm(right, axis=0)
                   /abs(np.sum(left.conj()*(Bs@right), axis=0)))
    diagnostics = dict(scaling=scaling, frequency_scale_per_s=float(w0),
        state_scale=R.tolist(), equation_scale=E.tolist(),
        scaled_A_norm_2=float(normA), scaled_B_norm_2=float(normB),
        maximum_scaled_right_backward_error=float(np.max(right_error)),
        maximum_scaled_left_backward_error=float(np.max(left_error)),
        epsilon_times_absolute_sensitivity_per_s=(np.finfo(float).eps*sensitivity).tolist(),
        sensitivity_note='First-order normwise indicator, not a rigorous error bound.',
        coordinates='Original z=R*x; As=E*A*R/w0, Bs=E*B*R; physical lambda=w0*mu.')
    return mu*w0, R[:, None]*right, diagnostics


def solve(wing, speed, *, elements=24, panels=16, density=1.225, lag=True,
          retain=24, shapes=False, sampling='arithmetic_integrated',
          eigensystem_scaling='energy_convective'):
    sampling_options(sampling)
    if eigensystem_scaling not in EIGENSYSTEM_SCALINGS:
        raise ValueError('Unknown eigensystem scaling: '+str(eigensystem_scaling))
    beam = mechanics(wing, elements=elements, density=density, sampling=sampling, panels=panels)
    wet = beam['M']+beam['Ma']
    values, basis = eigh(beam['K'], wet)
    if values.min() <= 0:
        raise ValueError('Independent energy model has nonpositive stiffness')
    take = len(values) if retain == 0 else min(retain, len(values))
    basis, values = basis[:, :take], values[:take]
    if speed == 0:
        # The still-air added-mass limit: do not divide by U or invent a
        # stagnation closure for circulation. This is its own physical limit.
        roots = 1j*np.sqrt(values)
        vectors = basis.astype(complex)
        error = np.zeros(take)
        dimension = take
        eigensystem = dict(scaling='still_air_analytic', requested_scaling=eigensystem_scaling,
                           frequency_scale_per_s=1., coordinates='Unchanged positive still-air wet frequencies.')
    else:
        aero = aerodynamics(beam, panels, sampling)
        A, B = modal_pencil(beam, aero, basis, values, speed, density, lag)
        roots, v, eigensystem = pencil_eigensystem(A, B, values, speed,
            beam['common']['chord_m'], density, np.diff(aero['edges']) if lag else [],
            scaling=eigensystem_scaling)
        nq = take
        dimension = len(roots)
        residual = A@v-(B@v)*roots
        denom = (np.linalg.norm(A,2)+np.abs(roots)*np.linalg.norm(B,2))*np.linalg.norm(v,axis=0)
        error = np.linalg.norm(residual,axis=0)/denom
        vectors = basis@v[:nq]
    selected = np.where(roots.imag > 1e-6)[0]
    selected = selected[np.argsort(roots[selected].imag)]
    result = dict(wing=str(wing), speed_m_s=speed, sampling=sampling, sampling_options=sampling_options(sampling),
                  requested_elements=elements,
                  actual_elements=len(beam['nodes'])-1, requested_panels=panels,
                  actual_panels=len(grid(panels, beam['common']))-1,
                  retained_mechanical_modes=take, density_kg_m3=density, lag=lag,
                  computed_dimension=dimension, maximum_backward_error=float(np.max(error)),
                  eigensystem=eigensystem,
                  roots_per_s=np.c_[roots.real, roots.imag].tolist(),
                  positive_roots_per_s=np.c_[roots[selected].real, roots[selected].imag].tolist(),
                  positive_frequencies_Hz=(roots[selected].imag/(2*np.pi)).tolist(),
                  minimum_energy_eigenvalue=float(values.min()))
    if shapes:
        # Output-only refinement: sample the union of mechanical and aerodynamic nodes.
        span = np.unique(np.r_[beam['nodes'], grid(panels, beam['common'])])
        rows = []
        cea, nea = beam['table']['Cea_m'], beam['table']['Nea_m']
        for j in selected:
            v = vectors[:, j]
            out = []
            for s in span:
                wc, dc, _, h, dh, _, phi, _ = fields(beam['nodes'], s)@v
                out.append([wc-nea*phi, -h-cea*phi, 0., dh, dc, phi])
            out = np.asarray(out)
            out /= np.linalg.norm(out)
            rows.append(dict(real=out.real.tolist(), imag=out.imag.tolist()))
        result.update(span_m=span.tolist(), positive_shapes=rows)
    return result


def checks():
    """Independent analytic mechanics and horseshoe asymptotes; no native runs."""
    common, original = properties('25')
    material = dict(original, Cea_m=0., Nea_m=0.,
                    inertia=[[.1*common['gravity_m_s2'], 0., 0.,
                              2e-5*common['gravity_m_s2'], 3e-5*common['gravity_m_s2']]]*3)
    exact = np.arange(1, 6, 2)/(4*common['length_m'])*np.sqrt(material['stiffness'][3]/5e-5)
    torsion = []
    for n in (24, 48):
        beam = mechanics('25', elements=n, density=0., material=material)
        ids = np.arange(4, len(beam['K']), 5)
        w = eigh(beam['K'][np.ix_(ids,ids)], beam['M'][np.ix_(ids,ids)], eigvals_only=True)
        f = np.sqrt(w[:3])/(2*np.pi)
        e = abs(f/exact-1)
        torsion.append(e.tolist())
    assert max(torsion[-1]) < .002
    assert np.all(np.array(torsion[1]) < .3*np.array(torsion[0]))
    chord = common['chord_m']
    w = horseshoe_influence(np.array([-1e6,1e6]), chord)[0,0]
    influence_error = abs(w/(-1/(np.pi*chord))-1)
    assert influence_error < 1e-7
    # The 2D prescribed-heave transfer recovers ASWING's own rational lag,
    # rather than imposing exact Theodorsen aerodynamics on this reference.
    U = 30.
    omega = np.array([0., 1., 30., 300., 3e5])
    transfer = (U+1j*omega*chord)/(-w+2j*omega/(np.pi*U))
    expected = np.pi*chord*U*(1+1j*omega*chord/U)/(1+2j*omega*chord/U)
    lag_error = np.max(abs(transfer/expected-1))
    assert lag_error < 1e-7
    return dict(analytic_torsion_Hz=exact.tolist(), torsion_relative_errors=torsion,
                infinite_span_self_influence_relative_error=float(influence_error),
                prescribed_heave_lag_relative_error=float(lag_error))

