"""Mounted nonlinear static equilibrium of connected ASW beams.

Mixed, objective midpoint discretization of the spatial beam equations, with
SO(3) rotations, exact rigid directions, and conservative nodal wrenches. When
a flight condition is supplied, circulation is an unknown of the same Newton
system. This discretization is independently convergent; it is not ASWING's
Euler-angle-average discrete system. See docs/NUMERICS.md for scope.
"""
from copy import deepcopy
from dataclasses import fields
import numpy as np
from .vector_ops import cross3
from scipy.optimize import root
from scipy.spatial.transform import Rotation
from .aero import AnalysisError, _validate, evaluate_aerodynamics, FrozenInfluences, _add_section_reactions
from .geometry import PanelMesh, mesh_beam, surface_frame, geometry_summary, attachment_geometry
from .structure import Section
from .inertia import Motion, InertiaModel, inertial_wrench
from .operating import OperatingSystem
from .struts import strut_load
from .ground import body_to_earth, GroundIntersectionError
from .joints import hinge_laws
from .atmosphere import operating_air
from .recovery import recover_structure
from .local_motion import NetworkMotion
from .dynamic_inertia import moving_mass_loads
from .discretization import normalize as normalize_discretization, requirements, report as mesh_report
from .discretization import CURRENT_MESH_RECIPE, checked_recipe
from .point_objects import active_weights, analysis_weight_station, rigid_weight_attachments, RIGID_ATTACHMENT_SCOPE


def exp(v):
    return Rotation.from_rotvec(np.asarray(v)).as_matrix()


def log(r):
    return Rotation.from_matrix(np.asarray(r)).as_rotvec()


class StaticNetwork:
    # Alternative discrete laws must opt out of midpoint-specific derivatives.
    # This is per network: one solve must never change another solve's tangent.
    analytic_mechanics = True

    def __init__(self, model, panels, condition, gravity, loads, motion=None, operating_constraints=(), strut_mode="bilateral", *, allow_signed_point_weights=False, allow_signed_distributed_weights=False, quiescent_density=None, quiescent_body_added_mass_factor=None, mesh_recipe=CURRENT_MESH_RECIPE):
        from .sensors import validate_sensors
        validate_sensors(model)
        self.model, self.condition = model, condition
        self.mesh_recipe = checked_recipe(mesh_recipe)
        self.quiescent_density = None
        self.quiescent_body_added_mass_factor = None
        if quiescent_density is None and quiescent_body_added_mass_factor is not None:
            raise AnalysisError('A still-air body coefficient requires explicit quiescent_density.')
        if quiescent_density is not None:
            from .quiescent import density_value, validate_model, stationary
            from .body_apparent import coefficient
            self.quiescent_density = density_value(quiescent_density)
            self.quiescent_body_added_mass_factor = coefficient(
                1. if quiescent_body_added_mass_factor is None else quiescent_body_added_mass_factor)
            validate_model(model)
            stationary(Motion() if motion is None else motion)
            if condition is not None or operating_constraints or allow_signed_point_weights or allow_signed_distributed_weights:
                raise AnalysisError('Quiescent network requires no FlightCondition, operating constraints or signed weights.')
        self.panels = panels = normalize_discretization(panels, model)
        self.loads = list(loads)
        if model.diagnostics:
            raise AnalysisError("Resolve unrecognized input before structural analysis.")
        if strut_mode not in ("bilateral", "wire"):
            raise AnalysisError("Strut mode must be bilateral or wire.")
        self.tension_only = strut_mode == "wire"
        self.struts = model.records.get("strut", [])
        # Structural-only loads have no engine operating point. Keep the
        # engine records in the model for attachment geometry and meshing.
        self.engines = model.records.get("engine", []) if condition is not None else []
        for row in self.struts:
            strut_load(row, row[2:5], tension_only=self.tension_only)
        self.hinges = hinge_laws(model.records)
        if condition is not None:
            _validate(model, condition)
            if motion is not None:
                raise AnalysisError("Specify motion in FlightCondition when aerodynamic loads are enabled.")
        self.motion = condition.motion() if condition is not None else (Motion() if motion is None else motion)
        if not isinstance(self.motion, Motion):
            raise AnalysisError("Structural-only motion must be an inertia.Motion instance.")
        if (allow_signed_point_weights or allow_signed_distributed_weights) and (condition is not None or operating_constraints or
                any(np.any(getattr(self.motion, key)) for key in ('rates', 'acceleration', 'angular_acceleration'))):
            raise AnalysisError("Signed static Weight loads require no airflow, no operating constraints and zero motion.")
        self.gravity_override = gravity is not None
        self.gravity = np.asarray([0., 0., -model.constants[0]] if gravity is None else gravity, dtype=float)
        if self.gravity.shape != (3,) or not np.all(np.isfinite(self.gravity)):
            raise AnalysisError("Gravity must be a finite xyz acceleration vector in input units.")
        self.gravity = self.gravity_at(condition)
        stations = {k: [r['t'] for r in rows] for k, rows in requirements(model, self.loads, mesh_recipe=self.mesh_recipe).items()}
        for load in self.loads:
            for key in ("force", "moment"):
                v = np.asarray(load.get(key, [0., 0., 0.]), dtype=float)
                if v.shape != (3,) or not np.all(np.isfinite(v)):
                    raise AnalysisError("Applied loads must be finite xyz vectors.")

        self.meshes, self.beam_nodes, self.beam_elements = [], {}, {}
        self.fractions = {}
        positions, endpoints, frame0, frame1, compliance = [], [], [], [], []
        self.sections = []
        self.station_nodes = {}
        ni = ei = 0
        for beam in model.beams:
            mesh = mesh_beam(beam, panels, stations[beam.index], mesh_recipe=self.mesh_recipe)
            n = len(mesh.tm)
            ts = np.r_[mesh.t0, mesh.t1[-1]]
            ids = np.arange(ni, ni+n+1)
            self.beam_nodes[beam.index] = ids
            self.beam_elements[beam.index] = slice(ei, ei+n)
            original = mesh.r1-mesh.r0
            self.fractions[beam.index] = np.sum((mesh.rm-mesh.r0)*original, axis=1)/np.sum(original**2, axis=1)
            self.station_nodes[beam.index] = (ts, ids)
            positions.extend(beam.position(ts))
            endpoints.extend(zip(ids[:-1], ids[1:]))
            frame0.extend(surface_frame(beam, mesh.t0, "right"))
            frame1.extend(surface_frame(beam, mesh.t1, "left"))
            values = {f.name: beam.value(f.name, mesh.ts) for f in fields(Section)}
            sections = [Section(**{key: float(v[i]) for key, v in values.items()}) for i in range(n)]
            self.sections.extend(sections)
            compliance.extend(section.compliance() for section in sections)
            self.meshes.append(mesh)
            ni += n+1; ei += n
        self.nn, self.ne = ni, ei
        self.rj = np.asarray(positions)
        self.ends = np.asarray(endpoints)
        self.a, self.b = self.ends.T
        self.R0a, self.R0b = np.asarray(frame0), np.asarray(frame1)
        self.S = np.asarray(compliance)
        self.k0 = log(self.R0a.transpose(0, 2, 1) @ self.R0b)
        Rbar0 = self.R0a @ exp(self.k0/2)
        self.p0a = np.concatenate([m.r0 for m in self.meshes])
        self.p0b = np.concatenate([m.r1 for m in self.meshes])
        self.offa, self.offb = self.p0a-self.rj[self.a], self.p0b-self.rj[self.b]
        self.v0 = np.einsum("nji,nj->ni", Rbar0, self.p0b-self.p0a)
        self.ds = np.concatenate([m.length for m in self.meshes])
        self.damping_times = np.concatenate([np.stack([
            m.beam.value(key,m.ts) for key in ('tdgam','tdeps','tdgam','tdeps','tdgam','tdeps')],axis=1)
            for m in self.meshes])
        self.L = max(float(np.linalg.norm(np.ptp(self.rj, axis=0))), float(max(self.ds)))
        self.F = max(1., sum(np.linalg.norm(load.get("force", [0, 0, 0])) +
                            np.linalg.norm(load.get("moment", [0, 0, 0]))/self.L for load in self.loads))
        self.weights = active_weights(model)
        self.rigid_weight_attachments = rigid_weight_attachments(model)
        weight_stations = [analysis_weight_station(model, row) for row in self.weights]
        if any(t != row[1] for row, t in zip(self.weights, weight_stations)):
            # All structural/dynamic consumers use the same analysis anchors.
            # Original records and their lossless source remain untouched.
            self.weights = [row.copy() for row in self.weights]
            for row, t in zip(self.weights, weight_stations):
                row[1] = t
        self.inertia_model = InertiaModel(model, self.meshes, allow_signed_point_weights=allow_signed_point_weights,
                                          allow_signed_distributed_weights=allow_signed_distributed_weights)
        self.F = max(self.F, sum(abs(row[5]) for row in self.weights),
                     sum(float(np.sum(np.abs(m.beam.value("mg", m.tm) + m.beam.value("Dmg", m.tm))*m.length)) for m in self.meshes))
        self.F = max(self.F, sum(abs(strut_load(row, row[2:5], tension_only=self.tension_only)["tension"]) for row in self.struts))
        for element in self.inertia_model.elements(self.meshes):
            f, m = inertial_wrench(*(element[k] for k in ("mass", "position", "inertia", "spin")),
                                   self.motion, self.gravity, model.reference[2])
            self.F = max(self.F, float(np.linalg.norm(f, axis=1).sum()+np.linalg.norm(m, axis=1).sum()/self.L))
        if condition is not None:
            rho = operating_air(model, condition)["density"]
            self.F = max(self.F, .5*rho*condition.speed**2*model.reference[0, 0])
        self.constraints = []
        count = 0
        for kind in ("ground", "joint"):
            for index, row in enumerate(model.records.get(kind, []), 1):
                typ = int(row[-1])
                if typ not in ((0, 1, 2) if kind == "ground" else (0, 1, 2, 3)):
                    raise AnalysisError(f"Unsupported {kind} constraint type {typ}.")
                i = self.node(row[0], row[1] if kind == "ground" else row[2])
                j = None if kind == "ground" else self.node(row[1], row[3])
                width = 6 if typ in (0, 3) else 3
                constraint = dict(kind=kind, type=typ, a=i, b=j, sl=slice(count, count+width))
                if typ == 3:
                    # Structural moment on beam 1: left trace at an interior
                    # station; inward trace at either endpoint. Do not replace
                    # it with the joint's free-end reaction couple (eq. 195).
                    before = np.flatnonzero(self.b == i)
                    element = int(before[-1] if len(before) else np.flatnonzero(self.a == i)[0])
                    constraint.update(law=self.hinges[index], element=element, end=bool(len(before)),
                                      beam=int(row[0]), other_beam=int(row[1]), t=float(row[2]), other_t=float(row[3]))
                self.constraints.append(constraint)
                count += width
        if not model.records.get("ground"):
            raise AnalysisError("Mounted equilibrium requires Ground constraints to define the body frame.")
        self.nc = count
        from .circulation import CirculationBasis
        self.circulation_basis = CirculationBasis(self.meshes if condition is not None else [], None if condition is None else condition.circulation_modes)
        self.ng = self.circulation_basis.size
        self.gamma_scale = condition.speed*model.reference[0, 1] if condition is not None else 1.
        self.operating = OperatingSystem(model, condition, self.motion, operating_constraints, self.L, self.F)
        self.gamma_start = 6*self.nn+6*self.ne+self.nc
        self.operating_start = self.gamma_start+self.ng
        self.size = self.operating_start+self.operating.count
        self.aero_key = self.aero_cached = None
        self.frozen_influences = FrozenInfluences(model, self.meshes) if condition is not None and condition.freeze_influences else None
        self.mass_key = self.mass_cached = None
        self.nfev = 0
        self.tangent_influences = None
        self.iteration_fields = None
        self._tangent_loads = None
        self._damping_cache = None

    def damping_report(self, *, compliance=None):
        """Reuse the material-only energy check while its matrices match.

        Physical state changes do not change this check. Compare all material
        values so in-place model edits invalidate it, and return an independent
        report so changing an exported snapshot cannot poison later results.
        """
        values = self.S if compliance is None else compliance, self.damping_times, self.ds
        cached = self._damping_cache
        if cached is None or any(not np.array_equal(a, b) for a, b in zip(values, cached[0])):
            from .damping import damping_diagnostics
            owned = tuple(np.array(value, copy=True) for value in values)
            report = damping_diagnostics(*owned)
            for value in owned:
                value.flags.writeable = False
            self._damping_cache = owned, report
        return deepcopy(self._damping_cache[1])

    def material_strain_rate(self, local_motion):
        """Rate of the selected structural formulation's strain measures."""
        return local_motion.strain_rate()

    def node(self, beam, t):
        ts, ids = self.station_nodes[int(beam)]
        at = int(np.argmin(abs(ts-t)))
        if abs(ts[at]-t) > 1e-10*max(1., abs(t)):
            raise AnalysisError("Attachment station was not inserted into the structural mesh.")
        return int(ids[at])

    def unpack(self, x):
        kin = x[:6*self.nn].reshape(self.nn, 6)
        angles = kin[:, 3:]
        Q, = self.local_maps('node_rotation', (angles,), lambda rows: (exp(angles[rows]),))
        r = self.rj+self.L*kin[:, :3]
        internal = x[6*self.nn:6*(self.nn+self.ne)].reshape(self.ne, 6)
        N, M = internal[:, :3]*self.F, internal[:, 3:]*self.F*self.L
        start = 6*(self.nn+self.ne)
        return r, Q, N, M, x[start:start+self.nc], self.circulation_basis.decode(x[self.gamma_start:self.operating_start]*self.gamma_scale)

    def local_maps(self, name, arrays, compute):
        """Pure row maps; reuse only within an explicitly enabled tangent."""
        tangent = self.tangent_influences
        if getattr(tangent, 'local_geometry', False):
            return tangent.local_rows(('network', name), arrays, compute)
        return compute(slice(None))

    def constitutive_frame(self, Ra, Rb):
        def compute(rows):
            a, b = Ra[rows], Rb[rows]
            rotation = log(a.transpose(0, 2, 1)@b)
            return rotation, a@exp(rotation/2)
        return self.local_maps('constitutive_frame', (Ra, Rb), compute)

    def geometry(self, r, Q):
        oa = np.einsum("nij,nj->ni", Q[self.a], self.offa)
        ob = np.einsum("nij,nj->ni", Q[self.b], self.offb)
        pa, pb = r[self.a]+oa, r[self.b]+ob
        Ra, Rb = Q[self.a]@self.R0a, Q[self.b]@self.R0b
        return pa, pb, Ra, Rb, oa, ob

    def deformed_meshes(self, r, Q, geometry):
        pa, pb, Ra, Rb, *_ = geometry
        out = []
        for mesh in self.meshes:
            sl = self.beam_elements[mesh.beam.index]
            a, b = self.a[sl], self.b[sl]
            original = mesh.r1-mesh.r0
            fraction = self.fractions[mesh.beam.index]
            qa, qb = Q[a], Q[b]
            def frames(rows):
                aa, bb = qa[rows], qb[rows]
                dq = log(aa.transpose(0, 2, 1)@bb)
                return (aa@exp(dq*fraction[rows, None])@mesh.frames[rows],)
            frame, = self.local_maps(('mesh_frame', mesh.beam.index),
                (qa, qb, fraction, mesh.frames), frames)
            rm = pa[sl]+fraction[:, None]*(pb[sl]-pa[sl])
            length = mesh.length*np.linalg.norm(pb[sl]-pa[sl], axis=1)/np.linalg.norm(original, axis=1)
            out.append(PanelMesh(mesh.beam, mesh.t0, mesh.t1, mesh.tm, pa[sl], pb[sl], rm,
                                 frame, length, Ra[sl], Rb[sl], mesh.ts, mesh.theta, mesh.mesh_recipe))
        return out

    def point_positions(self, r, Q):
        return [r[i]+Q[i]@(row[2:5]-self.rj[i]) for row in self.weights for i in [self.node(*row[:2])]]

    def gravity_at(self, condition):
        if self.gravity_override or condition is None:
            return self.gravity
        g = self.model.constants[0] if condition.gravity_magnitude is None else condition.gravity_magnitude
        return body_to_earth(condition.attitude).T@np.array([0.,0.,-g])

    def steady_geometry(self, r, Q):
        zero = np.zeros_like(r)
        motion = NetworkMotion(self,r,Q,zero,zero,zero,zero)
        geometry = self.geometry(r,Q)
        pa,pb,Ra,Rb,_,_ = geometry
        rotation, frame = self.constitutive_frame(Ra, Rb)
        return geometry,pb-pa,rotation,frame,self.deformed_meshes(r,Q,geometry),motion

    def external(self, r, Q, meshes, gamma, condition, motion, operating_key, *, local_motion=None, circulation_rate=None, gravity=None, _loads_only=False):
        cache = self._tangent_loads if _loads_only else None
        if cache is not None:
            # This cache is owned by one equilibrium call and enabled only
            # during its initial rank/first-load tangents. Actual state bytes
            # also distinguish every finite-difference trial, motion and load.
            cache_key = (r.tobytes(), Q.tobytes(), gamma.tobytes(), operating_key,
                         None if local_motion is None else local_motion.key(),
                         None if circulation_rate is None else np.asarray(circulation_rate).tobytes(),
                         motion.rates.tobytes(), motion.acceleration.tobytes(), motion.angular_acceleration.tobytes(),
                         None if gravity is None else np.asarray(gravity).tobytes())
            if cache_key in cache.entries:
                return cache.entries[cache_key]
        force, moment = np.zeros_like(r), np.zeros_like(r)
        element_moments = np.zeros((self.ne, 2, 3))
        element_forces = np.zeros_like(element_moments)
        point_positions = self.point_positions(r, Q)
        point_rotations = [Q[self.node(*row[:2])] for row in self.weights]
        gravity = self.gravity_at(condition) if gravity is None else np.asarray(gravity)
        if local_motion is None:
            masses = self.inertia_model.elements(meshes, point_positions, point_rotations)
        else:
            key=(r.tobytes(),Q.tobytes(),local_motion.key(),motion.rates.tobytes(),motion.acceleration.tobytes(),
                 motion.angular_acceleration.tobytes(),gravity.tobytes(),_loads_only)
            if key!=self.mass_key:
                self.mass_cached=moving_mass_loads(self,local_motion,meshes,motion,gravity,point_positions,point_rotations,
                                                  with_end_forces=True,_loads_only=_loads_only)
                self.mass_key=key
            cached_force,cached_moment,masses,cached_ends,cached_end_forces=self.mass_cached
            force,moment,element_moments=cached_force.copy(),cached_moment.copy(),cached_ends.copy()
            element_forces=cached_end_forces.copy()
        if self.quiescent_density is not None:
            if condition is not None:
                raise AnalysisError('Quiescent fluid cannot be combined with a flowing FlightCondition.')
            from .quiescent import add_loads
            add_loads(self, r, meshes, motion, local_motion, force, moment, element_forces, element_moments)
        aero = None
        if condition is not None:
            # Force/reaction perturbations do not change geometry or circulation.
            key = (r.tobytes(), Q.tobytes(), gamma.tobytes(), operating_key,
                   None if local_motion is None else local_motion.key(),
                   None if circulation_rate is None else np.asarray(circulation_rate).tobytes(), _loads_only)
            if key != self.aero_key:
                if condition.freeze_influences and self.frozen_influences is None:
                    self.frozen_influences = FrozenInfluences(self.model, self.meshes)
                ids = [self.node(*row[2:4]) for row in self.engines]
                positions = [r[i]+Q[i]@(row[4:7]-self.rj[i]) for row, i in zip(self.engines, ids)]
                self.aero_cached = evaluate_aerodynamics(self.model, condition, meshes, gamma, point_positions,
                                                        positions, Q[ids],local_motion=local_motion,circulation_rate=circulation_rate,circulation_basis=self.circulation_basis,
                                                        frozen_influences=self.frozen_influences, _loads_only=_loads_only,
                    _tangent_influences=self.tangent_influences, _iteration_fields=self.iteration_fields,
                                                        sensor_positions=[r[j]+Q[j]@(row[3:6]-self.rj[j])
                                                            for row in self.model.records.get('sensor', []) for j in [self.node(*row[1:3])]])
                self.aero_key = key
            aero = self.aero_cached

        def panel_wrench(sl, position, f, m):
            # Equal splitting preserves integrated force and moment exactly,
            # including the theta-midpoint and section-centroid lever arms.
            for end, ids in enumerate((self.a[sl], self.b[sl])):
                couple = (m+cross3(position-r[ids], f))/2
                np.add.at(force, ids, f/2)
                np.add.at(moment, ids, couple)
                element_moments[sl, end] += couple
                element_forces[sl, end] += f/2

        for mesh in meshes:
            beam, t = mesh.beam, mesh.tm
            sl = self.beam_elements[beam.index]
            if aero is not None:
                strips = aero["strips"][sl]
                if local_motion is None:
                    panel_wrench(sl, mesh.rm, np.array([s["force"] for s in strips]), np.array([s["moment"] for s in strips]))
                else:
                    if beam.lifting:
                        fractions=self.fractions[beam.index]
                        sampled_force=np.array([s['force'] for s in strips]);sampled_moment=np.array([s['moment'] for s in strips])
                    else:
                        fractions=np.array([s['force_fractions'] for s in strips])
                        sampled_force=np.array([s['force_samples'] for s in strips]);sampled_moment=np.zeros_like(sampled_force)
                    for end,(ids,fs,ms) in enumerate(local_motion.nodal_wrenches(beam.index,fractions,sampled_force,sampled_moment)):
                        np.add.at(force,ids,fs);np.add.at(moment,ids,ms)
                        element_moments[sl,end]+=ms
                        element_forces[sl,end]+=fs
        for element in masses if local_motion is None else []:
            f, m = inertial_wrench(*(element[k] for k in ("mass", "position", "inertia", "spin")),
                                   motion, gravity, self.model.reference[2])
            if element["point"] is None:
                panel_wrench(self.beam_elements[element["beam"]], element["position"], f, m)
            else:
                i = self.node(*self.weights[element["point"]][:2])
                force[i] += f[0]
                moment[i] += m[0]+cross3(element["position"][0]-r[i], f[0])
        for k, row in enumerate(self.weights):
            i = self.node(*row[:2])
            if aero is not None:
                f = np.asarray(aero["point_forces"][k])
                force[i] += f
                moment[i] += cross3(point_positions[k]-r[i], f)
        if aero is not None:
            for shoulder in aero['body_shoulders']:
                i=self.node(shoulder['beam'],shoulder['t']);f=np.asarray(shoulder['force'])
                force[i]+=f;moment[i]+=cross3(np.asarray(shoulder['position'])-r[i],f)
            for engine in aero["engines"]:
                i = self.node(engine["beam"], engine["t"])
                force[i] += engine["force"]
                moment[i] += engine["moment"]+cross3(np.asarray(engine["position"])-r[i], engine["force"])
        for load in self.loads:
            i = self.node(load["beam"], load["t"])
            force[i] += load.get("force", [0., 0., 0.])
            moment[i] += load.get("moment", [0., 0., 0.])
        result = force, moment, aero, masses, element_moments, element_forces
        if cache is not None:
            # Unconstrained trial rows consume only the circulation residual
            # and transferred loads. Keep neither mass nor strip reports for
            # every numerical perturbation.
            cached_aero = None if aero is None else dict(circulation_residual=aero['circulation_residual'])
            cache.put(cache_key, (force, moment, cached_aero, None, element_moments, element_forces))
        return result

    def custom_operating_values(self, data, values, force, moment, *, elastic_motion=None):
        """Evaluate user rows with this operator's physical section recovery."""
        from .custom_constraints import evaluate_custom
        return evaluate_custom(self, data, values, force, moment)

    def residual(self, x, factor=1., detail=False, *, elastic_motion=None, circulation_rate=None,
                 condition_override=None, motion_override=None, gravity_override=None, operating_factor=None, operating_targets=None, history_context=None, hinge_charts=None, _mechanical_data=None, _constitutive_data=None):
        """Mixed residual, optionally with nodal (u, omega, udot, omegadot).

        Steady calls use zero local motion with the same distributed mass and
        load transfer as dynamics. Supplied elastic_motion also activates the
        material strain-rate law. The caller supplies time kinematics; this
        method alone is not an unsteady solver.
        """
        self.nfev += 1
        from .hinge_history import current,checked
        chart_values=current(self) if hinge_charts is None else checked(self,hinge_charts)
        chart_by_joint={c["law"].index:v for c,v in zip((c for c in self.constraints if c["type"]==3),chart_values)}
        operating_unknowns = x[self.operating_start:]
        condition, motion, operating_values = self.operating.apply(operating_unknowns,
            condition_override=condition_override,motion_override=motion_override)
        if (self.inertia_model.signed_point_weights or self.inertia_model.signed_distributed_weights) and (condition is not None or elastic_motion is not None or
                any(np.any(getattr(motion, key)) for key in ('rates', 'acceleration', 'angular_acceleration'))):
            raise AnalysisError("Signed Weight entries are static gravity loads, not physical negative masses; dynamic or moving-frame evaluation is unavailable.")
        gravity = self.gravity_at(condition) if gravity_override is None else np.asarray(gravity_override)
        r, Q, N, M, reactions, gamma = self.unpack(x)
        # Steady and dynamic states share the same virtual-power load transfer
        # and distributed mass quadrature. A different steady nodal split would
        # leave a converged trim out of balance at zero time derivatives.
        reuse_geometry = self.tangent_influences is not None and elastic_motion is None
        if reuse_geometry:
            geometry,dr,k,Rbar,meshes,local_motion = self.tangent_influences.steady_geometry(
                self,r,Q,lambda:self.steady_geometry(r,Q))
            pa,pb,Ra,Rb,oa,ob = geometry
        else:
            zero = np.zeros_like(r)
            local_motion = NetworkMotion(self,r,Q,*((zero,zero,zero,zero) if elastic_motion is None else elastic_motion))
            geometry = self.geometry(r, Q)
            pa, pb, Ra, Rb, oa, ob = geometry
            dr = pb-pa
            k, Rbar = self.constitutive_frame(Ra, Rb)
        local = np.c_[np.einsum("nji,nj->ni", Rbar, N), np.einsum("nji,nj->ni", Rbar, M)]
        deformation = np.einsum("nij,nj->ni", self.S, local)*self.ds[:, None]
        strain_rate = np.zeros_like(deformation) if elastic_motion is None else self.material_strain_rate(local_motion)
        if elastic_motion is not None:
            if np.any(self.damping_times < 0) or not np.all(np.isfinite(self.damping_times)):
                raise AnalysisError('Material damping times must be finite and nonnegative for unsteady analysis.')
            deformation -= self.damping_times*strain_rate*self.ds[:,None]
        compatibility = np.c_[(np.einsum("nji,nj->ni", Rbar, dr)-self.v0-deformation[:, :3])/self.L,
                              k-self.k0-deformation[:, 3:]]
        if not reuse_geometry:
            meshes = self.deformed_meshes(r, Q, geometry)
        # Load/flight-path equations need nodal wrenches and frame kinematics,
        # not wake diagnostics or sensor reports. Detailed output and other
        # operating equations still request those full recovery fields.
        from .structured_static import load_kinematic_constraints
        loads_only = not detail and load_kinematic_constraints(self)
        fext, mext, aero, masses, element_moments, element_forces = self.external(r, Q, meshes, gamma, condition, motion,(operating_unknowns.tobytes(),repr(condition)),
            local_motion=local_motion,circulation_rate=circulation_rate,gravity=gravity,
            _loads_only=loads_only)
        if loads_only and any(c.quantity=='flight_path' for c in self.operating.constraints):
            # This is the same condition-only calculation as the full aero
            # report; elastic pose and circulation do not enter flight path.
            aero={**aero,'earth_state':condition.earth_state(self.model)}
        if (self.iteration_fields is not None and self.iteration_fields.phase == 'capture'
                and self.iteration_fields.capture_circulation):
            self.iteration_fields.circulation_mechanics = dict(r=r, Q=Q, N=N, M=M,
                meshes=meshes, local_motion=local_motion, element_moments=element_moments)
        total_force = fext.sum(axis=0)
        total_moment = (mext+cross3(r-self.model.reference[1], fext)).sum(axis=0)
        if getattr(self.iteration_fields, 'capture_frame_loads', False):
            self.iteration_fields.frame_loads = np.c_[fext, mext+cross3(r-self.model.reference[1], fext)]
        custom_values=None
        if self.operating.custom:
            custom_values=self.custom_operating_values(dict(r=r,Q=Q,N=N,M=M,section_frame=Rbar,
                aero=aero,condition=condition,motion=motion,gravity=gravity,local_motion=local_motion,
                element_forces=element_forces,element_moments=element_moments,
                strain_rate=strain_rate,
                mechanical_strain=None if elastic_motion is None else np.c_[np.einsum('nji,nj->ni',Rbar,dr)-self.v0,k-self.k0]/self.ds[:,None]),
                operating_values,total_force,total_moment,elastic_motion=elastic_motion)
        operating_residual, operating_report = self.operating.evaluate(total_force, total_moment, aero, condition,
            factor if operating_factor is None else operating_factor, motion=motion, values=operating_values, targets=operating_targets,custom_values=custom_values,history_context=history_context)
        f, m = fext*factor, mext*factor
        strut_report = []
        for row in self.struts:
            i = self.node(*row[:2])
            position = r[i]+Q[i]@(row[2:5]-self.rj[i])
            # Passive stiffness remains present at zero external load. Only
            # dLo is continued, so an axial brace can remove a mechanism.
            state = strut_load(row, position, tension_only=self.tension_only, factor=factor)
            # A local geometry partial may receive this same strut tangent
            # analytically. Still evaluate the physical law and branch checks.
            if not getattr(self.iteration_fields, 'omit_strut_loads', False):
                f[i] += state["force"]
                m[i] += cross3(position-r[i], state["force"])
            if detail:
                strut_report.append(dict(beam=int(row[0]), t=float(row[1]), node=i,
                                          **{k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in state.items()}))
        omit_mechanics = bool(getattr(self.iteration_fields, "omit_stationary_mechanics", False))
        if not omit_mechanics:
            np.add.at(f, self.a, N); np.add.at(f, self.b, -N)
            np.add.at(m, self.a, M+cross3(dr, N)/2+cross3(oa, N))
            np.add.at(m, self.b, -M+cross3(dr, N)/2-cross3(ob, N))
        capture_mechanics=_mechanical_data is not None
        constraints, reaction_report, hinge_report = [], [], []
        for c in self.constraints:
            i, j, typ = c["a"], c["b"], c["type"]
            v = reactions[c["sl"]]
            F = v[:3]*self.F if typ != 2 else np.zeros(3)
            T = v[-3:]*self.F*self.L if typ != 1 else np.zeros(3)
            if j is None:
                if typ != 2:
                    constraints.extend((r[i]-self.rj[i])/self.L)
                if typ != 1:
                    constraints.extend(log(Q[i]))
                if not omit_mechanics:f[i] += F; m[i] += T
            else:
                d = r[j]-r[i]
                if typ != 2:
                    constraints.extend((d-Q[i]@(self.rj[j]-self.rj[i]))/self.L)
                if typ != 1:
                    relative = Q[i].T@Q[j]
                    if typ == 3:
                        e, end, law = c["element"], c["end"], c["law"]
                        sign = -1 if end else 1
                        offset = ob[e] if end else oa[e]
                        structural = M[e]+sign*cross3(dr[e], N[e])/2+cross3(offset, N[e])
                        structural += sign*factor*element_moments[e, int(end)]
                        axis = Q[i]@law.axis
                        mh = structural@axis
                        chart = chart_by_joint[law.index]
                        hinge_vector = log(exp(-chart*law.axis)@relative)-(law.angle(mh, factor)-chart)*law.axis
                        if detail:
                            hinge_report.append(dict(**law.report(mh, axis), node=i, other_node=j,
                                                     **{key: c[key] for key in ("beam", "other_beam", "t", "other_t")},
                                                     moment_trace="left" if end else "right"))
                        elif capture_mechanics:
                            hinge_report.append(dict(joint=law.index,structural_moment=float(mh)))
                    constraints.extend(hinge_vector if typ == 3 else log(relative))
                if not omit_mechanics:
                    f[i] += F; f[j] -= F
                    m[i] += T+cross3(d, F); m[j] -= T
            if detail:
                reaction_report.append(dict(kind=c["kind"], type=typ, node=i, other_node=j,
                                            force=F.tolist(), moment=(T if j is None else T+cross3(d, F)).tolist(),
                                            other_force=None if j is None else (-F).tolist(),
                                            other_moment=None if j is None else (-T).tolist()))
        if omit_mechanics:
            compatibility=np.zeros_like(compatibility)
            constraints=np.zeros(len(constraints))
        residual = np.r_[compatibility.ravel(), (f/self.F).ravel(), (m/(self.F*self.L)).ravel(), constraints,
                         [] if aero is None else aero["circulation_residual"], operating_residual]
        if capture_mechanics:
            # Retain only data already computed by this residual. Requesting
            # detailed output here would also compute wake/sensor diagnostics
            # during every Newton matrix build.
            _mechanical_data.update(r=r,Q=Q,section_frame=Rbar,hinges=hinge_report,hinge_charts=chart_by_joint)
        if _constitutive_data is not None:
            # Alternate constitutive equations need these physical unknowns,
            # without requesting wake/sensor/output recovery on Newton probes.
            _constitutive_data.update(r=r, Q=Q, N=N, M=M, strain_rate=strain_rate)
        if detail:
            damping = None
            if elastic_motion is not None:
                damping = self.damping_report()
            return residual, dict(r=r, Q=Q, N=N, M=M, section_frame=Rbar, meshes=meshes, aero=aero,
                                  distributed_mass_force=self.mass_cached[-1].sum(axis=1),
                                  local_motion=local_motion, element_forces=element_forces, element_moments=element_moments,
                                  mechanical_strain=None if elastic_motion is None else np.c_[np.einsum('nji,nj->ni',Rbar,dr)-self.v0,k-self.k0]/self.ds[:,None],
                                  strain_rate=strain_rate, damping_times=self.damping_times,
                                  damping=damping,
                                  force=fext, moment=mext, reactions=reaction_report, masses=masses,
                                  struts=strut_report, hinges=hinge_report, hinge_charts=chart_by_joint,
                                  gravity=gravity,condition=condition,motion=motion,
                                  operating_values=operating_values, operating_constraints=operating_report)
        return residual

    def jacobian(self, x, factor, *, progress=None, _load_cache=None, _direct_mechanics=True, _direct_circulation=True, _direct_geometry=None, _sparse=False, **residual_options):
        from .tangent_influences import TangentInfluences
        from .source_discrete import SourceDiscreteNetwork
        from .source_coupled import SourceCoupledNetwork
        from .source_airflow import SourceAirflowNetwork
        previous = self.tangent_influences
        previous_loads, self._tangent_loads = self._tangent_loads, _load_cache
        direct_geometry = (getattr(self,'_frequency_local_geometry',False)
                           if _direct_geometry is None else _direct_geometry)
        if _direct_geometry is None and type(self) is SourceAirflowNetwork and self.steady_trim:
            from .structured_static import load_kinematic_constraints
            # Reuse the complete local-plus-induced-field derivative for
            # ordinary trim. All operating-variable columns and unsupported
            # target types retain their full-residual path.
            direct_geometry = direct_geometry or load_kinematic_constraints(self)
        _direct_mechanics = _direct_mechanics and (self.analytic_mechanics or isinstance(self, SourceDiscreteNetwork))
        direct_geometry = direct_geometry and (self.analytic_mechanics or
            type(self) in (SourceCoupledNetwork, SourceAirflowNetwork))
        self.tangent_influences = TangentInfluences(local_geometry=direct_geometry)
        self.aero_key = None  # Populate from this tangent's base state.
        try:
            from .wall_root import wall_root_derivatives
            with wall_root_derivatives(self, x,
                    condition_override=residual_options.get('condition_override'),
                    motion_override=residual_options.get('motion_override')):
                return self._jacobian(x, factor, progress=progress, direct_mechanics=_direct_mechanics,
                                      direct_circulation=_direct_circulation, direct_geometry=direct_geometry,
                                      sparse=_sparse, **residual_options)
        finally:
            self.tangent_influences = previous
            self._tangent_loads = previous_loads

    def _jacobian(self, x, factor, *, progress=None, direct_mechanics=True, direct_circulation=True, direct_geometry=False, sparse=False, **residual_options):
        # Absolute dimensionless steps are essential at rigid limits: MINPACK's
        # relative-only perturbations of roundoff-sized displacements disappear
        # when added to a finite jig position, falsely zeroing Jacobian columns.
        completed = reported = 0
        if progress is not None:
            progress('static_tangent', 0, self.size)
        def advanced(count):
            nonlocal completed, reported
            completed += count
            if progress is not None and (completed == self.size or completed-reported >= 16):
                progress('static_tangent', completed, self.size)
                reported = completed
        mechanical_data={} if direct_mechanics else None
        base = self.residual(x, factor, _mechanical_data=mechanical_data, **residual_options)
        if sparse:
            from scipy.sparse import csc_matrix,hstack
            pieces={}
        else:
            jac = np.zeros((self.size, self.size))
        assembled = set()
        self.circulation_derivative_diagnostics = dict(method='forward differences', fallback=None)
        # Mounted full corrections, harmonic startup and response construction
        # share the complete geometry decomposition. Explicitly disabling it
        # retains the original full-residual stencil for independent checks.
        # The final Newton matrix is not assumed to
        # belong to the converged state or to the dynamic rotation chart.
        if direct_geometry and not residual_options and self.condition is not None:
            from .geometry_tangent import geometry_columns, GeometryDerivativeUnavailable
            capture = {} if direct_circulation and self.ng else None
            try:
                geometry, diagnostics = geometry_columns(self,
                    lambda delta:self.residual(x+delta,factor),lambda delta:x+delta,
                    np.maximum(1.,abs(x)),step=1e-6,factor=factor,difference_order=1,_nodewise_state=True,
                    _direct_vortex=True,_direct_volume=True,_direct_geometry=True,
                    # Source compatibility remains in its complete local
                    # residual probes; never substitute midpoint beam columns.
                    _direct_structural=self.analytic_mechanics,
                    _captured_fields=capture,
                    progress=None if progress is None else lambda done,total:progress('static_tangent',done,self.size))
            except GeometryDerivativeUnavailable as exc:
                self.geometry_derivative_diagnostics = dict(method='original full residual differences',fallback=str(exc))
            else:
                if sparse:pieces[0]=geometry
                else:jac[:,:6*self.nn] = geometry.toarray()
                assembled.update(range(6*self.nn));advanced(6*self.nn)
                self.geometry_derivative_diagnostics = diagnostics
                if capture is not None:
                    from .circulation_tangent import circulation_columns, CirculationDerivativeUnavailable
                    try:
                        # The geometry capture belongs to exactly this state,
                        # condition and load factor. Reuse its influence and
                        # load data for the same direct block as sparse Newton
                        # and Bode, without probing each circulation unknown.
                        circulation = circulation_columns(self, capture['fields'], factor)
                    except CirculationDerivativeUnavailable as exc:
                        self.circulation_derivative_diagnostics['fallback'] = str(exc)
                    else:
                        if sparse:pieces[self.gamma_start]=csc_matrix(circulation)
                        else:jac[:, self.gamma_start:self.operating_start] = circulation
                        assembled.update(range(self.gamma_start, self.operating_start))
                        advanced(self.ng)
                        self.circulation_derivative_diagnostics['method'] = 'direct fixed-geometry blocks'
                    finally:
                        capture.clear()
        # Source pose derivatives still use complete physical stencils. Their
        # fixed-geometry circulation columns need not repeat those stencils.
        # This capture is confined to the same state/factor, with no load cache,
        # rate overrides or outer lagged-field context. It never freezes fields
        # in the remaining geometry columns.
        from .source_discrete import SourceDiscreteNetwork
        if (isinstance(self, SourceDiscreteNetwork) and direct_circulation and self.ng
                and self.gamma_start not in assembled and not residual_options
                and self.iteration_fields is None and self._tangent_loads is None):
            from .structured_static import linearization, StructuredTangentUnavailable
            from .circulation_tangent import circulation_columns, CirculationDerivativeUnavailable
            try:
                with linearization(self, x, factor, capture_circulation=True) as (fields, _):
                    circulation = circulation_columns(self, fields, factor)
            except (StructuredTangentUnavailable, CirculationDerivativeUnavailable) as exc:
                self.circulation_derivative_diagnostics['fallback'] = str(exc)
            else:
                if sparse:pieces[self.gamma_start]=csc_matrix(circulation)
                else:jac[:,self.gamma_start:self.operating_start]=circulation
                assembled.update(range(self.gamma_start,self.operating_start))
                advanced(self.ng)
                self.circulation_derivative_diagnostics['method']='direct fixed-geometry blocks'
        mechanical=None
        self.mechanical_derivative_diagnostics=dict(method='original residual differences',fallback=None)
        if direct_mechanics:
            from .mechanical_tangent import network_mechanical_columns,source_network_mechanical_columns,MechanicalDerivativeUnavailable
            try:
                builder=network_mechanical_columns
                if isinstance(self, SourceDiscreteNetwork):
                    from .source_dynamics import SourceDynamicNetwork
                    if getattr(self.constitutive_motion,'__func__',None) not in (
                            SourceDiscreteNetwork.constitutive_motion,SourceDynamicNetwork.constitutive_motion):
                        raise MechanicalDerivativeUnavailable('Unknown source rate-dependent constitutive law.')
                    builder=source_network_mechanical_columns
                mechanical,diagnostics=builder(self,mechanical_data,
                    np.maximum(1.,abs(x)),1e-6,factor=factor)
            except MechanicalDerivativeUnavailable as exc:
                self.mechanical_derivative_diagnostics['fallback']=str(exc)
            else:
                if sparse:
                    if mechanical.shape[1]:pieces[6*self.nn]=mechanical
                else:
                    block=mechanical.tocoo()
                    jac[block.row,6*self.nn+block.col]=block.data
                assembled.update(range(6*self.nn,self.gamma_start))
                advanced(self.gamma_start-6*self.nn)
                self.mechanical_derivative_diagnostics=diagnostics
        internal_start, internal_end = 6*self.nn, 6*(self.nn+self.ne)
        # Each internal wrench touches its element's compatibility equations
        # and its two endpoint balances. Alternating elements have disjoint
        # rows, so their original finite differences can share one evaluation.
        # Custom targets and sprung hinges can read those wrenches elsewhere;
        # preserve the general column-by-column path for either case.
        grouped = mechanical is None and not self.operating.custom and not any(c['type'] == 3 for c in self.constraints)
        groups = [np.concatenate([np.arange(sl.start+parity, sl.stop, 2)
                                  for sl in self.beam_elements.values()]) for parity in (0, 1)]
        grouped = grouped and all(np.unique(self.ends[elements]).size == 2*len(elements)
                                  for elements in groups)
        if grouped:
            for elements in groups:
                if not len(elements):
                    continue
                rows = np.concatenate([
                    6*elements[:,None]+np.arange(6),
                    6*self.ne+3*self.a[elements,None]+np.arange(3),
                    6*self.ne+3*self.b[elements,None]+np.arange(3),
                    6*self.ne+3*self.nn+3*self.a[elements,None]+np.arange(3),
                    6*self.ne+3*self.nn+3*self.b[elements,None]+np.arange(3)], axis=1)
                for component in range(6):
                    columns = internal_start+6*elements+component
                    h = 1e-6*np.maximum(1., np.abs(x[columns]))
                    trial = x.copy(); trial[columns] += h
                    difference = self.residual(trial, factor, **residual_options)-base
                    values=difference[rows]/h[:,None]
                    if sparse:
                        for column,rr,vv in zip(columns,rows,values):
                            pieces[int(column)]=csc_matrix((vv,(rr,np.zeros(len(rr),dtype=int))),shape=(self.size,1))
                    else:jac[rows,columns[:,None]] = values
                    advanced(len(columns))
        for j in range(self.size):
            if j in assembled:
                continue
            if grouped and internal_start <= j < internal_end:
                continue
            h = 1e-6*max(1., abs(x[j]))
            trial = x.copy(); trial[j] += h
            values=(self.residual(trial, factor, **residual_options)-base)/h
            if sparse:pieces[j]=csc_matrix(values[:,None])
            else:jac[:, j] = values
            advanced(1)
        if sparse:
            # Blocks cover disjoint complete column ranges. Preserve every
            # nonzero, including roundoff-sized entries; no dropping threshold.
            blocks=[];width=0
            for start,block in sorted(pieces.items()):
                if start!=width:raise RuntimeError('Incomplete or overlapping sparse Newton columns.')
                blocks.append(block);width+=block.shape[1]
            if width!=self.size:raise RuntimeError('Incomplete sparse Newton matrix.')
            jac=hstack(blocks,format='csc');jac.eliminate_zeros();jac.sort_indices()
        return jac


def equilibrate(network, tolerance=1e-8, continuation_steps=4, *, initial_state=None, progress=None, **residual_options):
    """Use sparse mechanics for supported steady operating targets."""
    from .structured_static import steady_cache_progress, structured_steady_constraints
    if (structured_steady_constraints(network) and initial_state is None
            and not residual_options):
        from .structured_static import equilibrate as structured_equilibrate, StructuredTangentUnavailable
        try:
            return structured_equilibrate(network, tolerance, continuation_steps,
                                          progress=progress)
        except StructuredTangentUnavailable:
            pass
    return _equilibrate_full(network, tolerance, continuation_steps,
                            initial_state=initial_state, progress=steady_cache_progress(network, progress),
                            **residual_options)


def _equilibrate_full(network, tolerance=1e-8, continuation_steps=4, *, initial_state=None, progress=None, **residual_options):
    """Load continuation for the common steady or zero-rate unsteady residual."""
    if not np.isfinite(tolerance) or not 0 < tolerance <= 1e-5:
        raise AnalysisError("Equilibrium tolerance must be positive and no greater than 1e-5.")
    if not isinstance(continuation_steps, int) or continuation_steps < 1:
        raise AnalysisError("At least one continuation step is required.")
    if isinstance(initial_state,dict) and initial_state.get('feedback') is not None:
        raise AnalysisError('A controller equilibrium seed requires the matching controller definition.')
    if progress is not None:
        progress('static_load', 0., 1.)
    from .rigid_initial_rank import reject_redundant_rigid_constraints
    reject_redundant_rigid_constraints(network)
    if network.operating.minimum_indices:
        from .control_allocation import equilibrate_allocation
        return equilibrate_allocation(network,tolerance,continuation_steps,initial_state,residual_options)
    if network.operating.custom:
        from .custom_constraints import equilibrate_custom
        return equilibrate_custom(network,tolerance,continuation_steps,initial_state,residual_options)
    if initial_state is not None:
        from .equilibrium_state import correct
        return correct(network,initial_state,tolerance,residual_options,progress=progress)
    model, condition = network.model, network.condition
    x = np.zeros(network.size)
    if condition is not None:
        if progress is not None: progress('static_initial_airflow',0,network.ng)
        initial = evaluate_aerodynamics(model, condition, network.meshes, frozen_influences=network.frozen_influences,
                                        _circulation_progress=progress)
        physical = np.array([s["circulation"] for s in initial["strips"] if s["lifting"]])
        x[network.gamma_start:network.operating_start] = network.circulation_basis.encode(physical)/network.gamma_scale
    # Explicit tangent rank check catches unrestrained mechanisms even when
    # zero loading makes their residual identically zero at the initial guess.
    from .tangent_influences import TangentLoads
    initial_loads = TangentLoads() if not network.operating.constraints and not residual_options else None
    initial_x = x.copy()
    if progress is not None: progress('static_rank_assembly',0,network.size)
    jac = network.jacobian(x, 0., progress=progress, _load_cache=initial_loads, **residual_options)
    if progress is not None: progress('static_rank_svd',0,network.size)
    norms = np.linalg.norm(jac, axis=0)
    singular = np.linalg.svd(jac/np.maximum(norms, 1e-30), compute_uv=False)
    if singular[-1] < 1e-10*singular[0]:
        raise AnalysisError("Constraints leave a mechanism or redundant reactions/operating targets; check Ground, Joint and operating definitions.")
    reached, step = 0., 1./continuation_steps
    steps = 0
    # Finite stiffness and elastic restraints retain fresh stage tangents:
    # small changes in Newton history can affect near-zero moment precision.
    reuse_stage_tangent = (network.condition is not None and not network.operating.constraints
                           and not residual_options and not np.any(network.S)
                           and not network.hinges and not network.struts)
    previous_tangent = None
    while reached < 1-1e-12:
        target = min(1., reached+step)
        failure = ''
        if progress is not None:
            progress('static_load', target, 1.)
        # Rigid mounted continuation can start an intermediate stage with
        # the preceding Newton tangent. MINPACK updates its local model and can
        # request a fresh tangent at a changed state. Rank checking, the first
        # loaded stage and the final physical load always use fresh tangents.
        # Bound the warm attempt; failure retries this same stage with a
        # fresh tangent and the original evaluation budget.
        if target == 1.:
            previous_tangent = None
        tangent_state = x.copy() if previous_tangent is not None else None
        tangent_value = None if previous_tangent is None else previous_tangent.copy()
        def tangent(state):
            nonlocal tangent_state, tangent_value
            if tangent_state is None or not np.array_equal(state, tangent_state):
                tangent_value = network.jacobian(state, target, progress=progress,
                    _load_cache=initial_loads if reached == 0. and np.array_equal(state, initial_x) else None,
                    **residual_options).copy()
                tangent_state = state.copy()
                if progress is not None:
                    progress('static_load', target, 1.)
            return tangent_value.copy()
        for attempt in range(2 if previous_tangent is not None else 1):
            if attempt:
                tangent_state = tangent_value = None
            try:
                solution = root(lambda state: network.residual(state, target, **residual_options), x, method="hybr",
                                jac=tangent,
                                options={"xtol": min(1e-9, tolerance/10), "maxfev": 50 if previous_tangent is not None and not attempt else 6*network.size+200})
                error = float(np.max(np.abs(network.residual(solution.x, target, **residual_options))))
            except GroundIntersectionError as exc:
                error = np.inf
                failure = ' '+str(exc)
            except AnalysisError:
                if previous_tangent is None or attempt:
                    raise
                error = np.inf
            if error <= tolerance and np.all(np.isfinite(solution.x)):
                break
        if error <= tolerance and np.all(np.isfinite(solution.x)):
            initial_loads = None
            x = solution.x; reached = target; steps += 1
            previous_tangent = tangent_value.copy() if reuse_stage_tangent else None
            step = min(1./continuation_steps, step*1.5)
        else:
            previous_tangent = None
            step /= 2
            if step < 1/256:
                raise AnalysisError(f"Coupled equilibrium did not converge at load fraction {target:.4f}; residual {error:.3g}.{failure}")
    return x, steps


def network_result(network, x, *, sensor_frame=None, **residual_options):
    """Independent, JSON-ready snapshot of the common network state."""
    residual, data = network.residual(x, detail=True, **residual_options)
    result = network_snapshot(network, residual, data, sensor_frame=sensor_frame)
    if network.frozen_influences is not None:
        warning = network.frozen_influences.capacity_warning()
        if warning is not None:
            result['frozen_influence_cache_warning'] = warning
    return result


def network_snapshot(network, residual, data, *, sensor_frame=None, linear_output=False):
    """Recover outputs from one explicitly supplied physical evaluation.

    Data belongs to this evaluation, not a last-state cache. Callers that also
    need controller outputs can use the same loads without evaluating twice.
    Linear output stencils only need endpoint traces at sensor anchors.
    """
    model = network.model
    r, Q = data["r"], data["Q"]
    applied_force = data["force"].sum(axis=0)
    applied_moment = (data["moment"]+cross3(r-model.reference[1], data["force"])).sum(axis=0)
    support_force, support_moment = np.zeros(3), np.zeros(3)
    for reaction in data["reactions"]:
        if reaction["kind"] == "ground":
            support_force += reaction["force"]
            support_moment += reaction["moment"]+cross3(r[reaction["node"]]-model.reference[1], reaction["force"])
    # A body-fixed strut anchor is a support. Collinear axial force can be
    # transferred to that anchor without changing the total moment.
    for strut in data["struts"]:
        support_force += strut["force"]
        support_moment += cross3(np.asarray(strut["anchor"])-model.reference[1], strut["force"])
    aero = data['aero']
    if aero is None:
        result = {}
    elif linear_output:
        # These stencils read aerodynamic outputs and discard the snapshot.
        # Only section-reaction recovery writes into the aerodynamic data.
        result = dict(aero, strips=[row.copy() for row in aero['strips']],
                      section_output_definitions=aero['section_output_definitions'].copy())
    else:
        result = deepcopy(aero)
    if aero is not None:
        reaction_sampling = ('Network analysis: eight-point material mass quadrature with current elastic and rigid kinematics, summed per interval and divided by current length. Point masses excluded.'
            if 'source_discrete' not in data else
            'Source mounted analysis: endpoint-averaged distributed gravity force per interval divided by current aerodynamic interval length. Point masses excluded.')
        _add_section_reactions(result, data['meshes'],
            {mesh.beam.index:data['distributed_mass_force'][network.beam_elements[mesh.beam.index]]
             for mesh in data['meshes']},
            reaction_sampling)
    elements, structure = recover_structure(network, data, sensor_traces_only=linear_output)
    result.update(analysis="constrained_static" if network.operating.count else "mounted_static", converged=True, residual=float(np.max(abs(residual))),
                  evaluations=network.nfev, structural_nodes=network.nn,
                  structural_elements=network.ne, geometry=geometry_summary(model, meshes=data["meshes"]),
                  **({} if linear_output else dict(mesh_discretization=mesh_report(
                      model, network.meshes, network.panels, network.loads))),
                  max_displacement=float(np.max(np.linalg.norm(r-network.rj, axis=1))),
                  max_rotation_deg=float(np.rad2deg(np.max(np.linalg.norm(log(Q), axis=1)))),
                  reactions=data["reactions"], applied_force=applied_force.tolist(), applied_moment=applied_moment.tolist(),
                  struts=data["struts"], strut_mode="wire" if network.tension_only else "bilateral", hinges=data["hinges"],
                  mass_properties=network.inertia_model.summary(data["masses"]),
                  gravity_body=data['gravity'].tolist(),
                  gravity_source="body_vector_override" if network.gravity_override else "Earth_magnitude",
                  operating_values=data["operating_values"], operating_constraints=data["operating_constraints"],
                  support_force=support_force.tolist(), support_moment=support_moment.tolist(),
                  force_balance=(applied_force+support_force).tolist(), moment_balance=(applied_moment+support_moment).tolist(),
                  nodes=[dict(index=int(i), beam=beam.index, t=float(t), position=r[i].tolist(), jig_position=network.rj[i].tolist(),
                              rotation=Q[i].tolist()) for beam in model.beams
                         for t, i in zip(*network.station_nodes[beam.index])],
                  elements=elements, structure=structure,
                  limitations=["Quasi-steady snapshot with prescribed or force/moment-constrained motion; use time analysis to evolve a trajectory.",
                               "SO(3) midpoint beam discretization; refine the mesh to assess solution accuracy. ASWING discrete parity is unverified.",
                               "Rigid/pinned/roller/sprung joints, axial struts, body/point-volume flow and engine types 0/1/2 are supported.",
                               "Struts use an explicit bilateral or tension-only wire law; buckling loads are not specified by ASW input. See the numerical notes for formula ambiguities.",
                               "CDi and span efficiency use the frozen straight Trefftz wake; total CD and load balance use near-field forces, including CDi_near."])
    if 'source_discrete' in data:
        from .source_discrete import source_output_metadata, SECTION_POLICY, COUPLED_POLICY
        result.update(source_output_metadata(network))
        if network.structural_operator in (SECTION_POLICY, COUPLED_POLICY):
            mass_scope = result['mass_properties'].get('scope', '')
            result['mass_properties'].update(inertia_reference=None, inertia_cg=None,
                spatial_matrix=None, spin_angular_momentum=None, dynamic_inertia_available=False,
                scope=(mass_scope+' Static mass and first moment for endpoint-averaged gravity; no dynamic inertia or spin model for this operator.').strip())
        elif getattr(network, 'source_dynamic', False):
            result['mass_properties'].update(inertia_reference=None, inertia_cg=None,
                spatial_matrix=None, spin_angular_momentum=None, dynamic_inertia_available=True,
                scope='Mass and first moment describe the source gravity rule. Dynamic inertia uses the endpoint-product descriptor operator, including section and point inertia. No single symmetric aggregate spatial tensor is asserted for this finite-difference rule.')
    if network.quiescent_density is not None:
        from .quiescent import report
        result['fluid'] = report(network, data['meshes'])
    if network.rigid_weight_attachments:
        result['rigid_weight_attachments'] = deepcopy(network.rigid_weight_attachments)
        result['limitations'].append(RIGID_ATTACHMENT_SCOPE)
    from .sensors import network_sensors, source_sensor_limitations, UNITS, LIMITATIONS
    result['sensors'] = network_sensors(network, data, elements, sensor_frame)
    result['sensor_metadata'] = dict(units=UNITS, limitations=LIMITATIONS)
    if 'source_discrete' in data:
        result['sensor_metadata'] = dict(units=UNITS, limitations=source_sensor_limitations(network, data))
    if getattr(network,'control_allocation',None) is not None:
        result['control_allocation']=deepcopy(network.control_allocation)
    if getattr(network,'custom_trim',None) is not None:
        result['custom_trim']=deepcopy(network.custom_trim)
    result["attachments"] = attachment_geometry(model, result["nodes"])
    if data["hinges"]:
        result["limitations"].append("Jangle uses natural cubic splines and the beam-1 inward endpoint/left interior structural-moment trace. ASWING spline/interior-joint trace parity and offset/interior hinge passivity are unverified; discontinuous angle jumps are unsupported. Equilibrium convergence does not establish static or dynamic stability.")
    if result.get('body_shoulders'):
        from .body_shoulders import LIMITATION
        result['limitations'].append(LIMITATION)
    result['limitations']+=result.get('ground_plane',{}).get('limitations',[])
    if result.get('gust', {}).get('type', 'none') != 'none':
        from .gust import LIMITATIONS as GUST_LIMITATIONS
        result['limitations'] += GUST_LIMITATIONS
    return result


def solve_static(model, condition=None, panels=24, *, gravity=None, loads=(), tolerance=1e-8,
                 continuation_steps=4, motion=None, operating_constraints=(), strut_mode="bilateral", derivatives=None, controller=None,
                 initial_state=None, progress=None, allow_signed_point_weights=False, allow_signed_distributed_weights=False):
    """Solve mounted equilibrium. Loads are body-axis dead nodal force/moment.

    Explicit gravity is a body-axis override; the default rotates Earth gravity
    into the prescribed/solved aircraft attitude. Ground types 0/1/2
    and joint types 0/1/2/3 are supported. Steady body rates and accelerations are
    specified in FlightCondition, or Motion for a structural-only calculation.

    allow_signed_point_weights and allow_signed_distributed_weights explicitly
    permit signed gravity-loading devices in an air-free, zero-motion static calculation. Their signed
    mass bookkeeping is not a physical inertia model and cannot launch time
    integration. Ordinary physical mass validation remains the default.

    Optional progress(stage, current, total) reports static_tangent columns and
    static_load continuation targets. Eligible saved-state corrections also
    report equilibrium_tangent and equilibrium_rank columns, or an indeterminate
    equilibrium_rank_svd check. Controller, custom-target and allocation paths
    currently report only an initial static_load.
    """
    if (allow_signed_point_weights or allow_signed_distributed_weights) and (controller is not None or derivatives is not None):
        raise AnalysisError("Signed static Weight loading does not support controllers or aerodynamic derivatives.")
    if controller is not None:
        if progress is not None:
            progress('static_load', 0., 1.)
        from .steady_feedback import solve_feedback_base
        network, state, feedback, options, steps, diagnostics = solve_feedback_base(model, condition, panels,
            controller=controller, gravity=gravity, loads=loads, motion=motion,
            operating_constraints=operating_constraints, tolerance=tolerance,
            continuation_steps=continuation_steps, strut_mode=strut_mode,initial_state=initial_state)
        result = network_result(network, state.x, **options)
        _, data = network.residual(state.x, detail=True, **options)
        residual, result['feedback'] = feedback.evaluate(state, data, np.zeros(feedback.size))
        result.update(controller=feedback.report(), continuation_steps=steps, controller_equilibrium=diagnostics,
                      residual=max(result['residual'], float(np.max(abs(residual)))))
        from .equilibrium_state import capture
        result['equilibrium_initialization']=diagnostics
        result['equilibrium_state']=capture(network,state.x,feedback=feedback,feedback_values=state.feedback,
            commands=result['feedback']['commands'],residual=result['residual'])
        if derivatives is not None:
            from .derivatives import linearize_equilibrium
            result['derivatives']=linearize_equilibrium(network,state.x,feedback=feedback,feedback_state=state,**derivatives)
        return result
    from .equilibrium_state import warm_start_recipe
    network = StaticNetwork(model, panels, condition, gravity, loads, motion, operating_constraints, strut_mode,
                            allow_signed_point_weights=allow_signed_point_weights,
                            allow_signed_distributed_weights=allow_signed_distributed_weights,
                            mesh_recipe=warm_start_recipe(model, panels, initial_state))
    x, steps = equilibrate(network, tolerance, continuation_steps,initial_state=initial_state,progress=progress)
    result = network_result(network, x)
    result["continuation_steps"] = steps
    from .equilibrium_state import capture
    signed = bool(network.inertia_model.signed_point_weights or network.inertia_model.signed_distributed_weights)
    result['equilibrium_state']=capture(network,x,residual=result['residual'],include_launch=not signed)
    if signed:
        note = "Signed Weight, mg and Dmg entries specify static gravity forces at rotating pylon endpoints or section centroids. Mass properties are algebraic bookkeeping; this state cannot initialize physical dynamics."
        result['limitations'].append(note)
        result['equilibrium_state']['limitations'].append(note)
    result['equilibrium_initialization']=getattr(network,'equilibrium_diagnostics',dict(initialization='undeformed load continuation'))
    if derivatives is not None:
        from .derivatives import linearize_equilibrium
        result['derivatives'] = linearize_equilibrium(network, x, **derivatives)
    return result
