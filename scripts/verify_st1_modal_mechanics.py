"""ST-1 named modal mechanics: serial source-preserving vacuum comparisons."""
import argparse
import math
from pathlib import Path
import resource
import time

import verify_sa14_defaults as common

ROOT=common.ROOT
BASE=ROOT/'reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST1 High aspect ratio/Modal_analysis'
CASES={
    'angle':dict(model='[20_m70_20]_2a',mass=.091,icc=2.79e-8,inn=6.82e-6,
        fields=dict(EIcc=.983,GJ=1.18,EInn=290.,GKc=1.1e6,EA=3.9e6,GKn=1.2e5,EIcs=0.),
        targets={'1B':5.86,'2B':36.8,'3B':103.,'1T':187.}),
    'coupled':dict(model='[45_0]_3s',mass=.0697,icc=1.25e-8,inn=5.22e-6,
        fields=dict(EIcc=.522,GJ=.368,EInn=298.,GKc=2.6e5,EA=3.7e6,GKn=2.9e5,EIcs=.102),
        targets={'1B':4.75,'2B':29.81,'3B':83.7,'1T':95.}),
}
PENDING={
    'cross':dict(targets={'1B':5.74,'2B':36.,'3B':101.,'1T':78.},
        reason='Modal source has an extra unnamed scale and GKn multiplier 1e-5; its named shear stiffness differs from the static/report configuration.'),
    'thin-up':dict(targets={'1B':1.4,'2B':8.14,'3B':21.8,'1T':59.,'1F':7.6},
        reason='Supplied thin model has negative distributed weight/mass multiplier; generating up/down setups are not yet established.'),
    'thin-down':dict(targets={'1B':1.4,'2B':8.14,'3B':218.,'1T':59.,'1F':7.6},
        reason='Same negative-mass/setup issue. Literal Table 3 prints 218 for 3B; postprocessor says 21.8. Retain the conflict pending reconciliation.'),
}


def prepare(out):
    files=[Path(__file__),ROOT/'scripts/verify_sa14_defaults.py',
           ROOT/'docs/validation/aswing-authoritative-references.md',ROOT/'docs/validation/aswing-authoritative-sources.json',
           *sorted((ROOT/'openswing').glob('*.py')),BASE/'post_traitement.m',ROOT/'reference/aswing_doc.txt']
    catalog=common.read(ROOT/'docs/validation/aswing-authoritative-sources.json')
    for e in catalog['files']:
        if e['id'] in ('isae-part-3','drela-unsteady'):
            for field,key in [('local_pdf','sha256'),('local_text','text_sha256')]:
                assert common.sha(ROOT/e[field])==e[key];files.append(ROOT/e[field])
    for c in CASES.values():
        for suffix in ('.asw','.sh','_eigen.txt'):files.append(BASE/(c['model']+suffix))
        source=(BASE/(c['model']+'.asw')).read_text();assert source.rstrip().endswith('\nEngine')
        script=(BASE/(c['model']+'.sh')).read_text();assert 'I 40' in script and '-0.1 300' in script and '\nf\nn\n' in script
    for name in ('[0_90]_3s.asw','[45_0]_s.asw'):files.append(BASE/name)
    pins={p.relative_to(ROOT).as_posix():common.sha(p) for p in files}
    jobs=[dict(case=name,nominal=n) for name in CASES for n in (40,80)]
    common.write(out/'plan.json',dict(observed_utc=common.utc(),pins=pins,cases=CASES,pending=PENDING,jobs=jobs,
        named_frequency_required=22,currently_runnable_named_frequencies=8,relative_tolerance=.05,
        source='ISAE Part III Table 3, p.35; ASW rows, not experimental rows. Original labels retained.',
        physics='Original modal files with only End appended to empty Engine. Fixed frame; stationary self-weight equilibrium; '
                'no tip mass; no material damping. Source endpoint structural and real-inertia operator. '
                'Original MODE f command interpreted as enabling vacuum (Drela user documentation MODE menu). '
                'Binary startup toggle state remains unavailable. Earlier still-air angle-ply run retained separately as a diagnostic.',
        modal_survey=dict(count=16,shift=[-.01,0.],method='full_shift_invert',step=1e-5),
        selection='Positive-frequency modes, classified by dominant structural kinetic shape activity in current local axes: '
                  'normal displacement/chord rotation=B, chord displacement/normal rotation=F, span rotation=T. '
                  'A family needs >55% activity. Ascending frequency within each family; no frequency-target-based selection. '
                  'First three B modes must have 0/1/2 internal normal-displacement zeros; first T mode zero internal twist zeros.',
        gates=dict(base=1e-8,pencil_action_relative=1e-8,mesh_relative=.01,shape_activity=.55),
        primary_archive_passes_added=0,
        limits=dict(blas_threads=1,address_space_mib=512,cpu_seconds=15,wall_seconds=25)))
    print('Declared all 22 report frequency targets; two original layouts runnable on nominal40/80 meshes.')


def shape_activity(mode,base,c):
    import numpy as np
    def vector(v):return np.asarray(v['real'])+1j*np.asarray(v['imag'])
    nodes=base['nodes'];t=np.array([n['t'] for n in nodes]);assert np.all(np.diff(t)>0)
    q=np.array([n['rotation'] for n in nodes]);u=np.array([vector(n['displacement']) for n in mode['output']['nodes']])
    r=np.array([vector(n['rotation']) for n in mode['output']['nodes']])
    u=np.einsum('nji,nj->ni',q,u);r=np.einsum('nji,nj->ni',q,r)
    weights=np.zeros(len(t));weights[:-1]+=np.diff(t)/2;weights[1:]+=np.diff(t)/2
    activity=dict(B=float(weights@(c['mass']*abs(u[:,2])**2+c['icc']*abs(r[:,0])**2)),
                  F=float(weights@(c['mass']*abs(u[:,0])**2+c['inn']*abs(r[:,2])**2)),
                  T=float(weights@((c['icc']+c['inn'])*abs(r[:,1])**2)),
                  A=float(weights@(c['mass']*abs(u[:,1])**2)))
    total=sum(activity.values());assert total>0
    fractions={k:v/total for k,v in activity.items()};family=max(fractions,key=fractions.get)
    if fractions[family]<=.55:family='mixed'
    shape=r[:,1] if family=='T' else u[:,{'B':2,'F':0,'A':1}.get(family,2)]
    pivot=shape[np.argmax(abs(shape))];real=(shape*pivot.conjugate()/abs(pivot)).real
    active=real[abs(real)>1e-3*np.max(abs(real))]
    zeros=int(np.sum(active[:-1]*active[1:]<0))
    return dict(mode_index=mode['index'],frequency=mode['frequency'],family=family,
                activity_fractions=fractions,internal_zeros=zeros)


def run(out,index):
    plan=common.read(out/'plan.json');common.authenticate(plan['pins']);job=plan['jobs'][index];c=plan['cases'][job['case']]
    folder=out/f'job-{index}';folder.mkdir();original=(BASE/(c['model']+'.asw')).read_text();source=original+'End\n'
    (folder/'model.asw').write_text(source)
    import numpy as np
    from scipy.sparse import save_npz
    from openswing.asw import parse_asw
    from openswing.bridge import dispatch
    from openswing import linear_dynamics as dynamics
    model=parse_asw(source,beam_interpolation='drela-segspl-v1');assert not model.diagnostics and len(model.beams)==1
    beam=model.beams[0];sample=np.array([-.28,0.,.28])
    for name,value in dict(**c['fields'],mg=c['mass']*9.81,mgcc=c['icc']*9.81,mgnn=c['inn']*9.81,
                           twist=0.,chord=.03,Xax=.5).items():
        np.testing.assert_allclose(beam.value(name,sample),value,rtol=2e-15,atol=0)
    for name in ('Cea','Nea','Cta','Nta','Ccg','Ncg','Dmg'):assert np.all(beam.value(name,sample)==0)
    assert len(model.records['weight'])==1 and model.records['weight'][0][5]==0
    request=dict(action='modes',mode='modes',source=source,condition=None,gravity=[0.,0.,-9.81],loads=[],
        panels=dict(default=job['nominal'],beams={'1':dict(count=job['nominal'],spacing='cosine')}),
        numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator='drela-fixed-vacuum-v1'),
        modes=dict(frame='fixed',vacuum=True,**plan['modal_survey'],
            matrices=False,rank_tolerance=1e-9,tolerance=1e-9,continuation_steps=4,
            position=[0.,0.,0.],attitude=[0.,0.,0.]))
    common.write(folder/'request.json',request)
    original_linearize=dynamics.linearize;captured=[]
    def capture(system,*args,**kwargs):
        a,m=original_linearize(system,*args,**kwargs);captured.append((system,a,m));return a,m
    dynamics.linearize=capture;started=time.monotonic()
    try:result=dispatch(request)
    finally:dynamics.linearize=original_linearize
    seconds=time.monotonic()-started;common.write(folder/'result.json',result)
    assert len(captured)==1;system,a,m=captured[0]
    save_npz(folder/'A.npz',a);save_npz(folder/'M.npz',m)
    base=result['base'];assert result['converged'] and base['converged'] and base['residual']<1e-8
    residual=float(np.max(abs(system.residual(np.zeros(system.size),np.zeros(system.size)))))
    assert residual<1e-8 and system.network.ng==0
    assert len(base['nodes'])==job['nominal']+1
    assert result['frame_mode']=='fixed' and result['vacuum'] is True and 'fluid' not in result
    assert base['gravity_body']==[0.,0.,-9.81]
    audits=[]
    for mode in result['modes']:
        # linearize returns the physical-time pencil, M dz/dt = A z.
        lam=complex(*mode['eigenvalue']);checks={}
        for side in ('right','left'):
            v=np.asarray(mode[side]['real'])+1j*np.asarray(mode[side]['imag'])
            av,mv=(a@v,m@v) if side=='right' else (v.conjugate()@a,v.conjugate()@m)
            error=float(np.linalg.norm(av-lam*mv)/(np.linalg.norm(av)+abs(lam)*np.linalg.norm(mv)))
            assert error<1e-8;checks[side]=error
        assert abs(mode['eigenvalue'][0])<1e-6*max(1.,abs(mode['eigenvalue'][1]))
        audits.append(dict(index=mode['index'],**checks))
    classified=[shape_activity(mode,base,c) for mode in result['modes'] if mode['eigenvalue'][1]>1e-6]
    selected={}
    for family,number in [('B',3),('T',1)]:
        candidates=sorted((r for r in classified if r['family']==family),key=lambda r:r['frequency'])
        assert len(candidates)>=number,(family,classified)
        for rank,r in enumerate(candidates[:number],1):
            assert r['internal_zeros']==rank-1,(family,rank,r)
            selected[str(rank)+family]=r
    comparisons=[]
    for name,expected in c['targets'].items():
        actual=selected[name]['frequency'];error=abs(actual/expected-1)
        comparisons.append(dict(label=name,expected_Hz=expected,actual_Hz=actual,error_percent=100*error,
                                passed=error<=.05,mode_index=selected[name]['mode_index']))
    common.authenticate(plan['pins'])
    common.write(folder/'report.json',dict(observed_utc=common.utc(),job=job,seconds=seconds,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,base_residual=residual,
        time_scale=system.W,pencil_audits=audits,classified=classified,comparisons=comparisons,
        plan_sha256=common.sha(out/'plan.json'),artifacts={p.name:common.sha(p) for p in folder.iterdir() if p.is_file()}))
    print(dict(job=job,seconds=seconds,frequencies=[(r['family'],r['frequency'],r['internal_zeros']) for r in classified],
               comparisons=comparisons))


def summarize(out):
    plan=common.read(out/'plan.json');common.authenticate(plan['pins']);cases={}
    for i,job in enumerate(plan['jobs']):
        folder=out/f'job-{i}';r=common.read(folder/'report.json')
        assert r['plan_sha256']==common.sha(out/'plan.json') and r['job']==job
        for name,h in r['artifacts'].items():assert common.sha(folder/name)==h
        cases.setdefault(job['case'],{})[str(job['nominal'])]=r
    rows=[];mesh=[]
    for name,grids in cases.items():
        for coarse,fine in zip(grids['40']['comparisons'],grids['80']['comparisons'],strict=True):
            assert coarse['label']==fine['label']
            change=abs(coarse['actual_Hz']/fine['actual_Hz']-1)
            mesh.append(dict(case=name,label=coarse['label'],relative_change=change,passed=change<.01))
            rows.append(dict(case=name,**fine,coarse_passed=coarse['passed'],mesh_passed=change<.01))
    passed=sum(r['passed'] and r['coarse_passed'] and r['mesh_passed'] for r in rows)
    common.write(out/'summary.json',dict(observed_utc=common.utc(),required=22,passed=passed,computed=8,pending=14,
        rows=rows,mesh=mesh,pending_cases=plan['pending'],plan_sha256=common.sha(out/'plan.json'),
        primary_archive_passes_added=0,production_physics_changed=False,full_ST1_validated=False))
    print(dict(passed=passed,required=22,computed=8,pending=14,rows=rows,mesh=mesh))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('prepare','run','summary'))
    p.add_argument('--output',type=Path,required=True);p.add_argument('--index',type=int)
    args=p.parse_args();common.bounded()
    if args.action=='prepare':prepare(args.output.resolve())
    elif args.action=='run':run(args.output.resolve(),args.index)
    else:summarize(args.output.resolve())
