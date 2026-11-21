"""Independent real-mass/gravity load map for stationary loaded Daedalus.

Primary sources: Drela steady theory 75--83, 87--96 and unsteady theory
22--27, 37--40, 46--47. Parsed material samples and the physical state chart
are explicit input seams. No production physics module is imported.

Each beam requires mass_material arrays mg,Ccg,Ncg,mgcc,mgnn and their D
variants, sampled at the ORIGINAL structural station ts. These are densities,
not integrated element values. Mass/inertia integrate the fixed original
mesh.length with independent Gauss quadrature (eight points by default). Current stretching
does not create mass. Section axes interpolate the full material triads along
their SO(3) geodesic. Their exact rotation-weight transposes and endpoint-pylon
arms transfer quadrature wrenches to nodes by virtual power. Distributed
translation already integrates the finite-segment parallel-axis contribution;
no additional ds**2/12 tensor is added.

The map is exact at the supplied stationary base and to FIRST ORDER there.
The quadratic convective term in interpolated relative angular acceleration
is omitted because its value and derivative vanish at zero base rates. This
is not a finite-motion time integrator. Absolute angular acceleration retains
Omega cross omega as required for body-component rate derivatives; the printed
unsteady formulas do not explicitly show that transport term. It is quadratic
and therefore immaterial to this particular stationary first-order comparison.

State keys: r,Q,u,w,udot,wdot,Omega,acceleration,angular_acceleration,gravity.
All vectors use physical body axes and consistent ASW input units. Other keys
from FullAeroReference.physical_inputs are accepted but unused. Point Weight
mass, spin and inertia are divided by the literal Constant g. Point tensor
products Ixy,Ixz,Iyz are the negatives of tensor off-diagonal entries.

Returned nodal moments are couples about each node. Component totals are
moments about Reference row 2 (fixture.reference[1]); acceleration is specified
at Reference row 3. No aerodynamic/apparent loads, constraints or supports are
included. Matching this discrete load map does not prove ASWING executable or
complete-aircraft response agreement.
"""

import numpy as np

from elastic_fin_kinematics import (
    exponential, logarithm, left_jacobian, inverse_left_jacobian,
)


def _array(value, shape, name):
    value = np.asarray(value)
    if value.shape != shape or not np.all(np.isfinite(value)):
        raise ValueError(name+' requires finite entries with shape '+str(shape))
    return value


def _real(value, shape, name):
    value = _array(value, shape, name)
    if np.iscomplexobj(value) and np.any(value.imag != 0):
        raise ValueError(name+' is a frozen real material input')
    return np.asarray(value.real, dtype=float).copy()


def _mv(matrix, vector):
    return np.einsum('...ij,...j->...i', matrix, vector)


class RealInertiaReference:
    """Material quadrature and virtual-power transfer, independent of native loads."""

    def __init__(self, fixture, base_state, *, quadrature=8):
        if (isinstance(quadrature, (bool, np.bool_))
                or not isinstance(quadrature, (int, np.integer)) or quadrature < 1):
            raise ValueError('Mass quadrature degree must be an integer at least one')
        self.nq = int(quadrature)
        self.fixture = fixture
        self.nn = len(base_state['r'])
        self.ends = np.asarray(fixture['ends'], dtype=int).copy()
        if (self.ends.ndim != 2 or self.ends.shape[1] != 2
                or np.any(self.ends < 0) or np.any(self.ends >= self.nn)):
            raise ValueError('Each material element requires two valid node IDs')
        self.ne = len(self.ends)
        self.reference = _real(fixture['reference'], (4, 3), 'reference rows')
        self.g = float(fixture['constants'][0])
        if not np.isfinite(self.g) or self.g <= 0:
            raise ValueError('Literal mass-conversion gravity must be positive')
        self.base = self._state(base_state)
        if any(np.any(self.base[key] != 0) for key in (
            'u', 'w', 'udot', 'wdot', 'Omega', 'acceleration', 'angular_acceleration'
        )):
            raise ValueError('First-order mass reference requires a stationary base')
        nodes, weights = np.polynomial.legendre.leggauss(self.nq)
        self.fractions, self.weights = (nodes+1)/2, weights/2
        self.beams = []
        covered = []
        for raw in fixture['beams']:
            ids = np.asarray(raw['element_ids'], dtype=int)
            count = len(ids)
            if ids.shape != (count,) or np.any(ids < 0) or np.any(ids >= self.ne):
                raise ValueError('Invalid beam material element IDs')
            covered.extend(ids)
            original = raw['original_mesh']
            length = _real(original['length'], (count,), 'original material length')
            if np.any(length <= 0):
                raise ValueError('Original material lengths must be positive')
            properties = raw['mass_material']
            entries = []
            for prefix in ('', 'D'):
                values = {key: _real(properties[prefix+key], (count,), prefix+key)
                          for key in ('mg', 'Ccg', 'Ncg', 'mgcc', 'mgnn')}
                if any(np.any(values[key] < 0) for key in ('mg', 'mgcc', 'mgnn')):
                    raise ValueError('Dynamic real masses and centroid inertias must be nonnegative')
                entries.append(dict(
                    mass=values['mg']*length/self.g,
                    c=values['Ccg'], n=values['Ncg'],
                    icc=values['mgcc']*length/self.g,
                    inn=values['mgnn']*length/self.g,
                ))
            self.beams.append(dict(
                index=raw['index'], ids=ids.copy(), entries=entries,
                R0a=_real(raw['R0a'], (count, 3, 3), 'first jig material triad'),
                R0b=_real(raw['R0b'], (count, 3, 3), 'last jig material triad'),
                offa=_real(raw['offa'], (count, 3), 'first endpoint pylon'),
                offb=_real(raw['offb'], (count, 3), 'last endpoint pylon'),
            ))
        if sorted(covered) != list(range(self.ne)):
            raise ValueError('Beams must cover each material element exactly once')
        rows = np.asarray(fixture['records']['weight'])
        attachments = fixture['attachments']['weight']
        rows = _real(rows, (len(attachments), 17), 'literal Weight records')
        self.points = []
        for index, (row, attachment) in enumerate(zip(rows, attachments)):
            node = int(attachment['node'])
            if node < 0 or node >= self.nn or attachment['index'] != index or row[5] < 0:
                raise ValueError('Invalid point mass attachment')
            xx, yy, zz, xy, xz, yz = row[11:17]/self.g
            tensor = np.array([[xx, -xy, -xz], [-xy, yy, -yz], [-xz, -yz, zz]])
            if np.linalg.eigvalsh(tensor).min() < -1e-12*max(abs(tensor).max(), 1e-30):
                raise ValueError('Point centroid inertia must be positive semidefinite')
            self.points.append(dict(node=node, mass=row[5]/self.g,
                offset=_real(attachment['offset'], (3,), 'point pylon'),
                inertia=tensor, spin=row[8:11]/self.g))
        self.evaluations = 0

    def _state(self, state):
        result = {key: _array(state[key], (self.nn, 3), key) for key in ('r', 'u', 'w', 'udot', 'wdot')}
        result['Q'] = _array(state['Q'], (self.nn, 3, 3), 'Q')
        result.update({key: _array(state[key], (3,), key) for key in (
            'Omega', 'acceleration', 'angular_acceleration', 'gravity')})
        return result

    def _sample(self, beam, state):
        a, b = self.ends[beam['ids']].T
        qa, qb = state['Q'][a], state['Q'][b]
        oa, ob = _mv(qa, beam['offa']), _mv(qb, beam['offb'])
        pa, pb = state['r'][a]+oa, state['r'][b]+ob
        ra, rb = qa@beam['R0a'], qb@beam['R0b']
        dtype = np.result_type(*state.values())
        rotation = np.empty((len(a), self.nq, 3, 3), dtype=dtype)
        wa, wb = np.empty_like(rotation), np.empty_like(rotation)
        for element, (first, last) in enumerate(zip(ra, rb)):
            arc = logarithm(first.T@last)
            inverse = inverse_left_jacobian(arc)
            for j, fraction in enumerate(self.fractions):
                rotation[element, j] = first@exponential(fraction*arc)
                wb[element, j] = first@(fraction*left_jacobian(fraction*arc))@inverse@first.T
                wa[element, j] = np.eye(3)-wb[element, j]
        f = self.fractions[None, :, None]
        interpolate = lambda x, y: (1-f)*x[:, None]+f*y[:, None]
        va = state['u'][a]+np.cross(state['w'][a], oa)
        vb = state['u'][b]+np.cross(state['w'][b], ob)
        aa = (state['udot'][a]+np.cross(state['wdot'][a], oa)
              +np.cross(state['w'][a], np.cross(state['w'][a], oa)))
        ab = (state['udot'][b]+np.cross(state['wdot'][b], ob)
              +np.cross(state['w'][b], np.cross(state['w'][b], ob)))
        angular = lambda value: _mv(wa, value[a, None])+_mv(wb, value[b, None])
        return dict(a=a, b=b, oa=oa, ob=ob, rotation=rotation, Wa=wa, Wb=wb,
            origin=interpolate(pa, pb), velocity=interpolate(va, vb),
            acceleration=interpolate(aa, ab), omega=angular(state['w']),
            alpha=angular(state['wdot']))

    def _wrench(self, state, position, arm, velocity, omega, acceleration, alpha, mass, tensor, spin):
        relative_velocity = velocity+np.cross(omega, arm)
        reference_arm = position-self.reference[2]
        absolute_acceleration = (
            state['acceleration']+np.cross(state['angular_acceleration'], reference_arm)
            +np.cross(state['Omega'], np.cross(state['Omega'], reference_arm))
            +acceleration+np.cross(alpha, arm)+np.cross(omega, np.cross(omega, arm))
            +2*np.cross(state['Omega'], relative_velocity)
        )
        total_rate = state['Omega']+omega
        total_alpha = state['angular_acceleration']+alpha+np.cross(state['Omega'], omega)
        gravity_force = mass[..., None]*state['gravity']
        inertial_force = -mass[..., None]*absolute_acceleration
        centroid_moment = -_mv(tensor, total_alpha)-np.cross(total_rate, _mv(tensor, total_rate)+spin)
        return gravity_force, inertial_force, centroid_moment

    def _transfer(self, sample, force, moment):
        """Exact transpose of the declared position/material-rotation map."""
        f = self.fractions[None, :, None]
        result = []
        for ids, weight, angular, arm in (
            (sample['a'], 1-f, sample['Wa'], sample['oa']),
            (sample['b'], f, sample['Wb'], sample['ob']),
        ):
            nodal_force = (weight*force).sum(axis=1)
            nodal_moment = _mv(angular.swapaxes(-1, -2), moment).sum(axis=1)
            nodal_moment += np.cross(arm, nodal_force)
            result.append((ids, nodal_force, nodal_moment))
        return result

    def evaluate(self, state):
        """Return physical nodal wrenches and independently accumulated totals."""
        self.evaluations += 1
        s = self._state(state)
        dtype = np.result_type(*s.values())
        groups = {key: np.zeros((self.nn, 6), dtype=dtype) for key in (
            'distributed', 'point', 'gravity', 'inertial', 'primary', 'additional')}
        end_force = np.zeros((self.ne, 2, 3), dtype=dtype)
        end_moment = np.zeros_like(end_force)
        sample_total_force = np.zeros(3, dtype=dtype)
        sample_total_moment = np.zeros(3, dtype=dtype)
        mass_total = 0.

        def add(group, transfer):
            for ids, force, moment in transfer:
                np.add.at(groups[group][:, :3], ids, force)
                np.add.at(groups[group][:, 3:], ids, moment)

        for beam in self.beams:
            sample = self._sample(beam, s)
            rotation = sample['rotation']
            for entry, group in zip(beam['entries'], ('primary', 'additional')):
                mass = entry['mass'][:, None]*self.weights
                mass_total += mass.sum()
                arm = entry['c'][:, None, None]*rotation[..., 0]+entry['n'][:, None, None]*rotation[..., 2]
                position = sample['origin']+arm
                diagonal = np.stack([entry['icc'], entry['icc']+entry['inn'], entry['inn']], axis=-1)
                diagonal = diagonal[:, None, :]*self.weights[None, :, None]
                tensor = (rotation*diagonal[..., None, :])@rotation.swapaxes(-1, -2)
                fg, fi, mi = self._wrench(s, position, arm, sample['velocity'], sample['omega'],
                    sample['acceleration'], sample['alpha'], mass, tensor, np.zeros_like(position))
                gravity = self._transfer(sample, fg, np.cross(arm, fg))
                inertia = self._transfer(sample, fi, mi+np.cross(arm, fi))
                total = self._transfer(sample, fg+fi, mi+np.cross(arm, fg+fi))
                add('gravity', gravity)
                add('inertial', inertia)
                add('distributed', total)
                add(group, total)
                for end, (_, force, moment) in enumerate(total):
                    end_force[beam['ids'], end] += force
                    end_moment[beam['ids'], end] += moment
                sample_total_force += (fg+fi).sum(axis=(0, 1))
                sample_total_moment += (mi+np.cross(position-self.reference[1], fg+fi)).sum(axis=(0, 1))

        point_force, point_moment, point_position = [], [], []
        for point in self.points:
            node = point['node']
            rotation = s['Q'][node]
            arm = rotation@point['offset']
            position = s['r'][node]+arm
            mass = np.asarray(point['mass'])
            mass_total += mass
            tensor = rotation@point['inertia']@rotation.T
            spin = rotation@point['spin']
            fg, fi, mi = self._wrench(s, position, arm, s['u'][node], s['w'][node],
                s['udot'][node], s['wdot'][node], mass, tensor, spin)
            gravity = (np.array([node]), fg[None, :], np.cross(arm, fg)[None, :])
            inertia = (np.array([node]), fi[None, :], (mi+np.cross(arm, fi))[None, :])
            force, moment = fg+fi, mi+np.cross(arm, fg+fi)
            add('gravity', [gravity])
            add('inertial', [inertia])
            add('point', [(np.array([node]), force[None, :], moment[None, :])])
            point_force.append(force)
            point_moment.append(moment)
            point_position.append(position)
            sample_total_force += force
            sample_total_moment += mi+np.cross(position-self.reference[1], force)

        total = groups['distributed']+groups['point']
        result = dict(nodal_force=total[:, :3], nodal_moment=total[:, 3:],
            element_end_force=end_force, element_end_moment=end_moment,
            point_object_force=np.asarray(point_force).reshape(-1, 3),
            point_object_nodal_moment=np.asarray(point_moment).reshape(-1, 3),
            point_object_position=np.asarray(point_position).reshape(-1, 3),
            sample_total_force=sample_total_force, sample_total_moment=sample_total_moment,
            mass_total=np.asarray(mass_total))
        for name, values in {'total': total, **groups}.items():
            result[name+'_force'] = values[:, :3].sum(axis=0)
            result[name+'_moment'] = (values[:, 3:]+np.cross(s['r']-self.reference[1], values[:, :3])).sum(axis=0)
            if name != 'total':
                result[name+'_nodal_force'] = values[:, :3]
                result[name+'_nodal_moment'] = values[:, 3:]
        return result
