"""Read-only archived component adapters for the complete ISAE suite.

plan(root) performs no production import. run(root, job) evaluates only the
declared component coordinates; process ownership and deadlines belong to the
suite runner. No old report, source table or archive is overwritten.
"""
from hashlib import sha256
import importlib.util
import json
import math
import os
from pathlib import Path
import sys


CT_GATE = 2e-12
SCHEMA = 'isae-suite-isolated-propeller-v1'


def _read(path):
    return json.loads(Path(path).read_text())


def _pin(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=sha256(raw).hexdigest())


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _one(rows, predicate, name):
    matches = [row for row in rows if predicate(row)]
    _require(len(matches) == 1, 'Expected exactly one '+name+'.')
    return matches[0]


def plan(root):
    """Six original P-1 CT curves, 110 scalars, with no experimental target."""
    root = Path(root).resolve()
    source_manifest = root/'docs/validation/isae-p1-sources.json'
    figure_inventory = root/'docs/validation/isae-figure-inventory.json'
    manifest, inventory = _read(source_manifest), _read(figure_inventory)
    kernels = [_pin(path) for path in sorted((root/'openswing').glob('*.py'))]
    _require(bool(kernels), 'No current production kernel files found.')
    jobs = []
    for blades, expected_count in ((2, 20), (3, 20), (4, 15)):
        prefix = 'da4022_9x6.75'+('' if blades == 2 else f'_{blades}b')+'_static_'
        primary_name = _one(manifest['files'], lambda name: name.startswith(prefix) and name.endswith('.txt'), 'primary CP table')
        primary = root/'.reference/isae-p1'/primary_name
        primary_pin = _pin(primary)
        _require(primary_pin['sha256'] == manifest['files'][primary_name]['sha256'], 'Primary P-1 CP table changed.')
        figure = _one(inventory['figures'], lambda row: f'P1_CT_{blades}_' in row['path'], 'archived P-1 figure')
        original = root/'.reference/isae-validation'/inventory['revision']/figure['path']
        _require(_pin(original)['sha256'] == figure['sha256'], 'Original P-1 FIG changed.')
        extracted = root/'.reference/isae-validation/figure-series'/(figure['sha256']+'.json')
        _require(_pin(extracted)['sha256'] == figure['extracted_sha256'], 'Extracted P-1 figure changed.')
        series = _read(extracted)['series']
        experiment = _one(series, lambda row: row['label'] == 'Experiments', 'source-alignment curve')['xy']
        samples = []
        for line_number, line in enumerate(primary.read_text().splitlines()[1:], 2):
            if not line.strip():
                continue
            words = line.split()
            _require(len(words) == 3, 'Expected original RPM/CT/CP table columns.')
            rpm, ct, cp = map(float, words)
            _require(all(math.isfinite(x) for x in (rpm, ct, cp)) and rpm > 0 and cp >= 0, 'Invalid P-1 source sample.')
            samples.append(dict(line=line_number, rpm_lexeme=words[0], cp_lexeme=words[2], rpm=rpm, cp=cp, alignment_ct=ct))
        _require(len(samples) == expected_count and len(experiment) == expected_count, 'P-1 source row count changed.')
        _require(all([row['rpm'], row['alignment_ct']] == xy for row, xy in zip(samples, experiment)),
                 'Primary CP table and archived RPM/measurement source alignment differ.')
        shared = [Path(__file__).resolve(), root/'scripts/verify-isae-p1.py', source_manifest,
                  figure_inventory, primary, original, extracted]
        pins = [_pin(path) for path in shared]
        for viscous in ('ON', 'OFF'):
            curve = _one(series, lambda row: 'ASWING' in row['label'] and f'Pv {viscous}:' in row['label'], 'ASWING P-1 curve')
            _require(len(curve['xy']) == expected_count, 'Archived CT count changed.')
            observations = []
            for index, (sample, xy) in enumerate(zip(samples, curve['xy'])):
                _require(len(xy) == 2 and all(math.isfinite(x) for x in xy), 'Invalid archived CT coordinate.')
                _require(xy[0] == sample['rpm'], 'Archived CT and supplied CP RPM coordinates differ.')
                observations.append(dict(index=index, primary_line=sample['line'],
                    rpm=sample['rpm'], rpm_lexeme=sample['rpm_lexeme'],
                    supplied_CP=sample['cp'], cp_lexeme=sample['cp_lexeme'],
                    archived_CT=xy[1], source_series_label=curve['label'],
                    missing=False))
            jobs.append(dict(id=f'P-1-{blades}blade-Pv{viscous}', case_id='P-1', family='P-1',
                adapter='components', component_schema=SCHEMA,
                scope='Original archived isolated static propeller CT curve; supplied CP, not independent power prediction or aircraft hover.',
                settings=dict(blades=blades, viscous=viscous, diameter_m=.2286,
                    density_kg_m3=1.2256, drag_area_m2=blades*.8e-4 if viscous == 'ON' else 0.,
                    axial_velocity_m_s=0., interpolation='none; evaluate each literal RPM/CP pair'),
                outputs=['CT'], coordinate_count=expected_count, expected_output_count=expected_count,
                expected_outputs=expected_count,
                missing_output_count=0, observations=observations,
                numerical_gate=dict(quantity='absolute CT difference', comparison='<', value=CT_GATE),
                expected_operations=dict(evaluate_calls=expected_count, engine_load_calls=expected_count, aircraft_solves=0),
                suggested_cap_seconds=30, source_pins=pins, kernel_pins=kernels,
                reference=dict(kind='archived_ASWING', original_figure=str(original),
                    extracted_figure=str(extracted), primary_CP_table=str(primary),
                    primary_table_columns_1based=dict(rpm=1, supplied_CP=3),
                    experimental_comparison_performed=False,
                    source_alignment='Raw primary RPM/CT pairs equal the stored experimental curve only to identify the CP input rows; CT acceptance uses the ASWING series exclusively.')))
    _require(len(jobs) == 6 and sum(j['expected_output_count'] for j in jobs) == 110, 'Incomplete P-1 curve catalog.')
    return jobs


def _evaluator(root):
    configured = os.environ.get('OPENSWING_KERNEL')
    _require(configured is None or Path(configured).resolve() == root,
             'OPENSWING_KERNEL would select a different production checkout.')
    sys.path.insert(0, str(root))
    path = root/'scripts/verify-isae-p1.py'
    spec = importlib.util.spec_from_file_location('_isae_suite_verified_p1', path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    actual = Path(sys.modules['openswing.propulsion'].__file__).resolve()
    _require(actual == root/'openswing/propulsion.py', 'P-1 helper imported a different production module.')
    return helper.evaluate, str(actual)


def run(root, job):
    """Return all requested scalars, including any failed component rows."""
    root = Path(root).resolve()
    canonical = _one(plan(root), lambda row: row['id'] == job.get('id'), 'planned P-1 job')
    # The outer suite may attach scheduling fields, but cannot silently change
    # coordinates, settings, source identity or acceptance criteria.
    for key, value in canonical.items():
        _require(job.get(key) == value, 'Prepared P-1 job changed: '+key)
    evaluate, imported = _evaluator(root)
    settings = canonical['settings']
    rows = []
    for observation in canonical['observations']:
        row = dict(observation)
        try:
            result = evaluate(observation['rpm'], observation['supplied_CP'],
                settings['diameter_m'], settings['drag_area_m2'], settings['density_kg_m3'])
            result = {key: float(value) for key, value in result.items()}
            _require(all(math.isfinite(v) for v in result.values()), 'Nonfinite P-1 component result.')
            difference = result['CT']-observation['archived_CT']
            row.update(status='computed', predicted_CT=result['CT'], difference=difference,
                absolute_difference=abs(difference), reference_passed=abs(difference) < CT_GATE,
                numerical_passed=result['independent_check_error'] < CT_GATE,
                component=result)
        except (AssertionError, ValueError, RuntimeError, FloatingPointError) as error:
            row.update(status='failed', predicted_CT=None, reference_passed=False,
                numerical_passed=False, error=type(error).__name__+': '+str(error))
        rows.append(row)
    pins_held = all(_pin(Path(item['path'])) == item for item in canonical['source_pins']+canonical['kernel_pins'])
    numerical = pins_held and all(row['numerical_passed'] for row in rows)
    reference = numerical and all(row['reference_passed'] for row in rows)
    errors = [row['absolute_difference'] for row in rows if row['status'] == 'computed']
    checks = [dict(name=f"CT:row{row['index']:02d}", rpm=row['rpm'],
        predicted=row['predicted_CT'], expected=row['archived_CT'],
        abs_error=row.get('absolute_difference'), tolerance=CT_GATE,
        comparison='<', passed=bool(row['reference_passed'] and row['numerical_passed']))
        for row in rows]
    return dict(id=canonical['id'], case_id='P-1', family='P-1', adapter='components',
        component_schema=SCHEMA, status='computed' if numerical else 'numerical_failure',
        reference_match=reference, reference_checks=checks,
        numerical_passed=numerical, reference_passed=reference,
        scope=canonical['scope'], settings=settings, numerical_gate=canonical['numerical_gate'],
        accounting=dict(required_coordinates=canonical['coordinate_count'], required_outputs=canonical['expected_output_count'],
            attempted_outputs=len(rows), computed_outputs=sum(r['status']=='computed' for r in rows),
            passed_outputs=sum(r['reference_passed'] and r['numerical_passed'] for r in rows),
            failed_outputs=sum(not(r['reference_passed'] and r['numerical_passed']) for r in rows),
            missing_outputs=0, unrun_outputs=0),
        maximum_absolute_CT_difference=max(errors) if errors else None, rows=rows,
        source_pins=canonical['source_pins'], kernel_pins=canonical['kernel_pins'],
        source_pins_unchanged=pins_held, imported_production_module=imported,
        operations=canonical['expected_operations'], reference=canonical['reference'],
        limits=['The six P-1 jobs cover 110 archived CT scalars at 55 distinct RPM input rows.',
            'CP and CdA are supplied original study inputs; experimental agreement is not tested.',
            'No claim for P-2/P-3/P-4/P-5, aircraft-level hover, or unspecified propeller outputs.'])
