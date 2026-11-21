"""Independent virtual-work transfer of complete aerodynamic loads to nodes.

Inputs are the saved actual-aircraft fixture, current physical node poses, and
the independent FullAeroReference output maps. No native observed loads are
read, and no aerodynamic field, production module, residual or solve is used.
All forces/couples use physical ASW units in the instantaneous body gauge.

For each lifting strip at material fraction f, translational work gives
F_a=(1-f)F, F_b=f F. Geodesic angular interpolation gives
omega(f)=Wa omega_a+Wb omega_b, so nodal couples are Wa.T m and Wb.T m.
Here m is already the strip couple about the sampled centerline. There is no
additional (rm-rnode) cross F term: the independent nodal translations already
produce rm, and adding that arm would duplicate the strip force moment.

Body force_samples already include quadrature weights. They are transferred
at their original material fractions with zero intrinsic sample couples. The
reported integrated body_moment is consequently NOT transferred a second time.
Point drag and intrinsic engine wrenches act at rigid pylon endpoints, giving
node couple m+(Q offset) cross F. This is the point-wrench relation in Drela
steady equations 95--106 and the transpose of the nodal kinematic map.

Supported scope: zero endpoint-to-node offsets, constant jig material triads
within each beam, no unequal radius jumps, and type-0 engines. Geometry and
loads retain their complex perturbations; the transpose is never conjugated.
The output is external aerodynamic load only, excluding real-mass inertia,
gravity, struts, joints, reactions and prescribed loads.
"""

import numpy as np

from daedalus_full_aero_reference import sample_beam


def _array(value, shape, name):
    value = np.asarray(value)
    if value.shape != shape or not np.all(np.isfinite(value)):
        raise ValueError(f"{name} must be finite with shape {shape}.")
    return value


class AeroTransferReference:
    """Transfer independent full-aero outputs to every fixture node.

    evaluate(state, aero_outputs) returns lifting/body/point/engine component
    nodal_force and nodal_moment arrays, their nodal totals, and total force and
    moment about fixture.reference[1]. Every nodal couple is about that node's
    current position. state need only contain r[nnodes,3] and Q[nnodes,3,3].
    Lifting arrays follow fixture beam order, as in FullAeroReference; the
    actual Daedalus fixture has one nonlifting body and 108 structural nodes.
    """

    def __init__(self, fixture):
        self.fixture = fixture
        self.beams = fixture['beams']
        base_r = np.asarray(fixture['loaded_base']['r'])
        self.nn = len(base_r)
        _array(base_r, (self.nn, 3), 'loaded base node positions')
        ends = np.asarray(fixture['ends'])
        if (ends.ndim != 2 or ends.shape[1] != 2 or np.iscomplexobj(ends)
                or not np.all(np.isfinite(ends)) or np.any(ends != np.floor(ends))
                or np.any(ends < 0) or np.any(ends >= self.nn)):
            raise ValueError('Fixture endpoints must be valid node-index pairs.')
        self.ends = ends.astype(int)
        self.origin = _array(np.asarray(fixture['reference'])[1], (3,), 'moment origin')
        self.lifting = []
        self.body = []
        represented = []
        for beam in self.beams:
            ids = np.asarray(beam['element_ids'])
            if (ids.ndim != 1 or np.iscomplexobj(ids) or np.any(ids != np.floor(ids))
                    or np.any(ids < 0) or np.any(ids >= len(self.ends))):
                raise ValueError('Beam element indices are invalid.')
            represented.extend(ids.astype(int).tolist())
            count = len(ids)
            for name in ('offa', 'offb'):
                if np.any(_array(beam[name], (count, 3), name) != 0):
                    raise ValueError('Nonzero beam endpoint offsets require an extended transfer.')
            first = _array(beam['R0a'], (count, 3, 3), 'first jig frames')
            last = _array(beam['R0b'], (count, 3, 3), 'last jig frames')
            if (not count or np.max(abs(first-first[0])) > 2e-13
                    or np.max(abs(last-first[0])) > 2e-13):
                raise ValueError('Transfer requires constant jig triads on each beam.')
            fractions = _array(beam['fraction'], (count,), 'strip material fractions')
            if np.any(fractions.real <= 0) or np.any(fractions.real >= 1):
                raise ValueError('Strip fractions must lie strictly inside their elements.')
            if beam['lifting']:
                self.lifting.append(beam)
            else:
                self.body.append(beam)
                radius = beam['distributions']['radius']
                if np.any((np.diff(radius['t']) == 0) & (np.diff(radius['values']) != 0)):
                    raise ValueError('Body radius jumps require explicit additional point loads.')
        if sorted(represented) != list(range(len(self.ends))):
            raise ValueError('Each fixture element must belong to exactly one beam.')
        if len(self.body) != 1:
            raise ValueError('The actual-aircraft output schema requires exactly one body beam.')
        self.np = sum(len(beam['element_ids']) for beam in self.lifting)
        self.attachments = fixture['attachments']
        for kind in ('weight', 'engine'):
            entries = self.attachments[kind]
            if len(entries) != len(fixture['records'].get(kind, [])):
                raise ValueError('Attachment and literal record counts differ.')
            for entry in entries:
                node = entry['node']
                if int(node) != node or not 0 <= node < self.nn:
                    raise ValueError('Attachment node is invalid.')
                _array(entry['offset'], (3,), 'attachment pylon offset')
        for row in fixture['records'].get('engine', []):
            if len(row) < 15 or row[1] != 0 or np.any(np.asarray(row)[15:] != 0):
                raise ValueError('Only type-0 engines with zero optional fields are supported.')
        self.evaluations = 0

    def evaluate(self, state, aero_outputs):
        self.evaluations += 1
        r = _array(state['r'], (self.nn, 3), 'current node positions')
        Q = _array(state['Q'], (self.nn, 3, 3), 'current deformation rotations')
        if (np.max(abs(Q.transpose(0, 2, 1)@Q-np.eye(3))) > 2e-10
                or np.any(np.linalg.det(Q).real <= 0)):
            raise ValueError('Current deformation rotations must be proper orthogonal matrices.')
        lift_force = _array(aero_outputs['lifting_force'], (self.np, 3), 'lifting strip forces')
        lift_moment = _array(aero_outputs['lifting_moment'], (self.np, 3), 'lifting strip couples')
        body = self.body[0]
        fractions = np.asarray(body['body_quadrature']['u'])
        if (fractions.ndim != 1 or not np.all(np.isfinite(fractions))
                or np.any(fractions <= 0) or np.any(fractions >= 1)):
            raise ValueError('Body quadrature fractions must lie inside each element.')
        body_samples = _array(aero_outputs['body_force_samples'],
                              (len(body['element_ids']), len(fractions), 3),
                              'weighted body force samples')
        point_force = _array(aero_outputs['point_force'],
                             (len(self.attachments['weight']), 3), 'point drag forces')
        engine_force = _array(aero_outputs['engine_force'],
                              (len(self.attachments['engine']), 3), 'intrinsic engine forces')
        engine_moment = _array(aero_outputs['engine_moment'], engine_force.shape,
                               'intrinsic engine couples')
        dtype = np.result_type(r, Q, lift_force, lift_moment, body_samples,
                               point_force, engine_force, engine_moment)
        result = {kind+'_nodal_'+quantity: np.zeros((self.nn, 3), dtype=dtype)
                  for kind in ('lifting', 'body', 'point', 'engine')
                  for quantity in ('force', 'moment')}
        # Sampling needs kinematic placeholders, but transfer depends only on
        # poses. No velocity or acceleration from observed loads is consumed.
        zero = np.zeros((self.nn, 3), dtype=dtype)
        geometry_state = dict(r=r, Q=Q, u=zero, w=zero, udot=zero, wdot=zero)
        start = 0
        for beam in self.lifting:
            count = len(beam['element_ids'])
            force = lift_force[start:start+count]
            moment = lift_moment[start:start+count]
            sampled = sample_beam(beam, geometry_state, self.ends)
            a, b = self.ends[beam['element_ids']].T
            f = np.asarray(beam['fraction'])
            for nodes, weight, angular in ((a, 1-f, sampled['Wa']), (b, f, sampled['Wb'])):
                np.add.at(result['lifting_nodal_force'], nodes, weight[:, None]*force)
                np.add.at(result['lifting_nodal_moment'], nodes,
                          np.einsum('nji,nj->ni', angular, moment))
            start += count
        a, b = self.ends[body['element_ids']].T
        for nodes, weight in ((a, 1-fractions), (b, fractions)):
            np.add.at(result['body_nodal_force'], nodes,
                      np.sum(weight[None, :, None]*body_samples, axis=1))
        for kind, records, force, intrinsic in (
                ('point', self.attachments['weight'], point_force, np.zeros_like(point_force)),
                ('engine', self.attachments['engine'], engine_force, engine_moment)):
            for j, entry in enumerate(records):
                node = int(entry['node'])
                arm = Q[node]@entry['offset']
                result[kind+'_nodal_force'][node] += force[j]
                result[kind+'_nodal_moment'][node] += intrinsic[j]+np.cross(arm, force[j])
        result['nodal_force'] = sum(result[kind+'_nodal_force'] for kind in ('lifting','body','point','engine'))
        result['nodal_moment'] = sum(result[kind+'_nodal_moment'] for kind in ('lifting','body','point','engine'))
        result['total_force'] = result['nodal_force'].sum(axis=0)
        result['total_moment'] = (result['nodal_moment']
            +np.cross(r-self.origin, result['nodal_force'])).sum(axis=0)
        return result
