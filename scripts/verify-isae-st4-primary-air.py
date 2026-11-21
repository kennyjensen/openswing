"""Conditional primary ST-4 modes in explicitly specified still air.

Preserve the experimental reconstruction and store every solve, including
rejections. Density is an assumption, not a recovered laboratory condition.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import time

import numpy as np
from isae_st4_primary import configurations, parameters, source, provenance

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kernel', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--endpoint', choices=['lower', 'upper', 'both'], default='both')
    parser.add_argument('--density', type=float, required=True)
    args = parser.parse_args()
    if not np.isfinite(args.density) or args.density <= 0:
        parser.error('--density must be finite and positive')
    kernel = args.kernel.resolve()
    sys.path.insert(0, str(kernel))
    from openswing.asw import parse_asw
    from openswing.linear_dynamics import solve_modes

    pins = {p.name: sha(p) for p in sorted((kernel/'openswing').glob('*.py'))}
    sources = provenance()
    sources[Path(__file__).name] = sha(__file__)
    endpoints = ['lower', 'upper'] if args.endpoint == 'both' else [args.endpoint]
    specs = [dict(**case, icc_endpoint=endpoint, panels=panels)
             for case in configurations() for endpoint in endpoints for panels in [8, 16, 32]]
    destination = ROOT/'.reference/isae-st4-primary-air'
    destination.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = dict(status='RUNNING', modules=pins, scripts_and_inputs=sources,
                  requested=len(specs), runs=[], density=args.density,
                  full_physical_validation=False,
                  scope='All primary configurations, hanging gravity +z, fixed-frame '
                  'thin-strip still-air inertia at explicitly assumed density. '
                  'No fitted parameters. Experimental density, fixture and pylon '
                  'properties remain incompletely specified.')
    save(args.output, report)
    for spec in specs:
        assert pins == {p.name: sha(p) for p in sorted((kernel/'openswing').glob('*.py'))}
        assert provenance() == {k: v for k, v in sources.items() if k != Path(__file__).name}
        text, params = source(spec), parameters(spec)
        model = parse_asw(text)
        assert model.dumps() == text
        settings = dict(frame='fixed', count=12, shift=[-.1, 0.], method='dense',
                        gravity=[0., 0., params['gravity']], matrices=True,
                        quiescent_density=args.density)
        identity = dict(specification=spec, source_sha256=hashlib.sha256(text.encode()).hexdigest(),
                        modules=pins, scripts_and_inputs=sources, settings=settings)
        key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        cache = destination/(key+'.json')
        if cache.exists():
            run = json.loads(cache.read_text())
            assert run['identity'] == identity
            if run['status'] == 'computed':
                assert sha(ROOT/run['matrices']['path']) == run['matrices']['sha256']
        else:
            start = time.perf_counter()
            run = dict(identity=identity, source=text, parameters=params)
            try:
                result = solve_modes(model, None, spec['panels'], **settings)
            except (ValueError, RuntimeError) as exc:
                run.update(status='rejected', error=type(exc).__name__+': '+str(exc))
            else:
                assert result['converged'] and not result['vacuum']
                assert result['fluid']['kind'] == 'quiescent'
                assert result['fluid']['density'] == args.density
                np.testing.assert_allclose(result['base']['gravity_body'], settings['gravity'], atol=1e-13, rtol=0)
                matrices = result.pop('matrices')
                assert np.isfinite(matrices['A']).all() and np.isfinite(matrices['M']).all()
                matrix_path = destination/(key+'.npz')
                np.savez_compressed(matrix_path, A=matrices['A'], M=matrices['M'])
                run.update(status='computed', result=result,
                           matrices=dict(path=matrix_path.relative_to(ROOT).as_posix(), sha256=sha(matrix_path)))
            run['seconds'] = time.perf_counter()-start
            save(cache, run)
        report['runs'].append(dict(specification=spec, cache=cache.relative_to(ROOT).as_posix(),
                                   sha256=sha(cache), status=run['status'], seconds=run['seconds']))
        save(args.output, report)
        print(len(report['runs']), report['requested'], spec, run['status'],
              f"{run['seconds']:.2f}s", flush=True)
    report['status'] = 'PRIMARY_CONDITIONAL_STILL_AIR_RUNS_COMPLETE_WITH_REJECTIONS_RETAINED'
    report['counts'] = {status: sum(r['status'] == status for r in report['runs'])
                        for status in ['computed', 'rejected']}
    save(args.output, report)


if __name__ == '__main__':
    main()
