"""Pinned public ROM syntax and independent nonzero-input transfer checks.

External samples are fetched into .reference when absent; they are not included
in release archives. The source manifest pins repository revision and SHA256.
"""
import hashlib
import json
from pathlib import Path
import platform
import re
import sys
import urllib.request
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import scipy
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.reduced_model import solve_reduced_model
from openswing.rom_file import parse_rom,write_rom,real_rom,rom_response,export_rom,array

manifest_path=Path('docs/validation/rom-file-sources.json')
manifest=json.loads(manifest_path.read_text())
files=[Path(__file__).resolve(),manifest_path.resolve(),Path('examples/mechanical-reference.rom').resolve(),
       Path('examples/instrumented-oscillator.asw').resolve(),Path('examples/actuator-lag-controller.json').resolve(),
       *sorted(Path('openswing').resolve().glob('*.py'))]
provenance=dict(versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),
    source_sha256={str(p.relative_to(Path.cwd())):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
checkpoint=Path('.reference/rom-file-verification-checkpoint.json')
saved=json.loads(checkpoint.read_text()) if checkpoint.exists() else {}
cache=saved.get('cases',{}) if saved.get('provenance')==provenance else {}


def record(name,compute):
    if name in cache:
        print('Resumed '+name,flush=True);return cache[name]
    result=compute();cache[name]=result
    temporary=checkpoint.with_suffix('.tmp');temporary.write_text(json.dumps(dict(provenance=provenance,cases=cache),allow_nan=False));temporary.replace(checkpoint)
    print(name+': '+json.dumps(result.get('errors',{})),flush=True);return result


def numeric_columns(text):
    # Separate literal-column check, independent of the annotated grammar.
    return np.array([[float(v.replace('D','e').replace('d','e')) for v in line.split()[:2]]
        for line in text.splitlines() if line.strip() and not line.lstrip().startswith('#')])


def published(item):
    path=Path(item['local'])
    data=path.read_bytes() if path.exists() else b''
    if hashlib.sha256(data).hexdigest()!=item['sha256']:
        data=urllib.request.urlopen(item['url']).read()
        assert hashlib.sha256(data).hexdigest()==item['sha256'],item['url']
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    source=data.decode();model=parse_rom(source);normalized=write_rom(model)
    np.testing.assert_array_equal(numeric_columns(source),numeric_columns(normalized))
    again=parse_rom(normalized)
    assert {k:v for k,v in model.items() if k!='source'}=={k:v for k,v in again.items() if k!='source'}
    assert model['source'].encode()==data
    out=rom_response(model,[0.,1.,10.,100.,1000.]);assert out['converged']
    # Every currently published specimen here has zero printed input coupling.
    assert np.max(abs(array(model['matrices']['B'])),initial=0.)==0
    assert np.max(abs(array(model['matrices']['D'])),initial=0.)==0
    for sample in out['samples']:assert np.max(abs(array(sample['response'])),initial=0.)==0
    errors=dict(coefficient_changes=0)
    if item['path'].endswith('Modal_analysis/Pazy_wing_flutter_alpha3_up.rom'):
        assert model['modes']==[dict(index=3,eigenvalue=[1.20391,192.997])]
        np.testing.assert_array_equal(array(model['matrices']['C'])[:,0],[-.87009e-4-.64185e-4j,-.40566e-1+.40499e-2j])
    if item['path'].endswith('[p15_0].rom'):
        # Independent kinematic identity for these mounted sensor GPS columns.
        names=[o['name'] for o in model['outputs']];c=array(model['matrices']['C'])
        poles=np.array([complex(*m['eigenvalue']) for m in model['modes']])
        relative=[]
        for axis in 'XYZ':
            v=c[names.index(f'U{axis} vel [1]')];p=c[names.index(f'R{axis} pos [1]')]
            relative.extend(abs(v-poles*p)/np.maximum(abs(v),1e-30))
        error=float(max(relative));assert error<2e-4,error
        errors['maximum_printed_velocity_position_identity_error']=error
    return dict(kind='published ASWING annotated ROM',source=item,printed_modes=len(model['modes']),
        real_states=len(out['real_matrices']['A']),inputs=model['inputs'],outputs=model['outputs'],
        modes=model['modes'],selected_state_names=model['state_names'],numeric_rows=len(numeric_columns(source)),errors=errors)


def independent_file():
    model=parse_rom(Path('examples/mechanical-reference.rom').read_text());out=rom_response(model,[0,.1,2,15,30,100])
    errors=[]
    for sample in out['samples']:
        s=1j*sample['omega'];h=1/(2*s*s+10*s+500)
        exact=np.array([[h,.1-.3*h],[s*h,-.3*s*h],[s*s*h,-.3*s*s*h],[0,2/(s+4)]])
        errors.append(float(np.max(abs(array(sample['response'])-exact))))
    assert max(errors)<3e-15
    return dict(kind='original two-input oscillator and first-order filter',result=out,
        errors=dict(maximum_absolute_transfer_error=max(errors)))


def generated(scaled=False,controller=False):
    source=Path('examples/instrumented-oscillator.asw').read_text()
    L,T,F=(2.,2.,3.) if scaled else (1.,1.,1.)
    if scaled:source=source.replace('L 1 m','L 2 m').replace('T 1 s','T 2 s').replace('F 1 N','F 3 N')
    law=json.loads(Path('examples/actuator-lag-controller.json').read_text()) if controller else None
    frequencies=np.array([0.,1.,5.,20.,100.]);model=parse_asw(source)
    result=solve_reduced_model(model,FlightCondition(speed=10,alpha=0,mach=0),4,gravity=[0,0,0],count=3 if controller else 2,
        controller=law,inputs=['power.1','command.RY[2]'] if controller else ['power.1'],
        outputs=['RY[2]','UY[2]','Ay[2]'],frequencies=(frequencies*T).tolist())
    text=export_rom(result,model.units,model.name);out=rom_response(parse_rom(text),frequencies)
    expected=[]
    m,k,c=2*F*T*T/L,500*F/L,10*F*T/L
    for omega in frequencies:
        s=1j*omega;plant=m*s*s+c*s+k
        if controller:
            kp,kd,tau=200*F/L,20*F*T/L,.05*T
            h=np.array([F,kp])/((1+tau*s)*plant+kp+kd*s)
        else:h=np.array([F/plant])
        expected.append(np.array([1,s,s*s])[:,None]*h)
    expected=np.array(expected);actual=np.array([array(s['response']) for s in out['samples']])
    error=np.max(abs(actual-expected),axis=0)/np.maximum(np.max(abs(expected),axis=0),1e-30)
    assert error.max()<2e-7,error
    converted=np.array([array(s['reduced']) for s in result['samples']])*np.array([L,L/T,L/T**2])[None,:,None]
    if controller:converted[:,:,1]/=L
    interchange=np.max(abs(actual-converted),axis=0)/np.maximum(np.max(abs(converted),axis=0),1e-30)
    assert interchange.max()<1e-10,interchange
    return dict(kind='generated lag-controller ROM' if controller else 'generated oscillator ROM',source=source,controller=law,
        input_si_scales=dict(L=L,T=T,F=F),rom_text=text,imported=out,
        independent=dict(real=expected.real.tolist(),imag=expected.imag.tolist()),
        errors=dict(normalized_reference=error.tolist(),normalized_interchange=interchange.tolist()))


if __name__=='__main__':
    cases=[record(f'published-{i}',lambda item=item:published(item)) for i,item in enumerate(manifest['sources'])]
    cases.append(record('independent-file',independent_file))
    cases += [record('generated-si',lambda:generated()),record('generated-scaled',lambda:generated(True)),
              record('generated-controller-scaled',lambda:generated(True,True))]
    Path('docs/validation/rom-file.json').write_text(json.dumps(dict(description='Annotated ASWING ROM syntax, exact coefficient preservation and independent nonzero-input transfer verification.',
        **provenance,cases=cases,limitations=['The nine external samples have zero control/direct matrices. Their numerical forced dynamics are therefore not a nonzero transfer benchmark.',
            'The original independent mechanical and newly generated examples provide nonzero SISO/MIMO, conjugate, feedthrough and SI-scaling checks.',
            'Printed ROM transfer matrices do not contain all data used by ASWING Bode reconstruction corrections; executable interoperability and aircraft physics parity are not established.']),indent=2,allow_nan=False)+'\n')
    print(f'Completed {len(cases)} ROM exchange cases with {len(provenance["source_sha256"])} generating hashes.',flush=True)
