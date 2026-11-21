"""Audit v2 physical preservation, historical reproduction and scaled numerics.

No native equilibrium/tangent runs and no monkeypatching. The historical pencil
assembly is compiled verbatim from the archived function's AST for comparison.
The archived candidate remains an immutable source/data archive.
"""
import argparse
import ast
import copy
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import zipfile

import numpy as np
from scipy.linalg import eigh, eig, solve
from scipy.optimize import linear_sum_assignment
import durrant_unloaded_reference as reference

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    data=Path(path).read_bytes()
    return json.loads(gzip.decompress(data) if str(path).endswith('.gz') else data)


def arrays(actual,expected):
    a,b=np.asarray(actual),np.asarray(expected)
    if a.shape!=b.shape:raise ValueError('Array dimensions differ')
    return float(np.max(abs(a-b)/np.maximum(1.,abs(b)),initial=0.))


def historical_assembly(source):
    module=ast.parse(source)
    function=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='solve')
    branch=next(n for n in function.body if isinstance(n,ast.If) and ast.unparse(n.test)=='speed == 0')
    statements=branch.orelse
    begin=next(i for i,n in enumerate(statements) if isinstance(n,ast.Assign) and ast.unparse(n.targets[0])=='(Gq, Gv, L)')
    end=next(i for i,n in enumerate(statements) if isinstance(n,ast.Assign) and ast.unparse(n.targets[0])=='(roots, v)')
    body=copy.deepcopy(statements[begin:end])
    original_dump=ast.dump(ast.Module(body=body,type_ignores=[]),include_attributes=False)
    template=ast.parse('def historical_pencil(beam,aero,basis,values,speed,density,lag,take):\n return A,B\n')
    template.body[0].body=body+template.body[0].body
    namespace={'np':np}
    exec(compile(ast.fix_missing_locations(template),'<archived-physical-pencil>','exec'),namespace)
    return namespace['historical_pencil'],hashlib.sha256(original_dump.encode()).hexdigest()


def root_comparison(expected,actual):
    a,b=np.asarray(expected),np.asarray(actual)
    a=a[:,0]+1j*a[:,1];b=b[:,0]+1j*b[:,1]
    if len(a)!=len(b):raise ValueError('Full-spectrum dimensions differ')
    rows,cols=linear_sum_assignment(abs(a[:,None]-b[None,:]))
    absolute=abs(a[rows]-b[cols]);scaled=absolute/np.maximum(1.,np.maximum(abs(a[rows]),abs(b[cols])))
    low=[int(i) for i in rows if .1<a[i].imag/(2*np.pi)<40]
    worst=int(np.argmax(scaled))
    return dict(maximum_absolute_difference_per_s=float(absolute.max()),maximum_scaled_difference=float(scaled.max()),
        worst_expected=[float(a[rows[worst]].real),float(a[rows[worst]].imag)],
        worst_actual=[float(b[cols[worst]].real),float(b[cols[worst]].imag)],
        low_modes=[dict(expected=[float(a[i].real),float(a[i].imag)],actual=[float(b[cols[i]].real),float(b[cols[i]].imag)],
                        absolute_difference_per_s=float(absolute[i]),scaled_difference=float(scaled[i])) for i in low])


def spectrum(result):
    a=np.asarray(result['roots_per_s'])
    return dict(total_roots=len(a),maximum_real_part_per_s=float(a[:,0].max()),
        strictly_positive_real_part_count=int(np.sum(a[:,0]>0)),
        positive_above_1e_minus8_threshold_count=int(np.sum(a[:,0]>1e-8)),
        nonoscillatory_count_at_1e_minus8_threshold=int(np.sum(abs(a[:,1])<=1e-8)),
        positive_nonoscillatory_roots_per_s=a[(a[:,0]>1e-8)&(abs(a[:,1])<=1e-8)].tolist())


def reference_call(module,spec,scaling=None):
    kw=dict(elements=spec['mechanical_elements'],panels=spec['aero_panels'],density=spec['density_kg_m3'],
            lag=spec['aero_lag'],retain=spec['retained_modes'],shapes=True,sampling=spec['sampling'])
    if scaling is not None:kw['eigensystem_scaling']=scaling
    return module.solve(spec['wing'],spec['speed_m_s'],**kw)


def historical_errors(actual,expected):
    result={k:arrays(actual[k],expected[k]) for k in ('roots_per_s','positive_roots_per_s','positive_frequencies_Hz','span_m')}
    for part in ('real','imag'):
        result['shape_'+part]=arrays([s[part] for s in actual['positive_shapes']],[s[part] for s in expected['positive_shapes']])
    if max(result.values())>=2e-12:raise ValueError('Historical unscaled reproduction failed original2e-12 tolerance')
    return result


def pencil_checks(spec, historical_pencil):
    beam=reference.mechanics(spec['wing'],elements=spec['mechanical_elements'],density=spec['density_kg_m3'],sampling=spec['sampling'],panels=spec['aero_panels'])
    aero=reference.aerodynamics(beam,spec['aero_panels'],sampling=spec['sampling'])
    values,basis=eigh(beam['K'],beam['M']+beam['Ma'])
    take=len(values) if spec['retained_modes']==0 else min(len(values),spec['retained_modes'])
    values,basis=values[:take],basis[:,:take]
    params=(beam,aero,basis,values,spec['speed_m_s'],spec['density_kg_m3'],spec['aero_lag'])
    A,B=reference.modal_pencil(*params)
    oldA,oldB=historical_pencil(*params,take)
    if not np.array_equal(A,oldA) or not np.array_equal(B,oldB):raise ValueError('Physical pencil changed')
    widths=np.diff(aero['edges']) if spec['aero_lag'] else []
    R,E,w0=reference.eigensystem_coordinates(values,spec['speed_m_s'],beam['common']['chord_m'],spec['density_kg_m3'],widths)
    As,Bs=E[:,None]*A*R[None,:]/w0,E[:,None]*B*R[None,:]
    C=solve(Bs,As)
    ordinary,v=eig(C)
    generalized,_,diagnostics=reference.pencil_eigensystem(A,B,values,spec['speed_m_s'],beam['common']['chord_m'],spec['density_kg_m3'],widths)
    comparison=root_comparison(np.c_[generalized.real,generalized.imag],np.c_[ordinary.real*w0,ordinary.imag*w0])
    if comparison['maximum_scaled_difference']>=2e-7:raise ValueError('Standard-matrix cross-check exceeds existing2e-7 portability tolerance')
    residual=np.linalg.norm(As@v-(Bs@v)*ordinary,axis=0)/((np.linalg.norm(As,2)+abs(ordinary)*np.linalg.norm(Bs,2))*np.linalg.norm(v,axis=0))
    if residual.max()>=1e-9:raise ValueError('Standard-route pencil residual exceeds original1e-9 threshold')
    return dict(dimension=len(A),original_A_bitwise_equal=True,original_B_bitwise_equal=True,
        A_sha256=hashlib.sha256(A.tobytes()).hexdigest(),B_sha256=hashlib.sha256(B.tobytes()).hexdigest(),
        scaled_B_condition_2=float(np.linalg.cond(Bs)),standard_route_comparison=comparison,
        maximum_standard_route_pencil_error=float(residual.max()),diagnostics=diagnostics)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results',type=Path,default=ROOT/'docs/validation/durrant-unloaded-results')
    parser.add_argument('--archive',type=Path,default=ROOT/'candidate-history/integration-v1.zip')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise ValueError('Use a fresh audit output')
    run=read(args.results/'run.json')
    if run['status']!='computed' or len(run['cases'])!=12:raise ValueError('Incomplete12-case replay')
    for name,value in run['invocation']['source_sha256'].items():
        if name!='native_structure_helper' and sha(ROOT/name)!=value:raise ValueError('Replay sources changed')
    report=dict(status='running',cases=[],api_checks=[])
    def save():args.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    with tempfile.TemporaryDirectory(prefix='durrant-v1-audit-') as temporary:
        oldroot=Path(temporary)
        with zipfile.ZipFile(args.archive) as archive:
            manifest=json.loads(archive.read('ARCHIVE-MANIFEST.json'))
            if set(archive.namelist())!=set(manifest)|{'ARCHIVE-MANIFEST.json'}:raise ValueError('Archive membership changed')
            for name,value in manifest.items():
                if Path(name).is_absolute() or '..' in Path(name).parts:raise ValueError('Invalid archive path')
                content=archive.read(name)
                if hashlib.sha256(content).hexdigest()!=value:raise ValueError('Archive source/data hash changed')
                p=oldroot/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(content)
        spec=importlib.util.spec_from_file_location('archived_v1_reference',oldroot/'scripts/durrant_unloaded_reference.py')
        old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
        historical_pencil,assembly_hash=historical_assembly((oldroot/'scripts/durrant_unloaded_reference.py').read_text())
        physical_functions=('properties','grid','fields','mechanics','horseshoe_influence','aerodynamics')
        def functions(path):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef)}
        old_ast,new_ast=functions(oldroot/'scripts/durrant_unloaded_reference.py'),functions(Path(reference.__file__))
        if any(old_ast[n]!=new_ast[n] for n in physical_functions):raise ValueError('Physical assembly function AST changed')
        report.update(physical_functions_AST_unchanged=list(physical_functions),historical_pencil_AST_sha256=assembly_hash)
        for name,entry in run['native_cases'].items():
            if sha(args.results/entry['file'])!=entry['sha256']:raise ValueError('Saved native hash changed')
            if (args.results/entry['file']).read_bytes()!=(oldroot/'docs/validation/durrant-unloaded-results'/entry['file']).read_bytes():raise ValueError('Saved native result is not byte-identical')
        for entry in run['cases']:
            if entry['status']!='computed' or sha(args.results/entry['file'])!=entry['sha256']:raise ValueError('Replay case is invalid')
            current=read(args.results/entry['file']);s=current['spec'];result=current['reference']
            archived=read(oldroot/'docs/validation/durrant-unloaded-results'/entry['file'])['reference']
            unscaled=reference_call(reference,s,'unscaled')
            errors=historical_errors(unscaled,archived)
            matrices={}
            old_beam=old.mechanics(s['wing'],elements=s['mechanical_elements'],density=s['density_kg_m3'],sampling=s['sampling'],panels=s['aero_panels'])
            new_beam=reference.mechanics(s['wing'],elements=s['mechanical_elements'],density=s['density_kg_m3'],sampling=s['sampling'],panels=s['aero_panels'])
            old_aero=old.aerodynamics(old_beam,s['aero_panels'],sampling=s['sampling']);new_aero=reference.aerodynamics(new_beam,s['aero_panels'],sampling=s['sampling'])
            for label,a,b,keys in [('beam',new_beam,old_beam,['nodes','K','M','Ma','D_per_speed']),('aero',new_aero,old_aero,['edges','W','P','V','L'])]:
                for key in keys:
                    if not np.array_equal(a[key],b[key]):raise ValueError('Physical matrix changed')
                    matrices[label+'.'+key]=dict(bitwise_equal=True,sha256=hashlib.sha256(a[key].tobytes()).hexdigest())
            check=pencil_checks(s,historical_pencil)
            if not all(p['resolved_assignment'] for c in current['comparisons'] for p in c['pairs']):raise ValueError('Low-mode native assignment is ambiguous')
            report['cases'].append(dict(id=entry['id'],spec=s,unscaled_reproduction_errors=errors,physical_matrices=matrices,
                pencil=check,scaled_minus_archived=root_comparison(archived['roots_per_s'],result['roots_per_s']),
                archived_spectrum=spectrum(archived),scaled_spectrum=spectrum(result),native_comparisons=current['comparisons']))
            save();print(entry['id'],'historical reproduction / physical matrices / standard eig passed',flush=True)
        base=dict(wing='25',speed_m_s=24.,mechanical_elements=8,aero_panels=8,density_kg_m3=1.225,sampling='glauert_all')
        extra=[dict(base,aero_lag=lag,retained_modes=keep) for lag,keep in [(True,12),(False,0),(False,12)]]
        extra.append(dict(base,aero_lag=True,retained_modes=12,density_kg_m3=0.))
        for s in extra:
            a=reference_call(old,s);b=reference_call(reference,s,'unscaled');c=reference_call(reference,s,'energy_convective')
            report['api_checks'].append(dict(spec=s,unscaled_reproduction_errors=historical_errors(b,a),
                scaled_spectrum=spectrum(c),scaled_minus_unscaled=root_comparison(b['roots_per_s'],c['roots_per_s']),pencil=pencil_checks(s,historical_pencil)))
            save()
        for keep in (0,12):
            s=dict(base,aero_lag=True,retained_modes=keep,speed_m_s=0.)
            a=reference_call(old,s)
            for scaling in reference.EIGENSYSTEM_SCALINGS:
                b=reference_call(reference,s,scaling)
                report['api_checks'].append(dict(spec=s,scaling=scaling,zero_speed_physical_results_unchanged=historical_errors(b,a)))
                save()
    report.update(status='verified',recorded=time.time(),full_reference_roots=sum(c['scaled_spectrum']['total_roots'] for c in report['cases']),
        exact_physical_matrix_blocks=sum(len(c['physical_matrices']) for c in report['cases']),exact_original_pencils=len(report['cases'])+len(extra),
        saved_native_cases_reused_byte_identically=3,new_native_calculations=0,
        hashes={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),Path(reference.__file__),ROOT/'scripts/verify-durrant-unloaded.py',args.archive,args.results/'run.json']},
        scope='Physical matrices and historical unscaled outputs preserved; scaled reference/standard eig agreement verified, distinct from physical convergence or experimental validation.')
    save()
    print(json.dumps({k:v for k,v in report.items() if k not in ('cases','api_checks','hashes')},indent=2))


if __name__=='__main__':main()
