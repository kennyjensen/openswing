"""Read-only ST4 source genealogy; no physics, target replacement or fitting."""
import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
CASE = ROOT/'reference/isae-validation'/REVISION/'3 - Structure/CASE - ST4 Concentrated weight'
HISTORY = ROOT/'reference/isae-st4-source-history-20261109'
STUDY = ROOT/'artifacts/isae/st4-mechanics-resumed-20261109'
NS = {'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def read(path): return json.loads(path.read_text())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def pin(path): return dict(path=str(path.relative_to(ROOT)), sha256=sha(path), bytes=path.stat().st_size)
def decimal(token): return Decimal(token.replace(',', '.'))


def spreadsheet(path):
    with zipfile.ZipFile(path) as archive:
        strings = [''.join(node.itertext()) for node in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('s:si', NS)]
        sheet = ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
        cells = {}
        for cell in sheet.findall('.//s:row/s:c', NS):
            value, formula = cell.find('s:v', NS), cell.find('s:f', NS)
            token = None if value is None else value.text
            if cell.attrib.get('t') == 's': token = strings[int(token)]
            cells[cell.attrib['r']] = dict(token=token, formula=None if formula is None else formula.text)
    return cells


def audit():
    source_manifest = read(ROOT/'reference/isae-validation/manifest.json')
    assert source_manifest['revision'] == REVISION
    sources = []
    for path in sorted(CASE.rglob('*')):
        if path.is_file():
            assert sha(path) == source_manifest['files'][path.relative_to(CASE.parents[1]).as_posix()]['sha256']
            sources.append(pin(path))
    catalog = read(ROOT/'docs/validation/aswing-authoritative-sources.json')
    report_source = next(r for r in catalog['files'] if r['id'] == 'isae-part-3')
    for pathkey, hashkey in [('local_pdf','sha256'), ('local_text','text_sha256')]:
        path = ROOT/report_source[pathkey]; assert sha(path) == report_source[hashkey]; sources.append(pin(path))
    treepath = ROOT/'reference/isae-st2-input-history-20261109/pre-rename-tree.json'
    tree_receipt = treepath.with_name('pre-rename-tree-source.json')
    assert sha(treepath) == read(tree_receipt)['sha256']
    tree = read(treepath); assert tree['truncated'] is False
    prefix = '3_Structure/CASE - ST4 Concentrated weight/'
    blobs = []
    for row in tree['tree']:
        if row['path'].startswith(prefix) and row['type'] == 'blob':
            path = CASE/row['path'][len(prefix):]; data = path.read_bytes()
            git_sha = hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
            assert git_sha == row['sha']
            blobs.append(dict(original_path=row['path'], current_path=str(path.relative_to(ROOT)), git_blob=git_sha))
    assert len(blobs) == len(sources)-2 == 69
    histories = {}
    for label in ('current','original'):
        path = HISTORY/(label+'-commits.json'); receipt = HISTORY/(label+'-receipt.json')
        assert sha(path) == read(receipt)['sha256'] and read(receipt)['link'] is None
        histories[label] = [dict(sha=c['sha'], date=c['commit']['author']['date'], message=c['commit']['message']) for c in read(path)]
        sources.extend([pin(path), pin(receipt)])
    assert [c['sha'] for c in histories['current']] == ['a58ec61bbafb22f9915ed4188b34bc35727e05bc']
    assert [c['sha'] for c in histories['original']] == ['a58ec61bbafb22f9915ed4188b34bc35727e05bc', '8f368bb58255ea7c39390911b21cdae4a5e96363']
    sources.extend([pin(treepath), pin(tree_receipt)])
    assert not any(Path(r['original_path']).name == 'W0.asw' for r in blobs)
    cells = spreadsheet(CASE/'Modal_analysis.xlsx')
    csv_rows = []
    with (CASE/'Eigen_data_save.csv').open() as stream:
        rows = list(csv.reader(stream, delimiter=';'))
    header = rows[0]
    names = ['fb1_exp','fb1_Asw','fb2_exp','fb2_Asw','ft_exp','ft_Asw']
    for line, row in enumerate(rows[1:], 2):
        if row[0].strip():
            csv_rows.append(dict(line=line, weight=row[0].strip().upper(), inches=row[1],
                values={name:row[header.index(name)] for name in names}))
    get = lambda weight, inches: next(r for r in csv_rows if r['weight'] == weight and r['inches'] == str(inches))
    # Original literal cells, not formulas or recomputed OpenSwing values.
    duplicate_pairs = [('O31','O14'), ('S31','W14'), ('W31','S14')]
    for a,b in duplicate_pairs:
        assert cells[a]['formula'] is cells[b]['formula'] is None and cells[a]['token'] == cells[b]['token']
    assert [cells[c]['token'].strip() for c in ('A31','B31','A14','B14')] == ['7F','24','7C','21']
    for weight,inches,rownum in [('7F',24,31), ('7F',32,32), ('7F',40,33), ('7C',21,14), ('7D',33,20)]:
        row = get(weight,inches)
        for name,col in zip(names, ('N','O','R','S','V','W'), strict=True):
            assert decimal(row['values'][name]) == decimal(cells[col+str(rownum)]['token'])
    # Experiment columns identify source rows without consulting any prediction.
    # These six printed entries were checked visually on Part III PDF p48.
    printed = {'7d_069':['4.2','34.2','22.4'], '7f_083':['4.4','34.2','21.5']}
    matches = {}
    for key,weight,positions in [('7d_069','7D',[33,39]), ('7f_083','7F',[32,40])]:
        items = []
        for inches in positions:
            row = get(weight,inches); source_tokens = [row['values'][name] for name in ('fb1_exp','fb2_exp','ft_exp')]
            compatible = []
            for shown, original in zip(printed[key], source_tokens, strict=True):
                value = Decimal(shown); half = Decimal('0.5')*Decimal(10)**value.as_tuple().exponent
                compatible.append(abs(decimal(original)-value) <= half)
            items.append(dict(inches=inches, csv_line=row['line'], experimental_tokens=source_tokens,
                              compatible_with_printed_precision=compatible))
        matches[key] = dict(paper_experimental_tokens=printed[key], candidates=items)
    assert [r['compatible_with_printed_precision'] for r in matches['7d_069']['candidates']] == [[True,False,False],[False,True,True]]
    assert [r['compatible_with_printed_precision'] for r in matches['7f_083']['candidates']] == [[True,True,True],[False,False,False]]
    # Use only declared identical-position files for the alternate CSV check.
    # No scanning predictions for a better reference or mass position.
    study = read(STUDY/'plan.json')
    for p,h in study['pins'].items():
        if p.startswith('openswing/'): assert sha(ROOT/p) == h
    comparisons = []
    for weight,inches in [('7D',33), ('7D',39), ('7F',24), ('7F',32), ('7F',40)]:
        model = weight.lower()+'_b'+str(inches); row = get(weight,inches)
        targets = sorted(float(decimal(row['values'][name])) for name in ('fb1_Asw','fb2_Asw','ft_Asw'))
        states = []
        for n in (64,128):
            index = study['jobs'].index(dict(model=model, panels=n))
            folder = STUDY/f'job-{index:02d}'; state = read(folder/'report.json')
            assert read(STUDY/f'execution-{index:02d}.json')['returncode'] == 0
            assert state['plan_sha256'] == sha(STUDY/'plan.json')
            for p,h in state['artifacts'].items(): assert sha(folder/p) == h
            states.append(state)
        errors = [max(abs(s['frequencies_Hz'][i]/target-1)*100 for s in states) for i,target in enumerate(targets)]
        comparisons.append(dict(model=model, source_line=row['line'], target_Hz=targets,
            coarse_Hz=states[0]['frequencies_Hz'], fine_Hz=states[1]['frequencies_Hz'],
            worst_mesh_error_percent=errors, reference_agreement_within_5_percent=[e <= 5 for e in errors],
            primary_votes_added=0))
    # A source-versus-source control: original CSV and directly paired native
    # ASWING text, with no OpenSwing values involved in this comparison.
    import isae_suite_modes as native_parser
    native_crosscheck = []
    for model, targets in study['direct_exports'].items():
        path = Path(study['models'][model]['path']).parent/'vaccum.txt'
        assert native_parser.decode_table((ROOT/path).read_text(), True) == targets
        weight, inches = model.split('_b'); row = get(weight.upper(), int(inches))
        values = sorted((decimal(row['values'][name]), name, row['values'][name])
                        for name in ('fb1_Asw','fb2_Asw','ft_Asw'))
        for i,((value, column, token), target) in enumerate(zip(values, targets[:3], strict=True), 1):
            expected = target['frequency_Hz']
            half = float(Decimal('0.5')*Decimal(10)**value.as_tuple().exponent)
            native_half = target['half_printed_units'][1]/(2*math.pi)
            native_crosscheck.append(dict(model=model, ordinal=i, csv_line=row['line'], csv_column=column,
                csv_token=token, native_path=str(path), native_line=target['line'],
                native_rad_s_token=target['raw_tokens'][2], native_Hz=expected,
                error_percent=100*(float(value)/expected-1),
                printed_precision_consistent=abs(float(value)-expected) <= half+native_half))
    assert len(native_crosscheck) == 15
    assert [(r['model'],r['ordinal']) for r in native_crosscheck if not r['printed_precision_consistent']] == [('7f_b48',3)]
    selected_addresses = ['A14','B14','O14','S14','W14','A31','B31','O31','S31','W31',
                          'A32','B32','C32','N32','O32','R32','S32','V32','W32','P32','T32','X32']
    sources.extend([pin(Path(__file__)), pin(Path(native_parser.__file__)), pin(STUDY/'plan.json')])
    return dict(observed_utc=datetime.now(timezone.utc).isoformat(), sources=sources,
        initial_st4_blob_count=len(blobs), original_blobs_identical=blobs, public_history=histories,
        missing_W0_in_first_upload=True, workbook_cells={k:cells[k] for k in selected_addresses},
        literal_duplicate_pairs=duplicate_pairs, experimental_row_identity=matches,
        declared_csv_comparisons=comparisons, csv_vs_direct_native=native_crosscheck,
        production_solver_calls=0, primary_counts_changed=False,
        conclusions=[
            'All69 original ST4 blobs are unchanged since the first public structural upload; no corrected W0 is recovered.',
            'The7f paper83% row has all three experimental entries from the32-inch source row, independently of any OpenSwing prediction.',
            'The7d paper69% row combines first-bending experimental data from33 inches with both upper experimental entries from39 inches.',
            'The7f24-inch ASWING triplet duplicates three literal7c21-inch spreadsheet values, with the upper labels exchanged. No formula reveals a recoverable original run.',
            'The7f48-inch CSV third frequency is28.28Hz, but its directly paired ASWING export gives30.715302918Hz. The7.929% source-versus-source difference is independent of OpenSwing.',
            'CSV and paper scopes remain separate; experimental values identify source rows only and never become acceptance targets.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); result = audit(); args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream: json.dump(result, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps(dict(original_blobs=result['initial_st4_blob_count'], comparison_models=len(result['declared_csv_comparisons']),
                          production_solver_calls=0, primary_counts_changed=False)))
