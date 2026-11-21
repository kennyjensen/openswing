"""Bounded serial modal comparison of all parseable original ST-4 models."""
import argparse
from decimal import Decimal
import importlib.util
from pathlib import Path
import resource
import time

import verify_sa14_defaults as common
import isae_st4_mechanics as source
import isae_suite_modes as archive

ROOT=common.ROOT


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def prepare(out):
    import numpy as np
    from openswing.asw import parse_asw
    manifest=common.read(ROOT/'reference/isae-validation/manifest.json');assert manifest['revision']==source.REVISION
    files=[p for p in source.CASE.rglob('*') if p.is_file() and p.suffix in ('.asw','.txt','.sh','.m','.xlsx','.csv')]
    for p in files:assert common.sha(p)==manifest['files'][p.relative_to(source.CACHE).as_posix()]['sha256']
    files += [*sorted((ROOT/'openswing').glob('*.py')),Path(__file__),ROOT/'scripts/isae_st4_mechanics.py',
        ROOT/'scripts/isae_suite_modes.py',ROOT/'scripts/verify_sa14_defaults.py',
        ROOT/'scripts/verify-isae-st4-transfer-current.py',ROOT/'scripts/isae_st4_transfer.py',
        ROOT/'tests/test_isae_st4_mechanics.py',ROOT/'reference/aswing_doc.txt',
        ROOT/'docs/validation/aswing-authoritative-references.md',ROOT/'docs/validation/aswing-authoritative-sources.json']
    for e in common.read(ROOT/'docs/validation/aswing-authoritative-sources.json')['files']:
        if e['id'] in ('isae-part-3','drela-steady','drela-unsteady'):
            for field,key in [('local_pdf','sha256'),('local_text','text_sha256')]:
                p=ROOT/e[field];assert common.sha(p)==e[key];files.append(p)
    inventory=[];models={};jobs=[]
    for p in sorted(source.MODELS.rglob('*.asw')):
        text=p.read_text();record=dict(path=p.relative_to(ROOT).as_posix(),id=p.stem)
        try:m=parse_asw(text)
        except Exception as e:record.update(status='parse_rejected',error=str(e));inventory.append(record);continue
        assert m.dumps()==text and len(m.beams)==1 and not m.diagnostics
        b=m.beams[0];assert tuple(b.domain)==(.0001,1.2192)
        np.testing.assert_allclose(b.position([.0001,1.2192]),[[0,0,0],[0,0,1.2192]],rtol=0,atol=1e-14)
        np.testing.assert_array_equal(m.records['ground'],[[1,.0001,0]])
        fields={k:float(b.value(k,.5)) for k in ('EIcc','GJ','mg','mgcc','mgnn','Cea','Ccg')}
        for k,v in dict(EIcc=41.1744*9.81,GJ=20.2506*9.81,mg=1.2947*9.81,mgnn=0.,Cea=.437*.2032,Ccg=.454*.2032).items():assert abs(fields[k]-v)<1e-12
        assert abs(fields['mgcc']/9.81-(.0035 if p.parent.name=='Weight7b' else .0078))<1e-14
        for k in ('EInn','GKc','GKn','EA'):assert np.isinf(b.value(k,.5))
        points=[list(map(float,[r[5]/9.81,r[1],r[2],r[3],r[4]])) for r in m.records['weight']]
        assert len(points)==2 and all(.0001<=r[1]<=1.2192 and r[0]>=0 for r in points)
        record.update(status='executable',properties=fields,points=points,raw_weights=[r.tolist() for r in m.records['weight']])
        inventory.append(record);models[p.stem]=record
    assert len(inventory)==33 and len(models)==32
    # Start with exact direct-export controls, then execute every other original model.
    ordered=['7a_b17','WING','7d_b33','7f_b40']+[k for k in models if k not in ('7a_b17','WING','7d_b33','7f_b40')]
    for name in ordered:
        for n in (64,128):jobs.append(dict(model=name,panels=n))
    paper=[]
    for row,(name,position,*values) in enumerate(source.PAPER,1):
        assert name in models
        for label,token in zip(source.LABELS,values,strict=True):
            number=Decimal(token)
            paper.append(dict(row=row,model=name,position_token=position,label=label,raw_token=token,
                expected=float(number),original_absolute_tolerance=float(Decimal(5)*Decimal(10)**(number.as_tuple().exponent-1)),
                qualification=source.QUALIFICATIONS.get(name,'')))
    assert len(paper)==72
    aggregates={name:archive._aggregate(source.CASE/name) for name in ('Modal_analysis.xlsx','Eigen_data_save.csv')}
    direct={}
    for directory in archive.VARIANTS:
        p=source.MODELS/directory;driver=archive.decode_driver((p/'Flutter_analysis.sh').read_text())
        direct[Path(driver['model']).stem]=archive.decode_table((p/'vaccum.txt').read_text(),True)
    out.mkdir(parents=True,exist_ok=True)
    common.write(out/'plan.json',dict(observed_utc=common.utc(),pins={p.relative_to(ROOT).as_posix():common.sha(p) for p in files},
        inventory=inventory,models=models,jobs=jobs,paper=paper,aggregate_targets=aggregates,direct_exports=direct,
        required_paper_cells=72,reference_relative=.05,mesh_relative=.001,shape_MAC=.99,pencil_gate=1e-8,
        limits=dict(blas_threads=1,address_space_mib=512,cpu_seconds=15,wall_seconds=25),
        protocol='All32 parseable original ST-4 files, unchanged, fixed-frame vacuum with zero gravity and unloaded geometry, '
        'following the pre-OPER MODE convention. Native initial toggle and historical settings remain unknown. '
        'Source fixed-vacuum endpoint operator; nominal64/128 cosine grids with exact weight stations,16 roots near(-.1,300). '
        'All72 Table6 ASWING frequency cells retained, mapped to declared original models before solving. '
        'Mode labels use first-three elastic-energy dominance; no nearest-target assignment. '
        'Workbook/CSV and five direct exports are separate overlapping diagnostics, not additional primary votes. '
        'Paper position conflicts, missing W0 identity, malformed W0M and missing45in input stay explicit. '
        'No full-family, complete-spectrum, experimental, gravity-loaded or airflow claim.'))
    print('Prepared64 serial states,72 published paper targets; all original sources retained.')


def run(out,index):
    plan=common.read(out/'plan.json');common.authenticate(plan['pins']);job=plan['jobs'][index];model=plan['models'][job['model']]
    folder=out/f'job-{index:02d}';folder.mkdir()
    import numpy as np
    from scipy.sparse import save_npz
    from openswing.bridge import dispatch
    from openswing import linear_dynamics as dynamics
    request=dict(action='modes',mode='modes',source=(ROOT/model['path']).read_text(),condition=None,
        panels=dict(default=job['panels'],beams={'1':dict(count=job['panels'],spacing='cosine')}),
        numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator='drela-fixed-vacuum-v1'),
        modes=dict(frame='fixed',vacuum=True,count=16,shift=[-.1,300.],method='full_shift_invert',
            position=[0.,0.,0.],attitude=[0.,0.,0.],gravity_magnitude=0.,matrices=False))
    common.write(folder/'request.json',request);held=[];original=dynamics.linearize
    def capture(system,*args,**kwargs):
        a,m=original(system,*args,**kwargs);held.append((system,a,m));save_npz(folder/'A.npz',a);save_npz(folder/'M.npz',m);return a,m
    dynamics.linearize=capture;started=time.monotonic()
    try:result=dispatch(request)
    finally:dynamics.linearize=original
    seconds=time.monotonic()-started;common.write(folder/'result.json',result);assert len(held)==1
    system,a,m=held[0];base=result['base'];nodes=base['nodes'];n=len(nodes)
    assert system.size==18*n and system.network.ng==0 and result['vacuum'] and result['frame_mode']=='fixed'
    assert base['gravity_body']==[0.,0.,0.] and result['converged'] and base['converged']
    s=np.array([v['jig_position'][2] for v in nodes]);q=np.array([v['rotation'] for v in nodes]);r=np.array([v['position'] for v in nodes])
    points=np.asarray(model['points']);mass=1.2947*1.2192+sum(points[:,0])
    first=1.2947*1.2192*np.array([.454*.2032,0.,1.2192/2])+np.sum(points[:,0,None]*points[:,2:5],axis=0)
    checks=dict(base_residual=base['residual'],fresh_residual=float(np.max(abs(system.residual(np.zeros(system.size),np.zeros(system.size))))),
        zero_force=float(np.max(abs(np.asarray(base['applied_force'])))),zero_moment=float(np.max(abs(np.asarray(base['applied_moment'])))),
        undeformed=float(np.max(abs(r-np.array([v['jig_position'] for v in nodes])))),rotation=float(np.max(abs(q-np.eye(3)))),
        total_mass=abs(base['mass_properties']['mass']-mass),first_moment=float(np.max(abs(np.asarray(base['mass_properties']['first_moment'])-first))))
    assert max(checks.values())<1e-7,checks
    audits=[];values=np.asarray([complex(*mode['eigenvalue']) for mode in result['modes']]);assert len(values)==16
    for mode,lam in zip(result['modes'],values,strict=True):
        assert sum(abs(values-lam)<1e-8*max(1,abs(lam)))==1
        audit=dict(index=mode['index'],neutral_relative=float(abs(lam.real)/max(1.,abs(lam.imag))))
        assert audit['neutral_relative']<1e-8
        vectors={}
        for side in ('left','right'):
            v=np.asarray(mode[side]['real'])+1j*np.asarray(mode[side]['imag']);vectors[side]=v
            av,mv=(a@v,m@v) if side=='right' else (v.conjugate()@a,v.conjugate()@m)
            error=float(np.linalg.norm(av-lam*mv)/(np.linalg.norm(av)+abs(lam)*np.linalg.norm(mv)))
            assert error<plan['pencil_gate'];audit[side]=error
        audit['mass_pairing']=float(abs(np.vdot(vectors['left'],m@vectors['right'])-1))
        assert audit['mass_pairing']<1e-8;audits.append(audit)
    positive=sorted([mode for mode in result['modes'] if mode['eigenvalue'][1]>1e-6],key=lambda mode:mode['eigenvalue'][1]);assert len(positive)>=3
    shapes=[];fractions=[];frequencies=[]
    for mode in positive[:3]:
        v=np.asarray(mode['right']['real'])+1j*np.asarray(mode['right']['imag']);geometry=v[:6*n].reshape(n,6)
        shape=np.column_stack((geometry[:,:3],geometry[:,3:]));shapes.append(shape)
        dtheta=np.diff(geometry[:,3:],axis=0);ds=np.diff(s)
        bending=model['properties']['EIcc']*np.sum(abs(dtheta[:,0])**2/ds)
        torsion=model['properties']['GJ']*np.sum(abs(dtheta[:,2])**2/ds)
        assert bending+torsion>0;fractions.append(float(torsion/(bending+torsion)))
        frequencies.append(mode['eigenvalue'][1]/(2*np.pi))
    classification=source.classify(fractions)
    np.savez_compressed(folder/'shapes.npz',stations=s,shapes=np.asarray(shapes))
    # Independent six-state equations, including Eq80 and both exact point jumps.
    helper=load(ROOT/'scripts/verify-isae-st4-transfer-current.py','st4_current_transfer')
    verified,witness=helper.roots(lambda f:helper.discrete_boundary(f,model['points'],s,rotary=model['properties']['mgcc']/9.81),frequencies)
    transfer_error=float(np.max(abs(verified/np.asarray(frequencies)-1)))
    assert transfer_error<1e-7
    common.authenticate(plan['pins'])
    report=dict(observed_utc=common.utc(),job=job,checks=checks,pencil_audits=audits,classification=classification,
        positive_frequencies_Hz=[mode['eigenvalue'][1]/(2*np.pi) for mode in positive],frequencies_Hz=frequencies,
        independent_discrete_frequencies_Hz=verified.tolist(),independent_transfer_relative=transfer_error,transfer_witnesses=witness,
        solver_seconds=seconds,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        plan_sha256=common.sha(out/'plan.json'),artifacts={p.name:common.sha(p) for p in folder.iterdir()})
    common.write(folder/'report.json',report)
    print(dict(index=index,**job,frequencies_Hz=frequencies,classification=classification,seconds=seconds,transfer_error=transfer_error),flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run']);p.add_argument('--output',type=Path,required=True);p.add_argument('--index',type=int)
    a=p.parse_args();common.bounded()
    if a.action=='prepare':prepare(a.output)
    else:run(a.output,a.index)


if __name__=='__main__':main()
