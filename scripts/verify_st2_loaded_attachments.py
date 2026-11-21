"""Compare loaded ST-2 pylon and explicit rigid-extension modal equations.

This is an equivalence diagnostic, not additional native ASWING targets.
Every run is one bounded process; source models and earlier studies stay intact.
"""
import argparse
from pathlib import Path
import resource
import time

import verify_sa14_defaults as common

ROOT = common.ROOT
PRIOR = ROOT/'artifacts/isae/st2-attachment-interpretations-20261109/refined'
PYLON = ROOT/'artifacts/isae/st2-span-profile-20261109'


def prepare(out):
    paths = [Path(__file__), ROOT/'scripts/verify_sa14_defaults.py',
             ROOT/'docs/validation/aswing-authoritative-references.md',
             ROOT/'docs/validation/aswing-authoritative-sources.json',
             ROOT/'reference/aswing_doc.txt', *sorted((ROOT/'openswing').glob('*.py'))]
    sources = {}
    for name, folder in [('pylon', PYLON/'job-0'), ('extension', PRIOR/'job-2')]:
        report = common.read(folder/'report.json')
        for filename, digest in report['artifacts'].items():
            assert common.sha(folder/filename) == digest
        paths += [folder/'report.json', folder/'request.json']
        sources[name] = common.read(folder/'request.json')['source']
    catalog = common.read(ROOT/'docs/validation/aswing-authoritative-sources.json')
    for entry in catalog['files']:
        if entry['id'] in ('isae-part-3', 'drela-steady', 'drela-unsteady'):
            for key, digest in [('local_pdf', 'sha256'), ('local_text', 'text_sha256')]:
                assert common.sha(ROOT/entry[key]) == entry[digest]
                paths.append(ROOT/entry[key])
    out.mkdir()
    for name, source in sources.items():
        path = out/(name+'.asw'); path.write_text(source); paths.append(path)
    common.write(out/'plan.json', dict(observed_utc=common.utc(),
        pins={p.relative_to(ROOT).as_posix(): common.sha(p) for p in paths},
        jobs=[dict(variant=v, main_intervals=n, extension_intervals=e)
              for n,e in [(45,4),(90,8)] for v in ('pylon','extension')],
        gates=dict(base=1e-8, balance=1e-7, pencil=1e-8, neutral=1e-8,
                   equivalence_frequency=1e-7, equivalence_shape=1-1e-7,
                   equivalence_position=1e-8, mesh_frequency=.01, mesh_shape=.99),
        limits=dict(blas_threads=1, address_space_mib=512, cpu_seconds=15, wall_seconds=25),
        modal_survey=dict(count=12, shift=[-.1,0.], method='full_shift_invert'),
        protocol='Fresh self-weight plus original 3kg point mass equilibria, fixed-frame vacuum. '
            'Two explicit previously reviewed in-domain models: endpoint pylon or rigid extension/joint. '
            'Same modified-cosine main-beam grids; uniform rigid-extension grids. '
            'Compare all six positive returned roots in frequency order and main-wing physical shapes. '
            'Check original left/right matrix equations. No native frequency target, scope change, '
            'production change, automatic retry, or inferred out-of-domain parsing policy.'))
    print('Prepared four serial loaded attachment modal states.')


def run(out, index):
    plan = common.read(out/'plan.json'); common.authenticate(plan['pins'])
    job = plan['jobs'][index]; folder = out/f'job-{index}'; folder.mkdir()
    import numpy as np
    from scipy.sparse import save_npz
    from openswing.bridge import dispatch
    from openswing import linear_dynamics as dynamics
    panels = dict(default=job['main_intervals'], beams={
        '1': dict(count=job['main_intervals'], spacing='modified-cosine')})
    if job['variant'] == 'extension':
        panels['beams']['2'] = dict(count=job['extension_intervals'], spacing='uniform')
    request = dict(action='modes', mode='modes', source=(out/(job['variant']+'.asw')).read_text(),
        panels=panels, condition=None, gravity=[0.,0.,-9.81], loads=[],
        numerics=dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-fixed-vacuum-v1'),
        modes=dict(frame='fixed', vacuum=True, **plan['modal_survey'], matrices=False,
                   tolerance=1e-9, rank_tolerance=1e-9, continuation_steps=4))
    common.write(folder/'request.json', request)
    held = []; original = dynamics.linearize
    def capture(system, *args, **kwargs):
        a,m = original(system, *args, **kwargs); held.append((system,a,m))
        save_npz(folder/'A.npz', a); save_npz(folder/'M.npz', m)
        return a,m
    dynamics.linearize = capture; started = time.monotonic()
    try: result = dispatch(request)
    finally: dynamics.linearize = original
    seconds = time.monotonic()-started; common.write(folder/'result.json', result)
    assert len(held) == 1
    system,a,m = held[0]; base = result['base']; nodes = base['nodes']; n = len(nodes)
    checks = dict(base_residual=base['residual'],
        fresh_residual=float(np.max(abs(system.residual(np.zeros(system.size),np.zeros(system.size))))),
        force_balance=float(np.max(abs(np.asarray(base['force_balance'])))),
        moment_balance=float(np.max(abs(np.asarray(base['moment_balance'])))),
        mass=abs(base['mass_properties']['mass']-(3+.3745*.55)))
    assert result['converged'] and base['converged'] and result['vacuum']
    assert base['gravity_body'] == [0.,0.,-9.81]
    assert checks['base_residual'] < plan['gates']['base'] and checks['fresh_residual'] < plan['gates']['base']
    assert max(checks.values()) < plan['gates']['balance'], checks
    modes = result['modes']; values = np.asarray([complex(*v['eigenvalue']) for v in modes])
    assert len(values) == plan['modal_survey']['count']
    audits = []
    for mode,lam in zip(modes,values,strict=True):
        assert sum(abs(values-lam)<1e-8*max(1.,abs(lam))) == 1
        audit = dict(index=mode['index'], neutral=abs(lam.real)/max(1.,abs(lam.imag)))
        assert audit['neutral'] < plan['gates']['neutral']
        assert np.min(abs(values-lam.conjugate())) < 1e-8*max(1.,abs(lam))
        for side in ('left','right'):
            v = np.asarray(mode[side]['real'])+1j*np.asarray(mode[side]['imag'])
            av,mv = (a@v,m@v) if side=='right' else (v.conjugate()@a,v.conjugate()@m)
            audit[side] = float(np.linalg.norm(av-lam*mv)/(np.linalg.norm(av)+abs(lam)*np.linalg.norm(mv)))
            assert audit[side] < plan['gates']['pencil']
        audits.append(audit)
    positive = sorted([v for v in modes if v['eigenvalue'][1]>1e-6], key=lambda v:v['eigenvalue'][1])
    assert len(positive) == 6
    main = [i for i,node in enumerate(nodes) if node['beam']==1]
    assert len(main) == job['main_intervals']+1
    # Source state geometry occupies the first six components at every node.
    shapes = []
    for mode in positive:
        v = np.asarray(mode['right']['real'])+1j*np.asarray(mode['right']['imag'])
        shape = v[:6*n].reshape(n,6)[main].copy(); shape[:,:3] *= system.L/.55
        shapes.append(shape)
    np.savez_compressed(folder/'shapes.npz', shapes=np.asarray(shapes),
        stations=np.asarray([nodes[i]['jig_position'][1] for i in main]),
        positions=np.asarray([nodes[i]['position'] for i in main]),
        rotations=np.asarray([nodes[i]['rotation'] for i in main]))
    common.authenticate(plan['pins'])
    report = dict(observed_utc=common.utc(), job=job, checks=checks, pencil_audits=audits,
        frequencies_Hz=[v['eigenvalue'][1]/(2*np.pi) for v in positive],
        solver_seconds=seconds, peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        plan_sha256=common.sha(out/'plan.json'), artifacts={p.name:common.sha(p) for p in folder.iterdir()})
    common.write(folder/'report.json', report)
    print({k:report[k] for k in ('job','frequencies_Hz','checks','solver_seconds','peak_rss_kib')})


def summarize(out):
    plan = common.read(out/'plan.json'); common.authenticate(plan['pins'])
    import numpy as np
    records = []; shapes = []
    for index,job in enumerate(plan['jobs']):
        folder = out/f'job-{index}'; report = common.read(folder/'report.json')
        assert report['job']==job and report['plan_sha256']==common.sha(out/'plan.json')
        for name,digest in report['artifacts'].items(): assert common.sha(folder/name)==digest
        records.append(report)
        with np.load(folder/'shapes.npz') as z: shapes.append({k:z[k] for k in z.files})
    def compare(i,j,mesh=False):
        left,right = shapes[i],shapes[j]; grid = np.linspace(0.,.55,257)
        def sample(item):
            a = np.asarray([np.column_stack([np.interp(grid,item['stations'],v[:,k]) for k in range(6)]) for v in item['shapes']])
            a[:,[0,-1],:] *= np.sqrt(.5)
            return a.reshape(6,-1)
        a,b = sample(left),sample(right)
        mac = abs(a.conjugate()@b.T)**2/np.outer(np.sum(abs(a)**2,axis=1),np.sum(abs(b)**2,axis=1))
        mutual = np.array_equal(np.argmax(mac,axis=1),np.arange(6)) and np.array_equal(np.argmax(mac,axis=0),np.arange(6))
        freq = abs(np.asarray(records[i]['frequencies_Hz'])/records[j]['frequencies_Hz']-1)
        result = dict(left=i,right=j,mesh_refinement=mesh,frequency_relative=freq.tolist(),
                      shape_MAC=np.diag(mac).tolist(),mutual_shape_assignment=bool(mutual))
        result['passed'] = bool(mutual and np.min(np.diag(mac)) >= plan['gates']['mesh_shape' if mesh else 'equivalence_shape']
            and np.max(freq) <= plan['gates']['mesh_frequency' if mesh else 'equivalence_frequency'])
        if not mesh:
            assert np.array_equal(left['stations'],right['stations'])
            result['position_difference'] = float(np.max(abs(left['positions']-right['positions'])))
            result['rotation_difference'] = float(np.max(abs(left['rotations']-right['rotations'])))
            result['passed'] &= max(result['position_difference'],result['rotation_difference']) <= plan['gates']['equivalence_position']
        return result
    comparisons = [compare(0,1),compare(2,3),compare(0,2,True),compare(1,3,True)]
    summary = dict(observed_utc=common.utc(),plan_sha256=common.sha(out/'plan.json'),
        states=records, comparisons=comparisons, passed=all(v['passed'] for v in comparisons),
        native_reference_targets=0, primary_counts_changed=False, out_of_domain_policy_verified=False)
    common.write(out/'summary.json',summary)
    print(dict(passed=summary['passed'],comparisons=comparisons))


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('action',choices=['prepare','run','summarize'])
    parser.add_argument('--output',type=Path,required=True); parser.add_argument('--index',type=int)
    args=parser.parse_args(); args.output=args.output.resolve(); common.bounded()
    if args.action=='prepare': prepare(args.output)
    elif args.action=='run': run(args.output,args.index)
    else: summarize(args.output)
