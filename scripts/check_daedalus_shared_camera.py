"""One-camera, harmonic rigid-motion fit to the native 1 Hz movie outlines.

Image identifiability diagnostic only. No Bode curve, elastic state or physical
parameter is fitted. Optional fixed yaw amplitudes are ambiguity profiles.
"""
import argparse
from pathlib import Path
from check_daedalus_load_sensitivity import ROOT, read
from daedalus_bounded_job import run

CAMERA=ROOT/'artifacts/daedalus-animation-calibration-20261113'
STUDY=ROOT/'artifacts/daedalus-shared-camera-20261114'


def fit_camera(folder,args):
    import numpy as np
    from scipy.optimize import least_squares
    from scipy.spatial.transform import Rotation
    cameras=sum([read(CAMERA/f'camera-joint-{i}/result.json')['fits'] for i in (0,20,40,60,80)],[])
    cams=sorted([c for c in cameras if c['name']=='fast-rudder' and c['perspective'] and c['frame']<90],key=lambda c:c['frame'])
    assert len(cams)==18 and all(c['success'] for c in cams)
    phase=np.array([c['frame'] for c in cams])*2*np.pi/90
    harmonic=np.c_[np.cos(phase),np.sin(phase)]
    xz=np.array(read(CAMERA/'fairing-pieces/result.json')['literal_outline_xz'])
    fairing=np.c_[xz[:,0],np.zeros(len(xz)),xz[:,1]]
    angle=np.linspace(0,2*np.pi,181,endpoint=False)
    disk=np.c_[np.full(len(angle),-6.5),5.5*np.cos(angle),5.5*np.sin(angle)]
    angles=np.linspace(0,2*np.pi,180,endpoint=False);normals=np.c_[np.cos(angles),np.sin(angles)]
    target=np.stack([np.stack([np.max(normals@np.array(c[key]).T,axis=1) for key in ('observed_fairing','observed_disk')]) for c in cams])
    pivot=np.array([2.5,0.,-5.6])
    old=np.array([c['parameters'] for c in cams]);initial=np.zeros(21);initial[:9]=old.mean(axis=0)
    mean_rotation=Rotation.from_rotvec(old[:,:3]).mean();initial[:3]=mean_rotation.as_rotvec();C=mean_rotation.as_matrix()
    relative=Rotation.from_matrix(np.einsum('ij,njk->nik',C.T,Rotation.from_rotvec(old[:,:3]).as_matrix())).as_rotvec()
    initial[9:15]=np.linalg.lstsq(harmonic,relative,rcond=None)[0].ravel()
    image_motion=np.linalg.lstsq(harmonic,old[:,4:6]-initial[4:6],rcond=None)[0]/initial[3]
    initial[15:]=(np.c_[image_motion,np.zeros(2)]@C+np.cross(initial[9:15].reshape(2,3),pivot)).ravel()
    if args['seed']:initial=np.array(read(Path(args['seed'])/'result.json')['parameters'])
    low=np.r_[[-4.]*3,5.,250.,300.,-.02,0.,0.,[-.05]*6,[-1.]*6]
    high=np.r_[[4.]*3,20.,550.,550.,.02,1.5,1.5,[.05]*6,[1.]*6]
    scale=np.r_[[1.]*3,10.,100.,100.,.01,1.,1.,[.01]*6,[.2]*6]

    def predict(p):
        rotation=harmonic@p[9:15].reshape(2,3)
        translation=harmonic@p[15:21].reshape(2,3)
        camera=Rotation.from_rotvec(p[:3]).as_matrix()
        values=[]
        for j,shape in enumerate((fairing,disk)):
            # Linear harmonic geometry, as in the displayed Bode perturbation.
            moved=shape[None]+np.cross(rotation[:,None,:],shape[None]-pivot)+translation[:,None,:]
            view=moved@camera.T
            image=p[3]*view[:,:,:2]/(1+p[6]*view[:,:,2,None])+p[4:6]
            support=np.max(np.einsum('ij,nkj->nik',normals,image),axis=2)+p[7+j]
            values.append(support)
        return np.stack(values,axis=1)

    truth=None
    if args.get('synthetic_from'):
        truth=np.array(read(Path(args['synthetic_from'])/'result.json')['parameters'])
        target=predict(truth)
    amplitude=args['yaw_rate']
    fixed={axis:value for axis,value in [(0,args.get('roll_rate')),(2,amplitude)] if value is not None}
    active=np.array([i for i in range(21) if all(i not in (9+axis,12+axis) for axis in fixed)])
    if not fixed:
        expand=lambda x:x
        x0=initial;bounds=(low,high);scales=scale
    else:
        def expand(x):
            p=initial.copy();p[active]=x[:len(active)]
            for j,(axis,value) in enumerate(fixed.items()):
                theta=value*np.pi/180*40/(2*np.pi);angle=x[len(active)+j]
                p[9+axis]=theta*np.cos(angle);p[12+axis]=theta*np.sin(angle)
            return p
        x0=np.r_[initial[active],[np.arctan2(initial[12+axis],initial[9+axis]) for axis in fixed]]
        bounds=(np.r_[low[active],[-10.]*len(fixed)],np.r_[high[active],[10.]*len(fixed)]);scales=np.r_[scale[active],[1.]*len(fixed)]
    x0=np.maximum(bounds[0]+1e-10,np.minimum(bounds[1]-1e-10,x0))
    initial_residual=predict(expand(x0))-target
    result=least_squares(lambda x:(predict(expand(x))-target).ravel(),x0,bounds=bounds,x_scale=scales,
        max_nfev=args['evaluations'],ftol=1e-8,xtol=1e-8,gtol=1e-7)
    p=expand(result.x);predicted=predict(p);residual=predicted-target
    rates=np.hypot(p[9:12],p[12:15])*2*np.pi*180/np.pi/40
    singular=np.linalg.svd(result.jac*scales,compute_uv=False)
    np.savez_compressed(folder/'arrays.npz',target=target,predicted=predicted,residual=residual,phase=phase,
        normalized_jacobian_singular_values=singular)
    return dict(frames=[c['frame'] for c in cams],frequency_hz=1.,native_display_amplitude_F3=40,
        parameters=p.tolist(),parameter_order='camera rotvec 3, scale, offset 2, inverse distance, padding 2; body rotation cos/sin 2x3; pivot translation cos/sin 2x3',
        optimizer_success=bool(result.success),optimizer_message=result.message,evaluations=int(result.nfev),
        active_bounds=result.active_mask.tolist(),fixed_yaw_rate_deg_s_per_F3=amplitude,
        fixed_roll_rate_deg_s_per_F3=args.get('roll_rate'),
        inferred_linear_rate_amplitudes_deg_s_per_F3=rates.tolist(),
        synthetic_source=args.get('synthetic_from'),
        synthetic_expected_rate_amplitudes_deg_s_per_F3=None if truth is None else (np.hypot(truth[9:12],truth[12:15])*2*np.pi*180/np.pi/40).tolist(),
        initial_support_rms_px=float(np.sqrt(np.mean(initial_residual**2))),
        support_rms_px=float(np.sqrt(np.mean(residual**2))),support_max_px=float(np.max(abs(residual))),
        support_rms_by_object_px=np.sqrt(np.mean(residual**2,axis=(0,2))).tolist(),
        frame_support_rms_px=np.sqrt(np.mean(residual**2,axis=(1,2))).tolist(),
        max_frame_rotation_radians=float(np.linalg.norm(harmonic@p[9:15].reshape(2,3),axis=1).max()),
        normalized_jacobian_singular_values=singular.tolist(),
        qualification='One constant camera, optics and raster padding over 18 unique phases. Literal rigid fairing and propeller-disk geometry; small fore-boom elastic motion and raster correlations remain unmodeled. Image fit, not native validation or a statistical confidence interval. No aerodynamic/structural solve or parameter change.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag',required=True);parser.add_argument('--seed');parser.add_argument('--yaw-rate',type=float)
    parser.add_argument('--synthetic-from')
    parser.add_argument('--roll-rate',type=float)
    parser.add_argument('--evaluations',type=int,default=12)
    args=vars(parser.parse_args());inputs=[CAMERA/'fairing-pieces/result.json']
    inputs.extend(CAMERA/f'camera-joint-{i}/result.json' for i in (0,20,40,60,80))
    inputs += [ROOT/'docs/validation/aswing-authoritative-references.md',ROOT/'docs/validation/aswing-authoritative-sources.json',
        ROOT/'docs/validation/daedalus-animation-sources-20261113.json']
    if args['seed']:inputs.append(Path(args['seed'])/'result.json')
    if args['synthetic_from']:inputs.append(Path(args['synthetic_from'])/'result.json')
    run(STUDY,args['tag'],inputs,fit_camera,args,__file__)
