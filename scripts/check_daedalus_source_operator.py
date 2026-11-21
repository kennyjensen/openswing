"""Daedalus using Drela endpoint balance equations, one capped serial stage.

The literal aircraft and exact C16 node stations are preserved. SEGSPL and
the source moving-airflow operator replace the older midpoint/natural pair.
An old state is an explicitly provisional initial guess only: all equilibrium
equations and all dynamic matrices are recomputed under the new identity.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
LIMITS = dict(address_space_bytes=512*1024**2, cpu_seconds=15, wall_seconds=25)
SPEEDS = [6.7]
CHANNELS = ['yaw_rate', 'roll_rate', 'sideslip', 'bank']
PROJECT = ROOT/'examples/dae-cruise-physical-mesh-project.json'
REFERENCE = ROOT/'docs/validation/daedalus-rudder-four-outputs.csv'
VARIANTS = [
    ('daedalus-source-20261113','Endpoint equations, pointwise'),
    ('daedalus-source-fourier8-20261113','Eight Fourier modes per surface'),
    ('daedalus-source-nolag-20261113','Aerodynamic lag disabled'),
    ('daedalus-source-noplume-20261113','Propeller plume disabled'),
]


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def pin(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def imports():
    global np, sp, spla
    import numpy as np
    import scipy.sparse as sp
    import scipy.sparse.linalg as spla


def setup(speed, seed, frozen=False, no_lag=False, no_plume=False, fourier=0):
    from dataclasses import replace
    from openswing.asw import parse_asw
    from openswing.source_airflow import SourceAirflowNetwork
    from openswing.equilibrium_state import restore, restore_physical_fields
    from openswing.time_state import read_condition
    config = read(PROJECT)['cases'][0]['configuration']
    original = config['equilibrium']['state']
    packet = original if seed is None else read(seed)
    launch = original['launch']
    model = parse_asw(config['source'], beam_interpolation='drela-segspl-v1')
    if no_plume:
        # Original manual, Engine jet: negative Rdisk disables the plume while
        # retaining the physical disk radius and propulsion force law.
        for row in model.records['engine']:
            row[12] = -abs(row[12])
    condition = replace(read_condition(launch['condition']), speed=speed/.3048,
                        freeze_influences=frozen, aero_lag=not no_lag,
                        circulation_modes={b.index:fourier for b in model.beams if b.lifting} if fourier else {})
    panels = dict(default=16, beams={k:dict(nodes=v[0]) for k,v in original['identity']['stations'].items()})
    n = SourceAirflowNetwork(model, panels, condition, launch['gravity'], launch['loads'],
        operating_constraints=launch['released_constraints'], strut_mode=launch['strut_mode'],
        mesh_recipe='physical-breaks-v1', steady_trim=True)
    for k,(stations,indices) in n.station_nodes.items():
        np.testing.assert_array_equal(stations, original['identity']['stations'][str(k)][0])
    # Deliberate initial-guess conversion, never an identity relabel or an
    # accepted old equilibrium. Subsequent stages enforce the new identity.
    if seed is None and fourier:
        # Explicit least-squares initial guess in the requested sine space.
        # This is never accepted without solving the new weighted equations.
        packet=dict(packet,circulation=n.circulation_basis.decode(
            n.circulation_basis.encode(packet['circulation'],strict=False)).tolist())
    x = restore_physical_fields(n, packet) if seed is None else restore(n, packet)
    assert (n.nn, n.ne, n.ng) == (108, 103, 4*fourier if fourier else 82)
    assert abs(n.operating.apply(x[n.operating_start:])[0].speed*.3048-speed) < 1e-12
    return n, x


def canonical(n, x):
    """Same physical equations with six acceleration/net-load slots instead of trim."""
    from copy import copy
    from openswing.operating import OperatingSystem, time_load_constraints
    c, motion, _ = n.operating.apply(x[n.operating_start:])
    p = copy(n)
    p.condition, p.motion = c, motion
    p.operating = OperatingSystem(p.model, c, motion, time_load_constraints('free'), p.L, p.F)
    p.size = p.operating_start+p.operating.count
    p.aero_key = p.mass_key = None
    y = np.r_[x[:n.operating_start], np.zeros(p.operating.count)]
    return p, y


def trim_matrix(n, x):
    """Reorder the full canonical force/moment rows, then differentiate trim controls.

    Geometry/circulation/internal-load derivatives are the exact same equations.
    Flight-path angle depends on the frame/flow variables, not elastic geometry.
    No acceleration column is substituted for a trim variable.
    """
    p, y = canonical(n, x)
    common = n.operating_start
    r, rp = n.residual(x), p.residual(y)
    np.testing.assert_allclose(r[:common], rp[:common], atol=2e-13, rtol=2e-13)
    j = p.jacobian(y, 1., _sparse=True, _direct_geometry=True,
        progress=lambda *v: print(v, flush=True))
    targets = {c.quantity: common+i for i, c in enumerate(p.operating.constraints)}
    rows = [j[:common, :common]]
    for i, c in enumerate(n.operating.constraints):
        if c.quantity == 'flight_path':
            rows.append(sp.csc_matrix((1, common)))
        else:
            assert c.target == 0 and c.weight == 1
            assert abs(r[common+i]-rp[targets[c.quantity]]) < 2e-13
            rows.append(j[targets[c.quantity]:targets[c.quantity]+1, :common])
    right = []
    for k in range(common, n.size):
        h = 1e-5*max(1., abs(x[k]))
        d = np.zeros(n.size); d[k] = h
        right.append((8*(n.residual(x+d)-n.residual(x-d))-
                      (n.residual(x+2*d)-n.residual(x-2*d)))/(12*h))
    matrix = sp.hstack([sp.vstack(rows, format='csc'), sp.csc_matrix(np.array(right).T)], format='csc')
    # Independent complete-residual directional check includes all seven trim variables.
    direction = np.random.default_rng(371).normal(size=n.size)
    direction /= np.linalg.norm(direction)
    h = 2e-6
    fd = (n.residual(x+h*direction)-n.residual(x-h*direction))/(2*h)
    error = float(np.linalg.norm(matrix@direction-fd)/max(np.linalg.norm(fd), 1e-30))
    assert error < 2e-5, error
    return matrix, error


def save_state(folder, n, x, **extra):
    from openswing.equilibrium_state import capture
    r = n.residual(x)
    packet = capture(n, x, residual=float(max(abs(r))))
    write(folder/'state.json', packet)
    c = n.operating.apply(x[n.operating_start:])[0]
    return dict(residual_max=float(max(abs(r))), accepted=bool(max(abs(r)) <= 1e-9),
        speed_m_s=c.speed*.3048, alpha_deg=c.alpha, beta_deg=c.beta,
        controls=c.controls, powers=c.powers, attitude_deg=list(c.attitude), **extra)


def trim(folder, args):
    n, x = setup(args.speed, args.seed, args.frozen, args.no_lag, args.no_plume, args.fourier)
    before = float(max(abs(n.residual(x))))
    if args.stage == 'residual':
        _, data=n.residual(x,detail=True)
        write(folder/'sections.json',data['aero']['strips'])
        return save_state(folder, n, x)
    j, check = trim_matrix(n, x)
    from openswing.equilibrium_state import check_tangent_rank
    rank = check_tangent_rank(j)
    factor = spla.splu(j)
    history = [before]
    for iteration in range(6):
        r = n.residual(x); error = float(max(abs(r)))
        if error <= 1e-9:
            break
        delta = factor.solve(-r)
        for power in range(9):
            trial = x+delta/2**power
            try:
                next_error = float(max(abs(n.residual(trial))))
            except ValueError:
                continue
            if next_error < error*(1-1e-4/2**power) or next_error <= 1e-9:
                x = trial; history.append(next_error)
                break
        else:
            raise RuntimeError('Full residual line search did not decrease; retain previous state.')
        print('residual', next_error, flush=True)
    sp.save_npz(folder/'trim-tangent.npz', j)
    return save_state(folder, n, x, residual_history=history, directional_relative_error=check,
        tangent_rank_check=rank, qualification='Rank checked at start of this correction stage.')


def dynamic(args):
    from openswing.linear_dynamics import _dynamic_base
    from openswing.operating import time_load_constraints
    n, x = setup(args.speed, args.seed, args.frozen, args.no_lag, args.no_plume, args.fourier)
    assert max(abs(n.residual(x))) <= 1e-9
    z = np.zeros_like(n.rj)
    options = dict(elastic_motion=(z,z,z,z), circulation_rate=np.zeros(n.circulation_basis.panels))
    return _dynamic_base(n, x, time_load_constraints('free'), 'free', options,
        position=(0,0,0), attitude=(0,0,0), velocity=(0,0,0), gravity_magnitude=None)


def linear(folder, args):
    from openswing.linear_dynamics import linearize, state_layout
    from openswing.frequency_response import HarmonicInput, input_partials
    system = dynamic(args)
    a, m = linearize(system, sparse=True, progress=lambda *v: print('linear', v, flush=True))
    b, _, _ = input_partials(system, [HarmonicInput(system, 'control.3', 0)], 0., 1e-5)
    c = np.zeros((4, system.size))
    start = system.frame_start
    c[0, start+5] = system.W
    c[1, start+3] = system.W
    alpha, beta = np.deg2rad([system.condition.alpha, system.condition.beta])
    c[2, start:start+3] = system.V*np.array([np.cos(alpha)*np.sin(beta), np.cos(beta), np.sin(alpha)*np.sin(beta)])/system.condition.speed
    c[3, start+9] = 1.
    c *= 180/np.pi
    sp.save_npz(folder/'A.npz', a); sp.save_npz(folder/'M.npz', m)
    np.savez_compressed(folder/'maps.npz', B=b, C=c)
    write(folder/'layout.json', state_layout(system))
    return dict(size=system.size, speed_m_s=system.condition.speed*.3048,
        state_derivative_diagnostics=system.state_derivative_diagnostics,
        mass_derivative_diagnostics=getattr(system, 'mass_derivative_diagnostics', None))


def staged_linear(folder, args):
    """Same production derivative blocks, checkpointed between bounded jobs."""
    from openswing.tangent_influences import TangentInfluences
    from openswing.linear_dynamics import dynamic_circulation_columns, state_layout
    from openswing.mechanical_tangent import mechanical_columns
    from openswing.local_rate_tangent import local_rate_columns
    from openswing.descriptor_mass import mass_matrix
    from openswing.frequency_response import HarmonicInput, input_partials
    system = dynamic(args)
    n = system.network
    n.tangent_influences = TangentInfluences(local_geometry=True); n.aero_key = None
    zero = np.zeros(system.size)
    r, state, options = system.residual(zero, zero, detail=True)
    _, data = n.residual(state.x, detail=True, **options)
    assert max(abs(r)) < 1e-9
    clips = tuple(v['power_clipped'] for v in data['aero']['engines'])
    def checked(z):
        value = system.residual(z, zero)
        assert tuple(v['power_clipped'] for v in n.aero_cached['engines']) == clips
        return value
    scales = np.r_[np.maximum(1.,abs(system.base)),np.ones(system.size-n.size)]
    step = 1e-5
    diagnostics = {}
    if args.stage == 'geometry_fd':
        indices=list(range(args.start,min(6*n.nn,args.start+args.count)))
        columns=[]
        for j in indices:
            h=step*scales[j]; d=zero.copy(); d[j]=h
            value=(8*(checked(d)-checked(-d))-(checked(2*d)-checked(-2*d)))/(12*h)
            columns.append(sp.csc_matrix(value[:,None]))
        sp.save_npz(folder/'geometry-part.npz',sp.hstack(columns,format='csc'))
        diagnostics=dict(columns=indices,method='Production fallback: fourth-order complete residual stencils',step=step)
    elif args.stage == 'geometry_join':
        indices=[]; blocks=[]
        for chunk in args.chunks:
            assert read(chunk/'terminal.json')['returncode']==0
            p=read(chunk/'plan.json')
            assert p['arguments']['speed']==args.speed
            assert p['inputs_sha256'][str(args.seed.resolve())]==pin(args.seed)
            indices+=read(chunk/'result.json')['diagnostics']['columns']
            blocks.append(sp.load_npz(chunk/'geometry-part.npz'))
        assert indices==list(range(6*n.nn))
        sp.save_npz(folder/'geometry.npz',sp.hstack(blocks,format='csc'))
        diagnostics=dict(columns=len(indices),method='Complete residual fallback, all geometry columns included')
    elif args.stage == 'geometry':
        from openswing.geometry_tangent import geometry_columns
        from openswing.support_outputs import SupportTangent
        support = SupportTangent(system)
        a, diagnostics = geometry_columns(n, checked, lambda z:system.unpack(z,zero)[0].x,
            scales, step, _direct_vortex=True, _direct_volume=True, _nodewise_state=True,
            _direct_geometry=True, _rotation_chart='spatial', _strut_tangent=support,
            _direct_structural=False, _structural_system=system,
            progress=lambda *v:print('geometry', v, flush=True))
        sp.save_npz(folder/'geometry.npz', a)
    elif args.stage == 'other':
        columns = {}
        mechanical, diagnostics['mechanical'] = mechanical_columns(system,data,scales,step)
        columns.update({j:mechanical[:,k] for k,j in enumerate(range(6*n.nn,n.gamma_start))})
        circ = dynamic_circulation_columns(system)
        columns.update({j:sp.csc_matrix(circ[:,k,None]) for k,j in enumerate(range(n.gamma_start,n.operating_start))})
        local, indices, diagnostics['local_motion'] = local_rate_columns(system)
        columns.update({int(j):local[:,k] for k,j in enumerate(indices)})
        remaining = [j for j in range(6*n.nn,system.size) if j not in columns]
        for j in remaining:
            h = step*scales[j]; d = zero.copy(); d[j] = h
            value = (8*(checked(d)-checked(-d))-(checked(2*d)-checked(-2*d)))/(12*h)
            columns[j] = sp.csc_matrix(value[:,None])
        a = sp.hstack([columns[j] for j in range(6*n.nn,system.size)],format='csc')
        sp.save_npz(folder/'other.npz', a)
        diagnostics['full_stencil_columns'] = remaining
    elif args.stage == 'mass':
        m = mass_matrix(system,state,data,step,sparse=True)
        sp.save_npz(folder/'M.npz', m)
        b, _, _ = input_partials(system,[HarmonicInput(system,'control.3',0)],0.,step)
        c = np.zeros((4,system.size)); start = system.frame_start
        c[0,start+5] = system.W; c[1,start+3] = system.W
        alpha,beta = np.deg2rad([system.condition.alpha,system.condition.beta])
        c[2,start:start+3] = system.V*np.array([np.cos(alpha)*np.sin(beta),np.cos(beta),np.sin(alpha)*np.sin(beta)])/system.condition.speed
        c[3,start+9] = 1.; c *= 180/np.pi
        np.savez_compressed(folder/'maps.npz', B=b, C=c)
        write(folder/'layout.json', state_layout(system))
        diagnostics = getattr(system,'mass_derivative_diagnostics',{})
    else:
        for part in args.parts:
            p = read(part/'plan.json')
            assert p['arguments']['speed'] == args.speed
            assert p['inputs_sha256'][str(args.seed.resolve())] == pin(args.seed)
            assert read(part/'terminal.json')['returncode'] == 0
        geo,other,mass = args.parts
        a = sp.hstack([sp.load_npz(geo/'geometry.npz'),sp.load_npz(other/'other.npz')],format='csc')
        m = sp.load_npz(mass/'M.npz')
        # Independent full residual probes exercise complete assembled A and M.
        errors=[]
        rng=np.random.default_rng(12345)
        for _ in range(3):
            d=rng.normal(size=system.size); d/=np.linalg.norm(d); h=2e-6
            fd=(checked(h*d)-checked(-h*d))/(2*h)
            fm=-(system.residual(zero,h*d)-system.residual(zero,-h*d))/(2*h)
            ea=float(np.linalg.norm(a@d-fd)/np.linalg.norm(fd))
            em=float(np.linalg.norm(m@d-fm)/np.linalg.norm(fm))
            assert ea<2e-5 and em<2e-6,(ea,em)
            errors.append(dict(state_relative=ea,rate_relative=em))
        sp.save_npz(folder/'A.npz',a); sp.save_npz(folder/'M.npz',m)
        (folder/'maps.npz').write_bytes((mass/'maps.npz').read_bytes())
        diagnostics=dict(complete_directional_checks=errors)
    return dict(size=system.size,speed_m_s=system.condition.speed*.3048,
                base_residual=float(max(abs(r))),diagnostics=diagnostics)


def response(folder, args):
    from openswing.frequency_response import harmonic_solve
    from openswing.harmonic_structure import ReusableBeamStructure
    matrix = Path(args.matrix)
    assert read(matrix/'terminal.json')['returncode'] == 0
    a, m = (sp.load_npz(matrix/name) for name in ('A.npz', 'M.npz'))
    maps = np.load(matrix/'maps.npz')
    size=2044-82+(4*args.fourier if args.fourier else 82)
    assert a.shape == m.shape == (size,size)
    for pencil in (a,m):
        for array in (pencil.data,pencil.indices,pencil.indptr): array.flags.writeable=False
    # The exact production beam elimination retains every entry and restores
    # the complete vector; it is not modal reduction or an entry cutoff.
    structure = ReusableBeamStructure(a,m,
        np.r_[np.arange(6*103),np.arange(6*(103+108),1296)],
        np.arange(6*(108+103)),np.arange(size-660,size-12),np.arange(size-660,size-12))
    frequencies = sorted(set(np.geomspace(.1, 10., 61).tolist()+[.2, 1.1, 1.15737773741517, 1.3]))
    selected = frequencies[args.start:args.start+args.count]
    rows = []
    for f in selected:
        print('harmonic', f, a.nnz, m.nnz, flush=True)
        z, checks = harmonic_solve(a, m, maps['B'][:, 0], 2*np.pi*f, _structure=structure)
        out = maps['C']@z
        rows.append(dict(frequency_hz=f, real=out.real.tolist(), imag=out.imag.tolist(),
                         magnitude=abs(out).tolist(), checks=checks))
    return dict(channels=CHANNELS, speed_m_s=args.speed, samples=rows,
                frequency_count_total=len(frequencies), start=args.start, structure=structure.report)


def constrained_response(folder, args):
    """Exact restriction to prescribed axial/normal/pitch accelerations.

    Three acceleration variables and their net-load equations are removed.
    Three full nonlinear mixed-frame probes independently check the restricted
    pencil. Elastic motion and all twelve frame kinematic states survive.
    """
    from openswing.linear_dynamics import _dynamic_base
    from openswing.operating import time_load_constraints
    from openswing.frequency_response import harmonic_solve
    from openswing.harmonic_structure import ReusableBeamStructure
    assert not args.fourier, 'Mixed-frame diagnostic currently uses the pointwise case.'
    n,x=setup(args.speed,args.seed,args.frozen,args.no_lag,args.no_plume,args.fourier)
    z=np.zeros_like(n.rj)
    options=dict(elastic_motion=(z,z,z,z),circulation_rate=np.zeros(n.circulation_basis.panels))
    system=_dynamic_base(n,x,time_load_constraints('mixed',{'force.y':0.,'moment.x':0.,'moment.z':0.}),
        'mixed',options,position=(0,0,0),attitude=(0,0,0),velocity=(0,0,0),gravity_magnitude=None)
    keep=np.delete(np.arange(2044),n.operating_start+np.array([0,2,4]))
    a=sp.load_npz(args.matrix/'A.npz')[keep,:][:,keep].tocsc()
    m=sp.load_npz(args.matrix/'M.npz')[keep,:][:,keep].tocsc()
    maps=np.load(args.matrix/'maps.npz'); b=maps['B'][keep,0]; c=maps['C'][:,keep]
    assert system.size==2041 and a.shape==m.shape==(system.size,system.size)
    zero=np.zeros(system.size); errors=[]
    assert max(abs(system.residual(zero,zero)))<1e-9
    rng=np.random.default_rng(12345)
    for _ in range(3):
        d=rng.normal(size=system.size);d/=np.linalg.norm(d);h=2e-6
        fd=(system.residual(h*d,zero)-system.residual(-h*d,zero))/(2*h)
        fm=-(system.residual(zero,h*d)-system.residual(zero,-h*d))/(2*h)
        ea=float(np.linalg.norm(a@d-fd)/np.linalg.norm(fd))
        em=float(np.linalg.norm(m@d-fm)/np.linalg.norm(fm))
        assert ea<2e-5 and em<2e-6,(ea,em)
        errors.append(dict(state_relative=ea,rate_relative=em))
    for pencil in (a,m):
        for array in (pencil.data,pencil.indices,pencil.indptr): array.flags.writeable=False
    structure=ReusableBeamStructure(a,m,np.r_[np.arange(6*n.ne),np.arange(6*(n.ne+n.nn),n.gamma_start)],
        np.arange(6*(n.nn+n.ne)),np.arange(system.velocity_start,system.frame_start),
        np.arange(system.velocity_start,system.frame_start))
    rows=[]
    for f in (.1,.2,.7,1.,1.15737773741517,1.5,2.,8.9):
        state,checks=harmonic_solve(a,m,b,2*np.pi*f,_structure=structure)
        out=c@state
        rows.append(dict(frequency_hz=f,real=out.real.tolist(),imag=out.imag.tolist(),
            magnitude=abs(out).tolist(),checks=checks))
    return dict(channels=CHANNELS,samples=rows,full_residual_checks=errors,
        scope='Mixed frame: prescribed axial/normal/pitch accelerations; lateral/roll/yaw free. All elastic and frame kinematic states retained.',
        identification='Documented allowable constraint choice, not identified reference settings.')


def report(folder, args):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import LogLocator, FuncFormatter, NullFormatter
    study=args.study.resolve()
    jobs=[]; failures=[]
    source_pins=read(study/'study-plan.json')['source_pins']
    for receipt in sorted(study.glob('*/terminal.json')):
        job=receipt.parent; t=read(receipt); p=read(job/'plan.json')
        assert t['process_reaped'] and t['inputs_unchanged'] and t['limits']==LIMITS
        assert p['source_pins']==source_pins
        for path,digest in p['inputs_sha256'].items():
            candidate=job/'runner.py' if path==str(Path(__file__).resolve()) else Path(path)
            assert pin(candidate)==digest,str(candidate)
        jobs.append((job,t,p))
        if t['returncode']!=0: failures.append(dict(job=job.name,**t))
    with REFERENCE.open() as stream: raw=list(csv.DictReader(stream))
    reference={key:np.array([[float(r['frequency_Hz']),float(r['reference_drawing_magnitude'])]
                           for r in raw if r['channel']==key]) for key in CHANNELS}
    fig,axes=plt.subplots(2,2,figsize=(12,8.2),sharex=True,layout='constrained')
    colors=['#2563eb','#059669','#ea580c','#9333ea','#dc2626']
    summary=[]; csvrows=[]; all_checks=[]
    study_speeds=read(study/'study-plan.json')['speeds_m_s']
    for speed,color in zip(study_speeds,colors):
        collected=[]
        for job,t,p in jobs:
            if t['returncode']==0 and p['arguments']['stage']=='response' and p['arguments']['speed']==speed:
                result=read(job/'result.json'); assert result['channels']==CHANNELS
                collected+=result['samples']
        collected.sort(key=lambda r:r['frequency_hz'])
        frequencies=np.array([r['frequency_hz'] for r in collected])
        assert len(frequencies)==65 and len(set(frequencies))==65
        magnitude=np.array([r['magnitude'] for r in collected])
        refs=np.column_stack([np.exp(np.interp(np.log(frequencies),np.log(reference[k][:,0]),np.log(reference[k][:,1]))) for k in CHANNELS])
        errors=abs(magnitude/refs-1)
        db=20*np.log10(magnitude/refs)
        # Equal log-frequency weighting; four extra feature samples are excluded from RMS.
        grid=np.geomspace(.1,10.,61)
        uniform=np.array([np.min(abs(np.log(f/grid)))<1e-12 for f in frequencies])
        assert sum(uniform)==61
        j=int(np.argmin(abs(frequencies-1.15737773741517)))
        band=np.flatnonzero((frequencies>=.6)&(frequencies<=2.))
        minimum=int(band[np.argmin(magnitude[band,0])])
        trim=read(study/f'certify-{speed:g}/result.json')
        assert trim['accepted'] and len(trim['residual_history'])==1
        assembled=read(study/f'assembled-{speed:g}/result.json')
        entry=dict(speed_m_s=speed,trim=trim,frequencies=len(frequencies),
            comparison_values=int(errors.size),within_5_percent=int((errors<=.05).sum()),
            rms_log_magnitude_error_db=float(np.sqrt(np.mean(db[uniform]**2))),
            channel_rms_db={k:float(np.sqrt(np.mean(db[uniform,i]**2))) for i,k in enumerate(CHANNELS)},
            channel_median_error_percent={k:float(np.median(errors[:,i])*100) for i,k in enumerate(CHANNELS)},
            yaw_0_1_hz=float(magnitude[0,0]),yaw_0_1_error_percent=float((magnitude[0,0]/refs[0,0]-1)*100),
            yaw_at_reference_dip=float(magnitude[j,0]),yaw_at_reference_dip_error_percent=float((magnitude[j,0]/refs[j,0]-1)*100),
            sampled_yaw_minimum_hz=float(frequencies[minimum]),sampled_yaw_minimum=float(magnitude[minimum,0]),
            complete_matrix_checks=assembled['diagnostics']['complete_directional_checks'])
        summary.append(entry)
        for i,key in enumerate(CHANNELS):
            axes.flat[i].loglog(frequencies,magnitude[:,i],color=color,
                label=f'Endpoint/SEGSPL {speed:g} m/s'+(' frozen' if args.frozen else '')+(' lag disabled' if args.no_lag else '')+(' plume disabled' if args.no_plume else '')+(f' Fourier {args.fourier}' if args.fourier else ''),lw=1.65)
        for r,want,error in zip(collected,refs,errors):
            all_checks.append(r['checks'])
            for i,key in enumerate(CHANNELS):
                csvrows.append([speed,r['frequency_hz'],key,r['real'][i],r['imag'][i],r['magnitude'][i],want[i],error[i]*100])
    titles=['Yaw rate r','Roll rate p','Sideslip beta','Bank angle']
    with (ROOT/'artifacts/daedalus-speed-20261113/report/comparison.csv').open() as stream:
        old=list(csv.DictReader(stream))
    for i,key in enumerate(CHANNELS):
        rows=[r for r in old if r['channel']==key and float(r['speed_m_s'])==6.7]
        axes.flat[i].loglog([float(r['frequency_hz']) for r in rows],
            [float(r['magnitude_display']) for r in rows],color='#059669',lw=1.65,label='Midpoint/natural, 6.7 m/s unfrozen')
    for i,key in enumerate(CHANNELS):
        ax=axes.flat[i];ref=reference[key]
        ax.loglog(ref[:,0],ref[:,1],color='black',lw=2.1,ls='--',label='Drela drawing')
        ax.fill_between(ref[:,0],.95*ref[:,1],1.05*ref[:,1],color='black',alpha=.1)
        ax.set_title(titles[i]);ax.set_xlabel('Frequency (cycles/s)')
        ax.set_ylabel(('deg/s' if i<2 else 'deg')+' per native F3 unit')
        ax.set_xlim(.1,10.)
        for axis in (ax.xaxis,ax.yaxis):
            axis.set_major_locator(LogLocator(base=10))
            axis.set_minor_locator(LogLocator(base=10,subs=np.arange(2,10)))
            axis.set_major_formatter(FuncFormatter(lambda x,pos:f'{x:g}'))
            axis.set_minor_formatter(NullFormatter())
        ax.grid(which='major',alpha=.4);ax.grid(which='minor',alpha=.14)
    axes.flat[0].legend(fontsize=8,ncol=2)
    heading='Daedalus: endpoint beam operator and SEGSPL at 6.7 m/s'+(' — lag disabled diagnostic' if args.no_lag else '')+(' — plume disabled diagnostic' if args.no_plume else '')
    fig.suptitle(heading+'\nLiteral mass/stiffness, same C16 stations, fresh trim; shaded band = ±5% of drawing',fontsize=12)
    fig.savefig(folder/'four-output-speed.svg');fig.savefig(folder/'four-output-speed.png',dpi=140)
    plt.close(fig)
    with (folder/'comparison.csv').open('x',newline='') as stream:
        writer=csv.writer(stream)
        writer.writerow(['speed_m_s','frequency_hz','channel','real_display','imag_display','magnitude_display','reference_magnitude','absolute_relative_error_percent'])
        writer.writerows(csvrows)
    assert all(min(c['reciprocal_condition'],1.)>=1e-12 and max(c['backward_errors'])<=1e-9 and max(c['scaled_residuals'])<=1e-7 for c in all_checks)
    return dict(observed_utc=utc(),speeds=summary,total_harmonic_solves=len(all_checks),
        best_aggregate_speed_m_s=min(summary,key=lambda r:r['rms_log_magnitude_error_db'])['speed_m_s'],
        any_speed_matches_all_samples=any(r['within_5_percent']==r['comparison_values'] for r in summary),
        max_scaled_harmonic_residual=max(max(c['scaled_residuals']) for c in all_checks),
        min_harmonic_reciprocal_condition=min(c['reciprocal_condition'] for c in all_checks),
        reference_yaw_minimum=float(reference['yaw_rate'][:,1].min()),
        successful_jobs=sum(t['returncode']==0 for _,t,_ in jobs),retained_failed_jobs=failures,
        max_successful_cpu_seconds=max(t['cpu_seconds'] for _,t,_ in jobs if t['returncode']==0),
        max_successful_wall_seconds=max(t['wall_seconds'] for _,t,_ in jobs if t['returncode']==0),
        max_successful_rss_kib=max(t['peak_rss_kib'] for _,t,_ in jobs if t['returncode']==0),
        qualifications=['Documented operator/option comparison, not identified historical operating-point validation.',
            'Fixed corrected C16 physical-breaks-v1 mesh; high-frequency mesh convergence remains open.',
            'Drela moving-airflow operator and SEGSPL, PG Mach .1, aerodynamic lag='+str(not args.no_lag)+'; influence freezing='+str(args.frozen)+'.',
            'Reference phase and original operating-point settings are unavailable.',
            'Plume disabled by documented negative Rdisk option='+str(args.no_plume)+'.',
            'No mass/stiffness property, input gain, production default, ISAE count or acceptance gate changed.'])


def summary(folder,args):
    """Presentation of completed comparisons; no solver or matrix assembly."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import LogLocator, FuncFormatter, NullFormatter
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    with REFERENCE.open() as stream: raw=list(csv.DictReader(stream))
    summaries=[]
    for (study,label),color in zip(VARIANTS,['#2563eb','#059669','#ea580c','#9333ea']):
        report_dir=ROOT/'artifacts'/study/'report'
        assert read(report_dir/'terminal.json')['returncode']==0
        with (report_dir/'comparison.csv').open() as stream: rows=list(csv.DictReader(stream))
        summaries.append(dict(label=label,study=study,**read(report_dir/'result.json')['speeds'][0]))
        for i,key in enumerate(CHANNELS):
            selected=[r for r in rows if r['channel']==key]
            assert len(selected)==65
            axes.flat[i].loglog([float(r['frequency_hz']) for r in selected],
                [float(r['magnitude_display']) for r in selected],label=label,color=color,lw=1.5)
    for i,key in enumerate(CHANNELS):
        ax=axes.flat[i]; rows=[r for r in raw if r['channel']==key]
        f=[float(r['frequency_Hz']) for r in rows]; v=np.array([float(r['reference_drawing_magnitude']) for r in rows])
        ax.loglog(f,v,color='black',ls='--',lw=2,label='Drela drawing')
        ax.fill_between(f,.95*v,1.05*v,color='black',alpha=.08)
        ax.set_title(['Yaw rate','Roll rate','Sideslip','Bank angle'][i])
        ax.set_xlabel('Frequency (cycles/s)'); ax.set_ylabel(('deg/s' if i<2 else 'deg')+' per native F3 unit')
        ax.set_xlim(.1,10)
        for axis in (ax.xaxis,ax.yaxis):
            axis.set_major_locator(LogLocator(base=10));axis.set_minor_locator(LogLocator(base=10,subs=np.arange(2,10)))
            axis.set_major_formatter(FuncFormatter(lambda x,pos:f'{x:g}'));axis.set_minor_formatter(NullFormatter())
        ax.grid(which='major',alpha=.4);ax.grid(which='minor',alpha=.14)
    axes.flat[0].legend(fontsize=8)
    fig.suptitle('Daedalus: documented operator and option comparisons\n6.7 m/s, same mass/stiffness and C16 stations; shaded band = ±5% of drawing')
    fig.savefig(folder/'comparison.svg');fig.savefig(folder/'comparison.png',dpi=140);plt.close(fig)
    return dict(cases=summaries,any_case_matches_all_samples=False,
        qualification='Separate controlled comparisons, not identified original operating-point settings.')


def animation_trace(folder,args):
    """Extract image-coordinate boom traces, without inferring 3-D motion."""
    from PIL import Image
    results=[]
    for name,f in [('slow-rudder',.2),('fast-rudder',1.)]:
        path=ROOT/'reference/daedalus-rudder-animations-20261113'/(name+'.gif')
        movie=Image.open(path);rows=[]
        # Each first cycle is 91 frames, including the repeated endpoint.
        # Annotated times (frame1=0, frame46=T/2) define simulation time;
        # GIF playback delay is deliberately not interpreted as physical time.
        for index in range(0,91,5):
            movie.seek(index);rgb=np.asarray(movie.convert('RGB')).astype(int)
            mask=(rgb[:,:,0]<100)&(rgb[:,:,1]>150)&(rgb[:,:,2]>150)&(abs(rgb[:,:,1]-rgb[:,:,2])<30)
            # Reject annotation pixels. A broad corridor around the central
            # boom rejects isolated palette/overlap pixels on the fin; retain
            # the first unfiltered extraction separately in its old job.
            mask[:200,:]=False
            y,x=np.nonzero(mask)
            original_count=len(x)
            central=(x>=400)&(x<=520)&(y>=350)&(y<=500)
            assert central.sum()>20,(name,index,int(central.sum()))
            line=np.polyfit(x[central],y[central],1)
            on_boom=abs(y-np.polyval(line,x))<8
            x,y=x[on_boom],y[on_boom]
            assert len(x)>20,(name,index,len(x))
            edges=[]
            for near in (x<=x.min()+1,x>=x.max()-1):
                edges.append([float(np.mean(x[near])),float(np.mean(y[near]))])
            rows.append(dict(frame=index,time_seconds=index/(90*f),cyan_pixels=len(x),
                rejected_off_boom_pixels=original_count-len(x),fitted_central_line=line.tolist(),
                image_left_endpoint=edges[0],image_right_endpoint=edges[1]))
        movie.close();endpoints=np.array([[*r['image_left_endpoint'],*r['image_right_endpoint']] for r in rows])
        phase=2*np.pi*np.array([r['time_seconds'] for r in rows])*f
        design=np.column_stack([np.ones(len(rows)),np.cos(phase),np.sin(phase)])
        coefficients=np.linalg.lstsq(design,endpoints,rcond=None)[0]
        results.append(dict(name=name,frequency_hz=f,samples=rows,
            offset_cos_sin_coefficients_px=coefficients.tolist(),
            max_fit_residual_px=float(abs(design@coefficients-endpoints).max())))
    return dict(traces=results,scope='First-cycle cyan tailboom raster bounds; image-coordinate candidate landmarks only.',
        limitations=['Occlusion, palette overlap and antialiasing can move a raster endpoint; an eight-pixel corridor is an image-analysis filter, not a physical tolerance.',
            'Projection, viewing scale and aircraft-frame motion are not calibrated.',
            'No inferred physical deflection, phase validation or Bode agreement claim.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['residual', 'trim', 'linear', 'response', 'geometry', 'geometry_fd', 'geometry_join', 'other', 'mass', 'assemble', 'report', 'constraints', 'summary', 'animation_trace'])
    parser.add_argument('--study', type=Path, required=True)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--speed', type=float, required=True)
    parser.add_argument('--frozen', action='store_true', help='Separate control using frozen jig influence coefficients.')
    parser.add_argument('--no-lag', action='store_true', help='Diagnostic only: documented K/L=False. Default remains True.')
    parser.add_argument('--no-plume', action='store_true', help='Diagnostic only: documented negative Rdisk option, retaining thrust.')
    parser.add_argument('--fourier', type=int, default=0, choices=range(0,19), help='Uniform sine-mode count per lifting beam; zero is pointwise.')
    parser.add_argument('--seed', type=Path)
    parser.add_argument('--matrix', type=Path)
    parser.add_argument('--parts', type=Path, nargs=3)
    parser.add_argument('--chunks', type=Path, nargs='+')
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--count', type=int, default=12)
    args = parser.parse_args()
    study = args.study.resolve()
    study.mkdir(parents=True, exist_ok=True)
    sources = list((ROOT/'openswing').glob('*.py'))+[PROJECT, REFERENCE, ROOT/'examples/dae.asw']
    source_pins = {str(p):pin(p) for p in sources}
    if not (study/'study-plan.json').exists():
        write(study/'study-plan.json', dict(observed_utc=utc(), speeds_m_s=[6.7] if args.frozen else SPEEDS,
            source_pins=source_pins, limits=LIMITS, trim_tolerance=1e-9,
            mesh='Exact original physical-breaks-v1 C16 stations: 108 nodes, 103 elements, 82 lifting intervals',
            fixed_settings=dict(mach=.1, freeze_influences=args.frozen, aero_lag=not args.no_lag, plume_enabled=not args.no_plume,
                fourier_modes_per_lifting_beam=args.fourier,
                structural_operator='drela-moving-airflow-v1', beam_interpolation='drela-segspl-v1'),
            initial_guess='Old midpoint physical fields only; requires full new-policy trim and new dynamic matrices.',
            reference='Four digitized magnitude curves; original operating point and phases unavailable.',
            comparison='All four outputs over 0.1–10 Hz; no property or amplitude fitting.'))
    assert read(study/'study-plan.json')['source_pins'] == source_pins
    assert read(study/'study-plan.json')['fixed_settings']['freeze_influences'] == args.frozen
    assert read(study/'study-plan.json')['fixed_settings']['aero_lag'] == (not args.no_lag)
    assert read(study/'study-plan.json')['fixed_settings'].get('plume_enabled',True) == (not args.no_plume)
    assert read(study/'study-plan.json')['fixed_settings'].get('fourier_modes_per_lifting_beam',0) == args.fourier
    folder = study/args.tag
    folder.mkdir(exist_ok=False)
    (folder/'runner.py').write_bytes(Path(__file__).read_bytes())
    inputs = [Path(__file__)]
    if args.seed: inputs.append(args.seed)
    if args.matrix: inputs += [args.matrix/p for p in ('A.npz','M.npz','maps.npz','result.json','terminal.json')]
    if args.parts:
        for part in args.parts: inputs += list(part.glob('*.npz'))+[part/'result.json',part/'terminal.json',part/'plan.json']
    if args.chunks:
        for part in args.chunks: inputs += [part/'geometry-part.npz',part/'result.json',part/'terminal.json',part/'plan.json']
    if args.stage=='report':
        inputs += [study/'study-plan.json']
        for name in ('result.json','terminal.json','plan.json'): inputs += list(study.glob('*/'+name))
        inputs += [ROOT/'artifacts/daedalus-speed-20261113/report/comparison.csv']
    if args.stage=='summary':
        for root,_ in VARIANTS:
            inputs += [ROOT/'artifacts'/root/'report'/name for name in ('comparison.csv','result.json','terminal.json')]
    if args.stage=='animation_trace':
        inputs += [ROOT/'reference/daedalus-rudder-animations-20261113'/name for name in ('slow-rudder.gif','fast-rudder.gif','source-receipt.json')]
    pins = {str(p.resolve()):pin(p) for p in inputs}
    write(folder/'plan.json', dict(observed_utc=utc(), arguments={k:str(v) if isinstance(v,Path) else [str(p) for p in v] if isinstance(v,list) else v for k,v in vars(args).items()},
        inputs_sha256=pins, source_pins=source_pins, limits=LIMITS))
    sys.stdout.flush()
    started = time.monotonic()
    pid = os.fork()
    if pid == 0:
        code = 0
        try:
            for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
                os.environ[name] = '1'
            resource.setrlimit(resource.RLIMIT_AS, (LIMITS['address_space_bytes'],)*2)
            resource.setrlimit(resource.RLIMIT_CPU, (LIMITS['cpu_seconds'],)*2)
            sys.path.insert(0, str(ROOT))
            with (folder/'stdout.log').open('x') as out, (folder/'stderr.log').open('x') as err:
                os.dup2(out.fileno(),1); os.dup2(err.fileno(),2)
                try:
                    imports()
                    result = trim(folder,args) if args.stage in ('trim','residual') else linear(folder,args) if args.stage=='linear' else response(folder,args) if args.stage=='response' else constrained_response(folder,args) if args.stage=='constraints' else report(folder,args) if args.stage=='report' else summary(folder,args) if args.stage=='summary' else animation_trace(folder,args) if args.stage=='animation_trace' else staged_linear(folder,args)
                    write(folder/'result.json', result)
                except BaseException:
                    traceback.print_exc(); code = 1
                sys.stdout.flush(); sys.stderr.flush()
        except BaseException:
            traceback.print_exc(); code = 1
        os._exit(code)
    reaped = 0; timed_out = False
    try:
        while not reaped:
            reaped,status,usage = os.wait4(pid,os.WNOHANG)
            if reaped: break
            if time.monotonic()-started > LIMITS['wall_seconds']:
                timed_out = True; os.kill(pid,signal.SIGKILL)
                reaped,status,usage = os.wait4(pid,0); break
            time.sleep(.05)
    finally:
        if not reaped:
            os.kill(pid,signal.SIGKILL); reaped,status,usage = os.wait4(pid,0)
    terminal = dict(observed_utc=utc(), returncode=os.waitstatus_to_exitcode(status), process_reaped=True,
        timed_out=timed_out, cpu_seconds=usage.ru_utime+usage.ru_stime, wall_seconds=time.monotonic()-started,
        peak_rss_kib=usage.ru_maxrss, limits=LIMITS,
        inputs_unchanged=all(pin(p)==h for p,h in {**source_pins,**pins}.items()))
    write(folder/'terminal.json', terminal)
    print(json.dumps(terminal), flush=True)
    raise SystemExit(terminal['returncode'] or (0 if terminal['inputs_unchanged'] else 1))


if __name__ == '__main__':
    main()
