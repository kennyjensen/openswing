"""Complete SA13 figure scope, blocked until original setup can be established.

Planning uses only pinned decoded data and the standard library. It never turns
the historical graph-outline experiments into original ASWING comparisons.
"""
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path

REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
MANIFEST_SHA256 = '813347a3bd9fcbd029a1ec86e0c3141f82422af26f33ebde7c2f732a16bf27f6'
DECODED = 'docs/validation/isae-sa13-sources.json'
DECODED_SHA256 = '439c59ead8599f99417ea53db7d146567cd6f4918e672c339ca0694f76499397'
REPORT_TEXT = '.reference/isae-validation/reports/Experimental_validation_of_ASWING_Part_1_Aerodynamics_V4.txt'
REPORT_TEXT_SHA256 = '37899d50a5ed73f82cfba79cc82b8a968792c70c7d3572548fd11fcb1eff8096'
COUNTS = {'r33': (64, 36, 64), 'r101': (74, 74, 54),
          'rs1': (65, 24, 65), 'pressure': (103, 103, 56)}
LABELS = ('Continuous ASWING 5.96', 'Discrete ASWING 5.96')
BLOCKER = 'ORIGINAL_BODY_SETUP_UNAVAILABLE'
REASON = ('Original radius/derivative tables, interpolation and closure, operating/build/mesh '
          'settings, and sensor/output normalization are not retained. A plotted outline '
          'does not establish an original input. No exact runnable reference pair is known.')
QUALIFICATIONS = [
    'All eight ASWING-labelled series and every original row are retained; no mesh duplication or fitted target.',
    'Continuous blue curves use a modified ASWING radius-derivative implementation (report section6.2, page40). '
    'Discrete red curves retain the original-discretization label; the actual historical build remains unknown.',
    'Figure floating-point samples have no printed-decimal precision contract. Tolerance is unset, not inferred from float rendering.',
    'Unavailable NaN/padding ordinates remain required unavailable slots, never zeros or passes.',
    'Experimental series and unlabeled outlines remain source context, not acceptance targets.',
    'The report describes surface-sensor velocities and steady Bernoulli, but the saved pressure-output mapping '
    'is unresolved; original sensor locations are missing. The discrete curve has a separate geometry-only identity.',
    'No original model, driver or native numerical table exists in this archived family. '
    'Conditional outline reconstructions and their historical kernels are not current parity evidence.',
]


def _require(condition, message):
    if not condition:
        raise ValueError('SA13 '+message)


def _pin(root, path):
    path = Path(path)
    if not path.is_absolute():
        path = root/path
    data = path.read_bytes()
    return dict(path=path.relative_to(root).as_posix(), bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest())


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _source_diagnostics(case, variant):
    if case['name'] != 'pressure' or variant != 'discrete':
        return []
    curve, upper, lower = [case['series'][i]['xy'] for i in (2, 3, 4)]
    errors, previous, ended = [], None, False
    for (x, y), hi, lo in zip(curve, upper, lower, strict=True):
        if y is None:
            ended = True
            continue
        _require(not ended and None not in hi+lo and x == hi[0] == lo[0],
                 'pressure outline and ordinate stations differ.')
        radius = (hi[1]-lo[1])/2
        if previous is not None:
            _require(x > previous[0], 'pressure outline stations must increase.')
        slope = 0. if previous is None else (radius-previous[1])/(x-previous[0])
        errors.append(abs(y-(100*slope*slope-5)))
        previous = x, radius
    _require(len(errors) == 56 and max(errors) < 2e-12, 'archived pressure geometry identity changed.')
    return [dict(code='PRESSURE_OUTPUT_MAPPING_UNRESOLVED',
        formula='Y_i = 100*((R_i-R_(i-1))/(x_i-x_(i-1)))^2 - 5; slope_0=0',
        finite_values=56, retained_values=103, maximum_identity_error=max(errors),
        physical_pressure_match=False,
        interpretation='Exact relation in stored data, including an inferred -5 offset; '
        'not an established full-Bernoulli pressure coefficient or a solver pass.',
        documentation='docs/validation/isae-sa13-pressure-geometry-20261109.md')]


def plan(root):
    root = Path(root).resolve()
    cache = root/'.reference/isae-validation'/REVISION
    manifest_path = cache.parent/'manifest.json'
    _require(_pin(root, manifest_path)['sha256'] == MANIFEST_SHA256, 'original manifest changed.')
    _require(_pin(root, DECODED)['sha256'] == DECODED_SHA256, 'decoded source evidence changed.')
    _require(_pin(root, REPORT_TEXT)['sha256'] == REPORT_TEXT_SHA256, 'primary report text changed.')
    manifest = json.loads(manifest_path.read_text())
    decoded = json.loads((root/DECODED).read_text())
    _require(manifest['revision'] == decoded['revision'] == REVISION, 'revision changed.')
    cases = decoded['cases']
    _require([c['name'] for c in cases] == list(COUNTS), 'four-figure inventory changed.')
    folder = cache/Path(cases[0]['path']).parent
    _require({p.name for p in folder.iterdir()} == {c['filename'] for c in cases},
             'original family inventory changed; review additional files.')
    report_pdf = cache/decoded['isae_report']['path']
    report_pin = _pin(root, report_pdf)
    _require(report_pin['sha256'] == decoded['isae_report']['sha256'] ==
             manifest['files'][decoded['isae_report']['path']]['sha256'], 'primary report PDF changed.')
    common = [_pin(root, p) for p in (manifest_path, root/DECODED, root/REPORT_TEXT,
                                     root/'scripts/isae_suite_sa13.py')] + [report_pin]
    jobs = []
    for case in cases:
        source = _pin(root, cache/case['path'])
        expected = manifest['files'][case['path']]
        _require(source['sha256'] == case['sha256'] == expected['sha256'] and
                 source['bytes'] == expected['bytes'], 'original figure changed.')
        series = case['series']
        _require([s['label'] for s in series[1:3]] == list(LABELS) and len(series) == 5,
                 'original series classification changed.')
        size, continuous_finite, discrete_finite = COUNTS[case['name']]
        for index, (variant, finite_count) in enumerate(zip(('continuous', 'discrete'),
                                                          (continuous_finite, discrete_finite)), 1):
            curve = series[index]
            _require(len(curve['xy']) == size, 'source row count changed.')
            observations = []
            for row, (x, y) in enumerate(curve['xy']):
                _require((x is None or _finite(x)) and (y is None or _finite(y)), 'invalid source sample.')
                observations.append(dict(name=f'ordinate_row{row+1:03d}', source_row_1based=row+1,
                    source_series_index=index, source_location=curve['location'], coordinate=x,
                    coordinate_hex=float(x).hex() if x is not None else None,
                    expected=y, expected_hex=float(y).hex() if y is not None else None,
                    expected_token=None, tolerance=None,
                    unavailable_reason='Original figure ordinate is unavailable (NaN/padding).' if y is None else None))
            _require(sum(o['expected'] is not None for o in observations) == finite_count,
                     'finite reference accounting changed.')
            jobs.append(dict(id=f'SA-13:{case["name"]}:{variant}', case_id='SA-13', adapter='sa13',
                model_path=None, driver_path=None, table_path=source['path'],
                target_kind='modified_aswing_figure' if variant == 'continuous' else 'original_discretization_figure',
                variant=variant, curve_label=curve['label'], figure=case['name'],
                expected_outputs=size, finite_reference_outputs=finite_count,
                unavailable_reference_outputs=size-finite_count, observations=observations,
                source_context_series=[deepcopy(series[i]) for i in (0, 3, 4)],
                figure_axes=deepcopy(case['axes']), settings=None,
                caption_incidence_degrees=case['isae_report_alpha'],
                source_hull=case['primary_hull'], execution_route='unsupported',
                blocker_code=BLOCKER, unsupported_reason=REASON,
                source_diagnostics=_source_diagnostics(case, variant),
                sources=[source]+common, qualifications=list(QUALIFICATIONS),
                production_imports=0, complete_family_reproduction=False))
    _require(len(jobs) == 8 and sum(j['expected_outputs'] for j in jobs) == 612,
             'complete source coverage changed.')
    return jobs


@lru_cache(maxsize=4)
def _canonical(root):
    return {j['id']: j for j in plan(root)}


def verify_reference_sources(root, job):
    root = Path(root).resolve()
    _require(all(_pin(root, p['path']) == p for p in job['sources']), 'source/helper changed.')
    decoded = json.loads((root/DECODED).read_text())
    folder = (root/job['table_path']).parent
    _require({p.name for p in folder.iterdir()} == {c['filename'] for c in decoded['cases']},
             'original family inventory changed.')
    _require(_canonical(str(root)).get(job['id']) == job, 'source targets, classification or blocked route changed.')


def reference_contract(job):
    return {o['name']: {key: o[key] for key in ('expected', 'expected_hex', 'expected_token',
                    'tolerance', 'source_row_1based', 'coordinate')} for o in job['observations']}


def _checks(job):
    return [dict(name=o['name'], predicted=None, expected=o['expected'],
                 expected_hex=o['expected_hex'], expected_token=None, tolerance=None,
                 source_row_1based=o['source_row_1based'], coordinate=o['coordinate'],
                 abs_error=None, passed=False, unavailable_reason=o['unavailable_reason'] or REASON)
            for o in job['observations']]


def validate_result_contract(job, result):
    _require(job['execution_route'] == 'unsupported' and job['blocker_code'] == BLOCKER,
             'unexpected execution route.')
    _require(result.get('id') == job['id'] and result.get('case_id') == 'SA-13', 'result identity changed.')
    _require(result.get('status') == 'unsupported' and result.get('numerical_pass') is False and
             result.get('reference_match') is False and result.get('sources_unchanged') is True,
             'blocked scope cannot become a computed result.')
    _require(result.get('reference_checks') == _checks(job), 'blocked targets or unavailable values changed.')
    _require(result.get('source_diagnostics') == job['source_diagnostics'],
             'source diagnostic was removed or changed into a pressure validation claim.')
    _require(result.get('physical_calls') == 0 and result.get('production_imports') == 0 and
             result.get('physical_solver_calls', 0) == 0 and result.get('numerical_checks') == [],
             'blocked scope must perform no physical calculation.')
    return True


def validate_blocked(root, job):
    verify_reference_sources(root, job)
    result = deepcopy(job)
    result.update(status='unsupported', numerical_pass=False, reference_match=False,
                  reference_checks=_checks(job), numerical_checks=[], physical_calls=0,
                  production_imports=0, sources_unchanged=True, seconds=0.)
    validate_result_contract(job, result)
    return result


def run(root, job):
    return validate_blocked(root, job)
