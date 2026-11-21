#!/usr/bin/env python3
"""Extract the complete AP-2 stored reference scope without importing a solver.

SciPy reads the original MAT containers here only. Consumers use the frozen
JSON catalog. Generated models replace exactly two Engine rows and preserve
every other byte; the two saved endpoint models remain completely untouched.
"""
import argparse
import csv
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path

from scipy.io import loadmat


ROOT = Path(__file__).resolve().parents[1]
REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
MANIFEST_SHA256 = '813347a3bd9fcbd029a1ec86e0c3141f82422af26f33ebde7c2f732a16bf27f6'
FAMILY = ('2 - Propellers/AP - Aero Propulsive Cases - Propeller Wing Interaction/'
          'AP-2 - Propeller lateral and vertical position on the wing lift to drag ratio')
CONFIG = (
    dict(id='APROPOS1', model='APROPOS1', alpha=1.05, cdp=.0045,
         variable='CL_CD1', z_R=[-1.017, -.508, 0., .508], experiment='Velhuis2_CL_CD2.csv'),
    dict(id='APROPOS4', model='APROPOS', alpha=4.2, cdp=.005,
         variable='CL_CD4', z_R=[-1.017, -.508, 0., .508, 1.017], experiment='Velhuis2_CL_CD.csv'))
SCALAR_NAMES = ('CL', 'CD')
CATALOG_PATH = 'docs/validation/isae-ap2-reference.json'
NOTES_PATH = 'docs/validation/isae-ap2-reference.md'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def pin(root, path):
    path = Path(path)
    raw = path.read_bytes()
    return dict(path=path.relative_to(root).as_posix(), bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest())


def coefficient(token, name, line=4, column=None):
    value = Decimal(token)
    tolerance = Decimal(5).scaleb(value.as_tuple().exponent-1)
    require(value.is_finite() and tolerance > 0, 'Invalid AP2 coefficient token.')
    return dict(name=name, token=token, expected=float(value), tolerance=float(tolerance),
                expected_decimal=str(value), tolerance_decimal=str(tolerance),
                source_line=line, source_column_1based=column,
                precision='Original printed half-last-place; no widened gate.')


def read_export(path):
    lines = path.read_text().splitlines()
    require(lines[1].strip() == '# Operating point sequence...' and
            lines[2].split() == ['#', 'i', 't', 'CL', 'CD'], 'AP2 export header changed.')
    data = [(i+1, line) for i, line in enumerate(lines[3:], 3) if line.strip()]
    require(len(data) == 1, 'AP2 export must retain exactly one original row.')
    line, raw = data[0]
    tokens = raw.split()
    require(len(tokens) == 4 and tokens[:2] == ['1', '1.000'], 'AP2 export row changed.')
    return dict(row_number=1, source_line=line, raw_line=raw, tokens=tokens), [
        coefficient(token, name, line, col) for token, name, col in zip(tokens[2:], SCALAR_NAMES, (3, 4))]


def engine_rows(raw):
    lines = raw.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.strip() == b'Engine']
    require(len(starts) == 1, 'AP2 requires one literal Engine section.')
    start = starts[0]
    end = next(i for i in range(start+1, len(lines)) if lines[i].strip() == b'End')
    indices = [i for i in range(start+1, end) if lines[i].strip() and
               not lines[i].lstrip().startswith(b'#')]
    require(indices == [39, 41], 'AP2 original Engine row locations changed.')
    tokens = [line.decode().split() for i, line in enumerate(lines) if i in indices]
    require(all(len(row) == 15 for row in tokens), 'AP2 Engine column count changed.')
    return lines, indices, tokens


def generated_tokens(x, y, z):
    # This scalar magnitude range and both retained endpoints support the
    # producer's default num2str five-significant-digit numeric tokens. It is
    # an explicit reconstruction policy, not recovered MATLAB binary identity.
    def row(sign):
        sy = format(sign*y, '.5g')
        return ['1', '1', '1', sy, format(x, '.5g'), sy, format(z, '.5g'),
                '-1.0', '0.0', '0.0', '0.0', '0.0', '0.1180',
                '500' if sign == 1 else '-500', '4.4874e-04']
    return dict(positive=row(1), negative=row(-1))


def generated_source(raw, tokens, endpoint=False):
    if endpoint:
        return raw
    lines, indices, _ = engine_rows(raw)
    for index, key in zip(indices, ('positive', 'negative')):
        original = lines[index]
        ending = original[len(original.rstrip(b'\r\n')):]
        lines[index] = ' '.join(tokens[key]).encode()+ending
    return b''.join(lines)


def extract(root=ROOT):
    root = Path(root).resolve()
    manifest_path = root/'.reference/isae-validation/manifest.json'
    require(hashlib.sha256(manifest_path.read_bytes()).hexdigest() == MANIFEST_SHA256,
            'Original ISAE manifest changed.')
    manifest = json.loads(manifest_path.read_text())
    require(manifest['revision'] == REVISION, 'Original ISAE revision changed.')
    family = root/'.reference/isae-validation'/REVISION/FAMILY
    native = family/'Aswing_Simulation'
    originals = sorted(p for p in family.rglob('*') if p.suffix in
                       ('.m', '.asv', '.asw', '.sh', '.mat', '.csv', '.txt'))
    require(len(originals) == 16, 'Original AP2 producer/data inventory changed.')
    pins = []
    for path in originals:
        actual = pin(root, path)
        expected = manifest['files'][path.relative_to(family.parent.parent.parent).as_posix()]
        require(all(actual[k] == expected[k] for k in ('bytes', 'sha256')),
                'Original AP2 source changed: '+str(path))
        pins.append(actual)
    series = []
    for config in CONFIG:
        name = config['id']
        model, driver, matpath, csvpath = [native/(n+s) for n, s in
            ((config['model'], '.asw'), (name, '.sh'), (name, '.mat'), (name+'_temp', '.csv'))]
        raw = model.read_bytes()
        lines, indices, saved_tokens = engine_rows(raw)
        commands = driver.read_text().splitlines()
        require(commands[1].endswith('aswing '+config['model']+' <<EOF') and
                commands[8] == 'I 150' and commands[14:18] ==
                ['!V  50', '!E1 330', '!A '+str(config['alpha']), 'x'] and
                commands[20] == '74 75' and commands[23] == name+'_temp.csv',
                'Original AP2 driver binding changed.')
        require(all(float(lines[i].split()[-1]) == config['cdp'] for i in (103, 104)),
                'AP2 per-model Cdp changed.')
        mat = loadmat(matpath)
        values, yp = mat[config['variable']], mat['y_p']
        require(values.shape == (len(config['z_R']), 13) and yp.shape == (13, 1),
                'AP2 MAT grid shape changed.')
        experiment = family/'Experimental_Data'/config['experiment']
        experimental_rows = list(csv.reader(experiment.read_text().splitlines()[2:]))
        require(len(experimental_rows) == 13 and
                all(float(yp[j, 0]) == float(row[0])*.64 for j, row in enumerate(experimental_rows)),
                'AP2 MAT input coordinates do not match the independent producer X grid.')
        csvrow, csvtargets = read_export(csvpath)
        ratio = csvtargets[0]['expected']/csvtargets[1]['expected']
        require(ratio == float(values[-1, -1]), 'AP2 final CSV ratio differs from final MAT cell.')
        rows = []
        for i, z_R in enumerate(config['z_R']):
            for j in range(13):
                x, y, z = -1.44*.118, float(yp[j, 0]), z_R*.118
                value = float(values[i, j])
                require(all(math.isfinite(v) for v in (x, y, z, value)), 'Nonfinite AP2 source target.')
                tokens = generated_tokens(x, y, z)
                endpoint = i == len(config['z_R'])-1 and j == 12
                if endpoint:
                    require([tokens['positive'], tokens['negative']] == saved_tokens,
                            'AP2 generated endpoint differs from original Engine tokens.')
                generated = generated_source(raw, tokens, endpoint)
                glines, _, _ = engine_rows(generated)
                require(len(glines) == len(lines) and
                        all(a == b for k, (a, b) in enumerate(zip(lines, glines)) if k not in indices),
                        'AP2 reconstruction modified non-Engine bytes.')
                rows.append(dict(row_number=i*13+j+1, row_index=i, col_index=j, x=x, y=y, z=z,
                    coordinate_hex={k: v.hex() for k, v in zip(('x', 'y', 'z'), (x, y, z))},
                    z_over_R=z_R, independent_y_source_line=j+3,
                    engine_tokens=tokens, ratio=value, ratio_hex=value.hex(), tolerance=0.,
                    precision='Exact stored MAT float identity diagnostic; not recovered ASWING coefficient printing precision.',
                    paired_csv={v['name']: v for v in csvtargets} if endpoint else None,
                    original_endpoint=endpoint, generated_source_sha256=hashlib.sha256(generated).hexdigest()))
        dec_cl, dec_cd = [Decimal(v['token']) for v in csvtargets]
        half_cl, half_cd = [Decimal(v['tolerance_decimal']) for v in csvtargets]
        series.append(dict(id=name, model_path=model.relative_to(root).as_posix(),
            driver_path=driver.relative_to(root).as_posix(), mat_path=matpath.relative_to(root).as_posix(),
            csv_path=csvpath.relative_to(root).as_posix(), alpha=config['alpha'], shape=list(values.shape),
            mat_variable=config['variable'], mat_header=mat['__header__'].decode(),
            original_model_sha256=hashlib.sha256(raw).hexdigest(),
            non_engine_bytes_sha256=hashlib.sha256(b''.join(v for i, v in enumerate(lines) if i not in indices)).hexdigest(),
            engine_source_lines=[i+1 for i in indices], cdp=config['cdp'], rows=rows,
            coordinate_source=experiment.relative_to(root).as_posix(),
            coordinate_rule='MAT y_p equals experimental first X column times 0.64 exactly. No experimental CL/CD value is used as an input or target.',
            driver_settings=dict(speed=50., powers={'1': 330.}, alpha=config['alpha'], node_I=150),
            paired_csv_row=csvrow,
            endpoint_ratio_interval_from_printed_coefficients_decimal=[
                str((dec_cl-half_cl)/(dec_cd+half_cd)), str((dec_cl+half_cl)/(dec_cd-half_cd))],
            endpoint_ratio_matching_mat_indices=[[i, j] for i in range(values.shape[0])
                for j in range(values.shape[1]) if float(values[i, j]) == ratio]))
    unpaired = []
    for name in ('APROPOS1_temp.txt', 'APROPOS4_temp.txt', 'APROPOS_temp.txt'):
        path = native/name
        row, observations = read_export(path)
        ratio = observations[0]['expected']/observations[1]['expected']
        matches = [dict(series=s['id'], row_index=v['row_index'], col_index=v['col_index'])
                   for s in series for v in s['rows'] if v['ratio'] == ratio]
        unpaired.append(dict(table_path=path.relative_to(root).as_posix(), rows=[row], observations=observations,
            status='UNPAIRED_ORIGINAL_EXPORT', blocked_reason='No retained driver selects this TXT path and no generating input state is independently bound.',
            ratio_coincidences=matches,
            qualification='An output-ratio coincidence does not establish the input coordinates; no input is selected from target agreement.'))
    catalog = dict(format='isae-ap2-reference', version=1, revision=REVISION,
        status='SOURCE_EXTRACTED_CONDITIONAL_RECONSTRUCTION_NOT_NUMERICAL_VALIDATION',
        manifest=pin(root, manifest_path), extractor=pin(root, root/'scripts/extract-isae-ap2-reference.py'),
        source_pins=pins, series=series, unpaired=unpaired,
        accounting=dict(series=2, mat_cells=117, paired_coefficient_targets=4,
            unpaired_coefficient_targets=6, distinct_target_records=127,
            declared_meshes=[150, 300], mesh_jobs=234, mesh_output_slots=242,
            blocked_export_jobs=3, blocked_export_slots=6, planned_jobs=237, planned_output_slots=248),
        reconstruction=dict(changed_source_lines=[40, 42], token_join='single ASCII space',
            endpoint_rule='Use original complete bytes unchanged; verify generated tokens match both saved Engine rows.',
            generated_rule='Replace only Engine row content, retaining its original line ending and every non-Engine byte.',
            number_format='Explicit five significant digits over this scalar coordinate range; supported by retained endpoint tokens. Historical MATLAB binary/format-version identity is not recovered.',
            mutator='change_ppropeller_position.m lines 9–10 and 13–23',
            sweep='AP2_Jet_Wing_interaction.m lines 19–36 and 88–107'),
        qualifications=[
            'All 117 MAT ratio cells are retained, including duplicate values. Two endpoint ratios are algebraically dependent on four paired CSV coefficient tokens, not independent validations.',
            'MAT float.hex tokens and zero tolerance describe stored-value identity only. Original coefficient printing intervals for 115 interior cells are unavailable; no CL/CD columns are inferred from their ratios.',
            'Both shell drivers select 74/75 and explicitly write the four-column CL/CD CSV. The commented MATLAB Var11/Var17 expressions conflict with those exports; an earlier output selection is plausible but unproven.',
            'Reconstruct intermediate inputs only from the explicit producer coordinate grid and Engine mutator, preserving each original non-Engine model byte. These are declared generated variants, not retained original input files.',
            'The two model bases retain distinct Cdp values: APROPOS1=.0045 and APROPOS=.005. No fitted property or common-base substitution is used.',
            'MAT y_p has independent provenance in experimental X coordinates. Experimental ratio ordinates are excluded from both inputs and comparison targets.',
            'APROPOS4 final CSV ratio also occurs in the opposite-z first MAT row. Positive saved z and final producer coordinates bind the endpoint; ratio equality alone does not.',
            'APROPOS1_temp.txt ratio equals MAT row 1, column 6, but this output-derived coincidence does not bind its generating model. All three TXT exports remain separate blocked records.',
            'Historical startup atmosphere, PG, K/F, pose, influence-update policy, original binary and exact historical node arrays are not recovered. The driver establishes V=50, shared power 1=330, alpha=1.05/4.2 and NODE I150.',
            'The additional 300-interval grid is a declared current refinement, not an original driver command. Both meshes retain the same original target records.',
            'CL/CD comparison must use aerodynamic coefficient definitions; net engine thrust is not a replacement drag target. No complete AP2 family pass follows from this catalog.'])
    require(sum(len(s['rows']) for s in series) == 117 and
            sum(row['paired_csv'] is not None for s in series for row in s['rows']) == 2,
            'AP2 complete target accounting changed.')
    catalog['canonical_payload_sha256'] = hashlib.sha256(canonical(catalog)).hexdigest()
    return catalog


def notes(catalog):
    return '''# AP-2 original reference catalog

The [machine catalog](isae-ap2-reference.json) retains all **117 stored MAT ratio
cells**, four directly paired endpoint CL/CD tokens, and six coefficient tokens
from three unpaired TXT exports. This is source extraction and a declared input
reconstruction; no solver runs or numerical validation are performed here.

The planned two-mesh scope contains **237 jobs and 248 scalar slots**: 234 jobs
compare 117 ratios on 150/300 intervals, with eight additional endpoint coefficient
slots; three blocked TXT jobs retain six further slots. Repeated mesh targets and
algebraically dependent endpoint ratios are not independent validations.

| Series | Original model | Alpha | MAT shape | Cdp |
|---|---|---:|---:|---:|
| APROPOS1 | APROPOS1.asw | 1.05° | 4×13 | 0.0045 |
| APROPOS4 | APROPOS.asw | 4.2° | 5×13 | 0.005 |

The original source directory is pinned at ISAE revision
`f62943df20e9e4d7d9f50e070477b22426b5f865`, under `2 - Propellers/AP - Aero
Propulsive Cases - Propeller Wing Interaction/AP-2 - Propeller lateral and
vertical position on the wing lift to drag ratio`.

`AP2_Jet_Wing_interaction.m` lines 19–36 and 88–107 declare the vertical grids,
axial coordinate and nested producer loops. Every MAT `y_p` coordinate exactly
equals the corresponding experimental CSV first X-column times 0.64. Those
coordinates are independently specified inputs; experimental CL/CD ordinates
are not used. `change_ppropeller_position.m` lines 9–10 and 13–23 changes only the
two Engine rows. Generated variants preserve every non-Engine byte and original
line ending. Five-significant-digit coordinate tokens match both retained
endpoint models; intermediate files are explicitly reconstructions. Endpoint
requests use the complete original model bytes unchanged.

Both `.sh` drivers lines 8–24 declare NODE I150, V=50, shared engine power 1=330,
the incidence, selectors 74/75 and the CSV destination. The four-column exports
label CL and CD directly. The commented MATLAB `Var11/Var17` expressions at
lines 33/102 conflict with the retained columns. A stale output selection is a
plausible explanation, not established producer history. This conflict does not
erase the direct shell/export pairing or explicit coordinate/mutator recipe.

The final CSV ratios exactly equal the final MAT cells. APROPOS4's ratio also
occurs in the opposite-z first row; its positive saved z and final grid position
are necessary pairing evidence. APROPOS1_temp.txt happens to reproduce MAT
row 1, column 6 as a ratio, but selecting input coordinates from that coincidence
would be output-derived pairing. All three TXT files remain unpaired.

Every MAT double retains its native `float.hex()` value. Tolerance 0 is an exact
stored-value identity diagnostic, **not recovered ASWING printed precision**.
The two CSV endpoints retain their own decimal coefficient tokens and original
half-last-place bounds (CL 5e-7, CD 5e-8). Endpoint ratio intervals are propagated
from those bounds and stored separately. They are not assigned to other MAT
cells, and no lost CL/CD columns are inferred from ratios. Aerodynamic CL/CD
must remain distinct from net engine force.

Original startup state, atmosphere/PG/KF, influence-update policy, executable
identity and exact historical node arrays remain unresolved. The 300-interval
mesh is a declared current refinement. No complete-family validation is claimed.

Regenerate and check without running physics:

```sh
.venv/bin/python scripts/extract-isae-ap2-reference.py
.venv/bin/python scripts/extract-isae-ap2-reference.py --check
```
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    catalog = extract(root)
    outputs = {root/CATALOG_PATH: json.dumps(catalog, sort_keys=True, indent=2, allow_nan=False)+'\n',
               root/NOTES_PATH: notes(catalog)}
    for path, text in outputs.items():
        if args.check:
            require(path.read_text() == text, 'AP2 canonical extraction differs: '+str(path))
        else:
            path.write_text(text)
    print(json.dumps(dict(status='MATCH_REPRODUCIBLE_CATALOG' if args.check else 'SOURCE_CATALOG_EXTRACTED',
        canonical_payload_sha256=catalog['canonical_payload_sha256'], accounting=catalog['accounting'],
        production_imports=0, physics_calls=0, outputs=[pin(root, path) for path in outputs])))


if __name__ == '__main__':
    main()
