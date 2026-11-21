"""Primary Pazy inertia mapping audited against the original Nastran MO matrix.

The spreadsheet off-diagonals are signed CONM2 products, despite the README's
matrix-element wording. Negate them when forming the physical inertia tensor.
The earlier pazy_primary module is retained to reproduce its historical study.
"""
import re
import numpy as np
from pazy_primary import ROOT,CACHE,FOLDER,sha,mesh,projection
from pazy_primary import source as historical_source, model as historical_model


def source(skin):
    data=historical_source(skin)
    products=data['inertia'].copy()
    data['inertia']=np.array([2*np.diag(np.diag(j))-j for j in products])
    assert np.min(np.linalg.eigvalsh(data['inertia']))>0
    data['conm2_products']=products
    return data


def model(skin,orientation='horizontal'):
    text,_=historical_model(skin,orientation);data=source(skin)
    rotation=np.eye(3) if orientation=='horizontal' else np.array([[1.,0,0],[0,0,-1.],[0,1.,0]])
    rows=[]
    for position,offset,mass,j in zip(data['coordinates'],data['offset'],data['mass'],data['inertia']):
        tensor=rotation@j@rotation.T;point=rotation@(position+offset)
        row=[1,1+position[1],*point,9.81*mass,0,0,0,0,0,
             *(9.81*np.array([tensor[0,0],tensor[1,1],tensor[2,2],-tensor[0,1],-tensor[0,2],-tensor[1,2]]))]
        rows.append(' '.join(format(float(x),'.17g') for x in row))
    text,count=re.subn(r'(?ms)^Weight\n.*?^End$', 'Weight\n'+'\n'.join(rows)+'\nEnd',text,count=1);assert count==1
    text='! CONM2 product signs verified against the original Nastran rigid-body mass matrix.\n'+text
    text=text.replace('Pazy primary skin','Pazy primary CONM2-audited skin')
    return text,data
