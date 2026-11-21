"""Explicit production adapter for the unloaded independent-wing study.

The independent reference never imports this module. Native calculations must
name a kernel checkout; imports and material-table identity are verified before
the existing structural reconstruction is extended with zero-camber airloads.
"""
import importlib
import json
import runpy
import sys
from pathlib import Path
import numpy as np


def load_kernel(kernel_root):
    root=Path(kernel_root).resolve()
    if not (root/'openswing/linear_dynamics.py').is_file():
        raise ValueError('The explicit kernel root has no OpenSwing dynamics implementation.')
    sys.path.insert(0,str(root))
    modules={name:importlib.import_module('openswing.'+name) for name in ['asw','aero','linear_dynamics']}
    if any(Path(module.__file__).resolve().parents[1]!=root for module in modules.values()):
        raise ValueError('Imported OpenSwing does not belong to the requested kernel root.')
    return root,modules


def source_for_case(kernel_root,spec):
    root,_=load_kernel(kernel_root)
    structure=runpy.run_path(str(root/'scripts/verify-durrant-structure.py'))
    source=structure['configuration'](dict(wing=spec['wing']))
    source=source.replace('Vacuum structural study only; aerodynamic coefficients are not reconstructed.',
        'Unloaded analogue: zero camber, Cm, gravity, and disabled stall; not a published case.')
    source=source.replace('structural reconstruction','unloaded finite-wing analogue')
    source=source.rsplit('End',1)[0]+'t dCLda CLmax CLmin alpha Cm Cdf Cdp\n'
    for station in (1,2):
        source+=f'{station} {2*np.pi:.17g} 100 -100 0 0 0 0\n'
    return source+'End\n'


def condition_for_case(modules,spec):
    return modules['aero'].FlightCondition(speed=spec['speed_m_s'],alpha=0.,beta=0.,mach=0.,
        density=spec['density_kg_m3'],aero_lag=spec['aero_lag'],stall=False)


def compute(kernel_root,spec,progress=lambda message:None):
    root,modules=load_kernel(kernel_root)
    dyn=modules['linear_dynamics']
    source=source_for_case(root,spec)
    condition=condition_for_case(modules,spec)
    panels=dict(default=spec['panels'],beams={'1':dict(count=spec['panels'],spacing='uniform')})
    progress('native_equilibrium')
    system,_=dyn.make_system(modules['asw'].parse_asw(source),condition,panels=panels,
        gravity=[0.,0.,0.],tolerance=1e-9,continuation_steps=4)
    base=system.base_report()
    if base['modal_base']['continuous_residual']>=1e-9 or base['max_displacement']>=1e-10 or abs(base['CL'])>=1e-10:
        raise ValueError('The prescribed zero-load base was not recovered.')
    result=dict(condition=vars(condition),panels=panels,gravity=[0.,0.,0.],base=base,
        actual_elements=system.network.ne,jig_positions=system.network.rj.tolist(),searches=[])
    progress('native_linearization')
    a,m=dyn.linearize(system,step=1e-5)
    for shift in ([-.1,100.],[-.3,200.]):
        progress('native_search_'+str(shift))
        modes,metadata=dyn.eigensystem(a,m,time_scale=system.W,count=24,
            method='full_shift_invert',shift=shift)
        rows=[]
        for mode in modes:
            if max(mode['right_backward_error'],mode['left_backward_error'])>=1e-9:
                raise ValueError('Original native descriptor residual exceeds1e-9.')
            shape=mode['right'][:6*system.network.nn].reshape(system.network.nn,6).copy()
            shape[:,:3]*=system.L
            rows.append(dict(eigenvalue_per_s=mode['eigenvalue'],frequency_Hz=mode['eigenvalue'][1]/(2*np.pi),
                right_backward_error=mode['right_backward_error'],left_backward_error=mode['left_backward_error'],
                mechanical_shape=dyn.complex_data(shape)))
        result['searches'].append(dict(shift_per_s=shift,metadata=metadata,modes=rows))
    return dict(source=source,spec=spec,native=result)


def validate_saved(record,kernel_root,spec,kernel_hashes):
    root,modules=load_kernel(kernel_root)
    expected_source=source_for_case(root,spec)
    if record['status']!='computed' or record['source']!=expected_source:
        raise ValueError('Saved native source differs from the requested unloaded reconstruction.')
    old=record['spec']
    expected=dict(wing=spec['wing'],speed_m_s=spec['speed_m_s'],panels=spec['panels'],
        density_kg_m3=spec['density_kg_m3'],aero_lag=spec['aero_lag'],tangent_step=1e-5)
    if any(old[key]!=value for key,value in expected.items()):
        raise ValueError('Saved native physical settings differ from the requested case.')
    old_kernel={Path(path).name:value for path,value in record['source_sha256'].items()
                if Path(path).parent.name=='openswing' and path.endswith('.py')}
    if old_kernel!=kernel_hashes:
        raise ValueError('Saved native result belongs to different production kernel sources.')
    native=record['native']
    expected_condition=json.loads(json.dumps(vars(condition_for_case(modules,spec))))
    if native['condition']!=expected_condition or native['gravity']!=[0.,0.,0.]:
        raise ValueError('Saved native condition differs from the requested condition.')
    if native['panels']!=dict(default=spec['panels'],beams={'1':dict(count=spec['panels'],spacing='uniform')}):
        raise ValueError('Saved native discretization differs from requested uniform panels.')
    base=native['base']
    if base['modal_base']['continuous_residual']>=1e-9 or base['max_displacement']>=1e-10 or abs(base['CL'])>=1e-10:
        raise ValueError('Saved native unloaded base is not sufficiently resolved.')
    if [s['shift_per_s'] for s in native['searches']]!=[[-.1,100.],[-.3,200.]]:
        raise ValueError('Saved native search coverage differs.')
    if any(max(row['right_backward_error'],row['left_backward_error'])>=1e-9
           for search in native['searches'] for row in search['modes']):
        raise ValueError('Saved original native descriptor residual exceeds1e-9.')
    return dict(source=record['source'],spec=spec,native=native)
