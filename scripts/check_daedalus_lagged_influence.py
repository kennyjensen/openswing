"""Bounded diagnostic of omitted influence-coefficient geometry derivatives.

Hold vortex/volume coefficients at the loaded equilibrium only when taking
pose derivatives. Circulation, freestream and all other columns stay live.
This tests a possible Newton-matrix approximation; it is not a production mode
or a claim that historical ASWING used this dynamic approximation.
"""
import argparse
from pathlib import Path
from types import SimpleNamespace
from check_daedalus_load_sensitivity import ROOT, SOURCE, read
from check_daedalus_mesh_residual import accepted
from check_daedalus_mesh_zeros import load, paths, factor_at
from daedalus_bounded_job import run

STUDY=ROOT/'artifacts/daedalus-lagged-influence-20261114'
SAMPLES=ROOT/'artifacts/daedalus-mesh-zeros-20261114/coarse-samples'


class LoadedCoefficients:
    phase='record'
    capture_circulation=False

    def __init__(self):self.saved={}
    def fixed_geometry(self,key,compute):return compute()
    def get(self,key,compute):
        if key[0] not in ('vortex','volume'):return compute()
        assert key[1] is not None,key
        if self.phase=='record':
            assert key not in self.saved,key
            self.saved[key]=compute()
        return self.saved[key]


class Probe:
    def __init__(self):
        import numpy as np
        from check_daedalus_structural_resolution import dynamic
        self.system=dynamic(SimpleNamespace(seed=paths('coarse')[2]));self.n=self.system.network
        self.zero=np.zeros(self.system.size);self.fields=LoadedCoefficients();self.calls=0
        assert not self.n.condition.freeze_influences and self.n.condition.mach==.1
        assert self.system.size==2044 and not self.n.hinges and not self.n.loads
        original=self.sample(self.zero,False);held=self.sample(self.zero,True)
        self.fields.phase='held'
        self.base_difference=float(max(abs(held-original)))
        assert self.base_difference<2e-13 and max(abs(original))<1e-9

    def sample(self,z,held):
        self.n.aero_key=None
        assert self.n.iteration_fields is None
        self.n.iteration_fields=self.fields if held else None
        try:result=self.system.residual(z,self.zero)
        finally:self.n.iteration_fields=None
        self.calls+=1
        return result

    def action(self,z,h):
        import numpy as np
        pose=np.zeros_like(z);pose[:6*self.n.nn]=z[:6*self.n.nn]
        pieces=[]
        for component in (np.real,np.imag):
            value=np.zeros(self.system.size)
            for offset,weight in ((-2,1),(-1,-8),(1,8),(2,-1)):
                probe=offset*h*component(pose)
                value+=weight*(self.sample(probe,True)-self.sample(probe,False))/(12*h)
            pieces.append(value)
        delta=pieces[0]+1j*pieces[1]
        allowed=np.r_[np.arange(6*self.n.ne,6*(self.n.ne+self.n.nn)),np.arange(self.n.gamma_start,self.n.size)]
        assert max(abs(delta[np.setdiff1d(np.arange(len(z)),allowed)]))==0
        return delta


def packet(folder):
    import numpy as np
    accepted(folder)
    with np.load(folder/'arrays.npz') as data:return dict(data)


def step(folder,args):
    import numpy as np
    p=Probe();a,m,b,c,layout,seed,structure=load('coarse');f=args['frequency']
    saved=packet(SAMPLES);index=int(np.argmin(abs(saved['frequencies']-f)))
    assert abs(saved['frequencies'][index]-f)<1e-12
    original=saved['outputs'][index]
    if args['from_tag']:
        previous=STUDY/args['from_tag'];record=accepted(previous)
        assert record['frequency_hz']==f
        z=packet(previous)[args['state']]
    else:z=saved['states'][index]
    delta=p.action(z,args['width']);residual=(2j*np.pi*f*m-a)@z-b-delta
    solve=factor_at(a,m,2j*np.pi*f,structure);dz,checks=solve(-residual)
    y=c@z;dy=c@dz
    absolute=float(max(abs(residual)))
    relative=float(np.linalg.norm(residual)/max(np.linalg.norm(b)+np.linalg.norm(delta),1e-30))
    output_change=float(max(abs(dy)/np.maximum(abs(y),1e-30)))
    valid=absolute<2e-11 and relative<2e-8 and output_change<2e-7
    np.savez_compressed(folder/'arrays.npz',state=z,next_state=z+dz,output=y,next_output=c@(z+dz),
        correction=delta,full_modified_residual=residual,state_correction=dz,output_correction=dy,
        original_output=original)
    return dict(frequency_hz=f,from_tag=args['from_tag'],state=args['state'],width=args['width'],
        evaluated_state_accepted=valid,full_modified_residual=absolute,relative_modified_residual=relative,
        next_output_relative_change=output_change,solve_checks=checks,base_difference=p.base_difference,
        nonlinear_evaluations=p.calls,held_coefficient_keys=[repr(k) for k in p.fields.saved],
        output_magnitude=abs(y).tolist(),next_output_magnitude=abs(c@(z+dz)).tolist(),
        amplitude_change_percent=(100*(abs(y)/abs(original)-1)).tolist(),
        qualification='Only pose derivatives of loaded vortex/volume influence coefficients are omitted. Full circulation, frame, local velocity/rate, plume and structural feedback remain. No historical implementation is authenticated.')


def report(folder,args):
    import csv
    import numpy as np
    from check_daedalus_mesh_zeros import CHANNELS
    with (ROOT/'docs/validation/daedalus-rudder-four-outputs.csv').open() as stream:raw=list(csv.DictReader(stream))
    reference={ch:np.array([[float(r['frequency_Hz']),float(r['reference_drawing_magnitude'])]
        for r in raw if r['channel']==ch]) for ch in CHANNELS}
    for values in reference.values():
        assert np.all(values>0) and np.all(np.diff(values[:,0])>0)
    rows=[];checks=[]
    for tag in args['parts']:
        narrow=STUDY/tag;wide=STUDY/(tag+'-wide')
        rn,rw=accepted(narrow),accepted(wide)
        assert rn['evaluated_state_accepted'] and rw['evaluated_state_accepted']
        dn,dw=packet(narrow),packet(wide)
        np.testing.assert_array_equal(dn['state'],dw['state'])
        delta=float(max(abs(dn['correction']-dw['correction'])))
        output_delta=float(max(abs(dn['output_correction']-dw['output_correction'])/abs(dn['output'])))
        assert delta<2e-11 and output_delta<2e-7
        f=rn['frequency_hz'];checks.append(dict(tag=tag,frequency_hz=f,width_load_difference=delta,
            width_output_correction_difference_relative=output_delta,full_modified_residual=rn['full_modified_residual']))
        for j,ch in enumerate(CHANNELS):
            values=reference[ch];assert values[0,0]<=f<=values[-1,0]
            target=float(np.exp(np.interp(np.log(f),np.log(values[:,0]),np.log(values[:,1]))))
            y=dn['output'][j];old=dn['original_output'][j]
            rows.append(dict(frequency_hz=f,channel=ch,original_magnitude=float(abs(old)),
                diagnostic_magnitude=float(abs(y)),reference_magnitude=target,
                amplitude_change_percent=float(100*(abs(y)/abs(old)-1)),reference_error_percent=float(100*(abs(y)/target-1))))
    with (folder/'comparison.csv').open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    return dict(comparisons=rows,checks=checks,
        qualification='Converged conditional derivative-omission diagnostic at the original equilibrium. No production change, parameter fitting, native ASWING authentication or ISAE progress credit.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=['step','report'])
    parser.add_argument('--tag',required=True);parser.add_argument('--frequency',type=float,default=1.15737773741517)
    parser.add_argument('--width',type=float,default=.0005);parser.add_argument('--from-tag')
    parser.add_argument('--state',choices=['state','next_state'],default='next_state');parser.add_argument('--parts',nargs='*',default=[])
    args=vars(parser.parse_args())
    inputs=[ROOT/'scripts'/s for s in ['check_daedalus_mesh_zeros.py','check_daedalus_mesh_residual.py',
        'check_daedalus_source_operator.py','check_daedalus_structural_resolution.py']]
    inputs+=list((ROOT/'openswing').glob('*.py'))
    inputs+=[ROOT/p for p in ['examples/dae.asw','examples/dae-cruise-physical-mesh-project.json','docs/validation/ISAE_STATUS.md',
        'docs/validation/aswing-authoritative-sources.json','reference/aswing-authoritative-20261108/drela-aswing-steady.pdf',
        'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf']]
    inputs+=[SOURCE/'trim-6.7-1/state.json',SOURCE/'mass-6.7/layout.json',SOURCE/'report/comparison.csv']
    if args['stage']=='report':inputs+=[ROOT/'docs/validation/daedalus-rudder-four-outputs.csv']
    folders=[SOURCE/'assembled-6.7',SAMPLES]
    if args['from_tag']:folders+=[STUDY/args['from_tag']]
    for tag in args['parts']:folders+=[STUDY/tag,STUDY/(tag+'-wide')]
    for path in folders:inputs+=[p for p in path.iterdir() if p.suffix in ('.npz','.json')]
    run(STUDY,args['tag'],inputs,globals()[args['stage']],args,__file__)


if __name__=='__main__':main()
