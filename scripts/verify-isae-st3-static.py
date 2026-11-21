"""Source-pinned ST-3 static experiments and exact signed-load reconstruction.

Archived MATLAB/shell scripts are inspected, never executed. Every experimental
load is solved with its original sign, without resetting its digitized origin.
"""
from pathlib import Path
import argparse, hashlib, json, re, sys, time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from openswing.asw import parse_asw
from openswing.network import StaticNetwork, network_result
from openswing.structured_static import equilibrate
from isae_st3_static_reference import PROPERTIES, LENGTH, CHORD, EA, solve, observables

REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
FOLDER = '3 - Structure/CASE - ST3 Low aspect ratio'
CACHE = ROOT/'.reference/isae-validation'/REVISION
STATIC = FOLDER+'/Static_Deflection_analysis'
LAYUPS = {'0_3_90': ('[0_3_90]_S', '[03_90]_S'),
          'p15_0': ('[+15_2_0_2]_S', '[+15_2_0_2]_S'),
          'm15_0': ('[-15_2_0_2]_S', '[-15_2_0_2]_S')}
TORQUE_FACTOR = 9.81*CHORD


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def source_path(name):
    return STATIC+'/['+name+'].asw'


def inspect(text, name):
    model = parse_asw(text)
    assert model.dumps() == text and len(model.beams) == 1 and not model.diagnostics
    beam = model.beams[0]
    t = np.linspace(.0001, .558, 5)
    ei, gj, inn, coupling = PROPERTIES[name]
    expected = dict(EIcc=ei, GJ=gj, EInn=inn, EIcs=coupling, EA=EA, EIcn=0., EIsn=0.,
                    Cea=0., Nea=0., Cta=0., Nta=0., Ccg=0., Ncg=0.,
                    mg=0., mgcc=0., mgnn=0., chord=CHORD, twist=0.)
    for field, value in expected.items():
        np.testing.assert_allclose(beam.value(field, t), value, atol=1e-15, rtol=2e-15)
    for field in ['GKc', 'GKn']:
        assert np.all(np.isinf(beam.value(field, t)))
    np.testing.assert_allclose(beam.position([.0001, .558]), [[0, 0, 0], [0, LENGTH, 0]])
    np.testing.assert_array_equal(model.records['ground'], [[1, .0001, 0]])
    assert len(model.records['weight']) == 2
    return model


def reconstruct(text, name, force, couple):
    """Static wrench equivalence only. Never use derived inertia for dynamics."""
    model = inspect(text, name)
    rows, loads, proof = [], [], []
    for j, row in enumerate(model.records['weight']):
        assert np.all(np.asarray(row[6:]) == 0)
        point = np.asarray(row[2:5]); anchor = model.beams[0].position(row[1])
        np.testing.assert_allclose(point-anchor, [(-1 if j == 0 else 1)*CHORD/2, 0, 0])
        weight = force/2 + couple/CHORD*(1 if j == 0 else -1)
        original_point = point.copy()
        if weight < 0:
            point = 2*anchor-point
            loads.append(dict(beam=int(row[0]), t=float(row[1]), force=[0., 0., -2*weight]))
        rows.append([int(row[0]), row[1], *point, abs(weight)])
        proof.append(dict(original_weight_N=weight, original_point=original_point.tolist(),
                          anchor=anchor.tolist(), derived_weight_N=abs(weight), derived_point=point.tolist()))
    block = 'Weight\n'+'\n'.join(' '.join(format(x, '.17g') for x in row) for row in rows)+'\nEnd'
    derived, count = re.subn(r'(?ims)^Weight\s*\n.*?^end\s*$', block, text, count=1)
    assert count == 1
    parsed = parse_asw(derived)
    assert len(parsed.records['weight']) == 2
    return parsed, derived, loads, proof


def compute(text, spec):
    model, derived, loads, proof = reconstruct(text, spec['name'], spec['force_N'], spec['couple_Nm'])
    start = time.perf_counter()
    net = StaticNetwork(model, spec['panels'], None, [0., 0., -9.81], loads)
    state, steps = equilibrate(net)  # unchanged production default convergence settings
    result = network_result(net, state)
    tip = result['nodes'][-1]
    return dict(seconds=time.perf_counter()-start, result=result,
                observables=observables(np.array(tip['position']), np.array(tip['rotation'])),
                derived_source=derived, explicit_nodal_loads=loads, reconstruction=proof,
                solver='production structured_static.equilibrate; condition=None',
                static_equivalence_only=True)


def measurements():
    rows = []
    for name, (folder, stem) in LAYUPS.items():
        for kind in ['F', 'M']:
            for quantity in ['Z', 'THETA']:
                base = CACHE/FOLDER/folder
                prefix = stem+'_'+kind+'_VS_'+quantity
                for p in sorted(p for p in base.iterdir() if p.name.startswith(prefix) and p.suffix == '.csv'):
                    reference = p.stem.lower().endswith('_num')
                    raw = np.loadtxt(p, skiprows=2, delimiter=',')
                    assert raw.ndim == 2 and raw.shape[1] == 2 and np.isfinite(raw).all()
                    rows.append(dict(name=name, kind=kind, quantity=quantity,
                                     category='Dunn_analysis_digitization' if reference else 'experiment_digitization',
                                     path=p.relative_to(CACHE).as_posix(), sha256=sha(p),
                                     columns=['tip_h_m' if quantity == 'Z' else 'tip_theta_deg',
                                              'force_N' if kind == 'F' else 'couple_Nm'],
                                     values=raw.tolist()))
    assert len(rows) == 24
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT/'docs/validation/isae-st3-static.json')
    parser.add_argument('--cache', type=Path, default=ROOT/'.reference/isae-st3-static-runs')
    args = parser.parse_args(); args.cache.mkdir(parents=True, exist_ok=True)
    modules = {p.name: sha(p) for p in sorted((ROOT/'openswing').glob('*.py'))}
    script_pins = {p.name: sha(p) for p in [Path(__file__), ROOT/'scripts/isae_st3_static_reference.py']}
    manifest = json.loads((ROOT/'.reference/isae-validation/manifest.json').read_text())
    assert manifest['revision'] == REVISION
    paths = [p for p in (CACHE/STATIC).iterdir() if p.is_file() and p.suffix in ['.m', '.sh', '.asw', '.eps', '.txt']]
    data = measurements()
    paths += [CACHE/r['path'] for r in data]
    sources = {p.relative_to(CACHE).as_posix(): dict(sha256=sha(p), bytes=p.stat().st_size) for p in sorted(set(paths))}
    for path, pin in sources.items():
        assert manifest['files'][path]['sha256'] == pin['sha256'], path
    sources_text = {name: (CACHE/source_path(name)).read_text() for name in LAYUPS}
    literal = []
    for name, text in sources_text.items():
        model = inspect(text, name)
        try:
            StaticNetwork(model, 8, None, [0., 0., -9.81], [])
        except Exception as exc:
            literal.append(dict(name=name, status='unsupported_literal_solve', error_type=type(exc).__name__, error=str(exc)))
        else:
            raise AssertionError('Signed-weight handling changed: re-audit reconstruction.')

    specifications = {}; requests = []
    def request(name, force, couple, panels, role):
        spec = dict(name=name, force_N=float(force), couple_Nm=float(couple), panels=panels)
        key = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()
        specifications[key] = spec
        requests.append(dict(key=key, role=role))
        return key
    for dataset in data:
        if dataset['category'] != 'experiment_digitization':
            continue
        dataset['native_keys'] = []
        for index, (measured, load) in enumerate(dataset['values']):
            force, couple = (load, 0.) if dataset['kind'] == 'F' else (0., load)
            keys = [request(dataset['name'], force, couple, mesh, dict(kind='measurement', path=dataset['path'], index=index)) for mesh in [32, 64]]
            dataset['native_keys'].append(keys)
    for name in LAYUPS:
        for force, couple in [(4.905 if name == '0_3_90' else 3.924, 0.), (0., .55), (0., .55*TORQUE_FACTOR)]:
            for sign in [-1., 1.]:
                for mesh in [8, 16, 32, 64]:
                    request(name, sign*force, sign*couple, mesh, dict(kind='mesh_and_sign_refinement'))
    archived = []
    for name, text in sources_text.items():
        w = inspect(text, name).records['weight']
        force = w[0][5]+w[1][5]
        couple = CHORD/2*(w[0][5]-w[1][5])
        archived.append(dict(name=name, literal_force_N=force, literal_couple_Nm=couple,
                             native_key=request(name, force, couple, 64, dict(kind='last_literal_weights'))))

    runs = []; references = {}; failures = []
    for index, (key, spec) in enumerate(specifications.items()):
        identity = dict(specification=spec, modules=modules, scripts=script_pins, input_sha256=sources[source_path(spec['name'])]['sha256'])
        digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        path = args.cache/(digest+'.json')
        if path.exists():
            row = json.loads(path.read_text()); assert row['identity'] == identity
        else:
            try:
                row = dict(key=key, identity=identity, status='computed', result=compute(sources_text[spec['name']], spec))
            except Exception as exc:
                row = dict(key=key, identity=identity, status='failed', error_type=type(exc).__name__, error=str(exc))
            path.write_text(json.dumps(row, indent=2)+'\n')
        runs.append(row)
        if row['status'] != 'computed':
            failures.append(row)
        refspec = {k: v for k, v in spec.items() if k != 'panels'}
        refkey = hashlib.sha256(json.dumps(refspec, sort_keys=True).encode()).hexdigest()
        if refkey not in references:
            refidentity = dict(specification=refspec, script_sha256=script_pins['isae_st3_static_reference.py'])
            refdigest = hashlib.sha256(json.dumps(refidentity, sort_keys=True).encode()).hexdigest()
            refpath = args.cache/('reference-'+refdigest+'.json')
            if refpath.exists():
                reference = json.loads(refpath.read_text()); assert reference['identity'] == refidentity
            else:
                try:
                    reference = dict(identity=refidentity, status='computed', result=solve(spec['name'], spec['force_N'], spec['couple_Nm']))
                except Exception as exc:
                    reference = dict(identity=refidentity, status='failed', error_type=type(exc).__name__, error=str(exc))
                refpath.write_text(json.dumps(reference, indent=2)+'\n')
            references[refkey] = reference
        row['reference_key'] = refkey
        print(f"{index+1}/{len(specifications)} {spec} {row['status']}", flush=True)
    assert modules == {p.name: sha(p) for p in sorted((ROOT/'openswing').glob('*.py'))}
    output = dict(status='COMPUTED_WITH_RETAINED_LIMITATIONS', revision=REVISION, sources=sources, modules=modules,
                  scripts=script_pins, datasets=data, requests=requests, runs=runs, independent_references=references,
                  literal_input_probes=literal, archived_final_weights=archived, archived_torque_factor=TORQUE_FACTOR,
                  full_suite_validated=False, goal_complete=False)
    args.output.write_text(json.dumps(output, indent=2)+'\n')
    print('RESULT', args.output, 'native', len(runs), 'failed', len(failures), 'references', len(references), flush=True)


if __name__ == '__main__':
    main()
