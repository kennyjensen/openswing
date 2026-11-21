"""Bounded thin-blade ST-1 modal reconstruction; retain unresolved mode identities."""
import argparse
from pathlib import Path
import resource
import time

import verify_st1_modal_mechanics as modal

common = modal.common
ROOT = common.ROOT
SOURCE = modal.BASE/'[45_0]_s.asw'


def prepare(out):
    prior = common.read(ROOT/'artifacts/isae/st1-cross-modal-reconstruction-20261109/retry/plan.json')
    common.authenticate(prior['pins'])
    out.mkdir(); (out/'inputs').mkdir()
    source = SOURCE.read_text()
    cases = {}
    for name, sign in [('thin-up',1),('thin-down',-1)]:
        lines = source.splitlines(keepends=True)
        header = next(i for i,line in enumerate(lines) if line.split()[:6] == ['t','x','y','z','chord','Xax'])
        fields = lines[header].split(); values = lines[header+1].split()
        assert len(fields)==16 and len(values)==17
        assert float(values[1+fields.index('mg')]) == -9.81
        assert float(values[1+fields.index('EIcs')]) == -1
        values[1+fields.index('mg')] = '9.81'
        values[1+fields.index('EIcs')] = str(sign)
        lines[header+1] = ' '.join(values)+'\n'
        derived = out/'inputs'/f'{name}.asw'
        derived.write_text(''.join(lines)+'End\n')
        cases[name] = dict(model=derived.relative_to(ROOT).as_posix(),mass=.0238,icc=6.22e-10,inn=1.91e-6,
            fields=dict(EIcc=.0143,GJ=.0195,EInn=99.,GKc=2.7e5,EA=1.3e6,GKn=1e5,EIcs=sign*.00632),
            targets=dict(modal.PENDING[name]['targets']))
    pins = dict(prior['pins'])
    for path in [Path(__file__),SOURCE,*sorted((out/'inputs').iterdir())]:
        pins[path.relative_to(ROOT).as_posix()] = common.sha(path)
    common.write(out/'plan.json',dict(observed_utc=common.utc(),pins=pins,cases=cases,
        jobs=[dict(case=name,nominal=n) for name in cases for n in (40,80)],
        modal_survey=dict(count=12,shift=[-.01,0.],method='full_shift_invert',step=1e-5),
        required=10,relative_tolerance=.05,
        source='Unchanged ASW frequencies in ISAE Part III Table3 p35, including literal down 3B=218.',
        reconstruction='Positive distributed mass .0238 kg/m from ISAE Table9 p52 and Minguet Table5.2(a) p124. '
          'Bend-twist magnitude .00632 N m2 from raw ASW and Minguet p124; retain ISAE/raw GKc and rotary inertias. '
          'Up uses positive coupling, down negative coupling in the same fixed axes. A half-turn about span '
          'has R=diag(-1,1,-1), so R K R.T changes only the c/s coupling sign for these centered properties. '
          'This represents ideal face orientations without negative inertia; historical file/label mapping remains unproven. '
          'Append End to empty Engine. All raw numeric table entries unchanged.',
        selection=prior['selection']+' Also attempt first F mode by the same activity rule. Missing family or unexpected shape zeros remain unresolved; do not select nearest frequency.',
        gates=prior['gates'],limits=prior['limits'],
        primary_passes_added=0,primary_archive_passes_added=0,
        qualifications='Conditional reconstruction. No automatic promotion to primary counts. Thin-down 218-vs-21.8 conflict retained. Strongly mixed modes may remain unlabelled by the existing classifier.'))
    print('Declared four serial jobs and all ten unchanged thin-blade frequency targets.',flush=True)


def run(out,index):
    plan=common.read(out/'plan.json');common.authenticate(plan['pins'])
    job=plan['jobs'][index];c=plan['cases'][job['case']];folder=out/f'job-{index}';folder.mkdir()
    source=(ROOT/c['model']).read_text();(folder/'model.asw').write_text(source)
    print('Source authenticated; importing numerical modules.',flush=True)
    import numpy as np
    from scipy.sparse import save_npz
    from openswing.asw import parse_asw
    from openswing.bridge import dispatch
    from openswing import linear_dynamics as dynamics
    model=parse_asw(source,beam_interpolation='drela-segspl-v1')
    assert not model.diagnostics and len(model.beams)==1
    beam=model.beams[0];sample=np.array([-.28,0.,.28])
    for name,value in dict(**c['fields'],mg=c['mass']*9.81,mgcc=c['icc']*9.81,mgnn=c['inn']*9.81,
                           twist=0.,chord=.03,Xax=.5).items():
        np.testing.assert_allclose(beam.value(name,sample),value,rtol=2e-15,atol=0)
    for name in ('Cea','Nea','Cta','Nta','Ccg','Ncg','Dmg','EIcn','EIsn'):
        assert np.all(beam.value(name,sample)==0)
    assert len(model.records['weight'])==1 and model.records['weight'][0][5]==0
    k=np.array([[.0143,.00632,0.],[.00632,.0195,0.],[0.,0.,99.]])
    r=np.diag([-1.,1.,-1.]);flipped=r@k@r.T
    assert flipped[0,1]==-.00632 and np.all(np.linalg.eigvalsh(k)>0)
    request=dict(action='modes',mode='modes',source=source,condition=None,gravity=[0.,0.,-9.81],loads=[],
        panels=dict(default=job['nominal'],beams={'1':dict(count=job['nominal'],spacing='cosine')}),
        numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator='drela-fixed-vacuum-v1'),
        modes=dict(frame='fixed',vacuum=True,**plan['modal_survey'],matrices=False,rank_tolerance=1e-9,
            tolerance=1e-9,continuation_steps=4,position=[0.,0.,0.],attitude=[0.,0.,0.]))
    common.write(folder/'request.json',request)
    original=dynamics.linearize;captured=[]
    def capture(system,*args,**kwargs):
        a,m=original(system,*args,**kwargs);captured.append((system,a,m))
        print('Equilibrium and linearization completed.',flush=True);return a,m
    dynamics.linearize=capture;started=time.monotonic()
    print('Starting modal dispatch.',flush=True)
    try:result=dispatch(request)
    finally:dynamics.linearize=original
    seconds=time.monotonic()-started;common.write(folder/'result.json',result)
    assert len(captured)==1;system,a,m=captured[0]
    save_npz(folder/'A.npz',a);save_npz(folder/'M.npz',m)
    base=result['base'];assert result['converged'] and base['converged'] and base['residual']<1e-8
    residual=float(np.max(abs(system.residual(np.zeros(system.size),np.zeros(system.size)))))
    assert residual<1e-8 and system.network.ng==0 and len(base['nodes'])==job['nominal']+1
    assert result['frame_mode']=='fixed' and result['vacuum'] and base['gravity_body']==[0.,0.,-9.81]
    audits=[]
    for mode in result['modes']:
        lam=complex(*mode['eigenvalue']);values={}
        for side in ('right','left'):
            v=np.asarray(mode[side]['real'])+1j*np.asarray(mode[side]['imag'])
            av,mv=(a@v,m@v) if side=='right' else (v.conjugate()@a,v.conjugate()@m)
            error=float(np.linalg.norm(av-lam*mv)/(np.linalg.norm(av)+abs(lam)*np.linalg.norm(mv)))
            assert error<1e-8;values[side]=error
        assert abs(lam.real)<1e-6*max(1.,abs(lam.imag))
        audits.append(dict(index=mode['index'],**values))
    classified=[modal.shape_activity(mode,base,c) for mode in result['modes'] if mode['eigenvalue'][1]>1e-6]
    selected={}
    for family,number in [('B',3),('T',1),('F',1)]:
        candidates=sorted((row for row in classified if row['family']==family),key=lambda row:row['frequency'])
        for rank,row in enumerate(candidates[:number],1):
            if row['internal_zeros']==rank-1:selected[str(rank)+family]=row
    comparisons=[]
    for label,expected in c['targets'].items():
        row=selected.get(label)
        comparisons.append(dict(label=label,expected_Hz=expected,
            actual_Hz=row['frequency'] if row else None,
            error_percent=100*abs(row['frequency']/expected-1) if row else None,
            passed=bool(row and abs(row['frequency']/expected-1)<=.05),
            mode_index=row['mode_index'] if row else None,
            identity_available=row is not None))
    common.authenticate(plan['pins'])
    common.write(folder/'report.json',dict(observed_utc=common.utc(),job=job,seconds=seconds,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,base_residual=residual,
        tip_position=base['nodes'][0]['position'],pencil_audits=audits,classified=classified,
        comparisons=comparisons,plan_sha256=common.sha(out/'plan.json'),
        artifacts={p.name:common.sha(p) for p in folder.iterdir() if p.is_file()}))
    print(dict(job=job,seconds=seconds,tip_position=base['nodes'][0]['position'],classified=classified,comparisons=comparisons),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('prepare','run'))
    p.add_argument('--output',type=Path,required=True);p.add_argument('--index',type=int)
    args=p.parse_args();common.bounded()
    if args.action=='prepare':prepare(args.output.resolve())
    else:run(args.output.resolve(),args.index)
