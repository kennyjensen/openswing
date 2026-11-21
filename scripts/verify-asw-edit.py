"""Edited ASW: independent axial mechanics/poles and equivalent flap inputs."""
import hashlib,json,platform,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import scipy
from openswing.asw import parse_asw
from openswing.asw_edit import edit_distribution,model_data
from openswing.bridge import dispatch


def run():
    files=[Path(__file__),Path('examples/instrumented-oscillator.asw'),Path('examples/rectangular.asw'),*sorted(Path('openswing').glob('*.py'))]
    study=dict(description='Edited ASW serialization: exact axial compliance and damped spring poles; equivalent rescaled flap derivatives.',
        versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),
        source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},cases={},
        limitations=['The spline endpoint convention is not verified against ASWING.',
            'Equivalent-input and native/WASM agreement are consistency checks, not independent aerodynamic validation.',
            'Exact ASWING cursor-graft, endpoint and complete editor conventions remain unverified; distribution-graft is a separate study.'])
    original=Path('examples/instrumented-oscillator.asw').read_text()
    for scale in (1,2,4):
        edit_request=dict(action='edit_distribution',source=original,beam=1,name='EA',edit=dict(multiplier=scale))
        edited=dispatch(edit_request);source=edited['source'];model=parse_asw(source)
        assert model_data(model)==model_data(edit_distribution(parse_asw(original),1,'EA',multiplier=scale))
        request=dict(action='solve',mode='mounted',source=source,panels=4,gravity=[0,0,0],condition=dict(speed=10,alpha=0,mach=0,powers={1:10}))
        response=dispatch(request);exact=.02/scale;actual=response['nodes'][-1]['position'][1]-2
        assert abs(actual-exact)<1e-10
        mode_request=dict(action='modes',source=source,panels=4,gravity=[0,0,0],condition=dict(speed=10,alpha=0,mach=0),modes=dict(count=8))
        modes=dispatch(mode_request);poles=[complex(*v['eigenvalue']) for v in modes['modes']]
        # m=2, k=EA/L=500*scale, Kelvin-Voigt c=k*.02.
        exact_poles=np.roots([2,10*scale,500*scale]);error=max(min(abs(p-v) for p in poles) for v in exact_poles)
        assert error<1e-6
        study['cases'][f'spring_{scale}']=dict(edit_request=edit_request,edited=edited,request=request,response=response,
            mode_request=mode_request,modes=modes,comparison=dict(displacement=actual,exact_displacement=exact,
            displacement_error=abs(actual-exact),exact_poles=[[v.real,v.imag] for v in exact_poles],max_pole_error=error))
        print(f'spring {scale}: displacement error {abs(actual-exact):.3g}, pole error {error:.3g}',flush=True)
    original=Path('examples/rectangular.asw').read_text();m=parse_asw(original)
    m=edit_distribution(edit_distribution(m,1,'dCLdF1',multiplier=2),1,'dCMdF1',multiplier=2)
    request=dict(action='solve',mode='rigid',source=m.dumps(),panels=12,condition=dict(speed=20,alpha=0,mach=0,controls={1:4}))
    reference=dispatch({**request,'source':original,'condition':{**request['condition'],'controls':{1:8}}})
    response=dispatch(request)
    delta=max(np.max(abs(np.asarray(response[key])-reference[key])) for key in ('force','moment'))
    assert delta<1e-9
    study['cases']['flap']=dict(request=request,response=response,reference=reference,comparison=dict(max_wrench_difference=delta))
    path=Path('docs/validation/asw-edit.json');path.write_text(json.dumps(study,indent=2,allow_nan=False)+'\n')
    print(f'Completed four cases; {len(study["source_sha256"])} source hashes; {path.stat().st_size} bytes.',flush=True)

if __name__=='__main__':run()
