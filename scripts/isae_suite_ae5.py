"""AE5 original modal/boundary ledger with unresolved input pairings explicit.

No numerical imports or guessed speed/material mapping on this blocked route.
The literal driver's independent numerical diagnostic is not a reference pass.
"""
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
FAMILY = '4 - Aeroelasticity/AE - Aeroelastic Cases/AE-5-D Low Aspect Ratio Wing - Flutter Boundaries'
SCHEMA = 'isae-ae5-original-source-ledger-v1'
QUALIFICATIONS = [
    'The literal driver has 22 speeds, while eig.txt has 29 indexed points. No speed is inferred from eigenvalue agreement.',
    'Literal GJ=8000, EInn=2.5, EIcn=0 conflict with report Table10 GJ=1.2, EInn=18499, EIcn=.0023.',
    'The alternate horizontal model terminates with an unterminated Engine block and has different material/geometry inputs.',
    'Analysis.m explicitly labels 46 ASWING boundary values; report Tables5/6 contribute nine separately retained targets.',
    'Boundary arrays and report tables have no established identical operating point. Their conflicting numbers are not averaged or substituted.',
    'Other CSV, EPS and plotted static/experimental material remains in the full source catalog, outside this modal/boundary denominator.',
    'Literal-source numerical checks are separate evidence and do not turn unresolved archived comparisons into passes.',
]


def require(ok, message):
    if not ok: raise ValueError('AE5: '+message)


def pin(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def cell(name, token, source, line, **metadata):
    value = Decimal(token.replace('D', 'E'))
    require(value.is_finite(), 'nonfinite native value')
    half = Decimal(10)**value.as_tuple().exponent/2
    return dict(name=name, expected=float(value), tolerance=float(half),
                exact_decimal_expected=str(value), exact_decimal_tolerance=str(half),
                source=str(source), line=line, token=token, **metadata)


def native_rows(path):
    rows = []
    lines = path.read_text().splitlines()
    require(lines[2].split() == ['#','Op.Point','Eigenvalue'], 'modal header changed')
    for line, text in enumerate(lines, 1):
        if not text.strip() or text.startswith('#'): continue
        tokens = text.split()
        require(len(tokens) == 3 and tokens[0].isdigit(), 'invalid modal row')
        for component, token in zip(('real','imaginary'),tokens[1:]):
            rows.append(cell(f'modal:line{line}:{component}',token,path,line,
                native_index=int(tokens[0]), component=component, units='1/s', IAS=None))
    require(len(rows) == 532 and {r['native_index'] for r in rows} == set(range(1,30)),
            'modal inventory changed')
    return rows


def boundary_rows(analysis, report):
    text = analysis.read_text()
    arrays = {}
    for match in re.finditer(r'^\s*(\w+)\s*=\s*\[([^\]]*)\];',text,re.M):
        arrays[match[1]] = (1+text[:match.start()].count('\n'), match[2].split())
    rows = []
    for layup, alpha, speed, frequency, count in (
        ('zero','alpha_0_90','V_O_90','f_0_90',7),
        ('positive','alpha_p_15','V_p_15','f_p_15',15),
        ('negative','alpha_m_15','V_m_15',None,2)):
        require(len(arrays[alpha][1]) == count, 'angle coordinates changed')
        for quantity, key, units in [('flutter_speed',speed,'m/s'),('flutter_frequency',frequency,'Hz')]:
            if key is None: continue
            line, values = arrays[key]
            require(len(values) == count, 'boundary array changed')
            for i,(angle,token) in enumerate(zip(arrays[alpha][1],values)):
                rows.append(cell(f'analysis:{layup}:{quantity}:{i}',token,analysis,line,
                    array=key,index=i,alpha=float(angle),alpha_token=angle,units=units,
                    dataset='Analysis.m explicit ASWING arrays'))
    require(len(rows) == 46, 'incomplete embedded boundaries')
    lines = report.read_text().splitlines()
    # Preserve every original ASWING table entry, separately from the arrays.
    for title, quantity, stride, offset, units in (
        ('Vf,exp','flutter_speed',7,3,'m/s'),
        ('ff,exp','flutter_frequency',7,3,'Hz')):
        start = lines.index(title, lines.index('PDF PAGE 19'))
        start = lines.index('Remark',start)+1
        for i in range(3):
            pos = start+i*stride+offset
            rows.append(cell(f'table5:{quantity}:layup{i}',lines[pos],report,pos+1,
                             layup_label=lines[start+i*stride],alpha=None,units=units,dataset='Report Table5'))
    start = lines.index('PDF PAGE 20')
    start = lines.index('[03/90]S',start)
    for i in range(3):
        pos = start+4*i+2
        token = lines[pos].split()[0]
        rows.append(cell(f'table6:divergence_speed:layup{i}',token,report,pos+1,
                         layup_label=lines[start+4*i],alpha=None,units='m/s',dataset='Report Table6'))
    require(len(rows) == 55, 'incomplete native boundary inventory')
    return rows


def plan(root):
    root = Path(root).resolve()
    cache = root/'.reference/isae-validation'/REVISION
    base = cache/FAMILY
    modal = base/'Flutter_Boundaries/eig.txt'
    analysis = base/'Flutter_Boundaries/Analysis.m'
    driver = base/'Flutter_Boundaries/[0_90]_3s_flutter.sh'
    model = base/'Flutter_Boundaries/[03_90].asw'
    alternate = base/'[0_3_90]_S/[03_90]_S.asw'
    report = cache.parent/'reports/Experimental_validation_of_ASWING_Part_4_Aeroelasticity_V4.txt'
    manifest_path = cache.parent/'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    sources = [pin(path) for path in (modal,analysis,driver,model,alternate)]
    for p in sources:
        original = manifest['files'][Path(p['path']).relative_to(cache).as_posix()]
        require(all(p[k] == original[k] for k in ('bytes','sha256')), 'pinned original changed')
    sources += [pin(report),pin(manifest_path),pin(__file__)]
    speeds = [float(x) for x in re.findall(r'^!V ([\d.]+)$',driver.read_text(),re.M)]
    require(speeds == list(range(9,31)), 'driver speeds changed')
    jobs = []
    for kind, observations, code in (
        ('modal',native_rows(modal),'OPERATING_INDEX_AND_MODEL_IDENTITY_UNRESOLVED'),
        ('boundaries',boundary_rows(analysis,report),'HISTORICAL_BENCH_AND_BOUNDARY_CONDITIONS_UNRESOLVED')):
        jobs.append(dict(id='AE-5:'+kind+':original',case_id='AE-5',family='AE-5',adapter='ae5',schema=SCHEMA,
            target_kind=kind, execution_route='unsupported', blocker_code=code,
            unsupported_reason='Original input/output correspondence is unresolved; preserve every target without inferred settings.',
            observations=observations, expected_outputs=len(observations), source_pins=sources,
            commanded_IAS=speeds, native_operating_point_count=29, driver_operating_point_count=22,
            physical_calls=0, production_imports=0, expected_operations=dict(cold_bridge_calls=0,modal_solves=0,retries=0),
            qualifications=QUALIFICATIONS, full_family_validated=False, suggested_cap_seconds=30))
    require(sum(j['expected_outputs'] for j in jobs) == 587, 'AE5 output denominator changed')
    return jobs


def reference_checks(job):
    return [dict(name=o['name'],predicted=None,expected=o['expected'],tolerance=o['tolerance'],
        exact_decimal_expected=o['exact_decimal_expected'],exact_decimal_tolerance=o['exact_decimal_tolerance'],
        comparison='<=',passed=False,source=o['source'],source_line=o['line'],units=o['units'])
        for o in job['observations']]


def verify_reference_sources(root, job):
    original = next(j for j in plan(root) if j['id'] == job['id'])
    require(all(job.get(key) == value for key,value in original.items()), 'prepared source contract changed')
    return True


def validate_result_contract(job, result):
    require(result.get('status') == 'unsupported' and result.get('numerical_pass') is False and
            result.get('numerical_passed') is not True and
            result.get('reference_match') is False, 'unmapped sources cannot claim numerical execution')
    require(result.get('reference_checks') == reference_checks(job), 'blocked source targets changed or fabricated')
    require(result.get('physical_calls') == result.get('production_imports') == 0 and
            result.get('operations') == job['expected_operations'], 'blocked route performed physics')
    require(result.get('source_pins_unchanged') is True and result.get('blocker_code') == job['blocker_code'] and
            result.get('full_family_validated') is False, 'source qualification lost')
    return True


def validate_blocked(root, job):
    verify_reference_sources(root,job)
    result = dict(status='unsupported',numerical_pass=False,reference_match=False,
        reference_checks=reference_checks(job),physical_calls=0,production_imports=0,
        operations=job['expected_operations'],source_pins_unchanged=True,blocker_code=job['blocker_code'],
        qualifications=QUALIFICATIONS,full_family_validated=False)
    validate_result_contract(job,result)
    return result


run = validate_blocked
