"""Saved-only boom/fin continuum comparison; imports no physical model or solver."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import time
import traceback
import numpy as np


def pin(path):
    data = Path(path).read_bytes()
    return dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def scalar(value):
    value = complex(value)
    return dict(real=value.real, imag=value.imag)


def channel(actual, reference):
    error = actual-reference
    denominator = float(abs(reference))
    return dict(actual=scalar(actual), reference=scalar(reference), error=scalar(error),
                absolute_error=float(abs(error)),
                relative_error=None if denominator == 0 else float(abs(error)/denominator))


def relative_motion(actual, reference, divisors):
    error = abs((actual-reference)/divisors[:, None])
    denominator = np.max(abs(reference/divisors[:, None]), axis=(0, 1))
    numerator = np.max(error, axis=(0, 1))
    return [dict(absolute_scaled_error=float(numerator[k]),
                 reference_scaled_infinity_norm=float(denominator[k]),
                 relative_error=None if denominator[k] == 0 else float(numerator[k]/denominator[k]))
            for k in range(actual.shape[-1])]


def matching_index(stations, station):
    tolerance = 64*np.finfo(float).eps*max(1., abs(station))
    matches = np.flatnonzero(abs(stations-station) <= tolerance)
    assert len(matches) == 1, (station, tolerance, matches.tolist())
    return int(matches[0])


def rotation_error(actual, reference):
    relative = np.einsum('nij,nkj->nik', actual, reference)
    vee = np.stack([relative[:, 2, 1]-relative[:, 1, 2],
                    relative[:, 0, 2]-relative[:, 2, 0],
                    relative[:, 1, 0]-relative[:, 0, 1]], axis=1)/2
    sine = np.sqrt(np.sum(vee**2, axis=1))
    cosine = np.clip((np.trace(relative, axis1=1, axis2=2)-1)/2, -1., 1.)
    return np.arctan2(sine, cosine)


def base_errors(actual_r, actual_R, reference_r, reference_R):
    return dict(maximum_position_error_ft=float(np.max(abs(actual_r-reference_r))),
                maximum_position_error_scaled_by_20=float(np.max(abs(actual_r-reference_r))/20),
                maximum_spatial_rotation_error_rad=float(np.max(rotation_error(actual_R, reference_R))),
                maximum_material_rotation_matrix_entry_error=float(np.max(abs(actual_R-reference_R))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=Path, default=Path('/tmp/openswing-daedalus-boom-fin-20261024'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    stage = args.stage.resolve()
    output = (args.output or stage/'review').resolve()
    output.mkdir(parents=True, exist_ok=True)
    target = output/'comparison.json'
    if target.exists():
        raise FileExistsError('Retain the prior comparison; choose a new output directory.')
    pins = {}

    def record(path):
        path = Path(path)
        value = pin(path)
        assert str(path) not in pins or pins[str(path)] == value
        pins[str(path)] = value
        return path

    def read(path):
        return json.loads(record(path).read_text())

    def arrays(path):
        with np.load(record(path), allow_pickle=False) as data:
            values = {key: data[key].copy() for key in data.files}
        assert all(np.isfinite(value).all() for value in values.values()), str(path)
        return values

    started = time.monotonic()
    result = dict(status='STARTED', script_pin=pin(__file__),
                  operations=dict(physical_evaluations=0, system_matrix_products=0,
                                  factorizations=0, solves=0, production_imports=0,
                                  saved_array_reductions=True, spatial_coordinate_conversions=True))
    try:
        plan = read(stage/'production/comparison-plan.json')
        oracle_plan = read(stage/'oracle/plan.json')
        for sourceplan in (plan, oracle_plan):
            for path, expected in sourceplan['pins'].items():
                assert pin(record(path)) == expected, path
        proposal = read(stage/'production/proposal.json')
        for path, expected in proposal['pins'].items():
            assert pin(record(path)) == expected, path
        fixture = read(stage/'production/continuum-fixture.json')
        summary = read(stage/'production/summary.json')
        oracle_closeout = read(stage/'oracle/session-closeout.json')
        assert oracle_closeout['all_owned_processes_terminal_reaped']
        frequencies = plan['frequencies_Hz']
        assert frequencies == oracle_plan['frequencies_Hz']
        assert plan['finest_relative_error_gate'] == oracle_plan['gates']['finest_production_relative_motion']
        assert plan['continuum_tightening_relative_gate'] == oracle_plan['gates']['continuum_tightening_relative_motion']
        divisors = np.array(plan['motion_divisors'])
        components = plan['motion_components']
        result.update(comparison_plan_pin=pin(stage/'production/comparison-plan.json'),
                      oracle_plan_pin=pin(stage/'oracle/plan.json'),
                      gates=dict(finest_relative_error=plan['finest_relative_error_gate'],
                                 continuum_tightening_relative=plan['continuum_tightening_relative_gate']),
                      formula=plan['primary_comparison'], motion_divisors=divisors.tolist(),
                      inputs=plan['inputs'], frequencies_Hz=frequencies,
                      continuum_tightening=[], base_comparisons=[], samples=[], reactions=[],
                      limits=[plan['interpretation'],
                              'Reaction and individual-channel errors are reported without an invented pass threshold.',
                              'All errors are from saved responses; no new equation solve or physical evaluation.',
                              'Near-zero component ratios are not floored. An exactly zero reference gives null relative error.',
                              'Base positions and material triads are compared; discontinuous base internal-load traces are excluded.'])
        Q = np.array(fixture['gauge']['cut']['rotation'])
        cutr = np.array(fixture['gauge']['cut']['position'])
        cutj = np.array(fixture['gauge']['cut']['jig_position'])
        oracle = {}
        for tolerance in ('coarse', 'tight'):
            execution = read(stage/f'oracle/execution-{tolerance}.json')
            assert execution['exit_code'] == 0 and execution['reaped'] and not execution['timed_out']
            report = read(stage/f'oracle/results/{tolerance}/report.json')
            assert report['status'] == 'PASS_CONTINUUM_EXECUTION'
            oracle[tolerance] = [arrays(stage/f'oracle/results/{tolerance}/response-{i}.npz') for i in range(len(frequencies))]
        for fi, frequency in enumerate(frequencies):
            tight, coarse = oracle['tight'][fi], oracle['coarse'][fi]
            motions = {}
            for label, packet in (('tight', tight), ('coarse', coarse)):
                motions[label] = np.concatenate([packet[name+'_states_physical'][:, :6] for name in ('boom', 'upper', 'lower')])
            for name in ('boom', 'upper', 'lower'):
                assert np.array_equal(tight[name+'_stations'], coarse[name+'_stations'])
            for inp, metric in enumerate(relative_motion(motions['coarse'], motions['tight'], divisors)):
                result['continuum_tightening'].append(dict(frequency_Hz=frequency, input=inp, **metric,
                    gate=plan['continuum_tightening_relative_gate'],
                    passed=metric['relative_error'] is not None and metric['relative_error'] <= plan['continuum_tightening_relative_gate']))
        c0, t0 = oracle['coarse'][0], oracle['tight'][0]
        coarse_base = np.concatenate([c0[name+'_base'] for name in ('boom', 'upper', 'lower')])
        tight_base = np.concatenate([t0[name+'_base'] for name in ('boom', 'upper', 'lower')])
        result['continuum_base_tightening'] = base_errors(
            cutr+np.einsum('ij,nj->ni', Q, coarse_base[:, :3]-cutj),
            np.einsum('ij,njk->nik', Q, coarse_base[:, 3:12].reshape(-1, 3, 3)),
            cutr+np.einsum('ij,nj->ni', Q, tight_base[:, :3]-cutj),
            np.einsum('ij,njk->nik', Q, tight_base[:, 3:12].reshape(-1, 3, 3)))
        csv_path = output/'channels.csv'
        csv_count = 0
        production_bases = {}
        with csv_path.open('x', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['mesh', 'frequency_Hz', 'input', 'node', 'beam', 'station', 'branch', 'component', 'unit',
                             'production_real', 'production_imag', 'reference_real', 'reference_imag',
                             'error_real', 'error_imag', 'absolute_error', 'relative_error'])
            for level in plan['levels']:
                folder = stage/'production/results'/level
                execution = read(stage/f'production/execution-{level}.json')
                closeout = read(stage/f'production/session-closeout-{level}.json')
                assert execution['exit_code'] == 0 and execution['reaped'] and not execution['timed_out']
                assert closeout['exit_code'] == 0 and closeout['reaped']
                report = read(folder/'report.json')
                assert report['status'] == 'PASS_PRODUCTION_COMPONENT'
                assert pin(folder/'report.json') == closeout['report_pin']
                stations = read(folder/'stations.json')
                geometry = arrays(folder/'loaded-geometry.npz')
                rows = read(folder/'samples.json')
                mapping = {}
                for beam, rowspec in stations.items():
                    for station, node in zip(rowspec['stations'], rowspec['indices']):
                        name = 'boom' if beam == '4' else ('lower' if station < 0 else 'upper')
                        index = matching_index(t0[name+'_stations'], station)
                        mapping[node] = (int(beam), station, name, index)
                assert sorted(mapping) == list(range(report['nodes']))
                refbase = np.array([t0[mapping[i][2]+'_base'][mapping[i][3]] for i in range(report['nodes'])])
                ref_r = cutr+np.einsum('ij,nj->ni', Q, refbase[:, :3]-cutj)
                ref_R = np.einsum('ij,njk->nik', Q, refbase[:, 3:12].reshape(-1, 3, 3))
                material_jig = np.array([fixture['branches'][mapping[i][2]]['materialframeatjig'] for i in range(report['nodes'])])
                prod_R = np.einsum('nij,njk->nik', geometry['physical_rotations'], material_jig)
                prod_r = geometry['physical_positions']
                production_bases[level] = (mapping, prod_r, prod_R)
                result['base_comparisons'].append(dict(mesh=level, nodes=report['nodes'], **base_errors(prod_r, prod_R, ref_r, ref_R)))
                tip_nodes = {name: next(node for node, spec in mapping.items() if spec[0] == beam and spec[1] == station)
                             for name, beam, station in [('boom_tip', 4, 20.), ('upper_tip', 3, 5.), ('lower_tip', 3, -3.5)]}
                for fi, frequency in enumerate(frequencies):
                    assert rows[fi]['frequency_Hz'] == frequency and rows[fi]['available']
                    packet = arrays(folder/f'response-{fi}.npz')
                    actual = packet['nodal_motion_physical']
                    assert actual.shape == (report['nodes'], 6, 2)
                    reference = np.array([oracle['tight'][fi][mapping[i][2]+'_states_physical'][mapping[i][3], :6]
                                          for i in range(report['nodes'])])
                    metrics = relative_motion(actual, reference, divisors)
                    for inp, metric in enumerate(metrics):
                        worst = np.unravel_index(np.argmax(abs((actual[:, :, inp]-reference[:, :, inp])/divisors)), actual.shape[:2])
                        tips = {name: {component: channel(actual[node, k, inp], reference[node, k, inp])
                                      for k, component in enumerate(components)} for name, node in tip_nodes.items()}
                        result['samples'].append(dict(mesh=level, frequency_Hz=frequency, input=inp, **metric,
                            worst_node=int(worst[0]), worst_component=components[worst[1]], tips=tips,
                            critical_upper_tip={k: tips['upper_tip'][k] for k in ('y_displacement', 'z_spatial_rotation')},
                            primary_gate_applies=level == plan['levels'][-1],
                            meets_one_percent=metric['relative_error'] is not None and metric['relative_error'] <= plan['finest_relative_error_gate']))
                        for node in range(report['nodes']):
                            beam, station, name, _ = mapping[node]
                            for k, component in enumerate(components):
                                a, b = actual[node, k, inp], reference[node, k, inp]
                                err = a-b
                                writer.writerow([level, frequency, inp, node, beam, station, name, component,
                                    'ft' if k < 3 else 'rad', a.real, a.imag, b.real, b.imag,
                                    err.real, err.imag, abs(err), '' if abs(b) == 0 else abs(err)/abs(b)])
                                csv_count += 1
                    ref = oracle['tight'][fi]
                    root_b = ref['boom_states_physical'][0]
                    tip_b = ref['boom_states_physical'][-1]
                    root_u, root_l = ref['upper_states_physical'][0], ref['lower_states_physical'][0]
                    expected = {'ground':dict(force=-root_b[6:9], moment=-root_b[9:12]),
                                'joint':dict(force=root_u[6:9]-root_l[6:9], moment=tip_b[9:12],
                                             other_force=-(root_u[6:9]-root_l[6:9]), other_moment=-(root_u[9:12]-root_l[9:12]))}
                    assert sorted(v['kind'] for v in rows[fi]['reactions']) == ['ground', 'joint']
                    for reaction in rows[fi]['reactions']:
                        kind = reaction['kind']
                        for field, wanted in expected[kind].items():
                            measured = np.array(reaction[field]['real'])+1j*np.array(reaction[field]['imag'])
                            for inp in range(2):
                                comps = [channel(measured[k, inp], wanted[k, inp]) for k in range(3)]
                                denom = float(np.max(abs(wanted[:, inp])))
                                result['reactions'].append(dict(mesh=level, frequency_Hz=frequency, input=inp,
                                    kind=kind, field=field, unit='lb ft' if 'moment' in field else 'lb',
                                    components=dict(zip('xyz', comps)), maximum_absolute_error=max(c['absolute_error'] for c in comps),
                                    relative_vector_infinity_error=None if denom == 0 else float(np.max(abs(measured[:, inp]-wanted[:, inp]))/denom)))
        result['base_mesh_changes'] = []
        for old, new in zip(plan['levels'][:-1], plan['levels'][1:]):
            mapping, old_r, old_R = production_bases[old]
            newmapping, new_r, new_R = production_bases[new]
            ids = []
            for node in range(len(mapping)):
                beam, station, _, _ = mapping[node]
                choices = [i for i, item in newmapping.items() if item[0] == beam and abs(item[1]-station) <= 64*np.finfo(float).eps*max(1., abs(station))]
                assert len(choices) == 1
                ids.append(choices[0])
            result['base_mesh_changes'].append(dict(coarse_mesh=old, fine_mesh=new,
                **base_errors(old_r, old_R, new_r[ids], new_R[ids])))
        result['channel_csv'] = dict(path=str(csv_path), rows=csv_count, **pin(csv_path))
        finest = [r for r in result['samples'] if r['primary_gate_applies']]
        result['gate_results'] = dict(continuum_tightening_passed=all(r['passed'] for r in result['continuum_tightening']),
            finest_one_percent_passed=all(r['meets_one_percent'] for r in finest),
            maximum_continuum_tightening_relative=max(r['relative_error'] for r in result['continuum_tightening']),
            maximum_finest_relative_error=max(r['relative_error'] for r in finest),
            per_mesh_maximum_relative_error={level:max(r['relative_error'] for r in result['samples'] if r['mesh'] == level) for level in plan['levels']})
        result['status'] = ('PASS_DECLARED_COMPONENT_COMPARISON_GATES' if result['gate_results']['continuum_tightening_passed']
                            and result['gate_results']['finest_one_percent_passed'] else 'COMPONENT_COMPARISON_FAILURES_RETAINED')
        result['counts'] = dict(mesh_frequency_input_comparisons=len(result['samples']),
                                continuum_tightening_comparisons=len(result['continuum_tightening']),
                                primary_finest_passed=sum(r['meets_one_percent'] for r in finest), primary_finest_total=len(finest),
                                reaction_vector_comparisons=len(result['reactions']), nodal_scalar_rows=csv_count)
        assert all(pin(path) == value for path, value in pins.items()), 'A saved input changed during reduction.'
        result['all_input_pins_unchanged'] = True
    except BaseException as exc:
        result.update(status='REDUCTION_FAILURE_RETAINED', error=type(exc).__name__+': '+str(exc), traceback=traceback.format_exc())
        raise
    finally:
        result.update(input_pins=pins, elapsed_seconds=time.monotonic()-started)
        target.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps({k:result[k] for k in ('status', 'gate_results', 'counts')}, indent=2), flush=True)


if __name__ == '__main__':
    main()
