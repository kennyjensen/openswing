"""Actual loaded Daedalus vortex geometry and geometric load-transfer regression.

Expected values use independent filament quadrature and SO(3) virtual work.
These maps exclude volume/jet/stall/load-law derivatives and aircraft solves.
"""
import json
from pathlib import Path

import numpy as np
import pytest

from openswing.asw import parse_asw
from openswing.equilibrium_state import restore, warm_start_recipe
from openswing.factored_influence import FactoredInfluence
from openswing.frozen_influence import lifting_geometry
from openswing.linear_dynamics import DynamicSystem
from openswing.local_motion import NetworkMotion
from openswing.network import StaticNetwork
from openswing.operating import time_load_constraints
from openswing.time_state import read_condition

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(__file__).with_name('data')/'daedalus-curved-aero'


@pytest.fixture(scope='module')
def loaded_maps():
    config = json.loads((ROOT/'examples/dae-cruise-physical-mesh-project.json').read_text())['cases'][0]['configuration']
    packet = config['equilibrium']['state']
    launch = packet['launch']
    model = parse_asw(config['source'])
    network = StaticNetwork(model, launch['panels'], read_condition(launch['condition']),
                            launch['gravity'], launch['loads'], operating_constraints=time_load_constraints('free'),
                            strut_mode=launch['strut_mode'], mesh_recipe=warm_start_recipe(model, launch['panels'], packet))
    system = DynamicSystem(network, restore(network, packet), 'free')
    with np.load(DATA/'inputs.npz') as saved:
        inputs = {key: saved[key] for key in saved.files}
    assert (network.nn, network.ng, system.size) == (108, 82, 2044)
    np.testing.assert_allclose(system.r0[inputs['receiving']], inputs['positions'], atol=2e-13, rtol=2e-13)
    np.testing.assert_allclose(system.gamma0, inputs['gamma'], atol=2e-13, rtol=2e-13)
    np.testing.assert_allclose(-system.U0, inputs['freestream'], atol=2e-13, rtol=2e-13)
    zero = np.zeros(system.size)

    def evaluate(z):
        state, _, _ = system.physical_state(z, zero)
        geometry = network.geometry(state.r, state.Q)
        meshes = network.deformed_meshes(state.r, state.Q, geometry)
        free = -state.U
        wind = free/np.linalg.norm(free)
        panels = lifting_geometry(meshes, wind)
        pg = np.eye(3)+(1/np.sqrt(1-system.condition.mach**2)-1)*np.outer(wind, wind)
        cores = np.maximum(system.condition.wake_core_ratio*panels['chord'], panels['ds'])
        effective = np.where(panels['physical'][:, None] == panels['physical'][None, :], 0., cores[None, :])
        result = {'g_'+key: panels[key] for key in ('a', 'b', 'cp', 'hv', 'ds')}
        result.update(g_axis=panels['rm'], g_pg=pg, g_wind=wind, g_source_core=cores)
        for name, points in (('cp', panels['cp']), ('hv', panels['hv']), ('axis', panels['rm'])):
            field = FactoredInfluence(points, panels['a'], panels['b'], wind, pg, effective,
                                      exclude_bound=None if name == 'cp' else np.eye(network.ng, dtype=bool))
            result['velocity_'+name] = field.apply(state.gamma)
        zeros = np.zeros_like(state.r)
        motion = NetworkMotion(network, state.r, state.Q, zeros, zeros, zeros, zeros)
        nodal = np.zeros((network.nn, 6))
        samples = {key: [] for key in ('r0', 'r1', 'rm', 'R0', 'R1', 'Rm', 'ds')}
        wa, wb, offset = [], [], 0
        for mesh in meshes:
            if not mesh.beam.lifting:
                continue
            beam = mesh.beam.index
            count = len(mesh.tm)
            selected = slice(offset, offset+count)
            fractions = network.fractions[beam]
            for ids, force, moment in motion.nodal_wrenches(beam, fractions, inputs['force'][selected], inputs['moment'][selected]):
                np.add.at(nodal[:, :3], ids, force)
                np.add.at(nodal[:, 3:], ids, moment)
            a, b = motion.wrench_weights(beam, fractions)
            wa.extend(a)
            wb.extend(b)
            for key, value in dict(r0=mesh.r0, r1=mesh.r1, rm=mesh.rm, R0=mesh.frame0,
                                   R1=mesh.frame1, Rm=mesh.frames, ds=mesh.length).items():
                samples[key].extend(value)
            offset += count
        result.update(Wa=np.array(wa), Wb=np.array(wb), transfer=nodal[inputs['receiving']],
                      **{'sample_'+key: np.array(value) for key, value in samples.items()})
        return result

    return evaluate, inputs


def assert_maps(actual, expected):
    assert set(actual) == set(expected)
    for key in expected:
        np.testing.assert_allclose(actual[key], expected[key], atol=2e-8, rtol=2e-8, err_msg=key)


def test_loaded_daedalus_base_maps(loaded_maps):
    evaluate, inputs = loaded_maps
    with np.load(DATA/'expected.npz') as expected:
        assert_maps(evaluate(np.zeros(inputs['directions'].shape[1])),
                    {key.removeprefix('base__'): expected[key] for key in expected if key.startswith('base__')})


@pytest.mark.parametrize('direction', range(4), ids=('1Hz-real', '1Hz-imag', 'dip-real', 'dip-imag'))
def test_loaded_daedalus_directional_maps(loaded_maps, direction):
    evaluate, inputs = loaded_maps
    z, h = inputs['directions'][direction], 5e-4
    probes = {m: evaluate(m*h*z) for m in (-2, -1, 1, 2)}
    actual = {key: (-probes[2][key]+8*probes[1][key]-8*probes[-1][key]+probes[-2][key])/(12*h) for key in probes[1]}
    prefix = f'd{direction}__'
    with np.load(DATA/'expected.npz') as expected:
        assert_maps(actual, {key.removeprefix(prefix): expected[key] for key in expected if key.startswith(prefix)})
