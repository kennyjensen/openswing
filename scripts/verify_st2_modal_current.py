"""Current-code ST-2 modal comparison, with literal models and mesh/shape checks.

Still-air density and prospective cosine grids are declared, not inferred as
the unavailable original run settings. Each invocation solves one bounded job.
"""
import argparse
from decimal import Decimal
from pathlib import Path
import resource
import time

import verify_sa14_defaults as common

ROOT=common.ROOT
BASE=ROOT/'reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST2 Pazy_Wing'
ORIENTATIONS={'upright':'01_Modal_Undeformed','horizontal':'02_Modal_Gravity'}
PAPER={'upright':{'OOP1':4.59,'OOP2':29.1,'T1':43.4,'IP1':128.,'OOP3':81.4},
       'horizontal':{'OOP1':4.67,'OOP2':29.2,'T1':43.2,'IP1':116.,'OOP3':81.4}}
LABELS=('OOP1','OOP2','T1','OOP3','IP1','T2','OOP4')


def prepare(out):
    from isae_suite_st2 import decode_modal
    out.mkdir(parents=True,exist_ok=True)
    paths=[Path(__file__),ROOT/'scripts/verify_sa14_defaults.py',ROOT/'scripts/isae_suite_st2.py',
           ROOT/'scripts/isae_suite_st2_modal.py',ROOT/'scripts/isae_st2_loaded_reference.py',
           ROOT/'docs/validation/aswing-authoritative-references.md',ROOT/'docs/validation/aswing-authoritative-sources.json',
           ROOT/'reference/aswing_doc.txt',*sorted((ROOT/'openswing').glob('*.py'))]
    pins={p.relative_to(ROOT).as_posix():common.sha(p) for p in paths}
    catalog=common.read(ROOT/'docs/validation/aswing-authoritative-sources.json')
    for entry in catalog['files']:
        if entry['id'] in ('isae-part-3','drela-unsteady','drela-steady'):
            for key,h in [('local_pdf','sha256'),('local_text','text_sha256')]:
                assert common.sha(ROOT/entry[key])==entry[h];pins[entry[key]]=entry[h]
    cases={};jobs=[]
    for orientation,folder in ORIENTATIONS.items():
        model=BASE/folder/'Pazy_wing.asw';table=model.with_suffix('.e00')
        for p in (model,table):pins[p.relative_to(ROOT).as_posix()]=common.sha(p)
        cases[orientation]=dict(source=model.relative_to(ROOT).as_posix(),reference=table.relative_to(ROOT).as_posix(),
            targets=decode_modal(table.read_text()),paper_targets=PAPER[orientation])
        for nominal in (38,78,158):jobs.append(dict(orientation=orientation,nominal=nominal,nodes=nominal+2))
    common.write(out/'plan.json',dict(observed_utc=common.utc(),pins=pins,cases=cases,jobs=jobs,required=14,
        modal_survey=dict(count=20,shift=[-.01,0.],method='full_shift_invert',step=1e-5),
        gates=dict(reference_relative=.05,mesh_relative=.01,shape_MAC=.99,pencil=1e-8,base=1e-9,neutral_relative=1e-8),
        limits=dict(blas_threads=1,address_space_mib=512,cpu_seconds=15,wall_seconds=25),
        protocol='Literal two modal models including inactive null Weight rows. Fixed-frame self-weight equilibrium, '
            'still air at source density1.23, no mean flow. Cosine38/78/158 intervals plus .52 break yield40/80/160 nodes. '
            'First seven positive roots by computed frequency, unique conjugate partners; no target-nearest pairing. '
            'Forty-node results retained; acceptance requires both80/160 reference frequencies, mesh convergence and '
            'mass-weighted shape correspondence. Ten named Table4 cells are overlapping cross-checks, not extra votes. '
            'All raw real components retained, separately from neutral undamped-mode verification. '
            'No historical medium, mesh or native eigenvector identity is claimed.'))
    print('Prepared six serial modal jobs; fourteen unique native frequencies and ten overlapping report labels.')


def run(out,index):
    plan=common.read(out/'plan.json');common.authenticate(plan['pins']);job=plan['jobs'][index];c=plan['cases'][job['orientation']]
    folder=out/f'job-{index}';folder.mkdir()
    import numpy as np
    from scipy.sparse import save_npz
    from openswing.bridge import dispatch
    from openswing import linear_dynamics as dynamics
    from isae_suite_st2_modal import spectrum_evidence
    source=(ROOT/c['source']).read_text()
    request=dict(action='modes',mode='modes',source=source,condition=None,gravity=[0.,0.,-9.81],loads=[],
        panels=dict(default=job['nominal'],beams={'1':dict(count=job['nominal'],spacing='cosine')}),
        numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator='drela-fixed-still-air-v1'),
        modes=dict(frame='fixed',vacuum=False,quiescent_density=1.23,**plan['modal_survey'],
            matrices=False,rank_tolerance=1e-9,tolerance=1e-9,continuation_steps=4,
            position=[0.,0.,0.],attitude=[0.,0.,0.]))
    common.write(folder/'request.json',request);held=[];original=dynamics.linearize
    def capture(system,*args,**kwargs):
        a,m=original(system,*args,**kwargs);held.append((system,a,m))
        save_npz(folder/'A.npz',a);save_npz(folder/'M.npz',m)
        return a,m
    dynamics.linearize=capture;started=time.monotonic()
    try:result=dispatch(request)
    finally:dynamics.linearize=original
    seconds=time.monotonic()-started;common.write(folder/'result.json',result)
    assert len(held)==1;system,a,m=held[0];network=system.network;base=result['base'];nodes=base['nodes']
    assert len(nodes)==job['nodes'] and system.size==18*job['nodes'] and network.ng==0
    assert len(network.model.records['weight'])==2 and all(not np.any(r[5:]) and r[1]==.558 for r in network.model.records['weight'])
    assert not network.model.diagnostics and result['frame_mode']=='fixed' and result['vacuum'] is False
    assert result['fluid']['density']==1.23 and base['gravity_body']==[0.,0.,-9.81]
    assert result['converged'] and base['converged'] and base['residual']<plan['gates']['base']
    fresh=float(np.max(abs(system.residual(np.zeros(system.size),np.zeros(system.size)))));assert fresh<plan['gates']['base']
    r=np.asarray([n['position'] for n in nodes]);q=np.asarray([n['rotation'] for n in nodes])
    s=np.asarray([n['jig_position'][2 if job['orientation']=='upright' else 1] for n in nodes])
    lengths=np.diff(s);assert abs(sum(lengths)-.55)<1e-12 and .52 in [n['t'] for n in nodes]
    cg=r-.005*q[:,:,0];lump=np.zeros(len(s));lump[:-1]+=.6787*lengths/2;lump[1:]+=.6787*lengths/2
    f=lump[:,None]*[0.,0.,-9.81];moment=np.cross(cg,f).sum(axis=0)
    checks=dict(fresh_residual=fresh,force_balance=float(np.max(abs(np.asarray(base['force_balance'])))),
        moment_balance=float(np.max(abs(np.asarray(base['moment_balance'])))),
        gravity_force=float(np.max(abs(np.asarray(base['applied_force'])-f.sum(axis=0)))),
        gravity_moment=float(np.max(abs(np.asarray(base['applied_moment'])-moment))),
        clamp_position=float(np.max(abs(r[0]))),clamp_rotation=float(np.max(abs(q[0]-np.eye(3)))))
    assert max(checks.values())<1e-7
    spectrum=spectrum_evidence([r['eigenvalue'] for r in result['modes']]);assert spectrum['distinct'] and spectrum['positive_enough'] and spectrum['unique_conjugates']
    common.write(folder/'spectrum.json',spectrum);audits=[]
    for mode in result['modes']:
        lam=complex(*mode['eigenvalue']);audit=dict(index=mode['index'])
        for side in ('right','left'):
            v=np.asarray(mode[side]['real'])+1j*np.asarray(mode[side]['imag'])
            av,mv=(a@v,m@v) if side=='right' else (v.conjugate()@a,v.conjugate()@m)
            error=float(np.linalg.norm(av-lam*mv)/(np.linalg.norm(av)+abs(lam)*np.linalg.norm(mv)))
            assert error<plan['gates']['pencil'];audit[side]=error
        audit['neutral_relative']=abs(lam.real)/max(1.,abs(lam.imag));assert audit['neutral_relative']<plan['gates']['neutral_relative']
        audits.append(audit)
    rows=[];shapes=[];archives=[]
    for ordinal,k in enumerate(spectrum['selected_indices']):
        mode=result['modes'][k];freq=mode['eigenvalue'][1]/(2*np.pi);target=c['targets'][ordinal]
        v=np.asarray(mode['right']['real'])+1j*np.asarray(mode['right']['imag']);geometry=v[:6*len(nodes)].reshape(-1,6)
        displacement=system.L*geometry[:,:3]+np.cross(geometry[:,3:],-.005*q[:,:,0])
        shapes.append(np.column_stack((displacement,geometry[:,3:])))
        rows.append(dict(ordinal=ordinal+1,mode_index=mode['index'],frequency_Hz=freq,expected_Hz=target['frequency_modulus_Hz'],
            error_percent=100*abs(freq/target['frequency_modulus_Hz']-1)))
        for axis,component in enumerate(('real','imaginary')):
            ref=target[component];error=abs(Decimal.from_float(float(mode['eigenvalue'][axis]))-Decimal(ref['exact_decimal_expected']))
            archives.append(dict(ordinal=ordinal+1,component=component,predicted=mode['eigenvalue'][axis],
                expected_token=ref['expected_token'],passed=error<=Decimal(ref['exact_decimal_tolerance']),absolute_error=float(error)))
    np.savez_compressed(folder/'shapes.npz',stations=s,shapes=np.asarray(shapes),rotations=q,cg=cg)
    common.authenticate(plan['pins'])
    report=dict(observed_utc=common.utc(),job=job,checks=checks,pencil_audits=audits,frequencies=rows,strict_archive_components=archives,
        tip_position=r[-1].tolist(),tip_CG=cg[-1].tolist(),seconds=seconds,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        plan_sha256=common.sha(out/'plan.json'),artifacts={p.name:common.sha(p) for p in folder.iterdir()})
    common.write(folder/'report.json',report);print(dict(job=job,frequencies=rows,seconds=seconds,peak_rss_kib=report['peak_rss_kib']))


def summarize(out):
    plan=common.read(out/'plan.json');common.authenticate(plan['pins'])
    import numpy as np
    from scipy.optimize import linear_sum_assignment
    from scipy.spatial.transform import Rotation,Slerp
    from isae_st2_loaded_reference import section_inertia
    grouped={}
    for i,job in enumerate(plan['jobs']):
        folder=out/f'job-{i}';report=common.read(folder/'report.json')
        assert report['job']==job and report['plan_sha256']==common.sha(out/'plan.json')
        for p,h in report['artifacts'].items():assert common.sha(folder/p)==h
        with np.load(folder/'shapes.npz') as z:shape={k:z[k] for k in z.files}
        grouped.setdefault(job['orientation'],{})[job['nodes']]=(report,shape)
    rows=[];mesh=[];paper=[];classifications=[]
    for orientation,grids in grouped.items():
        frame=np.array([[1,0,0],[0,0,-1],[0,1,0]]) if orientation=='upright' else np.eye(3)
        fine,fs=grids[160];grid=np.linspace(0.,.55,501)
        rotations=Slerp(fs['stations'],Rotation.from_matrix(fs['rotations']))(grid).as_matrix()@frame
        factors=np.array([np.linalg.cholesky(section_inertia(s,q,1.23)) for s,q in zip(grid,rotations)]);factors[[0,-1]]*=np.sqrt(.5)
        def sample(shape):return np.asarray([np.column_stack([np.interp(grid,shape['stations'],v[:,i]) for i in range(6)]) for v in shape['shapes']])
        def match(left,right):
            a=np.einsum('ngi,gij->ngj',sample(left),factors).reshape(7,-1);b=np.einsum('ngi,gij->ngj',sample(right),factors).reshape(7,-1)
            scores=abs(a.conj()@b.T)**2/np.outer(np.sum(abs(a)**2,axis=1),np.sum(abs(b)**2,axis=1))
            rr,cc=linear_sum_assignment(-scores);assert np.array_equal(rr,np.arange(7))
            return cc,scores[rr,cc]
        for coarse_nodes,fine_nodes in ((40,80),(80,160)):
            cr,cs=grids[coarse_nodes];fr,ss=grids[fine_nodes];assignment,mac=match(ss,cs)
            for i in range(7):
                change=abs(cr['frequencies'][i]['frequency_Hz']/fr['frequencies'][i]['frequency_Hz']-1)
                mesh.append(dict(orientation=orientation,coarse_nodes=coarse_nodes,fine_nodes=fine_nodes,ordinal=i+1,
                    frequency_change_percent=100*change,shape_MAC=float(mac[i]),ordinal_assignment=int(assignment[i])+1,
                    passed=bool(assignment[i]==i and mac[i]>plan['gates']['shape_MAC'] and change<plan['gates']['mesh_relative'])))
        # Independent family classification uses physical local CG displacement
        # and rotation, with source distributed mass and rotary inertia.
        sampled=sample(fs);u=np.einsum('nji,mnj->mni',rotations,sampled[:,:,:3]);rot=np.einsum('nji,mnj->mni',rotations,sampled[:,:,3:])
        inn=4.2793e-4+np.maximum(0.,(grid-.52)/.03)*(.0041-4.2793e-4)
        weights=np.ones(len(grid));weights[[0,-1]]=.5
        activity=np.stack((np.sum(weights*(.6787*abs(u[:,:,2])**2+6.9567e-5*abs(rot[:,:,0])**2),axis=1),
            np.sum(weights*(.6787*abs(u[:,:,0])**2+inn*abs(rot[:,:,2])**2),axis=1),
            np.sum(weights*(6.9567e-5+inn)*abs(rot[:,:,1])**2,axis=1),np.sum(weights*.6787*abs(u[:,:,1])**2,axis=1)),axis=1)
        fractions=activity/activity.sum(axis=1)[:,None];family=np.argmax(fractions,axis=1);orders={}
        for i,item in enumerate(fine['frequencies']):
            name=('OOP','IP','T','A')[family[i]];orders[name]=orders.get(name,0)+1;label=name+str(orders[name])
            classifications.append(dict(orientation=orientation,ordinal=i+1,label=label,activity_fractions=dict(zip(('OOP','IP','T','A'),fractions[i].tolist()))))
            expected_label=LABELS[i];classified=label==expected_label and fractions[i,family[i]]>.55
            m=next(x for x in mesh if x['orientation']==orientation and x['coarse_nodes']==80 and x['ordinal']==i+1)
            coarse=grids[80][0]['frequencies'][i]
            passed=item['error_percent']<=5 and coarse['error_percent']<=5 and m['passed'] and classified
            rows.append(dict(orientation=orientation,**item,label=label,coarse_error_percent=coarse['error_percent'],
                mesh_passed=m['passed'],family_identified=bool(classified),passed=bool(passed)))
            if label in PAPER[orientation]:
                expected=PAPER[orientation][label];error=100*abs(item['frequency_Hz']/expected-1)
                paper.append(dict(orientation=orientation,label=label,expected_Hz=expected,predicted_Hz=item['frequency_Hz'],error_percent=error,passed=bool(error<=5 and passed)))
    summary=dict(observed_utc=common.utc(),required=14,passed=sum(r['passed'] for r in rows),rows=rows,mesh_checks=mesh,
        classifications=classifications,paper_cross_checks=paper,production_equations_changed=False,archive_passes_added=0,
        source_models_modified=False,full_ST2_validated=False)
    common.write(out/'summary.json',summary);print({k:v for k,v in summary.items() if k not in ('mesh_checks','classifications')})


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=('prepare','run','summarize'));p.add_argument('--output',type=Path,required=True);p.add_argument('--index',type=int)
    a=p.parse_args()
    if a.action=='prepare':prepare(a.output)
    else:
        common.bounded()
        if a.action=='run':run(a.output,a.index)
        else:summarize(a.output)


if __name__=='__main__':main()
