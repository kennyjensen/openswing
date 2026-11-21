"""Independent sensor load/deflection refinement and free-fall measurements."""
import hashlib
import json
from pathlib import Path
import platform
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import scipy
from openswing.asw import parse_asw
from openswing.network import solve_static
from openswing.time_integration import solve_time
from openswing.ground import body_to_earth

PREFIX='''Name
Sensor verification cantilever
End
Unit
L 1 m
T 1 s
F 1 N
End
Constant
9.80665 1.225 340.294
End
Reference
2 1 2
End
Ground
1 0 0
End
'''
SOURCE=PREFIX+'''Beam 1
Straight cantilever
t y EIcc Cshell Nshell Atshell
0 0 100 0 .03 .004
2 2 100 0 .03 .004
End
Sensor
1 1 0 .2 0 .1
2 1 .7 .2 .7 .1
3 1 2 .2 2 .1
End
'''
FREE=PREFIX+'''Beam 1
Rigid reference beam
t y
0 0
2 2
End
Weight
1 0 0 0 0 9.80665 0 0 0 0 0 19.6133 29.41995 39.2266
End
Sensor
1 1 0 .3 .2 .1
End
'''


def bending(panels):
    force=.01; length=2.; stiffness=100.
    out=solve_static(parse_asw(SOURCE),panels=panels,gravity=[0,0,0],loads=[dict(beam=1,t=2,force=[0,0,-force])])
    samples=[]
    for sensor in out['sensors']:
        t=sensor['t']; expected_z=-force*t*t*(3*length-t)/(6*stiffness)
        expected_bank=force*t*(2*length-t)/(2*stiffness)*180/np.pi
        frame=np.array(sensor['section_axes_body'])
        force_body=frame@sensor['force_local']; moment_body=frame@sensor['moment_local']
        strain_t=sensor['strain_sample_t']; expected_strain=.03*force*(length-strain_t)/stiffness
        samples.append(dict(index=sensor['index'],t=t,strain_sample_t=strain_t,
            anchor_z=sensor['anchor_position_body'][2],linear_beam_z=expected_z,
            bank=sensor['bank'],linear_beam_bank=expected_bank,
            force_body=force_body.tolist(),moment_body=moment_body.tolist(),
            shell_strain=sensor['shell_strain'],linear_beam_strain=expected_strain))
        np.testing.assert_allclose(force_body,[0,0,-force],atol=1e-9)
        assert abs(moment_body[0]+force*(length-t)) < 1e-8
        assert abs(sensor['shell_strain']-expected_strain) < 2e-12
    error=max(abs(s['anchor_z']-s['linear_beam_z']) for s in samples)
    return dict(kind='small-load cantilever',source=SOURCE,panels=panels,sensors=samples,maximum_deflection_error=error,
                residual=out['residual'])


def free_fall(dt):
    position=np.array([1,2,3]); attitude=[20,-15,30]
    out=solve_time(parse_asw(FREE),panels=4,frame='free',duration=.2,dt=dt,position=position,attitude=attitude)
    p=position+body_to_earth(attitude)@[.3,.2,.1]
    errors=[]; samples=[]
    for snapshot in out['snapshots']:
        t=snapshot['time']; sensor=snapshot['sensors'][0]
        exact=p+np.array([0,0,-.5*9.80665*t*t])
        errors.append(float(np.linalg.norm(sensor['position_earth']-exact)))
        np.testing.assert_allclose(sensor['acceleration_sensor'],0,atol=1e-8)
        np.testing.assert_allclose(sensor['velocity_earth'],[0,0,-9.80665*t],atol=1e-8)
        samples.append(dict(time=t,specific_force=sensor['acceleration_sensor'],gps_position=sensor['position_earth'],exact_position=exact.tolist()))
    return dict(kind='free-fall GPS and accelerometer',source=FREE,step=dt,snapshots=samples,
                maximum_gps_position_error=max(errors),maximum_specific_force=max(np.linalg.norm(s['specific_force']) for s in samples))


if __name__=='__main__':
    bending_cases=[bending(n) for n in (4,8,16)]
    errors=[c['maximum_deflection_error'] for c in bending_cases]
    assert errors[1] < .4*errors[0] and errors[2] < .4*errors[1],errors
    falling=[free_fall(dt) for dt in (.05,.025,.0125)]
    errors=[c['maximum_gps_position_error'] for c in falling]
    assert errors[1] < .27*errors[0] and errors[2] < .27*errors[1],errors
    files=[Path(__file__).resolve(),*sorted(Path('openswing').resolve().glob('*.py'))]
    report=dict(description='Original sensor refinement benchmarks; not ASWING executable or measured-aircraft parity.',
        references=['https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf'],
        versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),
        source_sha256={str(p.relative_to(Path.cwd())):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        cases=bending_cases+falling,
        limitations=['Small-load Euler–Bernoulli deflections are a linear reference for a nonlinear beam; the load is chosen to make nonlinear corrections much smaller than mesh errors.',
                     'Strain is compared at the reported adjacent element midpoint, not falsely labeled as an exact nodal value.',
                     'GPS position includes the initial BDF1 step error. Specific force and velocity provide independent acceleration and trajectory checks.'])
    Path('docs/validation/sensors.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print('Cantilever sensor deflection errors:',[c['maximum_deflection_error'] for c in bending_cases])
    print('Free-fall GPS position errors:',errors)
    print('Maximum free-fall specific force:',max(c['maximum_specific_force'] for c in falling))
