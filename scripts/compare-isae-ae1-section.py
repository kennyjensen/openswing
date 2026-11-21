"""Six cold AE-1 solves changing only the constant section slope to 2*pi.

This is a diagnostic, not a fitted model or primary VLM reproduction. The
unchanged pilot solve routine receives an explicitly different input fixture;
no kernel, ground guard, tolerance, or saved baseline is patched.
"""
from pathlib import Path
import argparse
import gzip
import hashlib
import importlib.util
import json
import math
import signal
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
from isae_ae1 import configuration

loader = importlib.util.spec_from_file_location('ae1_pilot_driver', ROOT/'scripts/compare-isae-ae1.py')
PILOT = importlib.util.module_from_spec(loader)
loader.loader.exec_module(PILOT)
BASE_SLOPE = 6.1185
SLOPE = 2*math.pi


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    tmp = path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')
    tmp.replace(path)


def variant_configuration(refinement):
    original, data, panels = configuration(refinement)
    lines = original.splitlines()
    header = 't dCLda CLmax CLmin alpha Cm Cdf Cdp'
    assert lines.count(header) == 1
    index = lines.index(header)
    for i in (index+1, index+2):
        tokens = lines[i].split()
        assert len(tokens) == 8 and float(tokens[1]) == BASE_SLOPE
        tokens[1] = format(SLOPE, '.17g')
        lines[i] = ' '.join(tokens)
    assert lines[index+3] == 'End'
    text = '\n'.join(lines)+'\n'
    # Token comparison verifies the entire fixture, including masses and
    # section jumps. Exactly two scalar tokens differ.
    before, after = original.split(), text.split()
    assert len(before) == len(after)
    differences = [(a, b) for a, b in zip(before, after) if a != b]
    assert len(differences) == 2
    assert all(float(a) == BASE_SLOPE and float(b) == SLOPE for a, b in differences)
    return text, data, panels


def raw_write(path, value):
    raw = json.dumps(value, separators=(',', ':'), allow_nan=False).encode()
    packed = gzip.compress(raw, compresslevel=6, mtime=0)
    path.write_bytes(packed)
    return dict(file=path.name, bytes=len(packed), sha256=hashlib.sha256(packed).hexdigest(),
                uncompressed_bytes=len(raw), uncompressed_sha256=hashlib.sha256(raw).hexdigest())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-review', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), 'Do not overwrite or automatically repeat an existing diagnostic.'
    baseline_path = ROOT/'docs/validation/isae-ae1-sweep.json'
    baseline = json.loads(baseline_path.read_text())
    pilot_saved = json.loads((ROOT/'docs/validation/isae-ae1-pilot.json').read_text())
    assert baseline['execution']['status'] == 'completed'
    pins = dict(baseline['plan']['source_sha256'])
    pins[str(baseline_path.relative_to(ROOT))] = sha(baseline_path)
    pins[str(Path(__file__).relative_to(ROOT))] = sha(Path(__file__))
    for name, digest in pins.items():
        assert sha(ROOT/name) == digest, 'Changed frozen dependency: '+name
    specifications = [dict(refinement=r, intervals_per_half=15*r, alpha_deg=a, speed_m_s=u)
                      for r in (2, 4) for a, u in ((5., 30.), (5., 40.), (7., 30.))]
    fixtures = []
    for r in (2, 4):
        original, _, panels = configuration(r)
        candidate, _, candidate_panels = variant_configuration(r)
        assert panels == candidate_panels
        original_fixture = next(f for f in baseline['plan']['fixtures'] if f['refinement']==r)
        assert hashlib.sha256(original.encode()).hexdigest() == original_fixture['source_sha256']
        reference_state = next(s for s in pilot_saved['states'] if s['specification']==dict(
            refinement=r, intervals_per_half=15*r, alpha_deg=5., speed_m_s=30.))
        assert reference_state['panels'] == panels
        samples = [s['t'] for s in reference_state['result']['strips'] if s['lifting']]
        samples += [panels['beams']['1']['nodes'][0], panels['beams']['1']['nodes'][-1]]
        old_model, new_model = map(PILOT.parse_asw, (original, candidate))
        assert len(old_model.beams) == len(new_model.beams) == 1
        assert old_model.records.keys() == new_model.records.keys()
        for name in old_model.records:
            old_rows, new_rows = old_model.records[name], new_model.records[name]
            assert len(old_rows) == len(new_rows)
            assert all(PILOT.np.array_equal(a,b) for a,b in zip(old_rows,new_rows)), name
        assert PILOT.np.array_equal(old_model.constants, new_model.constants)
        assert all(PILOT.np.array_equal(a,b) for a,b in zip(old_model.reference,new_model.reference))
        old_beam, new_beam = old_model.beams[0], new_model.beams[0]
        assert old_beam.distributions.keys() == new_beam.distributions.keys()
        for side in ('left','right'):
            for derivative in range(4):
                for field in old_beam.distributions:
                    before = old_beam.value(field, samples, side=side, derivative=derivative)
                    after = new_beam.value(field, samples, side=side, derivative=derivative)
                    if field=='dCLda' and derivative==0:
                        assert PILOT.np.all(before==BASE_SLOPE) and PILOT.np.all(after==SLOPE)
                    else:
                        assert PILOT.np.array_equal(before,after), (field,side,derivative)
                        if field=='dCLda':assert PILOT.np.all(after==0.)
        fixtures.append(dict(refinement=r, baseline_source_sha256=original_fixture['source_sha256'],
            source_sha256=hashlib.sha256(candidate.encode()).hexdigest(), source=candidate, panels=panels,
            actual_semispan_m=original_fixture['actual_semispan_m'], nominal_semispan_m=.55,
            parsed_preflight=dict(receiver_and_endpoint_samples=len(samples),
                fields=len(old_beam.distributions), derivative_orders=[0,1,2,3], sides=['left','right'],
                all_other_records_and_distributions_unchanged=True)))
    review_bytes = args.source_review.read_bytes()
    review_sha256 = hashlib.sha256(review_bytes).hexdigest()
    plan = dict(schema='openswing-isae-ae1-section-v1', specifications=specifications,
        source_sha256=pins, baseline_identity=baseline['execution']['identity'],
        fixtures=fixtures, conditions=baseline['plan']['conditions'], gates=baseline['plan']['gates'],
        candidate=dict(field='dCLda', baseline=BASE_SLOPE, value=SLOPE,
                       relative_change=SLOPE/BASE_SLOPE-1, changed_table_tokens=2),
        unchanged='All other input tokens, meshes, flight conditions, stall controls and numerical settings.',
        solve_path='Unchanged pilot.compute routine with validation-driver-local fixture provider injection; kernel and adapter files unchanged.',
        path=baseline['plan']['path'], experimental_acceptance_threshold=None, stability_computed=False,
        source_review=json.loads(review_bytes), source_review_sha256=review_sha256,
        requested_new_states=6, requested_baseline_reuse=8,
        per_state_seconds_limit=120, batch_seconds_limit=600,
        failure_policy='Retain each failed or unrun request, continue independent cold cases within budget, no retries.',
        scope='Isolated source-defined section-slope diagnostic; neither primary VLM parity nor a new calibrated experimental model.')
    plan['identity'] = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    args.output.mkdir(parents=True)
    (args.output/'cases').mkdir()
    write(args.output/'plan.json', plan)
    started = time.monotonic()
    rows = []
    final_provenance_verified = False
    fatal_error = None

    def timeout(signum, frame):
        raise TimeoutError('Fixed diagnostic state/batch limit reached; no automatic retry.')

    signal.signal(signal.SIGALRM, timeout)

    def checkpoint(status='running'):
        manifest = dict(identity=plan['identity'], status=status, requested=6, recorded=len(rows),
            computed=sum(r['status']=='computed' for r in rows),
            failed=sum(r['status']=='failed' for r in rows), unrun=sum(r['status']=='unrun' for r in rows),
            seconds=time.monotonic()-started, final_provenance_verified=final_provenance_verified,
            fatal_error=fatal_error, states=rows)
        write(args.output/'manifest.json', manifest)
        return manifest

    checkpoint()
    try:
        for i, spec in enumerate(specifications):
            began = time.monotonic()
            remaining = plan['batch_seconds_limit']-(began-started)
            if remaining <= 0:
                row = dict(status='unrun', specification=spec, reason='Batch budget exhausted.')
            else:
                print(json.dumps(dict(starting=i+1, total=6, specification=spec)), flush=True)
                signal.alarm(max(1, int(min(plan['per_state_seconds_limit'], remaining))))
                original_provider = PILOT.configuration
                try:
                    PILOT.configuration = variant_configuration
                    row = PILOT.compute(spec)
                    assert row['source'] == next(f['source'] for f in fixtures if f['refinement']==spec['refinement'])
                except Exception as exc:
                    row = dict(status='failed', specification=spec, seconds=time.monotonic()-began,
                               error=type(exc).__name__+': '+str(exc), traceback=traceback.format_exc())
                finally:
                    PILOT.configuration = original_provider
                    signal.alarm(0)
            row['identity'] = plan['identity']
            entry = dict(index=i, specification=spec, status=row['status'],
                         raw=raw_write(args.output/'cases'/f'{i:03d}.json.gz', row))
            for name in ('observable', 'checks', 'counts', 'seconds', 'error', 'reason'):
                if name in row:
                    entry[name] = row[name]
            if row['status']=='computed':
                strips = [s for s in row['result']['strips'] if s['lifting']]
                entry['aero_diagnostics'] = dict(min_cl=min(s['cl'] for s in strips),
                    max_cl=max(s['cl'] for s in strips), stalled_strips=sum(bool(s['stalled']) for s in strips))
            rows.append(entry)
            checkpoint()
            print(json.dumps(entry), flush=True)
        for name, digest in pins.items():
            assert sha(ROOT/name) == digest, 'Frozen dependency changed during diagnostic: '+name
        assert sha(args.source_review) == review_sha256, 'Source review changed during diagnostic.'
        final_provenance_verified = True
    except BaseException as exc:
        fatal_error = type(exc).__name__+': '+str(exc)
        raise
    finally:
        signal.alarm(0)
        status = ('completed' if final_provenance_verified and len(rows)==6 and all(r['status']=='computed' for r in rows)
                  else 'completed_with_failures' if final_provenance_verified and len(rows)==6 and not any(r['status']=='unrun' for r in rows)
                  else 'incomplete')
        checkpoint(status)
    if status != 'completed':
        raise SystemExit(2)


if __name__ == '__main__':
    main()
