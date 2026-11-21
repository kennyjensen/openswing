"""Independent seven-coordinate real mechanics plus lifting-line aerodynamics.

Source-only candidate until a frozen runner authorizes evaluation. Coordinates
are [Earth translation, Earth rotation vector, hinge angle] in a Galilean frame
translating at the nominal aircraft velocity. No production imports or solves.
"""
import numpy as np
from coupled_fin_aero_reference import Reference as Aero, rotation, left_jacobian, left_jacobian_rate, skew


class Mechanics:
    def __init__(self, fixture):
        self.fixture = fixture
        self.H = np.asarray(fixture['hinge']['position'], dtype=float)
        k = np.asarray(fixture['hinge']['axis'], dtype=float)
        self.k = k/np.sqrt(np.sum(k*k))
        self.stiffness = fixture['hinge']['stiffness']
        self.V0 = np.array([-fixture['speed'], 0., 0.])

    def bodies(self, q, dq, ddq):
        """Independent exact CG trajectories and angular kinematics."""
        q, dq, ddq = map(np.asarray, (q, dq, ddq))
        R, P = rotation(q[3:6]), rotation(q[6]*self.k)
        J = left_jacobian(q[3:6])
        omega = J@dq[3:6]
        alpha = J@ddq[3:6]+left_jacobian_rate(q[3:6], dq[3:6])@dq[3:6]
        rows = []
        for name in ('carrier','fin'):
            f = self.fixture[name]
            is_fin = name == 'fin'
            arm = P@(np.asarray(f['cg'])-self.H) if is_fin else np.asarray(f['cg'])
            local = self.H+arm if is_fin else arm
            tangent = np.cross(self.k, arm) if is_fin else np.zeros(3)
            curvature = np.cross(self.k, tangent) if is_fin else np.zeros(3)
            offset = R@local
            local_velocity = R@tangent*dq[6]
            velocity = dq[:3]+np.cross(omega, offset)+local_velocity
            acceleration = (ddq[:3]+np.cross(alpha, offset)
                + np.cross(omega,np.cross(omega,offset))
                + 2*np.cross(omega,local_velocity)
                + R@(tangent*ddq[6]+curvature*dq[6]**2))
            Q = R@P if is_fin else R
            inertia = Q@np.asarray(f['inertia'])@Q.T
            axis = R@self.k if is_fin else np.zeros(3)
            angular_velocity = omega+axis*dq[6]
            angular_acceleration = alpha+axis*ddq[6]+np.cross(omega,axis)*dq[6]
            Jv = np.column_stack([np.eye(3),-skew(offset)@J,R@tangent])
            Jw = np.column_stack([np.zeros((3,3)),J,axis])
            force = -f['mass']*acceleration
            couple = -inertia@angular_acceleration-np.cross(angular_velocity,inertia@angular_velocity)
            rows.append(dict(name=name,mass=f['mass'],position=q[:3]+offset,
                offset=offset,velocity=velocity,acceleration=acceleration,
                orientation=Q,inertia=inertia,angular_velocity=angular_velocity,
                angular_acceleration=angular_acceleration,Jv=Jv,Jw=Jw,
                inertial_force=force,inertial_couple_cg=couple,
                generalized_inertia_load=Jv.T@force+Jw.T@couple,
                inertial_wrench_origin=np.r_[force,np.cross(offset,force)+couple]))
        return rows

    def mass_matrix(self, q):
        rows = self.bodies(q,np.zeros(7),np.zeros(7))
        return sum(row['mass']*(row['Jv'].T@row['Jv'])
                   +row['Jw'].T@row['inertia']@row['Jw'] for row in rows)

    def balancer(self, q, manufacture):
        R, J = rotation(np.asarray(q)[3:6]),left_jacobian(np.asarray(q)[3:6])
        force, moment = (R@np.asarray(manufacture[k]) for k in ('carrier_force','carrier_moment'))
        return dict(generalized=np.r_[force,J.T@moment,0.],wrench_origin=np.r_[force,moment])

    def spring(self, q, manufacture):
        value = np.zeros(7,dtype=np.result_type(q,float))
        value[6] = -self.stiffness*(q[6]-manufacture['eta_rest_rad'])
        return value


class Coupled:
    def __init__(self, n, degree, fixture, field_recorder=None):
        self.n,self.degree,self.fixture = n,degree,fixture
        self.aero = Aero(n,degree,fixture,field_recorder=field_recorder)
        self.mechanics = Mechanics(fixture)
        self.evaluations = 0

    def base_system(self):
        return self.aero.base_system()

    def manufacture(self, gamma):
        """One independently derived, mesh-specific steady balancing load."""
        if self.degree != 32:
            raise ValueError('Only declared Q32 manufactures the loads')
        q=self.aero.base_coordinates();zero=np.zeros(7)
        packet=self.aero.evaluate(q,zero,zero,gamma,lag=False)
        wrench=packet['fin_wrench_origin'][0]
        value=dict(n=self.n,quadrature=self.degree,eta_rad=float(q[6]),
            eta_rest_rad=float(q[6]-packet['generalizedloads'][6]/self.mechanics.stiffness),
            carrier_force=-wrench[:3],carrier_moment=-wrench[3:],gamma=np.asarray(gamma).copy())
        return value,packet

    def evaluate(self,q,dq,ddq,gamma,gammadot,control,manufacture,lag):
        """Complete independent physical residual and observable quantities."""
        self.evaluations+=1
        q,dq,ddq,gamma,gammadot=map(np.asarray,(q,dq,ddq,gamma,gammadot))
        aero=self.aero.evaluate(q,dq,ddq,gamma,gammadot,control,lag=lag)
        bodies=self.mechanics.bodies(q,dq,ddq)
        bal=self.mechanics.balancer(q,manufacture)
        spring=self.mechanics.spring(q,manufacture)
        inertial=sum(b['generalized_inertia_load'] for b in bodies)
        # Inertial reactions carry a minus sign. This is inertia minus applied
        # generalized loads; no extra apparent mass is added here.
        physical=-(inertial+bal['generalized']+spring+aero['generalizedloads'])
        residual=np.r_[physical,aero['residual']]
        kin=aero['geometry']['kinematics'];R=kin['R'];J=kin['J']
        point_positions=np.array([b['position'] for b in bodies])
        mass_wrench=np.array([b['inertial_wrench_origin'] for b in bodies])
        global_wrench=mass_wrench.sum(axis=0)+bal['wrench_origin']+aero['fin_wrench_origin'][0]
        fin=bodies[1]
        inertial_fin_hinge=np.r_[fin['inertial_force'],
            fin['inertial_couple_cg']+np.cross(fin['position']-kin['hinge'],fin['inertial_force'])]
        reaction=-(aero['fin_wrench_hinge'][0]+inertial_fin_hinge)
        def body_wrench(value):
            value=np.asarray(value)
            return np.concatenate([value[...,:3]@R,value[...,3:]@R],axis=-1)
        # Earth points are recorded at the zero-time reference slice. Their
        # perturbations include carrier translation; constant V0 is in velocity.
        nodes=kin['hinge']+self.aero.t[:,None]*aero['geometry']['s']
        node_velocity=np.array([self.aero.point_velocity(p,kin) for p in nodes])+self.mechanics.V0
        output=dict(frame_position_earth=q[:3],frame_rotation_vector=q[3:6],
            frame_velocity_body=R.T@(self.mechanics.V0+dq[:3]),
            frame_rates_body=R.T@kin['omega_carrier'],
            frame_acceleration_body=R.T@ddq[:3],frame_angular_acceleration_body=R.T@kin['alpha_carrier'],
            hinge_angle=np.array([q[6]]),hinge_rate=np.array([dq[6]]),gamma=gamma,
            fin_node_position_earth=nodes,fin_node_velocity_earth=node_velocity,
            fin_angular_velocity_earth=kin['omega_fin'],mass_point_positions_earth=point_positions,
            aero_wrenches_earth=aero['wrenches'],aero_wrenches_body=body_wrench(aero['wrenches']),
            mass_wrenches_body=body_wrench(mass_wrench),global_applied_wrench_body=body_wrench(global_wrench),
            hinge_reaction_on_fin_body=body_wrench(reaction),spring_generalized_force=spring,
            generalized_aerodynamic_load=aero['generalizedloads'])
        return dict(residual=residual,output=output,aero=aero,bodies=bodies,balancer=bal,
                    spring=spring,generalized_inertia_load=inertial)

    def linearize(self,gamma,manufacture,lag,epsilon,recorder=None):
        """Complex-step full residual/output derivatives; no matrix solves.

        Exactly22+2n evaluations: q7,v7,a7,Gamma n,Gamma_dot n,control1.
        Outputs are differentiated during these same evaluations and reused.
        """
        q=self.aero.base_coordinates();zero=np.zeros(7);gzero=np.zeros(self.n)
        sizes={'q':7,'v':7,'a':7,'gamma':self.n,'gamma_rate':self.n,'control':1}
        residual={};outputs={};shapes={}
        for group,size in sizes.items():
            columns=[];output_columns={}
            for j in range(size):
                args=dict(q=q.astype(complex),dq=zero.astype(complex),ddq=zero.astype(complex),
                          gamma=np.asarray(gamma,dtype=complex).copy(),gammadot=gzero.astype(complex),control=0j)
                if group=='control':args['control']=1j*epsilon
                else:args[{'v':'dq','a':'ddq','gamma_rate':'gammadot'}.get(group,group)][j]+=1j*epsilon
                packet=self.evaluate(**args,manufacture=manufacture,lag=lag)
                if recorder is not None:recorder(group,j,args,packet)
                columns.append(np.imag(packet['residual'])/epsilon)
                for key,value in packet['output'].items():
                    shapes[key]=np.asarray(value).shape
                    output_columns.setdefault(key,[]).append(np.imag(value).ravel()/epsilon)
            residual[group]=np.column_stack(columns)
            for key,cols in output_columns.items():outputs.setdefault(key,{})[group]=np.column_stack(cols)
        return dict(residual=residual,outputs=outputs,output_shapes=shapes,epsilon=epsilon,lag=lag)

    @staticmethod
    def harmonic(derivative,omega):
        lam=1j*omega;r=derivative['residual']
        matrix=np.column_stack([r['q']+lam*r['v']+lam*lam*r['a'],r['gamma']+lam*r['gamma_rate']])
        rhs=np.column_stack([-r['control'][:,0],np.zeros(len(matrix))])
        rhs[5,1]=1. # Physical positive carrier yaw couple, not native +target.Mz.
        return matrix,rhs

    @staticmethod
    def recover(derivative,omega,solution):
        """Recover both inputs; retain the native excluded-input net wrench.

        The physical balance also includes the unit carrier yaw couple in
        column two. Applying that correction symmetrically prevents a target
        convention from masquerading as a force-balance error.
        """
        lam=1j*omega;q=solution[:7];gamma=solution[7:]
        out={}
        for key,blocks in derivative['outputs'].items():
            value=((blocks['q']+lam*blocks['v']+lam*lam*blocks['a'])@q
                   +(blocks['gamma']+lam*blocks['gamma_rate'])@gamma)
            value[:,0]+=blocks['control'][:,0]
            out[key]=value.reshape((*derivative['output_shapes'][key],solution.shape[1]))
        out['physical_global_balance_body']=out['global_applied_wrench_body'].copy()
        out['physical_global_balance_body'][5,1]+=1.
        return out
