"""Compare all supplied Pazy static measurements without fitting properties.

Two explicit reconstructions are kept: original physical mass coordinates on
a valid tip pylon, and measured load locations. Neither is a literal-file pass.
"""
from pathlib import Path
import argparse
import hashlib
import json
import time
import numpy as np
from isae_st2 import ROOT, CACHE, FOLDER, STATIC, source, sha, measurements, compute_static, observables
from isae_st2_static_reference import solve as reference_solve


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT/'docs/validation/isae-st2-static.json')
    parser.add_argument('--cache', type=Path, default=ROOT/'.reference/isae-st2-static-runs')
    args = parser.parse_args(); args.cache.mkdir(parents=True, exist_ok=True)
    modules = {p.name: sha(p) for p in sorted((ROOT/'openswing').glob('*.py'))}
    scripts = {p.name: sha(p) for p in [Path(__file__), ROOT/'scripts/isae_st2.py', ROOT/'scripts/isae_st2_static_reference.py']}
    manifest = json.loads((CACHE.parent/'manifest.json').read_text())
    sources = {name: pin for name, pin in manifest['files'].items() if name.startswith(FOLDER+'/')}
    for name, pin in sources.items():
        assert sha(CACHE/name) == pin['sha256'], name
    datasets = measurements(); specs = {}; requests = []
    for data in datasets:
        data['requests'] = []
        for index, (mass, measured) in enumerate(data['values']):
            row = dict(index=index, keys={})
            for layout in ['archive_pylon', 'measured_tip']:
                row['keys'][layout] = []
                for panels in [16, 32, 64]:
                    spec = dict(kind=data['kind'], skin=0 if data['kind']=='bending' else data['skin'], mass_kg=mass, layout=layout, panels=panels)
                    key = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()
                    specs[key] = spec
                    row['keys'][layout].append(key)
                    requests.append(dict(key=key, dataset=data['source_path'], index=index))
            data['requests'].append(row)
    runs = {}
    for i, (key, spec) in enumerate(specs.items()):
        identity = dict(specification=spec, modules=modules, scripts=scripts, source_sha256=sha(source(spec['kind'])))
        pin = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        path = args.cache/(pin+'.json')
        if path.exists():
            run = json.loads(path.read_text()); assert run['identity'] == identity
        else:
            start = time.perf_counter()
            try:
                run = compute_static(spec); run['status'] = 'computed'
            except (ValueError, RuntimeError) as exc:
                run = dict(specification=spec, status='rejected', error=type(exc).__name__+': '+str(exc))
            if run['status'] == 'computed':
                assert run['result']['residual'] < 1e-8
                assert np.max(np.abs(run['result']['force_balance'])) < 1e-7
                assert np.max(np.abs(run['result']['moment_balance'])) < 1e-7
            run.update(identity=identity, seconds=time.perf_counter()-start)
            path.write_text(json.dumps(run, indent=2)+'\n')
        runs[key] = dict(status=run['status'], specification=spec, cache=str(path.relative_to(ROOT)), sha256=sha(path))
        if run['status']=='computed':
            runs[key].update(observables=run['observables'], residual=run['result']['residual'])
        else:
            runs[key]['error'] = run['error']
        print(i+1, len(specs), spec, run['status'], flush=True)
    for data in datasets:
        data['comparisons'] = []
        for layout in ['archive_pylon', 'measured_tip']:
            for j, panels in enumerate([16, 32, 64]):
                rows = []
                zero = runs[data['requests'][0]['keys'][layout][j]]
                assert data['values'][0][0] == 0
                for request, (mass, measured) in zip(data['requests'], data['values']):
                    run = runs[request['keys'][layout][j]]
                    predicted = None
                    if run['status']=='computed' and zero['status']=='computed':
                        predicted = run['observables'][data['quantity']]
                        if data['quantity']=='z_m':
                            predicted -= zero['observables']['z_m']
                    row = dict(mass_kg=mass, measured=measured, predicted=predicted, error=None if predicted is None else predicted-measured)
                    if data['quantity']=='twist_projected_deg' and run['status']=='computed':
                        row['archive_plot_convention_negated_local_twist_deg'] = -run['observables']['twist_asw_deg']
                    rows.append(row)
                finite = [r['error'] for r in rows if r['error'] is not None]
                data['comparisons'].append(dict(layout=layout, panels=panels, rows=rows,
                    computed=len(finite), total=len(rows), rmse=float(np.sqrt(np.mean(np.square(finite)))) if finite else None))
    independent = []
    for kind, skin, mass in [('bending', 0, 0.), ('bending', 0, 3.), ('torsion', 0, 2.), ('torsion', 1, 2.8)]:
        for layout in ['archive_pylon', 'measured_tip']:
            matches = [r for r in runs.values() if all(r['specification'][k]==v for k,v in dict(kind=kind,skin=skin,mass_kg=mass,layout=layout).items())]
            assert len(matches) == 3
            observations = []
            for row in matches:
                if row['status'] != 'computed':
                    observations.append(dict(panels=row['specification']['panels'], status='production_rejected')); continue
                run = json.loads((ROOT/row['cache']).read_text()); nodes=run['result']['nodes']
                stations = np.array([n['jig_position'][1] for n in nodes])
                reference = reference_solve(kind, mass, run['reconstruction']['point_xyz_m'], stations=stations)
                positions = np.array([n['position'] for n in nodes]); rotations = np.array([n['rotation'] for n in nodes])
                expected = observables(reference['positions'][-1], reference['rotations'][-1])
                observations.append(dict(panels=row['specification']['panels'], status='compared',
                    max_position_difference_m=float(np.max(abs(positions-np.array(reference['positions'])))),
                    max_rotation_component_difference=float(np.max(abs(rotations-np.array(reference['rotations'])))),
                    observable_differences={k:run['observables'][k]-v for k,v in expected.items()}, reference=reference))
            independent.append(dict(kind=kind,skin=skin,mass_kg=mass,layout=layout,observations=observations))
    out = dict(status='COMPARISONS_COMPLETE_NOT_PHYSICALLY_VALIDATED', upstream_revision=manifest['revision'], modules=modules,
        scripts=scripts, sources=sources, datasets=datasets, requests=requests, runs=runs, independent=independent,
        measurement_rows=sum(len(d['values']) for d in datasets), unique_conditions=len(runs),
        computed=sum(r['status']=='computed' for r in runs.values()), rejected=sum(r['status']!='computed' for r in runs.values()),
        limits=['All original files reject during mesh construction due to out-of-range point attachments.',
            'Derived inputs are explicitly labeled. Original material properties are not fitted or changed between skin cases.',
            'The measured-layout variant changes load coordinates only; it does not reconstruct the full primary stiffness/inertia distributions.',
            'Signed projected twist and archived negated local twist are distinct quantities.',
            'The original ASWING plot removes the zero-load vertical displacement; the same explicit subtraction is used here.',
            'No experimental tolerance or full-family validation pass is asserted.'])
    args.output.write_text(json.dumps(out, indent=2)+'\n')
    print(json.dumps({k:out[k] for k in ['status','measurement_rows','unique_conditions','computed','rejected']},indent=2),flush=True)


if __name__ == '__main__':
    main()
