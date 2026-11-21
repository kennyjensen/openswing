"""Independently assess literal FFWT-4 equilibrium meshes and shared-node fields."""
import argparse
import copy
from decimal import Decimal
import math
from pathlib import Path
import json

from isae_ffwt4_evidence import KernelArchive, pin, read, require, write

ROOT = Path(__file__).resolve().parents[1]


def expected_stations(source, nominal):
    """Independent straight-beam cosine grid plus literal point-mass stations."""
    lines = [line.split('#', 1)[0].strip() for line in source.splitlines()]
    start = next(i for i, line in enumerate(lines) if line.lower() == 'weight')
    block = lines[start+1:]
    block = block[:next(i for i, line in enumerate(block) if line.lower() == 'end')]
    scales = [line for line in block if line.startswith('*')]
    require(len(scales) == 1 and float(scales[0].split()[1]) == 1., 'Weight station scale changed')
    weights = [list(map(float, line.split())) for line in block if line and not line.startswith('*')]
    require(len(weights) == 60 and all(len(row) == 12 and row[0] == 1 and row[5] > 0 for row in weights),
            'Literal fixed-wing point-mass inventory changed')
    mandatory = sorted({-.5, 0., .5} | {row[1] for row in weights})
    require(len(mandatory) == 33, 'Mandatory station inventory changed')
    candidates = sorted(mandatory + [-.5*math.cos(math.pi*i/nominal) for i in range(nominal+1)])
    expected = []
    for t in candidates:
        if not expected or abs(t-expected[-1]) > 1e-12:
            expected.append(t)
    require(len(expected) == nominal+31, 'Unexpected cosine/attachment coincidence')
    return expected


def norm(vector):
    require(len(vector) == 3 and all(math.isfinite(v) for v in vector), 'Invalid vector field')
    return math.sqrt(sum(v*v for v in vector))


def mesh_fields(result, nominal, source):
    state = result['equilibrium_state']
    identity = state['identity']
    stations, indices = identity['stations']['1']
    expected = expected_stations(source, nominal)
    n = len(expected)
    require(len(stations) == n and all(math.isfinite(v) and abs(v-t) <= 1e-12 for v, t in zip(stations, expected)),
            'Saved stations differ from the independent cosine/attachment mesh')
    require(indices == list(range(n)) and identity['elements'] == [[i, i+1] for i in range(n-1)],
            'Mesh topology changed')
    require(len(identity['nodes']) == len(state['positions']) == len(state['rotations']) == n, 'Incomplete nodal state')
    require(all(norm([v[j]-[0., t, 0.][j] for j in range(3)]) <= 1e-12
                for v, t in zip(identity['nodes'], stations)), 'Jig geometry changed')
    displacement = [[p[j]-base[j] for j in range(3)] for p, base in zip(state['positions'], identity['nodes'])]
    rotation = state['rotations']
    for vector in displacement+rotation:
        norm(vector)
    require(max(map(norm, rotation)) < .1, 'Rotation-vector comparison requires this small-rotation regime')
    sensors = [s for s in result['sensors'] if s['index'] == 1]
    require(len(sensors) == 1 and sensors[0]['load_trace'] == 'left', 'Root trace changed')
    moment = sensors[0]['moment_local'][0]
    require(math.isfinite(moment), 'Nonfinite root moment')
    return dict(nominal=nominal, nodes=n, elements=n-1, stations=stations, root_moment=moment,
                displacement=displacement, rotation_vector=rotation)


def compare(coarse, fine):
    require(fine['nominal'] == 2*coarse['nominal'], 'Expected successive nominal mesh doubling')
    mapping = []
    for t in coarse['stations']:
        matches = [i for i, u in enumerate(fine['stations']) if abs(t-u) <= 1e-12]
        require(len(matches) == 1, 'A coarse node is missing or duplicated in the fine mesh')
        mapping.append(matches[0])
    require(len(set(mapping)) == len(mapping), 'Duplicate coarse station')
    gates = {}
    for name in ('root_moment', 'displacement', 'rotation_vector'):
        if name == 'root_moment':
            require(all(math.isfinite(v[name]) for v in (coarse, fine)), 'Invalid root moment')
            delta, scale, worst_station = abs(coarse[name]-fine[name]), abs(fine[name]), 0.
        else:
            require(len(coarse[name]) == len(mapping) and len(fine[name]) == len(fine['stations']), 'Incomplete vector field')
            scale = max(map(norm, fine[name]))
            differences = [norm([v[j]-fine[name][index][j] for j in range(3)])
                           for v, index in zip(coarse[name], mapping)]
            worst = max(range(len(differences)), key=differences.__getitem__)
            delta, worst_station = differences[worst], coarse['stations'][worst]
        require(scale > 0, 'Zero scale cannot establish a relative mesh gate')
        gates[name] = dict(maximum_absolute_change=delta, fine_scale=scale, maximum_percent=100*delta/scale,
                          relative_limit=.001, passed=delta <= .001*scale, worst_station=worst_station)
    return dict(nominal=[coarse['nominal'], fine['nominal']], nodes=[coarse['nodes'], fine['nodes']],
                common_nodes=len(mapping), gates=gates, passed=sum(v['passed'] for v in gates.values()), required=3)


def assess(folders, archive_path):
    first = read(folders[0]/'plan.json')
    archive = KernelArchive(archive_path, first['kernel_pins'])
    checked = {}
    def verify(record):
        old = checked.get(record['path'])
        if old is not None:
            require(old == record, 'Conflicting evidence hash')
        else:
            archive.verify(record)
            checked[record['path']] = record
    rows = []
    request0 = read(folders[0]/'request.json')
    for folder in folders:
        plan, report, request = (read(folder/name) for name in ('plan.json', 'report.json', 'request.json'))
        require(plan['kernel_pins'] == first['kernel_pins'] and plan['source_pins'] == first['source_pins'],
                'Mesh refinement changed equations or physical sources')
        records = plan['source_pins']+plan['kernel_pins']+[plan['helper'], report['result']]
        if 'kernel_archive' in plan:
            require(plan['kernel_archive'] == archive.manifest_pin and plan['runtime_kernel_pins'] == archive.runtime_pins,
                    'Runtime kernel changed')
            declared = {p['path'] for p in archive.runtime_pins}
            require(report['loaded_kernel_modules'] and all(p['path'] in declared for p in report['loaded_kernel_modules']),
                    'Unattributed runtime module')
            records += plan['inputs']+plan['runtime_kernel_pins']+[plan['kernel_archive'],plan['evidence_helper'],report['request']]
        for record in records+[pin(folder/name) for name in ('plan.json', 'report.json', 'request.json')]:
            verify(record)
        expected = copy.deepcopy(request0)
        nominal = plan['nominal']
        expected['panels'] = dict(default=nominal, beams={'1': dict(count=nominal, spacing='cosine')})
        require(request == expected, 'Something besides nominal mesh count changed')
        require(request['source'] == Path(plan['source_pins'][0]['path']).read_text(), 'Changed literal model')
        require(report['status'] == 'INITIAL_COMPARISON_COMPUTED' and report['residual'] <= 1e-8 and
                report['cold_solves'] == report['fresh_residuals'] == 1 and
                report['source_pins_unchanged'] and report['kernel_pins_unchanged'], 'Incomplete equilibrium evidence')
        result = read(report['result']['path'])
        require(result['converged'] and math.isfinite(result['residual']) and result['residual'] <= 1e-8,
                'Unconverged saved equilibrium')
        fields = mesh_fields(result, nominal, request['source'])
        require((fields['root_moment'], fields['nodes'], fields['elements']) ==
                (report['predicted'], report['nodes'], report['elements']), 'Report disagrees with saved state')
        target = plan['native_target']
        require(target == first['native_target'] and Path(target['source']).read_text().splitlines()[target['line']-1].split()
                == target['tokens'] and Decimal(target['tokens'][1]) == 0, 'Native t=0 target changed')
        native = float(Decimal(target['tokens'][2]))
        error = 100*abs(fields['root_moment']-native)/abs(native)
        require(abs(error-report['error_percent']) < 1e-12, 'Native error differs')
        rows.append(dict(fields, native=native, native_error_percent=error, native_passed=error <= 5.,
                         fresh_residual=report['residual'], full_history_spatially_validated=False))
    require([r['nominal'] for r in rows] == sorted({r['nominal'] for r in rows}), 'Mesh order or uniqueness changed')
    comparisons = [compare(a,b) for a,b in zip(rows,rows[1:])]
    return dict(status='INITIAL_SPATIAL_STUDY_ASSESSED', samples=rows, comparisons=comparisons,
                latest=comparisons[-1], kernel_archive=archive.manifest_pin, inputs=list(checked.values()),
                helper=pin(__file__), evidence_helper=pin(ROOT/'scripts/isae_ffwt4_evidence.py'),
                physical_solves=0, native_fraction_change=0, full_family_validated=False,
                qualifications=[
                    'Identical literal model, operating point, numerical tolerances and archived kernel; only nominal cosine count changes.',
                    'Independent straight-beam stations retain all 60 point masses at their 30 distinct stations plus the root and endpoints.',
                    'Root moment, displacement and small rotation-vector changes are compared; jig positions are removed from displacement.',
                    'Nodal fields are checked at every shared station without interpolation, normalized by the full fine-grid maximum norm.',
                    'All 0.1% gates are numerical comparisons; the 5% native allowance is separate.',
                    'Repeated t=0 targets add no native coverage. Full gust-history mesh accuracy, circulation/element fields and other cases remain open.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', type=Path, action='append', required=True)
    parser.add_argument('--kernel-archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(len(args.case) >= 2 and not args.output.exists(), 'Provide multiple meshes and a new output')
    result = assess([p.resolve() for p in args.case], args.kernel_archive)
    write(args.output, result)
    print(json.dumps(dict(samples=[{k:v for k,v in r.items() if k not in ('stations','displacement','rotation_vector')}
                                  for r in result['samples']], latest=result['latest'])), flush=True)


if __name__ == '__main__':
    main()
