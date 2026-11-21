"""All six original SA12 ground-effect polars; planning is source-only.

Euler pitch is absent from the archive. Pitch=alpha is an explicitly declared
wind-parallel reconstruction, never a claim to have recovered historical pose.
The image flag, normal, origin height, speed and all raw targets are preserved.
"""
import hashlib
import json
import math
from pathlib import Path
import time

try:
    from . import isae_suite_polars as polar
    from . import isae_suite_extra_polars as extra
except ImportError:
    import isae_suite_polars as polar
    import isae_suite_extra_polars as extra

REVISION = polar.REVISION
OUTPUTS = ('CL', 'CD', 'CDi', 'Cm')
HEIGHTS = {'05': .127, '2': .508, 'inf': 1000.}
FLAPS = ('Flap', 'No_Flap')
CONDITION_FIELDS = ('speed', 'alpha', 'beta', 'density', 'mach', 'freeze_influences',
    'stall', 'stall_factor', 'stall_width', 'wake_core_ratio', 'aero_lag',
    'body_added_mass_factor', 'ground_effect', 'ground_normal', 'position_earth', 'attitude')
QUALIFICATIONS = [
    'All six original85-row tables and four raw coefficient fields are required on both100/200 meshes; no experimental targets or MATLAB drag replacement are used.',
    'The drivers explicitly declare solid images, Earth normal[0,0,1], IAS35.76 and aircraft-origin Earth Z. The infinite-height label still uses images at1000m.',
    'No Euler pose is recorded. Pitch=alpha, zero bank/heading and beta=0 are declared wind-parallel reconstruction assumptions, not recovered historical settings.',
    'Five drivers select anchored defaults; No_Flap_hc_inf omits that selection. Its historical constraint/startup state remains unresolved; all jobs use a declared rigid geometry.',
    'Literal Constant rhoSL at declared sea level, Mach=0 and current influences are reconstruction choices. Historical atmosphere, PG and state before K/F toggles are unresolved.',
    polar.NODE_I_QUALIFICATION,
    'NODE/I100 requests 100 nodes. Its numeric value is reused for the unchanged current cosine100/200 interval reconstruction, without subtracting one; historical node arrays and circulation K remain unknown. Natural-v1 interpolation is unchanged.',
    'Every archived row and stall flag is retained. Angles11.25,11.5,11.75,12 are absent from all six tables and are not fabricated.',
    'CD is raw total near-field drag; CDi is the separate far-field Trefftz result. Numerical validity and precision matches do not prove historical setup or full-family reproduction.',
]


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _manifest(root):
    data = (root/'.reference/isae-validation/manifest.json').read_bytes()
    _require(hashlib.sha256(data).hexdigest() == extra.MANIFEST_SHA256, 'Original manifest changed.')
    result = json.loads(data)
    _require(result['revision'] == REVISION, 'Original revision changed.')
    return result


def decode_driver(text, output):
    declaration = extra.decode_driver(text, output)
    _require(all(s.split()[0].upper() in ('!V', '!A', '!RZ') for s in declaration['scalar_commands']),
             'Unreviewed control/pose/power command.')
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    ground = [i for i, line in enumerate(lines) if line.lower() == 'g']
    _require(len(ground) == 1, 'Expected one explicit ground declaration.')
    i = ground[0]
    _require(lines[i+1:i+3] == ['1', '0 0 1'], 'Unreviewed ground flag/normal.')
    heights = polar._command_values(lines, '!RZ')
    _require(len(heights) == 1, 'Expected one aircraft-origin Earth height.')
    _require(lines.count('%') == 1, 'Expected one constraint/default menu.')
    constraint = lines[lines.index('%')+1:i]
    _require(constraint in (['a', 'd'], ['d']), 'Unreviewed anchored/default command sequence.')
    declaration.update(ground_effect=1, ground_normal=[0., 0., 1.],
        height=polar._number(heights[0]), height_token=heights[0],
        anchored_defaults_selected=constraint == ['a', 'd'], euler_pose_recorded=False)
    return declaration


def _table_jobs(root, flap, height_label, manifest):
    _require(flap in FLAPS and height_label in HEIGHTS, 'Unreviewed SA12 variant/height.')
    cache = root/'.reference/isae-validation'/REVISION
    folders = list((cache/'1 - Aerodynamics/SA - Steady Aerodynamics Cases').glob('SA - 12 - *'))
    _require(len(folders) == 1, 'Missing or ambiguous original SA12 folder.')
    folder = folders[0]/'Aswing_Simulations'
    stem = f'Rectangular_Wing_{flap}_hc_{height_label}'
    model = folder/('Rectangular_Wing_flap.asw' if flap == 'Flap' else 'Rectangular_Wing_No_flap.asw')
    table, driver = folder/(stem+'.txt'), folder/(stem+'.sh')
    paths = (model, table, driver)
    helpers = (Path(__file__).resolve(), root/'scripts/isae_suite_polars.py', root/'scripts/isae_suite_extra_polars.py')
    sources = [polar._pin(p, root) for p in (*paths, *helpers)]
    for path, source in zip(paths, sources):
        expected = manifest['files'].get(path.relative_to(cache).as_posix())
        _require(expected is not None and all(source[k] == expected[k] for k in ('bytes', 'sha256')),
                 'Original source differs from manifest: '+str(path))
    _require(not any(model.with_suffix(s).exists() for s in ('.set', '.pnt', '.con')),
             'New startup sidecar requires review.')
    declaration = decode_driver(driver.read_text(), table.name)
    _require(declaration['model_file'] == model.name and declaration['speed'] == 35.76
             and declaration['requested_nodes'] == 100 and declaration['height'] == HEIGHTS[height_label],
             'Original model/speed/mesh/height declaration changed.')
    _require(declaration['anchored_defaults_selected'] == (flap != 'No_Flap' or height_label != 'inf'),
             'Original anchored-default declaration changed.')
    rows = extra.decode_table(table.read_text(), 12)
    tokens = declaration['alpha_tokens']
    _require(len(rows) == len(tokens) == 85, 'Original85-row accounting changed.')
    rho, rho_token = polar._rho_sl(model.read_text())
    jobs = []
    for row, token in zip(rows, tokens, strict=True):
        alpha = row['fields']['alpha']['value']
        _require(polar._number(token) == alpha, 'Archived alpha differs from exact driver command.')
        _require(row['fields']['conv']['value'] == 1, 'Archived convergence echo changed.')
        for level, count in enumerate((100, 200)):
            settings = extra._settings(declaration, row, rho, rho_token, count, level)
            settings.update(ground_effect=1, ground_normal=[0., 0., 1.],
                position_earth=[0., 0., declaration['height']], attitude=[0., alpha, 0.],
                pose_assumption='pitch_equals_alpha_wind_parallel; historical Euler pose absent')
            jobs.append(dict(id=f'SA-12:{table.stem}:row{row["row_index"]:03d}:n{count}',
                case_id='SA-12', adapter='sa12', flap=flap, height_label=height_label,
                model_path=sources[0]['path'], table_path=sources[1]['path'], driver_path=sources[2]['path'],
                row_index=row['row_index'], expected_outputs=4, required_outputs=list(OUTPUTS),
                settings=settings, sources=sources, reference_row=row, exact_driver_alpha_token=token,
                driver_declarations=declaration, archived_stall_flag=row['fields']['stall']['value'],
                execution_route='ground_polar', unsupported_reason=None, blocker_code=None,
                qualifications=list(QUALIFICATIONS), complete_family_reproduction=False))
    return jobs


def plan(root):
    root = Path(root).resolve()
    manifest = _manifest(root)
    jobs = [job for flap in FLAPS for height in HEIGHTS for job in _table_jobs(root, flap, height, manifest)]
    _require(len(jobs) == len({j['id'] for j in jobs}) == 1020, 'Incomplete/duplicate SA12 scope.')
    return jobs


def _validate_job(root, job):
    for source in job['sources']:
        _require(polar._pin(root/source['path'], root) == source, 'Pinned source changed: '+source['path'])
    canonical = _table_jobs(root, job.get('flap'), job.get('height_label'), _manifest(root))
    _require(next((j for j in canonical if j['id'] == job['id']), None) == job,
             'SA12 job/source/target/settings differs from declared literal plan.')


def reference_checks(predicted, row):
    checks = []
    for name in OUTPUTS:
        ref = row['fields'][name]
        value = predicted.get(name)
        finite = isinstance(value, (int, float)) and math.isfinite(value)
        available = finite and ref['value'] is not None
        error = abs(value-ref['value']) if available else None
        check = dict(name=name, predicted=value if finite else None, expected=ref['value'],
            expected_token=ref['token'], tolerance=ref['tolerance'], abs_error=error,
            passed=bool(available and error <= ref['tolerance']))
        if not available:
            check['unavailable_reason'] = ref.get('unavailable_reason', 'Production output unavailable or nonfinite.')
        checks.append(check)
    return checks


def physical_checks(model, condition, settings, result):
    """Separate wrench/normalization and analytic ground-pose checks."""
    import numpy as np
    checks = [dict(name='no parser diagnostics', passed=not model.diagnostics, diagnostics=list(model.diagnostics)),
              dict(name='converged', passed=bool(result['converged']))]
    def near(name, value, tolerance):
        value = float(value)
        checks.append(dict(name=name, value=value if math.isfinite(value) else None,
                           tolerance=tolerance, passed=math.isfinite(value) and abs(value) <= tolerance))
    near('circulation residual', result['residual'], 1e-8)
    force, moment, counts = polar.reconstructed_wrench(model, result)
    alpha = math.radians(settings['alpha'])
    wind, lift = np.array([math.cos(alpha), 0., math.sin(alpha)]), np.array([-math.sin(alpha), 0., math.cos(alpha)])
    qS = .5*condition.density*condition.speed**2*model.reference[0, 0]
    c, b = model.reference[0, 1:3]
    normalized = dict(CL=float(force@lift/qS), CD=float(force@wind/qS), CY=float(force[1]/qS),
                      Cm=float(moment[1]/(qS*c)), Cl=float(-moment[0]/(qS*b)), Cn=float(-moment[2]/(qS*b)))
    for name, value in normalized.items():
        near(name+' wrench normalization', value-result[name], 2e-10)
    near('reconstructed total force', np.max(abs(force-result['force']))/qS, 2e-10)
    near('reconstructed total moment', np.max(abs(moment-result['moment']))/(qS*c), 2e-10)
    near('near-field drag decomposition', result['CD']-sum(result[k] for k in
         ('CDi_near', 'CDp', 'CDbody', 'CDam', 'CDeng', 'CDrate')), 2e-10)
    ground = result['ground_plane']
    checks.append(dict(name='solid-ground image flag', passed=ground['flag'] == settings['ground_effect'] == 1))
    normal = np.array([-math.sin(alpha), 0., math.cos(alpha)])
    for name, expected in (('normal_body', normal), ('normal_earth', [0., 0., 1.]),
                           ('position_earth', settings['position_earth']), ('attitude', [0., settings['alpha'], 0.])):
        near('ground '+name, np.max(abs(np.asarray(ground[name])-expected)), 2e-10)
    near('ground offset', ground['offset']-settings['position_earth'][2], 2e-10)
    near('wind parallel to ground', np.asarray(ground['normal_body'])@wind, 2e-10)
    clearance = ground['minimum_clearance']
    checks.append(dict(name='positive ground clearance', value=clearance,
                       passed=isinstance(clearance, (int, float)) and math.isfinite(clearance) and clearance > 0))
    # Both byte-pinned inputs have a straight flat rectangular chord .254,
    # with the beam axis at chord/4. Evaluate both chord ends independently.
    expected_clearance = min(settings['position_earth'][2]+.25*.254*math.sin(alpha),
                             settings['position_earth'][2]-.75*.254*math.sin(alpha))
    near('rectangular-wing chord clearance', clearance-expected_clearance, 2e-10)
    checks.append(dict(name='finite far-field induced drag', passed=result.get('CDi') is not None and math.isfinite(result['CDi'])))
    return checks, force, moment, counts, normalized


def run(root, job):
    root = Path(root).resolve()
    start = time.monotonic()
    report = {key: job[key] for key in ('id', 'case_id', 'adapter', 'model_path', 'table_path', 'driver_path',
              'row_index', 'expected_outputs', 'required_outputs', 'settings', 'sources', 'qualifications', 'archived_stall_flag')}
    report.update(status='error', numerical_pass=False, reference_match=False,
                  reference_checks=reference_checks({}, job['reference_row']), numerical_checks=[],
                  physical_calls=0, complete_family_reproduction=False,
                  reference_scope='Four raw archived coefficients; wind-parallel reconstruction, historical Euler pose unresolved.')
    try:
        _validate_job(root, job)
        from openswing import asw, aero
        for module in (asw, aero):
            _require(Path(module.__file__).resolve() == root/'openswing'/(module.__name__.split('.')[-1]+'.py'),
                     'Production import did not resolve to declared repository.')
        s = job['settings']
        model = asw.parse_asw((root/job['model_path']).read_text(), beam_interpolation=s['beam_interpolation'])
        _require(float(model.constants[1]) == s['density'], 'rhoSL declaration/parser mismatch.')
        condition = aero.FlightCondition(**{key:s[key] for key in CONDITION_FIELDS})
        report['physical_calls'] = 1
        result = aero.solve_rigid(model, condition, panels=s['panels'], circulation_method=s['circulation_method'])
        checks, force, moment, counts, normalized = physical_checks(model, condition, s, result)
        report['numerical_checks'] = checks
        predicted = {key:None if result.get(key) is None else float(result[key]) for key in OUTPUTS}
        report['reference_checks'] = reference_checks(predicted, job['reference_row'])
        report['numerical_pass'] = all(check['passed'] for check in checks)
        report['status'] = 'computed' if report['numerical_pass'] else 'numerical_failure'
        report['reference_match'] = report['numerical_pass'] and all(check['passed'] for check in report['reference_checks'])
        report['result'] = dict(predicted=predicted, residual=float(result['residual']), panels=result['panels'],
            mesh_discretization=result.get('mesh_discretization'), reference=model.reference.tolist(),
            force=force.tolist(), moment=moment.tolist(), wrench_component_counts=counts,
            independently_normalized_coefficients=normalized, ground_plane=result['ground_plane'],
            trefftz=result['trefftz'], CDi_near=result['CDi_near'], CDp=result['CDp'],
            coefficient_definitions=result.get('coefficient_definitions'), circulation_solver=result.get('circulation_solver'))
        # Preserve the operands, so a saved-only checker can reconstruct the
        # wrenches and audit the actual atmosphere/influence/ground calculation.
        report['verification_payload'] = {key:result.get(key) for key in (
            'force', 'moment', 'CL', 'CD', 'CY', 'Cl', 'Cm', 'Cn', 'CDi', 'CDi_near',
            'CDp', 'CDbody', 'CDam', 'CDeng', 'CDrate', 'strips', 'body_shoulders',
            'engines', 'point_forces', 'atmosphere', 'reference_flow', 'mach',
            'aerodynamic_influences', 'lifting_airflow', 'circulation_residual',
            'circulation_local_residual', 'circulation_discretization', 'wake_core')}
    except Exception as exc:
        report.update(status='error', numerical_pass=False, reference_match=False,
                      error_type=type(exc).__name__, error=str(exc))
    finally:
        try:
            stable = all(polar._pin(root/s['path'], root) == s for s in job['sources'])
        except OSError:
            stable = False
        report['sources_unchanged'] = stable
        if not stable:
            report.update(status='source_mismatch', numerical_pass=False, reference_match=False)
        report['seconds'] = time.monotonic()-start
    nonfinite = []
    def clean(value, path=''):
        if hasattr(value, 'tolist'):
            return clean(value.tolist(), path)
        if isinstance(value, float) and not math.isfinite(value):
            nonfinite.append(path)
            return None
        if isinstance(value, dict):
            return {k:clean(v, path+'.'+k) for k,v in value.items()}
        if isinstance(value, (list, tuple)):
            return [clean(v, f'{path}[{i}]') for i,v in enumerate(value)]
        return value
    report = clean(report)
    report['nonfinite_fields'] = nonfinite
    if nonfinite:
        report.update(status='numerical_failure', numerical_pass=False, reference_match=False)
    return report
