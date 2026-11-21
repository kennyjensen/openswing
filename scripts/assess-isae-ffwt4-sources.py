"""Inventory every original FFWT-4 history using its explicit driver/model pair."""
import argparse
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
import re

from isae_ffwt4_evidence import pin, read, require, write

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
FAMILY = ('4 - Aeroelasticity/FFWT - Flared Folding Wingtips Cases/'
          'FFWT-4-U - Gust Alleviation of a Wing with and wo FFWT - Quantitative')


def resolve_model(requested, paths):
    exact = [p for p in paths if p.stem == requested]
    if exact:
        require(len(exact) == 1, 'Ambiguous exact model name')
        return exact[0], False
    candidates = [p for p in paths if p.stem.casefold() == requested.casefold()]
    require(len(candidates) == 1, 'Missing or ambiguous driver-selected model; no substitute allowed')
    return candidates[0], True


def driver_contract(source):
    lines = [(n, raw.strip()) for n, raw in enumerate(source.splitlines(), 1)
             if raw.strip() and not raw.lstrip().startswith('#')]
    invocation = re.search(r'\baswing\s+(\S+)\s+<<\s*EOF\s*$', lines[0][1])
    require(invocation is not None, 'Unrecognized ASWING invocation')
    positions = [i for i, (_, line) in enumerate(lines) if line.casefold() == 'gmod']
    require(positions, 'No original gust commands')
    conditions = {}
    for number, line in lines:
        match = re.fullmatch(r'!([AVBavb])\s+([-+\d.]+)', line)
        if match:
            key = match[1].upper()
            require(key not in conditions and Decimal(match[2]).is_finite(), 'Repeated or invalid operating constraint')
            conditions[key] = dict(value=str(Decimal(match[2])), line=number)
    require(set(conditions) <= {'A', 'V', 'B'} and {'A', 'V'} <= set(conditions), 'Missing initial angle/speed')
    histories = []
    for ordinal, start in enumerate(positions, 1):
        stop = positions[ordinal] if ordinal < len(positions) else len(lines)
        block = lines[start:stop]
        require(block[1][1] == '5', 'Unexpected gust type')
        parameters = [Decimal(t) for t in block[2][1].split()]
        require(len(parameters) == 4 and all(v.is_finite() for v in parameters), 'Invalid gust parameters')
        require(parameters[2] > 0 and parameters[3] > 0, 'Invalid original gust length or amplitude')
        time_rows = [(n, line.split()) for n, line in block if re.fullmatch(r'\d*\.\d+\s+\d+', line)]
        require(len(time_rows) == 1, 'Ambiguous time command')
        number, tokens = time_rows[0]
        require(Decimal(tokens[0]) > 0 and int(tokens[1]) == 200, 'Changed original time request')
        writers = [i for i, (_, line) in enumerate(block) if line.casefold() == 'w']
        require(len(writers) == 1 and writers[0]+1 < len(block), 'Missing or ambiguous output command')
        output = block[writers[0]+1][1]
        require(re.fullmatch(r'FFWT_[\w]+/FFWT_[\w]+-\d+\.txt', output) is not None,
                'Unexpected output path')
        if ordinal > 1:
            commands = [line.casefold() for _, line in block]
            oi = commands.index('oper')
            require(commands[oi+1] == '1', 'Later gust does not restore original operating point 1')
        histories.append(dict(ordinal=ordinal, gust_type=5, gust_parameters=list(map(str, parameters)),
                              gust_line=block[0][0], dt=tokens[0], time_request_count=200,
                              time_line=number, output=output, output_line=block[writers[0]+1][0],
                              commands=[dict(line=n, text=line) for n, line in block]))
    require(len({h['output'] for h in histories}) == len(histories), 'Duplicate output path')
    return dict(requested_model=invocation[1], invocation_line=lines[0][0], conditions=conditions,
                node_commands=[dict(line=n, text=line) for n, line in lines[1:positions[0]]],
                histories=histories)


def native_rows(source, dt):
    lines = source.splitlines()
    require(len(lines) >= 3 and lines[0].startswith('#') and 'Operating point sequence' in lines[1],
            'Unexpected native header')
    require(re.fullmatch(r'#\s*i\s+t\s+Mc`\s+mom\[\s*1\]\s*', lines[2]) is not None,
            'Native channel is not sensor-1 chordwise moment')
    step = Decimal(dt)
    require(step.is_finite() and step > 0, 'Invalid native time step')
    rows = []
    for number, line in enumerate(lines[3:], 4):
        if not line.strip():
            continue
        tokens = line.split()
        require(len(tokens) == 3 and int(tokens[0]) == len(rows)+1, 'Changed native columns or row order')
        t, value = (Decimal(v.replace('D', 'E').replace('d', 'E')) for v in tokens[1:])
        require(t.is_finite() and value.is_finite(), 'Nonfinite native value')
        half_time = Decimal(10)**t.as_tuple().exponent/2
        require(abs(t-len(rows)*step) <= half_time, 'Driver and output time grid disagree')
        rows.append(dict(row=len(rows)+1, source_line=number, time_token=tokens[1], moment_token=tokens[2],
                         exact_time=str(len(rows)*step), expected=str(value),
                         printed_half_interval=str(Decimal(10)**value.as_tuple().exponent/2)))
    require(len(rows) == 200, 'Every original history must retain all 200 exported values')
    return dict(title=lines[0].lstrip('#').strip(), rows=rows)


def model_title(source):
    lines = [line.split('#', 1)[0].strip() for line in source.splitlines()]
    index = next(i for i, line in enumerate(lines) if line.casefold() == 'name')
    return lines[index+1]


def assess(model_audit):
    cache = ROOT/'.reference/isae-validation'/REVISION
    base = cache/FAMILY
    manifest_path = cache.parent/'manifest.json'
    manifest = read(manifest_path)
    require(manifest['revision'] == REVISION, 'Changed reference revision')
    models, drivers, outputs = sorted(base.glob('*.asw')), sorted(base.glob('*.sh')), sorted(base.glob('*/*.txt'))
    require((len(models), len(drivers), len(outputs)) == (9, 5, 40), 'Changed complete source inventory')
    checked = {}
    for path in models+drivers+outputs+[base/'Analysis.m']:
        record = pin(path)
        original = manifest['files'][path.relative_to(cache).as_posix()]
        require(all(record[k] == original[k] for k in ('bytes', 'sha256')), 'Changed original source: '+str(path))
        checked[path.name if path.suffix != '.txt' else path.relative_to(base).as_posix()] = record
    audit = read(model_audit)
    require(audit['status'] == 'LITERAL_MODELS_INSPECTED' and audit['physical_solves'] == 0 and
            audit['kernel_pins_unchanged'], 'Complete literal mesh audit required')
    require(pin(audit['helper']['path']) == audit['helper'], 'Model checker changed')
    for record in audit['kernel_pins']:
        require(pin(record['path']) == record, 'Model-checking kernel changed')
    by_model = {m['model']: m for m in audit['models']}
    require(set(by_model) == {p.name for p in models}, 'Mesh audit omitted a model')
    for path in models:
        require(by_model[path.name]['source'] == pin(path), 'Mesh audit uses different model bytes')
        m = by_model[path.name]
        require([r['nominal'] for r in m['meshes']] == [8, 16], 'Missing mesh probe')
        if m['outside']:
            require(all(a['kind'] == 'weight' for a in m['outside']) and
                    all(r['status'] == 'rejected' and 'Attachment station is outside beam' in r['error']
                        for r in m['meshes']), 'Unexpected attachment failure')
        else:
            require(all(r['status'] == 'meshed' for r in m['meshes']), 'In-range model did not mesh')
    histories, selections = [], []
    for driver in drivers:
        contract = driver_contract(driver.read_text())
        require(len(contract['histories']) == 8, 'A driver must retain eight original gusts')
        model, case_difference = resolve_model(contract['requested_model'], models)
        require(contract['conditions']['A']['value'] == '6' and contract['conditions']['V']['value'] == '22',
                'Changed original incidence/speed')
        title = model_title(model.read_text())
        model_record = by_model[model.name]
        selections.append(dict(driver=driver.name, model=model.name, requested_model=contract['requested_model'],
            case_only_filename_difference=case_difference, conditions=contract['conditions'],
            node_commands=contract['node_commands'], model_title=title, outside=model_record['outside'],
            meshes=model_record['meshes']))
        for h in contract['histories']:
            path = base/h['output']
            require(path in outputs, 'Driver-named output missing from the complete inventory')
            parsed = native_rows(path.read_text(), h['dt'])
            histories.append(dict(id=path.stem, driver=driver.name, model=model.name,
                source=checked[h['output']], driver_source=checked[driver.name], model_source=checked[model.name],
                driver_contract=h, header_title=parsed['title'], header_matches_model=parsed['title'] == title,
                observations=parsed['rows'], required_values=200, values_computed_by_this_audit=0,
                attachment_compatibility='unresolved_out_of_range_weights' if model_record['outside'] else 'meshed_on_two_small_grids'))
    require({h['source']['path'] for h in histories} == {str(p.resolve()) for p in outputs} and len(histories) == 40,
            'Incomplete or repeated driver/output coverage')
    require(all(h['header_matches_model'] for h in histories), 'Driver-selected model and native title differ')
    required = sum(h['required_values'] for h in histories)
    require(required == 8000, 'Full archived denominator changed')
    selected = {s['model'] for s in selections}
    blocked = sum(h['required_values'] for h in histories if h['attachment_compatibility'].startswith('unresolved'))
    return dict(status='ALL_ORIGINAL_HISTORIES_INVENTORIED', revision=REVISION,
                drivers=selections, histories=histories, history_count=40, required_values=required,
                fixed_subset_values=1600, unresolved_attachment_values=blocked,
                by_driver=dict(Counter(h['driver'] for h in histories)),
                models_not_selected_by_retained_drivers=[p.name for p in models if p.name not in selected],
                model_audit=pin(model_audit), inputs=list(checked.values())+[pin(manifest_path), pin('.reference/aswing_doc.txt')],
                helper=pin(__file__), physical_solves=0, new_native_passes=0, full_family_validated=False,
                qualifications=[
                    'The five drivers select five models and export forty 200-row sensor-1 Mc-prime histories; all 8000 values remain required.',
                    'Flare10/20/30 drivers select their PM2 files, not the unmodified-name alternatives. Their selected PM2 files have out-of-range point-mass attachment stations.',
                    'The Flare20 driver explicitly constrains beta to 16 degrees; absent beta commands in other scripts are not evidence of a recovered zero-beta default.',
                    'Removed has a disclosed case-only model filename difference; its unique casefold match is used without modifying source bytes.',
                    'Internal model titles are not unique: Fixed is named Removed, and the selected Flare10/30 PM2 models are named Flare20. Explicit driver paths control pairing.',
                    'Current OpenSwing mesh rejection does not prove native ASWING rejection. Native out-of-range mass semantics or a different historical model remain unresolved.',
                    'MATLAB peak/increment reductions are derived evidence and add no independent history targets.',
                    'The driver requests count 200, and every retained export has 200 rows including startup; its retained endpoint is 199 times dt.',
                    'Node spacing, complete operating defaults, full numerical accuracy and shared execution registration remain open.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-audit', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), 'Preserve prior inventory evidence')
    result = assess(args.model_audit)
    write(args.output, result)
    print(json.dumps({k: result[k] for k in ('status', 'history_count', 'required_values', 'fixed_subset_values',
        'unresolved_attachment_values', 'models_not_selected_by_retained_drivers', 'new_native_passes')}))


if __name__ == '__main__':
    main()
