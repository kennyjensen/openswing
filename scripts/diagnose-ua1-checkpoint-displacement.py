"""Bounded diagnostic of displacement information lost by a physical checkpoint.

The capture run uses unchanged production. Probe restoration can retain the
captured displacement coordinates; this is an explicit diagnostic, not a new
production checkpoint format or validation pass.
"""
import argparse
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isae_ua1_stall_browser import read, write, pins, verify
from isae_ua_artifacts import write_trajectory

BASE = ROOT/'artifacts/isae/ua1-checkpoint-displacement-20261103'
FAILED = ROOT/'artifacts/isae/ua1-stall-corrected-20261103'


def prepare():
    assert not BASE.exists()
    prior = read(FAILED/'plan.json'); verify(prior['source_sha256'])
    receipt = read(FAILED/'n320-part046-execution.json')
    assert receipt['exit_code'] == 1
    BASE.mkdir()
    paths = [FAILED/'plan.json', FAILED/'n320-part045/request.json',
        FAILED/'n320-part045/checkpoint.json', FAILED/'n320-part046/request.json',
        FAILED/'n320-part046/trajectory.json.gz', FAILED/'n320-part046-execution.json']
    plan = dict(source_sha256={**prior['source_sha256'], **pins([Path(__file__).resolve()])},
        input_sha256=pins(paths), physical_limit=2e-8, subprocess_cap_seconds=45,
        serial=True, production_changed=False, native_validation=False,
        scope='Capture the accepted displacement before serialization; compare eight-step resumes with and without retaining it.')
    write(BASE/'plan.json', plan)
    for name in ('capture','ordinary','retained-displacement'):
        (BASE/name).mkdir()
    write(BASE/'capture/request.json', read(FAILED/'n320-part045/request.json'))
    request = read(FAILED/'n320-part046/request.json')
    full = read(FAILED/'request-n320.json')
    end = float(full['time']['forcing'].splitlines()[1+46*20+8].split()[0])
    request['time']['duration'] = end-request['checkpoint']['state']['time']
    write(BASE/'ordinary/request.json', request)
    write(BASE/'retained-displacement/request.json', request)
    print(json.dumps(dict(prepared=True)), flush=True)


def run(mode):
    from openswing.bridge import dispatch
    import openswing.time_state as time_state
    plan = read(BASE/'plan.json'); verify(plan['source_sha256']); verify(plan['input_sha256'])
    folder = BASE/mode; captured = {}
    original_pack = time_state.pack_state
    original_unpack = time_state.unpack_state
    kept = None if mode != 'retained-displacement' else read(BASE/'capture/displacements.json')

    def capture(network, state):
        packed = original_pack(network, state)
        actual = state.x[:6*network.nn].reshape(network.nn, 6)[:, :3]
        restored = (np.asarray(packed['network']['positions'])-network.rj)/network.L
        row = dict(time=state.time, scale=network.L, jig=network.rj.tolist(),
            displacement_coordinates=actual.tolist(), restored_coordinates=restored.tolist(),
            loss_metres=((restored-actual)*network.L).tolist())
        key = format(state.time, '.17g')
        # Several pack calls refer to the same accepted state; do not silently
        # combine differing displacement histories under an identical time.
        if key in captured:
            assert captured[key] == row
        captured[key] = row
        return packed

    def restore(network, data, feedback):
        state = original_unpack(network, data, feedback)
        if kept is not None:
            key = format(state.time, '.17g')
            if key in kept:
                saved = kept[key]
                assert saved['scale'] == network.L and np.array_equal(saved['jig'], network.rj)
                displacement = np.asarray(saved['displacement_coordinates'])
                assert np.array_equal(network.rj+network.L*displacement, np.asarray(data['network']['positions']))
                state.x[:6*network.nn].reshape(network.nn, 6)[:, :3] = displacement
                state.r = network.unpack(state.x)[0]
        return state

    time_state.pack_state = capture
    time_state.unpack_state = restore
    start = time.monotonic()
    try:
        raw = dispatch(read(folder/'request.json'))
    finally:
        time_state.pack_state = original_pack
        time_state.unpack_state = original_unpack
    seconds = time.monotonic()-start
    write_trajectory(folder/'trajectory.json.gz', raw)
    write(folder/'displacements.json', captured)
    assert raw['converged'] and raw['rejected_steps'] == 0
    assert raw['accepted_steps'] == (20 if mode == 'capture' else 8)
    report = dict(mode=mode, seconds=seconds, accepted_steps=raw['accepted_steps'], rejected_steps=0,
        maximum_lost_displacement_metres=max(float(abs(np.asarray(r['loss_metres'])).max()) for r in captured.values()),
        rows=[dict(time=s['time'], residual=s['residual'],
            acceleration_max_by_axis=abs(np.asarray(s['local_acceleration'])).max(axis=0).tolist(),
            velocity_max_by_axis=abs(np.asarray(s['local_velocity'])).max(axis=0).tolist()) for s in raw['snapshots']],
        production_changed=False, full_periodic_validation=False)
    write(folder/'report.json', report)
    write(folder/'completed.json', dict(output_sha256=pins([folder/name for name in
        ('request.json','trajectory.json.gz','displacements.json','report.json')]), exit_code=0))
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare','capture','ordinary','retained-displacement'])
    args = parser.parse_args()
    prepare() if args.action == 'prepare' else run(args.action)
