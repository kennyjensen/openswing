"""Refine explicitly bracketed reconstruction modes; never fit a reference speed."""
import argparse
import hashlib
import json
import platform
import runpy
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import scipy

STUDY = runpy.run_path(str(ROOT/'scripts/study-durrant-flutter.py'))
MATCH = runpy.run_path(str(ROOT/'scripts/analyze-durrant-flutter.py'))


def root(pair):
    return complex(*pair)


def matched(case, candidate, selected):
    result = MATCH['match'](case, candidate)
    pair = min(result['pairs'], key=lambda p: abs(root(p['before'])-selected))
    if abs(root(pair['before'])-selected) > 1e-9*max(1., abs(selected)) or not pair['resolved']:
        raise ValueError('The selected oscillatory mode cannot be uniquely matched.')
    value = root(pair['after'])
    # Check that the selected root is found by the independent shifted search.
    alternatives = [root(m['eigenvalue_per_s']) for m in candidate['searches'][1]['modes']]
    if min(abs(r-value) for r in alternatives) > 1e-7*max(1., abs(value)):
        raise ValueError('Selected boundary root is missing from the second search.')
    return value, pair


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cache-run', action='append', type=Path, default=[])
    args = parser.parse_args()
    assert not args.output.exists(), 'Use a fresh output directory.'
    args.output.mkdir(parents=True)
    plan = json.loads(args.plan.read_text())
    sources = STUDY['fingerprints']()
    record = dict(started=time.time(), plan=plan, source_sha256=sources,
        plan_sha256=hashlib.sha256(args.plan.read_bytes()).hexdigest(),
        versions=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__),
        cases=[], boundaries=[], cache_inputs=[])
    cache = []
    for directory in args.cache_run:
        raw = (directory/'run.json').read_bytes()
        manifest = json.loads(raw)
        for file, digest in manifest['source_sha256'].items():
            if file.startswith('openswing/') or file.startswith('docs/validation/'):
                assert sources[file] == digest, 'Cache model/kernel changed: '+file
        record['cache_inputs'].append(dict(directory=str(directory), observed_manifest=manifest,
            observed_manifest_sha256=hashlib.sha256(raw).hexdigest()))
        for entry in manifest['cases']:
            p = directory/entry['file']
            assert hashlib.sha256(p.read_bytes()).hexdigest() == entry['sha256']
            case = json.loads(p.read_text())
            if case['status'] == 'computed':
                cache.append((case, dict(path=str(p), sha256=entry['sha256'])))

    def save():
        p = args.output/'run.json'
        tmp = p.with_suffix('.part')
        tmp.write_text(json.dumps(record, indent=2, allow_nan=False)+'\n')
        tmp.replace(p)

    def evaluate(spec):
        assert STUDY['fingerprints']() == sources
        # Reuse only the exact model, physical controls, mesh, tangent and
        # two shifts. Cache records from incomplete jobs remain explicitly
        # observed terminal case records, not complete-run evidence.
        source, _, condition, panels, gravity, scale = STUDY['setup'](spec)
        wanted = MATCH['model_spec']({'spec': spec})
        found = None
        for candidate, provenance in cache:
            if MATCH['model_spec'](candidate) != wanted:
                continue
            if [s['shift'] for s in candidate['searches']] != spec['shifts']:
                continue
            assert candidate['source'] == source
            assert candidate['condition'] == json.loads(json.dumps(vars(condition)))
            assert candidate['panels'] == panels and candidate['gravity'] == gravity and scale == 1.
            found = dict(candidate, reused_from=provenance)
            break
        result = found if found is not None else STUDY['compute'](spec)
        assert STUDY['fingerprints']() == sources
        index = len(record['cases'])
        name = f'case-{index:03d}.json'
        raw = (json.dumps(result, indent=2, allow_nan=False)+'\n').encode()
        (args.output/name).write_bytes(raw)
        record['cases'].append(dict(file=name, status=result['status'], sha256=hashlib.sha256(raw).hexdigest()))
        save()
        return result, name

    save()
    for item in plan['boundaries']:
        boundary = dict(specification=item, status='running', trials=[])
        record['boundaries'].append(boundary)
        save()
        try:
            base = dict(wing=item['wing'], panels=item['panels'], incidence_deg=4.17,
                        shifts=[[-.1, 100.], [-.3, 200.]])
            lo, hi = item['bracket_m_s']
            left, left_file = evaluate(dict(base, speed_m_s=lo))
            right, right_file = evaluate(dict(base, speed_m_s=hi))
            pairs = [p for p in MATCH['match'](left, right)['pairs']
                     if p['resolved'] and p['before'][0]*p['after'][0] < 0]
            if not pairs:
                raise ValueError('No uniquely matched sign bracket at the requested endpoints.')
            selected = min(pairs, key=lambda p: abs((p['before'][1]+p['after'][1])/2-item['seed_imag_per_s']))
            fl, fh = root(selected['before']), root(selected['after'])
            boundary['initial_match'] = selected
            boundary['initial_files'] = [left_file, right_file]
            for iteration in range(24):
                width = 1e-4*max(abs(lo), abs(hi))
                choose_left = abs(fl.real) < abs(fh.real)
                best, value, best_file = (fl, lo, left_file) if choose_left else (fh, hi, right_file)
                small_growth = abs(best.real) <= 1e-6*max(abs(best), 1.)
                boundary.update(bracket_m_s=[lo, hi], endpoint_roots_per_s=[[fl.real, fl.imag], [fh.real, fh.imag]],
                    best_speed_m_s=value, best_root_per_s=[best.real, best.imag], best_file=best_file,
                    parameter_tolerance_m_s=width, normalized_growth=float(abs(best.real)/max(abs(best), 1.)))
                if hi-lo <= width and small_growth:
                    boundary['status'] = 'resolved'
                    break
                slope = (fh.real-fl.real)/(hi-lo)
                # Once a computed root is sufficiently neutral, explicitly
                # probe its other side within the desired bracket width.
                # This still requires opposite signs at computed endpoints.
                if small_growth:
                    trial = value-np.sign(best.real/slope)*.75*width
                else:
                    trial = lo-fl.real/slope
                    trial = float(np.clip(trial, lo+.05*(hi-lo), hi-.05*(hi-lo)))
                if not lo < trial < hi:
                    trial = (lo+hi)/2
                candidate, candidate_file = evaluate(dict(base, speed_m_s=float(trial)))
                f0, p0 = matched(left, candidate, fl)
                f1, p1 = matched(right, candidate, fh)
                if abs(f0-f1) > 1e-9*max(1., abs(f0)):
                    raise ValueError('The two endpoint modes match different trial modes.')
                boundary['trials'].append(dict(file=candidate_file, speed_m_s=float(trial),
                    root_per_s=[f0.real, f0.imag], left_match=p0, right_match=p1))
                if f0.real == 0:
                    # Preserve an actual signed endpoint on one side of an
                    # exactly neutral result; a later probe must bracket it.
                    if hi-trial < trial-lo:
                        lo, left, fl, left_file = trial, candidate, f0, candidate_file
                    else:
                        hi, right, fh, right_file = trial, candidate, f0, candidate_file
                elif np.sign(f0.real) == np.sign(fl.real):
                    lo, left, fl, left_file = trial, candidate, f0, candidate_file
                else:
                    hi, right, fh, right_file = trial, candidate, f0, candidate_file
                save()
            else:
                raise ValueError('Both speed and normalized-growth convergence were not attained.')
            print('Resolved', item, boundary['best_speed_m_s'], boundary['best_root_per_s'], flush=True)
        except Exception as exc:
            boundary.update(status='unresolved', error=repr(exc), traceback=traceback.format_exc())
            print(boundary['traceback'], flush=True)
        save()
    record['ended'] = time.time()
    record['status'] = 'computed' if all(b['status'] == 'resolved' for b in record['boundaries']) else 'contains unresolved boundaries'
    record['scope'] = 'Locally matched and refined oscillatory boundaries of a reconstructed model. No complete-spectrum stability, exact original ASWING setup or experimental-validation claim.'
    save()
    raise SystemExit(0 if record['status'] == 'computed' else 1)


if __name__ == '__main__':
    main()
