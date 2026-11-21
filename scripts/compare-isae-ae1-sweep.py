"""All finite published AE-1 speed coordinates, with unchanged pilot physics.

Reuse the eight frozen pilot states; compute the remaining 178 once. Save full
raw states compressed, retain failed requests, and never infer stability from
equilibrium convergence. The source experimental zeros remain missing.
"""
from pathlib import Path
import argparse
import copy
import gzip
import hashlib
import importlib.util
import json
import signal
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
from isae_ae1 import datasets

module_spec = importlib.util.spec_from_file_location('ae1_pilot', ROOT/'scripts/compare-isae-ae1.py')
PILOT = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(PILOT)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')
    temporary.replace(path)


def raw_write(path, value):
    data = json.dumps(value, separators=(',', ':'), allow_nan=False).encode()
    packed = gzip.compress(data, compresslevel=6, mtime=0)
    path.write_bytes(packed)
    return dict(file=path.name, bytes=len(packed), sha256=hashlib.sha256(packed).hexdigest(),
                uncompressed_bytes=len(data), uncompressed_sha256=hashlib.sha256(data).hexdigest())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), 'Inspect existing run before requesting a new run; automatic overwrite/retry is disabled.'
    pilot_path = ROOT/'docs/validation/isae-ae1-pilot.json'
    pilot = json.loads(pilot_path.read_text())
    for name, digest in pilot['plan']['source_sha256'].items():
        assert sha(ROOT/name) == digest, 'Pilot dependency changed: '+name
    tables = datasets()
    coordinates = sorted({(d['alpha_deg'], row[0]) for d in tables if d['reference']=='experiment'
                          for row in d['values'] if row[1] is not None})
    assert len(coordinates) == 92
    specifications = [dict(refinement=r, intervals_per_half=15*r, alpha_deg=a, speed_m_s=v)
                      for r in (2, 4) for a, v in [(0., 0.)]+coordinates]
    pins = dict(pilot['plan']['source_sha256'])
    pins[str(pilot_path.relative_to(ROOT))] = sha(pilot_path)
    pins[str(Path(__file__).relative_to(ROOT))] = sha(Path(__file__))
    for table in tables:
        path = Path(table['source_pin']['path'])
        assert sha(path) == table['source_pin']['sha256']
        pins[str(path.relative_to(ROOT))] = sha(path)
    plan = dict(schema='openswing-isae-ae1-sweep-v1', specifications=specifications,
                source_sha256=pins, pilot_identity=pilot['plan']['identity'],
                fixtures=pilot['plan']['fixtures'], conditions=pilot['plan']['conditions'],
                wall=pilot['plan']['wall'], path=pilot['plan']['path'], gates=pilot['plan']['gates'],
                displacement_convention=pilot['plan']['displacement_convention'],
                branch_limit=pilot['plan']['branch_limit'], experimental_acceptance_threshold=None,
                unique_measured_coordinates=92, unique_measured_values=184,
                requested_states=186, reused_pilot_states=8, requested_new_states=178,
                per_new_state_alarm_seconds=120, batch_seconds_limit=1800,
                failure_policy='Retain failed requests and continue to the next independent cold case; no retries. Stop when batch budget expires.',
                static_scope='All finite exported speed coordinates; high-speed measurements can be oscillatory. No stability calculation is performed.',
                source_tables=tables)
    identity = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    plan['identity'] = identity
    args.output.mkdir(parents=True)
    (args.output/'cases').mkdir()
    write(args.output/'plan.json', plan)
    lookup = {(r['specification']['refinement'], r['specification']['alpha_deg'], r['specification']['speed_m_s']):r
              for r in pilot['states']}
    started = time.monotonic()
    rows = []

    def timed_out(signum, frame):
        raise TimeoutError('Per-state alarm expired; no automatic retry.')

    signal.signal(signal.SIGALRM, timed_out)

    def checkpoint():
        counts = {status:sum(row['status']==status for row in rows) for status in ('computed', 'failed', 'unrun')}
        value = dict(identity=identity, status='running', requested=186, **counts,
                     recorded=len(rows), reused=sum(row['origin']['kind']=='reused_pilot' for row in rows),
                     new_attempted=sum(row['origin']['kind']=='new' and row['status']!='unrun' for row in rows),
                     seconds=time.monotonic()-started, states=rows)
        write(args.output/'manifest.json', value)
        return value

    try:
        for index, specification in enumerate(specifications):
            key = (specification['refinement'], specification['alpha_deg'], specification['speed_m_s'])
            began = time.monotonic()
            if key in lookup:
                # Keep the original scientific row byte-for-byte in content,
                # including its original identity and timing. Provenance is
                # carried by the manifest, not by rewriting the cached result.
                raw = copy.deepcopy(lookup[key])
                origin = dict(kind='reused_pilot', identity=pilot['plan']['identity'], source_sha256=sha(pilot_path))
            elif began-started >= plan['batch_seconds_limit']:
                raw = dict(status='unrun', specification=specification, reason='Batch budget exhausted before this request.')
                origin = dict(kind='new')
            else:
                origin = dict(kind='new')
                print(json.dumps(dict(starting=index+1, total=186, specification=specification)), flush=True)
                remaining = plan['batch_seconds_limit']-(began-started)
                signal.alarm(max(1, int(min(plan['per_new_state_alarm_seconds'], remaining))))
                try:
                    raw = PILOT.compute(specification)
                except Exception as exc:
                    raw = dict(status='failed', specification=specification,
                               seconds=time.monotonic()-began, error=type(exc).__name__+': '+str(exc),
                               traceback=traceback.format_exc())
                finally:
                    signal.alarm(0)
                raw['identity'] = identity
            entry = dict(index=index, specification=specification, origin=origin, status=raw['status'],
                         raw=raw_write(args.output/'cases'/f'{index:03d}.json.gz', raw))
            for key in ('observable', 'checks', 'counts', 'seconds', 'error', 'reason'):
                if key in raw:entry[key] = raw[key]
            if raw['status']=='computed' and specification['speed_m_s']:
                strips = [s for s in raw['result']['strips'] if s['lifting']]
                entry['aero_diagnostics'] = dict(min_cl=min(s['cl'] for s in strips),
                    max_cl=max(s['cl'] for s in strips), stalled_strips=sum(bool(s['stalled']) for s in strips))
            rows.append(entry)
            current = checkpoint()
            print(json.dumps(dict(recorded=len(rows), computed=current['computed'], failed=current['failed'],
                                  reused=current['reused'], status=entry['status'],
                                  seconds=entry.get('seconds'), specification=specification)), flush=True)
        assert all(sha(ROOT/name)==digest for name, digest in pins.items()), 'Frozen source changed during run'
    finally:
        signal.alarm(0)
        final = checkpoint()
        final['status'] = ('completed' if len(rows)==186 and final['computed']==186 else
                           'completed_with_failures' if len(rows)==186 and not final['unrun'] else 'incomplete')
        write(args.output/'manifest.json', final)
    if final['status']=='incomplete':
        raise SystemExit(2)


if __name__ == '__main__':
    main()
