"""One original AE6 airflow anchor, with all archived modal rows inventoried.

This is a declared-setup diagnostic, not a shared adapter or full-family pass.
Run one mesh at a time. The caller owns memory/time limits; there is no retry.
"""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
CACHE = ROOT/'.reference/isae-validation'/REVISION
FAMILY = CACHE/'4 - Aeroelasticity/AE - Aeroelastic Cases/AE-6-D Moderate Aspect Ratio Wing - Effect of Nacelle Position on flutter Onset'
ST4 = CACHE/'3 - Structure/CASE - ST4 Concentrated weight/Simulation_files'
GROUPS = ('Weight0', 'Weight7a', 'Weight7c', 'Weight7d', 'Weight7e', 'Weight7f')


def pin(path):
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size, sha256=digest)


def write(path, value):
    with path.open('w') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def rows(text):
    result = []
    assert text.splitlines()[2].split() == ['#', 'Op.Point', 'Eigenvalue']
    for line, content in enumerate(text.splitlines(), 1):
        if not content.strip() or content.lstrip().startswith('#'):
            continue
        tokens = content.split()
        assert len(tokens) == 3 and tokens[0].isdigit() and int(tokens[0]) > 0
        values = [Decimal(t.replace('D', 'E')) for t in tokens[1:]]
        assert all(v.is_finite() for v in values)
        result.append(dict(line=line, tokens=tokens, index=int(tokens[0]),
                           eigenvalue=[float(v) for v in values],
                           decimal_values=[str(v) for v in values],
                           decimal_half_units=[str(Decimal(10)**v.as_tuple().exponent/2) for v in values]))
    assert result
    return result


def prepare(folder, nominal):
    assert nominal in (32,64)
    manifest_path = CACHE.parent/'manifest.json'
    manifest_pin = pin(manifest_path)
    assert manifest_pin['sha256'] == '813347a3bd9fcbd029a1ec86e0c3141f82422af26f33ebde7c2f732a16bf27f6'
    manifest = json.loads(manifest_path.read_text())
    assert manifest['revision'] == REVISION
    def original(path):
        record = pin(path)
        expected = manifest['files'][path.relative_to(CACHE).as_posix()]
        assert all(record[k] == expected[k] for k in ('bytes','sha256'))
        return record
    tables = []
    actual = sorted(p.parent.name for p in (FAMILY/'Simulation_file').glob('*/eig.txt'))
    assert actual == sorted(GROUPS)
    for group in GROUPS:
        parent = FAMILY/'Simulation_file'/group
        driver, table = parent/'Flutter_analysis.sh', parent/'eig.txt'
        commands = [line.strip().lower() for line in driver.read_text().splitlines() if line.strip()]
        match = re.search(r'/aswing\s+([^\s]+)\s+<<eof', commands[1])
        assert match
        candidates = [p for p in parent.glob('*.asw') if p.stem.lower() == match[1]]
        assert len(candidates) == 1
        model = candidates[0]
        assert commands[commands.index('ww')+1] == 'eig.txt'
        assert commands[commands.index('nn')+1] == '16'
        assert [float(v) for v in commands[commands.index('nn')+2].split()] == [0.,300.]
        speeds = [float(c.split()[1]) for c in commands if c.startswith('!v ')]
        reference = rows(table.read_text())
        equivalent = ST4 if group == 'Weight0' else ST4/group
        overlaps = []
        for p in (model,driver,table):
            old = equivalent/p.name
            if old.exists():
                other = original(old)
                overlaps.append(dict(AE6=original(p), ST4=other,
                                     identical=other['sha256'] == pin(p)['sha256']))
        tables.append(dict(group=group, sources=[original(p) for p in (model,driver,table)],
                           rows=reference, scalar_slots=2*len(reference),
                           commanded_speeds=speeds, maximum_native_index=max(r['index'] for r in reference),
                           requested_modes=16, shift=[0.,300.], ST4_overlaps=overlaps,
                           historical_settings_authenticated=False))
    anchor = next(t for t in tables if t['group']=='Weight7a')
    assert len(anchor['ST4_overlaps']) == 3 and all(p['identical'] for p in anchor['ST4_overlaps'])
    parent = FAMILY/'Simulation_file/Weight7a'
    commands = [line.strip().lower() for line in (parent/'Flutter_analysis.sh').read_text().splitlines() if line.strip()]
    oper = commands[commands.index('oper')+1:commands.index('!!b 0.0')]
    expected = []
    for index in range(41):
        if index:
            expected.append('+')
        expected.append(f'!v {120+index/2:g}')
    assert oper == expected
    assert commands[commands.index('!!b 0.0')+1:commands.index('xx')] == ['%','a','p','d']
    assert commands[commands.index('modes')+1:commands.index('nn')] == ['%','.','p','d']
    targets = [r for r in anchor['rows'] if r['index'] == 2]
    assert len(targets) == 6
    source = (parent/'7a_b17.asw').read_text()
    request = dict(action='modes', source=source,
        numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator='drela-moving-airflow-v1'),
        panels=dict(default=nominal,beams={'1':dict(count=nominal,spacing='cosine')}),
        condition=dict(speed=120.5,alpha=0.,beta=0.,density=1.0771417304,mach=0.,gravity_magnitude=9.81,
            position_earth=[0.,0.,0.],attitude=[0.,0.,0.],rates=[0.,0.,0.],acceleration=[0.,0.,0.],
            angular_acceleration=[0.,0.,0.],ground_effect=0,freeze_influences=False,aero_lag=True,
            circulation_modes={'1':0},wake_core_ratio=.25,stall=True,stall_factor=40.,stall_width=.05),
        modes=dict(frame='fixed',count=16,shift=[0.,300.],method='full_shift_invert',
            step=1e-5,rank_tolerance=1e-9,tolerance=1e-9,matrices=True))
    plan = dict(family='AE-6',scope='Declared Weight7a, nativepoint2, IAS120.5; one mesh',
                nominal=nominal,manifest=manifest_pin,tables=tables,targets=targets,
                modal_rows=sum(len(t['rows']) for t in tables),
                modal_scalar_slots=sum(t['scalar_slots'] for t in tables),
                helper=pin(Path(__file__)),kernel_pins=[pin(p) for p in sorted((ROOT/'openswing').glob('*.py'))],
                acceptance_helper=pin(ROOT/'scripts/isae_acceptance.py'),
                matching='Injective minimum complex-distance correspondence, as in the prior identical ST4 airflow pilot; not authenticated native eigenvector identity.',
                numerical_gates=dict(base=1e-7,pencil=1e-8,mass_pair=1e-6,clamp=1e-8),
                operations=dict(cold_bridge_calls=1,modal_solves=1,retries=0),
                qualifications=[
                    'Literal input model, dimensional loads and zero Reference area retained; no fitted material or aerodynamic settings.',
                    'Original script commands IAS120 at point1,120.5 at point2, followed by half-unit increments; hidden startup sidecars remain unknown.',
                    'Original density/PG/node spacing/current-influence/lag details remain unverified; explicit current choices are declared, not historical recovery.',
                    'Other native points, nacelle positions, aggregate CSV outputs and historical vacuum exports are not covered by this one physical solve.',
                    'All1674 archived complex rows remain in this inventory. ST4 byte copies are duplicate evidence, not independent new targets.',
                    'No shared adapter, full sweep, mesh convergence, native modal identity or flutter-onset validation claim.'])
    assert plan['modal_rows']==1674
    folder.mkdir(parents=True,exist_ok=False)
    write(folder/'request.json',request)
    write(folder/'plan.json',plan)
    return request,plan


def run(folder,nominal,*,assess_only=False):
    if assess_only:
        request,plan=[json.loads((folder/name).read_text()) for name in ('request.json','plan.json')]
        assert plan['nominal']==nominal
        assert not (folder/'report.json').exists(), 'Preserve completed assessments; use a new evidence directory.'
        executed_helper=folder.parent/'helper-initial.py'
        assert pin(executed_helper)['sha256']==plan['helper']['sha256']
    else:
        request,plan=prepare(folder,nominal)
        executed_helper=Path(__file__)
    sys.path.insert(0,str(ROOT))
    import numpy as np
    from scipy.optimize import linear_sum_assignment
    from scripts.isae_acceptance import apply_reference_acceptance
    started=time.monotonic()
    last=[0.]
    def progress(*args):
        now=time.monotonic()
        if now-last[0]>=5:
            print(json.dumps(dict(progress=args,seconds=now-started)),flush=True)
            last[0]=now
    if assess_only:
        result=json.loads((folder/'result.json').read_text())
        timing=folder/'solve-timing.json'
        seconds=json.loads(timing.read_text())['seconds'] if timing.exists() else None
    else:
        from openswing.bridge import dispatch
        write(folder/'started.json',dict(request=pin(folder/'request.json'),started=time.time()))
        result=dispatch(request,progress=progress)
        seconds=time.monotonic()-started
        write(folder/'solve-timing.json',dict(seconds=seconds))
        write(folder/'result.json',result)
    checks=[]
    def check(name,ok,**values):
        checks.append(dict(name=name,passed=bool(ok),**values))
    d,b=result['diagnostics'],result['base']
    check('consistent converged base',result['converged'] and b['converged'] and d['base_residual']<=1e-7,
          base_residual=d['base_residual'])
    check('literal model',(FAMILY/'Simulation_file/Weight7a/7a_b17.asw').read_text()==request['source'])
    check('original count shift and frame',d['requested_count']==16 and d['shift']==[0.,300.] and result['frame_mode']=='fixed')
    check('source equations',result['numerics']==request['numerics'] and result['structural_operator']=='drela-moving-airflow-v1')
    check('gravity and dimensional outputs',b['gravity_body']==[0.,0.,-9.81] and b['CL'] is None and b['CD'] is None)
    a,m=[np.asarray(result['matrices'][k]) for k in ('A','M')]
    assert a.shape==m.shape==(d['full_dimension'],d['full_dimension']) and np.isfinite(a).all() and np.isfinite(m).all()
    an,mn=np.linalg.norm(a),np.linalg.norm(m)
    layout=d['state_layout'];poles=[]
    for index,mode in enumerate(result['modes']):
        pole=complex(*mode['eigenvalue']);poles.append(pole)
        v,w=[np.asarray(mode[k]['real'])+1j*np.asarray(mode[k]['imag']) for k in ('right','left')]
        denominator=an+abs(pole)*mn
        er=np.linalg.norm(a@v-pole*(m@v))/(denominator*np.linalg.norm(v))
        el=np.linalg.norm(w.conj()@a-pole*(w.conj()@m))/(denominator*np.linalg.norm(w))
        check(f'mode{index}: original right and left equations',max(er,el)<=1e-8,right=float(er),left=float(el))
        mass=abs(w.conj()@m@v-1)
        root=np.r_[v[:6],v[layout['local_velocity']['start']:layout['local_velocity']['start']+3],
                   v[layout['local_rates']['start']:layout['local_rates']['start']+3]]
        clamp=np.max(abs(root))/np.max(abs(v))
        check(f'mode{index}: mass and clamp',mass<=1e-6 and clamp<=1e-8,mass_defect=float(mass),clamp_defect=float(clamp))
    assert len(poles)==16
    expected=np.array([complex(*r['eigenvalue']) for r in plan['targets']])
    target_indices,selected=linear_sum_assignment(abs(expected[:,None]-np.asarray(poles)[None,:]))
    assert list(target_indices)==list(range(6)) and len(set(selected))==6
    reference=[];pairs=[]
    for index,mode_index in zip(target_indices,selected):
        target=plan['targets'][index];actual=[poles[mode_index].real,poles[mode_index].imag]
        pairs.append(dict(target=target,mode_index=int(mode_index),actual=actual))
        for k,name in enumerate(('real','imaginary')):
            native=Decimal(target['decimal_values'][k]);absolute=Decimal(target['decimal_half_units'][k])
            passed=abs(Decimal(str(actual[k]))-native)<=absolute
            reference.append(dict(name=f"line{target['line']}:{name}",predicted=float(actual[k]),expected=float(native),
                tolerance=float(absolute),exact_decimal_expected=str(native),exact_decimal_tolerance=str(absolute),
                unit='1/s',comparison='<=',passed=passed))
    pins=plan['kernel_pins']+[plan['manifest'],plan['acceptance_helper']]
    pins.extend(record for table in plan['tables'] for record in table['sources'])
    check('all physical input and implementation pins unchanged',all(pin(ROOT/p['path'])==p for p in pins))
    check('executed helper retained',pin(executed_helper)['sha256']==plan['helper']['sha256'])
    strict=dict(status='computed',numerical_pass=all(c['passed'] for c in checks),reference_checks=reference,
                reference_match=all(c['passed'] for c in reference),numerical_checks=checks,
                output_accounting=dict(required=12,reported=12,finite=12,unavailable=0,
                                       numerically_valid=12 if all(c['passed'] for c in checks) else 0,
                                       passed=sum(c['passed'] for c in reference),missing=0))
    write(folder/'strict.json',strict)
    report=apply_reference_acceptance(strict)
    report.update(solve_seconds=seconds,plan=pin(folder/'plan.json'),result=pin(folder/'result.json'),
                  assessment_helper=pin(Path(__file__)),executed_helper=pin(executed_helper),
                  new_solves=0 if assess_only else 1,
                  pairs=pairs,selected_eigenvalues=[mode['eigenvalue'] for mode in result['modes']],
                  complete_family_reproduction=False,native_modal_identity_verified=False,
                  historical_settings_authenticated=False,registered_family_counts_unchanged=True,
                  actual_nodes=b['structural_nodes'],actual_elements=b['structural_elements'])
    write(folder/'report.json',report)
    print(json.dumps(dict(status=report['status'],numerical_pass=report['numerical_pass'],
          output_accounting=report['output_accounting'],solve_seconds=seconds)),flush=True)
    assert report['numerical_pass']


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder',type=Path)
    parser.add_argument('--panels',type=int,choices=(32,64),default=32)
    parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--assess-only',action='store_true')
    args=parser.parse_args()
    assert not (args.prepare_only and args.assess_only)
    if args.prepare_only:
        prepare(args.folder.resolve(),args.panels)
    else:
        run(args.folder.resolve(),args.panels,assess_only=args.assess_only)
