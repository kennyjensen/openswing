"""FFWT3 original time-history inventory, with unresolved attachments explicit.

Retain every exported scalar and the driver-implied slots for the missing
history. No attachment is clipped, model is repaired, or native pass inferred.
This registration-only route imports no production or numerical code.
"""
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
FAMILY = ('4 - Aeroelasticity/FFWT - Flared Folding Wingtips Cases/'
          'FFWT-3-U - Gust Alleviation of a Wing with and wo FFWT - Qualitative Only')
SCHEMA = 'isae-ffwt3-original-histories-v1'
CHANNELS = dict(alpha_ref='deg', Lift='N', CL='1', Fn_sensor1='N', Mcprime_sensor1='N m', Phi_sensor2='deg')
QUALIFICATIONS = [
    'All six literal models have joint stations outside their chord-defined beam ranges. Native out-of-range attachment semantics are not documented by the reviewed sources.',
    'No endpoint clipping, station rewrite, guessed historical model, or fitted physical parameter is used.',
    'Free_Sweep_10_A-10 exports 701 rows through 2.45s, incompatible with its retained .01s/200-step driver.',
    'Free_Sweep_10_A30 has an output but no driver. Free_Sweep_30_A-10 has a driver but no output; its 201x6 scheduled slots remain unavailable.',
    'Driver-requested sensor3 is absent in every literal model and retained export. Only the six actual exported physical channels are scored.',
    'The type5 gust commands are x0=-10, zero spanwise slope, H=8, W=.75. Historical defaults, node spacing and complete constraints remain unverified.',
    'Peak-to-peak MATLAB reductions and plots are retained in the source catalog; they are not additional independent history values.',
]


def require(ok, message):
    if not ok:raise ValueError('FFWT3: '+message)


def pin(path):
    path = Path(path).resolve(); raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def sources(root):
    cache = Path(root).resolve()/'.reference/isae-validation'/REVISION
    manifest = json.loads((cache.parent/'manifest.json').read_text())
    require(manifest['revision'] == REVISION, 'reference revision changed')
    base = cache/FAMILY
    models = sorted(p.name for p in base.glob('*.asw'))
    drivers = {p.stem for p in base.glob('*.sh')}
    outputs = {p.stem for p in base.glob('*.txt')}
    require(models == sorted(f'{kind}_Sweep_{angle}.asw' for kind in ('Free','Sprung','Stiff') for angle in (10,30)), 'model inventory changed')
    require(len(drivers) == len(outputs) == 26 and len(drivers | outputs) == 27, 'history inventory changed')
    require(outputs-drivers == {'Free_Sweep_10_A30'} and drivers-outputs == {'Free_Sweep_30_A-10'}, 'unpaired source inventory changed')
    return cache, base, manifest, sorted(drivers | outputs)


def model_contract(name):
    angle = int(name.rsplit('_', 1)[1])
    end, tip = (.6591, .856) if angle == 10 else (.5725, .711)
    domains = {1: [-end,end], 2: [end,tip], 3: [-tip,-end]}
    joints = [(1,1,.6591),(1,2,.001),(2,1,-.6591),(2,3,-.001)]
    outside = [dict(joint=j, beam=b, station=t, domain=domains[b])
               for j,b,t in joints if not domains[b][0] <= t <= domains[b][1]]
    return dict(beam_domains={str(k):v for k,v in domains.items()}, out_of_range_joints=outside,
                sensors=[1,2], unrepresented_requested_sensor=3)


def driver_contract(path, model, output):
    lines = [line.strip().lower() for line in path.read_text().splitlines() if line.strip() and not line.lstrip().startswith('#')]
    require(lines[0].endswith(f'aswing {model.lower()} <<eof'), 'driver model changed')
    i = lines.index('gmod'); require(lines[i+1:i+3] == ['5','-10 0 8 0.75'], 'gust command changed')
    require('!v 20' in lines and lines[lines.index('w')+1] == output.lower(), 'speed/output command changed')
    alpha = next(float(line.split()[1]) for line in lines if line.startswith('!a '))
    time_rows = [line.split() for line in lines if re.fullmatch(r'[\d.]+ +\d+', line)]
    require(['0.01','200'] in time_rows, 'time command changed')
    require(lines.count('x') == 2 and lines[lines.index('x')+1] == '%', 'initial steady command changed')
    return dict(model=model, speed=20., alpha=alpha, dt=.01, steps=200,
                gust=dict(type=5, parameters=[-10.,0.,8.,.75]), initial_steady_command=True,
                normalized_commands=lines)


def cell(row, channel, token, time, source, line):
    value = Decimal(token.replace('D','E')) if token is not None else None
    require(value is None or value.is_finite(), 'nonfinite native value')
    half = Decimal(10)**value.as_tuple().exponent/2 if value is not None else None
    return dict(name=f'row{row:04d}:{channel}', channel=channel, time=time, source=str(source), line=line,
        token=token, expected=float(value) if value is not None else None,
        tolerance=float(half) if half is not None else None,
        exact_decimal_expected=str(value) if value is not None else None,
        exact_decimal_tolerance=str(half) if half is not None else None, units=CHANNELS[channel])


def build_job(root, stem, context=None):
    cache, base, manifest, stems = sources(root) if context is None else context
    require(stem in stems, 'unknown output/driver stem')
    match = re.fullmatch(r'((?:Free|Sprung|Stiff)_Sweep_(?:10|30))_A(-?\d+)',stem)
    require(match is not None, 'unrecognized case basename')
    model_name = match[1]; model = base/(model_name+'.asw')
    driver, output = base/(stem+'.sh'), base/(stem+'.txt')
    paths = [model,base/'Post_Traitement.m']+[p for p in (driver,output) if p.exists()]
    pins = [pin(p) for p in paths]
    for item in pins:
        original = manifest['files'][Path(item['path']).relative_to(cache).as_posix()]
        require(all(item[k] == original[k] for k in ('bytes','sha256')), 'pinned source changed')
    driver_data = driver_contract(driver,model_name,output.name) if driver.exists() else None
    observations = []; times = []; blockers = ['UNRESOLVED_OUT_OF_RANGE_JOINT_STATIONS']
    if output.exists():
        lines = output.read_text().splitlines()
        require('Operating point sequence' in lines[1], 'native output header changed')
        require(all(label in lines[2] for label in ('alpha_ref','Lift','CL','Fn','Mc`','Phi')), 'native columns changed')
        for number, raw in enumerate(lines,1):
            if not raw.strip() or raw.startswith('#'):continue
            tokens = raw.split(); require(len(tokens) == 8, 'native column count changed')
            require(int(tokens[0]) == len(times)+1, 'noncontiguous native row index')
            t = Decimal(tokens[1]); half = Decimal(10)**t.as_tuple().exponent/2
            require(t.is_finite() and (not times or float(t) > times[-1]), 'invalid time coordinate')
            times.append(float(t))
            observations.extend(cell(int(tokens[0]),name,token,float(t),output,number)
                                for name,token in zip(CHANNELS,tokens[2:]))
            if driver_data and abs(t-Decimal(len(times)-1)*Decimal('.01')) > half:
                if 'DRIVER_OUTPUT_TIME_GRID_MISMATCH' not in blockers:blockers.append('DRIVER_OUTPUT_TIME_GRID_MISMATCH')
        if driver_data and len(times) != driver_data['steps']+1 and 'DRIVER_OUTPUT_TIME_GRID_MISMATCH' not in blockers:
            blockers.append('DRIVER_OUTPUT_TIME_GRID_MISMATCH')
        if driver_data is None:blockers.append('MISSING_ORIGINAL_DRIVER')
    else:
        require(driver_data is not None, 'neither driver nor output')
        blockers.append('MISSING_ORIGINAL_OUTPUT')
        times = [float(Decimal(i)*Decimal('.01')) for i in range(driver_data['steps']+1)]
        observations = [cell(i+1,name,None,t,output,None) for i,t in enumerate(times) for name in CHANNELS]
    return dict(id='FFWT-3:'+stem+':original',case_id='FFWT-3',family='FFWT-3',adapter='ffwt3',schema=SCHEMA,
        output_basename=stem,target_kind='native_time_history',execution_route='unsupported',
        blocker_code=blockers[0],blocker_codes=blockers,
        unsupported_reason='Original joint station behavior is unresolved; do not alter the input model to force a comparison.',
        model_contract=model_contract(model_name),driver_contract=driver_data,
        observations=observations,expected_outputs=len(observations),
        retained_reference_values=sum(o['expected'] is not None for o in observations),
        native_rows=len(times) if output.exists() else 0,scheduled_rows=len(times),time_range=[times[0],times[-1]],
        source_pins=pins+[pin(cache.parent/'manifest.json'),pin(__file__)],
        missing_sources=[str(p) for p in (driver,output) if not p.exists()],
        expected_operations=dict(cold_bridge_calls=0,time_steps=0,retries=0),physical_calls=0,production_imports=0,
        qualifications=QUALIFICATIONS,full_family_validated=False,suggested_cap_seconds=30)


def plan(root):
    context = sources(root)
    jobs = [build_job(root,stem,context) for stem in context[3]]
    require(sum(j['expected_outputs'] for j in jobs) == 36462, 'required-output denominator changed')
    require(sum(j['retained_reference_values'] for j in jobs) == 35256, 'retained-reference denominator changed')
    return jobs


def reference_checks(job):
    return [dict(name=o['name'],predicted=None,expected=o['expected'],tolerance=o['tolerance'],
        exact_decimal_expected=o['exact_decimal_expected'],exact_decimal_tolerance=o['exact_decimal_tolerance'],
        comparison='<=',passed=False,source=o['source'],source_line=o['line'],time=o['time'],units=o['units'])
        for o in job['observations']]


def verify_reference_sources(root, job):
    original = build_job(root,job['output_basename'])
    require(all(job.get(k) == v for k,v in original.items()), 'prepared source contract changed')
    return True


def validate_result_contract(job, result):
    require(result.get('status') == 'unsupported' and result.get('numerical_pass') is False and
        result.get('numerical_passed') is not True and result.get('reference_match') is False, 'unresolved setup cannot claim numerical execution')
    require(result.get('reference_checks') == reference_checks(job), 'blocked targets changed or fabricated')
    require(result.get('physical_calls') == result.get('production_imports') == 0 and
        result.get('operations') == job['expected_operations'], 'blocked route performed physics')
    require(result.get('source_pins_unchanged') is True and result.get('blocker_codes') == job['blocker_codes'] and
        result.get('full_family_validated') is False and result.get('qualifications') == QUALIFICATIONS,
        'source qualification lost')
    return True


def validate_blocked(root, job):
    verify_reference_sources(root,job)
    result = dict(status='unsupported',numerical_pass=False,reference_match=False,
        reference_checks=reference_checks(job),physical_calls=0,production_imports=0,
        operations=job['expected_operations'],source_pins_unchanged=True,blocker_codes=job['blocker_codes'],
        qualifications=QUALIFICATIONS,full_family_validated=False)
    validate_result_contract(job,result)
    return result


run = validate_blocked
