"""Published MIT flying-wing comparison, retaining numerical discrepancies.

First fetch references and run extract-fw-reference.py. Optional --panels accepts
8, 16 and/or 32 to populate independent source-keyed caches; rerun without options
to collect all cases. The published aircraft/PDF are not redistributed here.
"""
import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import scipy
from openswing.aero import FlightCondition
from openswing.asw import parse_asw
from openswing.linear_dynamics import make_system, linearize, eigensystem, complex_data
from openswing.operating import OperatingConstraint

PLAN = {8: [64], 16: [38, 62, 64, 66, 70], 32: [62, 64, 66]}
CONSTRAINTS = [OperatingConstraint('alpha', 'force.z'),
               OperatingConstraint('attitude.elevation', 'force.x'),
               OperatingConstraint('control.2', 'moment.y')]


def case(source, reference, panels, step=1e-5):
    start = time.monotonic()
    condition = FlightCondition(speed=reference['speed_ft_s'], alpha=reference['alpha_deg'],
        controls={2: reference['control_2_deg']}, attitude=[0, reference['elevation_deg'], 0])
    system, _ = make_system(parse_asw(source), condition, panels, frame='free',
                            operating_constraints=CONSTRAINTS)
    base = system.base_report()
    a, m = linearize(system, step=step)
    def search(shift):
        modes, meta = eigensystem(a, m, time_scale=system.W, count=4,
                                  shift=shift, method='full_shift_invert')
        found = [mode for mode in modes if mode['eigenvalue'][0] > -3 and 15 < mode['eigenvalue'][1] < 24]
        assert len(found) == 1, 'Published BFF branch is not uniquely located in the specified window.'
        assert max(max(mode['right_backward_error'], mode['left_backward_error']) for mode in modes) < 1e-9
        return modes, meta, found[0]['eigenvalue']
    modes, meta, bff = search((-.1, 18.))
    _, _, repeat = search((-.3, 16.))
    shift_difference = float(np.linalg.norm(np.array(bff)-repeat))
    assert shift_difference < 1e-6
    values = base['operating_values']
    trim = dict(alpha_deg=values['alpha'], elevation_deg=values['attitude.elevation'],
                control_2_deg=values['control.2'], CL=base['CL'], CD=base['CD'], efficiency=base['efficiency'])
    error = {key: trim[key]-reference[key] for key in trim}
    bff_error = (np.array(bff)-reference['bff_root_per_s']).tolist()
    for mode in modes:
        for key in ('right', 'left'):
            mode[key] = complex_data(mode[key])
    record = dict(requested_panels=panels, actual_lifting_panels=base['lifting_panels'],
        structural_nodes=base['structural_nodes'], speed_ft_s=reference['speed_ft_s'], difference_step=step,
        time_scale=system.W, reference_point=reference['point'], trim=trim, trim_difference=error,
        bff_root_per_s=bff, bff_difference_per_s=bff_error, nearby_shift_difference_per_s=shift_difference,
        base=base, modes=modes, diagnostics=meta, elapsed_seconds=time.monotonic()-start)
    print(f"{panels} requested / {base['lifting_panels']} actual panels, V={condition.speed:g}: "
          f"lambda={bff[0]:+.6f}+{bff[1]:.6f}i /s; {record['elapsed_seconds']:.1f}s", flush=True)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--panels', nargs='+', type=int, choices=PLAN, default=list(PLAN))
    args = parser.parse_args()
    reference_path = ROOT/'docs/validation/fw-reference.json'
    reference = json.loads(reference_path.read_text())
    source_bytes = (ROOT/'.reference/fw.asw').read_bytes()
    assert hashlib.sha256(source_bytes).hexdigest() == reference['aircraft']['sha256']
    files = [Path(__file__), reference_path, *sorted((ROOT/'openswing').glob('*.py'))]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    provenance = dict(source_sha256=hashes, versions=dict(python=platform.python_version(),
                       numpy=np.__version__, scipy=scipy.__version__))
    key = hashlib.sha256(json.dumps(provenance, sort_keys=True).encode()).hexdigest()
    cache = ROOT/'.reference/flying-wing'/key
    cache.mkdir(parents=True, exist_ok=True)
    points = {p['speed_ft_s']: p for p in reference['points']}
    for panels in args.panels:
        for speed in PLAN[panels]:
            path = cache/f'{panels}-{speed}.json'
            if not path.exists():
                result = case(source_bytes.decode(), points[speed], panels)
                path.write_text(json.dumps(result, allow_nan=False)+'\n')
            else:
                print(f'Resumed {panels} panels, {speed} ft/s', flush=True)
    # One extra differentiation step distinguishes spatial error from tangent
    # error at the central comparison point. Stored separately for resumability.
    if 16 in args.panels:
        refined = cache/'16-64-refined.json'
        if not refined.exists():
            refined.write_text(json.dumps(case(source_bytes.decode(), points[64], 16, 3e-6), allow_nan=False)+'\n')
    paths = [cache/f'{n}-{v}.json' for n, speeds in PLAN.items() for v in speeds]
    paths.append(cache/'16-64-refined.json')
    if not all(p.exists() for p in paths):
        print('Partial cache saved; run remaining panel selections to assemble the study.', flush=True)
        return
    cases = [json.loads(p.read_text()) for p in paths]
    central = next(c for c in cases if c['requested_panels'] == 16 and c['speed_ft_s'] == 64 and c['difference_step'] == 1e-5)
    step_difference = float(np.linalg.norm(np.array(central['bff_root_per_s'])-cases[-1]['bff_root_per_s']))
    assert step_difference < 1e-5
    brackets = []
    for n in (16, 32):
        pairs = sorted((c for c in cases if c['requested_panels'] == n and c['difference_step'] == 1e-5), key=lambda c: c['speed_ft_s'])
        for lo, hi in zip(pairs, pairs[1:]):
            growth0, growth1 = lo['bff_root_per_s'][0], hi['bff_root_per_s'][0]
            if growth0 < 0 < growth1:
                brackets.append(dict(requested_panels=n, speed_bracket_ft_s=[lo['speed_ft_s'], hi['speed_ft_s']],
                    linearly_interpolated_zero_ft_s=lo['speed_ft_s']-growth0*(hi['speed_ft_s']-lo['speed_ft_s'])/(growth1-growth0)))
    output = dict(description='Comparison against published ASWING flying-wing trim/root-map facts; unresolved differences are retained, not fitted.',
        **provenance, reference=reference, assumptions=dict(
            trim='Steady straight unpowered glide; Fx=Fz=My=0 with alpha, elevation and F2 unknown.',
            frame='Free flight with six zero net-load targets; root mount remains relative to aircraft frame.',
            atmosphere='File density, sound speed and gravity at altitude zero; ambient Mach, stall enabled, no ground images.',
            discretization='OpenSwing pointwise circulation and objective SO(3) mixed beam; actual panels include required property breaks.',
            modal_search='Four local Arnoldi roots per shift; exact coordinate-integrator deflation; total finite dimension unclassified.',
            branch='Unique returned root with sigma > -3/s and 15 < omega < 24 rad/s; cross-checked at two nearby shifts.'),
        interpretation='Partial published comparison, not ASWING executable/discrete parity or experimental validation. Flutter values remain subject to mesh and setup uncertainty.',
        differentiation_step_difference_per_s=step_difference, sampled_flutter_brackets=brackets, cases=cases)
    target = ROOT/'docs/validation/flying-wing.json'
    target.write_text(json.dumps(output, indent=2, allow_nan=False)+'\n')
    print(f'Wrote {target.relative_to(ROOT)}; step difference {step_difference:.3g}/s', flush=True)


if __name__ == '__main__':
    main()
