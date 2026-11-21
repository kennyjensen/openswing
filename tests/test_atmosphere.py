"""Published COESA tables, independent hydrostatics, units and coupled targets."""
from pathlib import Path
import numpy as np
import pytest
from scipy.integrate import solve_ivp
from openswing.asw import parse_asw
from openswing.atmosphere import standard_atmosphere, operating_air
from openswing.aero import FlightCondition, solve_rigid
from openswing.network import solve_static
from openswing.operating import OperatingConstraint


def wing(name="rectangular"):
    return parse_asw(Path(f"examples/{name}.asw").read_text())


@pytest.mark.parametrize("height,temperature,pressure,density", [
    # NASA-TM-X-74335, Table I, geopotential altitudes, printed pp. 54,58,60,62.
    (5000, 255.650, 54019., .73612),
    (11000, 216.650, 22632., .36392),
    (20000, 216.650, 5474.8, .088035),
    (32000, 228.650, 868.01, .013225),
    (60000, 245.450, 20.314, .00028832),
    (70000, 217.450, 4.6342, .000074243),
    (84000, 188.650, .43597, .0000080510),
])
def test_published_geopotential_table_values(height, temperature, pressure, density):
    # The public operating input is geometric, not geopotential height.
    z = 6356766*height/(6356766-height)
    a = standard_atmosphere(z)
    assert a["geopotential_altitude_m"] == pytest.approx(height, abs=1e-9)
    # The printed lower table uses T_M above 80 km; kinetic T has the optional
    # table-8 molecular-weight correction. Table I high rows: printed p. 66.
    assert a["molecular_temperature_K"] == pytest.approx(temperature, abs=1e-9)
    assert a["pressure_Pa"] == pytest.approx(pressure, rel=3e-5)
    assert a["density_kg_m3"] == pytest.approx(density, rel=3e-5)


def test_all_layers_match_independently_integrated_hydrostatic_equilibrium():
    # Integrate log(p) in geometric height, using the seven explicitly specified
    # temperature lines and inverse-square gravity. No pressure-layer recurrence.
    def derivative(z, _):
        h = z/(1+z/6356766)
        if h < 11000: t = 288.15-.0065*h
        elif h < 20000: t = 216.65
        elif h < 32000: t = 216.65+.001*(h-20000)
        elif h < 47000: t = 228.65+.0028*(h-32000)
        elif h < 51000: t = 270.65
        elif h < 71000: t = 270.65-.0028*(h-51000)
        else: t = 214.65-.002*(h-71000)
        return [-9.80665/(1+z/6356766)**2/(8314.32/28.9644*t)]
    zs = np.array([3000, 12000, 25000, 40000, 49000, 60000, 81000, 86000])
    solution = solve_ivp(derivative, (0, 86000), [np.log(101325)], t_eval=zs,
                         method="DOP853", rtol=1e-11, atol=1e-12, max_step=100)
    actual = [standard_atmosphere(z)["pressure_Pa"] for z in zs]
    np.testing.assert_allclose(actual, np.exp(solution.y[0]), rtol=3e-9)


def test_layer_boundaries_are_continuous_and_high_altitude_molecular_correction():
    for h in (11000, 20000, 32000, 47000, 51000, 71000):
        z = 6356766*h/(6356766-h)
        lo, hi = standard_atmosphere(z-1e-5), standard_atmosphere(z+1e-5)
        for key in ("temperature_K", "pressure_Pa", "density_kg_m3", "sound_speed_m_s"):
            assert lo[key] == pytest.approx(hi[key], rel=1e-8)
    a = standard_atmosphere(86000)
    assert a["temperature_K"] == pytest.approx(186.8673, abs=.0002)
    assert a["temperature_K"]/a["molecular_temperature_K"] == pytest.approx(.999579)
    assert a["sound_speed_m_s"]**2 == pytest.approx(1.4*a["pressure_Pa"]/a["density_kg_m3"])
    assert standard_atmosphere(-5000)["pressure_Pa"] > 101325
    # Reports cannot mutate the cached atmosphere calculation.
    a["pressure_Pa"] = -1
    assert standard_atmosphere(86000)["pressure_Pa"] > 0


@pytest.mark.parametrize("altitude", [-5001, 86001, np.nan, np.inf])
def test_invalid_altitude_is_explicit(altitude):
    with pytest.raises(ValueError, match="altitude"):
        solve_rigid(wing(), FlightCondition(altitude_m=altitude), panels=4)


def test_density_sound_scaling_uses_asw_sea_level_constants_in_any_units():
    m = wing()
    a = operating_air(m, FlightCondition(altitude_m=5000))
    m.constants[1] *= .001
    m.constants[2] *= 100
    # Altitude has its own explicit SI units, even with custom model unit labels.
    m.units.declarations["L"] = (1., "custom_length")
    b = operating_air(m, FlightCondition(speed=3000, altitude_m=5000))
    assert b["density"] == pytest.approx(a["density"]*.001)
    assert b["sound_speed"] == pytest.approx(a["sound_speed"]*100)
    assert b["ambient_mach"] == pytest.approx(a["ambient_mach"])
    assert b["equivalent_airspeed"] == pytest.approx(a["equivalent_airspeed"]*100)


def test_altitude_is_independent_of_earth_position_and_density_override():
    m = wing()
    c = FlightCondition(altitude_m=12000, position_earth=[12, -50, 3], density=.7, mach=.1)
    r = solve_rigid(m, c, panels=4)
    air = r["atmosphere"]
    assert air["density"] == .7 and air["density_source"] == "override"
    assert air["altitude_m"] == 12000
    assert r["earth_state"]["position"][2] == 3
    assert r["mach"] == .1 and air["ambient_mach"] != .1
    assert air["sound_speed"] < m.constants[2]


def test_rigid_density_scaling_and_altitude_dependent_local_moment_mach():
    m = wing()
    low = solve_rigid(m, FlightCondition(mach=0), panels=8)
    high = solve_rigid(m, FlightCondition(mach=0, altitude_m=10000), panels=8)
    ratio = high["atmosphere"]["density_ratio"]
    np.testing.assert_allclose(high["force"], np.array(low["force"])*ratio, rtol=1e-11, atol=1e-9)
    assert high["CL"] == pytest.approx(low["CL"], rel=1e-12)
    np.testing.assert_allclose(high["apparent_mass"]["spatial_matrix"], np.array(low["apparent_mass"]["spatial_matrix"])*ratio, atol=1e-9)
    # A constant Cm distribution isolates the local sound-speed correction.
    from openswing.asw import Distribution
    m.beams[0].distributions["Cm"] = Distribution("Cm", np.array([0, 6]), np.array([.1, .1]), 0)
    low = solve_rigid(m, FlightCondition(speed=150, alpha=0, mach=0, stall=False), panels=8)
    high = solve_rigid(m, FlightCondition(speed=150, alpha=0, mach=0, altitude_m=12000, stall=False), panels=8)
    expected = np.sqrt((1-low["atmosphere"]["ambient_mach"]**2)/(1-high["atmosphere"]["ambient_mach"]**2))
    assert high["Cm"]/low["Cm"] == pytest.approx(expected, rel=1e-12)


@pytest.mark.parametrize("quantity,target", [("equivalent_airspeed", 30.), ("dynamic_pressure", .5*1.225*30**2)])
def test_altitude_speed_constraint_recovers_same_incompressible_loading(quantity, target):
    m = wing()
    baseline = solve_rigid(m, FlightCondition(mach=0), panels=4)
    r = solve_static(m, FlightCondition(speed=25, mach=0, altitude_m=10000), panels=4,
                     operating_constraints=[OperatingConstraint("speed", quantity, target)])
    assert r["operating_values"]["speed"] == pytest.approx(30/np.sqrt(r["atmosphere"]["density_ratio"]), rel=1e-10)
    np.testing.assert_allclose(r["force"], baseline["force"], rtol=1e-9, atol=1e-8)
    assert r["operating_constraints"][0]["actual"] == pytest.approx(target)


def test_prescribed_lift_load_factor_changes_only_its_target():
    m = wing()
    r = solve_static(m, FlightCondition(alpha=2, mach=0, load_factor=1.5), panels=4,
                     operating_constraints=[OperatingConstraint("alpha", "lift", 1000)])
    constraint = r["operating_constraints"][0]
    assert constraint["specified_target"] == 1000
    assert constraint["target"] == 1500
    assert constraint["actual"] == pytest.approx(1500, abs=1e-6)
    assert r["atmosphere"]["load_factor"] == 1.5
    a = solve_rigid(m, FlightCondition(load_factor=1), panels=4)
    b = solve_rigid(m, FlightCondition(load_factor=-2), panels=4)
    np.testing.assert_allclose(a["force"], b["force"], atol=1e-10)


def test_gravity_override_changes_weight_not_mass_and_rotates_with_attitude():
    m = wing("inertial")
    condition = FlightCondition(alpha=0, gravity_magnitude=3, attitude=[0, 30, 0])
    r = solve_static(m, condition, panels=4)
    assert r["mass_properties"]["mass"] == pytest.approx(100)
    np.testing.assert_allclose(r["gravity_body"], [1.5, 0, -3*np.sqrt(3)/2], atol=1e-10)
    np.testing.assert_allclose(np.array(r["applied_force"])-r["force"], np.array(r["gravity_body"])*100, atol=1e-7)
    explicit = solve_static(m, condition, panels=4, gravity=[0, 0, -1])
    np.testing.assert_allclose(explicit["gravity_body"], [0, 0, -1], atol=1e-10)
    assert explicit["mass_properties"]["mass"] == pytest.approx(100)
    assert explicit["gravity_source"] == "body_vector_override"


@pytest.mark.parametrize("kwargs", [dict(density=0), dict(gravity_magnitude=-1), dict(load_factor=np.nan)])
def test_invalid_air_parameters_fail_early(kwargs):
    with pytest.raises(ValueError):
        solve_rigid(wing(), FlightCondition(**kwargs), panels=4)


@pytest.mark.parametrize("quantity", ["equivalent_airspeed", "dynamic_pressure"])
def test_nonpositive_speed_pressure_targets_fail_before_iteration(quantity):
    with pytest.raises(ValueError, match="must be positive"):
        solve_static(wing(), FlightCondition(), panels=4,
                     operating_constraints=[OperatingConstraint("speed", quantity, -1)])
