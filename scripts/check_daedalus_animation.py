"""Bounded image geometry and harmonic-state comparisons for Drela's movies.

The camera is inferred from the literal fairing outline, not fitted to Bode
outputs. Raster fits are image measurements, not physical-validation passes.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
LIMITS=dict(address_space_bytes=512*1024**2,cpu_seconds=15,wall_seconds=25)
MOVIES=ROOT/'reference/daedalus-rudder-animations-20261113'
STUDY=ROOT/'artifacts/daedalus-animation-calibration-20261113'
SOURCE=ROOT/'artifacts/daedalus-source-20261113'


def read(p):return json.loads(Path(p).read_text())
def write(p,v):
    with Path(p).open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
def pin(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def utc():return datetime.now(timezone.utc).isoformat()


def camera(folder,args):
    import numpy as np
    from scipy.optimize import least_squares
    from scipy.spatial import ConvexHull
    from scipy.ndimage import label,binary_dilation
    from PIL import Image
    from openswing.asw import parse_asw
    model=parse_asw((ROOT/'examples/dae.asw').read_text(),beam_interpolation='drela-segspl-v1')
    beam=next(b for b in model.beams if b.index==5)
    t=np.unique(np.r_[np.linspace(*beam.domain,501),beam.distributions['chord'].t])
    r=beam.position(t);chord=beam.value('chord',t);axis=beam.value('Xax',t)
    leading=r[:,[0,2]].copy();leading[:,0]-=axis*chord
    trailing=leading.copy();trailing[:,0]+=chord
    points=np.r_[leading,trailing]
    hull=points[ConvexHull(points).vertices]
    theta=np.linspace(0,2*np.pi,180,endpoint=False)
    normals=np.c_[np.cos(theta),np.sin(theta)]
    result=[]
    for name,frequency in [('slow-rudder',.2),('fast-rudder',1.)]:
        movie=Image.open(MOVIES/(name+'.gif'));rows=[]
        for frame in range(args.start,min(91,args.start+args.count),5):
            movie.seek(frame);rgb=np.asarray(movie.convert('RGB')).astype(int)
            mask=(rgb[:,:,0]<100)&(rgb[:,:,2]>150)&(rgb[:,:,1]<200)&((rgb[:,:,2]-rgb[:,:,1])>40)
            mask[:200,:]=False
            labels,count=label(binary_dilation(mask,iterations=1))
            sizes=np.bincount(labels[mask],minlength=count+1);sizes[0]=0
            # Fine raster lines are disconnected. Keep all substantial pieces
            # rather than silently dropping the forward or aft outline.
            mask &= sizes[labels]>=5
            yy,xx=np.nonzero(mask);pixels=np.c_[xx,yy]
            assert len(pixels)>100,(name,frame,len(pixels))
            observed=pixels[ConvexHull(pixels).vertices]
            target=np.max(normals@observed.T,axis=1)
            def prediction(p,derivative=False):
                a=p[:4].reshape(2,2);b=p[4:6]
                projected=hull@a.T+b
                selected=np.argmax(normals@projected.T,axis=1)
                q=hull[selected]
                if derivative:
                    return np.c_[normals[:,0,None]*q,normals[:,1,None]*q,normals,np.ones(len(normals))]
                return np.sum(normals*projected[selected],axis=1)+p[6]
            a=np.array([[10.,0.],[1.4,-10.7]])
            initial=np.r_[a.ravel(),observed.mean(axis=0)-a@hull.mean(axis=0),.5]
            fit=least_squares(lambda p:prediction(p)-target,initial,
                jac=lambda p:prediction(p,True),
                bounds=([5.,-6.,-6.,-16.,250.,300.,0.],[16.,6.,6.,-5.,550.,550.,1.5]),
                xtol=1e-11,ftol=1e-11,gtol=1e-10,max_nfev=200)
            assert fit.success,(name,frame,fit.message)
            a=fit.x[:4].reshape(2,2);b=fit.x[4:6]
            vals,vecs=np.linalg.eigh(a@a.T);scale=np.sqrt(vals[-1])
            transverse=vecs[:,0]*np.sqrt(max(vals[-1]-vals[0],0))
            if transverse[0]<0:transverse=-transverse
            projection=np.c_[a[:,0],transverse,a[:,1]]
            np.testing.assert_allclose(projection@projection.T,scale**2*np.eye(2),rtol=1e-12,atol=1e-11)
            axes=projection/scale
            orientation=np.vstack([axes,np.cross(axes[0],axes[1])])
            row=dict(frame=frame,time_seconds=frame/(90*frequency),blue_pixels=len(pixels),
                affine_xz=a.tolist(),offset=b.tolist(),padding_px=float(fit.x[6]),
                scale_px_per_ft=float(scale),projection=projection.tolist(),orientation=orientation.tolist(),
                support_rms_px=float(np.sqrt(np.mean(fit.fun**2))),support_max_px=float(max(abs(fit.fun))),
                evaluations=fit.nfev,observed_hull=observed.tolist(),projected_hull=(hull@a.T+b).tolist())
            rows.append(row)
            print(name,frame,row['support_rms_px'],row['support_max_px'],scale,flush=True)
        movie.close();result.append(dict(name=name,frequency_hz=frequency,frames=rows))
    return dict(cameras=result,literal_outline_xz=hull.tolist(),
        method='Affine fit of literal fairing convex-hull support functions, 180 normals; orthographic completion uses equal-scale perpendicular image axes.',
        qualifications=['Camera fit only; no Bode or deformation target enters the fit.',
            'Orthographic projection, rigid fairing, SEGSPL outline and one-pixel raster bounds are hypotheses to verify.',
            'Padding is bounded to 0–1.5 pixels; high residuals or bound hits must remain visible.',
            'World transverse sign is selected so positive y projects rightward.'])


def states(folder,args):
    import numpy as np
    import scipy.sparse as sp
    from openswing.frequency_response import harmonic_solve
    from openswing.harmonic_structure import ReusableBeamStructure
    matrix=SOURCE/'assembled-6.7'
    assert read(matrix/'terminal.json')['returncode']==0
    a,m=(sp.load_npz(matrix/name) for name in ('A.npz','M.npz'))
    maps=np.load(matrix/'maps.npz')
    for pencil in (a,m):
        for array in (pencil.data,pencil.indices,pencil.indptr):array.flags.writeable=False
    structure=ReusableBeamStructure(a,m,np.r_[np.arange(618),np.arange(1266,1296)],
        np.arange(1266),np.arange(1384,2032),np.arange(1384,2032))
    rows=[];vectors=[]
    for f in (.2,1.):
        z,checks=harmonic_solve(a,m,maps['B'][:,0],2*np.pi*f,_structure=structure)
        out=maps['C']@z;vectors.append(z)
        rows.append(dict(frequency_hz=f,outputs_real=out.real.tolist(),outputs_imag=out.imag.tolist(),
            checks=checks))
    np.savez_compressed(folder/'states.npz',frequencies=[.2,1.],states=np.array(vectors))
    layout=read(SOURCE/'mass-6.7/layout.json');seed=read(SOURCE/'trim-6.7-1/state.json')
    # Physical state extraction does not reconstruct or alter the matrices.
    write(folder/'layout.json',layout);write(folder/'equilibrium.json',seed)
    for j,row in enumerate(rows):
        motions=vectors[j][:648].reshape(108,6).copy()
        motions[:,:3]*=layout['node_coordinates']['translation_scale']
        row['beams']={}
        for key,(t,indices) in seed['identity']['stations'].items():
            v=motions[np.array(indices)]
            row['beams'][key]=dict(stations=t,indices=indices,
                translation_real=v[:,:3].real.tolist(),translation_imag=v[:,:3].imag.tolist(),
                rotation_real=v[:,3:].real.tolist(),rotation_imag=v[:,3:].imag.tolist(),
                max_translation_40=float(np.max(abs(v[:,:3]))*40),
                max_rotation_degrees_40=float(np.max(abs(v[:,3:]))*40*180/np.pi))
        print(f"frequency={row['frequency_hz']} outputs={abs(maps['C']@vectors[j]).tolist()}",flush=True)
    return dict(samples=rows,units='Native feet/radians per unit F3; display amplitude 40 is reported separately.',
        source='Fresh source endpoint/SEGSPL, 6.7 m/s, C16 pointwise accepted trim and matrices',
        structure=structure.report)


def curvature(folder,args):
    """Image curvature relative to the local forward boom tangent.

    A rigid straight line stays straight under both orthographic and perspective
    projection. These are pixel-space observations, not inferred feet of bending.
    """
    import numpy as np
    from PIL import Image
    rows=[]
    cameras=read(STUDY/'fairing-pieces/result.json')['cameras']
    for movie_info in cameras:
        name=movie_info['name'];movie=Image.open(MOVIES/(name+'.gif'));samples=[]
        for cam in movie_info['frames']:
            frame=cam['frame'];movie.seek(frame);rgb=np.asarray(movie.convert('RGB')).astype(int)
            mask=(rgb[:,:,0]<100)&(rgb[:,:,1]>150)&(rgb[:,:,2]>150)&(abs(rgb[:,:,1]-rgb[:,:,2])<30)
            yy,xx=np.nonzero(mask & (np.indices(mask.shape)[0]>200))
            a=np.array(cam['affine_xz']);b=np.array(cam['offset'])
            # Use the fairing top x as a repeatable local landmark. Native
            # displayed cyan symbols may extend past the physical beam ends.
            mount=(a@np.array([2.5,0.])+b)[0];sx=a[0,0]
            select=(xx>mount-8*sx)&(xx<mount+16*sx)
            x,y=xx[select],yy[select]
            # Remove palette outliers by a broad 8-pixel corridor around the
            # central beam. All subsequent pixel observations are retained.
            middle=(x>mount-3*sx)&(x<mount+8*sx)
            line=np.polyfit(x[middle]-mount,y[middle],1)
            select=abs(y-np.polyval(line,x-mount))<8
            x,y=x[select],y[select]
            ux=np.unique(x);uy=np.array([np.mean(y[x==v]) for v in ux])
            # Single cubic across the observed centerline; report independent
            # fore-tangent extrapolation as well as residuals/actual pixels.
            xi=(ux-mount)/sx
            p=np.polynomial.polynomial.polyfit(xi,uy,3)
            residual=uy-np.polynomial.polynomial.polyval(xi,p)
            fore=(xi>=-7)&(xi<=0)
            front=np.polyfit(xi[fore],uy[fore],1)
            aft=(xi>=13)&(xi<=15.5)
            assert np.sum(fore)>10 and np.sum(aft)>6
            departure=float(np.mean(uy[aft]-np.polyval(front,xi[aft])))
            samples.append(dict(frame=frame,time_seconds=cam['time_seconds'],mount_x=float(mount),
                px_per_x_ft=float(sx),pixels=np.c_[ux,uy].tolist(),polynomial=p.tolist(),
                cubic_rms_px=float(np.sqrt(np.mean(residual**2))),
                cubic_max_px=float(max(abs(residual))),fore_line=front.tolist(),
                aft_departure_from_fore_tangent_px=departure))
        phase=np.array([2*np.pi*s['frame']/90 for s in samples])
        design=np.c_[np.ones(len(phase)),np.cos(phase),np.sin(phase)]
        values=np.array([s['aft_departure_from_fore_tangent_px'] for s in samples])
        fit=np.linalg.lstsq(design,values,rcond=None)[0]
        row=dict(name=name,frequency_hz=movie_info['frequency_hz'],samples=samples,
            mean_cos_sin_departure_px=fit.tolist(),amplitude_px=float(np.linalg.norm(fit[1:])),
            harmonic_max_residual_px=float(max(abs(design@fit-values))))
        rows.append(row);print(name,'amplitude',row['amplitude_px'],'residual',row['harmonic_max_residual_px'],flush=True)
    return dict(traces=rows,qualification='Raster curvature relative to observed forward tangent; no physical units or Bode pass inferred.')


def compare(folder,args):
    import numpy as np
    from scipy.spatial.transform import Rotation
    cameras=read(STUDY/'fairing-pieces/result.json')['cameras']
    traces=read(STUDY/'boom-curvature/result.json')['traces']
    seed=read(STUDY/'full-states/equilibrium.json')
    state_info=read(STUDY/'full-states/result.json')['samples']
    joint=[]
    if args.projective:
        for start in (0,20,40,60,80):joint+=read(STUDY/f'camera-joint-{start}/result.json')['fits']
    output=[]
    for cams,trace,state in zip(cameras,traces,state_info):
        assert cams['frequency_hz']==state['frequency_hz']==trace['frequency_hz']
        beam=state['beams']['4'];t=np.array(beam['stations']);indices=np.array(beam['indices'])
        r=np.array(seed['positions'])[indices]
        dr=np.array(beam['translation_real'])+1j*np.array(beam['translation_imag'])
        stations=np.linspace(t[0],t[-1],1001)
        r=np.array([np.interp(stations,t,r[:,j]) for j in range(3)]).T
        dr=np.array([np.interp(stations,t,dr[:,j]) for j in range(3)]).T
        angles=2*np.pi*np.array([cam['frame'] for cam in cams['frames']])/90
        design=np.c_[np.ones(len(angles)),np.cos(angles),np.sin(angles)]
        predictions=[];mean_projection=np.mean([cam['projection'] for cam in cams['frames']],axis=0)
        if args.projective:
            jc=sorted([v for v in joint if v['name']==cams['name'] and v['perspective']],key=lambda v:v['frame'])
            assert all(v['success'] for v in jc)
            mean_rotation=Rotation.from_matrix([v['rotation'] for v in jc]).mean().as_matrix()
            mean_parameters=np.median([v['parameters'] for v in jc],axis=0)
        for moving in (False,True):
            baseline=[];cosine=[];sine=[]
            for ci,cam in enumerate(cams['frames']):
                p=np.array(cam['projection']) if moving else mean_projection
                if args.projective:
                    parameters=np.array(jc[ci]['parameters']) if moving else mean_parameters
                    rotation=np.array(jc[ci]['rotation']) if moving else mean_rotation
                    rotated=r@rotation.T;d=1+parameters[6]*rotated[:,2]
                    base=parameters[3]*rotated[:,:2]/d[:,None]+parameters[4:6]
                    derivative=parameters[3]*(rotation[None,:2,:]/d[:,None,None]
                        -parameters[6]*rotated[:,:2,None]*rotation[None,2,None,:]/d[:,None,None]**2)
                    delta=40*np.einsum('nij,nj->ni',derivative,dr)
                else:base=r@p.T+cam['offset'];delta=40*dr@p.T
                mount=(np.array(cam['affine_xz'])@np.array([2.5,0.])+cam['offset'])[0]
                xi=(base[:,0]-mount)/cam['affine_xz'][0][0]
                fore=(xi>=-7)&(xi<=0);aft=(xi>=13)&(xi<=15.5)
                slope=np.polyfit(xi[fore],base[fore,1],1)
                displacement=delta[:,1]-slope[0]*delta[:,0]/cam['affine_xz'][0][0]
                coeff=np.polyfit(xi[fore],displacement[fore],1)
                response=np.mean(displacement[aft]-np.polyval(coeff,xi[aft]))
                baseline.append(np.mean(base[aft,1]-np.polyval(slope,xi[aft])))
                cosine.append(response.real);sine.append(-response.imag)
            baseline=np.array(baseline);cosine=np.array(cosine);sine=np.array(sine)
            observed=np.array([s['aft_departure_from_fore_tangent_px'] for s in trace['samples']])
            variants=[]
            # Unknown movie starting phase is disclosed, not an aerodynamic
            # parameter. Fit only that phase, without an amplitude multiplier.
            for offset in np.linspace(-np.pi,np.pi,721):
                predicted=baseline+cosine*np.cos(angles+offset)+sine*np.sin(angles+offset)
                centered=predicted-np.mean(predicted)
                error=np.sqrt(np.mean((centered-(observed-np.mean(observed)))**2))
                variants.append((error,offset,predicted))
            error,offset,predicted=min(variants,key=lambda item:item[0])
            harmonic=np.linalg.lstsq(design,predicted,rcond=None)[0]
            zero=baseline+cosine*np.cos(angles)+sine*np.sin(angles)
            row=dict(moving_camera=moving,best_phase_degrees=float(np.rad2deg(offset)),
                best_phase_rms_px=float(error),prediction_mean_cos_sin=harmonic.tolist(),
                predicted_amplitude_px=float(np.linalg.norm(harmonic[1:])),
                observed_amplitude_px=trace['amplitude_px'],
                predicted_departure_px=predicted.tolist(),zero_phase_departure_px=zero.tolist(),
                camera_baseline_departure_px=baseline.tolist(),
                local_complex_response_real=cosine.tolist(),local_complex_response_imag=(-sine).tolist())
            predictions.append(row)
        # Affine fairing pose differences give a separate, approximate angular
        # diagnostic. Perspective/raster errors limit high-frequency yaw.
        rotations=np.array([v['rotation'] for v in jc]) if args.projective else np.array([cam['orientation'] for cam in cams['frames']])
        mean_rotation=Rotation.from_matrix(rotations).mean().as_matrix()
        relative=Rotation.from_matrix(np.einsum('ij,njk->nik',mean_rotation.T,rotations)).as_rotvec()
        fit=np.linalg.lstsq(design,relative,rcond=None)[0]
        amplitude=np.sqrt(fit[1]**2+fit[2]**2)
        row=dict(name=cams['name'],frequency_hz=cams['frequency_hz'],predictions=predictions,
            rough_body_angular_rate_deg_s_per_F3=(amplitude*2*np.pi*cams['frequency_hz']*180/np.pi/40).tolist(),
            fairing_pose_harmonic_max_residual_degrees=float(np.max(abs(design@fit-relative))*180/np.pi),
            observed_departure_px=observed.tolist(),phase_degrees=np.rad2deg(angles).tolist())
        output.append(row)
        print(cams['name'],json.dumps({k:row[k] for k in ('rough_body_angular_rate_deg_s_per_F3','fairing_pose_harmonic_max_residual_degrees')}),flush=True)
        for row in predictions:print({k:row[k] for k in ('moving_camera','predicted_amplitude_px','observed_amplitude_px','best_phase_degrees','best_phase_rms_px')},flush=True)
    return dict(comparisons=output,projective=args.projective,qualifications=[
        'Camera fitted to fairing and propeller disk; disk occlusion and neglected small fore-boom motion remain limitations.' if args.projective else 'Orthographic camera inferred only from the fairing; independent perspective calibration remains open.',
        'Only movie starting phase is aligned; no physical parameter or amplitude multiplier is fitted.',
        'Cyan raster centerline has approximately half-pixel measurement residuals.',
        'Projected curvature comparison is diagnostic, not a native Bode validation.'])


def perspective(folder,args):
    import numpy as np
    from PIL import Image
    from scipy.spatial import ConvexHull
    from scipy.spatial.transform import Rotation
    from scipy.optimize import least_squares
    from scipy.ndimage import label,binary_dilation
    data=read(STUDY/'fairing-pieces/result.json');xz=np.array(data['literal_outline_xz'])
    fairing=np.c_[xz[:,0],np.zeros(len(xz)),xz[:,1]]
    angle=np.linspace(0,2*np.pi,181,endpoint=False)
    disk=np.c_[np.full(len(angle),-6.5),5.5*np.cos(angle),5.5*np.sin(angle)]
    theta=np.linspace(0,2*np.pi,180,endpoint=False);normals=np.c_[np.cos(theta),np.sin(theta)]
    rows=[]
    for movie in data['cameras']:
        gif=Image.open(MOVIES/(movie['name']+'.gif'))
        for cam in movie['frames']:
            if not args.start<=cam['frame']<args.start+args.count:continue
            gif.seek(cam['frame']);rgb=np.asarray(gif.convert('RGB')).astype(int)
            # The very thin disk outline is heavily antialiased (pink), while
            # its central glyph is saturated magenta. Retain both hues.
            mask=(rgb[:,:,0]>180)&(rgb[:,:,2]>180)&((rgb[:,:,0]-rgb[:,:,1])>20)&((rgb[:,:,2]-rgb[:,:,1])>20);mask[:200]=False
            labels,count=label(binary_dilation(mask,iterations=1));sizes=np.bincount(labels[mask],minlength=count+1);sizes[0]=0
            mask &= sizes[labels]>=5
            yy,xx=np.nonzero(mask);pixels=np.c_[xx,yy];hull=pixels[ConvexHull(pixels).vertices]
            targets=[np.max(normals@np.array(cam['observed_hull']).T,axis=1),np.max(normals@hull.T,axis=1)]
            initial=np.r_[Rotation.from_matrix(cam['orientation']).as_rotvec(),cam['scale_px_per_ft'],cam['offset'],0.,.3,.3]
            for projective in (False,True):
                def residual(p,detail=False):
                    rotation=Rotation.from_rotvec(p[:3]).as_matrix();scale=p[3];offset=p[4:6]
                    invdistance=p[6] if projective else 0.
                    output=[];images=[]
                    for j,shape in enumerate((fairing,disk)):
                        rotated=shape@rotation.T
                        image=scale*rotated[:,:2]/(1+invdistance*rotated[:,2,None])+offset
                        images.append(image)
                        output.append(np.max(normals@image.T,axis=1)+p[7+j]-targets[j])
                    return images if detail else np.concatenate(output)
                # 1/R is signed because screen y points downward. Orthographic
                # is the explicit R=infinity nested model.
                active=np.arange(9) if projective else np.array([0,1,2,3,4,5,7,8])
                def full(p):
                    value=initial.copy();value[active]=p;return value
                low=np.r_[[-4]*3,5.,250.,300.,-.02,0.,0.]
                high=np.r_[[4]*3,20.,550.,550.,.02,1.5,1.5]
                fit=least_squares(lambda p:residual(full(p)),initial[active],bounds=(low[active],high[active]),
                    max_nfev=150,ftol=1e-10,xtol=1e-10,gtol=1e-9)
                parameters=full(fit.x);images=residual(parameters,True)
                row=dict(name=movie['name'],frame=cam['frame'],perspective=projective,success=fit.success,
                    parameters=parameters.tolist(),rotation=Rotation.from_rotvec(parameters[:3]).as_matrix().tolist(),
                    support_rms_px=float(np.sqrt(np.mean(fit.fun**2))),support_max_px=float(max(abs(fit.fun))),
                    fairing_rms_px=float(np.sqrt(np.mean(fit.fun[:180]**2))),disk_rms_px=float(np.sqrt(np.mean(fit.fun[180:]**2))),
                    observed_fairing=cam['observed_hull'],observed_disk=hull.tolist(),
                    projected_fairing=images[0].tolist(),projected_disk=images[1].tolist())
                rows.append(row);print({k:row[k] for k in ('name','frame','perspective','success','support_rms_px','support_max_px')},'invdistance',parameters[6],flush=True)
    return dict(fits=rows,qualification='Joint camera fit to literal stiff fairing and 5.5 ft propeller disk. No Bode target. Jig disk neglects small fore-boom trim/motion; inspect residuals before using the camera.')


def fin(folder,args):
    import numpy as np
    from PIL import Image
    from scipy.spatial import ConvexHull
    from scipy.spatial.transform import Rotation
    from scipy.ndimage import label,binary_dilation
    from openswing.asw import parse_asw
    from openswing.geometry import surface_frame
    model=parse_asw((ROOT/'examples/dae.asw').read_text(),beam_interpolation='drela-segspl-v1')
    beam=next(b for b in model.beams if b.index==3)
    seed=read(STUDY/'full-states/equilibrium.json');states=read(STUDY/'full-states/result.json')['samples']
    joint=[]
    for start in (0,20,40,60,80):joint+=read(STUDY/f'camera-joint-{start}/result.json')['fits']
    rows=[]
    for name,state in zip(('slow-rudder','fast-rudder'),states):
        b=state['beams']['3'];ids=np.array(b['indices']);t=np.array(b['stations'])
        r=np.array(seed['positions'])[ids];q=Rotation.from_rotvec(np.array(seed['rotations'])[ids]).as_matrix()
        chord_direction=np.einsum('nij,nj->ni',q,surface_frame(beam,t)[:,:,0])
        chord=beam.value('chord',t);axis=beam.value('Xax',t)
        translation=np.array(b['translation_real'])+1j*np.array(b['translation_imag'])
        rotation=np.array(b['rotation_real'])+1j*np.array(b['rotation_imag'])
        shapes=[];increments=[]
        for fraction in (0.,1.):
            arm=(chord*(fraction-axis))[:,None]*chord_direction
            shapes.append(r+arm);increments.append(translation+np.cross(rotation,arm))
        base=np.concatenate(shapes);delta=np.concatenate(increments)
        gif=Image.open(MOVIES/(name+'.gif'));samples=[]
        cams=sorted([v for v in joint if v['name']==name and v['perspective']],key=lambda v:v['frame'])
        for cam in cams:
            frame=cam['frame'];gif.seek(frame);rgb=np.asarray(gif.convert('RGB')).astype(int)
            mask=(rgb[:,:,1]>150)&((rgb[:,:,1]-rgb[:,:,0])>40)&((rgb[:,:,1]-rgb[:,:,2])>40);mask[:200]=False
            labels,count=label(binary_dilation(mask,iterations=1));sizes=np.bincount(labels[mask],minlength=count+1);sizes[0]=0
            original=int(mask.sum());mask &= labels==int(np.argmax(sizes))
            yy,xx=np.nonzero(mask);points=np.c_[xx,yy];observed=points[ConvexHull(points).vertices]
            p=np.array(cam['parameters']);transform=np.array(cam['rotation'])
            def project(shape):
                v=shape@transform.T;return p[3]*v[:,:2]/(1+p[6]*v[:,2,None])+p[4:6]
            phase=2*np.pi*frame/90
            predicted=project(base+40*np.real(delta*np.exp(1j*phase)))
            fixed=project(base)
            def metrics(v):
                lo=v.min(axis=0);hi=v.max(axis=0);return np.r_[(lo+hi)/2,hi-lo]
            samples.append(dict(frame=frame,phase_degrees=360*frame/90,green_pixels=len(points),rejected_pixels=original-len(points),
                observed_hull=observed.tolist(),predicted_outline=predicted.tolist(),fixed_outline=fixed.tolist(),
                observed_center_width_height=metrics(observed).tolist(),
                predicted_center_width_height=metrics(predicted).tolist(),fixed_center_width_height=metrics(fixed).tolist()))
        angles=np.deg2rad([s['phase_degrees'] for s in samples]);design=np.c_[np.ones(len(angles)),np.cos(angles),np.sin(angles)]
        summary={}
        for key in ('observed','predicted','fixed'):
            values=np.array([s[key+'_center_width_height'] for s in samples]);fit=np.linalg.lstsq(design,values,rcond=None)[0]
            summary[key]=dict(mean_cos_sin=fit.tolist(),amplitude_px=np.sqrt(fit[1]**2+fit[2]**2).tolist(),
                max_harmonic_residual_px=np.max(abs(design@fit-values),axis=0).tolist())
        rows.append(dict(name=name,frequency_hz=state['frequency_hz'],samples=samples,metrics=summary))
        print(name,json.dumps(summary),flush=True)
    return dict(comparisons=rows,qualifications=[
        'Current finite-mesh fin outline with spatial incremental rotation; camera independently fitted to native fairing/disk.',
        'No amplitude/phase/physical parameter fit. F3 display amplitude 40; phase follows annotated movie time.',
        'Bounding-box metrics are image-space diagnostics and sensitive to occlusion, camera and mean shape.',
        'Fixed outline includes measured native camera/body pose changes but excludes local fin elastic response.'])


def wing(folder,args):
    import numpy as np
    from PIL import Image
    from scipy.spatial.transform import Rotation
    from openswing.asw import parse_asw
    from openswing.geometry import surface_frame
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    model=parse_asw((ROOT/'examples/dae.asw').read_text(),beam_interpolation='drela-segspl-v1')
    beam=next(b for b in model.beams if b.index==1)
    seed=read(STUDY/'full-states/equilibrium.json');states=read(STUDY/'full-states/result.json')['samples']
    joint=[]
    for start in (0,20,40,60,80):joint+=read(STUDY/f'camera-joint-{start}/result.json')['fits']
    rows=[];fig,axes=plt.subplots(3,2,figsize=(12,10),layout='constrained')
    for col,(name,state) in enumerate(zip(('slow-rudder','fast-rudder'),states)):
        b=state['beams']['1'];ids=np.array(b['indices']);t=np.array(b['stations'])
        r=np.array(seed['positions'])[ids];q=Rotation.from_rotvec(np.array(seed['rotations'])[ids]).as_matrix()
        chord_direction=np.einsum('nij,nj->ni',q,surface_frame(beam,t)[:,:,0])
        chord=beam.value('chord',t);axis=beam.value('Xax',t)
        translation=np.array(b['translation_real'])+1j*np.array(b['translation_imag'])
        rotation=np.array(b['rotation_real'])+1j*np.array(b['rotation_imag'])
        shapes=[];increments=[]
        for fraction in (0.,1.):
            arm=(chord*(fraction-axis))[:,None]*chord_direction
            shapes.append(r+arm);increments.append(translation+np.cross(rotation,arm))
        base=np.stack(shapes);delta=np.stack(increments)
        gif=Image.open(MOVIES/(name+'.gif'));samples=[]
        cams=sorted([v for v in joint if v['name']==name and v['perspective']],key=lambda v:v['frame'])
        for cam in cams:
            frame=cam['frame'];gif.seek(frame);rgb=np.asarray(gif.convert('RGB')).astype(int)
            mask=(rgb[:,:,0]>150)&((rgb[:,:,0]-rgb[:,:,1])>40)&((rgb[:,:,0]-rgb[:,:,2])>40);mask[:200]=False
            yy,xx=np.nonzero(mask);xmin=xx.min();tip=np.array([xmin,np.mean(yy[xx<=xmin+2])])
            assert xmin>2,('tip clipped',name,frame)
            p=np.array(cam['parameters']);transform=np.array(cam['rotation'])
            def project(shape):
                v=shape@transform.T;return p[3]*v[...,:2]/(1+p[6]*v[...,2,None])+p[4:6]
            phase=2*np.pi*frame/90
            predicted=project(base+40*np.real(delta*np.exp(1j*phase)));fixed=project(base)
            def left_tip(outline):
                # Both chord endpoints at the physical left tip, rather than
                # assuming the entire-wing minimum belongs to a particular edge.
                end=0 if outline[:,0,0].mean()<outline[:,-1,0].mean() else -1
                pair=outline[:,end];return pair[np.argmin(pair[:,0])]
            samples.append(dict(frame=frame,phase_degrees=360*frame/90,red_pixels=len(xx),
                observed_tip_px=tip.tolist(),predicted_tip_px=left_tip(predicted).tolist(),
                fixed_tip_px=left_tip(fixed).tolist(),predicted_outline=predicted.tolist(),fixed_outline=fixed.tolist()))
            if frame==0:
                ax=axes[0,col];ax.imshow(rgb.astype('uint8'))
                for edge in predicted:ax.plot(*edge.T,color='#7b2cbf',lw=1,label='OpenSwing' if edge is predicted[0] else None)
                ax.plot(*tip,'o',ms=4,color='black');ax.set_xlim(0,673);ax.set_ylim(560,230)
                ax.set_title(f'{state["frequency_hz"]:g} Hz — current wing projected into native frame')
        angles=np.deg2rad([s['phase_degrees'] for s in samples]);design=np.c_[np.ones(len(angles)),np.cos(angles),np.sin(angles)]
        summary={}
        for key,color in (('observed','black'),('predicted','#7b2cbf'),('fixed','#e69f00')):
            values=np.array([s[key+'_tip_px'] for s in samples]);fit=np.linalg.lstsq(design,values,rcond=None)[0]
            summary[key]=dict(mean_cos_sin=fit.tolist(),amplitude_px=np.sqrt(fit[1]**2+fit[2]**2).tolist(),
                max_harmonic_residual_px=np.max(abs(design@fit-values),axis=0).tolist())
            for j in range(2):
                ax=axes[1+j,col];ax.plot(np.rad2deg(angles),values[:,j]-fit[0,j],'.-',color=color,label=key)
                ax.set_ylabel(('Horizontal' if j==0 else 'Vertical')+' tip motion (px)');ax.set_xlabel('Cycle phase (deg)');ax.grid(alpha=.2);ax.legend()
        rows.append(dict(name=name,frequency_hz=state['frequency_hz'],samples=samples,metrics=summary))
        print(name,json.dumps(summary),flush=True)
    fig.suptitle('Wing-tip image diagnostic — independent fairing/propeller camera; no wing fit\nFixed = current mean wing with native camera/body motion only')
    fig.savefig(folder/'wing-comparison.png',dpi=150);fig.savefig(folder/'wing-comparison.svg');plt.close(fig)
    return dict(comparisons=rows,qualifications=[
        'No physical parameter, amplitude, phase or wing-camera fit. Same accepted 6.7 m/s full harmonic states as the boom comparison.',
        'Native tip is leftmost red pixel x with mean y over its first three pixel columns; prediction is leftmost physical tip chord endpoint.',
        'Camera is inferred from the small central fairing and propeller; extrapolation to the long wing strongly amplifies camera uncertainty.',
        'Chord-normal display used. Deformed chord unsweeping could alter outlines, but not the physical beam-axis motion.',
        'Measured native camera includes native body motion; this compares local elastic shape, not an independent free-frame Bode output.'])


def report(folder,args):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    from scipy.spatial import ConvexHull
    comparisons=read(STUDY/'perspective-curvature/result.json')['comparisons']
    fins=read(STUDY/'fin-outline-connected/result.json')['comparisons']
    joint=[]
    for start in (0,20,40,60,80):joint+=read(STUDY/f'camera-joint-{start}/result.json')['fits']
    fig,axes=plt.subplots(3,2,figsize=(12,11),layout='constrained')
    summary=[]
    for col,(row,finrow) in enumerate(zip(comparisons,fins)):
        name=row['name'];frequency=row['frequency_hz']
        with Image.open(MOVIES/(name+'.gif')) as gif:rgb=np.array(gif.convert('RGB'))
        ax=axes[0,col];ax.imshow(rgb)
        sample=finrow['samples'][0];points=np.array(sample['predicted_outline'])
        n=len(points)//2;outline=np.r_[points[:n],points[n:][::-1],points[:1]]
        ax.plot(*outline.T,color='#7b2cbf',lw=1.4,label='OpenSwing fin, projected')
        cam=next(v for v in joint if v['name']==name and v['frame']==0 and v['perspective'])
        for key in ('projected_fairing','projected_disk'):
            points=np.array(cam[key]);points=points[ConvexHull(points).vertices];points=np.r_[points,points[:1]]
            ax.plot(*points.T,color='#333333',lw=.7,ls='--',label='Camera fit' if key=='projected_fairing' else None)
        ax.set(xlim=(315,660),ylim=(510,345),title=f'{frequency:g} Hz — native GIF at t=0, with overlays',xlabel='Image x [pixels]',ylabel='Image y [pixels]')
        ax.legend(fontsize=8,loc='lower left')
        ax=axes[1,col];phase=np.array(row['phase_degrees'])/360
        observed=np.array(row['observed_departure_px']);pred=row['predictions'][1];predicted=np.array(pred['predicted_departure_px'])
        ax.plot(phase,observed-np.mean(observed),'o',ms=4,color='#006d77',label='Native GIF trace')
        ax.fill_between(phase,observed-np.mean(observed)-.5,observed-np.mean(observed)+.5,color='#006d77',alpha=.12,label='±0.5 px reference band')
        ax.plot(phase,predicted-np.mean(predicted),color='#7b2cbf',label='OpenSwing / measured camera')
        ax.set(title=f'Boom bending: {pred["observed_amplitude_px"]:.3f} px observed, {pred["predicted_amplitude_px"]:.3f} px predicted',
            xlabel='Cycles',ylabel='Departure from forward tangent [pixels]')
        ax.grid(alpha=.25);ax.legend(fontsize=8)
        ax=axes[2,col]
        for key,label,color,style in [('observed','Native fin','#006d77','o'),('predicted','OpenSwing fin','#7b2cbf','-'),('fixed','Local fin motion suppressed','#777777','--')]:
            values=np.array([s[key+'_center_width_height'][1] for s in finrow['samples']]);values-=np.mean(values)
            ax.plot(phase,values,style,color=color,ms=4,label=label)
        ax.set(title='Fin vertical motion — calibration remains uncertain',xlabel='Cycles',ylabel='Bounding-box center y, mean removed [pixels]')
        ax.grid(alpha=.25);ax.legend(fontsize=8)
        fits=[v for v in joint if v['name']==name and v['perspective']]
        summary.append(dict(name=name,frequency_hz=frequency,
            camera_support_rms_range_px=[min(v['support_rms_px'] for v in fits),max(v['support_rms_px'] for v in fits)],
            camera_largest_support_error_px=max(v['support_max_px'] for v in fits),
            inferred_inverse_distance_range_ft=[min(v['parameters'][6] for v in fits),max(v['parameters'][6] for v in fits)],
            boom_observed_amplitude_px=pred['observed_amplitude_px'],boom_predicted_amplitude_px=pred['predicted_amplitude_px'],
            boom_aligned_rms_px=pred['best_phase_rms_px'],phase_alignment_degrees=pred['best_phase_degrees'],
            fin_metrics=finrow['metrics']))
    fig.suptitle('Daedalus animation diagnostics — no physical parameters fitted\nLocal motion comparison supports boom bending; native Bode agreement remains open',fontsize=13)
    fig.savefig(folder/'animation-comparison.png',dpi=150);fig.savefig(folder/'animation-comparison.svg');plt.close(fig)
    terminals=[]
    for path in sorted(STUDY.glob('*/terminal.json')):
        terminal=read(path);assert terminal['process_reaped']
        terminals.append(dict(path=str(path.relative_to(ROOT)),**terminal))
    checks=read(STUDY/'full-states/result.json')['samples']
    return dict(observed_utc=utc(),summary=summary,
        harmonic_checks=[r['checks'] for r in checks],
        process_receipts=terminals,all_reaped=True,
        qualification='Raster comparison only. No new Bode/ISAE pass, no production change, no recovered native operating point. ±0.5 pixels is a descriptive reference band, not a statistical confidence interval.')


def mean_shape(folder,args):
    import numpy as np
    from scipy.spatial.transform import Rotation
    cameras=read(STUDY/'fairing-pieces/result.json')['cameras']
    traces=read(STUDY/'boom-curvature/result.json')['traces'];joint=[]
    for start in (0,20,40,60,80):joint+=read(STUDY/f'camera-joint-{start}/result.json')['fits']
    cases=[('endpoint 6.7',SOURCE/'trim-6.7-1/state.json')]
    cases += [(f'midpoint {v}',ROOT/f'artifacts/daedalus-speed-20261113/certify-{v}/state.json') for v in ('6','6.7','7.5','8.25','9.144')]
    rows=[]
    for label,path in cases:
        seed=read(path);t,ids=seed['identity']['stations']['4'];r=np.array(seed['positions'])[np.array(ids)]
        station=np.linspace(t[0],t[-1],1001);r=np.array([np.interp(station,t,r[:,j]) for j in range(3)]).T
        entry=dict(label=label,source=str(path.relative_to(ROOT)),body_boom_end_z_ft=float(r[-1,2]),cameras=[])
        for cams,trace in zip(cameras,traces):
            jc=sorted([v for v in joint if v['name']==cams['name'] and v['perspective']],key=lambda v:v['frame'])
            predictions=[]
            for cam,fit in zip(cams['frames'],jc):
                p=np.array(fit['parameters']);v=r@np.array(fit['rotation']).T
                projected=p[3]*v[:,:2]/(1+p[6]*v[:,2,None])+p[4:6]
                mount=(np.array(cam['affine_xz'])@np.array([2.5,0.])+cam['offset'])[0]
                xi=(projected[:,0]-mount)/cam['affine_xz'][0][0]
                fore=(xi>=-7)&(xi<=0);aft=(xi>=13)&(xi<=15.5)
                line=np.polyfit(xi[fore],projected[fore,1],1)
                predictions.append(float(np.mean(projected[aft,1]-np.polyval(line,xi[aft]))))
            entry['cameras'].append(dict(name=cams['name'],predicted_mean_px=float(np.mean(predictions)),
                observed_harmonic_mean_px=trace['mean_cos_sin_departure_px'][0]))
        rows.append(entry);print(entry,flush=True)
    return dict(cases=rows,qualifications=[
        'Saved accepted equilibria only; no new trim or change to any speed-case response.',
        'Five speed cases use the disclosed earlier midpoint/natural policy; the endpoint 6.7 case is shown separately.',
        'Image mean-shape agreement alone cannot determine operating speed or override Bode disagreement.'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['camera','states','curvature','compare','perspective','fin','wing','report','mean_shape'])
    parser.add_argument('--tag',required=True)
    parser.add_argument('--start',type=int,default=0)
    parser.add_argument('--count',type=int,default=91)
    parser.add_argument('--projective',action='store_true')
    args=parser.parse_args()
    STUDY.mkdir(exist_ok=True);folder=STUDY/args.tag;folder.mkdir(exist_ok=False)
    (folder/'runner.py').write_bytes(Path(__file__).read_bytes())
    inputs=[Path(__file__),ROOT/'examples/dae.asw',MOVIES/'slow-rudder.gif',MOVIES/'fast-rudder.gif',MOVIES/'source-receipt.json']
    if args.stage=='states':
        inputs += [SOURCE/'assembled-6.7'/name for name in ('A.npz','M.npz','maps.npz','plan.json','result.json','terminal.json')]
        inputs += [SOURCE/'mass-6.7/layout.json',SOURCE/'trim-6.7-1/state.json']
    if args.stage=='curvature':inputs += [STUDY/'fairing-pieces/result.json']
    if args.stage=='perspective':inputs += [STUDY/'fairing-pieces/result.json']
    if args.stage=='compare':
        inputs += [STUDY/p for p in ('fairing-pieces/result.json','boom-curvature/result.json',
            'full-states/equilibrium.json','full-states/result.json')]
        if args.projective:inputs += [STUDY/f'camera-joint-{start}/result.json' for start in (0,20,40,60,80)]
    if args.stage in ('fin','wing'):
        inputs += [STUDY/f'camera-joint-{start}/result.json' for start in (0,20,40,60,80)]
        inputs += [STUDY/'full-states/equilibrium.json',STUDY/'full-states/result.json']
    if args.stage=='report':
        inputs += [p for p in STUDY.glob('*/result.json')]
    if args.stage=='mean_shape':
        inputs += [STUDY/f'camera-joint-{start}/result.json' for start in (0,20,40,60,80)]
        inputs += [STUDY/'fairing-pieces/result.json',STUDY/'boom-curvature/result.json',SOURCE/'trim-6.7-1/state.json']
        inputs += [ROOT/f'artifacts/daedalus-speed-20261113/certify-{v}/state.json' for v in ('6','6.7','7.5','8.25','9.144')]
    pins={str(p.resolve()):pin(p) for p in inputs+list((ROOT/'openswing').glob('*.py'))}
    write(folder/'plan.json',dict(observed_utc=utc(),arguments=vars(args),inputs_sha256=pins,limits=LIMITS))
    sys.stdout.flush();started=time.monotonic();pid=os.fork()
    if pid==0:
        code=0
        for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
        resource.setrlimit(resource.RLIMIT_AS,(LIMITS['address_space_bytes'],)*2)
        resource.setrlimit(resource.RLIMIT_CPU,(LIMITS['cpu_seconds'],)*2)
        sys.path.insert(0,str(ROOT))
        with (folder/'stdout.log').open('x') as out,(folder/'stderr.log').open('x') as err:
            os.dup2(out.fileno(),1);os.dup2(err.fileno(),2)
            try:write(folder/'result.json',globals()[args.stage](folder,args))
            except BaseException:traceback.print_exc();code=1
            sys.stdout.flush();sys.stderr.flush()
        os._exit(code)
    reaped=0;timed_out=False
    try:
        while not reaped:
            reaped,status,usage=os.wait4(pid,os.WNOHANG)
            if reaped:break
            if time.monotonic()-started>LIMITS['wall_seconds']:
                timed_out=True;os.kill(pid,signal.SIGKILL);reaped,status,usage=os.wait4(pid,0);break
            time.sleep(.05)
    finally:
        if not reaped:os.kill(pid,signal.SIGKILL);reaped,status,usage=os.wait4(pid,0)
    receipt=dict(observed_utc=utc(),returncode=os.waitstatus_to_exitcode(status),process_reaped=True,
        timed_out=timed_out,cpu_seconds=usage.ru_utime+usage.ru_stime,wall_seconds=time.monotonic()-started,
        peak_rss_kib=usage.ru_maxrss,limits=LIMITS,inputs_unchanged=all(pin(p)==h for p,h in pins.items()))
    write(folder/'terminal.json',receipt);print(json.dumps(receipt),flush=True)
    raise SystemExit(receipt['returncode'] or (0 if receipt['inputs_unchanged'] else 1))


if __name__=='__main__':main()
