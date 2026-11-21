"""Unexecuted production adapter for the fixed free-carrier/hinged-fin fixture.

Imports and physical work are deferred to explicit calls. This adapter supplies
literal ASW data and physical coordinate/output maps, not independent mechanics.
"""
from copy import deepcopy
import math


def _row(values):
    return ' '.join(format(float(v), '.17g') for v in values)


def _manufacture(fixture, n, manufacture):
    """Required external reference receipt; no derivation from production loads."""
    if n not in fixture['meshes']['fin_intervals']:
        raise ValueError('Only the two declared fin meshes are supported.')
    if manufacture['n'] != n or manufacture['quadrature'] != 32:
        raise ValueError('Use this mesh’s precomputed Q32 manufactured equilibrium.')
    if manufacture['eta_rad'] != math.radians(fixture['hinge']['base_angle_degrees']):
        raise ValueError('Manufactured pose differs from the declared fixed pose.')
    for key, width in [('carrier_force', 3), ('carrier_moment', 3), ('gamma', n)]:
        if len(manufacture[key]) != width or not all(math.isfinite(float(x)) for x in manufacture[key]):
            raise ValueError('Invalid manufactured '+key)
    if not math.isfinite(float(manufacture['eta_rest_rad'])):
        raise ValueError('Invalid manufactured spring rest angle.')
    return manufacture


def asw_source(fixture, n, manufacture):
    m = _manufacture(fixture, n, manufacture)
    c, f, h = (fixture[k] for k in ('carrier', 'fin', 'hinge'))
    g = fixture['gravity_constant']; k = h['stiffness']
    native_root=-f['length']/2; native_tip=f['length']/2
    rest = math.degrees(m['eta_rest_rad'])
    # A two-point linear Jangle law has exactly compliance1/k in radians/Nm.
    # +/-12 Nm is a table coordinate choice, not a torque limit or clip.
    spring = [_row([-k, rest-math.degrees(1.)]), _row([k, rest+math.degrees(1.)])]
    weights = []
    for body in (c, f):
        I = body['inertia']
        attachment_t=body['weight_attachment_t']-(f['length']/2 if body['beam']==f['beam'] else 0.)
        weights.append(_row([body['beam'], attachment_t, *body['cg'],
            g*body['mass'], 0., 0., 0., 0., 0.,
            g*I[0][0], g*I[1][1], g*I[2][2], -g*I[0][1], -g*I[0][2], -g*I[1][2]]))
    properties = [f['chord'], f['Xax'], f['alpha_degrees'], f['CLa'], f['dCLdF3'],
                  f['Cdf'], f['Cdp'], f['Cm'], f['CLmax'], f['CLmin']]
    tip = [h['position'][i]+f['length']*f['jig_span_direction'][i] for i in range(3)]
    lines = ['! Source-defined mechanical/aerodynamic fixture; no parameter fitting.',
        'Name','Free carrier with massive hinged fin','End','Unit','L 1 m','T 1 s','F 1 N','End',
        'Constant',_row([g, fixture['density'], fixture['sound_speed']]),'End',
        'Reference',_row([f['length']*f['chord'], f['chord'], f['length']]),
        '0 0 0','0 0 0','0 0 0','End',
        'Ground','1 0 0','End','Joint',_row([1,2,1,native_root,3]),'End',
        'Jangle',_row([1,*h['axis']]),*spring,'End','Weight',*weights,'End',
        'Beam 1','Exact rigid massless carrier link','t x y z EIcc EInn GJ EA GKc GKn',
        _row([0,*c['origin'],0,0,0,0,0,0]),_row([1,*c['jig_end'],0,0,0,0,0,0]),'End',
        'Beam 2','Exact rigid lifting fin; real inertia is the root-pylon Weight',
        't x y z chord Xax alpha dCLda dCLdF3 Cdf Cdp Cm CLmax CLmin',
        _row([native_root,*h['position'],*properties]),_row([native_tip,*tip,*properties]),'End']
    return '\n'.join(lines)+'\n'


def prepare(fixture, n, manufacture, lag=False, *, reference_geometry, geometry_recorder=None):
    """One parse and zero-rate network construction; no residual or solve here.

    Returns a portable geometric seed, with zero nuisance loads explicitly
    unbalanced. The normal production equilibrium correction must accept it
    with original residual/rank checks before any DynamicSystem is built.
    """
    import numpy as np
    from scipy.spatial.transform import Rotation
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition
    from openswing.network import StaticNetwork
    from openswing.operating import free_flight_constraints
    from openswing.equilibrium_state import capture
    m = _manufacture(fixture, n, manufacture)
    source = asw_source(fixture,n,m); model = parse_asw(source)
    condition = FlightCondition(speed=fixture['speed'], alpha=0., beta=0., mach=fixture['mach'],
        density=fixture['density'], altitude_m=fixture['altitude_m'], stall=False,
        ground_effect=0, aero_lag=lag, freeze_influences=False, circulation_modes={2:0},
        controls={3:0.}, rates=[0.,0.,0.], acceleration=[0.,0.,0.], angular_acceleration=[0.,0.,0.])
    panels = dict(default=4,beams={'1':dict(count=4,spacing='cosine'),
                                  '2':dict(count=n,spacing='cosine')})
    loads=[dict(beam=1,t=0.,force=list(m['carrier_force']),moment=list(m['carrier_moment']))]
    network=StaticNetwork(model,panels,condition,[0.,0.,0.],loads,
                          operating_constraints=free_flight_constraints())
    expected=fixture['meshes']['expected'][str(n)]
    fin_beam=next(b for b in model.beams if b.index==2)
    assert fin_beam.domain==(-fixture['fin']['length']/2,fixture['fin']['length']/2)
    assert (network.nn,network.ne,network.ng,network.size)==tuple(expected[k] for k in
        ('nodes','elements','circulation','network_dimension'))
    assert np.count_nonzero(network.S)==0 and len(network.hinges)==1
    h=np.asarray(fixture['hinge']['position']);a=np.asarray(fixture['hinge']['axis']);a=a/np.linalg.norm(a)
    eta=m['eta_rad'];q=Rotation.from_rotvec(eta*a).as_matrix()
    ids=network.beam_nodes[2];r=network.rj.copy();r[ids]=h+(network.rj[ids]-h)@q.T
    values=np.zeros(network.size);kin=values[:6*network.nn].reshape(-1,6)
    kin[:,:3]=(r-network.rj)/network.L;kin[ids,3:]=eta*a
    values[network.gamma_start:network.operating_start]=network.circulation_basis.encode(np.asarray(m['gamma']))/network.gamma_scale
    # Native material t=s-length/2 avoids the documented t=0 lifting
    # symmetry convention. Geometry is checked before ANY physical residual.
    from openswing.frozen_influence import lifting_geometry
    rotations=Rotation.from_rotvec(kin[:,3:]).as_matrix()
    loaded_meshes=network.deformed_meshes(r,rotations,network.geometry(r,rotations))
    fin_mesh=next(mesh for mesh in loaded_meshes if mesh.beam.index==2)
    jig_mesh=next(mesh for mesh in network.meshes if mesh.beam.index==2)
    native_nodes=network.station_nodes[2][0]
    physical_nodes=native_nodes+fixture['fin']['length']/2
    jig_expected=h+physical_nodes[:,None]*np.asarray(fixture['fin']['jig_span_direction'])
    loaded_expected=np.vstack([reference_geometry['r0'][0],reference_geometry['r1']])
    fields= lifting_geometry(loaded_meshes,np.asarray(reference_geometry['wind']))
    expected_frame=np.stack([reference_geometry[k] for k in ('c','s','normal')],axis=-1)
    joint=next(c for c in network.constraints if c['kind']=='joint')
    checks=[]
    def equal(name,actual,expected):
        actual,expected=np.asarray(actual),np.asarray(expected)
        passed=actual.shape==expected.shape and np.all(np.isfinite(actual)) and np.all(np.abs(actual-expected)<=2e-11+2e-11*np.abs(expected))
        checks.append(dict(name=name,passed=bool(passed),maximum_absolute=None if actual.shape!=expected.shape else float(np.max(np.abs(actual-expected),initial=0))))
    equal('jig ordered nodes',network.rj[ids],jig_expected)
    equal('physical material stations',physical_nodes,reference_geometry['t'])
    equal('loaded ordered nodes',r[ids],loaded_expected)
    equal('loaded r0',fin_mesh.r0,reference_geometry['r0']);equal('loaded r1',fin_mesh.r1,reference_geometry['r1'])
    equal('loaded rm',fin_mesh.rm,reference_geometry['rm']);equal('physical interval lengths',fin_mesh.length,reference_geometry['ds'])
    equal('loaded midpoint frame',fin_mesh.frames,np.broadcast_to(expected_frame,fin_mesh.frames.shape))
    equal('loaded first endpoint frame',fin_mesh.frame0,np.broadcast_to(expected_frame,fin_mesh.frame0.shape))
    equal('loaded second endpoint frame',fin_mesh.frame1,np.broadcast_to(expected_frame,fin_mesh.frame1.shape))
    for key in ('a','b','hv','cp','rm'):
        equal('loaded lifting '+key,fields[key],reference_geometry[key])
    equal('unloaded endpoints',np.array([jig_mesh.r0[0],jig_mesh.r1[-1]]),np.array([h,h+fixture['fin']['length']*np.asarray(fixture['fin']['jig_span_direction'])]))
    carrier=network.beam_nodes[1]
    equal('carrier jig pose',r[carrier],network.rj[carrier]);equal('carrier zero rotations',kin[carrier,3:],np.zeros((len(carrier),3)))
    checks.append(dict(name='terminal fin root joint and mass',passed=bool(joint['a']==network.beam_nodes[1][-1] and joint['b']==ids[0] and network.node(*network.weights[1][:2])==ids[0])))
    checks.append(dict(name='strictly ordered one-sided span',passed=bool(np.all(np.diff(physical_nodes)>0) and physical_nodes[0]==0. and physical_nodes[-1]==fixture['fin']['length'])))
    checks.append(dict(name='zero physical residual calls',passed=bool(network.nfev==0)))
    geometry_report=dict(native_parameter_map='t_native=s_physical-length/2',native_domain=list(fin_beam.domain),native_nodes=native_nodes,physical_nodes=physical_nodes,
        joint=dict(a=joint['a'],b=joint['b']),fin_node_ids=ids,jig_positions=network.rj[ids],loaded_positions=r[ids],
        loaded=dict(r0=fin_mesh.r0,r1=fin_mesh.r1,rm=fin_mesh.rm,frames=fin_mesh.frames,frame0=fin_mesh.frame0,frame1=fin_mesh.frame1,length=fin_mesh.length,lifting=fields),
        reference_geometry=reference_geometry,checks=checks,source=source)
    if geometry_recorder is not None:geometry_recorder(geometry_report)
    if not all(c['passed'] for c in checks):raise ValueError('Pre-residual fixture geometry mismatch: '+', '.join(c['name'] for c in checks if not c['passed']))
    # capture() is serialization/kinematics, and performs no residual evaluation.
    seed=capture(network,values,residual=None)
    return dict(source=source,model=model,condition=condition,panels=panels,loads=loads,
                initial_state=seed,seed_network=network,seed_raw=values,manufacture=deepcopy(m),fixture=deepcopy(fixture),geometry_report=geometry_report,
                scope='Geometric/reference-Gamma seed; nuisance force/reaction coordinates are zero guesses, not a converged base.')


def build_system(prepared, *, progress=None):
    """Future authorized production solve; no call occurs on adapter import."""
    import numpy as np
    from openswing.linear_dynamics import make_system
    system,steps=make_system(prepared['model'],prepared['condition'],prepared['panels'],
        frame='free',gravity=[0.,0.,0.],loads=prepared['loads'],
        initial_state=deepcopy(prepared['initial_state']),tolerance=1e-9,progress=progress)
    zero=np.zeros(system.size);fresh=system.residual(zero,zero)
    assert np.max(np.abs(fresh))<=1e-8
    # A free-frame acceleration solve must not hide an unbalanced manufactured base.
    assert np.max(np.abs(system.motion.acceleration))<=1e-8
    assert np.max(np.abs(system.motion.angular_acceleration))<=1e-8
    assert np.max(np.abs(system.Omega0))==0.
    r,Q,_,_,_,gamma=system.network.unpack(system.base)
    seed=prepared['initial_state']
    from scipy.spatial.transform import Rotation
    seedQ=Rotation.from_rotvec(np.asarray(seed['rotations'])).as_matrix()
    system.fixture_seed_comparison=dict(position_max_abs=float(np.max(np.abs(r-np.asarray(seed['positions'])))),
        rotation_matrix_max_abs=float(np.max(np.abs(Q-seedQ))),
        circulation_max_abs=float(np.max(np.abs(gamma-np.asarray(seed['circulation'])))),
        acceleration=system.motion.acceleration.tolist(),angular_acceleration=system.motion.angular_acceleration.tolist(),
        physical_seed_residual_was_unmeasured=True)
    return system,steps,fresh


def native_inputs(system):
    """Map native target sign to a physical positive carrier-root yaw couple."""
    from openswing.frequency_response import HarmonicInput
    return [HarmonicInput(system,'control.3',0),HarmonicInput(system,'target.moment.z',1)], [1.,-1.]


def physical_input_columns(native_B):
    """Input scale is already divided out by native input_partials."""
    out=native_B.copy();out[:,1]*=-1.
    return out


def kinematic_harmonic_state(system,fixture,q,gamma,omega):
    """First-order physical map only; internal/reaction entries are NOT filled.

    q=[Earth position perturbation3, Earth spatial rotation perturbation3, eta].
    Nuisance equations must be solved by production and are never synthesized
    from the independent reference. This map is for selected-coordinate checks.
    """
    import numpy as np
    from openswing.linear_dynamics import euler_matrix
    n=system.network;q=np.asarray(q,dtype=complex);gamma=np.asarray(gamma,dtype=complex)
    if q.shape!=(7,) or gamma.shape!=(n.ng,):raise ValueError('Wrong physical state dimensions.')
    z=np.zeros(system.size,dtype=complex);s=1j*omega
    a=np.asarray(fixture['hinge']['axis']);a=a/np.linalg.norm(a)
    H=np.asarray(fixture['hinge']['position']);ids=n.beam_nodes[2]
    tangent=np.cross(a,system.r0[ids]-H)
    kin=z[:6*n.nn].reshape(-1,6);kin[ids,:3]=tangent*q[6]/system.L;kin[ids,3:]=a*q[6]
    uv=z[system.velocity_start:system.frame_start].reshape(2,n.nn,3)
    uv[0,ids]=s*tangent*q[6]/system.V;uv[1,ids]=s*a*q[6]/system.W
    theta=system.R0.T@q[3:6];pdot=system.R0.T@(s*q[:3]);pddot=system.R0.T@(s*s*q[:3])
    frame=z[system.frame_start:system.feedback_start].reshape(4,3)
    frame[0]=(pdot-np.cross(theta,system.U0))/system.V
    frame[1]=s*theta/system.W;frame[2]=q[:3]/system.L
    # Original fixture has zero ASW attitude, where E=diag(-1,1,-1).
    E=euler_matrix(system.attitude)
    if not np.array_equal(E,np.diag([-1.,1.,-1.])):raise ValueError('Only the declared zero-attitude base is supported.')
    frame[3]=E@theta
    for i,c in enumerate(n.operating.constraints):
        axis='xyz'.index(c.variable.rsplit('.',1)[1])
        acc=pddot[axis] if c.variable.startswith('acceleration.') else (s*s*theta)[axis]
        z[n.operating_start+i]=acc/n.operating.scale[c.variable]
    z[n.gamma_start:n.operating_start]=gamma/n.gamma_scale
    mask=np.zeros(system.size,dtype=bool);mask[:6*n.nn]=True;mask[n.gamma_start:]=True
    return z,mask


def generalized_outputs(system,fixture,state):
    """Recover seven coordinates and direct frame/local velocities from raw z."""
    import numpy as np
    from openswing.linear_dynamics import euler_matrix
    z=np.asarray(state);n=system.network;frame=z[system.frame_start:system.feedback_start].reshape(4,3)
    theta_body=euler_matrix(system.attitude)@frame[3]
    a=np.asarray(fixture['hinge']['axis']);a=a/np.linalg.norm(a);ids=n.beam_nodes[2]
    node=z[:6*n.nn].reshape(-1,6);eta=node[ids,3:]@a
    local=z[system.velocity_start:system.frame_start].reshape(2,n.nn,3)
    eta_rate=(system.W*local[1,ids])@a
    rhat=system.L*frame[2];thetahat=system.R0@theta_body
    absolute=rhat+(system.L*node[:,:3]+np.cross(theta_body,system.r0))@system.R0.T
    return dict(q=np.r_[rhat,thetahat,eta[0]],hinge_angles_each_node=eta,
        hinge_rates_each_node=eta_rate,frame_velocity=system.V*frame[0],
        frame_rates=system.W*frame[1],earth_node_displacement=absolute,
        gamma=z[n.gamma_start:n.operating_start]*n.gamma_scale,
        carrier_constraint_translation=system.L*node[n.beam_nodes[1],:3],
        carrier_constraint_rotation=node[n.beam_nodes[1],3:])


def physical_yaw_output_correction(native_global_moment,native_ground_moment,input_amplitude):
    """For -target.Mz response, add missing +Mz applied load and remove gauge reaction.

    Fin/hinge reactions and all motion/circulation are unchanged. Do not label
    the raw native target wrench as the physical externally applied yaw couple.
    """
    import numpy as np
    torque=np.asarray([0.,0.,input_amplitude])
    return np.asarray(native_global_moment)+torque,np.asarray(native_ground_moment)-torque
