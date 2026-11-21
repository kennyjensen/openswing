"""Native adapter for the proposed free elastic wing/fin component.

No numerical work occurs on import. The fixture is a new component benchmark,
not a Daedalus trim adjustment. All base aero counterloads and circulation must
come from the independent reference before any native residual is evaluated.
"""
from copy import deepcopy
import json
import math
from pathlib import Path


DATA = Path(__file__).parent/'data'/'free-elastic-coupling'


def load_fixture():
    return json.loads((DATA/'fixture.json').read_text())


def _row(values):
    return ' '.join(format(float(value), '.17g') for value in values)


def asw_source(fixture):
    """Literal model: distinct physical beams, finite six-direction stiffness."""
    f, c = fixture, fixture['carrier']
    g = f['gravity_constant']
    inertia = c['inertia']
    weight = [c['beam'], c['weight_attachment_t'], *c['cg'], g*c['mass'],
              0., 0., 0., 0., 0., g*inertia[0][0], g*inertia[1][1], g*inertia[2][2],
              -g*inertia[0][1], -g*inertia[0][2], -g*inertia[1][2]]
    lines = ['! Proposed free elastic wing/fin benchmark; no fitted aircraft parameters.',
             'Name', 'Free carrier with tensioned elastic wing and fin', 'End',
             'Unit', 'L 1 m', 'T 1 s', 'F 1 N', 'End', 'Constant',
             _row([g, f['density'], f['sound_speed']]), 'End', 'Reference',
             _row([sum(b['length']*b['chord'] for b in f['branches'].values()), .55, 2.4]),
             '0 0 0', '0 0 0', '0 0 0', 'End', 'Ground', '1 0 0', 'End', 'Joint',
             _row([1, 2, 0, f['branches']['wing']['native_domain'][0], 0]),
             _row([1, 3, 1, f['branches']['fin']['native_domain'][0], 0]), 'End',
             'Weight', _row(weight), 'End', 'Beam 1', 'Exact rigid massless carrier link',
             't x y z EIcc EInn GJ EA GKc GKn',
             _row([0, *c['origin'], 0, 0, 0, 0, 0, 0]),
             _row([1, *c['jig_end'], 0, 0, 0, 0, 0, 0]), 'End']
    for name in ('wing', 'fin'):
        b = f['branches'][name]
        lines += [f"Beam {b['beam']}", name.capitalize()+' with real distributed mass',
                  't x y z chord Xax alpha dCLda dCLdF2 dCLdF3 Cdf Cdp Cm CLmax CLmin',
                  *[_row([t, *[b['root'][i]+s*b['span_direction'][i] for i in range(3)],
                          b['chord'], b['Xax'], b['alpha_degrees'], b['CLa'],
                          b['dCLdF'] if b['control'] == 2 else 0.,
                          b['dCLdF'] if b['control'] == 3 else 0.,
                          b['Cdf'], b['Cdp'], b['Cm'], 100., -100.])
                    for t, s in zip(b['native_domain'], (0., b['length']))],
                  't EIcc EInn GJ EA GKc GKn',
                  *[_row([t, *[b['stiffness'][key] for key in ('EIcc','EInn','GJ','EA','GKc','GKn')]])
                    for t in b['native_domain']],
                  't mg Ccg Ncg mgcc mgnn',
                  *[_row([t, g*b['mass_per_length'], b['cg_material'][0], b['cg_material'][2],
                          g*b['inertia_per_length'][0], g*b['inertia_per_length'][2]])
                    for t in b['native_domain']], 'End']
    return '\n'.join(lines)+'\n'


def mesh_data(fixture, intervals):
    """Pure canonical mesh arithmetic; no production imports or evaluation.

    Receiving nodes are wing then fin, each root-to-tip. Native carrier nodes
    precede them. Coincident joint nodes remain separate native unknowns.
    """
    if type(intervals) is not int or intervals not in fixture['mesh']['lifting_intervals']:
        raise ValueError('Only the two declared meshes are supported.')
    panels = dict(default=4, beams={'1':dict(nodes=list(fixture['mesh']['carrier_nodes']))})
    branches, nodes = {}, []
    for name in ('wing', 'fin'):
        b = fixture['branches'][name]
        length = b['length']
        s = [length*(1-math.cos(math.pi*j/intervals))/2 for j in range(intervals+1)]
        s[0], s[-1] = 0., length
        t = [x-length/2 for x in s]
        tm_s = [length*(1-math.cos(math.pi*(j+.5)/intervals))/2 for j in range(intervals)]
        fractions = [(m-a)/(z-a) for m,a,z in zip(tm_s,s[:-1],s[1:])]
        c, span = b['chord_direction'], b['span_direction']
        normal = [c[1]*span[2]-c[2]*span[1], c[2]*span[0]-c[0]*span[2], c[0]*span[1]-c[1]*span[0]]
        rotation = [[c[i], span[i], normal[i]] for i in range(3)]
        stretch = 1+b['tension']/b['stiffness']['EA']
        jig = [[b['root'][i]+x*span[i] for i in range(3)] for x in s]
        positions = [[b['root'][i]+stretch*x*span[i] for i in range(3)] for x in s]
        start = len(nodes)
        nodes += [dict(branch=name, beam=b['beam'], t=x, s=y, position=r, material_rotation=rotation)
                  for x,y,r in zip(t,s,positions)]
        panels['beams'][str(b['beam'])] = dict(nodes=t)
        branches[name] = dict(s=s, t=t, tm_s=tm_s, tm=[x-length/2 for x in tm_s],
                              fractions=fractions, jig_positions=jig, positions=positions,
                              material_rotation=rotation, receiving_ids=list(range(start,len(nodes))))
    return dict(intervals=intervals, panels=panels, branches=branches, receiving_nodes=nodes)


def frozen_loads(fixture, mesh, counterloads):
    """Subtract independent positive base aero nodal wrenches exactly once.

    counterloads has shape (2*(n+1),6), in mesh receiving-node order. Each
    moment is an intrinsic couple ABOUT ITS NODE, not about the carrier origin.
    All resulting loads are constant BODY-coordinate vectors. Their moment
    arms still move. An inertial-coordinate reference must rotate these vectors
    with the carrier; no local-material follower rotation belongs here.
    """
    import numpy as np
    values = np.asarray(counterloads, dtype=float)
    if values.shape != (len(mesh['receiving_nodes']), 6) or not np.isfinite(values).all():
        raise ValueError('Counterloads require one finite six-wrench per receiving node.')
    rows = [dict(beam=1, t=0., force=list(fixture['base']['carrier_balancer_force']),
                 moment=list(fixture['base']['carrier_balancer_moment']))]
    for node, aero in zip(mesh['receiving_nodes'], values):
        b = fixture['branches'][node['branch']]
        force, moment = -aero[:3].copy(), -aero[3:].copy()
        if node['s'] == b['length']:
            force += b['tension']*np.asarray(b['span_direction'])
        rows.append(dict(beam=node['beam'], t=node['t'], force=force.tolist(), moment=moment.tolist()))
    return rows


def build_network(fixture, intervals, counterloads, *, lag=True, residual_observer=None):
    """Construct only. Counterloads must already be frozen independently."""
    import numpy as np
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition
    from openswing.network import StaticNetwork
    from openswing.operating import free_flight_constraints
    mesh = mesh_data(fixture, intervals)
    source = asw_source(fixture)
    if source != (DATA/'model.asw').read_text():
        raise ValueError('Literal model and fixture are inconsistent.')
    model = parse_asw(source)
    c = fixture['condition']
    condition = FlightCondition(speed=fixture['speed'], density=fixture['density'], mach=fixture['mach'],
        alpha=c['alpha'], beta=c['beta'], attitude=c['attitude'], controls={int(k):v for k,v in c['controls'].items()},
        rates=c['rates'], acceleration=c['acceleration'], angular_acceleration=c['angular_acceleration'],
        stall=c['stall'], ground_effect=c['ground_effect'], aero_lag=lag,
        freeze_influences=c['freeze_influences'], wake_core_ratio=c['wake_core_ratio'], circulation_modes={2:0,3:0})
    loads = frozen_loads(fixture, mesh, counterloads)
    n = StaticNetwork(model, mesh['panels'], condition, fixture['gravity_override'], loads,
                      operating_constraints=free_flight_constraints())
    expected = fixture['mesh']['expected'][str(intervals)]
    assert (n.nn,n.ne,n.ng,n.nc,n.size) == tuple(expected[k] for k in
            ('nodes','elements','circulation','constraint_rows','network_dimension'))
    assert n.nfev == 0 and n.operating.count == 6 and not n.hinges and not n.circulation_basis.modes
    assert [b.physical_index for b in model.beams if b.lifting] == [2,3]
    assert [b.domain for b in model.beams if b.lifting] == [tuple(fixture['branches'][name]['native_domain']) for name in ('wing','fin')]
    assert len(n.constraints) == 3 and all(c['type'] == 0 for c in n.constraints)
    assert np.array_equal(model.reference[1:], np.zeros((3,3)))
    if residual_observer is not None:
        original = n.residual
        def observed(*args, **kwargs):
            residual_observer()
            return original(*args, **kwargs)
        n.residual = observed
    return dict(network=n, mesh=mesh, fixture=deepcopy(fixture), source=source, loads=loads,
                independent_counterloads=np.asarray(counterloads).copy())


def seed_packet(prepared, gamma):
    """Encode the analytic affine tensile base; no residual or correction.

    Loaded circulation is independent. Internal carrier resultants and all
    reactions follow the fixed preload alone, because base aero/counterloads
    cancel node by node. Full equilibrium acceptance is still mandatory.
    """
    import numpy as np
    from openswing.equilibrium_state import capture, reaction_scales
    from openswing.frozen_influence import lifting_geometry
    n, f, mesh = (prepared[key] for key in ('network','fixture','mesh'))
    gamma = np.asarray(gamma, dtype=float)
    if gamma.shape != (n.ng,) or not np.isfinite(gamma).all():
        raise ValueError('Independent pointwise circulation requires all wing/fin strips.')
    for part in np.split(gamma,2):
        if np.max(abs(part)) <= 1e-8:
            raise ValueError('Both lifting branches must have nonzero loaded circulation.')
    x = np.zeros(n.size)
    kin = x[:6*n.nn].reshape(n.nn,6)
    internal = x[6*n.nn:6*(n.nn+n.ne)].reshape(n.ne,6)
    checks = []
    def equal(name, actual, expected):
        a,b = np.asarray(actual),np.asarray(expected)
        passed = a.shape == b.shape and np.isfinite(a).all() and np.all(abs(a-b) <= 2e-11+2e-11*abs(b))
        checks.append(dict(name=name, passed=bool(passed), maximum_absolute=None if a.shape!=b.shape else float(np.max(abs(a-b),initial=0.))))
        if not passed:
            raise ValueError('Pre-residual geometry mismatch: '+name)
    receiving = []
    for name in ('wing','fin'):
        b, row = f['branches'][name], mesh['branches'][name]
        ids = n.beam_nodes[b['beam']]
        equal(name+' exact material node order', n.station_nodes[b['beam']][0], row['t'])
        equal(name+' jig nodes', n.rj[ids], row['jig_positions'])
        kin[ids,:3] = (np.asarray(row['positions'])-n.rj[ids])/n.L
        receiving.extend(ids.tolist())
    r = n.rj+n.L*kin[:,:3]
    for e,(a,b) in enumerate(zip(n.a,n.b)):
        if a in n.beam_nodes[1]:
            force = np.asarray(f['base']['carrier_internal_force'])
            moment = np.cross(np.asarray(f['carrier']['jig_end'])-(r[a]+r[b])/2,force)
        else:
            branch = f['branches']['wing' if a in n.beam_nodes[2] else 'fin']
            force = branch['tension']*np.asarray(branch['span_direction'])
            moment = np.zeros(3)
        internal[e,:3], internal[e,3:] = force/n.F, moment/(n.F*n.L)
    reaction = np.zeros(n.nc)
    for constraint in n.constraints:
        if constraint['kind'] == 'ground':
            assert constraint['a'] == n.node(1,0.)
            continue
        branch = 'wing' if constraint['b'] == n.node(2,f['branches']['wing']['native_domain'][0]) else 'fin'
        b = f['branches'][branch]
        expected_a = n.node(1,0. if branch=='wing' else 1.)
        assert constraint['a'] == expected_a and constraint['b'] == n.node(b['beam'],b['native_domain'][0])
        equal(branch+' coincident loaded joint', r[constraint['a']], r[constraint['b']])
        reaction[constraint['sl']] = np.r_[b['tension']*np.asarray(b['span_direction']),np.zeros(3)]
    x[6*(n.nn+n.ne):n.gamma_start] = reaction/reaction_scales(n)
    x[n.gamma_start:n.operating_start] = n.circulation_basis.encode(gamma)/n.gamma_scale
    Q = np.broadcast_to(np.eye(3),(n.nn,3,3)).copy()
    deformed = n.deformed_meshes(r,Q,n.geometry(r,Q))
    for name in ('wing','fin'):
        branch, row = f['branches'][name], mesh['branches'][name]
        actual = next(m for m in deformed if m.beam.index==branch['beam'])
        positions = np.asarray(row['positions'])
        equal(name+' material receivers', actual.tm, row['tm'])
        equal(name+' loaded endpoints0', actual.r0, positions[:-1])
        equal(name+' loaded endpoints1', actual.r1, positions[1:])
        equal(name+' current lengths', actual.length, np.diff(row['s'])*(1+branch['tension']/branch['stiffness']['EA']))
        fraction = np.asarray(row['fractions'])[:,None]
        equal(name+' receiver positions', actual.rm, (1-fraction)*positions[:-1]+fraction*positions[1:])
        equal(name+' material frame', actual.frames, np.broadcast_to(row['material_rotation'],actual.frames.shape))
    assert np.count_nonzero(n.S) > 0 and n.nfev == 0
    packet = capture(n,x,residual=None)
    report = dict(checks=checks,receiving_node_ids=receiving,material_mesh=mesh,
                  lifting_geometry=lifting_geometry(deformed,n.condition.vectors()[0]),
                  positions=r,rotations=Q,physical_internal_force=internal[:,:3]*n.F,
                  physical_internal_moment=internal[:,3:]*n.F*n.L,physical_reactions=reaction,
                  residual_evaluations=0,seed_is_unmeasured=True)
    prepared['receiving_node_ids'] = np.asarray(receiving,dtype=int)
    prepared['seed'] = packet
    return x,packet,report


def correct_base(prepared, packet, *, tolerance=1e-9, progress=None):
    """One explicitly invoked native correction; no call during preparation."""
    import numpy as np
    from openswing.network import equilibrate
    from openswing.linear_dynamics import DynamicSystem
    n = prepared['network']
    value,steps = equilibrate(n,tolerance=tolerance,initial_state=packet,progress=progress)
    system = DynamicSystem(n,value,'free')
    r,Q,*_,gamma = n.unpack(value)
    checks = dict(position_max=float(np.max(abs(r-np.asarray(packet['positions'])))),
                  rotation_max=float(np.max(abs(Q-np.eye(3)))),
                  circulation_max=float(np.max(abs(gamma-np.asarray(packet['circulation'])))),
                  acceleration_max=float(np.max(abs(system.motion.acceleration))),
                  angular_acceleration_max=float(np.max(abs(system.motion.angular_acceleration))))
    if any(v>2e-8 for v in checks.values()):
        raise ValueError('The corrected base left its declared steady manufactured state: '+str(checks))
    return system,value,dict(continuation_steps=steps,manufactured_base_deviation=checks)


def input_rhs(system, *, step=1e-5):
    """+1 rad fin incidence and +1 Nm carrier yaw, native target sign explicit."""
    from openswing.frequency_response import HarmonicInput,input_partials
    channels = [HarmonicInput(system,'control.3',0),HarmonicInput(system,'target.moment.z',1)]
    B,forcings,profiles = input_partials(system,channels,0.,step,constant_inputs={})
    signs = [1.,-1.]
    B = B.copy();B[:,1] *= -1
    return B,forcings,dict(signs=signs,channels=[c.report for c in channels],profiles=profiles,
                          meaning=['unit physical fin incidence in radians','unit physical carrier yaw couple in N m'])


def recover_state(system, Z, omega):
    """Physical harmonic maps, preserving Galilean/background-velocity terms.

    Absolute fields are perturbations in the frame translating with base U0.
    Native local rotations are spatial increments, not full material triads.
    """
    import numpy as np
    from openswing.linear_dynamics import euler_matrix
    z = np.asarray(Z)
    if z.ndim == 1:z=z[:,None]
    n,columns = system.network,z.shape[1]
    if np.any(system.Omega0) or np.any(system.motion.acceleration) or np.any(system.motion.angular_acceleration):
        # Residual acceptance permits roundoff acceleration. Do not silently
        # extend this zero-rate map to a spinning/accelerating operating point.
        if max(float(np.max(abs(x))) for x in (system.Omega0,system.motion.acceleration,system.motion.angular_acceleration)) > 2e-8:
            raise ValueError('The declared straight-flight base is required.')
    frame = z[system.frame_start:system.feedback_start].reshape(4,3,columns)
    kin = z[:6*n.nn].reshape(n.nn,6,columns)
    velocity = z[system.velocity_start:system.frame_start].reshape(2,n.nn,3,columns)
    theta = euler_matrix(system.attitude)@frame[3]
    rhat = system.L*frame[2]
    U,Omega = system.V*frame[0],system.W*frame[1]
    ub,thb = system.L*kin[:,:3],kin[:,3:]
    def cross(a,b):
        return np.moveaxis(np.cross(np.moveaxis(a,-2,-1),np.moveaxis(b,-2,-1)),-1,-2)
    arm = system.r0[:,:,None]
    absolute_u = rhat[None]+np.einsum('ij,njk->nik',system.R0,ub+cross(theta[None],arm))
    absolute_theta = np.einsum('ij,njk->nik',system.R0,thb+theta[None])
    carrier_velocity = system.R0@(U+cross(theta,system.U0[:,None]))
    absolute_velocity = np.einsum('ij,njk->nik',system.R0,
        U[None]+system.V*velocity[0]+cross(Omega[None],arm)+cross(theta,system.U0[:,None])[None])
    return dict(frame_position=rhat,frame_rotation=system.R0@theta,
                frame_U_body=U,frame_Omega_body=Omega,carrier_velocity_galilean=carrier_velocity,
                node_motion_body=np.concatenate((ub,thb),axis=1),
                node_motion_absolute=np.concatenate((absolute_u,absolute_theta),axis=1),
                node_velocity_absolute=absolute_velocity,
                node_angular_velocity_absolute=np.einsum('ij,njk->nik',system.R0,Omega[None]+system.W*velocity[1]),
                gamma=n.gamma_scale*z[n.gamma_start:n.operating_start],
                carrier_velocity_defect=carrier_velocity-1j*omega*rhat,
                node_velocity_defect=absolute_velocity-1j*omega*absolute_u)


def selected_outputs(system,Z,omega):
    """Receiving-node body motion and free-frame outputs in reference order."""
    import numpy as np
    raw=recover_state(system,Z,omega)
    ids=np.r_[system.network.beam_nodes[2],system.network.beam_nodes[3]]
    return dict(node_body_motion=raw['node_motion_body'][ids],
                node_absolute_motion=raw['node_motion_absolute'][ids],
                frame_motion=np.concatenate((raw['frame_position'],raw['frame_rotation'])),
                frame_velocity=raw['frame_U_body'],frame_rates=raw['frame_Omega_body'],gamma=raw['gamma'])


def extract_outputs(system,state,data):
    """Use this detailed evaluation only; no repeated residual or load law.

    Family order total/rate/apparent/remainder; group order wing/fin/global.
    Couples are transported once from current section axis to carrier origin.
    Xax=.35 means rate lift has a nonzero quarter-chord intrinsic couple.
    """
    import numpy as np
    from scipy.spatial.transform import Rotation
    n=system.network
    packet=data['aero'];strips=[row for row in packet['strips'] if row.get('lifting')]
    beam=np.asarray([row['beam'] for row in strips])
    if not np.array_equal(beam,np.r_[np.full(len(n.beam_nodes[2])-1,2),np.full(len(n.beam_nodes[3])-1,3)]):
        raise ValueError('Unexpected native strip order.')
    def vector(key):return np.asarray([row[key] for row in strips],dtype=float)
    position=vector('position')
    totalF,totalM=vector('force'),vector('moment')
    rateF=vector('circulation_rate_force')
    apparentF,apparentM=vector('apparent_force'),vector('apparent_moment')
    arms=[]
    for mesh in data['meshes']:
        if mesh.beam.lifting:
            chord=mesh.beam.value('chord',mesh.tm)
            xax=mesh.beam.value('Xax',mesh.tm)
            arms.extend(((.25-xax)*chord)[:,None]*mesh.frames[:,:,0])
    rateM=np.cross(np.asarray(arms),rateF)
    forces=np.stack((totalF,rateF,apparentF,totalF-rateF-apparentF))
    moments=np.stack((totalM,rateM,apparentM,totalM-rateM-apparentM))
    origin=n.model.reference[1]
    strip=np.concatenate((forces,moments+np.cross(position-origin,forces)),axis=2)
    wrenches=np.stack([np.sum(strip[:,mask],axis=1) for mask in
                      (beam==2,beam==3,np.ones(len(beam),dtype=bool))],axis=1)
    # Same-evaluation global checks detect an intrinsic/global arm mix-up.
    for j,prefix in enumerate(('', 'circulation_rate_', 'apparent_')):
        expected=np.r_[packet[prefix+'force'],packet[prefix+'moment']]
        if not np.allclose(wrenches[j,2],expected,atol=2e-11,rtol=2e-11):
            raise ValueError('Strip/global aerodynamic transport mismatch: '+prefix)
    ids=np.r_[n.beam_nodes[2],n.beam_nodes[3]]
    relative=state.Q[ids]@np.swapaxes(system.Q0[ids],1,2)
    body=np.c_[state.r[ids]-system.r0[ids],Rotation.from_matrix(relative).as_rotvec()]
    global_wrench=np.r_[data['force'].sum(axis=0),
        (data['moment']+np.cross(state.r-origin,data['force'])).sum(axis=0)]
    return dict(node_body_motion=body,frame_velocity=state.U.copy(),frame_rates=state.Omega.copy(),
                gamma=state.gamma.copy(),wrenches=wrenches,
                family_forces=forces,family_moments_axis=moments,velocity=vector('relative_velocity'),
                global_applied_wrench_body=global_wrench)


def snapshot(system,z,zdot,*,forcing=None,raw_recorder=None):
    """Exactly one explicit native detailed residual; caller owns its budget."""
    state,_,options=system.physical_state(z,zdot,forcing=forcing)
    residual,data=system.network.residual(state.x,detail=True,**options)
    raw=dict(residual=residual,state={key:getattr(state,key) for key in
             ('x','r','Q','u','w','U','Omega','position','orientation','gamma')},
             aero=data['aero'],force=data['force'],moment=data['moment'],reactions=data['reactions'])
    if raw_recorder is not None:raw_recorder(raw)
    out=extract_outputs(system,state,data)
    return out,raw


def directional_outputs(system,Z,omega,forcings,input_metadata,*,step=2.5e-6,
                        include_baseline=True,recorder=None):
    """Fourth-order physical output stencils: ±h and ±2h, real and imaginary.

    Each input uses eight fresh detailed residuals. There is one optional
    baseline; three frequencies can share the separately retained baseline.
    The original input forcing applies +F3 or negative target.Mz only to the
    real part of the real-amplitude input. Every probe may be saved before its
    output transport checks, using recorder(label, raw).
    """
    import numpy as np
    Z=np.asarray(Z)
    if Z.shape!=(system.size,2) or len(forcings)!=2 or not 0<step<1e-3:
        raise ValueError('Expected two declared input columns and a fixed small width.')
    if input_metadata['signs'] != [1.,-1.]:
        raise ValueError('Physical fin-incidence/yaw input signs changed.')
    baseline=None
    if include_baseline:
        zero=np.zeros(system.size)
        baseline,_=snapshot(system,zero,zero,raw_recorder=None if recorder is None else
                            lambda raw:recorder('base',raw))
    columns=[];widths=[]
    for column in range(2):
        z=Z[:,column];zdot=1j*omega*z
        scale=float(input_metadata['channels'][column]['scale'])
        norm=max(float(np.max(abs(z))),float(np.max(abs(zdot)))/system.W)
        width=min(step*scale,step/norm) if norm else step*scale
        if not np.isfinite(width) or width<=0:raise ValueError('Invalid output width.')
        widths.append(width);parts=[]
        for part,component in enumerate((np.real,np.imag)):
            values=[]
            for multiplier in (1,-1,2,-2):
                increment=multiplier*width
                label=f'input-{column}-part-{part}-factor-{multiplier:+d}'
                forcing=forcings[column](part,increment*input_metadata['signs'][column])
                recorded=None if recorder is None else lambda raw,label=label,increment=increment: recorder(label,
                    dict(**raw,probe=dict(column=column,part=part,multiplier=multiplier,width=width,
                                         z=increment*component(z),zdot=increment*component(zdot),
                                         native_input_increment=increment*input_metadata['signs'][column] if part==0 else 0.)))
                out,_=snapshot(system,increment*component(z),increment*component(zdot),forcing=forcing,raw_recorder=recorded)
                values.append(out)
            parts.append({key:(8*(values[0][key]-values[1][key])-(values[2][key]-values[3][key]))/(12*width)
                          for key in values[0]})
        columns.append({key:parts[0][key]+1j*parts[1][key] for key in parts[0]})
    output={key:np.stack([value[key] for value in columns],axis=-1) for key in columns[0]}
    physical=output['global_applied_wrench_body'].copy();physical[5,1]+=1.
    output['physical_global_balance_body']=physical
    return output,dict(baseline=baseline,widths=widths,stencil='fourth order ±h/±2h for real/imaginary parts',
                       residual_calls=16+int(include_baseline),physical_yaw_added_to_global_column=1)


def reaction_response(system,Z):
    """Raw native support derivatives, with loaded first-node moment arms."""
    import numpy as np
    z=np.asarray(Z)
    if z.ndim==1:z=z[:,None]
    n=system.network;kin=z[:6*n.nn].reshape(n.nn,6,-1)
    scale_start=6*(n.nn+n.ne)
    out=[]
    for c in n.constraints:
        indices=scale_start+np.arange(c['sl'].start,c['sl'].stop)
        F=n.F*z[indices[:3]];T=n.F*n.L*z[indices[3:]]
        if c['b'] is None:
            out.append(dict(kind='ground',node=c['a'],force=F,moment=T));continue
        d=system.r0[c['b']]-system.r0[c['a']]
        delta_d=n.L*(kin[c['b'],:3]-kin[c['a'],:3])
        F0=n.F*system.base[indices[:3]]
        moment=T+np.cross(d,F.T).T+np.cross(delta_d.T,F0).T
        out.append(dict(kind='joint',node=c['a'],other_node=c['b'],force=F,moment=moment,
                        other_force=-F,other_moment=-T))
    return out


def physical_yaw_balance(raw_global,raw_ground,input_amplitudes):
    """Retain raw target-excluded loads separately from the physical +Mz input."""
    import numpy as np
    global_value=np.asarray(raw_global).copy();ground=np.asarray(raw_ground).copy()
    global_value[5] += input_amplitudes
    ground[5] -= input_amplitudes
    return global_value,ground
