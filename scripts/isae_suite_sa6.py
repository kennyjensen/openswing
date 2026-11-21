"""Literal SA6 fmat static coefficients; planning and blockers run no physics.

The 35c model retains a shell driver. The original MATLAB postprocessor binds
all four chord variants to eleven control states by exact Cl/Cn tokens.
Unpaired spanwise models remain unsupported. Derivatives and inertia tensors
are outside this six-static-coefficient scope.
"""
import copy
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re
import time

try:
    from . import isae_suite_polars as polar
    from . import isae_suite_sa6_controls as control_scope
    from . import isae_suite_sa6_states as state_scope
    from . import isae_suite_sa6_mass as mass_scope
except ImportError:
    import isae_suite_polars as polar
    import isae_suite_sa6_controls as control_scope
    import isae_suite_sa6_states as state_scope
    import isae_suite_sa6_mass as mass_scope

REVISION = polar.REVISION
MANIFEST_SHA256 = '813347a3bd9fcbd029a1ec86e0c3141f82422af26f33ebde7c2f732a16bf27f6'
OUTPUTS = ('CX', 'CY', 'CL', 'Cl', 'Cm', 'Cn')
CHORDWISE = ('20b_15c', '20b_20c', '20b_30c', '20b_35c')
SPANWISE = ('10b_25c', '15b_25c', '20b_25c')
POSTPROCESSOR = 'Post_Treatment_Post_Stall.m'
POSTPROCESSOR_SHA256 = '0d4a2bf1a043bc9fe50b3d6ad56f1124a1d0dc741d14e917a5edf122393924bb'
POSTPROCESSOR_BINDING = 'original_matlab_control_binding'
BLOCKS = {
    'NO_MATCHING_DRIVER': 'No retained original driver invokes this model; fmat index alone does not prove its control command.',
    'NO_PAIRED_EXPORT': 'Original spanwise model has no paired archived numerical fmat output; experimental tables are excluded.',
}
QUALIFICATIONS = [
    'Six static stability-axis coefficients only; all stability/control derivatives and real/apparent inertia tensors are outside this scope.',
    'Original model bytes, including literal35c dCLdF1=-.071, are retained; no experimental reconstruction or fit.',
    'Original NODE count is not recovered.64/128 are declared current cosine-mesh requests, enriched by current mandatory stations.',
    'Frozen influences follow the documented ASWING K/F default; historical K/F startup state remains unresolved.',
    'Mach0, speed20, alpha12, beta/rates0 and sea-level density1.2256 are supported by the archived fmat metadata.',
    'Printed half-last-place checks do not establish complete historical settings, mesh convergence or entire-family reproduction.',
]


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _one(text, pattern):
    values = re.findall(pattern, text, re.MULTILINE)
    _require(len(values) == 1, 'Missing or ambiguous fmat metadata: '+pattern)
    return values[0]


def decode_fmat(text):
    """Decode exactly the six labeled static coefficients and source metadata."""
    header = 'Normalized forces in: Stability axes, x fwd, z down'
    _require(text.count(header) == 1, 'Expected one stability-axis force table.')
    block = text.split(header, 1)[1].split('Derivatives in:', 1)[0]
    fields = {}
    for name in OUTPUTS:
        token = _one(block, r'\b'+name+r'\s*=\s*(\S+)')
        fields[name] = polar.printed_value(token)
    number = r'([+\-0-9.EeDd]+)'
    patterns = {
        'mach': r'^\s*Mach =\s*'+number,
        'pg': r'1 / sqrt\(1-M\^2\) =\s*'+number,
        'chord': r'Reference\.\.\.\s+chord\s+c =\s*'+number,
        'span': r'^\s*span\s+b =\s*'+number,
        'area': r'^\s*area\s+S =\s*'+number,
        'q': r'dynamic pressure\s+q =\s*'+number,
        'speed': r'^\s*speed\s+V =\s*'+number,
        'alpha': r'^\s*alpha =\s*'+number,
        'beta': r'^\s*beta\s*=\s*'+number,
        'rho_ratio': r'rho/rhoSL =\s*'+number,
        'Wx': r'\bWx =\s*'+number, 'Wy': r'\bWy =\s*'+number,
        'Wz': r'\bWz =\s*'+number,
    }
    metadata = {k: polar.printed_value(_one(text, pattern)) for k, pattern in patterns.items()}
    index = int(_one(text, r'For deformed shape, operating point\s+(\d+)\s+\.\.\.'))
    return dict(row_index=index-1, operating_point=index, fields=fields, metadata=metadata)


def decode_driver(text):
    """Read the one archived command sequence; never execute shell contents."""
    lines = [s.strip() for s in text.splitlines() if s.strip()]
    expected = ['!/bin/sh', 'aswing Straight_Wing_20b_35c <<EOF', 'oper', '!V 20', '!A 12']
    for value in range(4, 45, 4):
        expected.append(f'!F1 {value}')
        if value != 44:
            expected.append('+')
    expected += ['xx', 'mm'] + ['Y']*14 + ['O']
    _require(lines == expected, 'Original SA6 driver differs from the reviewed command sequence.')
    return dict(model_file='Straight_Wing_20b_35c.asw', speed=20., alpha=12.,
                control_tokens=[str(v) for v in range(4, 45, 4)], requested_nodes=None,
                node_count_token=None,
                filename_warning='Post_Stall_15c.sh actually invokes35c; invocation controls pairing.')


def decode_postprocessor(text):
    """Read source-labelled control associations, never execute or fit MATLAB."""
    blocks = list(re.finditer(r'^Clark_Y_Steady_chord\s*=\s*\[(.*?)^\s*\];', text, re.M | re.S))
    _require(len(blocks) == 1 and len(re.findall(r'^Clark_Y_Steady_chord\s*=', text, re.M)) == 1,
             'Expected one original chordwise MATLAB matrix.')
    match = blocks[0]
    start_line = text.count('\n', 0, match.start(1)) + 1
    rows = []
    for offset, raw_line in enumerate(match[1].splitlines()):
        _require(bool(raw_line.strip()), 'Empty or unreviewed MATLAB matrix row.')
        tokens = raw_line.split()
        _require(len(tokens) == 17, 'Original MATLAB matrix requires 17 columns.')
        fields = [polar.printed_value(token) for token in tokens]
        _require(all(field['value'] is not None for field in fields), 'Nonfinite MATLAB matrix token.')
        index = len(rows)
        _require(tokens[0] == str(4*index), 'Original MATLAB control sequence changed.')
        rows.append(dict(matrix_row_index=index, line_number=start_line+offset, raw_line=raw_line,
                         tokens=tokens, control_token=tokens[0], control_value=fields[0]['value'],
                         synthetic_zero=index == 0))
    _require(len(rows) == 12 and all(polar._number(t) == 0 for t in rows[0]['tokens']),
             'Expected synthetic zero plus eleven original MATLAB control rows.')
    columns = {variant: {'Cl': 4+4*i, 'Cn': 5+4*i} for i, variant in enumerate(CHORDWISE)}
    evidence = {}
    for channel, number, label in [('Cl', 3, 'Rolling'), ('Cn', 4, 'Yawing')]:
        starts = list(re.finditer(r'^figure\(' + str(number) + r'\)\s*$', text, re.M))
        _require(len(starts) == 1, 'Missing or ambiguous MATLAB plot association.')
        begin = starts[0].end()
        following = re.search(r'^figure\(', text[begin:], re.M)
        end = begin+following.start() if following else len(text)
        section = text[begin:end]
        source_lines = []
        for i, (variant, fraction, marker) in enumerate(zip(
                CHORDWISE, ('0.15', '0.20', '0.3', '0.35'), ('s', 'o', 'd', 'v')), 1):
            column = columns[variant][channel]
            expression = ("plot(Clark_Y_Steady_chord(1:end,1),Clark_Y_Steady_chord(1:end,"
                          + str(column) + "),'r" + marker + "','MarkerFaceColor','r',MarkerSize=10)")
            plots = [m for m in re.finditer(r'^' + re.escape(expression) + r'\s*$', section, re.M)]
            _require(len(plots) == 1, 'MATLAB native channel/variant plot column changed.')
            legends = list(re.finditer(r'^leg' + str(i) + r'\s*=\s*"\$c_\{\\delta_F\} = '
                + re.escape(fraction) + r'c,.*ASWING,.*$', section, re.M))
            _require(len(legends) == 1, 'MATLAB ASWING variant label changed.')
            source_lines.append(dict(variant=variant, column_1based=column,
                plot_line=text.count('\n', 0, begin+plots[0].start())+1,
                legend_line=text.count('\n', 0, begin+legends[0].start())+1))
        xlabel = "xlabel('Aileron deflection in deg')"
        ylabel = "ylabel('" + label + " moment coefficient')"
        _require(section.count(xlabel) == section.count(ylabel) == 1,
                 'MATLAB control units or coefficient label changed.')
        legend_lines = [line.strip() for line in section.splitlines() if line.startswith('legend(')]
        _require(len(legend_lines) == 1 and re.findall(r',leg([1-4])[,)]', legend_lines[0]) == ['1','2','3','4'],
                 'MATLAB plot legend ordering changed.')
        evidence[channel] = dict(variants=source_lines,
            units_line=text.count('\n', 0, begin+section.index(xlabel))+1, units='degree')
    return dict(array_name='Clark_Y_Steady_chord', rows=rows, columns_1based=columns,
                plot_evidence=evidence, synthetic_zero_excluded=True)


def _postprocessor_binding(postprocessor, declaration, variant, row, fmat_text):
    """An exact two-channel witness binds the unchanged complete fmat row."""
    source = declaration['rows'][row['operating_point']]
    matched = []
    for name in ('Cl', 'Cn'):
        column = declaration['columns_1based'][variant][name]
        token = source['tokens'][column-1]
        _require(token == row['fields'][name]['token'], 'MATLAB/fmat coefficient tokens do not match exactly.')
        occurrences = list(re.finditer(r'\b'+name+r'\s*=\s*(\S+)', fmat_text))
        _require(len(occurrences) == 1 and occurrences[0].group(1) == token,
                 'Missing or ambiguous native coefficient witness.')
        matched.append(dict(name=name, token=token, postprocessor_line=source['line_number'],
            postprocessor_column_1based=column,
            fmat_line=fmat_text.count('\n', 0, occurrences[0].start(1))+1))
    return dict(kind=POSTPROCESSOR_BINDING, postprocessor_path=postprocessor,
        variant=variant, missing_original_driver=True, producer_execution_authenticated=False,
        array_name=declaration['array_name'], matrix_row_index=source['matrix_row_index'],
        matrix_row_tokens=list(source['tokens']), matched_fields=matched,
        control=dict(name='F1', token=source['control_token'], value=source['control_value'], units='degree',
                     source_line=source['line_number'], source_column_1based=1),
        plot_evidence={name: dict(declaration['plot_evidence'][name], variants=[e for e in
            declaration['plot_evidence'][name]['variants'] if e['variant'] == variant]) for name in ('Cl', 'Cn')},
        qualification='Original MATLAB labels and exact Cl/Cn tokens bind this fmat row to its declared control. '
                      'No original shell invocation is retained for this variant; historical execution/startup remains unverified. '
                      'All six original fmat coefficients remain targets. The synthetic zero row and experimental columns add no targets.')


def _settings(row, count, level, rho, rho_token, control):
    return dict(panels=count, mesh_level=level, base_panels=64,
        mesh_source='fallback64; historical mesh not recovered',
        alpha=row['metadata']['alpha']['value'], alpha_token=row['metadata']['alpha']['token'],
        speed=row['metadata']['speed']['value'], density=rho, density_token=rho_token,
        density_assumption='model rhoSL; archived rho/rhoSL1 and q245.1200 atV20 agree',
        mach=0., beta=0., controls={'1': control} if control is not None else None,
        freeze_influences=True, beam_interpolation='natural-v1', circulation_method='auto',
        stall=True, stall_factor=40., stall_width=.05, wake_core_ratio=.25,
        aero_lag=True, body_added_mass_factor=1.)


def plan(root, *, comparison_scopes=()):
    _require(len(set(comparison_scopes)) == len(comparison_scopes) and
             all(scope in (control_scope.SCOPE, state_scope.SCOPE, mass_scope.SCOPE) for scope in comparison_scopes),
             'Provide unique supported SA6 comparison scopes.')
    root = Path(root).resolve()
    cache = root/'.reference/isae-validation'/REVISION
    manifest_path = cache.parent/'manifest.json'
    raw = manifest_path.read_bytes()
    _require(hashlib.sha256(raw).hexdigest() == MANIFEST_SHA256, 'Original manifest changed.')
    manifest = json.loads(raw)
    folders = list((cache/'1 - Aerodynamics/SA - Steady Aerodynamics Cases').glob('SA - 6 - *'))
    _require(len(folders) == 1, 'Missing/ambiguous SA6 family.')
    folder = folders[0]
    models = {p.stem.removeprefix('Straight_Wing_'): p for p in folder.rglob('*.asw')}
    _require(set(models) == set(CHORDWISE+SPANWISE), 'Original seven-model inventory changed.')
    tables = sorted(folder.rglob('*.fmat_*'))
    _require(len(tables) == 44, 'Original44 fmat inventory changed.')
    driver = folder/'Simulation/chordwise/Post_Stall_15c.sh'
    shells = sorted(folder.rglob('*.sh'))
    aswing_drivers = [p for p in shells if re.search(r'(?mi)^[^#\n]*\baswing\s', p.read_text())]
    _require(aswing_drivers == [driver], 'Original ASWING driver inventory changed.')
    declaration = decode_driver(driver.read_text())
    postprocessor = folder/POSTPROCESSOR
    originals = list(models.values()) + tables + shells + [postprocessor]
    for path in originals:
        p = polar._pin(path, root)
        upstream = manifest['files'][path.relative_to(cache).as_posix()]
        _require(p['sha256'] == upstream['sha256'] and p['bytes'] == upstream['bytes'], 'Original bytes changed: '+str(path))
    postprocessor_pin = polar._pin(postprocessor, root)
    _require(postprocessor_pin['sha256'] == POSTPROCESSOR_SHA256, 'Original MATLAB source changed.')
    postprocessor_declaration = decode_postprocessor(postprocessor.read_text())
    helpers = [polar._pin(p, root) for p in
               (Path(__file__).resolve(), root/'scripts/isae_suite_polars.py', manifest_path)]
    # Preserve the two XFOIL drivers as inventory evidence, never ASWING setup.
    helpers += [polar._pin(p, root) for p in shells if p != driver]
    jobs = []
    for variant in CHORDWISE:
        model = models[variant]
        selected = [p for p in tables if p.name.startswith(model.stem+'.fmat_')]
        _require([int(p.suffix.split('_')[-1]) for p in selected] == list(range(1, 12)), 'Missing/duplicate fmat operating points.')
        rho, rho_token = polar._rho_sl(model.read_text())
        _require(rho == 1.2256, 'Original density changed.')
        witness_pairs = set()
        for path in selected:
            fmat_text = path.read_text()
            row = decode_fmat(fmat_text)
            _require(row['operating_point'] == int(path.suffix.split('_')[-1]), 'File/index mismatch.')
            expected = dict(mach=0., pg=1., chord=.254, span=1.524, area=.3871,
                            q=245.12, speed=20., alpha=12., beta=0., rho_ratio=1., Wx=0., Wy=0., Wz=0.)
            _require({k: v['value'] for k, v in row['metadata'].items()} == expected, 'Unreviewed fmat operating metadata.')
            binding = _postprocessor_binding(postprocessor_pin['path'], postprocessor_declaration,
                                             variant, row, fmat_text)
            pair = tuple(field['token'] for field in binding['matched_fields'])
            _require(pair not in witness_pairs, 'Ambiguous repeated MATLAB/fmat witness pair within variant.')
            witness_pairs.add(pair)
            has_driver = variant == '20b_35c'
            control = binding['control']['value']
            if has_driver:
                _require(control == float(declaration['control_tokens'][row['row_index']]),
                         'Original shell/MATLAB control association disagrees.')
            sources = [polar._pin(p, root) for p in (model, path)]
            if has_driver:
                sources.append(polar._pin(driver, root))
            else:
                sources.append(postprocessor_pin)
            for level, count in enumerate((64, 128)):
                job = dict(id=f'SA-6:{model.stem}:op{row["operating_point"]:03d}:n{count}',
                    case_id='SA-6', adapter='sa6', model_path=sources[0]['path'], table_path=sources[1]['path'],
                    driver_path=driver.relative_to(root).as_posix() if has_driver else None,
                    row_index=row['row_index'], expected_outputs=6, required_outputs=list(OUTPUTS),
                    reference_row=row, settings=_settings(row, count, level, rho, rho_token, control),
                    sources=sources+helpers, driver_declarations=declaration if has_driver else None,
                    execution_route='rigid_static_coefficients', blocker_code=None, unsupported_reason=None,
                    expected_operations={'cold_rigid_calls': 1},
                    qualifications=list(QUALIFICATIONS), complete_family_reproduction=False)
                if not has_driver:
                    job['source_binding'] = copy.deepcopy(binding)
                    job['qualifications'].append(binding['qualification'])
                jobs.append(job)
        _require(len(witness_pairs) == 11, 'Incomplete native MATLAB/fmat witness coverage.')
    for variant in SPANWISE:
        jobs.append(dict(id=f'SA-6:Straight_Wing_{variant}:unpaired', case_id='SA-6', adapter='sa6',
            model_path=models[variant].relative_to(root).as_posix(), table_path=None, driver_path=None,
            row_index=None, expected_outputs=0, required_outputs=[], reference_rows=[], settings={},
            sources=[polar._pin(models[variant], root)]+helpers, execution_route='unsupported',
            blocker_code='NO_PAIRED_EXPORT', unsupported_reason=BLOCKS['NO_PAIRED_EXPORT'],
            expected_operations={'cold_rigid_calls': 0}, qualifications=list(QUALIFICATIONS),
            complete_family_reproduction=False))
    _require(len(jobs) == 91 and len({j['id'] for j in jobs}) == 91, 'SA6 job accounting changed.')
    static_jobs = list(jobs)
    if control_scope.SCOPE in comparison_scopes:
        jobs += control_scope.plan(root, static_jobs, polar._pin)
    if state_scope.SCOPE in comparison_scopes:
        jobs += state_scope.plan(root, static_jobs, polar._pin)
    if mass_scope.SCOPE in comparison_scopes:
        jobs += mass_scope.plan(root, static_jobs, polar._pin)
    return jobs


@lru_cache(maxsize=8)
def _canonical(root, comparison_scopes=()):
    return {j['id']: j for j in plan(root, comparison_scopes=comparison_scopes)}


def _verify(root, job):
    _require(all(polar._pin(root/p['path'], root) == p for p in job['sources']), 'Pinned source/helper changed.')
    scopes = ((mass_scope.SCOPE,) if mass_scope.identifies(job) else
              (state_scope.SCOPE,) if state_scope.identifies(job) else
              (control_scope.SCOPE,) if control_scope.identifies(job) else ())
    _require(_canonical(str(root), scopes).get(job['id']) == job, 'Job settings, targets or route differ from original plan.')


def verify_postprocessor_sources(root, job):
    """Strict canonical/source check for saved reports; only outer result is extra."""
    root = Path(root).resolve()
    record = {key: value for key, value in job.items() if key != 'result'}
    binding = record.get('source_binding')
    _require(isinstance(binding, dict) and binding.get('kind') == POSTPROCESSOR_BINDING
             and record.get('adapter') == 'sa6' and record.get('case_id') == 'SA-6'
             and record.get('execution_route') in ('rigid_static_coefficients', control_scope.ROUTE, state_scope.ROUTE, mass_scope.ROUTE)
             and record.get('driver_path') is None and record.get('driver_declarations') is None
             and binding.get('missing_original_driver') is True
             and binding.get('producer_execution_authenticated') is False,
             'Unreviewed MATLAB source binding or historical execution claim.')
    try:
        _verify(root, record)
    except OSError as exc:
        raise ValueError('MATLAB source-binding evidence is unavailable.') from exc
    return True


def verify_control_sources(root, job):
    """Only canonical original-source F1 jobs, with optional outer result."""
    root = Path(root).resolve()
    record = {key:value for key,value in job.items() if key != 'result'}
    control_scope.validate_record_contract(record)
    _verify(root, record)
    return True


def validate_result_contract(job, result):
    if mass_scope.identifies(job):
        return mass_scope.validate_result_contract(job, result)
    if state_scope.identifies(job):
        return state_scope.validate_result_contract(job, result)
    if control_scope.identifies(job):
        return control_scope.validate_result_contract(job, result)
    return True


def verify_state_sources(root, job):
    """Canonical complete-operator state scope; only outer result may be extra."""
    root = Path(root).resolve()
    record = {key:value for key,value in job.items() if key != 'result'}
    state_scope.validate_record_contract(record)
    _verify(root, record)
    return True


def verify_mass_sources(root, job):
    """Canonical original tensor scope; only outer result may be extra."""
    root = Path(root).resolve()
    record = {key:value for key,value in job.items() if key != 'result'}
    mass_scope.validate_record_contract(record)
    _verify(root, record)
    return True


def mesh_diagnostics(jobs, results):
    """Describe each static/F1/state/mass mesh pair separately, with no new gate."""
    groups = {}
    for job in jobs:
        if job.get('expected_outputs'):
            key = (job.get('comparison_scope', 'static'), job['model_path'], job['table_path'], job['row_index'])
            groups.setdefault(key, []).append(job)
    diagnostics = []
    for (scope, model, table, index), pair in sorted(groups.items()):
        pair = sorted(pair, key=lambda j:j['settings']['panels'])
        record = dict(case_id='SA-6', comparison_scope=scope, model_path=model, table_path=table,
            row_index=index, panels=[j['settings']['panels'] for j in pair], status='UNAVAILABLE', passed=None)
        if len(pair) == 2 and record['panels'] == [64,128]:
            retained = [results.get(j['id'], {}) for j in pair]
            if all(r.get('status') == 'computed' and r.get('numerical_pass') is True for r in retained):
                values = [{c['name']:c.get('predicted') for c in r.get('reference_checks', [])} for r in retained]
                names = pair[0]['required_outputs']
                if all(set(v) == set(names) and all(control_scope.finite(x) for x in v.values()) for v in values):
                    record.update(status='DIAGNOSTIC_ONLY', absolute_changes={n:abs(values[1][n]-values[0][n]) for n in names},
                        symmetric_relative_changes={n:(abs(values[1][n]-values[0][n])/max(abs(values[0][n]),abs(values[1][n]))
                            if max(abs(values[0][n]),abs(values[1][n])) else 0.) for n in names},
                        relative_definition='abs(n128-n64)/max(abs(n128),abs(n64)); both zero gives0')
        diagnostics.append(record)
    return diagnostics


def reference_checks(predicted, job, reason=None):
    checks = []
    for name in job['required_outputs']:
        ref = job['reference_row']['fields'][name]
        value = predicted.get(name)
        finite = value is not None and math.isfinite(value) and ref['value'] is not None
        error = abs(value-ref['value']) if finite else None
        checks.append(dict(name=name, predicted=value if finite else None, expected=ref['value'],
            expected_token=ref['token'], tolerance=ref['tolerance'], abs_error=error,
            passed=bool(finite and error <= ref['tolerance']), units='dimensionless',
            **({} if finite else {'unavailable_reason': reason or 'No finite current prediction.'})))
    return checks


def _report(job):
    report = copy.deepcopy(job)
    report.update(status='error', reference_match=False, numerical_pass=False, numerical_checks=[],
        reference_checks=reference_checks({}, job), physical_calls=0, sources_unchanged=False)
    return report


def validate_blocked(root, job):
    root = Path(root).resolve()
    _verify(root, job)
    _require(job['execution_route'] == 'unsupported' and job['blocker_code'] in BLOCKS,
             'Job is not an original unsupported scope.')
    report = _report(job)
    report.update(status='unsupported', sources_unchanged=True, seconds=0.,
                  reference_checks=reference_checks({}, job, job['unsupported_reason']))
    return report


def stability_coefficients(force, moment, alpha_degrees, qS, chord, span):
    """Body x-aft/z-up wrench -> archived x-forward/z-down stability axes.

    Same rotation as derivatives.stability_rotation, expressed independently
    with scalars so decoder/unit tests need no production or NumPy imports.
    """
    c, s = math.cos(math.radians(alpha_degrees)), math.sin(math.radians(alpha_degrees))
    x, y, z = force
    mx, my, mz = moment
    values = dict(CX=(-c*x-s*z)/qS, CY=y/qS, CL=(-s*x+c*z)/qS,
                  Cl=(-c*mx-s*mz)/(qS*span), Cm=my/(qS*chord), Cn=(s*mx-c*mz)/(qS*span))
    return {key: float(value) for key, value in values.items()}


def run(root, job):
    """One unchanged-model cold rigid solve, never a fitted or retried state."""
    root = Path(root).resolve()
    if mass_scope.identifies(job):
        return mass_scope.run(root, job, _verify)
    if state_scope.identifies(job):
        return state_scope.run(root, job, _verify)
    if control_scope.identifies(job):
        return control_scope.run(root, job, _verify)
    if job['execution_route'] == 'unsupported':
        return validate_blocked(root, job)
    start = time.monotonic()
    report = _report(job)
    try:
        _verify(root, job)
        import numpy as np
        from openswing import asw, aero
        for module in (asw, aero):
            _require(Path(module.__file__).resolve() == root/'openswing'/(module.__name__.split('.')[-1]+'.py'),
                     'Production import resolved outside declared repository.')
        model = asw.parse_asw((root/job['model_path']).read_text(), beam_interpolation='natural-v1')
        s = job['settings']
        _require(float(model.constants[1]) == s['density'], 'Density declaration/parser mismatch.')
        _require(np.array_equal(model.reference[0], [.3871, .254, 1.524]) and
                 np.array_equal(model.reference[1], [0., 0., 0.]), 'Original coefficient references changed.')
        keys = ('speed', 'alpha', 'beta', 'density', 'mach', 'freeze_influences', 'stall',
                'stall_factor', 'stall_width', 'wake_core_ratio', 'aero_lag', 'body_added_mass_factor')
        condition = aero.FlightCondition(**{k: s[k] for k in keys}, controls={int(k): v for k, v in s['controls'].items()})
        report['physical_calls'] = 1
        result = aero.solve_rigid(model, condition, panels=s['panels'], circulation_method=s['circulation_method'])
        checks = report['numerical_checks']
        checks.extend([dict(name='no parser diagnostics', passed=not model.diagnostics, diagnostics=list(model.diagnostics)),
                       dict(name='converged', passed=bool(result['converged']))])
        residual = float(result['residual'])
        checks.append(dict(name='circulation residual', value=residual if math.isfinite(residual) else None,
                           tolerance=1e-8, passed=math.isfinite(residual) and residual <= 1e-8))
        force, moment, counts = polar.reconstructed_wrench(model, result)
        qS = .5*s['density']*s['speed']**2*model.reference[0, 0]
        chord, span = model.reference[0, 1:]
        predicted = stability_coefficients(force, moment, s['alpha'], qS, chord, span)
        c, sn = math.cos(math.radians(s['alpha'])), math.sin(math.radians(s['alpha']))
        actual = dict(CX=-result['CD'], CY=result['CY'], CL=result['CL'],
            Cl=c*result['Cl']+sn*result['Cn'], Cm=result['Cm'], Cn=-sn*result['Cl']+c*result['Cn'])
        errors = {name+' total wrench normalization': abs(predicted[name]-actual[name]) for name in OUTPUTS}
        errors.update({'reported total force': float(np.max(abs(force-result['force']))/qS),
            'reported total moment': float(np.max(abs(moment-result['moment']))/(qS*chord)),
            'near-field drag decomposition': abs(result['CD']-sum(result[k] for k in
                ('CDi_near', 'CDp', 'CDbody', 'CDam', 'CDeng', 'CDrate')))})
        for name, error in errors.items():
            error = float(error)
            checks.append(dict(name=name, value=error if math.isfinite(error) else None,
                               tolerance=2e-10, passed=math.isfinite(error) and error <= 2e-10))
        report['reference_checks'] = reference_checks(predicted, job)
        report['numerical_pass'] = all(c['passed'] for c in checks) and all(math.isfinite(v) for v in predicted.values())
        report['status'] = 'computed' if report['numerical_pass'] else 'numerical_failure'
        report['reference_match'] = report['numerical_pass'] and all(c['passed'] for c in report['reference_checks'])
        report['result'] = dict(predicted={k: float(v) if math.isfinite(v) else None for k, v in predicted.items()},
            residual=residual if math.isfinite(residual) else None, panels=result['panels'],
            mesh_discretization=result.get('mesh_discretization'), force=force.tolist(), moment=moment.tolist(),
            wrench_component_counts=counts, controls=s['controls'],
            coefficient_axes='Stability x forward, y right, z down; CL=-Fz/qS.',
            circulation_solver=result.get('circulation_solver'))
    except Exception as exc:
        report.update(status='error', numerical_pass=False, reference_match=False,
                      error_type=type(exc).__name__, error=str(exc))
    finally:
        try:
            stable = all(polar._pin(root/p['path'], root) == p for p in job['sources'])
        except OSError:
            stable = False
        report['sources_unchanged'] = stable
        if not stable:
            report.update(status='source_mismatch', numerical_pass=False, reference_match=False)
        report['seconds'] = time.monotonic()-start
    nonfinite = []
    def clean(value, path=''):
        if isinstance(value, float) and not math.isfinite(value):
            nonfinite.append(path)
            return None
        if isinstance(value, dict):
            return {k: clean(v, path+'.'+k) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [clean(v, path+f'[{i}]') for i, v in enumerate(value)]
        return value
    report = clean(report)
    report['nonfinite_fields'] = nonfinite
    if nonfinite:
        report.update(status='numerical_failure', numerical_pass=False, reference_match=False)
    return report
