"""Fresh ST-3 frequency sets, full-pencil checks and shape/mesh verification.

Original model bytes and workbook cells are retained. Each run invocation
executes one bounded state; native modal labels remain unverified.
"""
import argparse
import importlib.util
from pathlib import Path
import resource
import time

import verify_sa14_defaults as common
import isae_suite_st3_modal as adapter

ROOT=common.ROOT


def load_file(path, name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def prepare(out):
    jobs=adapter.plan(ROOT)
    for job in jobs:
        # New evidence paths use the visible reference directory. The adapter's
        # canonical historical paths remain untouched in its source records.
        assert job['expected_outputs']==3
    paths=[Path(__file__),ROOT/'scripts/verify_sa14_defaults.py',
        ROOT/'scripts/isae_suite_st3_modal.py',ROOT/'scripts/isae_acceptance.py',
        ROOT/'scripts/run-isae-suite.py',ROOT/'scripts/summarize-isae-suite.py',
        ROOT/'scripts/isae_st3_reference.py',ROOT/'scripts/verify-isae-st3-still-air-reference.py',
        ROOT/'tests/test_isae_suite_st3_modal.py',ROOT/'docs/validation/isae-st3-sources.json',
        ROOT/'docs/validation/aswing-authoritative-references.md',
        ROOT/'docs/validation/aswing-authoritative-sources.json',
        ROOT/'reference/aswing_doc.txt',ROOT/'reference/isae-validation/manifest.json',
        *sorted((ROOT/'openswing').glob('*.py'))]
    pins={p.relative_to(ROOT).as_posix():common.sha(p) for p in paths}
    for job in jobs:
        for source in job['sources']:
            path=source['path'].replace('.reference/','reference/',1)
            assert common.sha(ROOT/path)==source['sha256'];pins[path]=source['sha256']
    for entry in common.read(ROOT/'docs/validation/aswing-authoritative-sources.json')['files']:
        if entry['id'] in ('isae-part-3','drela-steady','drela-unsteady'):
            for field,key in [('local_pdf','sha256'),('local_text','text_sha256')]:
                assert common.sha(ROOT/entry[field])==entry[key];pins[entry[field]]=entry[key]
    common.write(out/'plan.json',dict(observed_utc=common.utc(),jobs=jobs,pins=pins,
        required_unique_cells=9,mesh_repeated_slots=18,
        gates=dict(reference_relative=.05,mesh_relative=.001,shape_MAC=.99,
            pencil=1e-8,base=1e-8,neutral_relative=1e-8,conjugate_relative=1e-8),
        limits=dict(blas_threads=1,address_space_mib=512,cpu_seconds=15,wall_seconds=25),
        protocol='All three literal modal inputs, existing64/128 cosine grids, fixed upright self-weight, '
        'zero mean flow and source-density still air. First three positive roots by frequency from12 roots, '
        'no target-nearest pairing. Independent left/right original-pencil checks for every root, '
        'unique conjugate pairing, fresh equilibrium, independent gravity loads and physical-shape MAC. '
        'Strict recorded-precision results and5% reference views retained separately. Both meshes must pass. '
        'Disputed workbook labels and historical medium/grid/startup remain qualified.'))
    print('Prepared six bounded states for nine distinct workbook cells.')


def run(out,index):
    plan=common.read(out/'plan.json');common.authenticate(plan['pins']);job=plan['jobs'][index]
    folder=out/f'job-{index}';folder.mkdir()
    import numpy as np
    from scipy.sparse import save_npz
    from openswing.bridge import dispatch
    from openswing import linear_dynamics as dynamics
    from isae_st3_reference import MATERIALS, ICC, INN, LENGTH
    from isae_acceptance import apply_reference_acceptance
    source=(ROOT/job['model_path']).read_text()
    helper=load_file(ROOT/'scripts/verify-isae-st3-still-air-reference.py','st3_property_audit')
    properties=helper.verify_properties(source,job['layup'])
    request=adapter.request(job,source);common.write(folder/'request.json',request)
    held=[];original=dynamics.linearize
    def capture(system,*args,**kwargs):
        a,m=original(system,*args,**kwargs);held.append((system,a,m))
        save_npz(folder/'A.npz',a);save_npz(folder/'M.npz',m)
        return a,m
    dynamics.linearize=capture;started=time.monotonic()
    try:result=dispatch(request)
    finally:dynamics.linearize=original
    seconds=time.monotonic()-started;common.write(folder/'result.json',result)
    assert len(held)==1
    system,a,m=held[0];base=result['base'];nodes=base['nodes'];network=system.network
    assert system.size==18*len(nodes) and len(nodes)==job['nominal']+2 and network.ng==0
    fresh=float(np.max(abs(system.residual(np.zeros(system.size),np.zeros(system.size)))))
    runner=load_file(ROOT/'scripts/run-isae-suite.py','st3_current_runner')
    strict=runner.checked_result(job,adapter.assess_bridge(job,result,fresh,network.ng))
    assert strict['status']=='computed' and strict['numerical_pass']
    accepted=apply_reference_acceptance(strict,relative_tolerance=plan['gates']['reference_relative'])
    adapter.validated_strict_result(job,accepted)
    common.write(folder/'strict-result.json',strict);common.write(folder/'accepted-result.json',accepted)
    p=MATERIALS[job['layup']];r=np.asarray([n['position'] for n in nodes]);q=np.asarray([n['rotation'] for n in nodes])
    s=np.asarray([n['jig_position'][2] for n in nodes]);ds=np.diff(s)
    assert abs(ds.sum()-LENGTH)<1e-12 and np.all(ds>=0)
    cg=r+p['offset']*q[:,:,0];mass=np.zeros(len(nodes))
    mass[:-1]+=p['mass']*ds/2;mass[1:]+=p['mass']*ds/2
    forces=mass[:,None]*[0.,0.,-9.81];moment=np.cross(cg,forces).sum(axis=0)
    checks=dict(fresh_residual=fresh,force_balance=float(np.max(abs(np.asarray(base['force_balance'])))),
        moment_balance=float(np.max(abs(np.asarray(base['moment_balance'])))),
        independent_force=float(np.max(abs(forces.sum(axis=0)-base['applied_force']))),
        independent_moment=float(np.max(abs(moment-base['applied_moment']))),
        clamp_position=float(np.max(abs(r[0]))),clamp_rotation=float(np.max(abs(q[0]-np.eye(3)))))
    assert max(checks.values())<1e-7
    eigenvalues=np.asarray([complex(*mode['eigenvalue']) for mode in result['modes']])
    assert len(eigenvalues)==12 and np.sum(eigenvalues.imag>1e-6)==np.sum(eigenvalues.imag< -1e-6)==6
    partners=[];audits=[]
    for i,(mode,lam) in enumerate(zip(result['modes'],eigenvalues,strict=True)):
        close=np.flatnonzero(abs(eigenvalues-lam.conjugate())<=plan['gates']['conjugate_relative']*max(1.,abs(lam)))
        assert len(close)==1 and close[0]!=i;partners.append(int(close[0]))
        assert sum(abs(eigenvalues-lam)<=1e-8*max(1.,abs(lam)))==1
        audit=dict(index=mode['index'])
        for side in ('left','right'):
            vector=np.asarray(mode[side]['real'])+1j*np.asarray(mode[side]['imag'])
            av,mv=(a@vector,m@vector) if side=='right' else (vector.conjugate()@a,vector.conjugate()@m)
            error=float(np.linalg.norm(av-lam*mv)/(np.linalg.norm(av)+abs(lam)*np.linalg.norm(mv)))
            assert error<plan['gates']['pencil'];audit[side]=error
        audit['neutral_relative']=abs(lam.real)/max(1.,abs(lam.imag))
        assert audit['neutral_relative']<plan['gates']['neutral_relative'];audits.append(audit)
    assert all(partners[partners[i]]==i for i in range(12))
    selected=adapter.selected_modes(strict['numerical_evidence']);shapes=[]
    for selected_mode in selected:
        mode=next(m for m in result['modes'] if m['index']==selected_mode['index'])
        vector=np.asarray(mode['right']['real'])+1j*np.asarray(mode['right']['imag'])
        geometry=vector[:6*len(nodes)].reshape(-1,6)
        displacement=system.L*geometry[:,:3]+np.cross(geometry[:,3:],p['offset']*q[:,:,0])
        # Upright beam: normal CG motion is body y; theta_x=-h', theta_z=phi.
        shapes.append(np.column_stack((displacement[:,1],-geometry[:,3],geometry[:,5])))
    np.savez_compressed(folder/'shapes.npz',stations=s,shapes=np.asarray(shapes))
    common.authenticate(plan['pins'])
    report=dict(observed_utc=common.utc(),job=job,properties=properties,checks=checks,pencil_audits=audits,
        conjugate_partners=partners,frequencies=accepted['reference_checks'],
        seconds=seconds,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        plan_sha256=common.sha(out/'plan.json'),artifacts={p.name:common.sha(p) for p in folder.iterdir()})
    common.write(folder/'report.json',report)
    print(dict(layup=job['layup'],nominal=job['nominal'],frequencies=[r['predicted'] for r in report['frequencies']],
        strict_passed=strict['output_accounting']['passed'],passed=accepted['output_accounting']['passed'],
        seconds=seconds,peak_rss_kib=report['peak_rss_kib']))


def summarize(out):
    plan=common.read(out/'plan.json');common.authenticate(plan['pins'])
    import numpy as np
    from isae_st3_reference import MATERIALS,weighted_shapes,assurance
    summary_module=load_file(ROOT/'scripts/summarize-isae-suite.py','st3_current_summary')
    reports={};accepted_jobs=[];strict_jobs=[]
    for i,job in enumerate(plan['jobs']):
        folder=out/f'job-{i}';report=common.read(folder/'report.json')
        assert report['job']==job and report['plan_sha256']==common.sha(out/'plan.json')
        for p,h in report['artifacts'].items():assert common.sha(folder/p)==h
        with np.load(folder/'shapes.npz') as z:shape={k:z[k] for k in z.files}
        reports.setdefault(job['layup'],{})[job['nominal']]=(report,shape)
        accepted=common.read(folder/'accepted-result.json');strict=common.read(folder/'strict-result.json')
        assert summary_module.scalar_counts(dict(job,result=accepted))['passed']==sum(r['passed'] for r in accepted['reference_checks'])
        accepted_jobs.append(dict(job,result=accepted));strict_jobs.append(dict(job,result=strict))
    rows=[]
    for layup,grids in reports.items():
        coarse,cs=grids[64];fine,fs=grids[128];mass=MATERIALS[layup]['mass']
        matrix=assurance(weighted_shapes(cs['stations'],cs['shapes'],mass),weighted_shapes(fs['stations'],fs['shapes'],mass))
        assert np.array_equal(np.argmax(matrix,axis=1),np.arange(3))
        for i,(a,b) in enumerate(zip(coarse['frequencies'],fine['frequencies'],strict=True)):
            change=abs(a['predicted']/b['predicted']-1);mac=float(matrix[i,i])
            mesh_pass=change<=plan['gates']['mesh_relative'] and mac>=plan['gates']['shape_MAC']
            rows.append(dict(layup=layup,rank=i+1,cell=b['cell'],original_label=b['original_label'],
                expected=b['expected'],predicted=b['predicted'],coarse_predicted=a['predicted'],
                error_percent=b['error_percent'],mesh_change_percent=100*change,shape_MAC=mac,
                mesh_pass=bool(mesh_pass),strict_passed=a['strict_passed'] and b['strict_passed'] and bool(mesh_pass),
                passed=a['passed'] and b['passed'] and bool(mesh_pass)))
    audits=[a for grids in reports.values() for r,_ in grids.values() for a in r['pencil_audits']]
    report=dict(observed_utc=common.utc(),required=9,passed=sum(r['passed'] for r in rows),
        strict_passed=sum(r['strict_passed'] for r in rows),rows=rows,
        repeated_mesh_accounting=summary_module.totals(accepted_jobs),
        repeated_strict_accounting=summary_module.totals(strict_jobs),
        adapter_mesh_checks=summary_module.st3_modal_mesh_diagnostics(accepted_jobs),
        independent_pencil_checks=2*len(audits),maximum_pencil_residual=max(a[s] for a in audits for s in ('left','right')),
        maximum_neutral_relative=max(a['neutral_relative'] for a in audits),
        solver_seconds=sum(r['seconds'] for grids in reports.values() for r,_ in grids.values()),
        peak_rss_kib=max(r['peak_rss_kib'] for grids in reports.values() for r,_ in grids.values()),
        production_changed=False,native_modal_identity_verified=False,historical_settings_authenticated=False,
        full_family_validated=False,qualification='Same nine native workbook cells; frequency-set comparison at5%, strict precision retained. '
        'Both meshes, physical-shape correspondence and independent matrix residuals required. No new eigenvector identity or historical input setting claimed.')
    common.authenticate(plan['pins']);common.write(out/'summary.json',report)
    print({k:v for k,v in report.items() if k not in ('rows','adapter_mesh_checks')})


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run','summarize'])
    p.add_argument('--output',type=Path,required=True);p.add_argument('--index',type=int)
    args=p.parse_args();common.bounded()
    if args.action=='prepare':prepare(args.output)
    elif args.action=='run':run(args.output,args.index)
    else:summarize(args.output)


if __name__=='__main__':main()
