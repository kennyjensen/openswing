"""Audit primary ST-4 still-air caches without running or fitting a solver.

Read live runner reports exactly once, retain their content-addressed snapshots,
check all saved full pencils/vectors, and compare frequency-ordered modes with
source/parameter/density-matched independent references. The experimental
comparison is conditional spectral rank, never nearest-frequency assignment.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import sys

import numpy as np
from isae_st4_primary import configurations, parameters, provenance, source, inputs
from isae_st4_reference import fields

ROOT = Path(__file__).resolve().parents[1]
RHO = 1.225
PANELS = (8, 16, 32)
ENDPOINTS = ('lower', 'upper')
TERMINAL = 'PRIMARY_CONDITIONAL_STILL_AIR_RUNS_COMPLETE_WITH_REJECTIONS_RETAINED'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path, digest=None):
    content = Path(path).read_bytes()
    if digest is not None:
        require(hashlib.sha256(content).hexdigest() == digest, f'Hash mismatch: {path}')
    return json.loads(content)


def key(spec):
    return spec['variant'], spec['position_in'], spec['icc_endpoint']


def complex_array(value):
    return np.asarray(value['real']) + 1j*np.asarray(value['imag'])


def finite_output(value):
    if isinstance(value, dict):
        for child in value.values():
            finite_output(child)
    elif isinstance(value, list):
        for child in value:
            finite_output(child)
    elif isinstance(value, float):
        require(np.isfinite(value), 'Nonfinite output value')


def shape_values(nodes, shapes, grid, hermite=False):
    """Native linear nodal fields or independent cubic Hermite bending fields."""
    if not hermite:
        return np.array([[np.interp(grid, nodes, v[:, j]) for j in range(3)]
                         for v in shapes]).transpose(0, 2, 1)
    indices = np.clip(np.searchsorted(nodes, grid, side='right')-1, 0, len(nodes)-2)
    out = np.empty((len(shapes), len(grid), 3), dtype=np.result_type(shapes, float))
    for q, (s, j) in enumerate(zip(grid, indices)):
        ds = nodes[j+1]-nodes[j]
        h, dh, _, phi, _ = fields((s-nodes[j])/ds, ds)
        out[:, q, :] = shapes[:, j:j+2].reshape(len(shapes), 6) @ np.array([h, dh, phi]).T
    return out


def kinetic_rows(nodes, shapes, grid, weights, params, hermite=False):
    """Energy coordinates, including midchord strip-air mass and pitch inertia."""
    h, dh, phi = shape_values(nodes, shapes, grid, hermite).transpose(2, 0, 1)
    channels = [
        np.sqrt(params['mass'])*(h+(params['cg_x']-params['ea_x'])*phi),
        np.sqrt(params['icc'])*dh,
        np.sqrt(params['ip'])*phi,
        np.sqrt(params['air_mass'])*(h+(params['air_x']-params['ea_x'])*phi),
        np.sqrt(params['air_ip'])*phi,
    ]
    result = (np.stack(channels, axis=2)*np.sqrt(weights)[None, :, None]).reshape(len(shapes), -1)
    for mass, t, x, _, z in params['points']:
        s = (t-params['t0'])*params['length']/(params['length']-params['t0'])
        v = shape_values(nodes, shapes, [s], hermite)[:, 0]
        result = np.column_stack([result, np.sqrt(mass)*(v[:, 0]+(z-s)*v[:, 1]+(x-params['ea_x'])*v[:, 2])])
    return result


def mac_matrix(nodes, shapes, reference, params):
    ref_nodes = np.asarray(reference['nodes'])
    boundaries = np.unique(np.r_[nodes, ref_nodes])
    # Four-point Gauss is exact for these piecewise polynomial products.
    gx, gw = np.polynomial.legendre.leggauss(4)
    widths = np.diff(boundaries)
    grid = (boundaries[:-1, None]+widths[:, None]*(gx+1)/2).ravel()
    weights = (widths[:, None]*gw/2).ravel()
    x = kinetic_rows(nodes, shapes, grid, weights, params)
    y = kinetic_rows(ref_nodes, np.asarray(reference['shapes']), grid, weights, params, True)
    norms = np.sum(abs(x)**2, axis=1)[:, None]*np.sum(abs(y)**2, axis=1)[None, :]
    require(np.all(norms > 0), 'Zero kinetic norm')
    return abs(x.conj() @ y.T)**2/norms


def pencil_errors(data, path):
    with np.load(path, allow_pickle=False) as matrices:
        a, m = matrices['A'], matrices['M']
    dimension = data['diagnostics']['full_dimension']
    require(a.shape == m.shape == (dimension, dimension), 'Full matrix dimension mismatch')
    require(np.isfinite(a).all() and np.isfinite(m).all(), 'Nonfinite full matrix')
    require(len(data['modes']) == 12, 'Expected 12 saved roots')
    norms = np.linalg.norm(a), np.linalg.norm(m)
    errors, pairings, poles = [], [], []
    for mode in data['modes']:
        eigenvalue = complex(*mode['eigenvalue'])
        right, left = complex_array(mode['right']), complex_array(mode['left'])
        require(right.shape == left.shape == (dimension,), 'Full vector dimension mismatch')
        require(np.isfinite(eigenvalue) and np.isfinite(right).all() and np.isfinite(left).all(), 'Nonfinite pole/vector')
        require(np.linalg.norm(right) > 0 and np.linalg.norm(left) > 0, 'Zero eigenvector')
        finite_output(mode['output'])
        scale = norms[0]+abs(eigenvalue)*norms[1]
        require(scale > 0, 'Zero full-pencil norm')
        errors.append([
            np.linalg.norm(a@right-eigenvalue*(m@right))/(scale*np.linalg.norm(right)),
            np.linalg.norm(left.conj()@a-eigenvalue*(left.conj()@m))/(scale*np.linalg.norm(left)),
        ])
        pairings.append(abs(np.vdot(left, m@right)-1))
        poles.append(eigenvalue)
        require(np.isclose(mode['frequency'], abs(eigenvalue.imag)/(2*np.pi), rtol=1e-12, atol=1e-12),
                'Frequency inconsistent with pole')
    poles = np.asarray(poles)
    conjugate_error = max(min(abs(poles-v.conjugate())) for v in poles)
    require(np.isfinite(errors).all() and np.isfinite(pairings).all(), 'Nonfinite pencil audit')
    return np.asarray(errors), np.asarray(pairings), float(conjugate_error)


def native_shapes(data, modes, params):
    positions = np.asarray([n['position'] for n in data['base']['nodes']])
    nodes = positions[:, 2]
    require(np.max(abs(positions[:, :2])) < 1e-10, 'Expected straight hanging reference geometry')
    require(abs(nodes[0]) < 1e-12 and abs(nodes[-1]-params['length']) < 1e-12 and np.all(np.diff(nodes) > 0),
            'Native span mismatch')
    layout = data['diagnostics']['state_layout']['node_coordinates']
    require(layout['width'] == 6*len(nodes) and layout['translation_scale'] == params['length'], 'Nodal layout mismatch')
    result, differences = [], []
    for mode in modes:
        state = complex_array(mode['right'])[layout['start']:layout['start']+layout['width']].reshape(len(nodes), 6)
        displacement, rotation = state[:, :3]*layout['translation_scale'], state[:, 3:]
        output_displacement = np.asarray([complex_array(v['displacement']) for v in mode['output']['nodes']])
        output_rotation = np.asarray([complex_array(v['rotation']) for v in mode['output']['nodes']])
        difference = max(float(np.max(abs(displacement-output_displacement))), float(np.max(abs(rotation-output_rotation))))
        scale = max(float(np.max(abs(displacement))), float(np.max(abs(rotation))), 1.)
        require(difference/scale < 1e-10, 'Right-state/output shape mapping disagrees')
        differences.append(difference/scale)
        result.append(np.column_stack([displacement[:, 1]+params['ea_x']*rotation[:, 2],
                                       -rotation[:, 0], rotation[:, 2]]))
    return nodes, np.asarray(result), differences


def validate_fluid(data, settings, panels):
    require(data['converged'] and not data['vacuum'] and data['frame_mode'] == 'fixed', 'Invalid modal state')
    fluid = data['fluid']
    require(fluid == data['base']['fluid'], 'Base/modal fluid metadata differ')
    require(fluid['kind'] == 'quiescent' and fluid['density'] == RHO, 'Wrong fluid/density')
    require(fluid['mean_velocity_body'] == [0., 0., 0.] and fluid['circulatory'] is False
            and fluid['wind_direction'] is None, 'Nonquiescent fluid metadata')
    equilibrium = data['base']['equilibrium_state']
    launch = equilibrium['launch']
    require(launch['condition'] is None and launch['gravity'] == settings['gravity']
            and launch['quiescent_density'] == RHO and launch['panels'] == panels, 'Wrong launch conditions')
    require(launch['controller'] is None and launch['motion'] == dict(rates=[0., 0., 0.],
            acceleration=[0., 0., 0.], angular_acceleration=[0., 0., 0.]), 'Unexpected controller or base motion')
    require(equilibrium['identity']['quiescent_density'] == RHO and equilibrium['identity']['circulation_count'] == 0,
            'Wrong equilibrium identity')
    require(np.allclose(data['base']['gravity_body'], settings['gravity'], atol=1e-13, rtol=0), 'Wrong body gravity')
    diagnostics = data['diagnostics']
    require(diagnostics['method'] == diagnostics['requested_method'] == 'dense' and diagnostics['requested_count'] == 12
            and diagnostics['shift'] == settings['shift'], 'Wrong solver diagnostics')
    require(diagnostics['state_layout']['circulation']['width'] == 0, 'Unexpected circulation unknowns')


def audit_references(report, expected, chord):
    require(report['status'] == 'PRIMARY_INDEPENDENT_AND_AIR_SENSITIVITY_COMPUTED_NOT_PHYSICALLY_VALIDATED', 'Reference report not complete')
    expected_all = {(k, rho, n) for k in expected for rho in (0., RHO) for n in (64, 128, 256, None)}
    references, pins = {}, {}
    for row in report['runs']:
        spec = row['specification']
        index = key(spec), row['density'], row['elements']
        require(index in expected_all and index not in references, 'Unexpected/duplicate reference')
        require(spec == expected[key(spec)], 'Reference specification mismatch')
        cache = read(ROOT/row['cache'], row['sha256'])
        identity = cache['identity']
        require(Path(row['cache']).stem == hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest(), 'Reference identity filename mismatch')
        require(all(identity[k] == row[k] for k in ('specification', 'density', 'elements', 'kind')), 'Reference identity mismatch')
        require(identity['sources'] == report['scripts_and_inputs'], 'Reference source pins mismatch')
        params = dict(parameters(spec), air_mass=np.pi*row['density']*chord**2/4,
                      air_ip=np.pi*row['density']*chord**4/128, air_x=chord/2)
        require(identity['parameters'] == params, 'Reference physical/air parameters mismatch')
        require(row['kind'] == ('continuous' if row['elements'] is None else 'energy'), 'Reference type mismatch')
        result = cache['result']
        frequency = np.asarray(result['frequencies_Hz'])
        require(frequency.shape == (6,) and np.isfinite(frequency).all() and np.all(frequency > 0)
                and np.all(np.diff(frequency) > 0), 'Invalid reference frequencies')
        if row['elements'] is None:
            require(len(result['boundary_checks']) == 6, 'Reference boundary count mismatch')
            for f, check in zip(frequency, result['boundary_checks']):
                lo, hi = check['bracket_Hz']; ratio = check['relative_boundary_singular_value']
                require(np.isfinite([lo, hi, ratio]).all() and 0 < lo <= f <= hi and ratio >= 0
                        and check['iterations'] > 0, 'Invalid continuous boundary certificate')
        else:
            nodes, shapes = np.asarray(result['nodes']), np.asarray(result['shapes'])
            require(shapes.shape == (6, len(nodes), 3) and np.isfinite(shapes).all()
                    and np.isfinite(nodes).all() and np.all(np.diff(nodes) > 0), 'Invalid reference shapes')
            require(abs(nodes[0]) < 1e-12 and abs(nodes[-1]-params['length']) < 1e-12, 'Reference span mismatch')
        references[index] = result
        pins[index] = dict(cache=row['cache'], sha256=row['sha256'])
    require(set(references) == expected_all and len(references) == 672, 'Incomplete reference coverage')
    rows = []
    for k in sorted(expected, key=str):
        exact = np.asarray(references[k, RHO, None]['frequencies_Hz'])
        energy = np.asarray([references[k, RHO, n]['frequencies_Hz'] for n in (64, 128, 256)])
        signed = energy/exact-1
        rows.append(dict(configuration=list(k), density=RHO, frequencies_Hz=exact.tolist(),
                         relative_energy_errors=abs(signed).tolist(), signed_relative_energy_errors=signed.tolist(),
                         nonmonotonic_error_modes=(np.where(np.any(np.diff(abs(signed), axis=0) >= 0, axis=0))[0]+1).tolist(),
                         maximum_boundary_singular_ratio=max(v['relative_boundary_singular_value'] for v in references[k, RHO, None]['boundary_checks']),
                         caches=[pins[k, RHO, n] for n in (64, 128, 256, None)]))
    return references, pins, rows


def observations_from_table(table, table_sha):
    observations, not_clear, seen = [], [], set()
    labels = ('first_bending', 'second_bending', 'first_torsional')
    require(len(table['records']) == 49, 'Primary record count changed')
    for record_index, record in enumerate(table['records']):
        position = record['span_position_in_from_root']
        config_id = f"{record['variant']}:{position}"
        phases = set()
        for observation_index, item in enumerate(record['zero_airspeed_observations']):
            phase = item['phase']
            require(phase in ('before_run', 'after_run', 'unloaded_control_after_weight_6_run',
                              'unloaded_control_after_weight_7d_run') and phase not in phases,
                    'Duplicate/invalid observation phase')
            phases.add(phase)
            observation_id = f"{config_id}:run-{record['run']}:{phase}"
            require(observation_id not in seen and item['indicated_airspeed_fps'] == 0, 'Invalid zero-speed observation')
            seen.add(observation_id)
            cells = item['frequencies']
            require(set(cells) == set(labels), 'Primary frequency labels changed')
            for label, cell in cells.items():
                if cell['value_hz'] is None:
                    require(cell['status'] == 'source_says_not_clear' and cell['printed'] == 'Not clear', 'Unexpected missing frequency cell')
                    not_clear.append(dict(observation_id=observation_id, run=record['run'], variant=record['variant'],
                                          position_in_from_root=position, phase=phase, label=label, cell=cell,
                                          table_sha256=table_sha, record_index=record_index, source=record['source']))
                else:
                    require(np.isfinite(cell['value_hz']) and cell['value_hz'] > 0, 'Invalid measured frequency')
            complete = all(v['value_hz'] is not None for v in cells.values())
            ordered = sorted((dict(source_printed_label=label, **cell) for label, cell in cells.items()),
                             key=lambda cell: cell['value_hz']) if complete else None
            observations.append(dict(observation_id=observation_id, configuration_id=config_id,
                run=record['run'], variant=record['variant'], position_in_from_root=position, phase=phase,
                record_index=record_index, observation_index=observation_index,
                printed_mode_cells=cells, ordered_triplet=ordered, complete_triplet=complete,
                included_in_spectral_comparison=complete, source=record['source'], table_sha256=table_sha,
                zero_airspeed_fields={k:v for k,v in item.items() if k != 'frequencies'},
                separate_test_freon_12_percent=record['freon_12_percent_at_test'],
                separate_test_medium_interpretation=record['test_medium_interpretation'],
                separate_test=record['test'], remarks=record['remarks']))
    require(len(observations) == 78 and sum(r['complete_triplet'] for r in observations) == 72 and len(not_clear) == 6,
            'Primary observation/complete-triplet/Not-clear counts changed')
    require({phase:sum(r['phase'] == phase for r in observations) for phase in {r['phase'] for r in observations}} ==
            dict(before_run=42, after_run=34, unloaded_control_after_weight_6_run=1,
                 unloaded_control_after_weight_7d_run=1), 'Primary phase counts changed')
    require(len({(r['variant'], r['position_in_from_root']) for r in observations}) == 42, 'Primary configuration count changed')
    return observations, not_clear


def experimental_comparison(observations, native, rejections, audit_errors):
    predictions = {(key(r['specification']), r['specification']['panels']): r for r in native}
    rejected = {(key(r['specification']), r['specification']['panels']) for r in rejections}
    invalid = {(key(r['specification']), r['specification']['panels']) for r in audit_errors}
    residuals, missing = [], []
    for observation in observations:
        if not observation['complete_triplet']:
            continue
        for endpoint in ENDPOINTS:
            for panels in PANELS:
                index = (observation['variant'], observation['position_in_from_root'], endpoint), panels
                if index not in predictions:
                    reason = 'rejected' if index in rejected else 'cache_audit_error' if index in invalid else 'not_yet_reported'
                    missing.append(dict(observation_id=observation['observation_id'], icc_endpoint=endpoint, panels=panels, reason=reason))
                    continue
                row = predictions[index]
                for rank, (cell, frequency) in enumerate(zip(observation['ordered_triplet'], row['frequencies_Hz'][:3]), 1):
                    measured = cell['value_hz']
                    residuals.append(dict(observation_id=observation['observation_id'], run=observation['run'],
                        configuration_id=observation['configuration_id'], phase=observation['phase'],
                        icc_endpoint=endpoint, panels=panels, spectral_rank=rank,
                        source_printed_label=cell['source_printed_label'], source_cell_status=cell['status'],
                        observed_frequency_Hz=measured, native_frequency_Hz=frequency,
                        native_minus_observed_Hz=frequency-measured, relative_discrepancy_percent=100*(frequency/measured-1),
                        source_sha256=row['source_sha256'], native_cache=row['cache'], native_cache_sha256=row['cache_sha256'],
                        table_sha256=observation['table_sha256'], record_index=observation['record_index'],
                        source_pdf_page_1_based=observation['source']['pdf_page_1_based']))
    require(len(residuals)+3*len(missing) == 1296, 'Experimental coverage accounting mismatch')
    summaries = []
    for endpoint in ENDPOINTS:
        for panels in PANELS:
            rows = [r for r in residuals if r['icc_endpoint'] == endpoint and r['panels'] == panels]
            values = np.array([r['relative_discrepancy_percent'] for r in rows])
            summaries.append(dict(icc_endpoint=endpoint, panels=panels, scalar_comparisons=len(rows), expected_scalar_comparisons=216,
                mean_absolute_discrepancy_percent=float(np.mean(abs(values))) if rows else None,
                median_absolute_discrepancy_percent=float(np.median(abs(values))) if rows else None,
                maximum_absolute_discrepancy_percent=float(np.max(abs(values))) if rows else None,
                largest_discrepancy=max(rows, key=lambda r:abs(r['relative_discrepancy_percent'])) if rows else None))
    return dict(all_observations=observations, scalar_comparisons=len(residuals), expected_scalar_comparisons=1296,
                individual_spectral_residuals=residuals, missing_triplet_comparisons=missing, summary=summaries)


def metric_summary(rows, count):
    entries = [(r, i) for r in rows for i in range(count)]
    if not entries:
        return dict(states=0, compared_modes=0, maximum_absolute_relative_frequency_error=None, minimum_kinetic_MAC=None)
    worst_f = max(entries, key=lambda x:x[0]['relative_frequency_errors'][x[1]])
    worst_s = min(entries, key=lambda x:x[0]['kinetic_shape_assurance'][x[1]])
    return dict(states=len(rows), compared_modes=len(entries),
        maximum_absolute_relative_frequency_error=worst_f[0]['relative_frequency_errors'][worst_f[1]],
        minimum_kinetic_MAC=worst_s[0]['kinetic_shape_assurance'][worst_s[1]],
        largest_frequency_error=dict(specification=worst_f[0]['specification'], frequency_rank=worst_f[1]+1),
        smallest_MAC=dict(specification=worst_s[0]['specification'], frequency_rank=worst_s[1]+1))


def save_csv(path, rows):
    with path.open('w', newline='') as stream:
        if rows:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reference', type=Path)
    parser.add_argument('--allow-incomplete', action='store_true')
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    require(not args.output.exists(), 'Use a new --output path to preserve previous reports')
    snapshots = args.output.parent/'snapshots'
    snapshots.mkdir(exist_ok=True)
    script_snapshot = snapshots/f'{Path(__file__).stem}-{sha(__file__)}.py'
    script_snapshot.write_bytes(Path(__file__).read_bytes())
    paths = [args.work/f'primary-air-{e}.json' for e in ENDPOINTS]
    reference_path = args.reference or args.work/'primary-reference-reciprocal.json'
    table_path = ROOT/'.reference/isae-st4-experiment-inputs/primary-table.json'
    loaded, report_pins = {}, {}
    for path in [*paths, reference_path, table_path]:
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        snapshot = snapshots/f'{path.stem}-{digest}.json'
        if snapshot.exists():
            require(snapshot.read_bytes() == content, 'Snapshot collision')
        else:
            snapshot.write_bytes(content)
        loaded[path] = json.loads(content)
        report_pins[path.name] = dict(path=str(path.resolve()), sha256=digest, snapshot=str(snapshot.resolve()))
    reports = [loaded[p] for p in paths]
    reference_report, table = loaded[reference_path], loaded[table_path]
    pdf_path = ROOT/'.reference/isae-st4-primary'/Path(table['source_pdf']['path']).name
    require(sha(pdf_path) == table['source_pdf']['sha256'], 'Primary PDF hash mismatch')
    require(all(r['status'] in ('RUNNING', TERMINAL) and r['requested'] == 126 and r['density'] == RHO for r in reports),
            'Unexpected air report state, density or request count')
    pins = provenance()
    air_pins = {**pins, 'verify-isae-st4-primary-air.py':sha(ROOT/'scripts/verify-isae-st4-primary-air.py')}
    reference_sources = ('verify-isae-st4-primary-reference.py', 'isae_st4_reference.py',
                         'isae_st4_loaded_reference.py', 'isae_st4_loaded_transfer.py')
    reference_sources = {**pins, **{name:sha(ROOT/'scripts'/name) for name in reference_sources}}
    require(all(r['scripts_and_inputs'] == air_pins for r in reports), 'Air source/input provenance mismatch or omitted pin')
    require(reference_report['scripts_and_inputs'] == reference_sources, 'Reference source/input provenance mismatch or omitted pin')
    modules = {p.name:sha(p) for p in sorted((ROOT/'openswing').glob('*.py'))}
    require(len(modules) == 98 and all(r['modules'] == modules for r in reports), 'Expected frozen 98-module native identity')
    expected = {key(dict(**case, icc_endpoint=e)):dict(**case, icc_endpoint=e) for case in configurations() for e in ENDPOINTS}
    require(len(expected) == 84, 'Primary configuration count mismatch')
    chord = inputs()[0]['wing_primary']['chord_m']
    references, reference_pins, reference_rows = audit_references(reference_report, expected, chord)
    native, rejected, audit_errors, seen, groups = [], [], [], set(), {}
    expected_native = {(k, n) for k in expected for n in PANELS}
    for endpoint, report in zip(ENDPOINTS, reports):
        for row in report['runs']:
            spec = row['specification']; k = key(spec); index = k, spec['panels']
            require(index in expected_native and index not in seen and k[2] == endpoint, 'Unexpected/duplicate native case')
            require({k:v for k,v in spec.items() if k != 'panels'} == expected[k], 'Native primary specification mismatch')
            require(row['status'] in ('computed', 'rejected'), 'Nonterminal native row')
            seen.add(index)
            stage = 'cache_identity'
            try:
                cache = read(ROOT/row['cache'], row['sha256'])
                identity = cache['identity']; params = parameters(spec)
                settings = dict(frame='fixed', count=12, shift=[-.1, 0.], method='dense', gravity=[0., 0., params['gravity']],
                                matrices=True, quiescent_density=RHO)
                require(Path(row['cache']).stem == hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest(), 'Native identity filename mismatch')
                require(identity['specification'] == spec and identity['modules'] == modules and identity['settings'] == settings,
                        'Native source/settings identity mismatch')
                require(identity['scripts_and_inputs'] == report['scripts_and_inputs'], 'Native input pins mismatch')
                require(cache['source'] == source(spec) and identity['source_sha256'] == hashlib.sha256(cache['source'].encode()).hexdigest(),
                        'Native source bytes mismatch')
                require(cache['parameters'] == params and cache['status'] == row['status'], 'Native parameters/status mismatch')
                if cache['status'] == 'rejected':
                    rejected.append(dict(specification=spec, cache=row['cache'], sha256=row['sha256'], error=cache['error']))
                    continue
                stage = 'fluid_and_full_pencil'
                data = cache['result']; validate_fluid(data, settings, spec['panels'])
                matrix_path = ROOT/cache['matrices']['path']
                require(sha(matrix_path) == cache['matrices']['sha256'], 'Matrix hash mismatch')
                backward, pairing, conjugate_error = pencil_errors(data, matrix_path)
                stage = 'frequency_and_shape_comparison'
                modes = sorted((v for v in data['modes'] if v['eigenvalue'][1] > 0), key=lambda v:v['frequency'])
                require(len(modes) == 6, 'Expected six positive roots')
                frequency = np.asarray([v['frequency'] for v in modes])
                require(np.isfinite(frequency).all() and np.all(frequency > 0) and np.all(np.diff(frequency) > 0), 'Invalid native frequencies')
                nodes, shapes, shape_map_errors = native_shapes(data, modes, params)
                air_params = dict(params, air_mass=np.pi*RHO*chord**2/4, air_ip=np.pi*RHO*chord**4/128, air_x=chord/2)
                assurance = mac_matrix(nodes, shapes, references[k, RHO, 256], air_params)
                require(assurance.shape == (6, 6) and np.isfinite(assurance).all()
                        and np.all(assurance >= 0) and np.all(assurance <= 1+1e-10), 'Invalid kinetic MAC')
                exact = np.asarray(references[k, RHO, None]['frequencies_Hz'])
                signed = frequency/exact-1
                result = dict(specification=spec, cache=row['cache'], cache_sha256=row['sha256'], matrices=cache['matrices'],
                    source_sha256=identity['source_sha256'], density=RHO, settings=settings, air_kinetic_parameters=air_params,
                    reference_FE256=reference_pins[k, RHO, 256], reference_continuous=reference_pins[k, RHO, None],
                    frequencies_Hz=frequency.tolist(), continuous_frequencies_Hz=exact.tolist(),
                    signed_frequency_errors_Hz=(frequency-exact).tolist(), signed_relative_frequency_errors=signed.tolist(),
                    relative_frequency_errors=abs(signed).tolist(), kinetic_shape_assurance=np.diag(assurance).tolist(),
                    kinetic_shape_assurance_matrix=assurance.tolist(), best_reference_mode_1based=(np.argmax(assurance, axis=1)+1).tolist(),
                    full_dimension=data['diagnostics']['full_dimension'], finite_dimension=data['diagnostics']['finite_dimension'],
                    base_residual=data['diagnostics']['base_residual'], full_pencil_backward_errors=backward.tolist(),
                    normalization_errors=pairing.tolist(), conjugate_pole_max_error=conjugate_error,
                    direct_state_output_mapping_errors=shape_map_errors, gravity_body=data['base']['gravity_body'], seconds=cache['seconds'])
                finite_output(result)
                native.append(result); groups.setdefault(k, []).append(result)
            except (AssertionError, ValueError, KeyError, TypeError, OSError, IndexError) as error:
                audit_errors.append(dict(specification=spec, cache=row['cache'], sha256=row['sha256'], reported_status=row['status'], stage=stage,
                                         error=type(error).__name__+': '+str(error)))
    for report in reports:
        if report['status'] == TERMINAL:
            require(len(report['runs']) == report['requested'] and report['counts'] == {
                status:sum(r['status'] == status for r in report['runs']) for status in ('computed', 'rejected')}, 'Terminal report count mismatch')
    complete = seen == expected_native and all(r['status'] == TERMINAL for r in reports)
    refinement, partial = [], []
    for k in sorted(expected, key=str):
        group = sorted(groups.get(k, []), key=lambda r:r['specification']['panels'])
        if [r['specification']['panels'] for r in group] != list(PANELS):
            partial.append(dict(configuration=list(k), available_panels=[r['specification']['panels'] for r in group]))
            continue
        errors = np.asarray([r['relative_frequency_errors'] for r in group])
        refinement.append(dict(configuration=list(k), panels=list(PANELS), relative_frequency_errors=errors.tolist(),
            signed_relative_frequency_errors=[r['signed_relative_frequency_errors'] for r in group],
            nonmonotonic_modes=(np.where(np.any(np.diff(errors, axis=0) >= 0, axis=0))[0]+1).tolist(),
            nonmonotonic_steps=[dict(from_panels=PANELS[j], to_panels=PANELS[j+1], modes=(np.where(np.diff(errors, axis=0)[j] >= 0)[0]+1).tolist()) for j in (0, 1)]))
    observations, not_clear = observations_from_table(table, report_pins[table_path.name]['sha256'])
    experiment = experimental_comparison(observations, native, rejected, audit_errors)
    experiment.update(not_clear_cells=not_clear, source_pdf=table['source_pdf'], source_semantics=table['semantics'])
    fine = [r for r in native if r['specification']['panels'] == 32]
    summary = dict(first_three_N32=metric_summary(fine, 3), all_six_N32=metric_summary(fine, 6),
        first_three_all_meshes=metric_summary(native, 3), all_six_all_meshes=metric_summary(native, 6),
        maximum_full_pencil_backward_error=float(max((np.max(r['full_pencil_backward_errors']) for r in native), default=0)),
        maximum_normalization_error=max((max(r['normalization_errors']) for r in native), default=0),
        maximum_base_residual=max((r['base_residual'] for r in native), default=0),
        maximum_conjugate_pole_error=max((r['conjugate_pole_max_error'] for r in native), default=0),
        maximum_FE256_relative_frequency_error=max(max(r['relative_energy_errors'][-1]) for r in reference_rows),
        maximum_continuous_boundary_singular_ratio=max(r['maximum_boundary_singular_ratio'] for r in reference_rows))
    checks = dict(no_rejections=not rejected, all_available_caches_audited=not audit_errors,
        all_six_frequency_errors_decrease_in_complete_groups=all(not r['nonmonotonic_modes'] for r in refinement),
        full_pencil_backward_errors_below_1e_9=bool(native) and summary['maximum_full_pencil_backward_error'] < 1e-9,
        normalization_errors_below_1e_7=bool(native) and summary['maximum_normalization_error'] < 1e-7,
        base_residuals_below_1e_8=bool(native) and summary['maximum_base_residual'] < 1e-8,
        conjugate_pole_errors_below_1e_8=bool(native) and summary['maximum_conjugate_pole_error'] < 1e-8,
        FE256_frequency_errors_below_1e_4=summary['maximum_FE256_relative_frequency_error'] < 1e-4,
        continuous_boundary_singular_ratios_below_1e_8=summary['maximum_continuous_boundary_singular_ratio'] < 1e-8)
    status = ('PRIMARY_STILL_AIR_COMPARISON_COMPLETE' if all(checks.values()) else
              'PRIMARY_STILL_AIR_COMPARISON_COMPLETE_WITH_DIAGNOSTIC_FLAGS') if complete else 'INCOMPLETE_PRIMARY_STILL_AIR_COMPARISON'
    result = dict(status=status, complete=complete, full_physical_validation=False, accuracy_acceptance_established=False,
        density=RHO, script_sha256=sha(__file__), modules=modules,
        script_source_snapshot=str(script_snapshot.resolve()),
        scripts_and_inputs={**pins, 'isae_st4_reference.py':sha(ROOT/'scripts/isae_st4_reference.py')},
        input_reports=report_pins, runner_statuses={e:r['status'] for e,r in zip(ENDPOINTS, reports)},
        terminal_native_states=len(seen), expected_native_states=252, native_states=len(native),
        rejected=rejected, cache_audit_errors=audit_errors, missing_native_states=[dict(configuration=list(k), panels=n) for k,n in sorted(expected_native-seen, key=str)],
        reference_states=len(references), density_matched_reference_states=336, matched_modes=6*len(native),
        complete_refinement_groups=len(refinement), partial_groups=partial, checks=checks, summary=summary,
        native_rows=native, native_refinement=refinement, independent_refinement=reference_rows, experiment=experiment,
        method=dict(frequency_order_retained=True, kinetic_metric_includes_air=True, nearest_frequency_assignment_used=False,
            frequency_fitting_or_input_tuning_used=False, measured_triplets_averaged=False,
            experimental_comparison='Sort each complete printed B1/B2/T triplet; compare with lowest three computed spectral ranks. Preserve printed labels, phase and every source cell.',
            kinetic_shape_mapping='h=u_y+ea_x*theta_z; dh=-theta_x; phi=theta_z; translations use state_layout translation_scale.',
            kinetic_metric='Distributed structural mass at cg_x, Icc*dh^2, Ip*phi^2, strip-air mass at chord/2 and strip-air pitch inertia, plus exact concentrated point contributions.',
            quadrature='Four-point Gauss on union of native/reference nodes; native nodal linear fields and reference Hermite bending/linear torsion.'),
        limitations=[
            'Density 1.225 kg/m^3 is an explicit assumption, not recovered zero-speed laboratory density. Zero-speed Freon entries and separate flutter-test mixtures remain distinct.',
            'Inviscid incompressible thin-strip added mass includes neither fluid damping nor finite-span, thickness, viscosity, wall or compressibility corrections.',
            'Sectional rotary-inertia endpoints are conditional geometric bounds, not a complete experimental uncertainty interval; fixture and pylon properties remain incompletely specified.',
            'Equivalent point pairs omit unreported pylon bending inertia and spanwise CG offsets; in-plane bending is constrained.',
            'All six numerical frequencies retain order. Low diagonal higher-mode MAC may reflect a near-degenerate pair or exchanged shape order; no relabeling or accuracy-threshold relaxation is applied.',
            'Earlier source-pinned 7f/48 upper N32 controls found mode6/7 individual MAC about0.352, despite pair-space squared principal cosines above0.9998. The mode split and individual shapes were not converged; this is not a blanket explanation for other cases.',
            'The six-root reference cannot diagnose native mode6 versus reference mode7. Dedicated eight-mode pair diagnostics are required for that question.',
            'Residual/reference tolerances are numerical controls. No experimental frequency-error or shape-MAC acceptance threshold has been established.',
            'All72 complete triplets are eligible. Every before/after observation and all6 Not-clear cells remain separate; no missing measurements are inferred.',
        ])
    # Prior pair diagnostics are contextual evidence, not replacements for any
    # current frequency-ordered row, and are optional for portable reproduction.
    prior = args.work/'quiescent-primary/shape-diagnosis.json'
    if prior.exists():
        result['prior_higher_pair_diagnostic'] = dict(path=str(prior.resolve()), sha256=sha(prior),
            scope='Three earlier candidate controls only; not a test of every current configuration.',
            report=read(prior))
    modes_csv = []
    for row in native:
        for i in range(6):
            modes_csv.append(dict(**row['specification'], frequency_rank=i+1, density=RHO,
                native_frequency_Hz=row['frequencies_Hz'][i], continuous_frequency_Hz=row['continuous_frequencies_Hz'][i],
                signed_relative_error=row['signed_relative_frequency_errors'][i], absolute_relative_error=row['relative_frequency_errors'][i],
                diagonal_air_kinetic_MAC=row['kinetic_shape_assurance'][i], best_reference_mode_1based=row['best_reference_mode_1based'][i],
                source_sha256=row['source_sha256'], cache=row['cache'], cache_sha256=row['cache_sha256']))
    outputs = {'modes_csv':args.output.with_name(args.output.stem+'-modes.csv'),
               'experimental_csv':args.output.with_name(args.output.stem+'-experimental.csv')}
    save_csv(outputs['modes_csv'], modes_csv)
    save_csv(outputs['experimental_csv'], experiment['individual_spectral_residuals'])
    result['companion_outputs'] = {k:dict(path=str(p.resolve()), sha256=sha(p)) for k,p in outputs.items()}
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    concise = {k:result[k] for k in ('status', 'complete', 'terminal_native_states', 'native_states', 'complete_refinement_groups', 'checks', 'summary')}
    concise.update(rejections=len(rejected), cache_audit_errors=len(audit_errors), experimental_scalar_comparisons=experiment['scalar_comparisons'])
    args.output.with_suffix('.txt').write_text(json.dumps(concise, indent=2)+'\n')
    print(json.dumps(concise, indent=2))
    if audit_errors:
        return 1
    if not complete and not args.allow_incomplete:
        print('Incomplete snapshot retained; pass --allow-incomplete for an interim audit.', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
