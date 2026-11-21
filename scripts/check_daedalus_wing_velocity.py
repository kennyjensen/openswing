"""Analytic local-velocity derivatives of the wing's six global load rows.

Differentiate printed steady Eqs. 67, 70, 72--73 / unsteady Eq. 34 with
geometry and circulation fixed. The independent field evaluator supplies base
airflow. No production aerodynamic derivative or fitted coefficient is used.
"""
import argparse
from copy import deepcopy
from types import SimpleNamespace
from check_daedalus_load_sensitivity import ROOT, read, write
from daedalus_bounded_job import run
from check_daedalus_circulation_phase import module, CAPTURE, REFERENCE
import check_daedalus_regular_mesh_response as response
from check_daedalus_component_difference import SEEDS

STUDY = ROOT/'artifacts/daedalus-wing-velocity-20261114'
CASES = [response.STUDY, ROOT/'artifacts/daedalus-pitch-balanced-base-20261114']
FREQUENCY = 1.15737773741517
LABELS = ['ordinary_lift', 'skin_drag', 'pressure_drag', 'stall_drag', 'section_pitch']


def audit(folder, args):
    import numpy as np
    import scipy.sparse as sp
    from daedalus_source_aero_reference import FullAeroReference, sample_beam, softplus
    case = args['case']
    previous = response.configure()
    system = previous.dynamic(SimpleNamespace(seed=SEEDS[case])); n = system.network
    capture = module(CAPTURE, '_wing_velocity_capture')
    zero = np.zeros(system.size)
    fixture = capture.fixed_fixture(system, (ROOT/'examples/dae.asw').read_text())
    packet = capture.capture(system, zero, zero)
    assert not np.any(packet['inputs']['motion']['rates'])
    assert not np.any(packet['inputs']['w']) and not np.any(packet['inputs']['gamma_dot'])
    beam = next(b for b in fixture['beams'] if b['index'] == 1)
    nodes = np.asarray(beam['node_ids'])
    for kind in ('engine', 'weight'):
        for attachment in fixture['attachments'][kind]:
            # No engine or point drag can respond to this wing-only velocity.
            if attachment['node'] in nodes:
                assert kind == 'weight' and attachment['row'][6] == 0

    # The independent stationary field evaluator need not model nonzero mean
    # acceleration: relative airflow is independent of acceleration, and at
    # Omega=w=0 its local-velocity derivative in real/apparent inertia is zero.
    # Remove acceleration ONLY from this field-evaluation copy, never the
    # actual system, captured state, or comparison matrix.
    airflow_packet = deepcopy(packet)
    for key in ('acceleration', 'angular_acceleration'):
        airflow_packet['inputs']['motion'][key] = np.zeros(3)
    # The separate jet reference accepts positive thrust only. A type-0
    # engine with exactly zero power has zero thrust, torque and plume, so
    # omit that inactive record from the independent airflow copy. Retain
    # all actual aircraft masses and the original comparison matrix.
    airflow_fixture = deepcopy(fixture)
    engine_rows = fixture['records']['engine']
    active = []
    for index, row in enumerate(engine_rows):
        power = packet['inputs']['condition']['powers'][int(row[0])]
        if power == 0:
            assert row[1] == 0 and row[10]*power == row[11]*power == 0
        else:
            active.append(index)
    airflow_fixture['records']['engine'] = engine_rows[active]
    airflow_fixture['attachments']['engine'] = [fixture['attachments']['engine'][i] for i in active]
    ref = FullAeroReference(airflow_fixture, airflow_packet, quadrature=32)
    fields = ref.evaluate(ref.base)
    count = len(beam['element_ids'])
    assert ref.lifting[0]['index'] == 1
    section = sample_beam(beam, ref.base, fixture['ends'])
    v = fields['lifting_velocity'][:count]
    observed = np.array([s['relative_velocity'] for s in packet['native']['aero']['strips'] if s['beam'] == 1])
    airflow_error = float(np.max(abs(v-observed)))
    np.testing.assert_allclose(v, observed, rtol=2e-9, atol=2e-8)
    span = section['Rm'][:, :, 1]; chord_axis = section['Rm'][:, :, 0]
    material = beam['material_receiver']; chord = material['chord']
    alpha = np.deg2rad(material['alpha']).copy(); cm = material['Cm'].copy(); cdp = material['Cdp'].copy()
    condition = packet['inputs']['condition']
    for key, value in condition['controls'].items():
        alpha += value*material[f'dCLdF{key}']/material['dCLda']
        cm += value*material[f'dCMdF{key}']; cdp += value*material[f'dCDdF{key}']
    normal = np.sin(alpha)[:, None]*chord_axis+np.cos(alpha)[:, None]*section['Rm'][:, :, 2]
    vp = v-np.sum(v*span, axis=1)[:, None]*span
    speed = np.linalg.norm(v, axis=1); normal_speed = np.linalg.norm(vp, axis=1)
    cl = fields['lifting_cl'][:count]; width = condition['stall_width']
    leakage = width*(softplus((cl-material['CLmax'])/width)-softplus((material['CLmin']-cl)/width))
    tangency = fields['circulation_local_residual'][:count]*condition['speed']
    if condition['stall']:
        tangency += normal_speed/material['dCLda']*condition['stall_factor']*leakage
    rho = ref.rho; sound = ref.sound; ds = section['ds']; gamma = packet['inputs']['gamma'][:count]
    beta = np.sqrt(1-(normal_speed/sound)**2)
    origin = fixture['reference'][1]
    lift_arm = section['rm']+((.25-material['Xax'])*chord)[:, None]*chord_axis-origin
    drag_arm = (section['r0']+section['r1'])/2-origin
    matrices = np.zeros((len(LABELS), 6, 3*n.nn))
    a, b = fixture['ends'][beam['element_ids']].T
    for component in range(3):
        dv = np.broadcast_to(-np.eye(3)[component], v.shape)
        dvp = dv-np.sum(dv*span, axis=1)[:, None]*span
        dS = np.sum(vp*dv, axis=1)/normal_speed
        dV = np.sum(v*dv, axis=1)/speed
        dt = np.sum(dv*normal, axis=1)
        forces = [
            (rho*gamma*ds)[:, None]*np.cross(dv, span),
            (.5*rho*chord*material['Cdf']*ds)[:, None]*(speed[:, None]*dv+dV[:, None]*v),
            (.5*rho*chord*cdp*ds)[:, None]*(normal_speed[:, None]*dvp+dS[:, None]*vp),
            (2*rho*chord*ds)[:, None]*(
                (2*tangency*dt/normal_speed)[:, None]*vp
                +(tangency**2/normal_speed)[:, None]*dvp
                -(tangency**2*dS/normal_speed**2)[:, None]*vp),
            np.zeros_like(v)]
        pitch = (.5*rho*chord**2*cm*ds*(2*normal_speed/beta
            +normal_speed**3/(sound**2*beta**3))*dS)[:, None]*span
        moments = [np.cross(lift_arm, forces[0]),
                   *[np.cross(drag_arm, force) for force in forces[1:4]], pitch]
        for k, (force, moment) in enumerate(zip(forces, moments)):
            wrench = np.c_[force, moment]
            for ids, weight in ((a, 1-beam['fraction']), (b, beam['fraction'])):
                for output in range(6):
                    np.add.at(matrices[k, output], 3*ids+component, weight*wrench[:, output])
    layout = read(CASES[case]/'mass/layout.json')
    force_scale = layout['internal_loads']['force_scale']; moment_scale = layout['internal_loads']['moment_scale']
    scales = np.array([force_scale]*3+[moment_scale]*3)
    normalized = matrices*system.V/scales[None, :, None]
    columns = (3*nodes[:, None]+np.arange(3)).ravel()
    actual = sp.load_npz(CASES[case]/'assembled/A.npz')[n.operating_start:n.operating_start+6,
        system.velocity_start+columns].toarray()
    expected = normalized.sum(axis=0)[:, columns]
    error = float(np.max(abs(actual-expected)))
    relative = float(np.linalg.norm(actual-expected)/np.linalg.norm(actual))
    np.testing.assert_allclose(actual, expected, rtol=2e-7, atol=2e-10)
    with np.load(CASES[case]/'response'/f'state-{FREQUENCY:.9g}.npz') as saved:
        z = saved['state']
    u = system.V*z[system.velocity_start:system.velocity_start+3*n.nn]
    roll_components = matrices[:, 3]@u
    by_axis = np.array([matrices.sum(axis=0)[3, j::3]@u[j::3] for j in range(3)])
    np.testing.assert_allclose(roll_components.sum(), by_axis.sum(), rtol=1e-13)
    np.savez_compressed(folder/'arrays.npz', physical_wrench_derivatives=matrices,
        normalized_wrench_derivatives=normalized, saved_matrix_rows=actual, wing_columns=columns,
        local_velocity=u, circulation=gamma, length=ds, span=span, lift_arm=lift_arm,
        positions=packet['inputs']['r'], nodes=nodes, endpoints=fixture['ends'][beam['element_ids']],
        fractions=beam['fraction'], scales=scales)
    encode = lambda v:dict(real=float(v.real), imag=float(v.imag), magnitude=float(abs(v)))
    result = dict(case=str(CASES[case].relative_to(ROOT)), nodes=len(nodes), velocity_columns=len(columns),
        checked_matrix_entries=int(actual.size), base_airflow_difference_ft_s=airflow_error,
        matrix_max_absolute_error=error, matrix_relative_frobenius_error=relative,
        native_dip_frequency_hz=FREQUENCY,
        roll_moment_components_lb_ft_per_F3={key:encode(v) for key,v in zip(LABELS,roll_components)},
        roll_moment_by_velocity_axis_lb_ft_per_F3={key:encode(v) for key,v in zip('xyz',by_axis)},
        total_wing_velocity_roll_moment=encode(roll_components.sum()),
        base_acceleration=packet['inputs']['motion']['acceleration'].tolist(),
        base_angular_acceleration=packet['inputs']['motion']['angular_acceleration'].tolist(),
        qualification='Analytic partial at fixed geometry and Gamma. This checks all six global load rows for wing translation-velocity columns, not the complete coupled dynamics or native ASWING agreement. Parsed material values and the declared section sampling/transfer policy are accepted inputs.')
    print(result, flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', type=int, choices=[0, 1], required=True)
    parser.add_argument('--tag', required=True)
    args = vars(parser.parse_args())
    inputs = response.inputs()+[*SEEDS, CAPTURE, ROOT/'scripts/check_daedalus_regular_mesh_response.py',
        ROOT/'scripts/check_daedalus_circulation_phase.py', ROOT/'scripts/check_daedalus_component_difference.py',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-steady.txt',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.txt']
    inputs += [ROOT/'scripts'/name for name in REFERENCE]
    case = CASES[args['case']]
    inputs += [case/'mass/layout.json', case/'assembled/A.npz', case/'response'/f'state-{FREQUENCY:.9g}.npz']
    run(STUDY, args['tag'], inputs, audit, args, __file__)
