"""Six serial independent finite-chord winglet controls; no production imports.

Retains the previously reviewed ring kernels/load closure from the pinned
swept finite-chord archive. One chord row is checked against the saved
arithmetic-sample lifting-line control before interpreting added chord rows.
"""
from datetime import datetime, timezone
import argparse
import gc
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT/'docs/validation/swept-finite-chord-evidence.zip'
ARCHIVE_HASH = '21c546760ebec24f3bdfb9369acfabe3d9a384ad3db94c442646d8271e4e7f58'
KERNELS = dict(vlm='1b1b90aa89829fcafadbb4c13f3972f580420d99071ca1c5ef8c0c7b542bb550',
               loads='449561e6d0cac588451ae5aae8703eceb956a9e76149bf81a4af7991df003821')
BASELINE = ROOT/'artifacts/isae/unswept-winglet-junction-20261107'
REQUESTS = [(1, 50), (1, 100), (2, 50), (4, 50), (2, 100), (4, 100)]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def portable(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {k:portable(v) for k,v in value.items()}
    if isinstance(value, (tuple, list)):
        return [portable(v) for v in value]
    return value


def write(path, data):
    path.write_text(json.dumps(portable(data), indent=2, allow_nan=False)+'\n')


def geometry(nc, n, vlm, loads):
    """Connected zero-thickness sheets, incidence in BC normals only.

    Normal-only incidence keeps a conforming sharp junction, exactly matching
    the ASWING benchmark's wind-shifted lifting geometry at one chord row.
    It is not an exact finite-angle intersection of twisted physical plates.
    """
    angle = 1/(2*np.pi)
    names = ('left', 'main', 'right')
    stations = [np.linspace(-.7, -.5, n//5+1), np.linspace(-.5, .5, n+1),
                np.linspace(.5, .7, n//5+1)]
    # Same chordwise coordinate array for every patch, including the
    # historical quarter-panel extension past the physical trailing edge.
    x = (np.arange(nc+1)/nc-.25)*.1
    qx = ((np.arange(nc+1)+.25)/nc-.25)*.1
    patches, quarters, mids, ts = {}, [], [], []
    for name, t in zip(names, stations):
        if name == 'left':
            y, z, normal = np.full_like(t, -.5), -.5-t, [np.sin(angle), np.cos(angle), 0.]
        elif name == 'main':
            y, z, normal = t.copy(), np.zeros_like(t), [np.sin(angle), 0., np.cos(angle)]
        else:
            y, z, normal = np.full_like(t, .5), t-.5, [np.sin(angle), -np.cos(angle), 0.]
        # Exact shared corner coordinates are declared, not inferred by a
        # proximity tolerance. End heights use the same floating .2 value.
        if name == 'left': z[0], z[-1] = .2, 0.
        if name == 'right': z[0], z[-1] = 0., .2
        grid = np.empty((nc+1, len(t), 3))
        grid[:,:,0], grid[:,:,1], grid[:,:,2] = x[:,None], y[None], z[None]
        qgrid = grid.copy(); qgrid[:,:,0] = qx[:,None]
        panels = np.stack([grid[:-1,:-1], grid[1:,:-1], grid[1:,1:], grid[:-1,1:]], axis=2)
        cp = .5*(grid[:-1,:-1]+grid[:-1,1:])
        cp[:,:,0] = ((np.arange(nc)+.75)/nc-.25)[:,None]*.1
        normals = np.broadcast_to(normal, cp.shape).copy()
        areas = np.linalg.norm(np.cross(panels[:,:,1]-panels[:,:,0],
                                        panels[:,:,3]-panels[:,:,0]), axis=-1)
        patches[name] = dict(panels=panels, collocation=cp, normal=normals, area=areas)
        quarters.append(np.stack([qgrid[:-1,:-1],qgrid[:-1,1:],qgrid[1:,1:],qgrid[1:,:-1]],
                                 axis=2).reshape(-1,4,3))
        mid = np.column_stack([np.zeros(len(t)-1), (y[:-1]+y[1:])/2, (z[:-1]+z[1:])/2])
        mids.append(mid); ts.extend((t[:-1]+t[1:])/2)
    topo = vlm.topology(dict(patches=patches), [1.,0.,0.])
    canonical = np.concatenate(quarters)
    defect = float(np.max(abs(canonical-topo['corners'])))
    assert defect < 128*np.finfo(float).eps
    topo['corners'] = canonical
    graph = loads.canonical_graph(topo, [('left',n//5,'main',0),('main',n,'right',0)])
    assert graph['maximum_canonical_coordinate_change_m'] == 0.
    return graph, np.concatenate(mids), np.asarray(ts), defect


def edge_masks(graph):
    a, b = graph['starts'], graph['ends']
    spanwise = a[:,0] == b[:,0]
    chordwise = np.all(a[:,1:] == b[:,1:], axis=1)
    assert np.all(spanwise ^ chordwise)
    front = spanwise & (a[:,0] == np.min(a[:,0]))
    return dict(all_spanwise=spanwise, chordwise=chordwise, front=front)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a fresh output directory; saved observations are preserved.')
    assert sha(ARCHIVE) == ARCHIVE_HASH
    baseline_plan = json.loads((BASELINE/'plan.json').read_text())
    baseline_verify = json.loads((BASELINE/'verification.json').read_text())
    assert all(sha(BASELINE/name) == pin for name,pin in baseline_verify['artifacts'].items())
    assert all(sha(ROOT/name) == pin for name,pin in baseline_plan['pins'].items())
    baseline = [r for r in json.loads((BASELINE/'results.json').read_text())
                if r['request']['sampling'] == 'arithmetic-control']
    assert [r['request']['main_intervals'] for r in baseline] == [50,100,200]
    args.output.mkdir(parents=True)
    shutil.copyfile(__file__, args.output/'driver-used.py')
    ref = args.output/'reference'; ref.mkdir()
    with zipfile.ZipFile(ARCHIVE) as archive:
        for name,pin in KERNELS.items():
            data = archive.read('work/reference/'+name+'.py')
            assert hashlib.sha256(data).hexdigest() == pin
            (ref/(name+'.py')).write_bytes(data)
    sys.path.insert(0, str(ref.resolve()))
    import vlm
    import loads
    assert Path(vlm.__file__).resolve() == (ref/'vlm.py').resolve()
    assert Path(loads.__file__).resolve() == (ref/'loads.py').resolve()
    assert not any(n == 'openswing' or n.startswith('openswing.') for n in sys.modules)
    plan = dict(utc=utc(), requests=[dict(chord_rows=c,main_span_intervals=n) for c,n in REQUESTS],
        driver_sha256=sha(Path(__file__)), archive_sha256=ARCHIVE_HASH, reference_kernel_pins=KERNELS,
        baseline_dir=str(BASELINE.relative_to(ROOT)), baseline_result_sha256=sha(BASELINE/'results.json'),
        unchanged_pins=baseline_plan['pins'],
        geometry=dict(main_span=1.,winglet_height=.2,chord=.1,reference_area=.1,
            incidence_radians=1/(2*np.pi),incidence='Rotated BC normals; geometric chord edges along x.',
            span_nodes='Uniform, each winglet has N/5 intervals; arithmetic samples.',
            chord_nodes='Uniform; quarter-panel fronts and 3/4-panel controls.',
            trailing_edge='Ring/wake rear extends 0.25 final-panel chord beyond physical TE; retained reference convention.',
            connections='Conforming left-main-right, shared chordwise boundary vertices; zero tolerance-based merging.'),
        physics=dict(speed=1.,density=1.225,PG_Mach=0.,core=0.,stall=False,wake=[1.,0.,0.],
            force='Canonical finite-edge midpoint vector Kutta-Joukowski; own edge omitted, all others retained.',
            quarter_chord_probe='x=0 at arithmetic span samples; one-chord own front edge excluded.',
            max_panels=560),
        limitations=['Independent finite-chord control; neither native ASWING output nor a replacement algorithm.',
                     'Incidence is imposed through normals while the three sheets remain geometrically joined.',
                     'Sharp-corner and sheet-edge singularities may remain; no convergence claim from execution.',
                     'Full canonical-edge loads differ from ASWING single-bound-line loads; both ledgers are retained.'])
    write(args.output/'plan.json', plan)
    rows = []
    for nc,n in REQUESTS:
        label = f'c{nc}-n{n}'
        start = time.monotonic()
        graph, probes, station, defect = geometry(nc,n,vlm,loads)
        topo = graph['topology']
        assert len(topo['corners']) <= plan['physics']['max_panels']
        solve = vlm.solve_boundary(topo, [1.,0.,0.])
        gamma = solve['gamma']
        force = loads.midpoint_loads(graph,gamma,[1.,0.,0.],density=1.225)
        masks = edge_masks(graph)
        ledger = {key:dict(force=force['edge_forces'][mask].sum(axis=0),
                          moment=force['edge_moments'][mask].sum(axis=0)) for key,mask in masks.items()}
        ledger['full'] = dict(force=force['force'],moment=force['moment'])
        front_sources = np.flatnonzero(topo['chord_index'] == 0)
        edge_lookup = {tuple(edge):i for i,edge in enumerate(graph['edge_vertices'])}
        front_edges = np.array([edge_lookup[tuple(sorted(v[:2]))]
                               for v in graph['source_vertices'][front_sources]])
        equivalent = None
        if nc == 1:
            # Canonical midpoint equality is required by the reference own-
            # edge exclusion. These are the same physical arithmetic samples.
            exact_mid = (graph['starts'][front_edges]+graph['ends'][front_edges])/2
            np.testing.assert_allclose(probes,exact_mid,atol=2e-16,rtol=0.)
            probes = exact_mid
            field = loads.velocity(probes,graph,gamma,own_edges=front_edges)+[1.,0.,0.]
            saved = next(r['result'] for r in baseline if r['request']['main_intervals'] == n)
            checks = dict(circulation=(gamma,np.asarray([s['circulation'] for s in saved['strips']])),
                quarter_chord_position=(probes,np.asarray([s['velocity_position'] for s in saved['strips']])),
                quarter_chord_velocity=(field,np.asarray([s['relative_velocity'] for s in saved['strips']])),
                front_force=(ledger['front']['force'],np.asarray(saved['force'])),
                front_moment=(ledger['front']['moment'],np.asarray(saved['moment'])))
            equivalent = {}
            for key,(actual,expected) in checks.items():
                np.testing.assert_allclose(actual,expected,atol=2e-12,rtol=2e-11)
                equivalent[key] = float(np.max(abs(actual-expected)))
        else:
            # No quarter-chord probe coincides with a finite vortex for nc=2,4.
            assert np.min(abs(graph['starts'][masks['all_spanwise'],0])) > .001
            field = loads.velocity(probes,graph,gamma)+[1.,0.,0.]
        # A fixed off-sheet receiver set avoids moving closer to an edge with
        # every refinement. These fields supplement, not replace, local probes.
        offsheet = np.array([[0.,.49,.01],[0.,.45,.05],[.025,.49,.01]])
        external = loads.velocity(offsheet,graph,gamma)+[1.,0.,0.]
        cumulative = []
        for name in ('left','main','right'):
            ns = topo['patch_shapes'][name][1]
            # Ring Gamma is cumulative; downstream minus upstream gives the
            # strength of each spanwise edge. Section total is trailing Gamma.
            cumulative.extend(gamma[topo['patch']==name].reshape(nc,ns)[-1])
        physical = dict(gamma=gamma, matrix=solve['matrix'], rhs=solve['rhs'],residual=solve['residual'],
            collocation=topo['collocation'],normals=topo['normal'],corners=topo['corners'],
            starts=graph['starts'],ends=graph['ends'],edge_coefficients=graph['edge_coefficients'],
            ray_starts=graph['ray_starts'],ray_coefficients=graph['ray_coefficients'],
            edge_midpoints=force['edge_midpoints'],edge_strengths=force['edge_strengths'],
            edge_velocity=force['edge_velocity'],edge_forces=force['edge_forces'],edge_moments=force['edge_moments'],
            quarter_chord_probes=probes,quarter_chord_velocity=field,material_stations=station,
            section_circulation=np.array(cumulative),offsheet_probes=offsheet,offsheet_velocity=external,
            **{'mask_'+k:v for k,v in masks.items()})
        artifact = args.output/(label+'.npz'); np.savez_compressed(artifact,**physical)
        row = dict(case=label,utc=utc(),chord_rows=nc,main_span_intervals=n,total_panels=len(gamma),
            status='computed',seconds=time.monotonic()-start,
            maximum_boundary_residual=solve['max_normal_residual_m_per_s'],
            relative_backward_error=solve['relative_backward_error'],canonical_coordinate_defect=defect,
            loads=ledger,CL=float(force['force'][2]/(.5*1.225*.1)),CD=float(force['force'][0]/(.5*1.225*.1)),
            quarter_chord_maximum_speed=float(np.max(np.linalg.norm(field,axis=1))),
            edge_maximum_speed=float(np.max(np.linalg.norm(force['edge_velocity'],axis=1))),
            offsheet_velocity=external,one_chord_equivalence=equivalent,
            artifact=dict(path=artifact.name,sha256=sha(artifact)))
        rows.append(row); write(args.output/'results.json',rows)
        print(label,'CL',row['CL'],'CD',row['CD'],'quarter speed',row['quarter_chord_maximum_speed'],
              'one-row errors',equivalent,flush=True)
        del graph,solve,force,physical
        gc.collect()
    assert all(sha(ROOT/name) == pin for name,pin in plan['unchanged_pins'].items())
    assert sha(Path(__file__)) == plan['driver_sha256']
    assert all(sha(ref/(name+'.py')) == pin for name,pin in KERNELS.items())
    assert not any(n == 'openswing' or n.startswith('openswing.') for n in sys.modules)
    write(args.output/'verification.json',dict(utc=utc(),production_imports=[],
        source_status_scope_pins_unchanged=True,independent_kernel_pins_verified=True,computed_cases=len(rows),
        artifacts={str(p.relative_to(args.output)):sha(p) for p in args.output.rglob('*') if p.is_file()}))


if __name__ == '__main__':
    main()
