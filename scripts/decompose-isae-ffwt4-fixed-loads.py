"""Locate fixed-shape aerodynamic mesh changes in retained literal-case data."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.geometry import surface_frame
from openswing.network import exp

def read(p):return json.loads(Path(p).read_text())
def pin(p):
    p=Path(p).resolve();b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--study',type=Path,required=True)
    p.add_argument('--plan-name',default='plan.json')
    p.add_argument('--output-name',default='fixed-load-decomposition.json');a=p.parse_args()
    plan=read(a.study/a.plan_name)
    for record in plan['inputs']:assert pin(record['path'])==record
    old=read(plan['fixed_pose_plan']['path']);request=read(old['request']['path'])
    model=parse_asw(request['source'],beam_interpolation=request['numerics']['beam_interpolation'])
    condition=FlightCondition(**request['condition']);free=condition.speed*condition.vectors()[0]
    rho=condition.density;assert rho==1.2256
    rotations={b.index:np.eye(3) for b in model.beams}
    for h in old['hinges']:rotations[h['other_beam']]=exp(np.array(h['axis_jig'])*np.deg2rad(h['angle_deg']))
    saved={};worst_force=worst_moment=0.
    for nodes in (55,107,211,419):
        aero=read(plan['aero_results'][str(nodes)]['path']);rows=[]
        for beam in model.beams:
            strips=[v for v in aero['strips'] if v['beam']==beam.index];t=np.array([v['t'] for v in strips])
            jig=surface_frame(beam,t);frames=rotations[beam.index]@jig
            c,s=frames[:,:,0],frames[:,:,1]
            chord=beam.value('chord',t);xax=beam.value('Xax',t)
            assert np.all(beam.value('Cm',t)==0)
            # The 107-node recipe bisects every 55-node interval exactly.
            ends=old['meshes'][str(nodes if nodes>55 else 107)]['beams'][str(beam.index)]['nodes']
            if nodes==55:ends=ends[::2]
            assert len(ends)==len(strips)+1
            lengths=np.linalg.norm(beam.position(np.array(ends[1:]))-beam.position(np.array(ends[:-1])),axis=1)
            np.testing.assert_allclose(lengths,[v['length'] for v in strips],rtol=0,atol=1e-13)
            for i,v in enumerate(strips):
                gamma=v['circulation'];length=v['length'];velocity=np.array(v['relative_velocity'])
                freestream=rho*gamma*np.cross(free,s[i])*length
                induced=rho*gamma*np.cross(velocity-free,s[i])*length
                total=np.array(v['force']);profile=total-freestream-induced
                quarter=np.array(v['position'])+(.25-xax[i])*chord[i]*c[i]
                moment=np.cross(v['position'],total)+v['moment']
                mf=np.cross(quarter,freestream);mi=np.cross(quarter,induced)
                remainder=moment-mf-mi
                # This literal stationary arm has zero intrinsic pitching
                # moment, apparent/rate force and nominal profile drag.
                worst_force=max(worst_force,float(np.max(abs(profile))))
                worst_moment=max(worst_moment,float(np.max(abs(remainder))))
                rows.append(dict(beam=beam.index,t0=ends[i],t1=ends[i+1],t=v['t'],
                    gamma=gamma,length=length,force=total.tolist(),moment=moment.tolist(),
                    free_force=freestream.tolist(),induced_force=induced.tolist(),other_force=profile.tolist(),
                    free_moment=mf.tolist(),induced_moment=mi.tolist(),other_moment=remainder.tolist(),
                    free_moment_per_gamma=(rho*length*np.cross(quarter,np.cross(free,s[i]))).tolist()))
        saved[nodes]=rows
    assert worst_force<1e-10 and worst_moment<1e-10,(worst_force,worst_moment)
    pairs=[]
    for coarse,fine in ((55,107),(107,211),(211,419)):
        c,f=saved[coarse],saved[fine];cells=[]
        for row in c:
            matches=[v for v in f if v['beam']==row['beam'] and
                v['t']>row['t0']-1e-13 and v['t']<row['t1']+1e-13]
            assert len(matches)==2,(coarse,row['beam'],row['t0'],row['t1'],len(matches))
            cell=dict(beam=row['beam'],t0=row['t0'],t1=row['t1'],t=row['t'])
            for key in ('force','moment','free_force','induced_force','other_force','free_moment','induced_moment','other_moment'):
                cell[key+'_change']=(np.sum([v[key] for v in matches],axis=0)-row[key]).tolist()
            fixed_gamma=np.sum([np.array(v['free_moment_per_gamma'])*row['gamma'] for v in matches],axis=0)
            changed_gamma=np.sum([np.array(v['free_moment_per_gamma'])*(v['gamma']-row['gamma']) for v in matches],axis=0)
            cell['free_moment_circulation_change']=changed_gamma.tolist()
            cell['free_moment_sampling_change']=(fixed_gamma-row['free_moment']).tolist()
            np.testing.assert_allclose(changed_gamma+fixed_gamma-row['free_moment'],cell['free_moment_change'],rtol=0,atol=1e-15)
            cells.append(cell)
        grouped=[]
        for label,choose in [('negative main',lambda v:v['beam']==1 and v['t']<0),
                             ('positive main',lambda v:v['beam']==1 and v['t']>0),
                             ('right tip',lambda v:v['beam']==2),('left tip',lambda v:v['beam']==3)]:
            selected=[v for v in cells if choose(v)]
            grouped.append(dict(region=label,**{key:np.sum([v[key] for v in selected],axis=0).tolist()
                for key in ('force_change','moment_change','free_moment_change','induced_moment_change','other_moment_change',
                            'free_moment_circulation_change','free_moment_sampling_change')}))
        negative=[v for v in cells if v['beam']==3 or (v['beam']==1 and v['t']<0)]
        largest=sorted(negative,key=lambda v:abs(v['moment_change'][0]),reverse=True)[:12]
        pairs.append(dict(coarse=coarse,fine=fine,regions=grouped,cells=cells,
            negative_half_moment_change=np.sum([v['moment_change'] for v in negative],axis=0).tolist(),
            largest_negative_half_Mx_cells=largest))
    result=dict(status='FIXED_SHAPE_LOAD_CHANGES_DECOMPOSED',pairs=pairs,
        maximum_nonlift_force=worst_force,maximum_nonlift_moment=worst_moment,
        native_passes_added=0,structural_equilibrium_claim=False,inputs=plan['inputs'])
    with (a.study/a.output_name).open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    for pair in pairs:print(json.dumps({k:v for k,v in pair.items() if k not in ('cells','largest_negative_half_Mx_cells')}),flush=True)
if __name__=='__main__':main()
