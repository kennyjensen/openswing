"""SA-7/8 literal tandem and fore-only polar comparisons, without fitting.

The independent SA-7 series is experimental total lift; SA-8 is CFD total lift
with the airframe. Other digitized series are not silently substituted.
"""
from pathlib import Path
import csv
import hashlib
import json
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from openswing.asw import parse_asw
from openswing.aero import FlightCondition,solve_rigid,AnalysisError


def stats(pairs):
    error=np.asarray([a-b for a,b in pairs])
    return dict(count=len(error),bias=float(error.mean()),rmse=float(np.sqrt(np.mean(error**2))),maximum_absolute_error=float(max(abs(error)))) if len(error) else None


def main():
    revision='f62943df20e9e4d7d9f50e070477b22426b5f865'
    cache=ROOT/'.reference/isae-validation'/revision
    manifest=json.loads((cache.parent/'manifest.json').read_text())
    modules={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'openswing').glob('*.py'))}
    identity=dict(modules=modules,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),revision=revision)
    directory=ROOT/'.reference/isae-tandem-runs'/hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    directory.mkdir(parents=True,exist_ok=True)
    models=[]
    for number in [7,8]:
        folder=next(cache.glob(f'1 - Aerodynamics/SA*/SA - {number} - *'))
        for source in sorted(folder.rglob('*.asw')):
            model=parse_asw(source.read_text())
            assert not model.diagnostics
            fore_only='Fore_Only' in source.name
            speed=69.15 if number==7 and fore_only else (70. if number==7 else 30.)
            reference=source.with_suffix('.txt')
            assert 'span eff.' in reference.read_text()
            table=np.loadtxt(reference)
            assert table.shape[1]==10
            used=[source,reference,source.with_suffix('.sh')]
            independent=[]; label=None
            if not fore_only:
                filename='NASA_Tandem_l163_g05.csv' if number==7 else 'Airframe_impact.csv'
                path=next(folder.rglob(filename));used.append(path)
                csvrows=list(csv.reader(path.read_text().splitlines()))
                column=0 if number==7 else 4
                label='Experiment_Total_l163_g05' if number==7 else 'CFD_w_airframe_total'
                assert csvrows[0][column]==label
                independent=[[float(r[column]),float(r[column+1])] for r in csvrows[2:] if len(r)>column+1 and r[column] and r[column+1]]
            sources={p.relative_to(cache).as_posix():manifest['files'][p.relative_to(cache).as_posix()] for p in used}
            for path in used:
                assert hashlib.sha256(path.read_bytes()).hexdigest()==sources[path.relative_to(cache).as_posix()]['sha256']
            cases=[];comparisons=[];lookup={}
            def run(alpha,panels,frozen,mach):
                spec=dict(source=source.relative_to(cache).as_posix(),alpha=float(alpha),panels=panels,freeze_influences=frozen,mach=mach,speed=speed)
                key=json.dumps(spec,sort_keys=True)
                if key in lookup:return cases[lookup[key]]
                saved=directory/(hashlib.sha256(key.encode()).hexdigest()+'.json')
                if saved.exists():
                    row=json.loads(saved.read_text());assert row['specification']==spec
                else:
                    start=time.monotonic()
                    try:
                        result=solve_rigid(model,FlightCondition(speed=speed,alpha=alpha,density=1.2256,mach=mach,freeze_influences=frozen),panels=panels)
                        assert result['converged'] and result['residual']<1e-8
                        row=dict(specification=spec,status='computed',result={k:float(result[k]) for k in ['CL','CD','Cm','CDi','CDp','residual']})
                    except AnalysisError as exc:
                        row=dict(specification=spec,status='rejected',error=str(exc))
                    row['seconds']=time.monotonic()-start
                    saved.write_text(json.dumps(row,indent=2)+'\n')
                lookup[key]=len(cases);cases.append(row)
                return row
            for frozen in [False,True]:
                for mach in [0.,None]:
                    for panels in [50,100]:
                        for row in table:run(row[2],panels,frozen,mach)
                        print(f'SA-{number} {source.stem} frozen={frozen} mach={mach} N={panels}',flush=True)
                    rows=[run(r[2],100,frozen,mach) for r in table]
                    external=[run(alpha,100,frozen,mach) for alpha,value in independent]
                    comparisons.append(dict(freeze_influences=frozen,mach=mach,panels=100,
                        aswing=dict(requested=len(rows),computed=sum(r['status']=='computed' for r in rows),
                            errors={k:stats([(r['result'][k],ref[col]) for r,ref in zip(rows,table) if r['status']=='computed']) for k,col in [('CL',5),('CD',6),('Cm',8),('CDi',7)]}),
                        independent=dict(label=label,requested=len(external),computed=sum(r['status']=='computed' for r in external),
                            CL_errors=stats([(r['result']['CL'],ref[1]) for r,ref in zip(external,independent) if r['status']=='computed'])),
                        mesh_change={k:stats([(run(r[2],100,frozen,mach)['result'][k],run(r[2],50,frozen,mach)['result'][k]) for r in table
                            if run(r[2],100,frozen,mach)['status']==run(r[2],50,frozen,mach)['status']=='computed']) for k in ['CL','CD','Cm']}))
            models.append(dict(case=number,source=source.relative_to(cache).as_posix(),sources=sources,reference=model.reference.tolist(),
                archived_aswing=table.tolist(),independent_reference=dict(label=label,points=independent),cases=cases,comparisons=comparisons))
    result=dict(status='LITERAL_TANDEM_COMPARISONS_NOT_FULL_VALIDATION',full_suite_validated=False,provenance=identity,models=models,
        settings=dict(meshes=[50,100],density=1.2256),limitations=[
            'Each archived model is unchanged, including the SA-7 fore-only model, whose geometry and section parameters differ from the tandem model canard. No surface is substituted or rescaled.',
            'SA-7 independent comparisons use the explicitly labeled experimental total lift CSV pair. SA-8 uses the explicitly labeled CFD total with airframe pair, not an experiment. Per-surface and drag-at-fixed-lift measurements remain pending.',
            'PG and K/F startup states are unknown; both choices are reported. Exact original node/interval placement, geometry and experimental reductions are not recovered.',
            'Two finite meshes are a sensitivity check, not continuum convergence or full validation. Rejected solves are counted and never interpolated or replaced.'])
    (ROOT/'docs/validation/isae-tandem.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
