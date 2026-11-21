"""Compare complete FFWT-4 histories at every shared time and material node.

Only saved evidence is read. Segment results are distilled one at a time to
JSONL, so a comparison does not retain two full nonlinear histories in memory.
"""
import argparse
import copy
from decimal import Decimal
import importlib.util
import json
import math
from pathlib import Path

from isae_ffwt4_evidence import KernelArchive, pin, read, require, write

ROOT = Path(__file__).resolve().parents[1]
DT = Decimal('.0149')
LIMIT = .001


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT/'scripts'/file)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


spatial = module('ffwt4_field_mesh', 'assess-isae-ffwt4-spatial.py')
history = module('ffwt4_field_history', 'assess-isae-ffwt4-history-v3.py')


def history_contract(data):
    require(data['status'] == 'HISTORY_ASSESSED' and data['complete'],
            'Complete histories are required for a full-window accuracy verdict')
    divisor = data['divisor']
    require(divisor in (2, 4, 8, 16) and Decimal(data['dt']) == DT/divisor,
            'Unsupported or changed time grid')
    count = 199*divisor
    require(data['accepted_steps'] == data['required_steps'] == count and
            data['rejected_steps'] == 0 and data['physical_solves'] == 0,
            'Incomplete or unassessed history')
    require(set(data['samples']) == {str(i) for i in range(count+1)}, 'Incomplete sample coverage')
    for tick in range(count+1):
        sample = data['samples'][str(tick)]
        require(math.isfinite(sample['time']) and abs(sample['time']-float(tick*DT/divisor)) <= 1e-10,
                'Saved sample clock differs')
        require(math.isfinite(sample['moment']) and math.isfinite(sample['residual']) and
                sample['residual'] <= 1e-8, 'Invalid saved sample')
    require(data['acceptance']['relative_tolerance'] == .05 and
            data['summary']['computed'] == 200 and data['summary']['fixed_history_required'] == 1600,
            'Native scope or allowance changed')


def pairing(kind, nominals, divisors, coarse_stations, fine_stations):
    require(all(d in (2, 4, 8, 16) for d in divisors), 'Unsupported time grid')
    if kind == 'spatial':
        require(nominals[1] == 2*nominals[0] and divisors[0] == divisors[1],
                'Spatial refinement must double only the nominal mesh count')
    else:
        require(kind == 'temporal' and nominals[0] == nominals[1] and divisors[1] == 2*divisors[0],
                'Temporal refinement must halve only the time step')
        require(coarse_stations == fine_stations, 'Time refinement changed material stations')
    for stations in (coarse_stations, fine_stations):
        require(len(stations) > 1 and all(math.isfinite(t) for t in stations) and
                all(b-a > 1e-12 for a, b in zip(stations, stations[1:])), 'Invalid material grid')
    mapping = []
    for station in coarse_stations:
        indices = [i for i, t in enumerate(fine_stations) if abs(t-station) <= 1e-12]
        require(len(indices) == 1, 'A shared material station is missing or duplicated')
        mapping.append(indices[0])
    require(len(set(mapping)) == len(mapping), 'Material mapping is not one-to-one')
    return mapping


def frame_contract(frame, tick, divisor, nodes):
    require(frame['tick'] == tick and math.isfinite(frame['time']) and
            abs(frame['time']-float(tick*DT/divisor)) <= 1e-10, 'Missing, repeated or shifted frame')
    require(math.isfinite(frame['moment']), 'Nonfinite root moment')
    for field in ('displacement', 'rotation_vector'):
        require(len(frame[field]) == nodes, 'Incomplete nodal field')
        lengths = [spatial.norm(vector) for vector in frame[field]]
        require(all(math.isfinite(length) for length in lengths), 'Nonfinite nodal magnitude')
        if field == 'rotation_vector':
            require(max(lengths) < .1, 'Rotation-vector subtraction requires small rotations')


def compare_frames(coarse_frames, fine_frames, *, kind, nominals, divisors, coarse_stations, fine_stations):
    """A streamed full-window comparison; no interpolation or output fitting."""
    mapping = pairing(kind, nominals, divisors, coarse_stations, fine_stations)
    ratio = divisors[1]//divisors[0]
    coarse = iter(coarse_frames)
    gates = {name: dict(maximum_absolute_difference=0., fine_scale=0., worst_coarser_tick=0,
                        worst_time=0., worst_station=0.)
             for name in ('root_moment', 'gust_increment', 'displacement', 'rotation_vector')}
    matched = 0
    seen = 0
    for tick, fine in enumerate(fine_frames):
        require(tick <= 199*divisors[1], 'Unexpected trailing fine frames')
        frame_contract(fine, tick, divisors[1], len(fine_stations))
        seen += 1
        if tick % ratio:
            continue
        current = next(coarse, None)
        require(current is not None, 'Incomplete coarser history')
        ctick = tick//ratio
        frame_contract(current, ctick, divisors[0], len(coarse_stations))
        if ctick == 0:
            c0, f0 = current['moment'], fine['moment']
        matched += 1
        for name, gate in gates.items():
            if name in ('root_moment', 'gust_increment'):
                c = current['moment']-(c0 if name == 'gust_increment' else 0.)
                f = fine['moment']-(f0 if name == 'gust_increment' else 0.)
                delta, scale, station = abs(c-f), abs(f), 0.
            else:
                scale = max(map(spatial.norm, fine[name]))
                differences = [spatial.norm([v[j]-fine[name][index][j] for j in range(3)])
                               for v, index in zip(current[name], mapping)]
                worst = max(range(len(differences)), key=differences.__getitem__)
                delta, station = differences[worst], coarse_stations[worst]
            require(math.isfinite(delta) and math.isfinite(scale), 'Nonfinite comparison magnitude')
            gate['fine_scale'] = max(gate['fine_scale'], scale)
            if delta > gate['maximum_absolute_difference']:
                gate.update(maximum_absolute_difference=delta, worst_coarser_tick=ctick,
                            worst_time=float(ctick*DT/divisors[0]), worst_station=station)
    require(seen == 199*divisors[1]+1 and matched == 199*divisors[0]+1 and next(coarse, None) is None,
            'Incomplete or oversized comparison window')
    for gate in gates.values():
        require(gate['fine_scale'] > 0, 'Zero scale cannot establish a relative accuracy gate')
        gate.update(maximum_percent_of_scale=100*gate['maximum_absolute_difference']/gate['fine_scale'],
                    relative_limit=LIMIT, passed=gate['maximum_absolute_difference'] <= LIMIT*gate['fine_scale'])
    return dict(kind=kind, nominal=nominals, divisors=divisors, common_times=matched,
                common_nodes=len(mapping), gates=gates, passed=sum(g['passed'] for g in gates.values()), required=4)


def extract(data, plans, reports, destination):
    """Retain one raw segment at a time; independently reconstruct deformation."""
    source = read(plans[0]['initial_request']['path'])['source']
    initial = read(plans[0]['initial_result']['path'])
    identity = initial['equilibrium_state']['identity']
    mesh = spatial.mesh_fields(initial, data['nominal'], source)
    del initial
    accepted = 0
    previous = None
    boundaries = 0
    with destination.open('x') as output:
        for segment, (plan, report) in enumerate(zip(plans, reports)):
            start, end = plan['start_step'], plan['end_step']
            require(start == accepted and 1 <= end-start <= 10, 'Noncontiguous saved segments')
            raw = read(report['result']['path'])
            require(raw['restart_context']['identity'] == identity and
                    len(raw['snapshots']) == end-start+1 and raw['accepted_steps'] == end-start and
                    raw['rejected_steps'] == 0 and raw['converged'], 'Incomplete saved segment or changed mesh')
            for offset, snapshot in enumerate(raw['snapshots']):
                tick = start+offset
                moment = history.snapshot_value(snapshot, tick, data['divisor'])
                saved = data['samples'][str(tick)]
                require(abs(moment-saved['moment']) <= 1e-8 and abs(snapshot['time']-saved['time']) <= 1e-10,
                        'History assessment differs from the saved snapshot')
                network = snapshot['restart']['state']['network']
                wrapper = dict(equilibrium_state=dict(identity=identity, positions=network['positions'],
                               rotations=network['rotations']), sensors=snapshot['sensors'])
                fields = spatial.mesh_fields(wrapper, data['nominal'], source)
                frame = dict(tick=tick, time=snapshot['time'], moment=moment,
                             displacement=fields['displacement'], rotation_vector=fields['rotation_vector'])
                if segment and offset == 0:
                    require(previous['tick'] == tick and abs(previous['moment']-moment) <= 1e-8,
                            'Continuation changed the shared root moment')
                    for field in ('displacement', 'rotation_vector'):
                        require(all(spatial.norm([a-b for a, b in zip(v, w)]) <= 1e-12
                                    for v, w in zip(previous[field], frame[field])),
                                'Continuation changed the shared nodal state')
                    boundaries += 1
                else:
                    output.write(json.dumps(frame, allow_nan=False, separators=(',', ':'))+'\n')
                previous = frame
            del raw
            accepted = end
    require(accepted == data['required_steps'], 'Extraction ended before the required horizon')
    return dict(file=pin(destination), nodes=mesh['nodes'], stations=mesh['stations'],
                frames=accepted+1, continuation_boundaries=boundaries)


def frames(path):
    with Path(path).open() as stream:
        for line in stream:
            yield json.loads(line)


def assess(coarse_path, fine_path, kind, output):
    data = [read(coarse_path), read(fine_path)]
    for value in data:
        history_contract(value)
    require(not output.exists(), 'Preserve previous comparison artifacts')
    initial_plans = [read(value['plans'][0]['path']) for value in data]
    archive = KernelArchive(data[0]['kernel_archive']['path'], initial_plans[0]['kernel_pins'])
    verified = {}
    plans, reports = [], []
    for value in data:
        require(value['kernel_archive'] == archive.manifest_pin, 'Changed equation archive')
        records = value['inputs']+value['plans']+value['reports']+[value[key] for key in
                  ('helper', 'core_helper', 'evidence_helper', 'terminal_journal')]
        for record in records:
            if record['path'] in verified:
                require(verified[record['path']] == record, 'Conflicting evidence hashes')
            else:
                require(pin(record['path']) == record, 'Changed saved evidence: '+record['path'])
                verified[record['path']] = record
        ps = [read(p['path']) for p in value['plans']]
        rs = [read(r['path']) for r in value['reports']]
        require(len(ps) == len(rs) == value['segments'], 'Incomplete segment inventory')
        receipts = read(value['terminal_journal']['path'])['jobs']
        receipts = {r['folder']: r for r in receipts}
        require(all(receipts.get(Path(p['path']).parent.name, {}).get('exit_code') == 0 for p in value['plans']),
                'Missing successful process receipts')
        plans.append(ps)
        reports.append(rs)
    for key in ('source_pins', 'kernel_pins', 'accuracy_gate'):
        require(initial_plans[0][key] == initial_plans[1][key], 'Refinement changed '+key)
    require(initial_plans[0]['accuracy_gate']['relative'] == LIMIT, 'Numerical accuracy allowance changed')
    requests = [read(p['initial_request']['path']) for p in initial_plans]
    expected = copy.deepcopy(requests[0])
    if kind == 'spatial':
        n = data[1]['nominal']
        expected['panels'] = dict(default=n, beams={'1': dict(count=n, spacing='cosine')})
    require(expected == requests[1], 'Refinement changed physical inputs')
    if kind == 'temporal':
        for key in ('initial_plan', 'initial_request', 'initial_result', 'initial_report', 'initial_helper'):
            require(initial_plans[0][key] == initial_plans[1][key], 'Time refinement changed the initial equilibrium')
        require(abs(data[0]['samples']['0']['moment']-data[1]['samples']['0']['moment']) <= 1e-8,
                'Time refinement changed the initial root moment')
    output.mkdir(parents=True)
    extracts = [extract(d, ps, rs, output/(name+'.jsonl'))
                for d, ps, rs, name in zip(data, plans, reports, ('coarser-fields', 'finer-fields'))]
    result = compare_frames(*(frames(e['file']['path']) for e in extracts), kind=kind,
        nominals=[d['nominal'] for d in data], divisors=[d['divisor'] for d in data],
        coarse_stations=extracts[0]['stations'], fine_stations=extracts[1]['stations'])
    for record in verified.values():
        require(pin(record['path']) == record, 'Evidence changed during field comparison')
    result.update(status='FULL_HISTORY_FIELDS_ASSESSED', assessments=[pin(coarse_path), pin(fine_path)],
        extracts=extracts, inputs=list(verified.values()), helper=pin(__file__),
        field_helper=pin(spatial.__file__), history_helper=pin(history.__file__),
        evidence_helper=pin(ROOT/'scripts/isae_ffwt4_evidence.py'), physical_solves=0,
        native_fraction_change=0, full_family_validated=False,
        qualifications=[
            'Complete 0..2.9651 s histories are required; a prefix cannot pass these accuracy gates.',
            'Every shared physical time and every shared material node is compared without interpolation.',
            'Scales are finer-grid maxima over shared times; nodal scales use every fine-grid material node.',
            'Displacement excludes the jig geometry. Rotation-vector subtraction requires norms below 0.1 rad.',
            'Root-moment increments subtract each history\'s own initial value; a steady offset cannot hide transient error.',
            'Strict 0.1% numerical gates are separate from the 5% native allowance; repeated targets add no coverage.',
            'One pair measures refinement change, not a proven absolute error bound. Other fields and histories remain open.'])
    write(output/'assessment.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--coarser', type=Path, required=True)
    parser.add_argument('--finer', type=Path, required=True)
    parser.add_argument('--kind', choices=('spatial', 'temporal'), required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    result = assess(args.coarser, args.finer, args.kind, args.output_dir)
    print(json.dumps({k: result[k] for k in ('status', 'kind', 'common_times', 'common_nodes', 'gates', 'passed', 'required')}))


if __name__ == '__main__':
    main()
