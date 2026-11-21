"""Run bounded unloaded-wing reference plans and optional native comparisons.

Independent calculations use no production modules. Native work requires an
explicit --kernel-root. --native saved audits pinned completed native records;
--native compute performs the same unloaded calculation on that checkout.
Outputs are atomic per-case records. Resume checks process identity, hashes,
plan, mode, and every completed artifact before reusing work.
"""
import argparse
import gzip
import hashlib
import json
import os
import platform
import re
import sys
import time
import traceback
from pathlib import Path
import numpy as np
import scipy
from scipy.optimize import linear_sum_assignment
import durrant_unloaded_reference as reference

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    raw=Path(path).read_bytes()
    return json.loads(gzip.decompress(raw) if str(path).endswith('.gz') else raw)


def atomic_json(path,data):
    raw=(json.dumps(data,indent=2,allow_nan=False)+'\n').encode()
    if str(path).endswith('.gz'):
        raw=gzip.compress(raw,mtime=0)
    temporary=path.with_name(path.name+'.part')
    with temporary.open('wb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())
    temporary.replace(path)
    return sha(path)


def identity(pid):
    try:
        fields=Path(f'/proc/{pid}/stat').read_text().split(')',1)[1].split()
        if fields[0]=='Z':
            return None
        return dict(pid=pid,start_ticks=int(fields[19]),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    except FileNotFoundError:
        return None


def plan_cases(plan):
    if set(plan)-{'schema','description','cases','saved_native'} or plan.get('schema')!=1:
        raise ValueError('Expected bounded study plan schema1.')
    cases=plan.get('cases',[])
    if not isinstance(cases,list) or not 1<=len(cases)<=32:
        raise ValueError('A plan must contain1–32 explicit cases.')
    out=[];ids=set();native_specs={}
    for raw in cases:
        allowed={'id','wing','speed_m_s','mechanical_elements','aero_panels','sampling',
                 'density_kg_m3','aero_lag','retained_modes','native_id','eigensystem_scaling'}
        if not isinstance(raw,dict) or set(raw)-allowed:
            raise ValueError('Unknown case fields.')
        spec={**dict(density_kg_m3=1.225,aero_lag=True,retained_modes=0,
                     eigensystem_scaling='energy_convective'),**raw}
        if not re.fullmatch('[a-z0-9][a-z0-9_-]{0,63}',spec.get('id','')) or spec['id'] in ids or spec['id'].startswith('native-'):
            raise ValueError('Case IDs must be unique simple filenames without the reserved native- prefix.')
        ids.add(spec['id'])
        if spec.get('wing') not in ['25','75'] or spec.get('sampling') not in reference.SAMPLING:
            raise ValueError('Unknown material reconstruction or sampling choice.')
        if spec['eigensystem_scaling'] not in reference.EIGENSYSTEM_SCALINGS:
            raise ValueError('Unknown eigensystem scaling.')
        for key in ['mechanical_elements','aero_panels']:
            if type(spec.get(key)) is not int or not 2<=spec[key]<=128:
                raise ValueError('Requested mechanical/aerodynamic grid counts must be2–128.')
        for key,lo,hi in [('speed_m_s',0.,100.),('density_kg_m3',0.,10.)]:
            if type(spec.get(key)) not in (int,float) or not np.isfinite(spec[key]) or not lo<spec[key]<=hi:
                raise ValueError('Speed and density must be finite, positive, and within bounded study limits.')
        if type(spec['aero_lag']) is not bool or type(spec['retained_modes']) is not int or not 0<=spec['retained_modes']<=640:
            raise ValueError('Lag must be boolean and retained modes an integer0–640 (0 means all).')
        if 'native_id' in spec:
            name=spec['native_id']
            if not isinstance(name,str) or not re.fullmatch('[a-z0-9][a-z0-9_-]{0,63}',name):
                raise ValueError('Invalid native case ID.')
            native=dict(wing=spec['wing'],speed_m_s=spec['speed_m_s'],panels=spec['aero_panels'],
                        density_kg_m3=spec['density_kg_m3'],aero_lag=spec['aero_lag'])
            if name in native_specs and native_specs[name]!=native:
                raise ValueError('A native case ID cannot refer to different physical settings.')
            native_specs[name]=native
        out.append(spec)
    return out,native_specs


def compare(reference_case,native,search=0):
    """One-to-one physical shape assignment in the explicit .1–40Hz window."""
    ri=[i for i,w in enumerate(reference_case['positive_frequencies_Hz']) if .1<w<40.]
    rm=[(complex(*reference_case['positive_roots_per_s'][i]),reference_case['positive_shapes'][i]) for i in ri]
    nm=[(complex(*row['eigenvalue_per_s']),row['mechanical_shape'])
        for row in native['searches'][search]['modes'] if .1<row['frequency_Hz']<40.]
    if not rm or not nm:
        return dict(status='no_matched_window',frequency_window_Hz=[.1,40.],pairs=[])
    xr=np.asarray(reference_case['span_m']);xn=np.asarray(native['jig_positions'])[:,2]
    grid=np.unique(np.r_[xr,xn]);ds=np.diff(grid)
    chord=reference.properties(reference_case['wing'])[0]['chord_m']
    metric=np.sqrt(np.r_[ds[0],ds[:-1]+ds[1:],ds[-1]][:,None]/2)*[1.,1.,1.,chord,chord,chord]
    def vector(shape,x):
        values=np.asarray(shape['real'])+1j*np.asarray(shape['imag'])
        values=np.stack([np.interp(grid,x,values[:,j]) for j in range(6)],axis=1)
        values=(values*metric).ravel()
        return values/np.linalg.norm(values)
    vr=np.asarray([vector(shape,xr) for _,shape in rm]);vn=np.asarray([vector(shape,xn) for _,shape in nm])
    mac=abs(vr.conj()@vn.T)**2
    rows,cols=linear_sum_assignment(1-mac);pairs=[]
    for i,j in zip(rows,cols):
        r,n=rm[i][0],nm[j][0]
        rmargin=float(mac[i,j]-np.max(np.delete(mac[i],j),initial=0.))
        nmargin=float(mac[i,j]-np.max(np.delete(mac[:,j],i),initial=0.))
        pairs.append(dict(reference_root_per_s=[r.real,r.imag],native_root_per_s=[n.real,n.imag],
            modal_assurance=float(mac[i,j]),reference_margin=rmargin,native_margin=nmargin,
            resolved_assignment=bool(mac[i,j]>.8 and rmargin>.1 and nmargin>.1),
            scaled_root_difference=float(abs(n-r)/max(1.,abs(r))),
            frequency_relative_difference=float(n.imag/r.imag-1),growth_difference_per_s=float(n.real-r.real)))
    return dict(status='compared',frequency_window_Hz=[.1,40.],pairs=pairs,
        unmatched_reference_roots_per_s=[[rm[i][0].real,rm[i][0].imag] for i in range(len(rm)) if i not in rows],
        unmatched_native_roots_per_s=[[nm[j][0].real,nm[j][0].imag] for j in range(len(nm)) if j not in cols])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True,help='Fresh output directory, or exact prior directory with --resume.')
    parser.add_argument('--native',choices=['none','saved','compute'],default='none')
    parser.add_argument('--kernel-root',type=Path)
    parser.add_argument('--case',action='append',default=[],help='Run only this explicit case ID; repeat to select several.')
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    plan=read_json(args.plan);cases,native_specs=plan_cases(plan)
    if args.case:
        if set(args.case)-{s['id'] for s in cases}:
            raise ValueError('Selected case is absent from the plan.')
        cases=[s for s in cases if s['id'] in args.case]
    if args.native!='none' and (args.kernel_root is None or any('native_id' not in s for s in cases)):
        raise ValueError('Native comparisons require --kernel-root and a native_id for every selected case.')
    sources={str(path.relative_to(ROOT)):sha(path) for path in [Path(__file__),
        ROOT/'scripts/durrant_unloaded_reference.py',ROOT/'scripts/durrant_unloaded_native.py',reference.REFERENCE]}
    kernel_hashes={};saved_pins={};native_adapter=None
    if args.native!='none':
        import durrant_unloaded_native as native_adapter
        kernel_root,unused=native_adapter.load_kernel(args.kernel_root)
        if sha(kernel_root/'docs/validation/durrant-reference.json')!=sha(reference.REFERENCE):
            raise ValueError('The explicit kernel material table differs from the independent table.')
        kernel_hashes={p.name:sha(p) for p in sorted((kernel_root/'openswing').glob('*.py'))}
        sources['native_structure_helper']=sha(kernel_root/'scripts/verify-durrant-structure.py')
    else:
        kernel_root=None
    for name in {s.get('native_id') for s in cases} if args.native=='saved' else []:
        pin=plan.get('saved_native',{}).get(name)
        if not isinstance(pin,dict) or set(pin)!={'record','record_sha256','terminal','terminal_sha256','log','log_sha256'}:
            raise ValueError('Saved native records require explicit record/terminal paths and hashes.')
        for key in ['record','terminal','log']:
            path=(args.plan.resolve().parent/pin[key]).resolve()
            if sha(path)!=pin[key+'_sha256']:
                raise ValueError('Pinned native artifact hash mismatch.')
        saved_pins[name]=pin
    invocation=dict(plan_sha256=sha(args.plan),selected_case_ids=[s['id'] for s in cases],
        native_mode=args.native,kernel_root=str(kernel_root) if kernel_root else None,
        source_sha256=sources,kernel_sha256=kernel_hashes,saved_pins=saved_pins)
    path=args.output/'run.json'
    if args.resume:
        record=read_json(path)
        if record['invocation']!=invocation:
            raise ValueError('Resume sources, plan, selection or native checkout changed.')
        if record['status']=='running' and identity(record['process']['pid'])==record['process']:
            raise ValueError('Recorded study process is still alive; do not restart it.')
        for item in record['cases']+list(record['native_cases'].values()):
            if sha(args.output/item['file'])!=item['sha256']:
                raise ValueError('Completed study artifact hash mismatch.')
        record.setdefault('resumes',[]).append(dict(observed=time.time(),previous_process=record['process']))
    else:
        args.output.mkdir(parents=True,exist_ok=False)
        record=dict(schema=1,status='running',started=time.time(),command=sys.argv,
            invocation=invocation,plan=plan,cases=[],native_cases={},
            versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),
            limitations=['Unloaded analogue, not published Case1 or loaded Case4.',
                'No fitted physics, material constants or post-hoc physical agreement thresholds.',
                'Native searches are local; independent full spectra and selected modal matches have distinct scopes.',
                'Packaged WASM/browser evidence is recorded separately; this native study does not claim those checks.'])
    record.update(process=identity(os.getpid()),status='running')
    def save(phase=None):
        if phase:record['phase']=phase
        record['updated']=time.time();atomic_json(path,record)
    def unchanged():
        current={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),ROOT/'scripts/durrant_unloaded_reference.py',
            ROOT/'scripts/durrant_unloaded_native.py',reference.REFERENCE]}
        if kernel_root:
            current['native_structure_helper']=sha(kernel_root/'scripts/verify-durrant-structure.py')
            if kernel_hashes!={p.name:sha(p) for p in sorted((kernel_root/'openswing').glob('*.py'))}:
                raise ValueError('Production sources changed during the study.')
        if current!=sources:
            raise ValueError('Study sources changed during the run.')
    save('self_checks')
    record['independent_self_checks']=reference.checks();save()
    for spec in cases:
        if any(row['id']==spec['id'] for row in record['cases']):continue
        unchanged();started=time.monotonic();save('reference_'+spec['id'])
        try:
            result=reference.solve(spec['wing'],spec['speed_m_s'],elements=spec['mechanical_elements'],
                panels=spec['aero_panels'],density=spec['density_kg_m3'],lag=spec['aero_lag'],
                retain=spec['retained_modes'],shapes=True,sampling=spec['sampling'],
                eigensystem_scaling=spec['eigensystem_scaling'])
            if result['maximum_backward_error']>=1e-9:
                raise ValueError('Independent original-pencil residual exceeds1e-9.')
            if any(result['eigensystem'].get(key,0.)>=1e-9 for key in
                   ['maximum_scaled_right_backward_error','maximum_scaled_left_backward_error']):
                raise ValueError('Independent scaled-pencil residual exceeds1e-9.')
            roots=np.asarray(result['roots_per_s'])
            case=dict(status='computed',spec=spec,reference=result,
                computed_reference_spectrum=dict(
                    all_mechanical_coordinates_retained=result['retained_mechanical_modes']==5*result['actual_elements'],
                    maximum_growth_per_s=float(roots[:,0].max()),
                    positive_growth_roots_per_s=roots[roots[:,0]>1e-8].tolist(),
                    positive_real_roots_per_s=roots[(abs(roots[:,1])<1e-8)&(roots[:,0]>1e-8)].tolist()))
            if args.native!='none':
                name=spec['native_id']
                if name not in record['native_cases']:
                    if args.native=='saved':
                        pin=saved_pins[name]
                        source_path=(args.plan.resolve().parent/pin['record']).resolve()
                        terminal=read_json((args.plan.resolve().parent/pin['terminal']).resolve())
                        raw=source_path.read_bytes();raw=gzip.decompress(raw) if source_path.suffix=='.gz' else raw
                        if terminal['exit_code']!=0 or hashlib.sha256(raw).hexdigest()!=terminal['output_sha256'] or terminal['log_sha256']!=pin['log_sha256']:
                            raise ValueError('Saved native terminal record does not prove this output.')
                        native=native_adapter.validate_saved(json.loads(raw),kernel_root,native_specs[name],kernel_hashes)
                        native['provenance']=dict(kind='saved_terminal_result',**pin)
                    else:
                        native=native_adapter.compute(kernel_root,native_specs[name],progress=save)
                        native['provenance']=dict(kind='computed',kernel_sha256=kernel_hashes)
                    filename='native-'+name+'.json.gz'
                    record['native_cases'][name]=dict(file=filename,sha256=atomic_json(args.output/filename,native))
                    save()
                native=read_json(args.output/record['native_cases'][name]['file'])
                case['comparisons']=[compare(result,native['native'],i) for i in range(len(native['native']['searches']))]
                case['native_id']=name
        except Exception as exc:
            case=dict(status='rejected',spec=spec,error=repr(exc),traceback=traceback.format_exc())
        unchanged();case['elapsed_s']=time.monotonic()-started
        filename=spec['id']+'.json.gz'
        record['cases'].append(dict(id=spec['id'],file=filename,status=case['status'],sha256=atomic_json(args.output/filename,case)))
        save();print(spec['id'],case['status'],flush=True)
    record.update(status='computed' if all(row['status']=='computed' for row in record['cases']) else 'contains_rejected_cases',ended=time.time())
    save('finished')
    if record['status']!='computed':raise SystemExit(1)


if __name__=='__main__':
    main()
