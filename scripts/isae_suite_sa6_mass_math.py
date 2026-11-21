"""Tensor evidence for the prescribed rigid SA6 comparison.

Planning imports only the standard library. Geometry and tensor assembly are
deferred; no aerodynamic evaluation or nonlinear solution is performed here.
The independent energy reconstruction checks the existing discrete operator.
It does not replace its sampling by continuum integrals or select a mesh from
the archived values.
"""

TRIANGLE = ((0, 0, 'xx'), (0, 1, 'xy'), (0, 2, 'xz'),
            (1, 1, 'yy'), (1, 2, 'yz'), (2, 2, 'zz'))
GATE = 2e-12


def compute_tensor_evidence(model, meshes, density, reported_centroid,
                            body_added_mass_factor=1.0):
    import numpy as np
    from openswing.inertia import InertiaModel, mass_summary, apparent_properties

    density = float(density)
    factor = float(body_added_mass_factor)
    center = np.asarray(reported_centroid, dtype=float)
    if not np.isfinite(density) or density < 0 or not np.isfinite(factor) or factor < 0:
        raise ValueError('Density and body added-mass factor must be finite and nonnegative.')
    if center.shape != (3,) or not np.isfinite(center).all():
        raise ValueError('Reported centroid reference must be a finite xyz vector.')
    inertia = InertiaModel(model, meshes)
    elements = inertia.elements(meshes)
    real = [{k: np.asarray(record[k]).tolist() for k in ('mass', 'position', 'inertia', 'spin')}
            for record in elements]
    real_arrays = [np.concatenate([np.asarray(e[k]) for e in elements])
                   for k in ('mass', 'position', 'inertia', 'spin')]
    apparent, geometry, body_geometry = [], [], []
    for mesh in meshes:
        frame = np.asarray(mesh.frames)
        span = frame[..., 1]
        if mesh.beam.lifting:
            chord = mesh.beam.value('chord', mesh.tm)
            xax = mesh.beam.value('Xax', mesh.tm)
            position = mesh.rm + ((.5-xax)*chord)[:, None]*frame[..., 0]
            mass = density*np.pi/4*chord**2*mesh.length
            apparent.append(dict(kind='surface', mass=mass.tolist(), position=position.tolist(),
                normal=frame[..., 2].tolist(), span=span.tolist(),
                rotational_mass=(density*np.pi/128*chord**4*mesh.length).tolist()))
            geometry.append(dict(beam=mesh.beam.index, rm=mesh.rm.tolist(),
                r0=mesh.r0.tolist(), r1=mesh.r1.tolist(), ds=mesh.length.tolist(),
                frame=frame.tolist(), chord=chord.tolist(), xax=xax.tolist()))
        else:
            from openswing.volume import body_quadrature
            _, position, radius, weights = body_quadrature(mesh)
            mass = factor*density*np.pi*radius**2*weights
            spans = np.broadcast_to(span[:, None, :], position.shape)
            apparent.append(dict(kind='body', mass=mass.ravel().tolist(),
                position=position.reshape(-1, 3).tolist(), normal=None,
                span=spans.reshape(-1, 3).tolist(), rotational_mass=np.zeros(mass.size).tolist()))
            body_geometry.append(dict(beam=mesh.beam.index,
                position=position.reshape(-1, 3).tolist(), radius=radius.ravel().tolist(),
                weights=weights.ravel().tolist(), span=spans.reshape(-1, 3).tolist()))

    # A nonzero auxiliary reference exercises translation even when the native
    # origin and printed mass-centroid coordinates are identical.
    scale = float(model.reference[0, 2])
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError('Reference span must be finite and positive.')
    references = dict(origin=np.zeros(3), reported_centroid=center,
                      probe=scale*np.array([.37, -.21, .13]))
    cache, tensors, real_origin = {}, {}, None
    for name, reference in references.items():
        key = tuple(reference)
        if key not in cache:
            r = mass_summary(*real_arrays, reference)
            a = apparent_properties(meshes, density, reference, factor)
            if name == 'origin':
                real_origin = r
            cache[key] = dict(reference=reference.tolist(),
                real_spatial_matrix=r['spatial_matrix'],
                apparent_spatial_matrix=a['spatial_matrix'])
        tensors[name] = cache[key]
    return dict(density=density, body_added_mass_factor=factor,
        reference_span=scale,
        reported_centroid=center.tolist(), physical_real_cg=real_origin['cg'],
        real_mass=real_origin['mass'], real_records=real, apparent_records=apparent,
        tensors=tensors, geometry=dict(lifting_panels=geometry, body_panels=body_geometry,
            nonlifting_beams=sum(not m.beam.lifting for m in meshes), beam_count=len(meshes)),
        operations=dict(aerodynamic_calls=0, nonlinear_solves=0, derivative_factorizations=0,
            real_element_assemblies=1, tensor_reference_evaluations=len(cache),
            real_matrix_assemblies=len(cache), apparent_matrix_assemblies=len(cache)),
        discretization='Existing rigid model_meshes physical frames, chord and Glauert midpoint positions; '
            'apparent mass uses current element sums and local section pitch inertia. '
            'Real mass uses InertiaModel finite-segment inertia. No continuum second-moment substitution.',
        centroid_qualification='The centroid-labelled comparison evaluates tensors at the explicit archived '
            'coordinate. For zero real mass the physical CG remains undefined; no apparent-mass CG is invented.')


def tensor_predictions(evidence):
    """All 33 original printed entries; no invented lower-triangle targets."""
    origin = evidence['tensors']['origin']
    center = evidence['tensors']['reported_centroid']
    result = {'real_mass.'+axis: float(origin['real_spatial_matrix'][i][i])
              for i, axis in enumerate(('xx', 'yy', 'zz'))}
    for label, matrix, offset in (
        ('apparent_mass', origin['apparent_spatial_matrix'], 0),
        ('real_inertia_origin', origin['real_spatial_matrix'], 3),
        ('apparent_inertia_origin', origin['apparent_spatial_matrix'], 3),
        ('real_inertia_centroid', center['real_spatial_matrix'], 3),
        ('apparent_inertia_centroid', center['apparent_spatial_matrix'], 3)):
        result.update({label+'.'+axis: float(matrix[i+offset][j+offset])
                       for i, j, axis in TRIANGLE})
    return result


def validate_tensor_evidence(evidence):
    """Reconstruct spatial tensors from 21 kinetic-energy evaluations each.

    Every symmetric entry is checked. The scalar energy formula uses direct
    cross products and local normal velocities, independently of the production
    block-matrix assembly. Saved summaries need no production imports.
    """
    import numpy as np

    checks = []

    def add(name, value, tolerance=GATE):
        value = float(value)
        checks.append(dict(name=name, value=value, comparison='<=', tolerance=tolerance,
                           passed=bool(np.isfinite(value) and value <= tolerance)))

    def require(condition, message):
        if not condition:
            raise ValueError(message)

    def array(value, shape, message):
        out = np.asarray(value, dtype=float)
        require(out.shape == shape and np.isfinite(out).all(), message)
        return out

    try:
        density = float(evidence['density'])
        factor = float(evidence['body_added_mass_factor'])
        require(np.isfinite(density) and density >= 0 and np.isfinite(factor) and factor >= 0,
                'Invalid fluid properties.')
        real, apparent = [], []
        total, first = 0., np.zeros(3)
        for record in evidence['real_records']:
            mass = np.asarray(record['mass'], dtype=float)
            require(mass.ndim == 1 and np.isfinite(mass).all() and np.all(mass >= 0), 'Invalid real masses.')
            n = len(mass)
            pos = array(record['position'], (n, 3), 'Invalid real positions.')
            own = array(record['inertia'], (n, 3, 3), 'Invalid local real inertias.')
            array(record['spin'], (n, 3), 'Invalid local spin.')
            require(np.max(abs(own-own.swapaxes(-1, -2)), initial=0) <= GATE,
                    'Local real inertia is not symmetric.')
            require(np.min(np.linalg.eigvalsh(own), initial=0) >= -GATE,
                    'Local real inertia is not positive semidefinite.')
            total += float(mass.sum()); first += (mass[:, None]*pos).sum(axis=0)
            real.append((mass, pos, own))
        require(bool(real), 'Missing real mass records.')
        add('real mass record sum', abs(total-float(evidence['real_mass']))/max(1., abs(total)))
        if total == 0:
            require(evidence['physical_real_cg'] is None, 'A zero-mass physical CG is undefined.')
        else:
            cg = array(evidence['physical_real_cg'], (3,), 'Missing physical real CG.')
            add('physical real centroid', np.max(abs(cg-first/total))/max(1., np.max(abs(cg))))
        for record in evidence['apparent_records']:
            mass = np.asarray(record['mass'], dtype=float)
            require(mass.ndim == 1 and np.isfinite(mass).all() and np.all(mass >= 0), 'Invalid apparent masses.')
            n = len(mass)
            pos = array(record['position'], (n, 3), 'Invalid apparent positions.')
            span = array(record['span'], (n, 3), 'Invalid apparent span axes.')
            spin = array(record['rotational_mass'], (n,), 'Invalid apparent rotational mass.')
            require(np.all(spin >= 0), 'Negative apparent rotational mass.')
            add('apparent span unit vectors', np.max(abs(np.sum(span*span, axis=1)-1), initial=0))
            if record['kind'] == 'surface':
                normal = array(record['normal'], (n, 3), 'Invalid physical normals.')
                add('apparent normal unit vectors', np.max(abs(np.sum(normal*normal, axis=1)-1), initial=0))
                add('apparent normal span orthogonality', np.max(abs(np.sum(normal*span, axis=1)), initial=0))
            else:
                require(record['kind'] == 'body' and record['normal'] is None and np.all(spin == 0),
                        'Unsupported apparent-mass record.')
                normal = None
            apparent.append((mass, pos, normal, span, spin))

        surface_records = [r for r in evidence['apparent_records'] if r['kind'] == 'surface']
        geometries = evidence['geometry']['lifting_panels']
        require(len(surface_records) == len(geometries), 'Surface geometry/record inventory differs.')
        require(len(apparent) == evidence['geometry']['beam_count'], 'Apparent beam inventory differs.')
        require(sum(r['kind'] == 'body' for r in evidence['apparent_records']) ==
                evidence['geometry']['nonlifting_beams'], 'Body inventory differs.')
        require(len(apparent) > 0, 'Missing apparent-mass records.')
        for geometry, record in zip(geometries, surface_records):
            n = len(record['mass'])
            frame = array(geometry['frame'], (n, 3, 3), 'Invalid physical section frames.')
            rm = array(geometry['rm'], (n, 3), 'Invalid physical sample positions.')
            array(geometry['r0'], (n, 3), 'Invalid physical first endpoints.')
            array(geometry['r1'], (n, 3), 'Invalid physical second endpoints.')
            chord = array(geometry['chord'], (n,), 'Invalid physical chords.')
            xax = array(geometry['xax'], (n,), 'Invalid physical axis locations.')
            ds = array(geometry['ds'], (n,), 'Invalid interval lengths.')
            require(np.all(ds > 0) and np.all(chord >= 0), 'Nonpositive intervals or negative chords.')
            add('physical frame orthonormality', np.max(abs(frame.swapaxes(-1, -2)@frame-np.eye(3)), initial=0))
            add('physical frame handedness', np.max(abs(np.cross(frame[..., 0], frame[..., 1])-frame[..., 2]), initial=0))
            expected = dict(mass=density*np.pi/4*chord**2*ds,
                rotational_mass=density*np.pi/128*chord**4*ds,
                position=rm+((.5-xax)*chord)[:, None]*frame[..., 0],
                normal=frame[..., 2], span=frame[..., 1])
            for key, value in expected.items():
                add('surface '+key+' geometry binding',
                    np.max(abs(np.asarray(record[key])-value), initial=0)/max(1., float(np.max(abs(value), initial=0))))
        body_records = [r for r in evidence['apparent_records'] if r['kind'] == 'body']
        bodies = evidence['geometry']['body_panels']
        require(len(bodies) == len(body_records), 'Body geometry/record inventory differs.')
        for geometry, record in zip(bodies, body_records):
            n = len(record['mass'])
            pos = array(geometry['position'], (n, 3), 'Invalid body quadrature positions.')
            radius = array(geometry['radius'], (n,), 'Invalid body quadrature radius.')
            weights = array(geometry['weights'], (n,), 'Invalid body quadrature weights.')
            span = array(geometry['span'], (n, 3), 'Invalid body quadrature span.')
            require(np.all(radius >= 0) and np.all(weights > 0), 'Invalid body quadrature measures.')
            for key, value in dict(position=pos, mass=factor*density*np.pi*radius**2*weights, span=span).items():
                add('body '+key+' geometry binding',
                    np.max(abs(np.asarray(record[key])-value), initial=0)/max(1., float(np.max(abs(value), initial=0))))

        def energy(q, ref, kind):
            u, omega = q[:3], q[3:]
            value = 0.
            if kind == 'real':
                for mass, pos, own in real:
                    vel = u+np.cross(omega, pos-ref)
                    value += np.sum(mass*np.sum(vel*vel, axis=1))
                    value += np.einsum('i,nij,j->', omega, own, omega)
            else:
                for mass, pos, normal, span, spin in apparent:
                    vel = u+np.cross(omega, pos-ref)
                    speed2 = (np.sum(vel*normal, axis=1)**2 if normal is not None else
                              np.sum(vel*vel, axis=1)-np.sum(vel*span, axis=1)**2)
                    value += np.sum(mass*speed2+spin*(span@omega)**2)
            return float(value)

        refs, matrices = {}, {}
        for name in ('origin', 'reported_centroid', 'probe'):
            block = evidence['tensors'][name]
            ref = array(block['reference'], (3,), 'Invalid reference.')
            refs[name] = ref; matrices[name] = {}
            for kind in ('real', 'apparent'):
                actual = array(block[kind+'_spatial_matrix'], (6, 6), 'Invalid spatial tensor.')
                expected = np.zeros((6, 6)); eye = np.eye(6)
                for i in range(6):
                    expected[i, i] = energy(eye[i], ref, kind)
                for i in range(6):
                    for j in range(i+1, 6):
                        expected[i, j] = expected[j, i] = (
                            energy(eye[i]+eye[j], ref, kind)-expected[i, i]-expected[j, j])/2
                scale = max(1., float(np.max(abs(expected))))
                add(name+' '+kind+' energy reconstruction', np.max(abs(actual-expected))/scale)
                add(name+' '+kind+' matrix symmetry', np.max(abs(actual-actual.T))/scale)
                add(name+' '+kind+' positive semidefinite', max(0., -float(np.min(np.linalg.eigvalsh(actual))))/scale)
                matrices[name][kind] = actual
        require(np.array_equal(refs['origin'], np.zeros(3)), 'Origin reference changed.')
        require(np.array_equal(refs['reported_centroid'], np.asarray(evidence['reported_centroid'])),
                'Reported centroid reference changed.')
        scale = float(evidence['reference_span'])
        require(np.isfinite(scale) and scale > 0 and
                np.array_equal(refs['probe'], scale*np.array([.37, -.21, .13])),
                'Oblique reference probe changed.')
        for name in ('reported_centroid', 'probe'):
            delta = refs[name]-refs['origin']
            transform = np.eye(6)
            for k in range(3):
                transform[:3, k+3] = np.cross(delta, np.eye(3)[k])
            for kind in ('real', 'apparent'):
                expected = transform.T@matrices['origin'][kind]@transform
                add(name+' '+kind+' reference translation',
                    np.max(abs(matrices[name][kind]-expected))/max(1., np.max(abs(expected))))
        operations = evidence['operations']
        require(all(operations[k] == 0 for k in ('aerodynamic_calls', 'nonlinear_solves', 'derivative_factorizations')),
                'Unexpected physical solution operations.')
        require(operations['real_element_assemblies'] == 1, 'Unexpected real element assemblies.')
        require(all(operations[k] == len({tuple(ref) for ref in refs.values()}) for k in
                    ('tensor_reference_evaluations', 'real_matrix_assemblies', 'apparent_matrix_assemblies')),
                'Tensor reference assembly counts differ.')
        require(len(tensor_predictions(evidence)) == 33, 'Incomplete printed tensor scope.')
        checks.append(dict(name='complete finite tensor evidence and scope', passed=True))
    except (ValueError, KeyError, TypeError, IndexError, OverflowError) as error:
        checks.append(dict(name='complete finite tensor evidence and scope', passed=False, error=str(error)))
    return checks
