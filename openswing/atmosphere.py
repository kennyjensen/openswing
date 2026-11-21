"""U.S. Standard Atmosphere 1976, lower atmosphere, and ASW operating air.

NASA-TM-X-74335, tables 2/4/8 and the hydrostatic, density and sound-speed equations.
Atmospheric altitude is geometric metres, independent of the model's Earth Z
and its input/output unit declarations (ASW guide, OPER explicit parameters).
"""
from functools import lru_cache
import math

R_EARTH = 6356766.0
G0 = 9.80665
R_AIR = 8314.32/28.9644
T0 = 288.15
P0 = 101325.0
GAMMA = 1.4
HEIGHTS = (0., 11000., 20000., 32000., 47000., 51000., 71000.)
LAPSES = (-.0065, 0., .001, .0028, 0., -.0028, -.002)


def _layer(temperature, pressure, gradient, dh):
    t = temperature+gradient*dh
    p = pressure*(t/temperature)**(-G0/(R_AIR*gradient)) if gradient else pressure*math.exp(-G0*dh/(R_AIR*temperature))
    return t, p


BASES = [(T0, P0)]
for i in range(1, len(HEIGHTS)):
    BASES.append(_layer(*BASES[-1], LAPSES[i-1], HEIGHTS[i]-HEIGHTS[i-1]))


@lru_cache(maxsize=128)
def _standard_values(altitude_m):
    z = float(altitude_m)
    if not math.isfinite(z) or not -5000 <= z <= 86000:
        raise ValueError("Standard-atmosphere geometric altitude must be between -5000 and 86000 metres.")
    h = R_EARTH*z/(R_EARTH+z)
    layer = max(i for i, base in enumerate(HEIGHTS) if h >= base) if h >= 0 else 0
    tm, pressure = _layer(*BASES[layer], LAPSES[layer], h-HEIGHTS[layer])
    # Table 8: kinetic temperature differs slightly from molecular-scale
    # temperature above 80 km. Density and sound speed use T_M directly.
    ratios = (1., .999996, .999989, .999971, .999941, .999909, .999870,
              .999829, .999786, .999741, .999694, .999641, .999579)
    ratio = 1.
    if z > 80000:
        x = (z-80000)/500
        i = min(int(x), len(ratios)-2)
        ratio = ratios[i]+(x-i)*(ratios[i+1]-ratios[i])
    return (z, h, tm*ratio, tm, pressure, pressure/(R_AIR*tm),
            math.sqrt(GAMMA*R_AIR*tm), G0*(R_EARTH/(R_EARTH+z))**2)


def standard_atmosphere(altitude_m):
    """Return a fresh SI report; the cached immutable calculation is inexpensive."""
    keys = ("altitude_m", "geopotential_altitude_m", "temperature_K", "molecular_temperature_K",
            "pressure_Pa", "density_kg_m3", "sound_speed_m_s", "gravity_m_s2")
    return dict(zip(keys, _standard_values(float(altitude_m))))


def operating_air(model, condition):
    """Resolve density/sound speed in file units without changing mass conversion.

    The .asw Constant density and sound speed are sea-level references. A supplied
    density overrides the atmospheric density, while temperature/sound speed still
    follow the specified altitude. PG Mach is independently overridable.
    """
    z, h, temperature, tm, pressure, _, _, _ = _standard_values(float(condition.altitude_m))
    sigma = pressure/P0*T0/tm
    density = float(model.constants[1]*sigma if condition.density is None else condition.density)
    sound = float(model.constants[2]*math.sqrt(tm/T0))
    gravity = float(model.constants[0] if condition.gravity_magnitude is None else condition.gravity_magnitude)
    if not math.isfinite(density) or density <= 0:
        raise ValueError("Ambient density must be positive and finite.")
    if not math.isfinite(gravity) or gravity < 0:
        raise ValueError("Gravity magnitude must be finite and nonnegative.")
    if not math.isfinite(condition.load_factor):
        raise ValueError("Lift load factor must be finite.")
    equivalent_speed = condition.speed*math.sqrt(density/model.constants[1])
    return dict(model="US Standard Atmosphere 1976 (lower atmosphere)", altitude_m=z,
                geopotential_altitude_m=h, temperature_K=temperature, molecular_temperature_K=tm,
                standard_pressure_Pa=pressure, standard_density_ratio=sigma,
                density=density, density_source="standard_atmosphere" if condition.density is None else "override",
                density_ratio=float(density/model.constants[1]), sound_speed=sound,
                gravity_magnitude=gravity, ambient_mach=float(condition.speed/sound),
                equivalent_airspeed=float(equivalent_speed), dynamic_pressure=float(.5*density*condition.speed**2),
                load_factor=float(condition.load_factor))
