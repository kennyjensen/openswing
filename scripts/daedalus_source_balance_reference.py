"""Independent stationary current-source force/moment and constraint balance.

No production imports. Parsed endpoint materials, topology and the declared
source averaging policy are inputs. Raw descriptor amplitudes supply motion,
internal resultants and reactions. Aerodynamics is evaluated independently by
the companion source reference. This does not evaluate beam compatibility.
"""
import numpy as np
from elastic_fin_kinematics import hat
from wing_inertia_reference import evaluate as distributed_inertia, PARTS


def cross_matrix(v):
    return np.array([hat(x) for x in v])


def chart(fixture, z, frequency):
    layout=fixture['layout'];base=fixture['base'];nn=layout['nodes'];ne=layout['elements']
    w=2*np.pi*frequency;L=layout['node_coordinates']['translation_scale']
    F=layout['internal_loads']['force_scale'];ML=layout['internal_loads']['moment_scale']
    vs=layout['local_velocity']['start'];fs=layout['frame']['start']
    V=layout['local_velocity']['scale'];W=layout['local_rates']['scale']
    pose=z[:6*nn].reshape(nn,6);u,rates=z[vs:fs].reshape(2,nn,3)
    internal=z[6*nn:6*(nn+ne)].reshape(ne,6)
    frame=z[fs:fs+12].reshape(4,3)
    phi,theta,psi=np.deg2rad(base['attitude_deg'])
    def rx(a):
        c,s=np.cos(a),np.sin(a);return np.array([[1,0,0],[0,c,-s],[0,s,c]])
    def ry(a):
        c,s=np.cos(a),np.sin(a);return np.array([[c,0,s],[0,1,0],[-s,0,c]])
    def rz(a):
        c,s=np.cos(a),np.sin(a);return np.array([[c,-s,0],[s,c,0],[0,0,1]])
    rotation=rz(-psi)@ry(theta)@rx(-phi)
    euler=np.array([[-1,0,np.sin(theta)],
        [0,np.cos(phi),np.sin(phi)*np.cos(theta)],
        [0,np.sin(phi),-np.cos(phi)*np.cos(theta)]])
    # Independent check against derivatives of the composed Earth rotation,
    # retaining the signs for ASWING bank/elevation/heading.
    orientation=lambda v:rz(-v[2])@ry(v[1])@rx(-v[0])
    for j in range(3):
        increment=np.eye(3)[j]*1e-5;angles=np.array([phi,theta,psi])
        derivative=(orientation(angles+increment)-orientation(angles-increment))/(2e-5)
        assert np.max(abs(rotation.T@derivative-hat(euler[:,j])))<2e-8
    frame_angle=euler@frame[3];U=V*frame[0];Omega=W*frame[1]
    acceleration=1j*w*U+np.cross(Omega,base['U'])
    angular_acceleration=1j*w*Omega
    op=layout['operating'];opvalue=np.array(op['scales'])*z[op['start']:op['start']+6]
    assert np.max(abs(fixture['aero']['reference'][2:]))==0,'This stationary fixture has zero reference offsets.'
    dr=L*pose[:,:3];dtheta=pose[:,3:];u=V*u;rates=W*rates
    kinematics=np.r_[((1j*w*dr-u)/V).ravel(),((1j*w*dtheta-rates)/W).ravel(),
        (acceleration-opvalue[:3])/fixture['acceleration_scale'],
        (angular_acceleration-opvalue[3:])/W**2,
        (1j*w*L*frame[2]-rotation@(U+np.cross(frame_angle,base['U'])))/V,
        (1j*w*frame_angle-Omega)/W]
    return dict(dr=dr,theta=dtheta,dQ=cross_matrix(dtheta)@base['Q'],u=u,w=rates,
        U=U,Omega=Omega,a=acceleration,alpha=angular_acceleration,
        dg=-np.cross(frame_angle,base['gravity']),
        dN=F*internal[:,:3],dM=ML*internal[:,3:],
        reactions=z[layout['reactions']['start']:layout['circulation']['start']],
        kinematics=kinematics,orientation=rotation,frame_angle=frame_angle,omega=w)


def wrench(r, force, moment, origin):
    return np.r_[force.sum(axis=0),(moment+np.cross(r-origin,force)).sum(axis=0)]


def derivative_wrench(r, dr, f0, df, dm, origin):
    return np.r_[df.sum(axis=0),(dm+np.cross(r-origin,df)+np.cross(dr,f0)).sum(axis=0)]


def inertia(fixture, motion):
    base=fixture['base'];r=base['r'];zero=np.zeros(3,complex);parts=[];labels=[]
    forces=[];moments=[];base_forces=[];base_moments=[]
    for sample in fixture['mass_samples']:
        value=distributed_inertia(sample,motion['dr'],motion['theta'],motion['u'],motion['w'],
            motion['U'],motion['Omega'],motion['omega'],zero)
        parts.append(value['wrenches']);labels.append('beam'+str(sample['beam']))
        forces.append(value['nodal_force'].sum(axis=0));moments.append(value['nodal_moment'].sum(axis=0))
        base_forces.append(value['base_force']);base_moments.append(value['base_moment'])
    # All literal Daedalus point inertias/spins vanish; retain their moving
    # pylon arms and parallel-axis inertia through their actual acceleration.
    point_f=np.zeros((len(PARTS),len(r),3),complex);point_m=np.zeros_like(point_f)
    point_f0=np.zeros_like(r);point_m0=np.zeros_like(r)
    for record in fixture['aero']['attachments']['weight']:
        row=np.asarray(record['row']);node=record['node'];assert np.max(abs(row[8:]))==0
        mass=row[5]/fixture['aero']['constants'][0];arm=base['Q'][node]@record['offset']
        darm=np.cross(motion['theta'][node],arm);position=r[node]+arm
        accelerations=[1j*motion['omega']*motion['U'],np.cross(motion['Omega'],base['U']),
            np.cross(motion['alpha'],position),1j*motion['omega']*motion['u'][node],
            np.cross(1j*motion['omega']*motion['w'][node],arm)]
        f0=mass*base['gravity'];point_f0[node]+=f0;point_m0[node]+=np.cross(arm,f0)
        for j,a in enumerate(accelerations):
            f=-mass*a;point_f[j,node]+=f;point_m[j,node]+=np.cross(arm,f)
        f=mass*motion['dg'];point_f[7,node]+=f;point_m[7,node]+=np.cross(arm,f)
        point_m[8,node]+=np.cross(darm,f0)
    origin=fixture['aero']['reference'][1]
    point_parts=np.array([wrench(r,f,m,origin) for f,m in zip(point_f,point_m)])
    point_parts[9,3:]+=np.cross(motion['dr'],point_f0).sum(axis=0)
    parts.append(point_parts);labels.append('points')
    forces.append(point_f.sum(axis=0));moments.append(point_m.sum(axis=0))
    base_forces.append(point_f0);base_moments.append(point_m0)
    return dict(force=np.array(forces),moment=np.array(moments),base_force=np.array(base_forces),
        base_moment=np.array(base_moments),parts=np.array(parts),labels=labels)


def aerodynamic_transfer(fixture, motion, base_loads, derivative_loads):
    """Differentiate the conservative section-to-node wrench translation."""
    r=fixture['base']['r'];dr=motion['dr'];ends=fixture['aero']['ends'];base=fixture['base']
    f0=np.zeros_like(r);m0=np.zeros_like(r);df=np.zeros_like(r,dtype=complex);dm=np.zeros_like(df)
    start=0;labels=[];group_wrenches=[]
    origin=fixture['aero']['reference'][1]
    for beam in fixture['aero']['beams']:
        ids=beam['element_ids'];a,b=ends[ids].T;fraction=beam['fraction'][:,None]
        arm=(fraction-.5)*(r[b]-r[a]);darm=(fraction-.5)*(dr[b]-dr[a])
        if beam['lifting']:
            sl=slice(start,start+len(ids));start+=len(ids)
            F,M=(base_loads['lifting_'+key][sl] for key in ('force','moment'))
            dF,dM=(derivative_loads['lifting_'+key][sl] for key in ('force','moment'))
        else:
            F,M=(base_loads['body_'+key] for key in ('force','moment'))
            dF,dM=(derivative_loads['body_'+key] for key in ('force','moment'))
        nf0=np.zeros_like(r);nm0=np.zeros_like(r);nf=np.zeros_like(df);nm=np.zeros_like(dm)
        for nodes in (a,b):
            np.add.at(nf0,nodes,F/2);np.add.at(nm0,nodes,(M+np.cross(arm,F))/2)
            np.add.at(nf,nodes,dF/2);np.add.at(nm,nodes,(dM+np.cross(darm,F)+np.cross(arm,dF))/2)
        labels.append('beam'+str(beam['index']));group_wrenches.append(derivative_wrench(r,dr,nf0,nf,nm,origin))
        f0+=nf0;m0+=nm0;df+=nf;dm+=nm
    for kind,key in [('weight','point'),('engine','engine')]:
        nf0=np.zeros_like(r);nf=np.zeros_like(df);nm=np.zeros_like(dm)
        for j,record in enumerate(fixture['aero']['attachments'][kind]):
            node=record['node'];arm=base['Q'][node]@record['offset'];darm=motion['dQ'][node]@record['offset']
            F=base_loads[key+'_force'][j];dF=derivative_loads[key+'_force'][j]
            M=base_loads['engine_moment'][j] if key=='engine' else np.zeros(3)
            dM=derivative_loads['engine_moment'][j] if key=='engine' else np.zeros(3,complex)
            f0[node]+=F;m0[node]+=M+np.cross(arm,F)
            df[node]+=dF;dm[node]+=dM+np.cross(arm,dF)+np.cross(darm,F)
            nf0[node]+=F;nf[node]+=dF;nm[node]+=dM+np.cross(arm,dF)+np.cross(darm,F)
        labels.append(key);group_wrenches.append(derivative_wrench(r,dr,nf0,nf,nm,origin))
    return dict(base_force=f0,base_moment=m0,force=df,moment=dm,
                group_wrenches=np.array(group_wrenches),labels=labels)


def mechanics(fixture,motion):
    """Beam resultant and rigid-joint conservation; live offset braces."""
    base=fixture['base'];r=base['r'];dr=motion['dr'];ends=fixture['aero']['ends'];a,b=ends.T
    parts=[];bases=[];labels=[];constraints=[]
    f0=np.zeros_like(r);m0=np.zeros_like(r);df=np.zeros_like(r,dtype=complex);dm=np.zeros_like(df)
    delta=r[b]-r[a];ddelta=dr[b]-dr[a];N=base['N'];M=base['M'];dN=motion['dN'];dM=motion['dM']
    for nodes,sign in ((a,1),(b,-1)):
        np.add.at(f0,nodes,sign*N);np.add.at(m0,nodes,sign*M+np.cross(delta,N)/2)
        np.add.at(df,nodes,sign*dN);np.add.at(dm,nodes,sign*dM+(np.cross(ddelta,N)+np.cross(delta,dN))/2)
    bases.append((f0,m0));parts.append((df,dm));labels.append('beam_internal')
    F=fixture['layout']['internal_loads']['force_scale'];ML=fixture['layout']['internal_loads']['moment_scale']
    L=fixture['layout']['node_coordinates']['translation_scale']
    for name in ('joint','ground'):
        f0=np.zeros_like(r);m0=np.zeros_like(r);df=np.zeros_like(r,dtype=complex);dm=np.zeros_like(df)
        for c in fixture['constraints']:
            if c['kind']!=name:continue
            assert c['type']==0
            i,j=c['a'],c['b'];sl=slice(*c['slice']);v=base['reactions'][sl];dv=motion['reactions'][sl]
            force=F*v[:3];couple=ML*v[3:];dforce=F*dv[:3];dcouple=ML*dv[3:]
            f0[i]+=force;m0[i]+=couple;df[i]+=dforce;dm[i]+=dcouple
            if j is not None:
                d=r[j]-r[i];dd=dr[j]-dr[i]
                f0[j]-=force;m0[j]-=couple;m0[i]+=np.cross(d,force)
                df[j]-=dforce;dm[j]-=dcouple;dm[i]+=np.cross(dd,force)+np.cross(d,dforce)
                anchor=base['Q'][i]@(fixture['jig_positions'][j]-fixture['jig_positions'][i])
                constraints.append((c['slice'][0],np.r_[(dd-np.cross(motion['theta'][i],anchor))/L,
                    base['Q'][i].T@(motion['theta'][j]-motion['theta'][i])]))
            else:constraints.append((c['slice'][0],np.r_[dr[i]/L,motion['theta'][i]]))
        bases.append((f0,m0));parts.append((df,dm));labels.append(name)
    f0=np.zeros_like(r);m0=np.zeros_like(r);df=np.zeros_like(r,dtype=complex);dm=np.zeros_like(df)
    anchor_wrench=np.zeros(6,complex);origin=fixture['aero']['reference'][1]
    for item in fixture['struts']:
        row=np.asarray(item['row']);i=item['node'];arm=base['Q'][i]@(row[2:5]-fixture['jig_positions'][i])
        darm=np.cross(motion['theta'][i],arm);position=r[i]+arm;dposition=dr[i]+darm
        rest=np.linalg.norm(row[5:8]-row[2:5])+row[8];vector=row[5:8]-position
        length=np.linalg.norm(vector);direction=vector/length;stiffness=row[9]/rest;tension=stiffness*(length-rest)
        force=tension*direction;k=stiffness*np.outer(direction,direction)+tension/length*(np.eye(3)-np.outer(direction,direction))
        dforce=-k@dposition
        f0[i]+=force;m0[i]+=np.cross(arm,force);df[i]+=dforce;dm[i]+=np.cross(arm,dforce)+np.cross(darm,force)
        anchor_wrench-=np.r_[dforce,np.cross(row[5:8]-origin,dforce)]
    bases.append((f0,m0));parts.append((df,dm));labels.append('struts')
    base_force=np.array([p[0] for p in bases]);base_moment=np.array([p[1] for p in bases])
    force=np.array([p[0] for p in parts]);moment=np.array([p[1] for p in parts])
    wrenches=np.array([derivative_wrench(r,dr,f,df,dm,origin) for f,df,dm in zip(base_force,force,moment)])
    return dict(base_force=base_force,base_moment=base_moment,force=force,moment=moment,
        wrenches=wrenches,labels=labels,constraints=np.concatenate([v for _,v in sorted(constraints)]),
        anchor_wrench=anchor_wrench)
