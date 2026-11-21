"""SA-11 drag at matched lift; every observed root and unresolved scan interval is retained."""
from pathlib import Path
import argparse, fcntl, hashlib, importlib.util, json, sys, time
import numpy as np
from scipy.optimize import brentq

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'scripts'))
from isae_sa11_reference import sha, REVISION, NAMES
spec=importlib.util.spec_from_file_location('sa11',ROOT/'scripts/verify-isae-sa11.py')
sa11=importlib.util.module_from_spec(spec); spec.loader.exec_module(sa11)
DEST=ROOT/'docs/validation'


class RejectedState(Exception):
    def __init__(self,row): self.row=row; super().__init__(row['error'])


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--case',choices=NAMES); args=parser.parse_args()
    sources=json.loads((DEST/'isae-sa11-sources.json').read_text())
    modules={p.name:sha(p) for p in (ROOT/'openswing').glob('*.py')}
    native_provenance=dict(revision=REVISION,modules=modules,script_sha256=sha(ROOT/'scripts/verify-isae-sa11.py'),
        reference_script_sha256=sha(ROOT/'scripts/isae_sa11_reference.py'),source_report_sha256=sha(DEST/'isae-sa11-sources.json'))
    native_id=hashlib.sha256(json.dumps(native_provenance,sort_keys=True).encode()).hexdigest()
    native_folder=ROOT/'.reference/isae-sa11-runs'/native_id
    assert json.loads((native_folder/'identity.json').read_text())==native_provenance
    identity=dict(native_provenance=native_provenance,script_sha256=sha(Path(__file__)))
    folder=ROOT/'.reference/isae-sa11-drag'/hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    folder.mkdir(parents=True,exist_ok=True)
    manifest=folder/'identity.json'
    if manifest.exists(): assert json.loads(manifest.read_text())==identity
    else:manifest.write_text(json.dumps(identity,indent=2)+'\n')
    rows=[];scans=[];summary=[]
    for case in sa11.case_entries(sources):
        if not case['has_experimental_reference'] or (args.case and args.case!=case['name']):continue
        sound=float(sa11.parse_asw(case['source']).constants[2])
        for mach,data in sources['experimental'].items():
            speed=float(mach)*sound
            for panels in [50,100]:
                scan_id=f"{case['case_id']}_M{mach}_N{panels}"
                angles=sorted(set([-1.]+np.linspace(0,10,41).tolist()+[r['xy'][0] for r in data['lift'][case['name']]['values']]))
                known={};scan=[]
                for alpha in angles:
                    request=sa11.specification(case,panels,speed,alpha)
                    path=native_folder/(sa11.request_key(request)+'.json')
                    if not path.exists():raise FileNotFoundError(f'Native scan is not ready: {request}. Resume after its pinned worker produces this entry.')
                    row=json.loads(path.read_text());assert row['specification']==request
                    row.update(cache_path=path.relative_to(ROOT).as_posix(),cache_sha256=sha(path));known[alpha]=row
                    scan.append(dict(alpha=alpha,status=row['status'],CL=row.get('result',{}).get('CL'),
                        error=row.get('error'),cache_path=row['cache_path'],cache_sha256=row['cache_sha256']))
                scans.append(dict(id=scan_id,case=case['case_id'],nominal_mach=float(mach),speed=speed,panels=panels,rows=scan))

                def evaluate(alpha):
                    if alpha in known:return known[alpha]
                    request=sa11.specification(case,panels,speed,alpha)
                    path=folder/('state-'+sa11.request_key(request)+'.json')
                    with path.with_suffix('.lock').open('a') as lock:
                        fcntl.flock(lock,fcntl.LOCK_EX)
                        if path.exists():
                            row=json.loads(path.read_text());assert row['specification']==request
                        else:
                            start=time.monotonic()
                            try:row=dict(specification=request,status='computed',result=sa11.compute(case['source'],request))
                            except sa11.AnalysisError as exc:row=dict(specification=request,status='rejected',error=str(exc),details=getattr(exc,'details',None))
                            row['seconds']=time.monotonic()-start
                            temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(row,indent=2)+'\n');temporary.replace(path)
                    row.update(cache_path=path.relative_to(ROOT).as_posix(),cache_sha256=sha(path));known[alpha]=row
                    return row

                for measurement in data['drag'][case['name']]['values']:
                    target,measured=measurement['xy']
                    request=dict(case=case['case_id'],nominal_mach=float(mach),speed=speed,panels=panels,
                        csv_row=measurement['row'],target_CL=target,measured_CD=measured,scan_id=scan_id)
                    path=folder/('point-'+hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest()+'.json')
                    with path.with_suffix('.lock').open('a') as lock:
                        fcntl.flock(lock,fcntl.LOCK_EX)
                        if path.exists():
                            row=json.loads(path.read_text());assert row['request']==request
                        else:
                            roots=[];failed=[];gaps=[]
                            def function(alpha):
                                state=evaluate(float(alpha))
                                if state['status']=='rejected':raise RejectedState(state)
                                return float(state['result']['CL']-target)
                            def add(alpha,bracket):
                                if any(abs(alpha-r['alpha'])<1e-8 for r in roots):return
                                state=evaluate(float(alpha));residual=state['result']['CL']-target
                                assert abs(residual)<=5e-8
                                roots.append(dict(alpha=float(alpha),bracket=bracket,lift_error=residual,
                                    result=state['result'],cache_path=state['cache_path'],cache_sha256=state['cache_sha256']))
                            for alpha in angles:
                                if known[alpha]['status']=='computed' and abs(known[alpha]['result']['CL']-target)<=1e-10:add(alpha,[alpha,alpha])
                            for left,right in zip(angles[:-1],angles[1:]):
                                a,b=known[left],known[right]
                                if a['status']!='computed' or b['status']!='computed':
                                    gaps.append([left,right]);continue
                                if (a['result']['CL']-target)*(b['result']['CL']-target)<0:
                                    try:
                                        root=brentq(function,left,right,xtol=1e-11,rtol=1e-12,maxiter=100);add(root,[left,right])
                                    except RejectedState as exc:
                                        failed.append(dict(bracket=[left,right],rejected_state=exc.row))
                            row=dict(request=request,roots=sorted(roots,key=lambda r:r['alpha']),failed_brackets=failed,
                                unresolved_scan_intervals=gaps,complete_sampled_scan=not(gaps or failed),
                                coverage='All sign-changing adjacent converged samples from -1 to10degrees, including the exact experimental lift angles. Failed intervals are not bridged; no extrapolation. Unsampled folds/tangencies and other solution branches remain possible.')
                            temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(row,indent=2)+'\n');temporary.replace(path)
                    row.update(cache_path=path.relative_to(ROOT).as_posix(),cache_sha256=sha(path));rows.append(row)
                group=[r for r in rows if r['request']['scan_id']==scan_id]
                single=[r for r in group if len(r['roots'])==1]
                complete=[r for r in single if r['complete_sampled_scan']]
                def errors(selected,offset=0.):
                    if not selected:return dict(count=0,rmse=None,bias=None,maximum_absolute_error=None)
                    values=np.array([r['roots'][0]['result']['CD']+offset-r['request']['measured_CD'] for r in selected])
                    return dict(count=len(values),rmse=float(np.sqrt(np.mean(values**2))),bias=float(values.mean()),maximum_absolute_error=float(max(abs(values))))
                summary.append(dict(scan_id=scan_id,case=case['case_id'],nominal_mach=float(mach),panels=panels,
                    requested=len(group),single_observed_root=len(single),multiple_observed_roots=sum(len(r['roots'])>1 for r in group),
                    no_observed_root=sum(not r['roots'] for r in group),unresolved_scan_intervals=len(group[0]['unresolved_scan_intervals']),
                    complete_single_root_scan=len(complete),raw_CD_observed_single_root=errors(single),raw_CD_complete_single_root=errors(complete),
                    documented_offset_CD_observed_single_root=errors(single,sources['postprocessing']['drag_offsets'][mach])))
                print('DONE',scan_id,'requests',len(group),'roots',sum(len(r['roots']) for r in group),'unresolved scan intervals',len(group[0]['unresolved_scan_intervals']),flush=True)
    assert modules=={p.name:sha(p) for p in (ROOT/'openswing').glob('*.py')}
    report=dict(status='PARTIAL_MATCHED_LIFT_COMPARISON',identity=identity,rows=rows,scans=scans,summary=summary,
        limitations=['A single observed root is not a unique physical solution when the sampled curve has failed intervals, or outside the sampled branches/range.',
            'Raw predictions retain input reference quantities and section properties. Primary normalization and apparatus differences remain unresolved.',
            'Fixed .0064/.0075 CD offsets are reported separately solely as documented ISAE display transformations; they are not solver output or a fit.',
            'Every observed root and unresolved interval is retained. Multiple roots are not reduced by choosing the closest drag.'])
    if args.case:
        (folder/('precompute-'+args.case+'.json')).write_text(json.dumps(report,indent=2)+'\n')
    else:
        native=DEST/'isae-sa11.json';native_report=json.loads(native.read_text())
        assert native_report['provenance']==native_provenance and native_report['total']==5304
        assert len(rows)==166
        report['identity']['study_sha256']=sha(native)
        (DEST/'isae-sa11-drag.json').write_text(json.dumps(report,indent=2)+'\n')
    print('COMPLETE',len(rows),'requests;',sum(len(r['roots']) for r in rows),'observed roots;',folder,flush=True)


if __name__=='__main__':main()
