"""Score authenticated saved SA-11 runs against the purpose of Figure 22.

Read-only numerical assessment: no OpenSwing/NumPy imports or physical solves.
Every configuration uses one declared setup. Missing targets stay required.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import resource
import signal
import statistics

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPEC = ROOT / 'docs/validation/sa11-paper-suite.json'


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    text = json.dumps(value, indent=2, allow_nan=False) + '\n'
    with Path(path).open('x') as stream:
        stream.write(text)


def bounded():
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    signal.alarm(25)


def interpolate(points, x, xkey, ykey, maximum_gap=.25):
    """Interpolate on the alpha-ordered valid branch, never across missing rows."""
    points = sorted(points, key=lambda p: p['alpha'])
    valid = [p for p in points if p['valid']]
    if any(not math.isfinite(p[xkey]) or not math.isfinite(p[ykey]) for p in valid):
        raise ValueError('Nonfinite accepted state')
    if any(b[xkey] <= a[xkey] for a, b in zip(valid, valid[1:])):
        return None, [], 'Nonmonotone branch requires an explicitly selected operating branch'
    for p in valid:
        if abs(p[xkey] - x) <= 1e-12:
            return p[ykey], [p['alpha']], None
    for a, b in zip(points, points[1:]):
        if not (a['valid'] and b['valid']):
            continue
        if a[xkey] < x < b[xkey]:
            if b['alpha'] - a['alpha'] > maximum_gap + 1e-12:
                return None, [a['alpha'], b['alpha']], 'Missing quarter-degree bracketing states'
            f = (x - a[xkey]) / (b[xkey] - a[xkey])
            return a[ykey] + f * (b[ykey] - a[ykey]), [a['alpha'], b['alpha']], None
    return None, [], 'No accepted bracket; extrapolation and rejected-state interpolation prohibited'


def decision(value, target, tolerance):
    if value is None:
        return 'unavailable', None
    if not math.isfinite(value) or not math.isfinite(target) or target == 0:
        raise ValueError('This nonzero-reference suite requires finite values')
    error = 100 * (value - target) / abs(target)
    return ('pass' if abs(error) <= 100 * tolerance else 'mismatch'), error


def build(spec_path):
    spec = read(spec_path)
    assert spec['version'] == 1 and spec['required_checks'] == 48
    pins = {}

    def pin(path, expected=None):
        path = Path(path)
        if not path.is_absolute():
            path = ROOT / path
        key = str(path.relative_to(ROOT))
        digest = pins.get(key) or sha(path)
        if expected is not None:
            assert digest == expected, str(path)
        pins[key] = digest
        return path

    pin(spec_path)
    pin(Path(__file__))
    catalog = read(pin('docs/validation/aswing-authoritative-sources.json'))
    paper = next(r for r in catalog['files'] if r['id'] == 'isae-part-1')
    pin(paper['local_pdf'], paper['sha256'])
    pin(paper['local_text'], paper['text_sha256'])
    paper_audit = read(pin(spec['paper_audit']))
    for path, digest in paper_audit['source_pins'].items():
        pin(path, digest)
    manifest = read(pin('reference/isae-validation/manifest.json'))
    cache = ROOT / 'reference/isae-validation' / manifest['revision']
    tables = {}

    def reference(path):
        path = Path(path)
        if not path.is_absolute():
            path = ROOT / path
        # Normalize the historical .reference alias without altering old evidence.
        path = path.resolve()
        entry = manifest['files'][str(path.relative_to(cache))]
        pin(path, entry['sha256'])
        if str(path) not in tables:
            content = path.read_bytes()
            assert hashlib.sha1(f'blob {len(content)}\0'.encode() + content).hexdigest() == entry['git_blob_sha1']
            tokens = [r.split() for r in content.decode().splitlines()
                      if len(r.split()) == 82 and r.split()[0].isdigit()]
            assert len(tokens) == 41
            tables[str(path)] = [dict(alpha=float(t[71]), CL=float(t[77]), CD=float(t[78]),
                                     speed=float(t[69]), valid=True, tokens=t) for t in tokens]
        return tables[str(path)]

    loaded = {}
    curves = []
    for configuration in spec['configurations']:
        folder = ROOT / configuration['source']
        if str(folder) not in loaded:
            plan = read(pin(folder / 'plan.json'))
            analysis = read(pin(folder / 'analysis.json'))
            verification = read(pin(folder / 'verification.json'))
            assert verification['analysis_sha256'] == sha(folder / 'analysis.json')
            assert analysis['plan_sha256'] == sha(folder / 'plan.json')
            # Authenticate current production source too; old pre-change snapshots
            # in the upper-winglet plan have explicit recorded replacements.
            for path, digest in plan.get('source_sha256', plan.get('pins', {})).items():
                change = plan.get('source_changes', {}).get(path)
                if change:
                    assert digest in (change['before'], change['after'])
                    pin(change['saved_before'], change['before'])
                    pin(path, change['after'])
                else:
                    pin(path, digest)
            for name, digest in plan.get('generated_pins', {}).items():
                pin(folder / name, digest)
            loaded[str(folder)] = plan, analysis
        plan, analysis = loaded[str(folder)]
        plan_digest = pins[str((folder / 'plan.json').relative_to(ROOT))]
        for label in spec['mach_labels']:
            points = []
            native = None
            if configuration['reader'] == 'original':
                for i, job in enumerate(plan['jobs']):
                    if not (job['variant'] == configuration['id'] and job['mach_label'] == label
                            and job['settings']['panels'] == configuration['nominal_intervals']):
                        continue
                    path = folder / 'jobs' / f'{i:04d}' / 'result.json'
                    pin(path, analysis['result_sha256'][str(path.relative_to(ROOT))])
                    row = read(path)
                    assert row['job_id'] == job['id'] and row['plan_sha256'] == plan_digest
                    native = reference(job['table_path'])
                    assert native[job['row_index']]['tokens'] == job['reference_row']['tokens']
                    assert job['settings']['freeze_influences'] == configuration['freeze_influences']
                    state = row['strict']
                    valid = state['status'] == 'computed'
                    if valid:
                        assert state['numerical_pass'] and all(c['passed'] for c in state['numerical_checks'])
                        raw = state['result']
                        assert raw['residual'] < 1e-8
                        values = raw['predicted']
                    else:
                        values = {}
                    points.append(dict(alpha=job['settings']['alpha'], valid=valid,
                        CL=values.get('CL'), CD=values.get('CD'),
                        status='computed' if valid else state['status'],
                        source=str(path.relative_to(ROOT))))
            else:
                for row in analysis['cases']:
                    case = row['case']
                    if case['label'] != label:
                        continue
                    path = folder / case['id'] / 'report.json'
                    pin(path, row['report_sha256'])
                    for name, digest in row['artifacts'].items():
                        pin(path.parent / name, digest)
                    native = reference(case['table'])
                    assert native[case['row']]['tokens'] == case['tokens']
                    assert case['condition']['freeze_influences'] == configuration['freeze_influences']
                    valid = row['status'] == 'COMPUTED_DIAGNOSTIC'
                    if valid:
                        raw = read(path.parent / 'accepted.json')
                        assert raw['converged'] and raw['residual'] < 1e-8
                        assert max(s['normal_mach'] for s in raw['strips']) < 1
                        assert all(raw[key] == row['values'][key] for key in ('CL', 'CD'))
                    points.append(dict(alpha=case['alpha'], valid=valid,
                        CL=row['values']['CL'] if valid else None,
                        CD=row['values']['CD'] if valid else None,
                        status='computed' if valid else 'rejected', source=str(path.relative_to(ROOT))))
            assert native and len({p['alpha'] for p in points}) == len(points)
            assert {r['speed'] for r in native} == {240. if label == '0_70' else 272.}
            curves.append(dict(configuration=configuration['id'], name=configuration['name'],
                label=label, setup=configuration['setup'], freeze_influences=configuration['freeze_influences'],
                points=sorted(points, key=lambda r: r['alpha']),
                reference=[{k:v for k,v in p.items() if k != 'tokens'} for p in native]))

    checks = []
    for curve in curves:
        for kind, xs, xkey, ykey in (
                ('lift', spec['alpha_degrees'], 'alpha', 'CL'),
                ('drag_at_equal_lift', spec['matched_CL'], 'CL', 'CD')):
            for x in xs:
                target, reference_bracket, why = interpolate(curve['reference'], x, xkey, ykey)
                assert why is None
                value, bracket, reason = interpolate(curve['points'], x, xkey, ykey,
                    spec['maximum_interpolation_gap_degrees'])
                status, error = decision(value, target, spec['relative_tolerance'])
                if kind == 'lift' and any(p['alpha'] == x and not p['valid'] for p in curve['points']):
                    status = 'rejected'
                # Existing paper/table audit sampled exactly these 48 ordinates.
                panel = {'lift': {'0_70':'a', '0_80':'b'}, 'drag_at_equal_lift': {'0_70':'c', '0_80':'d'}}[kind][curve['label']]
                figure_id = next(c['figure_id'] for c in spec['configurations'] if c['id'] == curve['configuration'])
                audited = next(c for c in paper_audit['comparisons']
                    if c['panel'] == panel and c['configuration'] == figure_id and c['x'] == x)
                allowance = (0.0064 if curve['label'] == '0_70' else 0.0075) if kind == 'drag_at_equal_lift' else 0.
                assert abs(target + allowance - audited['archive_postprocessed']) < 2e-12
                checks.append(dict(id=f"{curve['configuration']}:{curve['label']}:{kind}:{x}",
                    configuration=curve['configuration'], label=curve['label'], kind=kind, x=x,
                    target=target, actual=value, status=status, error_percent=error,
                    bracket_alpha=bracket, reference_bracket_alpha=reference_bracket, reason=reason))
    assert len(checks) == spec['required_checks'] and len({c['id'] for c in checks}) == len(checks)
    groups = []
    for config in spec['configurations']:
        rows = [c for c in checks if c['configuration'] == config['id']]
        errors = [abs(c['error_percent']) for c in rows if c['error_percent'] is not None]
        failed = [abs(c['error_percent']) for c in rows if c['status'] == 'mismatch']
        groups.append(dict(configuration=config['id'], name=config['name'], required=len(rows),
            counts=dict(Counter(c['status'] for c in rows)), maximum_error_percent=max(errors, default=None),
            failed_error_percent=dict(median=statistics.median(failed), maximum=max(failed)) if failed else None,
            fields={kind:dict(Counter(c['status'] for c in rows if c['kind'] == kind))
                    for kind in ('lift', 'drag_at_equal_lift')}))
    increments = []
    for c in checks:
        if c['kind'] != 'drag_at_equal_lift' or c['configuration'] == 'wing_alone':
            continue
        base = next(b for b in checks if b['configuration'] == 'wing_alone' and
                    b['kind'] == c['kind'] and b['label'] == c['label'] and b['x'] == c['x'])
        config = next(p for p in spec['configurations'] if p['id'] == c['configuration'])
        matched_setup = config['freeze_influences'] == spec['configurations'][0]['freeze_influences']
        actual = c['actual'] - base['actual'] if c['actual'] is not None and base['actual'] is not None else None
        increments.append(dict(configuration=c['configuration'], label=c['label'], CL=c['x'],
            target_delta_CD=c['target']-base['target'], actual_delta_CD=actual,
            matched_influence_convention=matched_setup,
            comparable_delta_CD=actual if matched_setup else None,
            reason=None if matched_setup and actual is not None else
                'Unify frozen/current influence convention before interpreting the paired winglet effect' if not matched_setup else
                'Missing accepted matched-lift bracket', counted_in_primary=False))
    return dict(observed_utc=datetime.now(timezone.utc).isoformat(), suite=spec['name'],
        required=len(checks), counts=dict(Counter(c['status'] for c in checks)), groups=groups,
        checks=checks, curves=curves, drag_increments=increments, pins=pins,
        physical_calls=0, historical_scope=dict(passed=1060, required=9184, unchanged=True),
        full_family_validated=False, protocol=spec)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', type=Path, default=DEFAULT_SPEC)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    bounded()
    assert not args.output.exists(), 'Use a new output directory; retain earlier observations'
    result = build(args.spec.resolve())
    args.output.mkdir(parents=True)
    write_new(args.output / 'analysis.json', result)
    print(json.dumps({k:result[k] for k in ('required','counts','groups','physical_calls')}, indent=2))
    signal.alarm(0)


if __name__ == '__main__':
    main()
