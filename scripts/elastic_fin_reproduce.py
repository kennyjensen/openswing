"""Reproduce one declared 1-Hz elastic-fin reference case from repository data.

Example (the output directory must not exist):
  python -I -B scripts/elastic_fin_reproduce.py --subdivisions 1 --output result

Use subdivisions 2 for the second declared mesh. Each invocation freezes its
source/fixture copies, owns one single-thread child with a 300-second cap, and
retains failures. It freshly computes the loaded continuum base and Green map;
no accepted response, serialized Green matrix, native model, or staging path is
needed. Importing this module performs no scientific work.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import traceback

SOURCES = (
    'elastic_fin_reproduce.py', 'elastic_fin_io.py', 'elastic_fin_aero.py',
    'elastic_fin_kinematics.py', 'elastic_fin_mechanics.py',
    'elastic_fin_response.py', 'elastic_fin_mesh.py', 'boom_fin_reference.py',
)
FIXTURE_SHA256 = '821330de408479d3fae677a8c189e2566da632eb6684f8415812c85ef4a15708'
THREAD_VARIABLES = ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS',
                    'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')


def pin(path):
    data = Path(path).read_bytes()
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def prepare_mechanics(fixture, subdivisions, directory, check, operations):
    """Original continuum equations, canonical nodes and physical tip inputs.

    Sampling only the canonical nodes omits old extra plotting/comparison rows;
    those rows never enter the boundary integration, load basis or equations.
    """
    import numpy as np
    from boom_fin_reference import Reference
    from elastic_fin_mechanics import ElasticCompliance
    from elastic_fin_mesh import explicit_mesh
    from elastic_fin_io import save_tree

    directory.mkdir()
    reference = Reference(fixture, rtol=1e-11)
    operations['loaded_base_calls'] += 1
    try:
        base_report = reference.solve_base()
    finally:
        operations['rod_reference'] = reference.ops.copy()
    write_json(directory/'base-report.json', base_report)
    save_tree(directory/'base', {
        name: {'nodes': branch['nodes'], 'end': branch['end']}
        for name, branch in reference.base.items()
    })
    compliance = ElasticCompliance(reference)
    mesh = explicit_mesh(fixture, subdivisions)
    nodes = [dict(branch='lower' if s < 0 else 'upper' if s > 0 else 'joint',
                  s=float(s), beam=3) for s in mesh['beams']['3']['nodes']]
    nodes += [dict(branch='boom', s=float(s), beam=4)
              for s in mesh['beams']['4']['nodes']]
    write_json(directory/'canonical-mesh.json', dict(mesh=mesh, nodes=nodes))
    base = compliance.sample_nodes(nodes)
    centers, elements = [], []
    for beam in (3, 4):
        grid = mesh['beams'][str(beam)]['nodes']
        for a, b in zip(grid[:-1], grid[1:]):
            s = (a+b)/2
            centers.append(dict(branch='boom' if beam == 4 else
                                'lower' if s < 0 else 'upper', s=s))
            elements.append(dict(beam=beam, t0=a, t1=b, t=s))
    center = compliance.sample_nodes(centers)
    clamp = -reference.base['boom']['nodes'][0, 12:18]
    joint = reference.base['boom']['end'][12:18]
    seed = dict(
        nodes=[dict(beam=node['beam'], t=node['s'],
                    position=base['r_gauge'][i].tolist(),
                    material_rotation=base['material_R_gauge'][i].tolist())
               for i, node in enumerate(nodes)],
        elements=[dict(**element, force=center['N_gauge'][i].tolist(),
                       moment=center['M_gauge'][i].tolist())
                  for i, element in enumerate(elements)],
        reactions=[dict(kind='ground', force=clamp[:3].tolist(), moment=clamp[3:].tolist()),
                   dict(kind='joint', force=joint[:3].tolist(), moment=joint[3:].tolist())],
        note='Independent mechanical seed; no native equilibrium or aero counterload manufacture.')
    write_json(directory/'mechanical-seed.json', seed)
    save_tree(directory/'sampled-base', dict(nodes=base, centers=center,
              reactions=dict(clamp_gauge=clamp, joint_on_boom_gauge=joint)))
    basis = compliance.point_load_basis(nodes, include_tip_inputs=True)
    # The first 6*nn columns are gauge nodal loads. Only the final two columns
    # are physical-axis tip Fy/Mz; rotate those once before gauge_loads=True.
    tip = basis['points'][-1]['wrench']
    tip[:3, -2:] = compliance.T@tip[:3, -2:]
    tip[3:, -2:] = compliance.T@tip[3:, -2:]
    save_tree(directory/'input-basis', basis)
    try:
        green = compliance.solve(1., basis['points'], nodes, basis['nrhs'],
                                 gauge_loads=True)
    finally:
        operations['continuum_compliance'] = compliance.ops.copy()
    save_tree(directory/'green', green)  # Raw result precedes acceptance.
    check('original continuum boundary gates', green['diagnostics']['available'],
          **green['diagnostics'])
    check('one loaded base and one continuum boundary solve',
          operations['loaded_base_calls'] == 1
          and compliance.ops['boundary_factorizations'] == 1
          and compliance.ops['boundary_solves'] == 1)
    return mesh, nodes, seed, green


def run_case(directory):
    """Execute the frozen case once; called only in the owned child."""
    for name in THREAD_VARIABLES:
        if os.environ.get(name) != '1':
            raise RuntimeError('Single-thread environment missing: '+name)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import numpy as np
    import scipy
    from elastic_fin_aero import AeroMap
    from elastic_fin_kinematics import NodalSampler
    from elastic_fin_response import Feedback, material_and_sampling, harmonic
    from elastic_fin_io import save_tree, STUDY_HISTORY

    plan = json.loads((directory/'plan.json').read_text())
    if (directory/'results').exists():
        raise RuntimeError('No retry or replacement in this case')
    for name, expected in plan['frozen_pins'].items():
        if pin(directory/name) != expected:
            raise RuntimeError('Frozen input changed: '+name)
    results = directory/'results'
    results.mkdir()
    start = time.monotonic()
    checks, completed, instances = [], [], []
    operations = dict(loaded_base_calls=0, aero_evaluations=0, field_integrations=0,
                      field_sets=0, steady_circulation_solves=0, coupled_two_rhs_solves=0,
                      production_calls=0, reused_aero_evaluations=0)
    error = None

    def check(name, passed, **details):
        checks.append(dict(name=name, passed=bool(passed), **details))
        write_json(directory/'checks.json', checks)
        if not passed:
            raise AssertionError(checks[-1])

    def compare(name, value, reference, absolute, relative):
        difference = abs(value-reference)
        allowance = absolute+relative*abs(reference)
        check(name, np.isfinite(value).all() and np.all(difference <= allowance),
              maximum_difference=float(np.max(difference)),
              maximum_gate_fraction=float(np.max(difference/allowance)))

    try:
        fixture = json.loads((directory/'inputs/fixture.json').read_text())
        mesh, nodes, seed, green = prepare_mechanics(
            fixture, plan['subdivisions'], results/'mechanics', check, operations)
        nn = len(nodes)
        fin = mesh['beams']['3']['nodes']
        nf = len(fin)
        check('declared dimensions', nn == plan['native_nodes']
              and nf-1 == plan['circulation_unknowns']
              and green['motion_gauge'].shape == (nn, 6, 6*nn+2))
        check('canonical receiving node order',
              all(n['beam'] == 3 and n['s'] == t for n, t in zip(nodes[:nf], fin)))
        material, tm, fractions = material_and_sampling(fixture, fin)
        sampler = NodalSampler([n['position'] for n in seed['nodes']],
            [n['material_rotation'] for n in seed['nodes']],
            np.c_[np.arange(nf-1), np.arange(1, nf)], fractions)
        T = np.asarray(fixture['gauge']['physical_to_gauge_rotation'])
        flow = dict(freestream=(T@np.array([6.7/.3048, 0., 0.])).tolist(),
                    density=.002378, sound_speed=1115., pg_mach=.1,
                    moment_origin=[0., 0., 0.])
        section = sampler.sample()
        gamma = accepted = first_response = None
        for variant, (degree, epsilon) in enumerate(plan['variants']):
            path = results/f'variant-{variant}'
            path.mkdir()
            (path/'raw').mkdir()
            (path/'fields').mkdir()

            def record_field(geometry, fields, diagnostics):
                key = hashlib.sha256(b''.join(np.asarray(geometry[name], dtype=np.complex128).tobytes()
                    for name in ('a', 'b', 'cp', 'hv', 'axis', 'pg', 'wind'))).hexdigest()
                target = path/'fields'/key
                if not target.with_suffix('.npz').exists():
                    save_tree(target, dict(geometry=geometry, fields=fields, diagnostics=diagnostics))

            aero = AeroMap(material, flow, degree, field_recorder=record_field)
            instances.append(aero)
            if gamma is None:
                base_system = aero.base_system(section)
                operations['steady_circulation_solves'] += 1
                gamma = np.linalg.solve(base_system['W'], base_system['rhs'])
                save_tree(results/'base-circulation', dict(**base_system, gamma=gamma))

            def record(call, inputs, sampled, value, output):
                count = sum(item.evaluations for item in instances)
                operations['aero_evaluations'] = count
                if count > plan['maximum_aero_evaluations']:
                    raise RuntimeError('Reference evaluation budget exhausted')
                save_tree(path/'raw'/f'call-{call:04d}', dict(inputs=inputs, outputs=output,
                    geometry={k: sampled[k] for k in ('rm', 'Rm', 'ds', 'Wa', 'Wb')},
                    field_diagnostics=value['diagnostics']))
                if call % 40 == 0:
                    print(json.dumps(dict(variant=variant, calls=call,
                                         elapsed_seconds=time.monotonic()-start)), flush=True)

            feedback = Feedback(sampler, aero, gamma, observer=record)
            base = feedback.base()
            check(f'base circulation {variant}', np.max(abs(base['residual'])) <= 2e-11,
                  maximum=float(np.max(abs(base['residual']))))
            if variant == 0:
                counter = base['nodal_wrench'].copy()
                save_tree(results/'fixed-counterloads', dict(nodes=nodes, nodal_wrench=counter,
                    gamma=gamma, gamma_tm=tm, semantics='Constant spatial load subtraction; no harmonic derivative.'))
            else:
                compare(f'base counterloads held {variant}', base['nodal_wrench'], counter, 2e-11, 2e-11)
            derivative = feedback.derivatives(epsilon)
            save_tree(path/'derivative', derivative)
            if accepted is None:
                accepted = derivative
            else:
                for variable, values in derivative['blocks'].items():
                    for name, value in values.items():
                        compare(f'derivative {variant} {variable} {name}', value,
                                accepted['blocks'][variable][name], 2e-11, 2e-11)
            operations['coupled_two_rhs_solves'] += 1
            response = harmonic(green, derivative, 1.)
            save_tree(path/'response', response)
            check(f'coupled residual and condition {variant}',
                  response['diagnostics']['available'], **response['diagnostics'])
            compare(f'mechanical recovery {variant}', response['motion_recovery_difference'],
                    np.zeros_like(response['motion_recovery_difference']), 2e-9, 0.)
            if first_response is None:
                first_response = response
            else:
                compare(f'coupled motion {variant}', response['motion_gauge'],
                        first_response['motion_gauge'], 2e-9, 2e-9)
                compare(f'coupled circulation {variant}', response['gamma'],
                        first_response['gamma'], 2e-9, 2e-9)
                for name, value in response['outputs'].items():
                    compare(f'coupled output {variant} {name}', value,
                            first_response['outputs'][name], 2e-9, 2e-9)
            completed.append(dict(variant=variant, quadrature=degree, epsilon=epsilon,
                evaluations=feedback.calls, field_sets=aero.field_sets,
                diagnostics=response['diagnostics']))
        check('exact fresh aerodynamic and solve scope',
              sum(a.evaluations for a in instances) == plan['maximum_aero_evaluations']
              and operations['steady_circulation_solves'] == 1
              and operations['coupled_two_rhs_solves'] == 3)
        check('no production imports', not any(k == 'openswing' or k.startswith('openswing.')
                                               for k in sys.modules))
        check('frozen source and fixture unchanged', all(pin(directory/name) == expected
              for name, expected in plan['frozen_pins'].items()))
    except BaseException as exc:
        error = dict(type=type(exc).__name__, message=str(exc), traceback=traceback.format_exc())
    finally:
        operations.update(aero_evaluations=sum(a.evaluations for a in instances),
                          field_integrations=sum(a.field_integrations for a in instances),
                          field_sets=sum(a.field_sets for a in instances))
        report = dict(status='PASS_PORTABLE_ELASTIC_FIN_REFERENCE' if error is None else 'FAILURE_RETAINED',
            error=error, operations=operations, completed=completed, checks=checks,
            passed=sum(c['passed'] for c in checks), total=len(checks),
            elapsed_seconds=time.monotonic()-start, plan_pin=pin(directory/'plan.json'),
            versions=dict(numpy=np.__version__, scipy=scipy.__version__),
            study_history=STUDY_HISTORY, limitations=plan['limitations'])
        write_json(directory/'report.json', report)
        print(json.dumps({k: report[k] for k in ('status', 'passed', 'total', 'operations',
                                               'elapsed_seconds')}), flush=True)
    return 0 if error is None else 1


def supervise(args):
    source = Path(__file__).resolve().parent
    fixture = Path(args.fixture).resolve()
    if pin(fixture)['sha256'] != FIXTURE_SHA256:
        raise ValueError('This entry point reproduces only the declared frozen boom-fin fixture')
    directory = Path(args.output).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    (directory/'source').mkdir()
    (directory/'inputs').mkdir()
    for name in SOURCES:
        shutil.copyfile(source/name, directory/'source'/name)
    shutil.copyfile(fixture, directory/'inputs/fixture.json')
    names = [f'source/{name}' for name in SOURCES]+['inputs/fixture.json']
    plan = dict(scope='Fresh independent 1-Hz fin-only elastic feedback reference',
        subdivisions=args.subdivisions, frequency_hz=1.,
        native_nodes=36 if args.subdivisions == 1 else 70,
        circulation_unknowns=19 if args.subdivisions == 1 else 38,
        variants=[[32, 1e-20], [32, 1e-24], [16, 1e-20]],
        maximum_aero_evaluations=1203 if args.subdivisions == 1 else 2343,
        maximum_seconds=300, threads=1, loaded_base_calls=1, continuum_boundary_solves=1,
        steady_circulation_solves=1, coupled_two_rhs_solves=3, reused_outputs=0,
        derivative_gate=dict(absolute=2e-11, relative=2e-11),
        response_gate=dict(absolute=2e-9, relative=2e-9),
        base_circulation_residual_gate=2e-11,
        coupled_component_backward_gate=1e-10, coupled_rcond_gate=1e-12,
        source_origins={name: dict(path=str(source/name), **pin(source/name)) for name in SOURCES},
        frozen_pins={name: pin(directory/name) for name in names},
        limitations=[
            'Declared fin-only aerodynamic bridge; boom aerodynamic radius is zero while literal boom real stiffness/mass/inertia remain.',
            'Original cut-gauge wind represents physical+x at6.7m/s; nativeft/s, density.002378, sound1115, fixedPG.1; F3 retains literal negative slope.',
            'Nodal geodesic interpolation and virtual-work transfer define discrete aero; the loaded continuum rod is inextensible and unshearable.',
            'Only1Hz and the two declared inputs F3/physical tipMz; no aircraft trim, native-production solve or full-aircraft/ASWING parity claim.',
            'This fresh reproduction retains original base/boundary/coupled/Q/epsilon gates. Historical mechanical-only comparisons are archived evidence, not recomputed from unavailable staging files.',
            'The original serializer failure and prefix reuse are historical study evidence; this run computes a fresh case once and retains any new failure.',
        ])
    write_json(directory/'plan.json', plan)
    env = os.environ.copy()
    for name in THREAD_VARIABLES:
        env[name] = '1'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    command = [sys.executable, '-I', '-B', str(directory/'source/elastic_fin_reproduce.py'),
               '--child', '--output', str(directory)]
    started = time.monotonic()
    timed_out = False
    with (directory/'stdout.log').open('x') as stdout, (directory/'stderr.log').open('x') as stderr:
        child = subprocess.Popen(command, cwd=directory, env=env, stdout=stdout,
                                 stderr=stderr, start_new_session=True)
        write_json(directory/'child.json', dict(pid=child.pid, command=command))
        try:
            code = child.wait(timeout=plan['maximum_seconds'])
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(child.pid, signal.SIGTERM)
            try:
                code = child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                code = child.wait()
        except BaseException:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)
            child.wait()
            raise
    receipt = dict(pid=child.pid, exit_code=code, timed_out=timed_out, terminal=True,
                   reaped=True, elapsed_seconds=time.monotonic()-started,
                   plan_pin=pin(directory/'plan.json'), stdout_pin=pin(directory/'stdout.log'),
                   stderr_pin=pin(directory/'stderr.log'),
                   report_pin=pin(directory/'report.json') if (directory/'report.json').exists() else None)
    write_json(directory/'execution.json', receipt)
    print(json.dumps(receipt), flush=True)
    return 0 if code == 0 and not timed_out else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--subdivisions', type=int, choices=(1, 2), default=1)
    parser.add_argument('--fixture', default=str(Path(__file__).resolve().parents[1]
        /'docs/validation/daedalus-boom-fin-fixture.json'))
    parser.add_argument('--output', required=True)
    parser.add_argument('--child', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    return run_case(Path(args.output).resolve()) if args.child else supervise(args)


if __name__ == '__main__':
    raise SystemExit(main())
