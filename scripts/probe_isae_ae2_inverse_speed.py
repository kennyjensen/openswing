"""Bounded AE-2 inverse-speed diagnostics using the unchanged custom solver.

The native Y positions are continuation coordinates, never fitted properties
or native validation passes. Neighboring 18/19 m/s points control the 17 m/s
comparison. Every worker is serial, capped, and retained without retries.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import isae_suite_aeroelastic as adapter

HELPER = ROOT/'scripts/verify-isae-ae2-sensor-continuation.py'
THREADS = {k:'1' for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')}
read = lambda p: json.loads(p.read_text())
pin = adapter._pin
write = adapter._write
now = lambda: datetime.now(timezone.utc).isoformat()


def prepare(stage):
    assert not stage.exists()
    originals = {speed: adapter._plan(ROOT, selected=f'AE-2-m15_02-b05-ias{speed:03d}-m80')[0]
                 for speed in (17,18,19,20)}
    base = originals[20]
    pins = {p['path']:p for j in originals.values() for p in j['source_pins']+j['kernel_pins']}
    for p in (HELPER, Path(__file__), ROOT/'reference/aswing-authoritative-20261108/isae-part-4.json',
              ROOT/'reference/aswing-authoritative-20261108/isae-part-4-aeroelasticity.pdf'):
        pins[str(p.resolve())] = pin(p)
    cases = []
    for nominal in (20,40):
        request = dict(action='solve', mode='mounted', source=Path(base['source']).read_text(),
            panels=dict(default=nominal, beams={'1':dict(count=nominal, spacing='cosine')}),
            condition=deepcopy(base['condition']), numerics=base['settings'],
            operating_constraints=[], strut_mode='bilateral', controller=None,
            tolerance=1e-10, continuation_steps=1)
        cold = f'm{nominal}-cold20'
        cases.append(dict(name=cold, predecessor=None, request=request, native_speed=20,
                          native_row=originals[20]['reference_row']))
        for speed in (19,17,18):
            target = deepcopy(request)
            target['operating_constraints'] = [dict(variable='speed', quantity='user.tip',
                expression='sensor("1.position_earth.y")',
                target=originals[speed]['reference_row']['values']['RY_m'],
                unit='input L', residual_scale=.558)]
            predecessor = cold if speed == 19 else f'm{nominal}-native19-y'
            cases.append(dict(name=f'm{nominal}-native{speed}-y', predecessor=predecessor,
                request=target, native_speed=speed, native_row=originals[speed]['reference_row']))
    write(stage/'plan.json', dict(observed_utc=now(), cases=cases, pins=list(pins.values()),
        limits=dict(address_space_bytes=512*1024**2, cpu_seconds=15, elapsed_seconds=25, supervisor_seconds=30),
        physical_inputs='Original negative-coupling model, beta5, frozen influences, PG0, density/gravity/wall unchanged.',
        native_reference_cells=0, primary_votes_added=0, retries=0,
        purpose=__doc__, limitations=[
            'Prescribing a native displacement and solving speed is a diagnostic, not a native fixed-speed pass.',
            'Nominal20/40 checks do not replace registered80/160 meshes.',
            'Following one local branch does not establish global uniqueness, stability or historical initialization.',
            'All production custom residual, complete tangent/rank and smoothness checks remain enabled.']))
    print('Prepared eight serial states: cold20 plus three inverse-speed targets per mesh.')


def checked(stage):
    plan = read(stage/'plan.json')
    assert all(pin(p['path']) == p for p in plan['pins']), 'Pinned source changed.'
    return plan


def run(stage, name):
    plan = checked(stage)
    limits = plan['limits']
    resource.setrlimit(resource.RLIMIT_AS, (limits['address_space_bytes'],)*2)
    resource.setrlimit(resource.RLIMIT_CPU, (limits['cpu_seconds'],)*2)
    signal.alarm(limits['elapsed_seconds'])
    spec = importlib.util.spec_from_file_location('inverse_sensor_worker', HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.run(stage, name)


def launch(stage, index):
    plan = checked(stage);case = plan['cases'][index]
    folder = stage/'cases'/case['name']
    assert not folder.exists(), 'Retain every attempt; no retries.'
    if case['predecessor']:
        previous = stage/'cases'/case['predecessor']
        assert read(previous/'terminal.json')['returncode'] == 0
        assert read(previous/'report.json')['status'] == 'computed'
    folder.mkdir(parents=True)
    began = time.monotonic();stamp = now();timed_out = False
    with (folder/'stdout.log').open('w') as stdout, (folder/'stderr.log').open('w') as stderr:
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'run',
            '--stage', str(stage), '--case', case['name']], cwd=ROOT, env={**os.environ, **THREADS},
            stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            code = child.wait(timeout=plan['limits']['supervisor_seconds'])
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(child.pid, signal.SIGKILL)
            code = child.wait()
    receipt = dict(name=case['name'], started_utc=stamp, finished_utc=now(),
        seconds=time.monotonic()-began, returncode=code, supervisor_timeout=timed_out,
        reaped=child.poll() is not None, primary_votes_added=0)
    write(folder/'terminal.json', receipt)
    print(json.dumps(receipt), flush=True)
    if (folder/'report.json').exists():
        r = read(folder/'report.json')
        print(json.dumps({k:r[k] for k in ('status','solve_seconds','values','error') if k in r}), flush=True)
    return code


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('prepare','launch','run'))
    p.add_argument('--stage', type=Path, required=True)
    p.add_argument('--index', type=int, default=0)
    p.add_argument('--case')
    a = p.parse_args();stage = a.stage.resolve()
    if a.action == 'prepare':prepare(stage)
    elif a.action == 'run':run(stage, a.case)
    else:raise SystemExit(launch(stage, a.index))
