"""Conditional ST-4 inputs from primary properties, without frequency fitting.

The two endpoints bound distributed chord-axis rotary inertia by nominal
airfoil thickness while fixing measured span-axis polar inertia. Concentrated
assemblies use equivalent chordwise point pairs. Their unreported bending
inertia and spanwise CG offset are zero in this explicitly reduced model.
"""
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]
INPUTS=ROOT/'.reference/isae-st4-experiment-inputs'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def inputs():
    return json.loads((INPUTS/'physical-setup.json').read_text()),json.loads((INPUTS/'primary-table.json').read_text())


def configurations():
    physical,table=inputs();found={}
    for row in table['records']:
        key=(row['variant'],row['span_position_in_from_root'])
        found.setdefault(key,[]).append(row['run'])
    assert len(found)==42
    return [dict(variant=variant,position_in=position,primary_runs=runs)
            for (variant,position),runs in found.items()]


def parameters(spec):
    physical,_=inputs();p=physical['wing_primary'];b=physical['section_rotary']
    icc=b['j_cc_'+spec['icc_endpoint']+'_kg_m'];points=[]
    if spec['variant']!='unloaded':
        mass=next(row for row in physical['concentrated_weights'] if row['name']==spec['variant'])
        s=spec['position_in']*.0254
        points=[[mass['equivalent_two_point_mass_each_kg'],s,x,0.,s] for x in mass['equivalent_two_point_x_m']]
    return dict(points=points,length=p['span_m'],t0=0.,mass=p['mass_per_span_kg_m'],icc=icc,ip=p['centroidal_polar_per_span_kg_m'],
        ei=p['EI_N_m2'],gj=p['GJ_N_m2'],ea_x=p['x_EA_from_LE_m'],cg_x=p['x_CG_from_LE_m'],gravity=9.80665)


def source(spec):
    p=parameters(spec);physical,_=inputs();chord=physical['wing_primary']['chord_m'];length=p['length'];g=p['gravity'];f=lambda x:format(x,'.17g')
    tag=spec['variant']+('' if spec['position_in'] is None else '-'+str(spec['position_in'])+'in')
    lines=[
        '! Conditional primary NACA TN1594 reconstruction; not the original ISAE model.',
        '! No fitted properties. Fixed polar inertia; chord-axis rotary inertia at geometry-bound '+spec['icc_endpoint']+' endpoint.',
        '! Stiff in-plane. Equivalent chordwise point masses; unreported pylon bending inertia and axial CG offset omitted.',
        '! Vacuum modes with gravity +z. Zero-speed experiments were in air of unspecified density.',
        '! Material parameter t=1+s(m) avoids the documented zero-origin mirroring rule; physical root is z=0.',
        'Name','NACA TN1594 '+tag+' jcc-'+spec['icc_endpoint'],'End',
        'Units','L 1 m','T 1 s','F 1 N','End',
        'Constant',f(g)+' 1.225 340.294','End',
        'Reference',f(chord*length)+' '+f(chord)+' '+f(length),'0 0 0','End']
    if p['points']:
        lines+=['Weight','! beam t x y z weight']
        for mass,s,x,y,z in p['points']:lines+=[' '.join(['1',f(1+s),f(x),f(y),f(z),f(mass*g)])]
        lines+=['End']
    lines+=['Ground','1 1 0','End','Beam 1','Primary vertical cantilever',
        't x y z chord Xax EIcc GJ EInn GKc EA GKn mg mgcc mgnn Cea Nea Cta Nta Ccg Ncg']
    for s in [0.,length]:
        values=[1+s,0.,0.,s,chord,0.,p['ei'],p['gj'],0.,0.,0.,0.,p['mass']*g,p['icc']*g,(p['ip']-p['icc'])*g,p['ea_x'],0.,p['ea_x'],0.,p['cg_x'],0.]
        lines+=[' '.join(map(f,values))]
    return '\n'.join(lines+['End',''])


def provenance():
    return {p.name:sha(p) for p in [INPUTS/'physical-setup.json',INPUTS/'primary-table.json',Path(__file__)]}
