"""One literal AE5 driver condition; source mismatch means no native pass claim.

Use an external serial time/address cap. No source repair or parameter fitting.
"""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
CACHE = ROOT/'.reference/isae-validation'/REVISION
FAMILY = CACHE/'4 - Aeroelasticity/AE - Aeroelastic Cases/AE-5-D Low Aspect Ratio Wing - Flutter Boundaries'


def pin(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def write(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False)+'\n')


def prepare(folder, nominal):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    model = FAMILY/'Flutter_Boundaries/[03_90].asw'
    driver = FAMILY/'Flutter_Boundaries/[0_90]_3s_flutter.sh'
    table = FAMILY/'Flutter_Boundaries/eig.txt'
    manifest = json.loads((CACHE.parent/'manifest.json').read_text())
    sources = [pin(p) for p in (model, driver, table, FAMILY/'Flutter_Boundaries/Analysis.m')]
    for p in sources:
        original = manifest['files'][Path(p['path']).relative_to(CACHE).as_posix()]
        assert all(p[k] == original[k] for k in ('bytes', 'sha256'))
    commands = [line.strip().lower() for line in driver.read_text().splitlines() if line.strip()]
    assert commands[commands.index('oper')+1:commands.index('!v 9')] == ['g','1','0 0 1','%','a','d','!b 15']
    speeds = [float(line.split()[1]) for line in commands if line.startswith('!v ')]
    assert speeds == list(range(9, 31)) and commands[commands.index('nn')+1:commands.index('hh')] == ['16','0 200']
    native = []
    for i, line in enumerate(table.read_text().splitlines(), 1):
        if not line.strip() or line.startswith('#'): continue
        tokens = line.split()
        assert len(tokens) == 3
        native.append(dict(line=i, tokens=tokens, index=int(tokens[0]), eigenvalue=list(map(float, tokens[1:]))))
    assert len(native) == 266 and sorted({r['index'] for r in native}) == list(range(1, 30))
    request = dict(action='modes', source=model.read_text(),
        numerics=dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-moving-airflow-v1'),
        panels=dict(default=nominal, beams={'1':dict(count=nominal, spacing='cosine')}),
        condition=dict(speed=9., alpha=0., beta=15., density=1.23, mach=0., gravity_magnitude=9.81,
            ground_effect=1, ground_normal=[0.,0.,1.], position_earth=[0.,0.,0.], attitude=[0.,0.,0.],
            rates=[0.,0.,0.], acceleration=[0.,0.,0.], angular_acceleration=[0.,0.,0.],
            freeze_influences=False, aero_lag=True, circulation_modes={'1':0},
            wake_core_ratio=.25, stall=True, stall_factor=40., stall_width=.05),
        modes=dict(frame='fixed',count=16,shift=[0.,200.],method='full_shift_invert',
            step=1e-5,rank_tolerance=1e-9,tolerance=1e-9,matrices=True))
    plan = dict(family='AE-5', scope='Literal first driver condition only; native index/speed identity unverified',
        nominal=nominal, source_pins=sources, native_rows=native, native_scalar_slots=532,
        commanded_speeds=speeds, native_operating_points=29, driver_operating_points=22,
        native_comparisons=0, full_family_validated=False,
        source_discrepancies=dict(GJ_literal=8000., GJ_report=1.2, EInn_literal=2.5, EInn_report=18499.,
            EIcn_literal=0., EIcn_report=.0023),
        kernel_pins=[pin(p) for p in sorted((ROOT/'openswing').glob('*.py'))], helper=pin(__file__),
        report=pin(CACHE.parent/'reports/Experimental_validation_of_ASWING_Part_4_Aeroelasticity_V4.txt'),
        qualifications=['Nominal cosine mesh, PG0, fixed frame, current influences and default stall settings are declared.',
                        'No fitted or repaired source. No native modal point is assigned a speed.',
                        'The report and literal model disagree; this is a source diagnostic, not a flutter comparison.'])
    write(folder/'plan.json', plan)
    write(folder/'request.json', request)
    return request, plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--nominal', type=int, choices=(32,64), default=32)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    assert not (args.output_dir/'result.json').exists(), 'Retain existing evidence; use another output directory'
    request, plan = prepare(args.output_dir, args.nominal)
    if args.prepare_only:
        print('Prepared literal AE5 source diagnostic; no native comparisons.', flush=True)
        return
    sys.path.insert(0, str(ROOT))
    from openswing.bridge import dispatch
    import numpy as np
    print('Starting one literal AE5 modal solve.', flush=True)
    start = time.monotonic()
    result = dispatch(request)
    seconds = time.monotonic()-start
    write(args.output_dir/'result.json', result)
    assert result['converged'] and result['base']['converged']
    d = result['diagnostics']
    assert d['base_residual'] <= 1e-7
    a,m = [np.asarray(result['matrices'][k]) for k in ('A','M')]
    an,mn = np.linalg.norm(a), np.linalg.norm(m)
    proofs = []
    for index, mode in enumerate(result['modes']):
        pole = complex(*mode['eigenvalue'])
        v,w = [np.asarray(mode[k]['real'])+1j*np.asarray(mode[k]['imag']) for k in ('right','left')]
        scale = an+abs(pole)*mn
        right = np.linalg.norm(a@v-pole*(m@v))/(scale*np.linalg.norm(v))
        left = np.linalg.norm(w.conj()@a-pole*(w.conj()@m))/(scale*np.linalg.norm(w))
        mass = abs(w.conj()@m@v-1)
        layout = d['state_layout']
        root = np.r_[v[:6],v[layout['local_velocity']['start']:layout['local_velocity']['start']+3],
                     v[layout['local_rates']['start']:layout['local_rates']['start']+3]]
        clamp = np.max(abs(root))/np.max(abs(v))
        proof = dict(index=index, eigenvalue=mode['eigenvalue'], right=float(right), left=float(left),
                     mass=float(mass), clamp=float(clamp))
        proof['passed'] = bool(max(right,left)<=1e-8 and mass<=1e-6 and clamp<=1e-8)
        proofs.append(proof)
    assert len(proofs) == 16 and all(p['passed'] for p in proofs)
    assert result['base']['ground_plane']['flag'] == 1
    assert all(pin(p['path']) == p for p in plan['source_pins']+plan['kernel_pins']+[plan['helper'],plan['report']])
    report = dict(status='NUMERICAL_DIAGNOSTIC_COMPUTED', solve_seconds=seconds,
        base_residual=d['base_residual'], full_dimension=d['full_dimension'], mode_proofs=proofs,
        native_comparisons=0, full_family_validated=False, request=pin(args.output_dir/'request.json'),
        result=pin(args.output_dir/'result.json'), plan=pin(args.output_dir/'plan.json'))
    write(args.output_dir/'report.json',report)
    print(json.dumps(dict(status=report['status'],seconds=seconds,dimension=d['full_dimension'],
                         eigenvalues=[p['eigenvalue'] for p in proofs])),flush=True)


if __name__ == '__main__': main()
