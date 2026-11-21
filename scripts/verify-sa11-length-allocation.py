"""Test SA-11 mesh allocation independently of geometry or force-law changes.

One foreground invocation runs one predeclared case. Counts derive only from
material lengths, never from native-output agreement. This is a diagnostic,
not a claim about original ASWING defaults or a primary comparison scope.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location(
    'practical', ROOT / 'scripts/verify-sa11-practical-resolution.py')
practical = importlib.util.module_from_spec(spec)
spec.loader.exec_module(practical)
from openswing.arc_length import material_arc

sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_text())


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def check(plan):
    for name, digest in plan['pins'].items():
        assert sha(ROOT / name) == digest, name


def prepare(out):
    assert not out.exists(), out
    model = practical.INC.model_at(-4.)
    lengths = {b.index: material_arc(b).total for b in model.beams}
    cases = []
    for n in (64, 128, 256):
        counts = {str(b): max(4, math.ceil(n * length / lengths[1]))
                  for b, length in lengths.items()}
        assert counts['1'] == n
        settings = dict(default=n, beams={b: dict(count=k, spacing='cosine')
                                         for b, k in counts.items()})
        for frozen in (True, False):
            cases.append(dict(id=f'n{n}-' + ('frozen' if frozen else 'current'),
                              main_intervals=n, counts=counts, intervals=settings,
                              frozen=frozen, modes=0, representation='pointwise'))
    files = list((ROOT / 'openswing').glob('*.py'))
    files += [Path(__file__), ROOT / 'scripts/verify-sa11-practical-resolution.py',
              ROOT / 'scripts/verify-sa11-winglet-incidence.py',
              ROOT / 'scripts/audit-sa11-avl-conversion.py',
              ROOT / 'scripts/verify-avl-matched-fields.py',
              practical.INC.SOURCE,
              ROOT / 'examples/isae-sa11-winglet-sources.json',
              ROOT / 'reference/aswing_doc.txt', ROOT / 'reference/aswing_faq.txt',
              ROOT / 'reference/fbhale/SetNodes.m', ROOT / 'reference/fbhale/manifest.json',
              ROOT / 'reference/aswing-authoritative-20261108/drela-aswing-steady.pdf',
              ROOT / 'reference/aswing-authoritative-20261108/isae-part-1-aerodynamics.pdf',
              ROOT / 'reference/aswing-authoritative-20261108/aswing-extended-user-manual.pdf',
              ROOT / 'docs/validation/ISAE_STATUS.md', ROOT / 'docs/validation/isae-progress-scopes.json',
              ROOT / 'docs/validation/isae-progress/history.json']
    files += list((practical.INC.FOLDER / 'Aswing_Simulations/Wing_tip_up').glob('*'))
    pins = {str(p.relative_to(ROOT)): sha(p) for p in files if p.is_file()}
    # Preserve and authenticate the previous complete primary refresh.
    previous = ROOT / 'artifacts/isae/sa11-complete-scope-20261108/analysis.json'
    for name, digest in read(previous)['source_sha256'].items():
        assert sha(ROOT / name) == digest, name
    pins[str(previous.relative_to(ROOT))] = sha(previous)
    plan = dict(observed_utc=datetime.now(timezone.utc).isoformat(), cases=cases,
                beam_material_lengths=lengths, pins=pins,
                previous_turn='progress: all sixteen original polars registered and refreshed; current163/9184 scope verified and timestamped',
                allocation='n_b=max(4,ceil(n_main*L_b/L_main)); current whole-beam cosine nodes, mandatory stations and Glauert receivers unchanged',
                setup='Previously disclosed bundled Joint correction and report-minus4 twist; alpha1, speed240, density1.2256, dynamicPG. Stall and local Mach guard unchanged. Frozen/current influence pairs.',
                source_scope='The manuals expose per-beam NODE controls but do not establish this allocation or original SA11 counts. FBHALE SetNodes explicitly selects a configured count per beam, not a native allocation default. No inferred historical setting.',
                interpretation='Three predetermined refinements test the uniform-per-beam allocation hypothesis. All outcomes retained; no selecting a mesh by reference error, repairing primary inputs, or adding primary passes.',
                production_equations_changed=False, primary_scope_changed=False)
    out.mkdir(parents=True)
    check(plan)
    write(out / 'plan.json', plan)
    (out / 'driver-used.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(dict(lengths=lengths, cases=cases)), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--prepare', action='store_true')
    group.add_argument('--case', type=int)
    args = parser.parse_args()
    assert all(os.environ.get(k) == '1' for k in
               ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'))
    out = args.output.resolve()
    if args.prepare:
        prepare(out)
        return
    plan = read(out / 'plan.json')
    check(plan)
    case = plan['cases'][args.case]
    def expired(*unused):
        raise TimeoutError('SA11 diagnostic exceeded30-second foreground limit')
    signal.signal(signal.SIGALRM, expired)
    signal.alarm(30)
    try:
        practical.run(out, case)
    finally:
        signal.alarm(0)
    check(plan)


if __name__ == '__main__':
    main()
