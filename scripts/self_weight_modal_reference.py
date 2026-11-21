"""Independent Hermite energy reference for a straight self-weight column.

K = integral(EI w'' v'' - mu*g*(L-s) w' v') ds; M = integral(mu*w*v) ds.
The clamped root is imposed explicitly; free-tip conditions are natural.
All distributed translational inertia and the varying compressive preload are
retained. No production solver or matrix is imported.
"""
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import eigsh, norm


def basis(x, h):
    w = np.array([1-3*x*x+2*x**3, h*(x-2*x*x+x**3), 3*x*x-2*x**3, h*(-x*x+x**3)])
    slope = np.array([(-6*x+6*x*x)/h, 1-4*x+3*x*x, (6*x-6*x*x)/h, -2*x+3*x*x])
    curvature = np.array([(-6+12*x)/h**2, (-4+6*x)/h, (6-12*x)/h**2, (-2+6*x)/h])
    return w, slope, curvature


def matrices(elements=96, gravity=0., *, ei=100., mass_per_length=1., length=1.):
    if not isinstance(elements, int) or isinstance(elements, bool) or elements < 2:
        raise ValueError('At least two integer elements are required.')
    if not np.all(np.isfinite([gravity, ei, mass_per_length, length])) or min(ei, mass_per_length, length) <= 0:
        raise ValueError('Finite gravity and positive finite beam parameters are required.')
    nodes = np.linspace(0., length, elements + 1)
    gx, gw = np.polynomial.legendre.leggauss(4)
    rows, columns, stiffness, inertia = [], [], [], []
    for e, (a, b) in enumerate(zip(nodes[:-1], nodes[1:])):
        k = np.zeros((4, 4)); m = np.zeros((4, 4))
        for x, weight in zip((gx + 1) / 2, gw * (b - a) / 2):
            w, slope, curvature = basis(x, b - a)
            s = a + x * (b - a)
            k += weight * (ei * np.outer(curvature, curvature)
                           - mass_per_length * gravity * (length - s) * np.outer(slope, slope))
            m += weight * mass_per_length * np.outer(w, w)
        indices = 2 * e + np.arange(4)
        rows.extend(np.repeat(indices, 4)); columns.extend(np.tile(indices, 4))
        stiffness.extend(k.ravel()); inertia.extend(m.ravel())
    size = 2 * len(nodes)
    k = coo_matrix((stiffness, (rows, columns)), shape=(size, size)).tocsc()[2:, 2:]
    m = coo_matrix((inertia, (rows, columns)), shape=(size, size)).tocsc()[2:, 2:]
    return nodes, k, m


def modes(elements=96, gravity=0., count=4, *, ei=100., mass_per_length=1., length=1.):
    nodes, k, m = matrices(elements, gravity, ei=ei, mass_per_length=mass_per_length, length=length)
    values, vectors = eigsh(k, M=m, k=count, sigma=0., which='LM', tol=1e-12,
                            v0=np.random.default_rng(815).normal(size=k.shape[0]))
    order = np.argsort(values); values = values[order]; vectors = vectors[:, order]
    residual = k @ vectors - (m @ vectors) * values
    backward = np.max(abs(residual), axis=0) / ((norm(k, np.inf) + abs(values) * norm(m, np.inf)) * np.max(abs(vectors), axis=0))
    if np.max(backward) > 1e-10:
        raise RuntimeError(f'Full energy-pencil residual failed: {backward}')
    shapes = np.vstack([np.zeros((2, count)), vectors]).T.reshape(count, len(nodes), 2)
    for shape in shapes:
        shape /= shape[np.argmax(abs(shape[:, 0])), 0]
    return dict(elements=elements, gravity=gravity, EI=ei, mass_per_length=mass_per_length,
        length=length, nodes=nodes.tolist(), squared_frequencies_rad2_s2=values.tolist(),
        representative_poles=[[float(np.sqrt(-v)), 0.] if v < 0 else [0., float(np.sqrt(v))] for v in values],
        shapes=shapes.tolist(), eigen_backward_errors=backward.tolist(),
        unstable_modes=int(np.sum(values < 0)),
        scope='Full Hermite displacement/slope energy pencil with distributed mass and self-weight geometric stiffness.')
