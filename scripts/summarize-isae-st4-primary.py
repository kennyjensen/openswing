"""Audit conditional primary ST-4 modal calculations against independent beams.

This is a numerical implementation check, not an experimental acceptance test.
All six modes retain frequency order. No properties or mode pairing are fitted
to measured frequencies. Full pencil residuals are recomputed from saved A/M.
"""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np
from isae_st4_primary import configurations, parameters, provenance, source, inputs
from isae_st4_reference import fields

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path, digest=None):
    if digest is not None:
        assert sha(path) == digest, path
    return json.loads(Path(path).read_text())


def key(spec):
    return spec['variant'], spec['position_in'], spec['icc_endpoint']


def complex_array(value):
    return np.asarray(value['real']) + 1j * np.asarray(value['imag'])


def finite_output(value):
    if isinstance(value, dict):
        for child in value.values():
            finite_output(child)
    elif isinstance(value, list):
        for child in value:
            finite_output(child)
    elif isinstance(value, float):
        assert np.isfinite(value)


def shape_values(nodes, shapes, grid, hermite=False):
    """Evaluate independent Hermite fields or native linear nodal fields."""
    if not hermite:
        return np.array([[np.interp(grid, nodes, v[:, j]) for j in range(3)]
                         for v in shapes]).transpose(0, 2, 1)
    indices = np.minimum(np.searchsorted(nodes, grid, side='right') - 1, len(nodes) - 2)
    indices = np.maximum(indices, 0)
    out = np.empty((len(shapes), len(grid), 3))
    for q, (s, j) in enumerate(zip(grid, indices)):
        ds = nodes[j+1] - nodes[j]
        h, dh, _, phi, _ = fields((s-nodes[j])/ds, ds)
        vectors = shapes[:, j:j+2].reshape(len(shapes), 6)
        out[:, q, :] = vectors @ np.array([h, dh, phi]).T
    return out


def kinetic_rows(nodes, shapes, grid, weights, params, hermite=False):
    values = shape_values(nodes, shapes, grid, hermite)
    h, dh, phi = values.transpose(2, 0, 1)
    distributed = np.stack([
        np.sqrt(params['mass']) * (h + (params['cg_x']-params['ea_x']) * phi),
        np.sqrt(params['icc']) * dh,
        np.sqrt(params['ip']) * phi,
    ], axis=2) * np.sqrt(weights)[None, :, None]
    points = []
    for mass, t, x, _, z in params['points']:
        s = (t-params['t0']) * params['length'] / (params['length']-params['t0'])
        v = shape_values(nodes, shapes, [s], hermite)[:, 0]
        points.append(np.sqrt(mass) * (v[:, 0] + (z-s)*v[:, 1] + (x-params['ea_x'])*v[:, 2]))
    result = distributed.reshape(len(shapes), -1)
    return np.column_stack([result, *points]) if points else result


def mac_matrix(native_nodes, native_shapes, reference, params):
    ref_nodes = np.asarray(reference['nodes'])
    boundaries = np.unique(np.r_[native_nodes, ref_nodes])
    # A four-point Gauss rule integrates the products of the cubic reference
    # shape and linear native nodal field on their common partition exactly.
    gx, gw = np.polynomial.legendre.leggauss(4)
    widths = np.diff(boundaries)
    grid = (boundaries[:-1, None] + widths[:, None]*(gx+1)/2).ravel()
    weights = (widths[:, None]*gw/2).ravel()
    x = kinetic_rows(native_nodes, native_shapes, grid, weights, params)
    y = kinetic_rows(ref_nodes, np.asarray(reference['shapes']), grid, weights, params, True)
    gram = x.conj() @ y.T
    return abs(gram)**2 / (np.sum(abs(x)**2, axis=1)[:, None] * np.sum(abs(y)**2, axis=1)[None, :])


def pencil_errors(data, path):
    with np.load(path) as matrices:
        a, m = matrices['A'], matrices['M']
    assert a.shape == m.shape == (data['diagnostics']['full_dimension'],)*2
    assert np.isfinite(a).all() and np.isfinite(m).all()
    norms = np.linalg.norm(a), np.linalg.norm(m)
    errors, pairings = [], []
    for mode in data['modes']:
        eigenvalue = complex(*mode['eigenvalue'])
        right, left = complex_array(mode['right']), complex_array(mode['left'])
        assert np.isfinite(eigenvalue) and np.isfinite(right).all() and np.isfinite(left).all()
        assert np.linalg.norm(right)>0 and np.linalg.norm(left)>0
        finite_output(mode['output'])
        scale = norms[0] + abs(eigenvalue)*norms[1]
        errors.append([
            np.linalg.norm(a@right - eigenvalue*(m@right))/(scale*np.linalg.norm(right)),
            np.linalg.norm(left.conj()@a - eigenvalue*(left.conj()@m))/(scale*np.linalg.norm(left)),
        ])
        pairings.append(abs(np.vdot(left, m@right)-1))
    assert np.isfinite(errors).all() and np.isfinite(pairings).all()
    return np.asarray(errors), np.asarray(pairings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reference', type=Path)
    parser.add_argument('--allow-incomplete', action='store_true')
    args = parser.parse_args()
    native_paths = [args.work/f'primary-native-{endpoint}.json' for endpoint in ['lower', 'upper']]
    reference_path = args.reference or args.work/'primary-reference.json'
    # Reports can be appended by the live sweep. Pin the exact bytes read,
    # not a later version that happens to exist when this audit finishes.
    report_bytes = {p.name:p.read_bytes() for p in [*native_paths, reference_path]}
    snapshots = args.output.parent/(args.output.stem+'-inputs')
    snapshots.mkdir(exist_ok=True)
    for name, content in report_bytes.items():
        (snapshots/name).write_bytes(content)
    native_reports = [json.loads(report_bytes[p.name]) for p in native_paths]
    reference_report = json.loads(report_bytes[reference_path.name])
    assert reference_report['status']=='PRIMARY_INDEPENDENT_AND_AIR_SENSITIVITY_COMPUTED_NOT_PHYSICALLY_VALIDATED'
    assert all(r['status'] in ['RUNNING', 'PRIMARY_CONDITIONAL_MODAL_COMPARISONS_COMPUTED_NOT_PHYSICALLY_VALIDATED'] for r in native_reports)
    chord = inputs()[0]['wing_primary']['chord_m']
    pins = provenance()
    for report in [*native_reports, reference_report]:
        for name, digest in report['scripts_and_inputs'].items():
            assert digest == (pins[name] if name in pins else sha(ROOT/'scripts'/name)), name
    modules = {p.name: sha(p) for p in sorted((ROOT/'openswing').glob('*.py'))}
    assert all(r['modules'] == modules for r in native_reports)
    expected = {key(dict(**case, icc_endpoint=e)) for case in configurations() for e in ['lower', 'upper']}
    expected_ref = {(k, rho, n) for k in expected for rho in [0., 1.225] for n in [64, 128, 256, None]}
    references = {}
    for row in reference_report['runs']:
        cache = read(ROOT/row['cache'], row['sha256'])
        identity = cache['identity']
        assert Path(row['cache']).stem == hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        for field in ['specification', 'density', 'elements', 'kind']:
            assert identity[field] == row[field]
        assert identity['sources'] == reference_report['scripts_and_inputs']
        spec = row['specification']; params = parameters(spec)
        # The air diagnostic has inertia only, and is centered at midchord.
        assert identity['parameters'] == dict(params, air_mass=np.pi*row['density']*chord**2/4,
            air_ip=np.pi*row['density']*chord**4/128, air_x=chord/2)
        assert row['kind'] == ('continuous' if row['elements'] is None else 'energy')
        index = key(spec), row['density'], row['elements']
        assert index not in references
        frequencies = np.asarray(cache['result']['frequencies_Hz'])
        assert len(frequencies) == 6 and np.isfinite(frequencies).all() and np.all(np.diff(frequencies)>0)
        assert np.all(frequencies>0)
        if row['elements'] is None:
            boundary = cache['result']['boundary_checks']; assert len(boundary)==6
            for frequency, check in zip(frequencies, boundary):
                ratio = check['relative_boundary_singular_value']
                bracket = check['bracket_Hz']
                assert np.isfinite(ratio) and ratio>=0 and np.isfinite(bracket).all()
                assert 0<bracket[0]<=frequency<=bracket[1] and check['iterations']>0
        references[index] = cache['result']
    assert set(references) == expected_ref and len(reference_report['runs']) == 672
    ref_rows = []
    for k in sorted(expected, key=str):
        for rho in [0., 1.225]:
            exact = np.asarray(references[k, rho, None]['frequencies_Hz'])
            energy = np.asarray([references[k, rho, n]['frequencies_Hz'] for n in [64, 128, 256]])
            errors = abs(energy/exact-1)
            ref_rows.append(dict(configuration=list(k), density=rho, frequencies_Hz=exact.tolist(),
                relative_energy_errors=errors.tolist(),
                nonmonotonic_error_modes=(np.where(np.any(np.diff(errors, axis=0)>=0, axis=0))[0]+1).tolist(),
                maximum_boundary_singular_ratio=max(v['relative_boundary_singular_value']
                    for v in references[k, rho, None]['boundary_checks'])))
    rows, rejected, groups, seen = [], [], {}, set()
    for report in native_reports:
        for row in report['runs']:
            cache = read(ROOT/row['cache'], row['sha256'])
            spec = row['specification']; params = parameters(spec); k = key(spec)
            index = k, spec['panels']; assert index not in seen; seen.add(index)
            identity = cache['identity']
            assert Path(row['cache']).stem == hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
            assert identity['specification'] == spec and identity['modules'] == modules
            assert identity['scripts_and_inputs'] == report['scripts_and_inputs']
            assert cache['source'] == source(spec)
            assert identity['source_sha256'] == hashlib.sha256(cache['source'].encode()).hexdigest()
            assert cache['parameters'] == params and cache['status'] == row['status']
            if cache['status'] != 'computed':
                rejected.append(dict(specification=spec, error=cache['error']))
                continue
            data = cache['result']; assert data['converged'] and data['vacuum']
            launch = data['base']['equilibrium_state']['launch']
            assert launch['gravity'] == [0., 0., params['gravity']] and launch['condition'] is None
            modes = sorted((v for v in data['modes'] if v['eigenvalue'][1]>0), key=lambda v:v['frequency'])
            assert len(modes) == 6
            frequency = np.asarray([v['frequency'] for v in modes])
            assert np.isfinite(frequency).all() and np.all(frequency>0) and np.all(np.diff(frequency)>0)
            matrix_path = ROOT/cache['matrices']['path']; assert sha(matrix_path) == cache['matrices']['sha256']
            backward, pairing = pencil_errors(data, matrix_path)
            nodes = np.asarray([n['position'][2] for n in data['base']['nodes']]); shapes = []
            assert np.max(abs(np.asarray([n['position'] for n in data['base']['nodes']])[:, :2])) < 1e-10
            assert abs(nodes[0])<1e-12 and abs(nodes[-1]-params['length'])<1e-12
            for mode in modes:
                displacement = np.asarray([complex_array(v['displacement']) for v in mode['output']['nodes']])
                rotation = np.asarray([complex_array(v['rotation']) for v in mode['output']['nodes']])
                shapes.append(np.column_stack([displacement[:, 1]+params['ea_x']*rotation[:, 2],
                                               -rotation[:, 0], rotation[:, 2]]))
            assurance = mac_matrix(nodes, np.asarray(shapes), references[k, 0., 256], params)
            assert np.isfinite(assurance).all() and np.all(assurance>=0) and np.all(assurance<=1+1e-10)
            exact = np.asarray(references[k, 0., None]['frequencies_Hz'])
            result = dict(specification=spec, source_sha256=identity['source_sha256'],
                frequencies_Hz=frequency.tolist(), continuous_frequencies_Hz=exact.tolist(),
                relative_frequency_errors=abs(frequency/exact-1).tolist(),
                kinetic_shape_assurance=np.diag(assurance).tolist(), kinetic_shape_assurance_matrix=assurance.tolist(),
                finite_dimension=data['diagnostics']['finite_dimension'], base_residual=data['diagnostics']['base_residual'],
                full_pencil_backward_errors=backward.tolist(), normalization_errors=pairing.tolist(), seconds=cache['seconds'])
            rows.append(result); groups.setdefault(k, []).append(result)
    expected_native = {(k, n) for k in expected for n in [8, 16, 32]}
    assert seen <= expected_native
    complete = seen == expected_native and all(r['status']!='RUNNING' for r in native_reports)
    if not args.allow_incomplete:
        assert complete, (len(seen), len(expected_native))
    refinement, partial = [], []
    for k in sorted(expected, key=str):
        group = sorted(groups.get(k, []), key=lambda r:r['specification']['panels'])
        if [r['specification']['panels'] for r in group] != [8, 16, 32]:
            partial.append(list(k)); continue
        errors = np.asarray([r['relative_frequency_errors'] for r in group])
        refinement.append(dict(configuration=list(k), relative_frequency_errors=errors.tolist(),
            nonmonotonic_modes=(np.where(np.any(np.diff(errors, axis=0)>=0, axis=0))[0]+1).tolist()))
    fine = [r for r in rows if r['specification']['panels']==32]
    maxima = dict(
        maximum_N32_frequency_error=max((max(r['relative_frequency_errors']) for r in fine), default=None),
        minimum_N32_kinetic_shape_assurance=min((min(r['kinetic_shape_assurance']) for r in fine), default=None),
        maximum_energy_N256_frequency_error=max(max(r['relative_energy_errors'][-1]) for r in ref_rows),
        maximum_full_pencil_backward_error=float(max((np.max(r['full_pencil_backward_errors']) for r in rows), default=0)),
        maximum_normalization_error=max((max(r['normalization_errors']) for r in rows), default=0),
        maximum_base_residual=max((r['base_residual'] for r in rows), default=0),
        maximum_boundary_singular_ratio=max(r['maximum_boundary_singular_ratio'] for r in ref_rows))
    checks = dict(no_rejections=not rejected,
        native_all_six_frequency_errors_decrease=all(not r['nonmonotonic_modes'] for r in refinement),
        full_pencil_backward_errors_below_1e_9=maxima['maximum_full_pencil_backward_error']<1e-9,
        normalization_errors_below_1e_7=maxima['maximum_normalization_error']<1e-7,
        base_residuals_below_1e_8=maxima['maximum_base_residual']<1e-8,
        reference_frequency_errors_below_1e_4=maxima['maximum_energy_N256_frequency_error']<1e-4,
        continuous_boundary_singular_ratios_below_1e_8=maxima['maximum_boundary_singular_ratio']<1e-8)
    status = ('PRIMARY_NUMERICAL_COMPARISON_COMPLETE' if all(checks.values())
              else 'PRIMARY_NUMERICAL_COMPARISON_COMPLETE_WITH_DIAGNOSTIC_FLAGS') if complete else 'INCOMPLETE_PRIMARY_NUMERICAL_COMPARISON'
    result = dict(status=status, complete=complete, full_physical_validation=False,
        accuracy_acceptance_established=False,
        acceptance_scope='Residual and reference checks are numerical controls. Native frequency error and shape correlation are reported without an experimental accuracy acceptance threshold.',
        script_sha256=sha(__file__), modules=modules, scripts_and_inputs=pins,
        report_sha256={name:hashlib.sha256(content).hexdigest() for name, content in report_bytes.items()},
        report_snapshots=str(snapshots),
        native_states=len(rows), rejected=rejected, expected_native_states=252,
        reference_states=len(references), independent_continuous_models=len(ref_rows),
        matched_modes=6*len(rows), complete_refinement_groups=len(refinement), partial_groups=partial,
        checks=checks, summary=maxima, native_rows=rows, native_refinement=refinement,
        independent_refinement=ref_rows,
        limitations=[
            'Hanging gravity is included. Native calculations omit ambient-air added mass.',
            'The two sectional rotary-inertia endpoints are conditional geometric bounds, not a complete experimental uncertainty interval.',
            'Equivalent point pairs omit unreported pylon bending inertia and spanwise CG offsets; in-plane bending is constrained.',
            'Density1.225 reference results are an assumed strip-air sensitivity, not OpenSwing predictions or recovered test density.',
            'Kinetic shape assurance integrates native linear nodal fields against independent Hermite bending/linear twist fields. Modes retain frequency order.',
            'No experimental frequencies enter these numerical errors or mode pairings. Experimental agreement requires a separate comparison.'])
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['status','native_states','reference_states','complete_refinement_groups','checks','summary']}, indent=2))


if __name__ == '__main__':
    main()
