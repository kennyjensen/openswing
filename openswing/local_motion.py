"""Elastic motion in a moving aircraft frame, with objective SO(3) interpolation.

Relative velocities and their time derivatives have body-axis components.
Absolute acceleration includes Coriolis transport; absolute angular acceleration
also includes Omega cross omega. See unsteady theory §§1–6.
"""
from dataclasses import dataclass
import numpy as np
from .vector_ops import cross3
from scipy.spatial.transform import Rotation
from .structure import skew


def rotation_vector(matrix):
    matrix = np.asarray(matrix)
    return Rotation.from_matrix(matrix.reshape(-1,3,3)).as_rotvec().reshape(matrix.shape[:-2]+(3,))


def rotation_matrix(vector):
    vector = np.asarray(vector)
    return Rotation.from_rotvec(vector.reshape(-1,3)).as_matrix().reshape(vector.shape[:-1]+(3,3))


def left_jacobian(vector, derivative=None):
    """SO(3) left Jacobian, or its exact directional derivative."""
    vector = np.asarray(vector,dtype=float)
    x = np.sum(vector**2,axis=-1)
    small = x < 1e-4
    safe = np.where(small,1.,x);theta = np.sqrt(safe)
    a = np.where(small,.5-x/24+x*x/720-x**3/40320,(1-np.cos(theta))/safe)
    b = np.where(small,1/6-x/120+x*x/5040-x**3/362880,(theta-np.sin(theta))/(safe*theta))
    k = skew(vector);kk = k@k
    if derivative is None:
        return np.eye(3)+a[...,None,None]*k+b[...,None,None]*kk
    da = np.where(small,-1/24+x/360-x*x/13440,
                  (theta*np.sin(theta)-2*(1-np.cos(theta)))/(2*safe**2))
    db = np.where(small,-1/120+x/2520-x*x/120960,
                  (theta*(1-np.cos(theta))-3*(theta-np.sin(theta)))/(2*safe**2*theta))
    dx = 2*np.sum(vector*np.asarray(derivative),axis=-1)
    dk = skew(derivative)
    return ((da*dx)[...,None,None]*k+a[...,None,None]*dk
            +(db*dx)[...,None,None]*kk+b[...,None,None]*(dk@k+k@dk))


def mv(matrix, vector):
    return np.einsum('...ij,...j->...i',matrix,vector)


def checked_rotation_arc(ra, rb):
    """Principal relative arc with the same uniqueness gate as motion sampling."""
    k = rotation_vector(np.swapaxes(np.asarray(ra),-1,-2)@np.asarray(rb))
    if np.any(np.linalg.norm(k,axis=-1) >= np.pi-1e-7):
        raise ValueError('An element relative rotation approaches pi; refine the structural mesh.')
    return k


def rotation_interpolation(ra, rb, wa, wb, aa, ab, fraction):
    """Rotation, spatial relative rate and its body-frame derivative on an arc.

    R(f) = Ra exp(f log(Ra.T Rb)). Fractions are fixed material coordinates.
    The principal relative arc must remain shorter than pi for a unique tangent.
    """
    ra,rb,wa,wb,aa,ab = map(np.asarray,(ra,rb,wa,wb,aa,ab))
    k = checked_rotation_arc(ra, rb)
    # Exact stationary endpoints have zero arc rates and accelerations.
    # Keep the same rotation and pi-domain check, but avoid solving tangent
    # systems whose right-hand sides are identically zero at static states.
    if not any(np.any(value) for value in (wa, wb, aa, ab)):
        z = np.asarray(fraction)[...,None]*k
        kd = np.zeros(np.broadcast_shapes(k.shape, wa.shape, wb.shape))
        w = np.zeros(np.broadcast_shapes(z.shape, kd.shape))
        a = np.zeros(np.broadcast_shapes(w.shape, aa.shape, ab.shape))
        return ra@rotation_matrix(z), w, a, kd
    rat = np.swapaxes(ra,-1,-2)
    relative_rate = mv(rat,wb-wa)
    j = left_jacobian(k)
    kd = np.linalg.solve(j,relative_rate[...,None])[...,0]
    kdd = np.linalg.solve(j,(mv(rat,ab-aa-cross3(wa,wb-wa))
                            -mv(left_jacobian(k,kd),kd))[...,None])[...,0]
    f = np.asarray(fraction)[...,None]
    z,zd,zdd = f*k,f*kd,f*kdd
    ji = left_jacobian(z)
    relative = mv(ra,mv(ji,zd))
    w = wa+relative
    a = aa+cross3(wa,relative)+mv(ra,mv(left_jacobian(z,zd),zd)+mv(ji,zdd))
    return ra@rotation_matrix(z),w,a,kd


def rotation_weights(ra, rb, fraction):
    """Maps endpoint spatial angular velocities to the interpolated rate.

    Transposes of these maps transfer a section couple to endpoint couples,
    preserving virtual power as well as total angular momentum.
    """
    ra,rb=np.asarray(ra),np.asarray(rb)
    k=rotation_vector(np.swapaxes(ra,-1,-2)@rb)
    f=np.asarray(fraction)[...,None]
    b=ra@(f[...,None]*left_jacobian(f*k))@np.linalg.inv(left_jacobian(k))@np.swapaxes(ra,-1,-2)
    return np.eye(3)-b,b


@dataclass
class LocalMotion:
    """Motion of a section origin/frame relative to body axes (batched arrays)."""
    origin: np.ndarray
    velocity: np.ndarray
    rates: np.ndarray
    acceleration: np.ndarray
    rate_derivative: np.ndarray

    def velocity_at(self, position):
        return self.velocity+cross3(self.rates,np.asarray(position)-self.origin)

    def acceleration_at(self, position):
        d = np.asarray(position)-self.origin
        return self.acceleration+cross3(self.rate_derivative,d)+cross3(self.rates,cross3(self.rates,d))

    def absolute_acceleration(self, position, motion, reference):
        return motion.at(position,reference)+self.acceleration_at(position)+2*cross3(motion.rates,self.velocity_at(position))

    def absolute_angular_acceleration(self, motion):
        return motion.angular_acceleration+self.rate_derivative+cross3(motion.rates,self.rates)

    @classmethod
    def concatenate(cls, fields):
        return cls(*(np.concatenate([getattr(f,key) for f in fields]) if fields else np.empty((0,3))
                     for key in cls.__dataclass_fields__))


class NetworkMotion:
    """Sample nodal elastic velocities/accelerations on the existing geometry."""
    def __init__(self, network, r, q, velocity, rates, acceleration, rate_derivative):
        self.network,self.r,self.q = network,r,q
        self.values = tuple(np.asarray(v,dtype=float) for v in (velocity,rates,acceleration,rate_derivative))
        if any(v.shape!=(network.nn,3) or not np.all(np.isfinite(v)) for v in self.values):
            raise ValueError('Elastic motion fields must be finite (structural_nodes, 3) arrays.')
        self.velocity,self.rates,self.acceleration,self.rate_derivative = self.values
        self.pa,self.pb,self.ra,self.rb,oa,ob = network.geometry(r,q)
        a,b = network.a,network.b
        self.va = self.velocity[a]+cross3(self.rates[a],oa)
        self.vb = self.velocity[b]+cross3(self.rates[b],ob)
        self.aa = self.acceleration[a]+cross3(self.rate_derivative[a],oa)+cross3(self.rates[a],cross3(self.rates[a],oa))
        self.ab = self.acceleration[b]+cross3(self.rate_derivative[b],ob)+cross3(self.rates[b],cross3(self.rates[b],ob))
        self.cache = {}
        self.cache_bytes = 0
        self.cache_limit = 16*1024**2

    def remember(self, slot, key, value):
        """Bound per-state transfer/sampling maps; never cache applied loads."""
        old = self.cache.pop(slot,None)
        if old is not None:self.cache_bytes -= old[2]
        arrays = tuple(vars(value).values()) if isinstance(value,LocalMotion) else value
        size = sum(v.nbytes for v in arrays) + sum(len(v[2]) for v in key)
        if self.cache_bytes + size <= self.cache_limit:
            self.cache[slot] = (key,value,size)
            self.cache_bytes += size
        return value

    def sample(self, beam, fraction, *, material=False):
        """Sample current straight centerline plus the appropriate rotation arc."""
        n = self.network;sl = n.beam_elements[beam]
        f = np.broadcast_to(fraction,(len(self.pa[sl]),)+np.shape(fraction)[1:])
        def shaped(value):
            value=value[sl]
            return value[:,None] if f.ndim==2 else value
        pa,pb,va,vb,aa,ab = map(shaped,(self.pa,self.pb,self.va,self.vb,self.aa,self.ab))
        ra,rb = (self.ra,self.rb) if material else (self.q[n.a],self.q[n.b])
        arrays=(shaped(ra),shaped(rb),shaped(self.rates[n.a]),
                shaped(self.rates[n.b]),shaped(self.rate_derivative[n.a]),shaped(self.rate_derivative[n.b]),f)
        tangent=getattr(n,'tangent_influences',None)
        if not getattr(tangent,'local_geometry',False):rotation,w,a,kd=rotation_interpolation(*arrays)
        else:
            stationary=not any(np.any(v) for v in arrays[2:6])
            rotation,w,a,kd=tangent.local_rows(('arc',beam,material,f.shape,stationary),arrays,
                lambda rows:rotation_interpolation(*(v[rows] for v in arrays)))
        ff=f[...,None]
        return LocalMotion(pa+(pb-pa)*ff,va+(vb-va)*ff,w,aa+(ab-aa)*ff,a),rotation,kd

    def surface(self):
        if 'surface' not in self.cache:
            self.cache['surface'] = LocalMotion.concatenate([
                self.sample(m.beam.index,self.network.fractions[m.beam.index])[0]
                for m in self.network.meshes if m.beam.lifting])
        return self.cache['surface']

    def point(self, kind, index):
        if kind not in ('weight','engine','sensor'):
            raise ValueError('Point motion kind must be weight, engine or sensor.')
        rows = self.network.weights if kind == 'weight' else self.network.model.records.get(kind, [])
        row = rows[index]
        offset = {'weight':0, 'sensor':1, 'engine':2}[kind]
        node = self.network.node(*row[offset:offset+2])
        return LocalMotion(self.r[node],*(v[node] for v in self.values))

    def station(self, beam, t):
        """Local motion at an inserted material station (including a shoulder)."""
        node=self.network.node(beam,t)
        return LocalMotion(self.r[node],*(v[node] for v in self.values))

    def body(self, mesh):
        """Local centerline motion at the body's force quadrature points."""
        from .volume import body_quadrature
        t,_,_,_=body_quadrature(mesh)
        fractions=(t-mesh.t0[:,None])/(mesh.t1-mesh.t0)[:,None]
        # The geometry and nodal motion belong to this NetworkMotion object.
        # Include actual bytes so manual field changes cannot reuse old samples.
        sl=self.network.beam_elements[mesh.beam.index]
        a,b=self.network.a[sl],self.network.b[sl]
        arrays=(fractions,self.pa[sl],self.pb[sl],self.q[a],self.q[b],
                self.va[sl],self.vb[sl],self.aa[sl],self.ab[sl],
                self.rates[a],self.rates[b],self.rate_derivative[a],self.rate_derivative[b])
        key=tuple((v.shape,v.dtype.str,v.tobytes()) for v in arrays)
        slot=('body',mesh.beam.index)
        cached=self.cache.get(slot)
        if cached is not None and cached[0]==key:return cached[1]
        return self.remember(slot,key,self.sample(mesh.beam.index,fractions)[0])

    def strain_rate(self):
        """Exact time derivative of this implementation's midpoint kinematics."""
        out=[]
        for mesh in self.network.meshes:
            sl=self.network.beam_elements[mesh.beam.index]
            field,rotation,kd=self.sample(mesh.beam.index,.5,material=True)
            vd=self.vb[sl]-self.va[sl]-cross3(field.rates,self.pb[sl]-self.pa[sl])
            out.append(np.c_[mv(rotation.transpose(0,2,1),vd),kd]/self.network.ds[sl,None])
        return np.concatenate(out)

    def wrench_weights(self, beam, fraction, *, material=False):
        """Owned rotation-transfer matrices shared by physical and derivative loads."""
        n=self.network;sl=n.beam_elements[beam];f=np.asarray(fraction)
        ra,rb=(self.ra[sl],self.rb[sl]) if material else (self.q[n.a[sl]],self.q[n.b[sl]])
        if f.ndim==2:ra,rb=ra[:,None],rb[:,None]
        # Material and apparent mass share exactly the same transfer maps.
        # Retain one bounded map per beam/material/sample shape. Include actual
        # bytes so changing geometry, fractions or dtype invalidates that map.
        key=tuple((v.shape,v.dtype.str,v.tobytes()) for v in (ra,rb,f))
        slot=('wrench_weights',beam,material,f.shape)
        cached=self.cache.get(slot)
        if cached is None or cached[0]!=key:
            tangent=getattr(n,'tangent_influences',None)
            value=(rotation_weights(ra,rb,f) if not getattr(tangent,'local_geometry',False) else
                   tangent.local_rows(slot,(ra,rb,f),lambda rows:rotation_weights(ra[rows],rb[rows],f[rows])))
            for array in value:array.flags.writeable=False
            wa,wb=self.remember(slot,key,value)
        else:wa,wb=cached[1]
        return wa,wb

    def nodal_wrenches(self, beam, fraction, force, moment, *, material=False):
        """Transfer sampled centerline wrenches, preserving virtual power.

        Fractions have shape (elements,) or (elements, quadrature_points).
        Moments are about each sampled centerline point.
        """
        n=self.network;sl=n.beam_elements[beam]
        f=np.broadcast_to(fraction,np.asarray(force).shape[:-1])
        wa,wb=self.wrench_weights(beam,f,material=material)
        out=[]
        for ids,weight,angular,position in ((n.a[sl],1-f,wa,self.pa[sl]),(n.b[sl],f,wb,self.pb[sl])):
            nodal_force=weight[...,None]*force
            nodal_moment=mv(angular.swapaxes(-1,-2),moment)
            if f.ndim==2:
                nodal_force=nodal_force.sum(axis=1);nodal_moment=nodal_moment.sum(axis=1)
            nodal_moment+=cross3(position-self.r[ids],nodal_force)
            out.append((ids,nodal_force,nodal_moment))
        return out

    def key(self):
        return tuple(v.tobytes() for v in self.values)
