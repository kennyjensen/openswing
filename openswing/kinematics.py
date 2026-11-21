"""Reference-point-aware rigid-frame flight kinematics.

No time integration or gust motion is implied. Velocities are aircraft motion
through stationary air, opposite the relative freestream used by aerodynamics.
"""
import numpy as np
from .ground import body_to_earth


def flight_kinematics(condition, model=None):
    rotation = body_to_earth(condition.attitude)
    motion = condition.motion()
    ra = np.zeros(3) if model is None else model.reference[2]
    rv = np.zeros(3) if model is None else model.reference[3]
    velocity = -condition.speed*condition.vectors()[0]
    velocity_origin = velocity-np.cross(motion.rates, rv)
    acceleration = motion.at(rv, ra)
    derivative = acceleration-np.cross(motion.rates, velocity)
    ve, ae, we = rotation@velocity, rotation@acceleration, rotation@motion.rates
    phi, theta, _ = np.deg2rad(condition.attitude)
    # R = Rz(-heading) Ry(elevation) Rx(-bank). Euler rates become
    # nonunique at the elevation pole; retain valid vector outputs there.
    euler_rates = None
    if abs(np.cos(theta)) > 1e-8:
        wx, wy, wz = motion.rates
        heading = (wy*np.sin(phi)-wz*np.cos(phi))/np.cos(theta)
        euler_rates = [-wx+heading*np.sin(theta), wy*np.cos(phi)+wz*np.sin(phi), heading]
    speed_rate = float(velocity@derivative/condition.speed)
    return dict(position=list(condition.position_earth), attitude=list(condition.attitude),
                body_to_earth=rotation.tolist(), velocity_reference=rv.tolist(), acceleration_reference=ra.tolist(),
                velocity_body=velocity.tolist(), velocity_earth=ve.tolist(),
                velocity_origin_body=velocity_origin.tolist(), velocity_origin_earth=(rotation@velocity_origin).tolist(),
                acceleration_velocity_reference_body=acceleration.tolist(), acceleration_velocity_reference_earth=ae.tolist(),
                acceleration_origin_body=motion.at(np.zeros(3), ra).tolist(),
                acceleration_earth=(rotation@motion.acceleration).tolist(),
                rates_earth=we.tolist(), angular_acceleration_earth=(rotation@motion.angular_acceleration).tolist(),
                velocity_derivative_body=derivative.tolist(), speed_rate=speed_rate,
                attitude_rates=euler_rates,
                # The guide's Ar = d(UY)/dt - UX WZ, at the velocity reference.
                # The vector derivative above supplies the general 3D relation.
                radial_acceleration=float(ae[1]-ve[0]*we[2]),
                flight_path=float(np.rad2deg(np.arctan2(ve[2],np.linalg.norm(ve[:2])))))
