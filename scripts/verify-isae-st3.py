"""Literal ST-3 modal study with independent beam and primary-source checks.

No material fitting, legacy-file repair or changed numerical tolerance. Gravity,
small positive airspeed and solver settings are explicitly separate studies.
Matrices are assembled once per operating point and reused for both root searches.
"""
from pathlib import Path
import argparse,hashlib,json,sys,time
import numpy as np
from scipy.optimize import linear_sum_assignment

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.linear_dynamics import make_system,linearize,eigensystem,complex_data
from isae_st3_reference import MATERIALS,LENGTH,ICC,INN,modes,weighted_shapes,assurance,branch_labels

REVISION='f62943df20e9e4d7d9f50e070477b22426b5f865'
FOLDER='3 - Structure/CASE - ST3 Low aspect ratio'
CACHE=ROOT/'.reference/isae-validation'/REVISION


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def pins():return {p.name:sha(p) for p in sorted((ROOT/'openswing').glob('*.py'))}
def source_path(name):return FOLDER+'/Vaccum_anaysis/['+name+'].asw'


def inspect_model(text,name):
    model=parse_asw(text);b=model.beams[0];p=MATERIALS[name];t=np.array([.0001,.27905,.558])
    assert len(model.beams)==1 and not model.diagnostics and b.domain==(.0001,.558)
    assert model.dumps()==text
    expected=dict(EIcc=p['EI'],GJ=p['GJ'],EIcs=p['coupling'],EIcn=0.,EIsn=0.,EA=1.132e7,
        mg=p['mass']*9.81,mgcc=ICC*9.81,mgnn=INN*9.81,chord=.14,
        Cea=p['offset'],Cta=p['offset'],Ccg=p['offset'],Nea=0.,Nta=0.,Ncg=0.,twist=0.)
    for field,value in expected.items():np.testing.assert_allclose(b.value(field,t),value,rtol=2e-15,atol=1e-15)
    np.testing.assert_allclose(b.value('EInn',t),np.inf if p['EInn']==0 else p['EInn'])
    np.testing.assert_allclose(b.position([.0001,.558]),[[0,0,0],[0,0,LENGTH]])
    assert not model.records.get('weight') and not model.records.get('engine')
    return model,expected


def compute(text,spec):
    model,_=inspect_model(text,spec['name'])
    condition=None if spec['speed']==0 else FlightCondition(speed=spec['speed'],alpha=0,beta=0,density=1.23,mach=0,stall=False)
    start=time.perf_counter()
    system,steps=make_system(model,condition,panels=spec['panels'],gravity=[0,0,-spec['gravity']],structured_base=True)
    a,m=linearize(system,step=spec['step'])
    base=system.base_report();assert base['residual']<1e-8
    searches=[]
    for shift in ([[-.1,0.],[-.3,180.]] if condition is None else [[-.1,100.],[-.3,180.]]):
        roots,diagnostics=eigensystem(a,m,time_scale=system.W,count=10,shift=shift,method=spec['method'],rank_tolerance=spec.get('rank_tolerance',1e-9))
        physical=[]
        for root in roots:
            assert max(root['right_backward_error'],root['left_backward_error'])<1e-9
            lam=complex(*root['eigenvalue'])
            if lam.imag<=2*np.pi*.5:continue
            shape=root['right'][:6*system.network.nn].reshape(-1,6).copy();shape[:,:3]*=system.L
            physical.append(dict(eigenvalue=root['eigenvalue'],frequency_Hz=lam.imag/(2*np.pi),shape=complex_data(shape),
                right_backward_error=root['right_backward_error'],left_backward_error=root['left_backward_error']))
        searches.append(dict(shift=shift,diagnostics=diagnostics,roots=physical))
    return dict(specification=spec,seconds=time.perf_counter()-start,base=base,
        jig_positions=system.network.rj.tolist(),searches=searches,
        assembly=dict(matrices=2,searches=len(searches),reuse='The same physical A and M are used for both eigenvalue searches.'))


def physical_shapes(rows,name):
    shapes=[]
    for row in rows:
        q=np.array(row['shape']['real'])+1j*np.array(row['shape']['imag'])
        shapes.append(np.column_stack([q[:,1]+MATERIALS[name]['offset']*q[:,5],-q[:,3],q[:,5]]))
    return np.asarray(shapes)


def match(run,reference):
    spec=run['specification'];name=spec['name'];positions=np.asarray(run['jig_positions'])[:,2]
    reference_shapes=weighted_shapes(reference['nodes'],reference['shapes'][:3],MATERIALS[name]['mass'])
    labels=reference['labels'][:3]
    matched=[]
    for search in run['searches']:
        rows=search['roots'];shape=physical_shapes(rows,name)
        matrix=assurance(reference_shapes,weighted_shapes(positions,shape,MATERIALS[name]['mass']))
        ir,ic=linear_sum_assignment(-matrix);assert list(ir)==[0,1,2]
        selected=[]
        for i,j in zip(ir,ic):
            assert matrix[i,j]>.9,(spec,labels[i],matrix[i,j])
            selected.append(dict(label=labels[i],root_index=int(j),frequency_Hz=rows[j]['frequency_Hz'],
                eigenvalue=rows[j]['eigenvalue'],shape_assurance=float(matrix[i,j]),
                independent_frequency_Hz=reference['frequencies_Hz'][i],
                relative_reference_error=rows[j]['frequency_Hz']/reference['frequencies_Hz'][i]-1))
        matched.append(dict(shift=search['shift'],modes=selected))
    for a,b in zip(matched[0]['modes'],matched[1]['modes']):
        assert abs(a['frequency_Hz']/b['frequency_Hz']-1)<1e-7,(spec,a,b)
    return matched


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--meshes',default='8,16,32,64');parser.add_argument('--output',type=Path,default=ROOT/'docs/validation/isae-st3.json');parser.add_argument('--no-air',action='store_true');args=parser.parse_args()
    modules=pins();script_sha=sha(Path(__file__));ref_sha=sha(ROOT/'scripts/isae_st3_reference.py')
    manifest=json.loads((ROOT/'.reference/isae-validation/manifest.json').read_text());meshes=[int(n) for n in args.meshes.split(',')]
    sources={source_path(name):manifest['files'][source_path(name)] for name in MATERIALS}
    inputs={name:(CACHE/source_path(name)).read_text() for name in MATERIALS}
    for name in MATERIALS:assert sha(CACHE/source_path(name))==sources[source_path(name)]['sha256'];inspect_model(inputs[name],name)
    refs={name:{str(g):[modes(name,n,g,count=5) for n in [48,96,192]] for g in [0.,9.81]} for name in MATERIALS}
    branches={name:{str(g):branch_labels(name,g) for g in [0.,9.81]} for name in MATERIALS}
    for name in refs:
        for g,rows in refs[name].items():
            for row in rows:row['labels']=branches[name][g]['labels']
    specs=[dict(name=name,panels=n,gravity=g,speed=0.,step=1e-5,method='full_shift_invert') for name in MATERIALS for g in [0.,9.81] for n in meshes]
    if not args.no_air:specs += [dict(name=name,panels=n,gravity=9.81,speed=speed,step=1e-5,method='full_shift_invert') for name in MATERIALS for speed in [.1,.01] for n in [16,32]]
    specs += [dict(name=name,panels=n,gravity=g,speed=0.,step=step,method=method) for name in MATERIALS for n,g,step,method in [(8,0.,1e-5,'dense'),(16,9.81,3e-6,'full_shift_invert')]]
    specs += [dict(name=name,panels=8,gravity=0.,speed=0.,step=1e-5,method='dense',rank_tolerance=rank) for name in MATERIALS for rank in [1e-11,1e-12]]
    for spec in specs:spec.setdefault('rank_tolerance',1e-9)
    cache=ROOT/'.reference/isae-st3-runs';cache.mkdir(parents=True,exist_ok=True);runs=[]
    for spec in specs:
        identity=dict(specification=spec,modules=modules,script_sha256=script_sha,reference_script_sha256=ref_sha,source_sha256=sources[source_path(spec['name'])]['sha256'])
        key=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest();file=cache/(key+'.json')
        if file.exists():row=json.loads(file.read_text());assert row['identity']==identity
        else:
            try:
                result=compute(inputs[spec['name']],spec)
                result['matches']=match(result,refs[spec['name']][str(spec['gravity'])][-1])
                row=dict(identity=identity,status='computed',result=result)
            except (ValueError,AssertionError) as exc:row=dict(identity=identity,status='rejected',error=type(exc).__name__+': '+str(exc))
            assert pins()==modules;file.write_text(json.dumps(row,indent=2)+'\n')
        runs.append(row);print(spec,row['status'],row.get('error',row.get('result',{}).get('seconds')),flush=True)
    report=dict(status='PARTIAL_MODAL_COMPARISON',full_suite_validated=False,
        provenance=dict(modules=modules,script_sha256=script_sha,reference_script_sha256=ref_sha,revision=REVISION,sources=sources,
            primary_sources_sha256=sha(ROOT/'docs/validation/isae-st3-sources.json')),
        references=refs,branch_tracking=branches,runs=runs,settings=dict(meshes=meshes,gravity=[0,9.81],air_density=1.23,air_speeds=[.1,.01] if not args.no_air else [],source_files='Unchanged literal inputs'),
        limitations=['Structural modes do not complete ST-3 static-deflection validation.',
            'ISAE and primary mode labels conflict; primary labels for coupled shapes are approximate.',
            'Finite positive speeds are a still-air-limit sensitivity, not an exact zero-flow solve.',
            'Mass/stiffness/axis properties differ between input files, report tables and primary plate model.',
            'The independent reference neglects tiny finite axial shortening; its air-free comparison is separate from air-loaded predictions.',
            'No experimental parameters are fitted. Mesh/root checks do not establish experimental agreement.'])
    args.output.write_text(json.dumps(report,indent=2)+'\n');print('WROTE',args.output,flush=True)


if __name__=='__main__':main()
