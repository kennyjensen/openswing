from pathlib import Path
import numpy as np
import pytest
from scipy.integrate import quad
from scipy.spatial.transform import Rotation
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, solve_rigid
from openswing.network import solve_static
from openswing.operating import OperatingConstraint
from openswing.propulsion import actuator_disk, engine_axes, engine_load, jet_profile, jet_velocity
from test_network import balanced


def engine(typ=0, radius=-1., omega=150., thrust=1., torque=-.03):
    row = np.zeros(25)
    row[:15] = [1,typ,1,0,-1.5,0,-.3,-1,0,0,thrust,torque,radius,omega,.002]
    return row


def wing(rows, filename="rectangular"):
    source = Path(f"examples/{filename}.asw").read_text()
    return parse_asw(source+"\nEngine\n"+"\n".join(" ".join(map(str, row)) for row in rows)+"\nEnd\n")


def test_hover_matches_ideal_momentum_theory_and_density_scaling():
    power, rho, radius = 1700., 1.17, .8
    state = actuator_disk(power, rho, 0., radius, 180., 0.)
    expected = (2*rho*np.pi*radius**2)**(1/3)*power**(2/3)
    assert state["thrust"] == pytest.approx(expected, rel=1e-12)
    assert state["thrust"]*state["delta_velocity"]/2 == pytest.approx(power)
    other = actuator_disk(power, rho/8, 0., radius, -180., 0.)
    assert other["thrust"] == pytest.approx(expected/2)
    assert other["torque"] == -state["torque"]


@pytest.mark.parametrize("power", [4000., 0., -1e8])
def test_forward_disk_power_budget_and_physical_windmill_branch(power):
    rho, v, r, omega, cda = 1.2, 25., .7, 190., .003
    state = actuator_disk(power, rho, v, r, omega, cda)
    dv = state["delta_velocity"]
    swirl = 1+5*(v/(omega*r))**2
    assert state["inviscid_power"] == pytest.approx((v+swirl*dv/2)*state["thrust"], abs=1e-8)
    assert v+dv > 0
    assert state["torque"]*omega == pytest.approx(-power)
    if power > -1e7:
        assert not state["power_clipped"]
        assert state["inviscid_power"]+state["viscous_power"] == pytest.approx(power)
    else:
        assert state["power_clipped"]
        # Minimum found independently by sampling power on either side.
        def f(d): return rho*np.pi*r*r*(v+swirl*d/2)*(v+d/2)*d
        assert f(dv-.001) > f(dv) and f(dv+.001) > f(dv)


@pytest.mark.parametrize("power", [2500., 0.])
def test_jet_integrated_linear_and_angular_momentum_at_every_station(power):
    rho = 1.225
    row = engine(1, radius=.8)
    state = engine_load(row, power, rho, np.zeros(3), np.array([25.,0.,0.]))
    for x in (.001, 1., 4., 10., 60.):
        c, b, dv, dw = map(float, jet_profile(state, x, rho))
        def velocities(r):
            return jet_velocity(np.array([[x, r, 0.]]), [state], np.array([1.,0.,0.]), rho)[0]
        # Direct polar integration of the actual velocity field, not k1..k4.
        momentum = quad(lambda r: 2*np.pi*r*rho*(25+velocities(r)[0])*velocities(r)[0], 0, b,
                        points=[c] if 0<c<b else None, epsabs=1e-8)[0]
        angular = quad(lambda r: 2*np.pi*r*r*rho*(25+velocities(r)[0])*velocities(r)[2], 0, b,
                       points=[c] if 0<c<b else None, epsabs=1e-8)[0]
        assert momentum == pytest.approx(state["thrust"], abs=1e-7)
        assert angular == pytest.approx(state["torque"], abs=1e-7)
    np.testing.assert_array_equal(jet_velocity([[-1,0,0],[3,100,0]], [state], [1,0,0], rho), 0.)


def test_axes_default_vertical_and_rotated_wrench_are_objective():
    np.testing.assert_allclose(engine_axes([0,0,0]), np.eye(3))
    q = Rotation.from_rotvec([.5,-.3,.2]).as_matrix()
    row = engine(); row[7:10] = [0,0,3]
    state = engine_load(row, 100, 1.2, [0,0,0], np.array([20.,0.,0.]))
    rotated = engine_load(row, 100, 1.2, [0,0,0], q@np.array([20.,0.,0.]), rotation=q)
    np.testing.assert_allclose(rotated["force"], q@state["force"], atol=1e-12)
    np.testing.assert_allclose(rotated["moment"], q@state["moment"], atol=1e-12)


def test_proportional_engines_superpose_and_mount_transfers_offset_moment():
    a, b = engine(), engine(thrust=.3, torque=.01)
    b[0] = 2
    model = wing([a,b])
    c = FlightCondition(alpha=3,mach=0,powers={1:120,2:-20})
    result = solve_rigid(model,c,panels=8)
    baseline = solve_rigid(wing([]),FlightCondition(alpha=3,mach=0),panels=8)
    expected_f = np.array([-114.,0.,0.]); expected_m = np.array([3.8,0,0])+np.cross(a[4:7],expected_f)
    np.testing.assert_allclose(np.array(result["force"])-baseline["force"],expected_f,atol=1e-10)
    np.testing.assert_allclose(np.array(result["moment"])-baseline["moment"],expected_m,atol=1e-10)
    mounted = solve_static(model,c,panels=8)
    np.testing.assert_allclose(mounted["force"],result["force"],atol=1e-8)
    balanced(mounted)


def test_propulsive_jet_changes_circulation_point_drag_and_closes_drag_breakdown():
    row = engine(radius=1.2)
    def with_weight(row):
        return parse_asw(wing([row]).dumps()+"\nWeight\n1 0 1 0 -.3 0 .04\nEnd\n")
    model = with_weight(row)
    c = FlightCondition(alpha=5,mach=0,powers={1:250})
    jet = solve_rigid(model,c,panels=16)
    row[12] *= -1
    nojet = solve_rigid(with_weight(row),c,panels=16)
    assert jet["CL"] > nojet["CL"]+.002
    assert jet["CD"] == pytest.approx(sum(jet[k] for k in ("CDi_near","CDp","CDam","CDeng")), abs=1e-12)
    assert abs(jet["strips"][7]["circulation"]-nojet["strips"][7]["circulation"]) > .01
    assert np.linalg.norm(jet["point_forces"][0]) > 1.1*np.linalg.norm(nojet["point_forces"][0])


def test_engine_power_is_an_operating_unknown_for_propulsive_balance():
    model = wing([engine()])
    result = solve_static(model,FlightCondition(alpha=0,mach=0),panels=8,gravity=[0,0,0],
                          operating_constraints=[OperatingConstraint("power.1","force.x",0)])
    assert result["operating_values"]["power.1"] > 20
    assert abs(result["applied_force"][0]) < 1e-7
    balanced(result)


def test_specified_surface_lift_excludes_direct_engine_loads():
    row=engine();row[7:10]=[-1,0,1]
    model=wing([row])
    reference=solve_rigid(model,FlightCondition(alpha=4,mach=0,powers={1:500}),panels=8)
    ez=FlightCondition(alpha=4).vectors()[2]
    target=np.array(reference["surface_force"])@ez
    assert np.array(reference["force"])@ez > target+200
    result=solve_static(model,FlightCondition(alpha=2,mach=0,powers={1:500}),panels=8,gravity=[0,0,0],
                        operating_constraints=[OperatingConstraint("alpha","lift",target)])
    assert result["operating_values"]["alpha"] == pytest.approx(4.,abs=1e-7)


def test_powered_braced_elastic_wing_couples_geometry_propulsion_and_circulation():
    model = parse_asw(Path("examples/powered.asw").read_text())
    condition = FlightCondition(alpha=5,mach=0,powers={1:3000})
    rigid = solve_rigid(model,condition,panels=12)
    elastic = solve_static(model,condition,panels=12)
    assert elastic["max_displacement"] > .02
    assert len(elastic["engines"]) == len(elastic["struts"]) == 2
    assert all(e["thrust"] > 0 for e in elastic["engines"])
    assert all(s["tension"] > 0 for s in elastic["struts"])
    assert abs(elastic["CL"]-rigid["CL"]) > .001
    assert {kind:sum(a['kind']==kind for a in elastic['attachments']) for kind in ('engine','strut','weight')} == dict(engine=2,strut=2,weight=2)
    for row,e in zip(model.records["engine"],elastic["engines"]):
        node = min((n for n in elastic["nodes"] if n["beam"] == e["beam"]),key=lambda n:abs(n["t"]-e["t"]))
        q=np.array(node["rotation"])
        expected_p=np.array(node["position"])+q@(row[4:7]-np.array(node["jig_position"]))
        np.testing.assert_allclose(e["position"],expected_p,atol=1e-12)
        np.testing.assert_allclose(e["axes"],q@engine_axes(row[7:10]),atol=1e-12)
        disk=next(o for o in elastic["attachments"] if o["kind"]=="engine" and np.linalg.norm(np.array(o["segments"][0][1])-expected_p)<1e-8)
        np.testing.assert_allclose(disk["segments"][0][1],e["position"],atol=1e-12)
    balanced(elastic,atol=1e-6)


def test_invalid_settings_and_reverse_disk_flow_are_rejected():
    with pytest.raises(ValueError,match="declared indices"):
        solve_rigid(wing([engine()]),FlightCondition(powers={2:10}),panels=4)
    row = engine(1, radius=0)
    with pytest.raises(ValueError,match="nonzero Rdisk"):
        solve_rigid(wing([row]),FlightCondition(),panels=4)
    with pytest.raises(ValueError,match="reverse flow"):
        actuator_disk(1000,1.2,-5,1,100,0)


def test_unloaded_jet_keeps_zero_field_and_arbitrarily_weak_power_response():
    row=engine(radius=.8,torque=0)
    rho=1.225;speed=25.;direction=np.array([1.,0.,0.])
    points=np.array([[-1.,0.,0.],[2.,0.,0.],[2.,.3,.2],[2.,4.,0.]])
    state=engine_load(row,0.,rho,np.zeros(3),speed*direction)
    np.testing.assert_array_equal(jet_velocity(points,[state],direction,rho),0.)
    np.testing.assert_array_equal(jet_velocity(points,[dict(state,axial_velocity=0.)],direction,rho),0.)
    with pytest.raises(ValueError,match='positive downstream convection'):
        jet_velocity(points,[dict(state,axial_velocity=-1.)],direction,rho)
    # The derivative of zero-power momentum balance is T'/(rho*pi*R²*V).
    # No small positive or negative command may be rounded to an unloaded jet.
    slope=row[10]/(rho*np.pi*row[12]**2*speed)
    for power in [1e-18,-1e-18,1e-8,-1e-8]:
        loaded=engine_load(row,power,rho,np.zeros(3),speed*direction)
        value=jet_velocity(points,[loaded],direction,rho)[1,0]
        assert value != 0
        assert value/power == pytest.approx(slope,rel=1e-10)


@pytest.mark.parametrize("spin", [-1, 1])
def test_p_factor_matches_independent_azimuthal_blade_element_integration(spin):
    rho, radius, omega, power, advance = 1.225, .8, spin*180., 2000., 25.
    row = engine(2, radius=-radius, omega=omega)
    row[14] = 0
    row[15:17] = cl, cla = .6, 5.8
    dv = actuator_disk(power,rho,advance,radius,omega,0)["delta_velocity"]
    vd = advance+dv/2
    nodes, weights = np.polynomial.legendre.leggauss(80)
    radii, dr = radius*(nodes+1)/2, radius*weights/2
    chord, blades = .06, 3
    phi = np.arctan2(vd,abs(omega)*radii)
    for j in range(4):
        row[17+2*j] = blades*chord/radius**2*np.sum(np.sin(phi)*(radii/radius)**j*dr)
        row[18+2*j] = blades*chord/radius**2*np.sum(np.cos(phi)*(radii/radius)**j*dr)
    psi = np.arange(192)*2*np.pi/192
    er = np.stack([np.zeros_like(psi),np.cos(psi),np.sin(psi)],axis=-1)
    xe = np.array([1.,0.,0.])
    et = -spin*np.cross(xe,er)
    arm = radii[:,None,None]*er[None,:,:]
    baseline = vd*xe-abs(omega)*radii[:,None,None]*et[None,:,:]
    def blade_wrench(side_velocity, mount_rate):
        velocity = baseline+side_velocity-np.cross(mount_rate,arm)
        axial = velocity[...,0]
        tangent = -np.sum(velocity*et[None,:,:],axis=-1)
        flow_angle = np.arctan2(axial,tangent)
        local_cl = cl+cla*(phi[:,None]-flow_angle)
        force = (.5*rho*(axial**2+tangent**2)*local_cl*chord*dr[:,None])[...,None]*(
            -np.cos(flow_angle)[...,None]*xe-np.sin(flow_angle)[...,None]*et[None,:,:])
        return np.r_[force.sum(axis=(0,1)),np.cross(arm,force).sum(axis=(0,1))]*blades/len(psi)
    h=1e-5
    for velocity,rate in [(np.array([0.,h,0.]),np.zeros(3)),(np.zeros(3),np.array([0.,0.,h]))]:
        expected=(blade_wrench(velocity,rate)-blade_wrench(-velocity,-rate))/(2*h)
        plus=engine_load(row,power,rho,np.zeros(3),advance*xe+velocity,rate)
        minus=engine_load(row,power,rho,np.zeros(3),advance*xe-velocity,-rate)
        actual=np.r_[plus["force"]-minus["force"],plus["moment"]-minus["moment"]]/(2*h)
        np.testing.assert_allclose(actual,expected,rtol=2e-7,atol=2e-8)
