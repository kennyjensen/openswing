"""Explicit primary-property Pazy gravity/static configurations and observables."""
import json
import re
import numpy as np
from pazy_primary_conm2 import ROOT, CACHE, model, mesh, source, sha

GRAVITY=9.807  # Explicit GRAV card in the primary SOL400 input.
MIDCHORD_OFFSET=(.5-.441)*.1
STATIC='03_2023_JA_Riso_Cesnik/03_Static_Structural'


def payload(skin,kind):
    assert kind in ['bending','torsion']
    x=MIDCHORD_OFFSET if kind=='bending' else (1-.441)*.1+(.04 if skin==0 else .08)
    return np.array([x,0.,0.])


def configuration(spec):
    text,data=model(spec['skin'],spec['orientation'])
    if spec['analysis']=='static':
        assert spec['orientation']=='horizontal'
        offset=payload(spec['skin'],spec['kind']);point=data['coordinates'][-1]+offset
        mass=spec['mass_kg'];assert mass>=0
        # Additional bench mass only. Preserve all 16 original masses and
        # their tensors, including whatever calibration/instrument mass is
        # already present in the primary equivalent inertia data.
        row=[1,1+data['coordinates'][-1,1],*point,9.81*mass]
        block=re.search(r'(?ms)^Weight\n(.*?)^End$',text);assert block
        replacement=block.group(0).replace('\nEnd','\n'+' '.join(format(float(x),'.17g') for x in row)+'\nEnd')
        text=text[:block.start()]+replacement+text[block.end():]
    return text,data,mesh(data,spec['refinement'])


def observables(position,rotation):
    position,rotation=np.asarray(position),np.asarray(rotation)
    point=position+rotation@np.array([MIDCHORD_OFFSET,0.,0.])
    return dict(midchord_position_m=point.tolist(),
        twist_xz_deg=float(np.degrees(np.arctan2(-rotation[2,0],rotation[0,0]))))


def datasets():
    rows=[]
    for folder,reference in [('01_GFEM_Bending','GFEM'),('02_GFEM_Torsion','GFEM'),
        ('03_Beam_Bending','UM/NAST'),('04_Beam_Torsion','UM/NAST'),
        ('05_Experimental_Bending','experiment'),('06_Experimental_Torsion','experiment')]:
        for path in sorted((CACHE/STATIC/folder).glob('*sweep*.txt')):
            data=np.loadtxt(path);assert np.all(np.isfinite(data))
            rows.append(dict(path=path.relative_to(CACHE).as_posix(),sha256=sha(path),
                kind='bending' if 'bending' in path.name else 'torsion',skin=int(re.search('skin([01])',path.name)[1]),
                quantity='twist' if '_rot_' in path.name else 'displacement',
                reference=reference,linear='_linear' in path.name,values=data.tolist(),
                convention='Displacements in percent of nominal0.55m semispan, twist in degrees. All sweep values subtract their own zero-payload gravity state.'))
    return rows
