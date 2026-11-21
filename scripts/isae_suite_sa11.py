"""All sixteen literal SA11 polars, with explicit input/normalization blockers.

Import and planning are source-only. Four baseline/extension 0.70/0.80 tables
use the rigid polar worker. Eight 0.75/0.78 tables have normalization conflicts;
the original winglet inputs also encounter reviewed import/attachment blockers.
Every archived row and all seven fields remain required on both declared grids.
"""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path

try:
    from . import isae_suite_polars as polar
    from . import isae_suite_extra_polars as extra
except ImportError:
    import isae_suite_polars as polar
    import isae_suite_extra_polars as extra

REVISION = polar.REVISION
MANIFEST_SHA256 = extra.MANIFEST_SHA256
VARIANTS = ('wing_alone', 'wing_extension', 'wingtip_up', 'wingtip_up_and_down')
DIRECTORIES = dict(zip(VARIANTS, ('wing_alone', 'wing_extension', 'Wing_tip_up', 'Wing_tip_up_and_down')))
LABELS = ('0_70', '0_75', '0_78', '0_80')
SPEEDS = dict(zip(LABELS, (240., 255., 266., 272.)))
GRIDS = (64, 128)
OUTPUTS = tuple(polar.OUTPUTS)
MODEL_SHA256 = {
    'wing_alone': '9aec506c70a96ee20f6b2cb2344afd35c1939da44ed6188d4b7a7555696b4d1a',
    'wing_extension': 'd36f2aacd601e079fc7206d882da8758fffab80ede3c8f0b8f001b86e7d9cfd4',
    'wingtip_up': 'a380f99376542087a3c3cc072ff4f5e9fb9542d8468d071fab36323322f05ac8',
    'wingtip_up_and_down': 'a5c9cffdf40fc848a3940ac4730787db228a89d8e0a2936b89d152462293577c',
}
BLOCKER = 'ARCHIVED_NORMALIZATION_CONFLICT'
BLOCKED_REASON = (
    'Original 0.75/0.78 lift and drag coefficients imply rho*S about104.7 times '
    'the supplied model normalization (S about97.67m2 at literal rhoSL, versus '
    'literal Sref0.9329m2). Historical model/reference/density/units are unresolved; '
    'all seven targets remain required and no model or output is rescaled.')
INPUT_BLOCKS = {
    'wingtip_up': ('ORIGINAL_JOINT_SCALING',
        'Original Joint multiplier has five values including integer columns; the documented Joint syntax has two station multipliers. '
        'The current literal parser rejects line32. Native acceptance of this malformed row is not established; no bundled correction is substituted.'),
    'wingtip_up_and_down': ('ORIGINAL_ATTACHMENT_DOMAIN',
        'Original Joint stations are +/-12.426 while the scaled beam1 domain is +/-1.2426. '
        'The literal model parses, but mandatory attachment meshing rejects these stations. No joint rescaling or bundled correction is substituted.'),
}
QUALIFICATIONS = [
    'Unchanged original model, driver and raw table are pinned; no upstream command or experimental postprocessing is executed.',
    'All four original paired inputs and sixteen tables are covered; the separate cant0 input has no paired archived polar and remains unpaired.',
    'Declared nominal64/128 requests use current cosine mesh rules; no historical NODE grid or mandatory-node placement is recovered.',
    'PG mach=None means current true speed divided by atmospheric sound speed at declared sea level; it is not the approximate filename label.',
    'The original report says PG enabled, but original KK/MM parser behavior and startup PG/K/F state are not recovered. No absent-command PG-off inference.',
    'Literal Constant rhoSL and speed commands are retained; sea-level atmosphere and current influence geometry are declared reconstruction choices.',
    'The existing natural-v1 rigid-polar route, stall law and local-Mach safeguards are retained; every archived stall row remains required.',
    '0.75/0.78 normalization-conflict tables are unsupported, with every row/channel preserved; no rescaling or inferred replacement geometry.',
    'Original winglet Joint import/attachment blockers are retained independently of normalization conflicts. Report-minus4 twist and bundled repaired inputs are separate diagnostics, never primary replacements.',
    'Baseline0.70 rows23 drag and37 lift also miss strict literal qS intervals slightly; those diagnostics and original precision gates are retained.',
    'Numerical validity, printed-precision agreement, mesh sensitivity and historical setup are separate; no whole-family completion is claimed.',
]
_TABLE_CACHE = {}
_MANIFEST_CACHE = {}


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _paths(root, variant, label):
    _require(variant in VARIANTS and label in LABELS, 'Unreviewed SA11 variant/Mach label.')
    cache = root/'.reference/isae-validation'/REVISION
    base = cache/'1 - Aerodynamics/SA - Steady Aerodynamics Cases'
    folders = list(base.glob('SA - 11 - *'))
    _require(len(folders) == 1, 'Missing or ambiguous original SA11 directory.')
    folder = folders[0]/'Aswing_Simulations'/DIRECTORIES[variant]
    spelling = 'wing_extentsion' if variant == 'wing_extension' else variant
    return cache, (folder/(variant+'.asw'), folder/f'{variant}_Ma_{label}.txt',
                   folder/f'{spelling}_polar_Ma_{label}.sh')


def _manifest(root):
    path = root/'.reference/isae-validation/manifest.json'
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    _require(digest == MANIFEST_SHA256, 'Original archive manifest changed.')
    if digest not in _MANIFEST_CACHE:
        _MANIFEST_CACHE[digest] = json.loads(raw)
    manifest = _MANIFEST_CACHE[digest]
    _require(manifest['revision'] == REVISION, 'Original archive revision changed.')
    return manifest


def _no_sidecars(model):
    _require(not any(model.with_suffix(suffix).exists() for suffix in ('.set','.pnt','.con')),
             'New startup sidecar requires explicit source/settings review.')


def _input_issue(model, variant):
    """Reviewed literal-source evidence; planning imports no numerical parser.

    Model hashes are checked before this function. Separate tests and the
    retained audit exercise the actual parser/mesher without an aero solve.
    """
    if variant not in INPUT_BLOCKS:
        return None
    code, reason = INPUT_BLOCKS[variant]
    lines = model.read_text().splitlines()
    start = lines.index('Joint')
    end = next(i for i in range(start+1,len(lines)) if lines[i].strip() == 'End')
    records = [dict(line=i+1,text=lines[i].strip()) for i in range(start+1,end)
               if lines[i].strip() and not lines[i].lstrip().startswith(('#','!'))]
    if variant == 'wingtip_up':
        _require(records[0]['line'] == 32 and records[0]['text'].split() == ['*','1','1','0.1','0.1','1'],
                 'Original Joint scaling evidence changed.')
    else:
        _require(len(records) == 4 and all(abs(float(r['text'].split()[2])) == 12.426
                 and abs(float(r['text'].split()[3])) == 12.426 for r in records),
                 'Original Joint attachment evidence changed.')
    return dict(code=code, reason=reason, joint_records=records,
                format_reference='reference/aswing_doc.txt:813; Joint scales t1/t2 only, not integer beam/type columns')


def decode_table(text):
    # SA10's reviewed 82-column FORMAT is shared by these SA11 exports. Its
    # family-specific planning, settings, counts and execution route are unused.
    rows = extra.decode_table(text, 10)
    for row in rows:
        for name, column in (('actual_speed', 69), ('actual_beta', 70), ('actual_alpha', 71)):
            row['fields'][name] = polar.printed_value(row['tokens'][column])
    return rows


def normalization_evidence(row, speed):
    """Printed intervals, not a fitted scale or a replacement reference target."""
    density, area = Decimal('1.2256'), Decimal('0.9329')
    velocity = Decimal(str(speed))
    qs = density*velocity**2*area/2
    channels = {}
    for force, coefficient in (('lift', 'CL'), ('drag', 'CD')):
        f, c = (Decimal(row['fields'][name]['token']) for name in (force, coefficient))
        hf, hc = (Decimal(5).scaleb(x.as_tuple().exponent-1) for x in (f, c))
        _require(f > hf and c > hc, 'Unreviewed normalization sign/zero interval.')
        lo, hi = (f-hf)/(c+hc), (f+hf)/(c-hc)
        channels[force] = dict(qS_interval=[str(lo), str(hi)], literal_qS_inside=lo <= qs <= hi,
            implied_area_at_literal_density=float(2*f/(density*velocity**2*c)))
    return dict(literal_qS=str(qs), literal_rhoSL=str(density), literal_Sref=str(area), channels=channels,
        interpretation='Only rho*S follows from force/coefficient/speed. Implied area assumes literal density/units; no historical geometry is identified.')


def _settings(row, speed, count, level):
    return dict(panels=count, mesh_level=level, base_panels=64,
        mesh_source='declared64/128 with current cosine spacing; no historical NODE/I request retained',
        alpha=row['fields']['alpha']['value'], alpha_token=row['fields']['alpha']['token'],
        speed=speed, density=1.2256, density_token='1.2256',
        density_assumption='literal Constant rhoSL; declared sea-level atmosphere',
        mach=None, freeze_influences=False, beta=0., beam_interpolation='natural-v1',
        circulation_method='auto', stall=True, stall_factor=40., stall_width=.05,
        wake_core_ratio=.25, aero_lag=True, body_added_mass_factor=1.)


def _table_jobs(root, variant, label, manifest):
    cache, paths = _paths(root, variant, label)
    model, table, driver = paths
    helpers = (Path(__file__).resolve(), root/'scripts/isae_suite_polars.py', root/'scripts/isae_suite_extra_polars.py')
    sources = [polar._pin(p, root) for p in (*paths, *helpers)]
    for path, source in zip(paths, sources):
        expected = manifest['files'].get(path.relative_to(cache).as_posix())
        _require(expected is not None and all(source[k] == expected[k] for k in ('bytes','sha256')),
                 'Original source differs from manifest: '+str(path))
    _require(sources[0]['sha256'] == MODEL_SHA256[variant], 'Original SA11 model changed.')
    input_issue = _input_issue(model, variant)
    if input_issue is not None:
        sources.append(polar._pin(root/'reference/aswing_doc.txt',root))
    _no_sidecars(model)
    declaration = extra.decode_driver(driver.read_text(), table.name)
    _require(declaration['model_file'] == model.name and declaration['speed'] == SPEEDS[label]
             and declaration['requested_nodes'] is None, 'Original model/speed/mesh declarations changed.')
    _require(all(s.split()[0].upper() in ('!V','!A') for s in declaration['scalar_commands']),
             'Unreviewed control/pose/power command.')
    rows = decode_table(table.read_text())
    tokens = declaration['alpha_tokens']
    _require(len(rows) == len(tokens) == 41, 'Original41-row accounting changed.')
    _require(polar._rho_sl(model.read_text()) == (1.2256, '1.2256'), 'Literal density changed.')
    lines = driver.read_text().splitlines()
    declaration['settings_commands'] = [dict(line=i+1,command=s.strip()) for i,s in enumerate(lines)
                                         if s.strip().lower() in ('kk','mm')]
    normalization_conflict = label in ('0_75','0_78')
    blocker_codes = ([BLOCKER] if normalization_conflict else []) + ([input_issue['code']] if input_issue else [])
    reasons = ([BLOCKED_REASON] if normalization_conflict else []) + ([input_issue['reason']] if input_issue else [])
    jobs = []
    for row, token in zip(rows, tokens, strict=True):
        fields = row['fields']; alpha = row['row_index']/4
        _require(polar._number(token) == fields['alpha']['value'] == fields['actual_alpha']['value'] == alpha,
                 'Original alpha command/actual/reference row differs.')
        _require(fields['speed']['value'] == fields['actual_speed']['value'] == SPEEDS[label]
                 and fields['beta']['value'] == fields['actual_beta']['value'] == 0
                 and fields['conv']['value'] == 1, 'Archived setup/convergence echo differs.')
        evidence = normalization_evidence(row, SPEEDS[label])
        for level,count in enumerate(GRIDS):
            jobs.append(dict(id=f'SA-11:{table.stem}:row{row["row_index"]:03d}:n{count}',
                case_id='SA-11', adapter='sa11', variant=variant, mach_label=label,
                model_path=sources[0]['path'], table_path=sources[1]['path'], driver_path=sources[2]['path'],
                row_index=row['row_index'], expected_outputs=7, required_outputs=list(OUTPUTS),
                settings=_settings(row, SPEEDS[label], count, level), sources=sources,
                reference_row=row, exact_driver_alpha_token=token, driver_declarations=declaration,
                archived_stall_flag=fields['stall']['value'], normalization_evidence=evidence,
                normalization_conflict=normalization_conflict, input_issue=input_issue,
                execution_route='unsupported' if blocker_codes else 'seven_fields',
                blocker_code=blocker_codes[0] if blocker_codes else None, blocker_codes=blocker_codes,
                unsupported_reason=' '.join(reasons) if reasons else None,
                qualifications=list(QUALIFICATIONS), complete_family_reproduction=False))
    return jobs


def plan(root):
    root = Path(root).resolve(); manifest = _manifest(root)
    jobs = [job for variant in VARIANTS for label in LABELS for job in _table_jobs(root, variant, label, manifest)]
    _require(len(jobs) == len({j['id'] for j in jobs}) == 1312, 'Incomplete/duplicate SA11 scope.')
    _require(sum(j['execution_route'] == 'unsupported' for j in jobs) == 984, 'Blocked scope changed.')
    return jobs


def _stable(root, job):
    try:
        return all(polar._pin(root/s['path'], root) == s for s in job['sources'])
    except OSError:
        return False


def _canonical(root, job):
    # Revalidate literal files before using a content-keyed cache. Inline blocked
    # rows share their82-job table catalog; workers never rebuild all1312 jobs.
    manifest = _manifest(root)
    _no_sidecars(root/job['model_path'])
    key = (str(root), job.get('variant'), job.get('mach_label'),
           tuple((p['path'],p['bytes'],p['sha256']) for p in job['sources']))
    if key not in _TABLE_CACHE:
        values = _table_jobs(root, job.get('variant'), job.get('mach_label'), manifest)
        _TABLE_CACHE[key] = {value['id']:value for value in values}
    _require(_TABLE_CACHE[key].get(job['id']) == job, 'SA11 job/source/target/settings differs from the declared literal plan.')


def _unsupported(job, reason, stable):
    checks = polar.reference_checks({}, job['reference_row'])
    for check in checks:
        check['unavailable_reason'] = reason
    return dict(id=job['id'], case_id='SA-11', adapter='sa11',
        status='unsupported' if stable else 'source_mismatch', numerical_pass=False, reference_match=False,
        physical_calls=0, sources_unchanged=stable, expected_outputs=7, required_outputs=list(OUTPUTS),
        reference_checks=checks, numerical_checks=[], blocker_code=job.get('blocker_code'),
        blocker_codes=job.get('blocker_codes',[]), input_issue=job.get('input_issue'),
        unsupported_reason=reason, normalization_evidence=job['normalization_evidence'],
        normalization_conflict=job['normalization_conflict'], qualifications=job['qualifications'],
        complete_family_reproduction=False, seconds=0.)


def validate_blocked(root, job):
    root = Path(root).resolve()
    if not _stable(root, job):
        return _unsupported(job, 'Pinned source changed.', False)
    _canonical(root, job)
    allowed = {BLOCKER} | {value[0] for value in INPUT_BLOCKS.values()}
    _require(job['execution_route'] == 'unsupported' and job['blocker_code'] in allowed,
             'Not a reviewed original-input/normalization blocker.')
    return _unsupported(job, job['unsupported_reason'], True)


def run(root, job):
    root = Path(root).resolve()
    if job['execution_route'] == 'unsupported':
        return validate_blocked(root, job)
    if not _stable(root, job):
        return _unsupported(job, 'Pinned source changed.', False)
    _canonical(root, job)
    _require(job['execution_route'] == 'seven_fields' and not job['normalization_conflict'],
             'Unreviewed SA11 physical route.')
    report = polar.run(root, deepcopy(job))
    report.update(required_outputs=list(OUTPUTS), expected_outputs=7, complete_family_reproduction=False,
        normalization_evidence=job['normalization_evidence'], normalization_conflict=False,
        archived_stall_flag=job['archived_stall_flag'],
        reference_scope='All seven original SA11 row outputs; declared PG/mesh, historical setup unresolved.')
    # Do not promote missing/duplicate or partial helper output to a match.
    checks = report['reference_checks']
    report['reference_match'] = bool(report.get('numerical_pass') and len(checks) == 7
        and {c['name'] for c in checks} == set(OUTPUTS) and all(c['passed'] for c in checks))
    return report
