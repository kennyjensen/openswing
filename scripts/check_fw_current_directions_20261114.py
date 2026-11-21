"""Full-residual modal checks on a verified current-mesh FW checkpoint."""
import argparse
import json
from pathlib import Path
from check_fw_current_mesh_20261114 import ROOT,STUDY,checked_system
from daedalus_bounded_job import run


def directions(folder,args):
    import numpy as np
    pencil=Path(args['pencil'])
    meta=json.loads((pencil.parent/'result.json').read_text())
    assert meta['mesh_recipe']=='accurate-arc-v2'
    current,base,_=checked_system(dict(speed=meta['speed_ft_s'],panels=meta['requested_panels'],
                                     seed=str(pencil.parent/'state.json')))
    with np.load(pencil) as data:a,m=data['a'],data['m']
    with np.load(Path(args['modes'])/'modes.npz') as data:
        vectors,values=data['right'],data['eigenvalues']
    assert current.size==len(a)==meta['dimension']
    rows=[];arrays={}
    for index,(v,lam) in enumerate(zip(vectors,values)):
        v=v/max(abs(v))
        for part in ('real','imag'):
            z,zd=getattr(v,part),getattr(lam*v,part)
            if max(np.max(abs(z)),np.max(abs(zd)))<1e-12:continue
            expected=a@z-m@zd
            scale=max(np.max(abs(a@z))+np.max(abs(m@zd)),1e-14)
            for h in (2e-4,4e-4):
                r=[current.residual(f*h*z,f*h*zd) for f in (1,-1,2,-2)]
                direct=(8*(r[0]-r[1])-(r[2]-r[3]))/(12*h)
                error=float(np.max(abs(direct))/scale)
                rows.append(dict(index=index,eigenvalue=[lam.real,lam.imag],part=part,width=h,
                    scaled_full_mode_residual=error,
                    scaled_matrix_difference=float(np.max(abs(direct-expected))/scale),
                    accepted=error<1e-7))
                arrays[f'{index}-{part}-{h}']=direct
    np.savez_compressed(folder/'directional-residuals.npz',**arrays)
    return dict(scope='Two-width fourth-order full nonlinear residual checks on the current default mesh.',
        speed_ft_s=meta['speed_ft_s'],mesh_recipe=meta['mesh_recipe'],base_residual=base['residual'],
        acceptance_threshold=1e-7,accepted=sum(r['accepted'] for r in rows),total=len(rows),
        maximum_scaled_residual=max(r['scaled_full_mode_residual'] for r in rows),checks=rows)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--tag',required=True)
    parser.add_argument('--pencil',required=True)
    parser.add_argument('--modes',required=True)
    args=vars(parser.parse_args())
    matrix=Path(args['pencil']).parent;mode=Path(args['modes'])
    inputs=[ROOT/'scripts/check_fw_current_mesh_20261114.py',ROOT/'scripts/check_fw_published_20261114.py',
        ROOT/'examples/fw.asw',ROOT/'docs/validation/fw-reference.json',
        *[matrix/name for name in ('pencil.npz','state.json','result.json','terminal.json')],
        *[mode/name for name in ('modes.npz','result.json','terminal.json')],
        *sorted((ROOT/'openswing').glob('*.py'))]
    run(STUDY,args['tag'],inputs,directions,args,__file__)
