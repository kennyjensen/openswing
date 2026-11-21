"""Continuous Fourier Trefftz reference integral for straight traces.

Steady equations 63 and 207–211 define the represented circulation and forces.
This is an explicit diagnostic, not a change to the discrete horseshoe outputs
or their derivatives. No pointwise Gamma interpolation is performed here.
"""
import math
from functools import lru_cache
import numpy as np
from numpy.polynomial.legendre import leggauss


@lru_cache(maxsize=7)
def _gauss(order):
    x, w = leggauss(order)
    x.setflags(write=False)
    w.setflags(write=False)
    return x, w


def _velocity(from_start, from_end, source):
    # Complex coordinates are side + i*lift in the common wind-normal plane.
    # Retain the signed side of the source sheet: tangential velocity jumps
    # across it and contributes to drag on a nonparallel receiving trace.
    divisor = source['direction']*source['half_span']
    minus, plus = from_end/divisor, from_start/divisor
    z = .5*(minus+plus)
    root = np.sqrt(minus)*np.sqrt(plus)
    ratio = 1/(z+root)
    n = np.arange(1, len(source['coefficients'])+1)
    field = np.sum(n*source['coefficients']*ratio[:, None]**n, axis=1)/root
    return 1j*source['direction']*np.conj(field)/(2*source['half_span'])


def _mutual(target, source, order):
    """Directed D/rho. Source integration is analytic; only target is sampled."""
    bounds = [0., math.pi]
    for edge in (source['start'], source['end']):
        projected = (edge-target['center'])/target['direction']
        for offset in (0., -1., 1., -4., 4., -16., 16.):
            eta = (projected.real+offset*abs(projected.imag))/target['half_span']
            if -1 < eta < 1:
                bounds.append(float(np.arccos(eta)))
    # Split the source-sheet crossing to integrate the two one-sided velocity
    # limits. A principal value at the crossing alone would omit its jump.
    origin = (target['center']-source['center'])/source['direction']
    slope = target['half_span']*target['direction']/source['direction']
    if slope.imag != 0:
        eta = -origin.imag/slope.imag
        if -1 < eta < 1 and abs((origin+slope*eta).real) < source['half_span']:
            bounds.append(float(np.arccos(eta)))
    bounds = sorted(set(bounds))
    x, w = _gauss(order)
    n = np.arange(1, len(target['coefficients'])+1)
    total = 0.
    for lo, hi in zip(bounds[:-1], bounds[1:]):
        # Endpoint smoothing also handles a coplanar source tip lying inside
        # this trace: velocity has an integrable inverse-square-root singularity.
        t = (x+1)*math.pi/2
        theta = lo+(hi-lo)*(1-np.cos(t))/2
        jacobian = (hi-lo)*np.sin(t)*math.pi/4
        gamma = np.sin(theta[:, None]*n)@target['coefficients']
        # Preserve sub-ulp distances to a shared endpoint. Forming the point
        # as center + a*cos(theta) would round it onto the singular tip.
        end_offset = -2*target['half_span']*target['direction']*np.sin(theta/2)**2
        start_offset = 2*target['half_span']*target['direction']*np.cos(theta/2)**2
        near_end = theta < math.pi/2
        from_start = np.where(near_end, target['end']-source['start']+end_offset,
                              target['start']-source['start']+start_offset)
        from_end = np.where(near_end, target['end']-source['end']+end_offset,
                            target['start']-source['end']+start_offset)
        velocity = np.imag(_velocity(from_start, from_end, source)*np.conj(target['direction']))
        total -= target['half_span']/2*float(np.sum(w*jacobian*np.sin(theta)*gamma*velocity))
    return total


def _unavailable(reason):
    return dict(available=False, reason=reason, CLi=None, CYi=None, CDi=None,
                efficiency=None, convention='Continuous Fourier Trefftz reference integral.')


def fourier_wake_forces(traces, wind, side, lift, speed, density, reference,
                        *, relative_tolerance=2e-10, max_order=256):
    """Integrate explicit sine-series traces in free space.

    Each trace has xyz ``start``, ``end`` and real ``coefficients``. Its shape
    is r(theta)=(start+end)/2+(end-start)*cos(theta)/2, theta decreasing pi→0.
    Projected traces must be straight; their directions and positions may
    differ. Staggering along wind is immaterial. Reversed orientation, shared
    endpoints and crossing traces are supported. Unsupported geometry
    or unresolved quadrature returns available=False, never a guessed value.
    """
    wind, side, lift, reference = map(lambda v: np.asarray(v, dtype=float), (wind, side, lift, reference))
    if any(v.shape != (3,) for v in (wind, side, lift)) or reference.shape != (2, 3):
        raise ValueError('Fourier wake requires three xyz axes and a two-row reference array.')
    axes = np.column_stack([wind, side, lift])
    if (not np.isfinite(axes).all() or not np.allclose(axes.T@axes, np.eye(3), atol=1e-12, rtol=0)
            or not np.allclose(np.cross(wind, side), lift, atol=1e-12, rtol=0)):
        raise ValueError('Fourier wake axes must be a finite right-handed orthonormal frame.')
    if (not np.isfinite(reference).all() or not np.isfinite([speed, density, relative_tolerance]).all()
            or min(speed, density, reference[0, 0], reference[0, 2], relative_tolerance) <= 0):
        raise ValueError('Fourier wake scales and tolerance must be finite and positive.')
    if isinstance(max_order, bool) or not isinstance(max_order, (int, np.integer)) or max_order not in (32, 64, 128, 256, 512):
        raise ValueError('Fourier wake maximum quadrature order must be 32, 64, 128, 256 or 512.')
    if not traces:
        return _unavailable('No Fourier lifting traces.')
    parsed = []
    for trace in traces:
        if any(np.iscomplexobj(trace[k]) for k in ('start', 'end', 'coefficients')):
            raise ValueError('Fourier wake geometry and coefficients must be real.')
        a, b, coefficients = (np.asarray(trace[k], dtype=float).copy() for k in ('start', 'end', 'coefficients'))
        if a.shape != (3,) or b.shape != (3,) or coefficients.ndim != 1 or not len(coefficients):
            raise ValueError('Each Fourier trace needs two xyz endpoints and at least one coefficient.')
        if not all(np.isfinite(v).all() for v in (a, b, coefficients)):
            raise ValueError('Fourier wake geometry and coefficients must be finite.')
        a, b = a-reference[1], b-reference[1]
        a, b = complex(a@side, a@lift), complex(b@side, b@lift)
        length = abs(b-a)
        if not np.isfinite(length):
            return _unavailable('Projected Fourier span exceeds floating-point range.')
        if length == 0:
            return _unavailable('A Fourier trace has zero projected span.')
        parsed.append((a, b, coefficients, length))
    geometry_scale = max(p[3] for p in parsed)
    epsilon = 64*np.finfo(float).eps*geometry_scale
    unloaded = all(not np.any(p[2]) for p in parsed)
    groups = []
    vertices = []
    for index, (a, b, coefficients, length) in enumerate(parsed):
        # The same physical endpoint can differ by roundoff after rotation or
        # projection. Reconcile vertices at the same tolerance used for sheets.
        snapped = []
        for point in (a, b):
            vertex = next((v for v in vertices if abs(v-point) <= epsilon), None)
            if vertex is None:
                vertex = point
                vertices.append(point)
            snapped.append(vertex)
        a, b = snapped
        length = abs(b-a)
        if length == 0:
            return _unavailable('A Fourier trace is shorter than the projected geometry resolution.')
        center = .5*(a+b)
        row = dict(start=a, end=b, center=center, direction=(b-a)/length, half_span=length/2,
                   coefficients=coefficients, members=[index])
        # Combine coincident sheets first. This preserves exact cancellation
        # even when each source is translated independently along the wind.
        match = None
        for group in groups:
            if abs(a-group['start']) <= epsilon and abs(b-group['end']) <= epsilon:
                match = group
                break
            if abs(a-group['end']) <= epsilon and abs(b-group['start']) <= epsilon:
                match = group
                coefficients *= (-1.)**np.arange(1, len(coefficients)+1)
                break
        if match is None:
            groups.append(row)
        else:
            count = max(len(match['coefficients']), len(coefficients))
            match['coefficients'] = np.pad(match['coefficients'], (0, count-len(match['coefficients'])))+np.pad(coefficients, (0, count-len(coefficients)))
            match['members'].append(index)
    scale = max(float(np.max(abs(g['coefficients']))) for g in groups)
    matrix = np.zeros((len(groups), len(groups)))
    errors = []
    if scale:
        for g in groups:
            g['coefficients'] /= scale
        for i, g in enumerate(groups):
            matrix[i, i] = math.pi/8*float(np.sum(np.arange(1, len(g['coefficients'])+1)*g['coefficients']**2))
        for i, target in enumerate(groups):
            for j in range(i):
                source = groups[j]
                energy_scale = math.sqrt(matrix[i, i])*math.sqrt(matrix[j, j])
                if energy_scale == 0:
                    continue
                old = np.array([_mutual(target, source, 16), _mutual(source, target, 16)])
                order = 32
                while True:
                    current = np.array([_mutual(target, source, order), _mutual(source, target, order)])
                    error = max(float(np.max(abs(current-old))), float(abs(current[0]-current[1])))
                    if np.isfinite(current).all() and error <= relative_tolerance*energy_scale:
                        break
                    if order == max_order:
                        return _unavailable('Continuous Fourier mutual integral did not converge; increase max_order or examine the projected traces.')
                    old, order = current, order*2
                matrix[i, j], matrix[j, i] = current
                errors.append(dict(groups=[i, j], order=order, normalized_error=error,
                                   relative_error=error/energy_scale))
    energy = float(matrix.sum())
    roundoff = 512*np.finfo(float).eps*float(np.sum(abs(matrix)))
    if energy < -roundoff:
        return _unavailable('Continuous Fourier wake energy is negative beyond roundoff; quadrature is unresolved.')
    energy = max(energy, 0.)
    impulse = 0j
    rolling = 0.
    for g in groups:
        a1 = g['coefficients'][0]
        a2 = g['coefficients'][1] if len(g['coefficients']) > 1 else 0.
        integral = math.pi*g['half_span']*a1/2
        impulse += 1j*g['direction']*integral
        rolling += (g['center']*np.conj(g['direction'])).real*integral+math.pi*g['half_span']**2*a2/4
    force = density*speed*scale*(impulse.real*side+impulse.imag*lift)
    roll = density*speed*scale*rolling
    drag = density*scale*scale*energy
    qs = .5*density*speed*speed*reference[0, 0]
    cli, cyi, cdi = float(force@lift/qs), float(force@side/qs), drag/qs
    efficiency = (cli*cli+cyi*cyi)/(math.pi*reference[0, 2]**2/reference[0, 0]*cdi) if cdi > 0 else (0. if unloaded else None)
    if not np.isfinite([*force, roll, drag, qs, cli, cyi, cdi]).all() or (efficiency is not None and not np.isfinite(efficiency)):
        return _unavailable('Continuous Fourier forces exceed floating-point range.')
    return dict(available=True, reason=None, CLi=cli, CYi=cyi, CDi=cdi, efficiency=efficiency,
        induced_drag=drag, force_transverse_body=force.tolist(), rolling_moment_wind=roll,
        Cl=-roll/(qs*reference[0, 2]), drag_matrix=(density*scale*scale*matrix).tolist(),
        trace_groups=[g['members'] for g in groups], quadrature=errors,
        convention='Continuous sine-series circulation; analytic self energy and source fields, refined target integrals.',
        scope='Free-space straight Fourier traces with arbitrary orientations. Explicit reference diagnostic; discrete solver outputs are unchanged.')


def fourier_wake_for_meshes(model, condition, meshes, circulation, basis, density, ground):
    """Reference integral of the selected basis; never fit pointwise circulation."""
    if model.reference[0, 0] == 0:
        return _unavailable('Continuous Fourier coefficient diagnostic requires a positive reference area; dimensional discrete wake outputs remain available.')
    if ground is not None and ground.flag:
        return _unavailable('Continuous Fourier reference does not yet include ground images.')
    lifting = [m for m in meshes if m.beam.lifting]
    if not lifting or any(b['representation'] != 'fourier' for b in basis.beams):
        return _unavailable('Continuous Fourier reference requires a Fourier basis on every lifting beam.')
    coefficients = basis.encode(circulation)
    wind, side, lift = condition.vectors()
    traces = []
    for mesh, description in zip(lifting, basis.beams, strict=True):
        if mesh.beam.index != description['beam']:
            raise ValueError('Fourier wake basis does not match lifting mesh order.')
        a, b = mesh.r0[0], mesh.r1[-1]
        theta = np.asarray(mesh.theta)
        center, half = .5*(a+b), .5*(b-a)
        span = np.linalg.norm((b-a)-np.dot(b-a, wind)*wind)
        for points, angles in ((mesh.r0, theta[:-1]), (mesh.r1, theta[1:]), (mesh.rm, .5*(theta[:-1]+theta[1:]))):
            error = points-(center+np.cos(angles)[:, None]*half)
            error -= (error@wind)[:, None]*wind
            if np.max(np.linalg.norm(error, axis=1), initial=0.) > 1e-11*span:
                return _unavailable('A projected Fourier trace is curved or is not linear in its material cosine coordinate.')
        start = description['coefficient_start']
        traces.append(dict(start=a, end=b, coefficients=coefficients[start:start+description['unknowns']]))
    return fourier_wake_forces(traces, wind, side, lift, condition.speed, density, model.reference[:2])
