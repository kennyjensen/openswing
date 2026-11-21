"""Independent complete aerodynamic directional map at stationary Daedalus.

No production imports, aircraft solves, fitted properties or inferred material
interpolation. Explicit parsed material samples define the discrete problem.
Primary equations are Drela steady 62--74, 95--106, 121--164, 204 and unsteady
22--27, 34--36, 41--45, 48--49. Independent component modules integrate the
vortex/volume/jet fields and implement SO(3) interpolation.

This evaluator is exact at a stationary loaded base and to FIRST ORDER about
it. The quadratic convective part of interpolated elastic angular acceleration
is omitted; its value and derivative vanish at this base. Consequently this is
not a finite-motion time integrator. The caller must check zero base rates and
accelerations. Raw physical input directions may be extracted from a native
state chart, but native sampled velocities, source strengths, forces and moments
are never expected-physics inputs. The input chart and material interpolation
are outside this comparison's scope.

Supported actual-case branches: zero ground/gust, live influences, sea-level
constant density/sound speed, pointwise circulation, positive-thrust type-0
engines, zero beam endpoint offsets, constant jig triads on each beam, and no
declared body radius jumps. Body apparent-mass factor is an explicit selected
convention; matching it does not prove the printed factor or historical parity.
"""

import numpy as np

from elastic_fin_aero import norm
from elastic_fin_kinematics import exponential, logarithm, left_jacobian, inverse_left_jacobian
from free_elastic_aero import MultiSurfaceAero
from daedalus_volume_reference import VolumeReference
from daedalus_jet_reference import engine_load, jet_velocity, point_drag
from daedalus_vortex_receivers import vortex_velocity


def physical_inputs(packet, control_ids, power_ids):
    """Extract physical inputs only; no native observed physics is accessed."""
    p = packet['inputs']; c = p['condition']; m = p['motion']
    result = {k: np.asarray(p[k]).copy() for k in
              ('r', 'Q', 'u', 'w', 'udot', 'wdot', 'gamma', 'gamma_dot')}
    result.update(U=np.asarray(p['frame']['U']), Omega=np.asarray(m['rates']),
                  acceleration=np.asarray(m['acceleration']),
                  angular_acceleration=np.asarray(m['angular_acceleration']),
                  controls=np.array([c['controls'].get(k, c['controls'].get(str(k), 0.)) for k in control_ids]),
                  powers=np.array([c['powers'].get(k, c['powers'].get(str(k), 0.)) for k in power_ids]))
    return result


def sample_beam(beam, state, ends):
    """Independent geometry and first-order elastic section kinematics."""
    a, b = ends[beam['element_ids']].T
    f = np.asarray(beam['fraction']); ff = f[:, None]
    r, Q = state['r'], state['Q']
    ra, rb = Q[a]@beam['R0a'], Q[b]@beam['R0b']
    frames, Wa, Wb = [], [], []
    for first, last, fraction in zip(ra, rb, f):
        arc = logarithm(first.T@last)
        weight = first@(fraction*left_jacobian(fraction*arc))@inverse_left_jacobian(arc)@first.T
        frames.append(first@exponential(fraction*arc)); Wa.append(np.eye(3)-weight); Wb.append(weight)
    Wa, Wb = np.array(Wa), np.array(Wb)
    angular = lambda v: np.einsum('nij,nj->ni', Wa, v[a])+np.einsum('nij,nj->ni', Wb, v[b])
    original = beam['original_mesh']
    ratio = np.asarray(original['length'])/norm(np.asarray(original['r1'])-original['r0'])
    return dict(r0=r[a], r1=r[b], rm=(1-ff)*r[a]+ff*r[b],
                R0=ra, R1=rb, Rm=np.array(frames), ds=ratio*norm(r[b]-r[a]),
                velocity=(1-ff)*state['u'][a]+ff*state['u'][b],
                omega=angular(state['w']),
                acceleration=(1-ff)*state['udot'][a]+ff*state['udot'][b],
                alpha=angular(state['wdot']), Wa=Wa, Wb=Wb)


def softplus(x):
    """Stable analytic continuation on each selected real half-plane."""
    positive = np.real(x) > 0
    return np.where(positive, x, 0.)+np.log1p(np.exp(np.where(positive, -x, x)))


class FullAeroReference:
    def __init__(self, fixture, base_packet, *, quadrature=32, jet_degree=16):
        self.fixture = fixture; self.beams = fixture['beams']; self.ends = fixture['ends']
        self.reference = np.asarray(fixture['reference']); self.jet_degree = jet_degree
        self.condition = base_packet['inputs']['condition']; c = self.condition
        if (c['ground_effect'] or c['gust'] not in (None, {}) or c['freeze_influences']
                or c['altitude_m'] != 0 or c['circulation_modes'] or c['mach'] is None):
            raise ValueError('Unsupported atmospheric/ground/gust/influence/circulation branch')
        self.control_ids = sorted(map(int, c['controls'])); self.power_ids = sorted(map(int, c['powers']))
        self.base = physical_inputs(base_packet, self.control_ids, self.power_ids)
        if any(np.any(self.base[k] != 0) for k in
               ('u', 'w', 'udot', 'wdot', 'gamma_dot', 'Omega', 'acceleration', 'angular_acceleration')):
            raise ValueError('First-order reference requires a stationary loaded base')
        self.rho = fixture['constants'][1] if c['density'] is None else c['density']
        self.sound = fixture['constants'][2]
        free = -self.base['U']-np.cross(self.base['Omega'], self.reference[3])
        mach = norm(free)/self.sound if c['mach'] is None else c['mach']
        material = {k: [] for k in MultiSurfaceAero.scalar_material}
        physical = []; self.lifting = []; self.body = []
        for beam in self.beams:
            if np.any(beam['offa']) or np.any(beam['offb']):
                raise ValueError('Endpoint offsets require an extended reference')
            if (np.max(abs(beam['R0a']-beam['R0a'][0])) > 2e-13
                    or np.max(abs(beam['R0b']-beam['R0a'][0])) > 2e-13):
                raise ValueError('This reference requires constant jig triads on each beam')
            if not beam['lifting']:
                self.body.append(beam); continue
            self.lifting.append(beam); m = beam['material_receiver']; ep = beam['material_endpoints']
            values = dict(chord=m['chord'], Xax=m['Xax'], alpha_radians=np.deg2rad(m['alpha']),
                          CLa=m['dCLda'], Cdf=m['Cdf'], Cdp=m['Cdp'], Cm=m['Cm'],
                          dCLdF3=m.get('dCLdF3', np.zeros_like(m['chord'])),
                          dCMdF3=m.get('dCMdF3', np.zeros_like(m['chord'])),
                          dCDdF3=m.get('dCDdF3', np.zeros_like(m['chord'])),
                          chord0=ep['right']['chord'], chord1=ep['left']['chord'],
                          Xax0=ep['right']['Xax'], Xax1=ep['left']['Xax'])
            for key in material: material[key].extend(values[key])
            physical.extend([beam['physical']]*len(m['chord']))
        self.material = {k: np.asarray(v) for k, v in material.items()}
        self.aero = MultiSurfaceAero(self.material, dict(freestream=free, density=self.rho,
            sound_speed=self.sound, pg_mach=mach, moment_origin=self.reference[1],
            wake_core_ratio=c['wake_core_ratio']), physical, quadrature)
        if len(self.body) != 1: raise ValueError('Actual Daedalus has one body beam')
        body = self.body[0]; q = body['body_quadrature']; bm = body['original_mesh']
        radius_table = body['distributions']['radius']
        if np.any((np.diff(radius_table['t']) == 0) & (np.diff(radius_table['values']) != 0)):
            raise ValueError('Declared radius jumps require an extended reference')
        for row in fixture['records']['engine']:
            if len(row) < 15 or np.any(row[15:] != 0):
                raise ValueError('Nonzero optional engine fields require an extended reference')
        samples = {k: q[k] for k in ('radius', 'dradius_dt', 'Cdf', 'Cdp')}
        samples.update(t0=bm['t0'], t1=bm['t1'], physical=np.full(len(bm['t0']), body['physical']))
        rows = np.asarray(fixture['records']['weight'])
        self.volume = VolumeReference(samples, point_cda=rows[:, 6], point_volume=rows[:, 7],
            quadrature_nodes=q['u'], quadrature_weights=q['weights01'])
        self.evaluations = 0

    def evaluate(self, state):
        self.evaluations += 1; s = state; c = self.condition; out = {}
        samples = {b['index']: sample_beam(b, s, self.ends) for b in self.beams}
        section = {k: np.concatenate([samples[b['index']][k] for b in self.lifting])
                   for k in ('r0', 'r1', 'rm', 'R0', 'R1', 'Rm', 'ds', 'velocity', 'omega', 'acceleration', 'alpha')}
        free = -s['U']-np.cross(s['Omega'], self.reference[3])
        g = self.aero.geometry(section, free); speed = norm(free); wind = free/speed
        gamma = s['gamma']; fields = self.aero.fields(g)['fields']; p = self.material
        body = self.body[0]; bs = samples[body['index']]
        attachments = {}
        for kind in ('weight', 'engine'):
            attachments[kind] = []
            for record in self.fixture['attachments'][kind]:
                node = record['node']; arm = s['Q'][node]@record['offset']
                attachments[kind].append(dict(position=s['r'][node]+arm,
                    velocity=s['u'][node]+np.cross(s['w'][node], arm),
                    rates=s['Omega']+s['w'][node], rotation=s['Q'][node]))
        points = np.array([a['position'] for a in attachments['weight']])
        def volume(locations, **exclusions):
            return speed*self.volume.evaluate(bs['r0'], bs['r1'], points, wind, g['pg'], locations, **exclusions)['velocity']
        def induced(locations, physical=None):
            return vortex_velocity(self.aero, g, gamma, locations, physical)[0]
        def motion_flow(locations, local):
            return free-np.cross(s['Omega'], locations-self.reference[3])-local
        engines = []; inlets = []
        for row, a in zip(self.fixture['records']['engine'], attachments['engine']):
            location = a['position']; inlet = motion_flow(location, a['velocity'])+volume(location)+induced(location)
            power = s['powers'][self.power_ids.index(int(row[0]))]
            engines.append(engine_load(row[:15], power, self.rho, location, inlet, a['rates'], a['rotation']))
            inlets.append(inlet)
        def jets(locations):
            return jet_velocity(locations, engines, wind, self.rho, degree=self.jet_degree)
        velocities = {}
        for receiver in ('cp', 'hv', 'axis'):
            local = section['velocity']+np.cross(section['omega'], g[receiver]-section['rm'])
            velocities[receiver] = (motion_flow(g[receiver], local)
                +np.einsum('ijk,j->ik', fields[receiver], gamma)+volume(g[receiver])+jets(g[receiver]))
        alpha = p['alpha_radians'].astype(np.result_type(s['controls'], float)); cm = p['Cm'].astype(alpha.dtype); cdp = p['Cdp'].astype(alpha.dtype)
        for control, value in zip(self.control_ids, s['controls']):
            get = lambda kind: np.concatenate([b['material_receiver'][f'dC{kind}dF{control}'] for b in self.lifting])
            alpha += value*get('L')/p['CLa']; cm += value*get('M'); cdp += value*get('D')
        normal = g['normal']; span = g['span']; nc = np.sin(alpha)[:, None]*g['c']+np.cos(alpha)[:, None]*normal
        v, vc, va = (velocities[k] for k in ('hv', 'cp', 'axis'))
        vp = v-np.sum(v*span, axis=1)[:, None]*span; S = norm(vp); V = norm(v)
        if np.any(S.real <= speed.real*1e-12) or np.any((S/self.sound).real >= 1):
            raise ValueError('Invalid local normal-speed branch')
        gd = s['gamma_dot'] if c['aero_lag'] else np.zeros_like(s['gamma_dot'])
        tangency = np.sum(vc*nc, axis=1)-2/np.pi*gd/S
        cl = 2*gamma/(p['chord']*S)
        limits = {k: np.concatenate([b['material_receiver'][k] for b in self.lifting]) for k in ('CLmin', 'CLmax')}
        width = c['stall_width']
        leakage = width*(softplus((cl-limits['CLmax'])/width)-softplus((limits['CLmin']-cl)/width))
        residual = (tangency-(S/p['CLa']*c['stall_factor']*leakage if c['stall'] else 0))/speed
        coeff = self.rho*g['ds']; chord = p['chord']
        lift = (coeff*gamma)[:, None]*np.cross(v, span)
        rate = (coeff*chord*gd/S)[:, None]*np.cross(v, span)
        profile = .5*(coeff*chord)[:, None]*(p['Cdf'][:, None]*V[:, None]*v+cdp[:, None]*S[:, None]*vp)
        profile += 2*(coeff*chord*tangency*tangency/S)[:, None]*vp
        arm = g['half_arm']; location = section['rm']+arm
        local_velocity = section['velocity']+np.cross(section['omega'], arm)
        acceleration = (s['acceleration']+np.cross(s['angular_acceleration'], location-self.reference[2])
            +np.cross(s['Omega'], np.cross(s['Omega'], location-self.reference[2]))
            +section['acceleration']+np.cross(section['alpha'], arm)
            +np.cross(section['omega'], np.cross(section['omega'], arm))+2*np.cross(s['Omega'], local_velocity))
        rates = s['Omega']+section['omega']
        angular = s['angular_acceleration']+section['alpha']+np.cross(s['Omega'], section['omega'])
        rate_scalar = np.sum(np.cross(va, rates)*normal, axis=1); ma = self.rho*np.pi/4*chord**2*g['ds']
        apparent = (ma*(rate_scalar-np.sum(acceleration*normal, axis=1)))[:, None]*normal
        pitch = (-ma*(chord/4*rate_scalar+chord**2/32*np.sum(angular*span, axis=1)))[:, None]*span
        apparent_moment = np.cross(arm, apparent)+pitch
        force = lift+rate+profile+apparent
        moment = (np.cross(g['quarter_arm'], lift+rate)
            +(.5*coeff*chord**2*cm*S*S/np.sqrt(1-(S/self.sound)**2))[:, None]*span+apparent_moment)
        out.update(lifting_force=force, lifting_moment=moment, lifting_cl=cl,
            lifting_velocity=v, lifting_rate_force=rate, lifting_apparent_force=apparent,
            lifting_apparent_moment=apparent_moment, circulation_local_residual=residual)
        total_force = force.sum(axis=0); total_moment = (moment+np.cross(section['rm']-self.reference[1], force)).sum(axis=0)
        bgeom = self.volume.sample_geometry(bs['r0'], bs['r1'], bs['ds']); locations = bgeom['position']
        a, b = self.ends[body['element_ids']].T; q = self.volume.u[None, :, None]
        local_velocity = (1-q)*s['u'][a, None]+q*s['u'][b, None]
        velocity = (motion_flow(locations, local_velocity)+volume(locations, exclude_body=body['physical'])
            +induced(locations, body['physical'])+jets(locations))
        acceleration = (s['acceleration']+np.cross(s['angular_acceleration'], locations-self.reference[2])
            +np.cross(s['Omega'], np.cross(s['Omega'], locations-self.reference[2]))
            +(1-q)*s['udot'][a, None]+q*s['udot'][b, None]+2*np.cross(s['Omega'], local_velocity))
        loads = self.volume.body_loads(bs['r0'], bs['r1'], bs['rm'], bs['ds'], bs['Rm'][:, :, 1],
            velocity, acceleration, self.rho, added_mass_factor=c['body_added_mass_factor'])
        for key in ('force', 'moment', 'force_samples', 'apparent', 'apparent_moment'):
            out['body_'+key] = loads[key]
        out['body_velocity'] = velocity
        total_force += loads['force'].sum(axis=0)
        total_moment += (loads['moment']+np.cross(bs['rm']-self.reference[1], loads['force'])).sum(axis=0)
        point_forces = []; point_velocities = []
        for i, (row, a) in enumerate(zip(self.fixture['records']['weight'], attachments['weight'])):
            location = a['position']; velocity = (motion_flow(location, a['velocity'])
                +volume(location, exclude_point=i)+induced(location)+jets(location))
            force = point_drag(velocity, self.rho, row[6]); point_forces.append(force); point_velocities.append(velocity)
            total_force += force; total_moment += np.cross(location-self.reference[1], force)
        out.update(point_force=np.array(point_forces), point_velocity=np.array(point_velocities), engine_inlet=np.array(inlets))
        for key in ('force', 'moment', 'axial_velocity', 'delta_velocity'):
            out['engine_'+key] = np.array([e[key] for e in engines])
        for engine in engines:
            total_force += engine['force']
            total_moment += engine['moment']+np.cross(engine['position']-self.reference[1], engine['force'])
        out.update(total_force=total_force, total_moment=total_moment)
        return out
