"""Replay SA-11 lower-winglet geometry trials and low-lift wake interactions.

One bounded saved-state audit per invocation. No aerodynamic solves, altered
vortex terms, core radius, geometry or acceptance gates.
"""
import argparse
from pathlib import Path
import math
import sys
import time

import audit_sa11_winglet_interactions as common

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / 'artifacts/isae/sa11-paper-suite-coverage-20261108'
PLANFORM = ROOT / 'artifacts/isae/sa11-lower-planform-20261108-v2'


def prepare(out):
    common.bounded()
    assert not out.exists()
    primary = common.read(PAPER / 'analysis.json')
    proof = common.read(PAPER / 'verification.json')
    assert proof['verified'] and proof['analysis_sha256'] == common.sha(PAPER / 'analysis.json')
    pins = dict(primary['pins'])
    old = common.read(PLANFORM / 'plan.json')
    old_result = common.read(PLANFORM / 'analysis.json')
    assert old_result['plan_sha256'] == common.sha(PLANFORM / 'plan.json')
    pins.update(old['pins'])
    for name, digest in old['generated_pins'].items():
        assert common.sha(PLANFORM / name) == digest
        pins[str((PLANFORM / name).relative_to(ROOT))] = digest
    common.authenticate(pins)
    cases = []
    for label in ('0_70', '0_80'):
        for configuration in ('upper_winglet', 'upper_lower_winglets'):
            check = next(c for c in primary['checks'] if c['configuration'] == configuration
                and c['label'] == label and c['kind'] == 'drag_at_equal_lift' and c['x'] == .3)
            curve = next(c for c in primary['curves'] if c['configuration'] == configuration and c['label'] == label)
            for alpha in check['bracket_alpha']:
                point = next(p for p in curve['points'] if p['alpha'] == alpha)
                path = ROOT / point['source']
                row = common.read(path)
                geometry = path.parent / 'geometry.npz'
                if not geometry.exists():
                    assert configuration == 'upper_winglet'
                    geometry = common.UPPER_GEOMETRY
                model = (ROOT / 'artifacts/isae/sa11-minimum-spacing-20261108/model.asw' if configuration == 'upper_winglet'
                         else ROOT / row['case']['model_path'])
                mesh_path = model.parent / 'mesh-import.json'
                cases.append(dict(id=f'{configuration}-{label}-a{round(alpha*4):02d}', group='equal_lift',
                    configuration=configuration, label=label, alpha=alpha, condition=row['case']['condition'],
                    report=str(path.relative_to(ROOT)), accepted=str((path.parent / 'accepted.json').relative_to(ROOT)),
                    geometry=str(geometry.relative_to(ROOT)), model=str(model.relative_to(ROOT)),
                    mesh=common.read(mesh_path)['panels'], state=None))
    for row in old_result['cases']:
        case = row['case']
        directory = PLANFORM / case['id']
        assert common.sha(directory / 'report.json') == row['report_sha256']
        cases.append(dict(id=f"planform-{case['id']}", group='geometry_trial', configuration=case['variant'],
            label=case['label'], alpha=case['alpha'], condition=case['condition'],
            report=str((directory / 'report.json').relative_to(ROOT)),
            accepted=str((directory / 'accepted.json').relative_to(ROOT)) if row['status']=='COMPUTED_DIAGNOSTIC' else None,
            state=str((directory / 'state.npz').relative_to(ROOT)), geometry=str((directory / 'geometry.npz').relative_to(ROOT)),
            model=str((PLANFORM / old['variants'][case['variant']]['model']).relative_to(ROOT)),
            mesh=dict(default=32, beams=common.read(PLANFORM / 'mesh.json'))))
    assert len(cases) == 14
    for case in cases:
        row = common.read(ROOT / case['report'])
        for name, digest in row['artifacts'].items():
            path = (ROOT / case['report']).parent / name
            assert common.sha(path) == digest
            pins[str(path.relative_to(ROOT))] = digest
        for key in ('report', 'accepted', 'state', 'geometry', 'model'):
            if case[key] is not None:
                pins[case[key]] = common.sha(ROOT / case[key])
    for path in (Path(__file__), Path(common.__file__), common.OPERATOR, common.AVL,
                 PAPER / 'analysis.json', PAPER / 'verification.json', PLANFORM / 'plan.json', PLANFORM / 'analysis.json',
                 ROOT / 'docs/validation/aswing-authoritative-references.md', ROOT / 'docs/validation/aswing-authoritative-sources.json'):
        pins[str(path.relative_to(ROOT))] = common.sha(path)
    common.authenticate(pins)
    out.mkdir(parents=True)
    (out / 'driver-used.py').write_text(Path(__file__).read_text())
    common.write(out / 'plan.json', dict(observed_utc=common.utc(), cases=cases, pins=pins,
        previous_goal_turn='Progress: six physical upper/lower samples resolved four missing paper checks; no new passes. Low-lift direct stall-pressure term is under0.6%of drag discrepancy.',
        protocol='Eight saved states bracket CL=.3 for upper and upper/lower at240/272m/s. Six earlier alpha0 geometry trials cover literal lower planform,cant36 and independently dimensioned published planform. Audit all14 including the retained rejected trial. Reconstruct zero-core PG field,tangency,forces and section Mach. Account for every ordered receiver/source pair and lower-root own trailing rays. No term omitted, no fitted inputs, no new physical calls.',
        source_basis='Jan PartI p35,Fig22 p39,Fig40 p68; NASA-TN-D-8473 p4/Fig2b; Drela steady Eqs64--70,149--161,200--204. Existing planform trials preserve root,twist and airfoil parameters,so are diagnostic alternatives rather than authenticated generating inputs.',
        limits='One foreground saved-state job,one BLAS thread,512MiB address-space,15CPU/25wall seconds. No browser/build/background work.',
        physical_solves=0, primary_passes_added=0))
    common.signal.alarm(0)
    print(dict(prepared=True, saved_states=len(cases), source_pins=len(pins)))


def run(out, index):
    common.bounded()
    begin = time.monotonic()
    plan = common.read(out / 'plan.json')
    common.authenticate(plan['pins'])
    case = plan['cases'][index]
    directory = out / case['id']
    assert not directory.exists()
    row = common.read(ROOT / case['report'])
    accepted = case['accepted'] is not None
    import numpy as np
    sys.path.insert(0, str(ROOT))
    from openswing.asw import parse_asw
    from openswing.geometry import model_meshes
    from openswing.frozen_influence import lifting_geometry
    model = parse_asw((ROOT / case['model']).read_text(), beam_interpolation='natural-v1')
    meshes = model_meshes(model, case['mesh'])
    g = lifting_geometry(meshes, np.array([1., 0., 0.]))
    with np.load(ROOT / case['geometry']) as saved:
        for key in g:
            np.testing.assert_allclose(g[key], saved[key], rtol=0, atol=2e-12)
    span = np.concatenate([m.frames[..., 1] for m in meshes])
    beam = np.concatenate([np.full(len(m.tm), m.beam.index) for m in meshes])
    t = np.concatenate([m.tm for m in meshes])
    sample = lambda name: np.concatenate([m.beam.value(name, m.tm) for m in meshes])
    normal = np.concatenate([np.sin(np.deg2rad(m.beam.value('alpha', m.tm)))[:, None]*m.frames[..., 0]
        + np.cos(np.deg2rad(m.beam.value('alpha', m.tm)))[:, None]*m.frames[..., 2] for m in meshes])
    if case['state']:
        with np.load(ROOT / case['state']) as saved:
            gamma, velocity, saved_force, cl, moments = [saved[key] for key in ('gamma','velocity','force','cl','section_moment')]
            np.testing.assert_array_equal(beam, saved['beam'])
            np.testing.assert_allclose(span, saved['span'], rtol=0, atol=2e-12)
            assert bool(saved['section_moment_available']) == accepted
    else:
        raw = common.read(ROOT / case['accepted'])
        assert raw['converged'] and raw['residual'] < 1e-8
        gamma, velocity, saved_force, cl, moments = [np.array([s[key] for s in raw['strips']])
            for key in ('circulation','relative_velocity','force','cl','moment')]
    speed = case['condition']['speed']
    alpha = math.radians(case['alpha'])
    axis = np.array([math.cos(alpha), 0., math.sin(alpha)])
    assert case['condition']['freeze_influences'] and case['condition']['mach'] == speed/340.21
    rho, qs = 1.2256, .5*1.2256*speed**2*.9329
    beta = np.sqrt(np.longdouble(1)-np.longdouble(speed/340.21)**2)
    pieces = common.module(common.OPERATOR,'lower_pairs').operators(g['hv'],g['a'],g['b'],beta)
    native = common.module(common.AVL,'lower_native').matrix
    scale = 1/(4*np.arccos(np.longdouble(-1))*np.longdouble('.079577472'))
    operator = native(g['hv'],g['a'],g['b'],speed/340.21,exclude_self=True,core_fraction=0.,dtype=np.longdouble)*scale
    full = sum(pieces.values())
    errors = dict(operator=float(np.max(abs(full-operator))))
    v = np.asarray(np.einsum('ijq,j->iq',full,gamma)+speed*axis,dtype=float)
    errors['velocity_relative'] = float(np.max(abs(v-velocity))/speed)
    del operator
    cp = native(g['cp'],g['a'],g['b'],speed/340.21,exclude_self=False,core_fraction=0.,dtype=np.longdouble)*scale
    vcp = np.asarray(np.einsum('ijq,j->iq',cp,gamma)+speed*axis,dtype=float)
    del cp
    perp = v-np.sum(v*span,axis=1)[:,None]*span
    vp = np.linalg.norm(perp,axis=1)
    mach = vp/340.21
    errors['section_cl'] = float(max(abs(2*gamma/(g['chord']*vp)-cl)))
    width, strength = (case['condition'][key] for key in ('stall_width','stall_factor'))
    f = width*(np.logaddexp(0,(cl-sample('CLmax'))/width)-np.logaddexp(0,(sample('CLmin')-cl)/width))
    tangency = np.sum(vcp*normal,axis=1)
    errors['tangency_relative'] = float(max(abs(tangency-vp*strength*f/sample('dCLda')))/speed)
    forces = dict(vortex=rho*gamma[:,None]*np.cross(v,span)*g['ds'][:,None],
        friction=.5*rho*np.linalg.norm(v,axis=1)[:,None]*v*(g['chord']*sample('Cdf')*g['ds'])[:,None],
        pressure=.5*rho*vp[:,None]*perp*(g['chord']*sample('Cdp')*g['ds'])[:,None],
        stall_leakage=2*rho*perp/vp[:,None]*(tangency**2*g['chord']*g['ds'])[:,None])
    force = sum(forces.values())
    errors['force_vector'] = float(np.max(abs(force-saved_force)))
    cd = float(np.sum(force@axis)/qs)
    lift_axis = np.array([-math.sin(alpha),0.,math.cos(alpha)])
    cl_total = float(np.sum(force@lift_axis)/qs)
    errors['coefficients'] = max(abs(cd-row['values']['CD']),abs(cl_total-row['values']['CL']))
    if accepted:
        assert max(mach)<1 and np.all(np.isfinite(moments))
        position = np.concatenate([m.rm for m in meshes])
        cm = float(np.sum(moments[:,1]+np.cross(position,saved_force)[:,1])/(qs*.37874))
        errors['moment'] = abs(cm-row['values']['Cm_origin'])
    else:
        assert max(mach)>=1 and np.all(np.isnan(moments)) and row['values']['Cm_origin'] is None
    errors['maximum_mach'] = abs(float(max(mach))-row['maximum_normal_mach'])
    measure = np.asarray(span*g['ds'][:,None],dtype=np.longdouble)
    pairs = {key:rho*gamma[:,None]*gamma[None,:]*(np.cross(tensor,measure[:,None,:])@axis)/qs
             for key,tensor in pieces.items()}
    total_pairs = sum(pairs.values())
    errors['pair_force'] = abs(float(total_pairs.sum())-float(np.sum(forces['vortex']@axis)/qs))
    blocks = {f'{receiver}_from_{source}':float(total_pairs[np.ix_(beam==receiver,beam==source)].sum())
              for receiver in range(1,6) for source in range(1,6)}
    own = np.eye(len(beam),dtype=bool)
    lower = beam>=4
    lower_own = lower[:,None]&own
    lower_same = lower[:,None]&(beam[:,None]==beam[None,:])&~own
    lower_main = lower[:,None]&(beam[None,:]==1)
    lower_upper = lower[:,None]&np.isin(beam[None,:],[2,3])
    lower_opposite = lower[:,None]&(beam[None,:]>=4)&(beam[:,None]!=beam[None,:])
    masks = dict(own_lower_horseshoe=lower_own,other_same_lower_beam=lower_same,
        lower_from_main=lower_main,lower_from_upper=lower_upper,lower_from_opposite_lower=lower_opposite)
    assert np.array_equal(sum(mask.astype(int) for mask in masks.values()),np.broadcast_to(lower[:,None],total_pairs.shape))
    partition = {key:{name:float(pair[mask].sum()) for name,mask in masks.items()} for key,pair in pairs.items()}
    root_records = []
    for b in (4,5):
        selected = np.flatnonzero(beam==b)
        if not len(selected):continue
        i = int(selected[np.argmin(abs(t[selected]))])
        rays = []
        for endpoint,sign in (('a',-1),('b',1)):
            delta = np.asarray(g['hv'][i]-g[endpoint][i],dtype=np.longdouble)
            radius2 = delta[1]**2+delta[2]**2
            xp = delta[0]/beta
            ray = sign*gamma[i]*np.array([0.,-delta[2],delta[1]])/(4*np.arccos(np.longdouble(-1))*radius2)*(1+xp/np.sqrt(xp*xp+radius2))
            rays.append(dict(endpoint=endpoint,distance_mm=float(np.sqrt(radius2)*1000),
                velocity=list(map(float,ray)),speed=float(np.linalg.norm(ray)),
                receiver_CD=float(rho*gamma[i]*np.dot(np.cross(ray,measure[i]),axis)/qs)))
        own_velocity = (pieces['half_wake'][i,i]+pieces['finite_origin'][i,i])*gamma[i]
        errors['own_ray'] = max(errors.get('own_ray',0.),float(np.max(abs(np.sum([r['velocity'] for r in rays],axis=0)-own_velocity))))
        root_records.append(dict(beam=b,index=i,t=float(t[i]),normal_mach=float(mach[i]),
            total_CD=float(force[i]@axis/qs),vortex_CD=float(total_pairs[i].sum()),
            own_horseshoe_CD=float(total_pairs[i,i]),rays=rays,
            source_beam_CD={str(k):float(total_pairs[i,beam==k].sum()) for k in range(1,6)}))
    assert errors['operator']<2e-10 and errors['velocity_relative']<2e-10
    assert errors['section_cl']<2e-12 and errors['tangency_relative']<1e-8
    assert errors['force_vector']<1e-9 and errors['coefficients']<2e-12
    assert errors.get('moment',0)<2e-12 and errors['maximum_mach']<2e-12
    assert errors['pair_force']<2e-12 and errors.get('own_ray',0)<2e-10
    if case['group']=='geometry_trial':
        for item in row['per_beam']:
            selected = beam==item['beam']
            assert abs(float(np.sum(force[selected]@axis)/qs)-item['CD'])<2e-12
            for key in forces:assert abs(float(np.sum(forces[key][selected]@axis)/qs)-item['CD_parts'][key])<2e-12
    directory.mkdir()
    np.savez(directory/'pairs.npz',**{key:np.asarray(pair,dtype=float) for key,pair in pairs.items()},
        beam=beam,t=t,force_CD=force@axis/qs,gamma=gamma,mach=mach)
    report = dict(observed_utc=common.utc(),verified=True,case=case,accepted=accepted,
        CL=cl_total,CD=cd,maximum_normal_mach=float(max(mach)),
        total_drag_parts={key:float(np.sum(value@axis)/qs) for key,value in forces.items()},
        beam_drag_parts={str(b):{key:float(np.sum(value[beam==b]@axis)/qs) for key,value in forces.items()} for b in range(1,6)},
        blocks=blocks,lower_partition=partition,root_records=root_records,errors=errors,
        physical_solves=0,primary_passes_added=0,plan_sha256=common.sha(out/'plan.json'),
        pairs_sha256=common.sha(directory/'pairs.npz'),seconds=time.monotonic()-begin,
        peak_rss_kib=common.resource.getrusage(common.resource.RUSAGE_SELF).ru_maxrss)
    common.write(directory/'report.json',report)
    common.signal.alarm(0)
    print(dict(id=case['id'],verified=True,accepted=accepted,CL=cl_total,CD=cd,
        errors=errors,lower_partition={key:sum(p[key] for p in partition.values()) for key in masks}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--index',type=int)
    args=parser.parse_args()
    if args.action=='prepare':prepare(args.output.resolve())
    else:run(args.output.resolve(),args.index)
