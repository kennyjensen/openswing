"""ST-5 rigid-joint study with explicitly reconstructed applied loads.

The literal negative-Dmg models remain rejected. This study converts their
zero-offset static load surrogate to conservative nodal forces, then refines
both that load representation and the production nonlinear beam mesh. It does
not relax inertia checks, fit loads, or claim the modified link joint is tested.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from openswing.asw import parse_asw, Distribution
from openswing.geometry import model_meshes
from openswing.network import StaticNetwork, network_result, solve_static
from openswing.structured_static import equilibrate

REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
CACHE = ROOT/'.reference/isae-validation'/REVISION
FOLDER = CACHE/'3 - Structure/CASE - ST5 Joined Wing'
CASES = [('JW_1_30lb_90_10', 'Figure_A_3.csv'),
         ('JW_1_20lb_90_10', 'Figure_A_5.csv'),
         ('JW_1_20lb_80_20', 'Figure_A_7.csv'),
         ('JW_1_FW_30lb', 'Figure_A_1.csv')]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def body_moments(rows):
    # Independent Euler expansion of (R_twist R_sweep R_dihedral)^T M_local.
    # All selected input twist multipliers are zero; dump tw-tw0 is total twist.
    theta, psi = np.deg2rad(rows[:, 5]), np.deg2rad(rows[:, 6])
    return np.cos(theta)*np.cos(psi)*rows[:, 7] - np.sin(psi)*rows[:, 8] + np.sin(theta)*np.cos(psi)*rows[:, 9]


def archived(path):
    lines = path.read_text().splitlines()
    beams = {}
    for i, line in enumerate(lines):
        match = re.search(r'Surface\s+Beam\s+(\d+):', line)
        if not match:
            continue
        exponents = np.fromstring(lines[i+1], sep=' ')
        assert len(exponents) == 27
        rows = []
        for candidate in lines[i+4:]:
            if (not candidate.strip() or set(candidate.strip()) == {'.'}
                    or re.search(r'Surface\s+Beam\s+\d+:', candidate)):
                break
            values = np.fromstring(candidate, sep=' ')
            assert len(values) == 28
            rows.append(values)
        raw = np.asarray(rows)
        rows = raw*10.**np.r_[0, exponents]
        assert len(rows) > 10 and np.all(np.diff(rows[:, 0]) >= -1e-6)
        # Cross-check the independently decoded text against the archived MAT.
        from scipy.io import loadmat
        mat = loadmat(path.with_suffix('.mat'))['beam_data'][0, int(match[1])-1]
        np.testing.assert_allclose(rows, mat, rtol=2e-14, atol=2e-14)
        beams[int(match[1])] = dict(rows=rows.tolist(), Mx_lbft=body_moments(rows).tolist(),
            raw_rows=raw.tolist(), raw_Mx=body_moments(raw).tolist(), column_exponents=np.r_[0,exponents].tolist(),
            convention='Reproduces the upstream MATLAB postprocessor and MAT file. Raw columns retained separately; geometry-angle scaling inconsistencies remain.')
    assert beams
    return beams


def reconstruct(model, panels):
    """Integrate -Dmg ds into linear nodal weights on each original interval.

    Eight-point Gauss quadrature is split at every property knot. The forces
    follow the material nodes and remain vertical. No net-load rescaling is
    applied. Shape interpolation and constitutive discretization both converge
    under mesh refinement; finite-mesh identity with signed inertia is not assumed.
    """
    # Reparse the lossless/current serialization. WASM SciPy spline objects
    # contain module state that Python deepcopy cannot pickle.
    derived = parse_asw(model.dumps())
    settings = dict(default=panels, beams={})
    loads, checks = [], []
    gx, gw = np.polynomial.legendre.leggauss(8)
    for beam, target, mesh in zip(model.beams, derived.beams, model_meshes(model, panels)):
        for key in ['Dmgcc', 'Dmgnn', 'DCcg', 'DNcg']:
            assert key not in beam.distributions or not np.any(beam.distributions[key].values), key
        assert not np.any(beam.value('twist', mesh.ts))
        t = np.r_[mesh.t0, mesh.t1[-1]]
        settings['beams'][str(beam.index)] = dict(nodes=t.tolist())
        distribution = beam.distributions['Dmg']
        assert np.min(distribution.values) < 0 and np.max(distribution.values) <= 0
        knots = np.unique(np.concatenate([np.r_[d.t, -d.t] if d.t[0] == 0 else d.t
                                          for d in beam.distributions.values()]))
        forces = np.zeros(len(t))
        integral = 0.
        exact_jig_moment = np.zeros(3)
        for j, (a, b) in enumerate(zip(t[:-1], t[1:])):
            cuts = np.r_[a, knots[(knots > a) & (knots < b)], b]
            for lo, hi in zip(cuts[:-1], cuts[1:]):
                q = (lo+hi)/2 + (hi-lo)/2*gx
                ds = np.linalg.norm(beam.position(q, derivative=1), axis=1)
                weights = -beam.value('Dmg', q)*ds*gw*(hi-lo)/2
                fraction = (q-a)/(b-a)
                forces[j] += weights@(1-fraction)
                forces[j+1] += weights@fraction
                integral += float(weights.sum())
                exact_jig_moment += np.sum(np.cross(beam.position(q), np.c_[np.zeros((len(q),2)),weights]), axis=0)
        assert abs(forces.sum()-integral) < 1e-10
        nodal_forces = np.c_[np.zeros((len(t),2)),forces]
        moment = np.cross(beam.position(t), nodal_forces).sum(axis=0)
        checks.append(dict(beam=beam.index, upward_force_lb=float(integral), force_sum_error=float(abs(forces.sum()-integral)),
                           nodal_jig_moment_lbft=moment.tolist(), continuous_jig_moment_lbft=exact_jig_moment.tolist(),
                           jig_moment_error_lbft=float(np.max(abs(moment-exact_jig_moment)))))
        loads += [dict(beam=beam.index, t=float(ti), force=fi.tolist()) for ti, fi in zip(t, nodal_forces)]
        target.distributions['Dmg'] = Distribution('Dmg', distribution.t.copy(), np.zeros_like(distribution.values), distribution.line)
    return derived, settings, loads, checks


def run_model(model, panels, method='structured'):
    derived, settings, loads, checks = reconstruct(model, panels)
    if method == 'dense':
        result = solve_static(derived, panels=settings, loads=loads)
    else:
        net = StaticNetwork(derived, settings, None, None, loads)
        state, steps = equilibrate(net)
        result = network_result(net, state)
        result['continuation_steps'] = steps
    assert result['converged'] and result['residual'] < 1e-8
    assert np.max(np.abs(result['force_balance'])) < 1e-7
    assert np.max(np.abs(result['moment_balance'])) < 1e-7
    return dict(load_checks=checks, result={k:result[k] for k in ['residual','evaluations','structural_nodes',
        'structural_elements','max_displacement','max_rotation_deg','force_balance','moment_balance',
        'applied_force','applied_moment','support_force','support_moment','continuation_steps','nodes','elements','reactions']})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--panels', nargs='+', type=int, default=[16,32,64,128,256])
    parser.add_argument('--cases', nargs='+', default=[x[0] for x in CASES])
    parser.add_argument('--method', choices=['structured','dense'], default='structured')
    parser.add_argument('--output', default='docs/validation/isae-st5.json')
    args = parser.parse_args()
    manifest = json.loads((CACHE.parent/'manifest.json').read_text())
    paths = list(FOLDER.rglob('*.asw'))
    for name, csv in CASES:
        paths += [FOLDER/'Rigid_Joint'/(name+suffix) for suffix in ['.txt','.mat','.sh']]
        paths.append(FOLDER/'Exp_data'/csv)
    paths += [FOLDER/'Rigid_Joint/Rigid_joint.m',FOLDER/'Link_Joint/Link_joint.m',
              CACHE/'5 - Technical Reports/Experimental_validation_of_ASWING_Part_3__Structure_V5.pdf']
    sources = {}
    for path in sorted(set(paths)):
        key = path.relative_to(CACHE).as_posix()
        assert sha(path) == manifest['files'][key]['sha256']
        sources[key] = manifest['files'][key]
    modules = {p.name:sha(p) for p in sorted((ROOT/'openswing').glob('*.py'))}
    identity = dict(modules=modules, script_sha256=sha(Path(__file__)))
    savedir = ROOT/'.reference/isae-st5-runs'/hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    savedir.mkdir(parents=True, exist_ok=True)
    literal = []
    for path in sorted(FOLDER.rglob('*.asw')):
        row = dict(path=path.relative_to(CACHE).as_posix())
        try:
            model = parse_asw(path.read_text())
            row['import'] = 'parsed'
            StaticNetwork(model, 8, None, None, [])
            row['network_setup'] = 'constructed_not_solved'
        except ValueError as exc:
            row.update(status='rejected', error=str(exc))
        literal.append(row)
    cases = []
    for name, csv in CASES:
        if name not in args.cases:
            continue
        path = FOLDER/'Rigid_Joint'/(name+'.asw')
        model = parse_asw(path.read_text())
        assert all(int(row[-1]) == 0 for row in model.records.get('joint', []))
        archive = archived(path.with_suffix('.txt'))
        experiment = np.genfromtxt(FOLDER/'Exp_data'/csv, delimiter=',', skip_header=2)
        case = dict(name=name, input_path=path.relative_to(CACHE).as_posix(), archived=archive,
                    experiment_file=csv, experiment=[[None if not np.isfinite(x) else float(x) for x in row] for row in experiment], runs=[])
        for panels in args.panels:
            spec = dict(case=name, panels=panels, method=args.method)
            save = savedir/(hashlib.sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest()+'.json')
            if save.exists():
                row = json.loads(save.read_text())
                assert row['specification'] == spec
            else:
                start = time.monotonic()
                try:
                    row = dict(specification=spec, status='computed', **run_model(model, panels, args.method))
                except ValueError as exc:
                    row = dict(specification=spec, status='rejected', error=str(exc))
                row['seconds'] = time.monotonic()-start
                save.write_text(json.dumps(row,indent=2,allow_nan=False)+'\n')
            case['runs'].append(row)
            print(name, panels, row['status'], round(row['seconds'],3), row.get('error',''), flush=True)
        cases.append(case)
    report = dict(status='RECONSTRUCTED_STATIC_LOAD_STUDY_NOT_LITERAL_VALIDATION', full_suite_validated=False,
        provenance={**identity, 'revision':REVISION,'sources':sources},
        settings=dict(meshes=args.panels,method=args.method, gravity='Default input g, zero motion, no aerodynamic condition',
                      reconstruction='Negative Dmg replaced by integrated upward body-axis nodal forces; original mg, geometry, stiffness, grounds and rigid joints unchanged'),
        literal_audit=literal,cases=cases,limitations=[
            'Literal negative-Dmg input is unsupported. These derived models are explicit static load reconstructions, not successful literal file solves.',
            'No load magnitude or distribution is fitted or renormalized. The archive labels do not by themselves establish the total load or its normalization.',
            'Part III p42 states link-joint results required modified ASWING code: x/y translations and z rotation are free. Standard Joint type 2 is not that custom constraint; link-joint results remain unvalidated.',
            'Production SO(3) midpoint mechanics and natural cubic property interpolation differ from unverified ASWING discretization/spline conventions.',
            'Archived text exponent rows reproduce the upstream MATLAB reduction and companion MAT arrays. Raw columns are retained too: scaled root dihedral disagrees with the clamped input geometry. The raw rear angle matches; the raw forward angle differs by about 0.11 degree, consistent with an unresolved geometry/spline difference. The reference is labeled archived MATLAB, not verified ASWING physical output. Missing CSV values remain null.',
            'The MATLAB plots normalize each wing/experimental abscissa separately; direct dimensional span comparisons must not silently inherit that normalization.',
            'The 20-lb cantilever experimental curve in the report is extrapolated from 30 lb, not an independent measurement; only the original 30-lb CSV is used here.'])
    (ROOT/args.output).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')


if __name__ == '__main__':
    main()
