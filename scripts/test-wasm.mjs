import { loadPyodide } from 'pyodide';
import { readFile, readdir } from 'node:fs/promises';
import path from 'node:path';
process.on('uncaughtException',error=>{console.error(error.message);process.exitCode=1;});
const py = await loadPyodide({indexURL:path.resolve('public/runtime')});
await py.loadPackage(['numpy','scipy']);
py.FS.mkdirTree('/home/pyodide/openswing');
for(const name of (await readdir('openswing')).filter(n=>n.endsWith('.py'))) py.FS.writeFile(`/home/pyodide/openswing/${name}`,await readFile(`openswing/${name}`,'utf8'));
py.globals.set('source',await readFile('examples/rectangular.asw','utf8'));
await py.runPythonAsync(`
import numpy as np
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, solve_rigid
from openswing.structure import Section, solve_cantilever
from openswing.network import solve_static
from openswing.operating import free_flight_constraints
m = parse_asw(source)
r = solve_rigid(m, FlightCondition(alpha=0, mach=0))
assert abs(r['CL']) < 1e-10
assert abs(r['CDp'] - .008) < 2e-5
r = solve_rigid(m, FlightCondition(alpha=5))
assert .43 < r['CL'] < .45
assert r['residual'] < 1e-8
b = solve_cantilever(2, Section(EIcc=100), tip_moment=[50*np.pi,0,0])
assert np.max(np.abs(b.position[-1] - [0,0,4/np.pi])) < 2e-7
r = solve_static(m, FlightCondition(alpha=5), panels=8)
assert .43 < r['CL'] < .45
assert r['max_displacement'] < 1e-10
assert np.max(np.abs(r['force_balance'])) < 1e-7
assert np.max(np.abs(r['moment_balance'])) < 1e-7
print('WebAssembly aerodynamic, nonlinear beam, and coupled rigid-limit checks passed')
`);
py.globals.set('source',await readFile('examples/flexible.asw','utf8'));
await py.runPythonAsync(`
r = solve_static(parse_asw(source), FlightCondition(alpha=5, mach=0), panels=12)
assert .40 < r['CL'] < .43
assert r['max_displacement'] > 1
assert r['residual'] < 1e-8
assert np.max(np.abs(r['force_balance'])) < 1e-6
assert np.max(np.abs(r['moment_balance'])) < 1e-6
print('WebAssembly finite-deformation aeroelastic check passed')
`);
py.globals.set('source',await readFile('examples/stress-wing.asw','utf8'));
await py.runPythonAsync(`
from openswing.recovery import recover_section
section = recover_section(Section(EIcc=100, GJ=80, EA=1000, Cea=.2, Nea=.1),
                          [3,10,5], [2,4,0], cshell=.2, nshell=.1, atshell=.002)
assert abs(section['shell']['axial_strain']-.008) < 1e-12
assert abs(section['shell']['shear_stress']-1175) < 1e-10
r = solve_static(parse_asw(source), FlightCondition(alpha=5,mach=0), panels=4)
assert r['structure']['summary']['strain_sections'] == len(r['elements'])
assert r['structure']['summary']['stress_sections'] == len(r['elements'])
assert r['structure']['units']['stress_to_pa'] == 1
assert max(abs(e['shell']['shear_stress']) for e in r['elements']) > 1e4
assert all(e['shell']['axial_strain_bound']+1e-14 >= abs(e['shell']['axial_strain']) for e in r['elements'])
print('WebAssembly section strain, translated torque and closed-shell stress checks passed')
`);
py.globals.set('source',await readFile('examples/inertial.asw','utf8'));
await py.runPythonAsync(`
r = solve_static(parse_asw(source), FlightCondition(alpha=5, mach=0, rates=[0,0,.03]), panels=8,
                 operating_constraints=free_flight_constraints())
assert r['analysis'] == 'constrained_static'
assert r['mass_properties']['mass'] == 100
assert np.max(np.abs(r['applied_force'])) < 1e-5
assert np.max(np.abs(r['applied_moment'])) < 1e-5
assert r['operating_values']['acceleration.z'] > 10
assert np.linalg.norm(r['apparent_force']) > 1
print('WebAssembly accelerating-frame and six-constraint free-flight checks passed')
`);
py.globals.set('source',await readFile('examples/powered.asw','utf8'));
await py.runPythonAsync(`
r = solve_static(parse_asw(source), FlightCondition(alpha=5, mach=0, powers={1:3000}), panels=8, strut_mode='wire')
assert len(r['engines']) == len(r['struts']) == 2
assert all(e['thrust'] > 0 and e['jet_enabled'] for e in r['engines'])
assert all(s['tension'] > 0 and not s['slack'] for s in r['struts'])
assert np.max(np.abs(r['force_balance'])) < 1e-5
assert np.max(np.abs(r['moment_balance'])) < 1e-5
print('WebAssembly powered, braced, finite-deformation equilibrium check passed')
`);
py.globals.set('source',await readFile('examples/wing-body.asw','utf8'));
await py.runPythonAsync(`
r = solve_static(parse_asw(source), FlightCondition(alpha=5, mach=0, acceleration=[0,0,1], body_added_mass_factor=2), panels=8)
assert .43 < r['CL'] < .45
assert r['panels'] > r['lifting_panels'] > 0
assert r['body_added_mass_factor'] == 2
assert np.linalg.norm(r['body_force']) > 1
assert r['max_displacement'] > .3
assert len(next(b for b in r['geometry'] if not b['lifting'])['quads']) > 0
assert np.max(np.abs(r['force_balance'])) < 1e-5
assert np.max(np.abs(r['moment_balance'])) < 1e-5
print('WebAssembly coupled wing/body/point-volume and body apparent-mass check passed')
`);
await py.runPythonAsync(`
from openswing.operating import OperatingConstraint
r = solve_static(parse_asw(source), FlightCondition(alpha=5, mach=0, ground_effect=1,
                 position_earth=[0,0,2], attitude=[0,4,0]), panels=8,
                 operating_constraints=[OperatingConstraint('attitude.elevation','flight_path',0)])
assert abs(r['earth_state']['attitude'][1]-5) < 1e-7
assert r['ground_plane']['flag'] == 1 and r['ground_plane']['minimum_clearance'] > 1
assert np.linalg.norm(r['body_force']) > 1
assert abs(r['gravity_body'][0]-9.80665*np.sin(np.deg2rad(5))) < 1e-8
assert np.max(np.abs(r['force_balance'])) < 1e-5
assert np.max(np.abs(r['moment_balance'])) < 1e-5
print('WebAssembly ground images, mixed-volume equilibrium and Earth-attitude target check passed')
`);
py.globals.set('source',await readFile('examples/articulated.asw','utf8'));
await py.runPythonAsync(`
r = solve_static(parse_asw(source), FlightCondition(alpha=5, mach=0), panels=4)
right, left = r['hinges']
assert 4 < right['angle_deg'] < 7
assert abs(right['angle_deg']+left['angle_deg']) < 1e-7
assert right['structural_moment'] > 1000
assert .35 < r['max_displacement'] < .55
assert np.max(np.abs(r['force_balance'])) < 1e-5
assert np.max(np.abs(r['moment_balance'])) < 1e-5
print('WebAssembly articulated-wing Jangle, circulation and load-balance checks passed')
`);
py.globals.set('source',await readFile('examples/flexible.asw','utf8'));
await py.runPythonAsync(`
from openswing.atmosphere import standard_atmosphere
assert abs(standard_atmosphere(86000)['temperature_K']-186.8673) < .0002
r = solve_static(parse_asw(source), FlightCondition(speed=25, alpha=3, mach=0, altitude_m=10000,
                 gravity_magnitude=4, load_factor=1.5), panels=4,
                 operating_constraints=[OperatingConstraint('speed','equivalent_airspeed',30),
                                        OperatingConstraint('alpha','lift',1000)])
assert abs(r['operating_values']['speed']-51.6352062255) < 1e-7
assert abs(r['operating_constraints'][1]['actual']-1500) < 1e-6
assert r['operating_constraints'][1]['specified_target'] == 1000
assert r['gravity_body'] == [0,0,-4]
assert np.max(np.abs(r['force_balance'])) < 1e-5
assert np.max(np.abs(r['moment_balance'])) < 1e-5
print('WebAssembly standard-atmosphere, equivalent-airspeed, gravity and lift-factor checks passed')
`);
py.globals.set('source',await readFile('examples/trim-aircraft.asw','utf8'));
await py.runPythonAsync(`
from openswing.operating import steady_turn_constraints
r = solve_static(parse_asw(source), FlightCondition(alpha=4, mach=0, attitude=[0,4,57], powers={1:120}), panels=4,
                 operating_constraints=steady_turn_constraints(np.deg2rad(3),trim_controls=[2,1,3],engine_control=1))
assert len(r['operating_constraints']) == 16
assert 8 < r['earth_state']['attitude'][0] < 10
assert abs(r['earth_state']['attitude_rates'][2]-np.deg2rad(3)) < 1e-9
assert np.max(np.abs(r['earth_state']['velocity_derivative_body'])) < 1e-8
assert r['max_displacement'] > .1
assert np.max(np.abs(r['applied_force'])) < 1e-5
assert np.max(np.abs(r['applied_moment'])) < 1e-5
assert np.max(np.abs(r['support_force'])) < 1e-5
assert np.max(np.abs(r['support_moment'])) < 1e-5
print('WebAssembly 16-constraint steady-turn flight trim and reference-point kinematics checks passed')
`);
py.globals.set('source',await readFile('examples/inertial.asw','utf8'));
await py.runPythonAsync(`
r = solve_static(parse_asw(source), FlightCondition(alpha=5, mach=0), panels=4,
                 operating_constraints=free_flight_constraints(),
                 derivatives=dict(response='free_flight',parameters=['alpha','control.1']))
d = r['derivatives']
assert d['matrices']['coefficients'][2][0] > 4
assert abs(d['matrices']['accelerations'][4][1]) > .1
assert np.max(np.abs(d['matrices']['net_wrench'])) < 1e-5
assert np.max(np.abs(d['matrices']['positions'])) < 1e-7
assert max(d['linear_residuals']) < 1e-9
assert d['column_scaled_reciprocal_condition'] > 1e-8
print('WebAssembly implicit free-flight stability/control derivatives and rigid limit passed')
`);
py.globals.set('source',await readFile('examples/rectangular.asw','utf8'));
await py.runPythonAsync(`
import numpy as np
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.structure import Section
from openswing.network import StaticNetwork
net=StaticNetwork(parse_asw(source),4,FlightCondition(alpha=0,mach=0,stall=False),[0,0,0],[])
x=np.zeros(net.size);z=np.zeros_like(net.rj);acc=z.copy();acc[:,2]=2
_,baseline=net.residual(x,detail=True,elastic_motion=(z,z,z,z))
_,data=net.residual(x,detail=True,elastic_motion=(z,z,acc,z))
added=1.225*np.pi/4*12
np.testing.assert_allclose(data['aero']['apparent_force'],[0,0,-2*added],atol=1e-12)
np.testing.assert_allclose((data['force']-baseline['force']).sum(axis=0),[0,0,-2*added],atol=1e-12)
_,lag=net.residual(x,detail=True,elastic_motion=(z,z,z,z),circulation_rate=np.full(net.ng,.5))
np.testing.assert_allclose(lag['aero']['circulation_rate_force'],[0,0,1.225*.5*12],atol=1e-12)
np.testing.assert_allclose(lag['aero']['circulation_residual'],-1/(np.pi*30**2),atol=1e-15)
print('WebAssembly local elastic apparent mass and circulation-rate residual/lift checks passed')
`);
py.globals.set('source',await readFile('examples/wing-body.asw','utf8'));
await py.runPythonAsync(`
import json
from openswing.damping import damping_diagnostics
net=StaticNetwork(parse_asw(source),4,FlightCondition(alpha=0,mach=0,stall=False),[0,0,0],[])
x=np.zeros(net.size);z=np.zeros_like(net.rj)
def mass_action(acc):
    _,data=net.residual(x,detail=True,elastic_motion=(z,z,*acc))
    json.dumps(data['aero'],allow_nan=False)
    return np.r_[data['force'].ravel(),data['moment'].ravel()]
rng=np.random.default_rng(43);a,b=rng.normal(0,1,(2,2,net.nn,3))
base=mass_action(np.zeros_like(a));ma=base-mass_action(a);mb=base-mass_action(b)
assert abs(a.ravel()@mb-b.ravel()@ma)<1e-10
assert a.ravel()@ma>0
s=Section(EIcc=10,GJ=10,EInn=20,EIcs=8,EA=100,GKc=50,GKn=50).compliance()
assert not damping_diagnostics(s[None],np.array([[1,0,1,0,1,0]]),[1])['passive']
print('WebAssembly distributed real/body/surface mass symmetry, energy and damping diagnostics passed')
`);
py.globals.set('source',await readFile('examples/inertial.asw','utf8'));
await py.runPythonAsync(`
from openswing.bridge import run_json
out=json.loads(run_json(json.dumps(dict(action='time',source=source,panels=4,
    condition=dict(alpha=5,mach=0),time=dict(duration=.03,dt=.01,frame='free')))))
assert out['accepted_steps']==3
assert max(s['residual'] for s in out['snapshots'])<1e-8
assert out['snapshots'][-1]['frame']['position_earth'][0]<-.8
assert np.max(abs(np.array(out['snapshots'][-1]['circulation_rate'])))>1
assert out['snapshots'][0]['frame']['position_earth']==[0,0,0]
print('WebAssembly implicit coupled circulation and six-DOF free-flight time integration passed')
`);
await py.runPythonAsync(`
from openswing.time_integration import solve_time
source='''Name
Axial time verification
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
Weight
1 2 0 2 0 19.6133
End
Beam 1
Axial bar
t y EA tdeps
0 0 1000 .02
2 2 1000 .02
End
'''
errors=[]
for dt in (.01,.005):
    out=solve_time(parse_asw(source),panels=4,duration=.1,dt=dt,gravity=[0,0,0],
        initial_loads=[dict(beam=1,t=2,force=[0,1,0])])
    times=np.array([s['time'] for s in out['snapshots']])
    actual=np.array([s['nodes'][-1]['position'][1]-2 for s in out['snapshots']])
    omega=np.sqrt(250-2.5**2)
    exact=.002*np.exp(-2.5*times)*(np.cos(omega*times)+2.5/omega*np.sin(omega*times))
    errors.append(np.max(abs(actual-exact)))
    assert max(s['residual'] for s in out['snapshots'])<1e-8
assert errors[1]<.3*errors[0]
print('WebAssembly damped structural release and BDF2 temporal convergence passed')
`);
py.globals.set('source',await readFile('examples/rectangular.asw','utf8'));
await py.runPythonAsync(`
from openswing.gust import gust_field
from openswing.bridge import run_json
from dataclasses import replace
import json
m=parse_asw(source)
c=FlightCondition(speed=10,alpha=0,mach=0,gust=dict(type='uniform',velocity=[5,0,0]))
r=solve_rigid(m,c,4)
assert abs(r['CDp']-.018)<1e-12
assert abs(r['atmosphere']['dynamic_pressure']-61.25)<1e-10
f=gust_field(dict(type='expression',components=['0','0','sin(pi*x)+t']))
np.testing.assert_allclose(f.velocity([[.5,0,0]],.2),[[0,0,1.2]],atol=1e-14)
try:
    gust_field(dict(type='expression',components=['0','0','x.__class__']))
    raise AssertionError('Unsafe expression was accepted')
except ValueError:
    pass
c=replace(c,gust=dict(type='expression',components=['0','0','.05*t']))
out=solve_time(m,c,4,duration=.04,dt=.01,gravity=[0,0,0])
for s in out['snapshots']:
    assert abs(s['gust']['reference_velocity_body'][2]-.05*s['time'])<1e-12
    assert s['residual']<1e-8
assert out['snapshots'][-1]['CL']>0
print('WebAssembly Earth gust expressions, force normalization and implicit gust response passed')
`);
py.globals.set('source',await readFile('examples/heave-pitch.asw','utf8'));
await py.runPythonAsync(`
from openswing.linear_dynamics import solve_modes, eigensystem
r=solve_modes(parse_asw(source),FlightCondition(speed=50,alpha=0,mach=0,stall=False),4,
              count=8,gravity=[0,0,0])
assert r['diagnostics']['finite_dimension']==8
growing=[m for m in r['modes'] if m['eigenvalue'][0]>0]
assert len(growing)==2
np.testing.assert_allclose([m['eigenvalue'][0] for m in growing],.77290818,atol=3e-5)
np.testing.assert_allclose([abs(m['eigenvalue'][1]) for m in growing],32.44995145,atol=3e-5)
assert max(m['left_backward_error'] for m in r['modes'])<1e-9
assert len(json.dumps(r,allow_nan=False))>100
modes,meta=eigensystem(-np.diag(np.arange(1.,9)),np.eye(8),count=2,shift=(-4.4,.1),method='shift_invert')
np.testing.assert_allclose(sorted(complex(*m['eigenvalue']).real for m in modes),[-5,-4],atol=1e-9)
print('WebAssembly coupled elastic/aerodynamic eigenmodes, complex outputs and shift-and-invert passed')
`);
