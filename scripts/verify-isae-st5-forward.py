"""Original ST5 forward-only exports, reusing the full-row recovery and runner.

Run each grid serially. Exact duplicate archived files are catalogued, not solved
again. No model, solver equation, load, or acceptance tolerance is adjusted.
"""
import argparse
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'scripts'/f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load('verify-isae-st5-roller')
decoder = load('extract-isae-st5-load-cases')
generator = load('verify-isae-st5-load-cases')
audit = load('assess-isae-st5-roller')
CASES = {f'{kind}_{load_}lb': (folder, f'JW_1_FW_{load_}lb')
         for kind, folder in [('cosine', 'Rigid_Joint'), ('elliptical', 'Elliptical_Loading')]
         for load_ in (20, 30)}
read, write, pin = runner.read, runner.write, runner.pin


def target_for(case, manifest):
    directory, name = CASES[case]
    base = runner.ARCHIVE/runner.RELATIVE
    paths = [base/directory/(name+suffix) for suffix in ('.asw', '.sh', '.txt')]
    pins = []
    for path in paths:
        p = pin(path)
        assert all(p[k] == manifest['files'][str(path.relative_to(runner.ARCHIVE))][k]
                   for k in ('bytes', 'sha256'))
        pins.append(p)
    duplicates = []
    for folder in ('Link_Joint', 'Elliptical_Loading/cosine_load'):
        copies = [base/folder/p.name for p in paths]
        if all(p.exists() and p.read_bytes() == q.read_bytes() for p, q in zip(copies, paths)):
            duplicates += [pin(p) for p in copies]
    blocks = decoder.observations(paths[2])
    assert len(blocks) == 1 and blocks[0]['beam'] == 1 and blocks[0]['row_count'] == 58
    for row in blocks[0]['rows']:
        if row['anchor_reason'] and 'rigid joint' in row['anchor_reason']:
            row['anchor_reason'] = 'literal geometry/property/control knot; no joint in this model'
    driver = paths[1].read_text().splitlines()
    assert driver[0].endswith(name+' <<EOF') and 'Aswing_R_5_92' in driver[0]
    assert [s.strip() for s in driver[1:] if s.strip()] == [
        'oper', 'x', 'k', 'v', '1 4 6 9 10 11 13 14 15 16 17 18 19 20 21 23 24 25 26',
        'w', name+'.txt', 'O', 'EOF']
    header = paths[2].read_text().splitlines()[:28]
    values = {}
    for label in ('Velocity', 'Alpha', 'Beta', 'Heading', 'Elev.', 'Bank', 'sum Fz', 'sum My',
                  'Ux', 'Uy', 'Uz', 'Wx', 'Wy', 'Wz', 'Udotx', 'Udoty', 'Udotz', 'Wdotx', 'Wdoty', 'Wdotz'):
        token = re.search(r'(?<!\w)'+re.escape(label)+r'\s*:\s*([-+\d.Ee]+)', '\n'.join(header)).group(1)
        v = Decimal(token)
        values[label] = dict(token=token, value=float(v), half=float(Decimal(5).scaleb(v.as_tuple().exponent-1)))
        if not label.startswith('sum '):
            assert v == 0
    tab = decoder.tables(paths[0])
    block = blocks[0]
    roots = [r['physical'] for r in block['rows'] if r['printed_t'] == 0]
    assert len(roots) == 2
    neg, pos = roots
    force = decoder.sub(decoder.mv(decoder.frame(pos[4:7]), pos[10:13]),
                        decoder.mv(decoder.frame(neg[4:7]), neg[10:13]))
    moment = decoder.sub(decoder.mv(decoder.frame(pos[4:7]), pos[7:10]),
                         decoder.mv(decoder.frame(neg[4:7]), neg[7:10]))
    arm = decoder.cross([decoder.value(tab, 1, k, 0) for k in ('x', 'y', 'z')], force)
    diagnostics = []
    for label, actual in [('sum Fz', force[2]), ('sum My', moment[1]+arm[1])]:
        diagnostics.append(dict(name='root_balance_'+label, passed=abs(actual-values[label]['value']) <= values[label]['half'], actual=actual, reference=values[label]))
    for row in block['rows']:
        assert all(row['physical'][j] == 0 for j in decoder.CONDITIONAL)
        if abs(row['exact_anchor_t'] or 0) not in (0., 2.001, 3.335) or row['exact_anchor_t'] is None:
            continue
        t = row['exact_anchor_t']
        p = {k: decoder.value(tab, 1, k, t) for k in ('EA', 'EIcc', 'EInn', 'Cshell', 'Nshell', 'Atshell')}
        v, h = row['physical'], block['printed_half_unit_by_column']
        eps = abs(v[11])/p['EA']+p['Cshell']*abs(v[9])/p['EInn']+p['Nshell']*abs(v[7])/p['EIcc']
        eps_half = h[11]/p['EA']+p['Cshell']*h[9]/p['EInn']+p['Nshell']*h[7]/p['EIcc']
        tau, tau_half = abs(v[8])/(2*p['Atshell']), h[8]/(2*p['Atshell'])
        for col, value, half in [(19, eps, eps_half), (20, tau, tau_half)]:
            diagnostics.append(dict(name=f'row{row["row"]}_shell_{decoder.NAMES[col]}',
                passed=abs(value-v[col]) <= half+h[col], actual=value, reference=v[col], interval_half=half+h[col]))
    assert all(c['passed'] for c in diagnostics), diagnostics
    columns = read(ROOT/'docs/validation/isae-st5-reference-target.json')['columns']
    return dict(schema='st5-forward-original-v1', case=case, source_pins=pins,
        byte_identical_duplicates=duplicates, beams=blocks, columns=columns,
        source_decoder_diagnostics=diagnostics, header_lines=header, header_values=values, driver_lines=driver,
        acceptance='Original ASWING outputs at unchanged printed precision; no experimental fitting.',
        uncertainties=[
            'Printed node centers plus exact literal knots are prospective grids, not recovered historical nodes.',
            'Sixteen original Weight records have exactly zero physical payload. Their coordinates do not add loads or analysis attachments.',
            'Selective output scaling has independent root-balance and literal-knot shell checks; historical exporter source is unavailable.',
            'All58rows/27outputs retained:14structural,10conditional zeros,2input echoes,1unresolved f_reac per row.',
            'Chord/Cm following-endpoint averaging is conditional display interpretation; f_reac remains unresolved.',
            'Original signed distributed loads and self-weight retained, without filename-based normalization.'])


def generated(source, target):
    """The same reviewed one-grid recovery, shared with the suite adapter."""
    text, patches, _ = generator.generate(source, target)
    def replace(before, after):
        nonlocal text
        assert text.count(before) == 1, before
        text = text.replace(before, after)
        patches.append(dict(before=before, after=after))
    replace('        state = restore(network, result[\'equilibrium_state\'])',
        "        from openswing.point_objects import active_weights\n"
        "        assert len(model.beams) == 1 and not model.records.get('joint')\n"
        "        assert len(model.records['weight']) == 16 and not active_weights(model)\n"
        "        assert len(network.constraints) == 1 and network.constraints[0]['b'] is None and network.constraints[0]['type'] == 0\n"
        "        state = restore(network, result['equilibrium_state'])")
    replace('clamps=max(clamp), joint_position=max(joint_position), joint_rotation=max(joint_rotation)',
            'clamps=max(clamp), joint_position=max(joint_position, default=0.), joint_rotation=max(joint_rotation, default=0.)')
    replace('rows=80, structural_entries=1120, conditional_zero_entries=800, input_echo_entries=160,',
            'rows=len(rows), structural_entries=len(rows)*14, conditional_zero_entries=len(rows)*10, input_echo_entries=len(rows)*2,')
    replace('unresolved_display_entries=80, cold_solves=3, fresh_residuals=3,',
            'unresolved_display_entries=len(rows), cold_solves=len(records), fresh_residuals=len(records),')
    replace("all_fine_mesh_gates_pass=all(v['passes'] for v in changes[-1]['measures'].values()),", 'all_fine_mesh_gates_pass=None,')
    replace("records[-1]['structural_matches'] == 1120", "records[-1]['structural_matches'] == len(rows)*14")
    compile(text, '<forward-verifier>', 'exec')
    return text, patches


def prepare(stage):
    assert not stage.exists()
    stage.mkdir(parents=True)
    manifest_path = ROOT/'.reference/isae-validation/manifest.json'
    manifest = read(manifest_path)
    assert manifest['revision'] == runner.REVISION
    paths = [Path(__file__), manifest_path, ROOT/'docs/validation/isae-st5-reference-target.json',
             generator.TEMPLATE, *[Path(m.__file__) for m in (runner, decoder, generator, audit)],
             *sorted((ROOT/'openswing').glob('*.py'))]
    cases = {}
    for case in CASES:
        folder = stage/case
        folder.mkdir()
        target = target_for(case, manifest)
        write(folder/'target.json', target)
        source = Path(target['source_pins'][0]['path'])
        text, patches = generated(source, folder/'target.json')
        (folder/'verifier.py').write_text(text)
        write(folder/'patches.json', patches)
        verifier = runner.load(folder/'verifier.py', '_forward_'+case)
        verifier.prepare(folder)
        plan = read(folder/'plan.json')
        assert [m['intervals_by_beam'] for m in plan['meshes']] == [{'1': n} for n in (38, 76, 152)]
        paths += [Path(p['path']) for p in target['source_pins']+target['byte_identical_duplicates']]
        paths += [folder/p for p in ('target.json', 'verifier.py', 'plan.json', 'patches.json')]
        cases[case] = dict(meshes=[38, 76, 152], decoder_checks=len(target['source_decoder_diagnostics']),
                           duplicate_files=len(target['byte_identical_duplicates']))
    write(stage/'plan.json', dict(status='PREPARED', cases=cases, pins=[pin(p) for p in sorted(set(paths))],
        cold_solves=12, fresh_residuals=12, requested_slots=4*3*58*27, concurrency=1, blas_threads=1,
        child_timeout_seconds=180, child_address_space_bytes=512*1024**2, production_solver_changes=False))
    print(json.dumps(cases), flush=True)


def assess(stage):
    study = read(stage/'plan.json')
    runner.stable(study['pins'])
    cases, totals, elapsed, solve_seconds = {}, {k: dict(matches=0,total=0) for k in audit.GROUPS}, 0., 0.
    for case in CASES:
        folder = stage/case
        target = read(folder/'target.json')
        original = Path(target['source_pins'][2]['path']).read_text().splitlines()
        block = target['beams'][0]
        levels, comparisons = [], []
        for level in range(3):
            run = folder/f'run-level{level}'
            receipt = read(run/'execution.json')
            runner.stable(receipt['outputs'])
            assert receipt['exit_code'] == 0 and receipt['process_reaped'] and receipt['physical_checks_pass']
            elapsed += receipt['elapsed_seconds']
            comparison = read(run/f'level{level}/comparison.json')
            assert comparison['numerical_gates_pass'] and len(comparison['rows']) == 58
            solve_seconds += comparison['seconds']
            counts = {k: dict(matches=0, total=0) for k in totals}
            for row, ref in zip(comparison['rows'], block['rows']):
                tokens = original[ref['source_line']-1].split()
                assert tokens == ref['raw_tokens'] and row['source_line'] == ref['source_line']
                expected = [float(t)*s for t, s in zip(tokens, block['physical_multipliers'])]
                half = [float(Decimal(10)**Decimal(Decimal(t).as_tuple().exponent))/2*s for t,s in zip(tokens, block['physical_multipliers'])]
                flags = [abs(a-b) <= h for a,b,h in zip(row['values'], expected, half)]
                assert expected == row['expected'] and half == row['half_last_place'] and flags == row['inside_printed_interval']
                for key, columns in audit.GROUPS.items():
                    counts[key]['matches'] += sum(flags[j] for j in columns)
                    counts[key]['total'] += len(columns)
            for key in totals:
                for field in ('matches', 'total'):
                    totals[key][field] += counts[key][field]
            levels.append(dict(level=level, intervals=comparison['intervals_by_beam'], counts=counts,
                physical_checks=comparison['checks'], solve_seconds=comparison['seconds'],
                errors={decoder.NAMES[j]: audit.errors(comparison['rows'], j) for j in decoder.STRUCTURAL}))
            comparisons.append(comparison)
        mesh = []
        for coarse, fine in zip(comparisons[:-1], comparisons[1:]):
            measures = {}
            for i, j in enumerate(decoder.STRUCTURAL):
                a = [r['structural_deformation'][i] for r in coarse['rows']]
                b = [r['structural_deformation'][i] for r in fine['rows']]
                change, envelope = max(abs(x-y) for x,y in zip(a,b)), max(map(abs,b))
                relative = change/envelope if envelope else (0. if change == 0 else None)
                measures[decoder.NAMES[j]] = dict(relative=relative, passed=relative is not None and relative <= .001)
            mesh.append(dict(coarse=coarse['level'], fine=fine['level'], measures=measures,
                             passed=sum(v['passed'] for v in measures.values()), total=14))
        cases[case] = dict(levels=levels, mesh_changes=mesh)
    assert sum(v['total'] for v in totals.values()) == study['requested_slots']
    result = dict(status='COMPLETE_COMPARISON_DIFFERENCES_RETAINED', goal_complete=False, family_validated=False,
        production_solver_changes=False, counts=totals, cases=cases, physical_solves_passed=12,
        fresh_residuals_passed=12, required_slots=study['requested_slots'],
        qualified_matches=sum(v['matches'] for k,v in totals.items() if k != 'unresolved_f_reac'),
        timing=dict(native_process_seconds=elapsed, dispatch_solve_seconds=solve_seconds),
        qualification='Zeros/input echoes do not establish physical prediction; unresolved f_reac stays in denominator.',
        evidence=[pin(stage/'plan.json'), *[pin(stage/c/f'run-level{i}/execution.json') for c in CASES for i in range(3)]])
    write(stage/'assessment.json', result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('cases','evidence')}, indent=2))
    for case, value in cases.items():
        print(case, 'mesh', value['mesh_changes'][-1]['passed'], '/14',
              'initial/fine median errors', [{k: level['errors'][k]['median_percent'] for k in ('z-z0','tw-tw0','Mc_prime')}
                                           for level in (value['levels'][0], value['levels'][-1])])


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('prepare', 'run', 'assess'))
    p.add_argument('--stage', type=Path, required=True)
    p.add_argument('--case', choices=CASES)
    p.add_argument('--level', type=int, choices=(0,1,2))
    args = p.parse_args()
    stage = args.stage.resolve()
    if args.action == 'run':
        assert args.case is not None and args.level is not None
        runner.run(stage, args.case, args.level)
    else:
        (prepare if args.action == 'prepare' else assess)(stage)
