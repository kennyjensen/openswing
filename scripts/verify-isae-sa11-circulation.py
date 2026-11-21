"""SA-11 Fourier/mesh sensitivity; the archived mode counts are unknown."""
from pathlib import Path
from dataclasses import asdict
import hashlib, importlib.util, json, sys, time
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, solve_rigid, AnalysisError
from isae_sa11_reference import sha
spec=importlib.util.spec_from_file_location('sa11',ROOT/'scripts/verify-isae-sa11.py')
sa11=importlib.util.module_from_spec(spec);spec.loader.exec_module(sa11)


def run(case, request):
    if request['pg'] not in ('speed', 'zero'):
        raise ValueError('SA-11 circulation PG setting must be speed or zero.')
    if type(request['frozen']) is not bool:
        raise ValueError('SA-11 circulation frozen setting must be boolean.')
    model=parse_asw(case['source'])
    condition=FlightCondition(speed=request['speed'],alpha=request['alpha'],
        mach=0. if request['pg']=='zero' else None,
        freeze_influences=request['frozen'],
        circulation_modes={b.index:request['modes_per_beam'] for b in model.beams if b.lifting})
    applied_condition=asdict(condition)
    try:
        r=solve_rigid(model,condition,request['panels'])
    except AnalysisError as exc:
        row=dict(specification=request,applied_condition=applied_condition,
                 status='rejected',error=str(exc),details=getattr(exc,'details',None))
        if (row['details'] or {}).get('kind')=='section_normal_mach':
            trace=exc.__traceback__
            while trace is not None and trace.tb_frame.f_code.co_name!='evaluate_aerodynamics':trace=trace.tb_next
            assert trace is not None
            local=trace.tb_frame.f_locals
            row['weighted_residual']=float(local['error'])
            row['maximum_local_residual']=float(np.max(abs(local['local_residual'](local['gamma']))))
        return row
    assert r['aerodynamic_influences']['frozen'] is condition.freeze_influences
    return dict(specification=request,applied_condition=applied_condition,status='computed',result={k:r[k] for k in
        ['CL','CD','CDi','CDp','Cm','Cl','Cn','CY','residual','evaluations','circulation_solver','lifting_airflow',
         'aerodynamic_influences','circulation_discretization']},
        weighted_residual=float(r['residual']),maximum_local_residual=float(np.max(np.abs(r['circulation_local_residual']))),
        profiles=[{k:s[k] for k in ['beam','t','position','circulation','cl','normal_mach','force']} for s in r['strips']])


def main():
    source_path=ROOT/'docs/validation/isae-sa11-sources.json';sources=json.loads(source_path.read_text())
    modules={p.name:sha(p) for p in (ROOT/'openswing').glob('*.py')}
    identity=dict(modules=modules,script_sha256=sha(Path(__file__)),source_report_sha256=sha(source_path))
    folder=ROOT/'.reference/isae-sa11-circulation'/hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    folder.mkdir(parents=True,exist_ok=True);rows=[]
    (folder/'identity.json').write_text(json.dumps(identity,indent=2)+'\n')
    for case in sa11.case_entries(sources):
        if not case['has_experimental_reference']:continue
        for panels in [50,100]:
            for modes in [5,9,19]:
                for alpha in [0.,5.]:
                    request=dict(case=case['case_id'],panels=panels,modes_per_beam=modes,alpha=alpha,speed=240.,pg='speed',frozen=False)
                    path=folder/(hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest()+'.json')
                    if path.exists():
                        row=json.loads(path.read_text());assert row['specification']==request
                    else:
                        start=time.monotonic();row=run(case,request);row['seconds']=time.monotonic()-start
                        temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(row,indent=2)+'\n');temporary.replace(path)
                    row.update(cache_path=path.relative_to(ROOT).as_posix(),cache_sha256=sha(path));rows.append(row)
                    print(len(rows),'/48',case['case_id'],panels,modes,alpha,row['status'],row.get('maximum_local_residual'),flush=True)
    assert len(rows)==48 and modules=={p.name:sha(p) for p in (ROOT/'openswing').glob('*.py')}
    report=dict(status='CIRCULATION_REPRESENTATION_SENSITIVITY_NOT_VALIDATION',identity=identity,rows=rows,
        references=dict(steady_theory_pdf_sha256=sha(ROOT/'.reference/asw_theory.pdf'),
            extended_manual_pdf_sha256=sha(ROOT/'.reference/ASWING_Extended_User_Manual.pdf'),
            notes='Drela steady theory eqs62/63 describes pointwise and Fourier alternatives. ISAE extended manual Figure1.13 illustrates k=1..19 with180nodes; it does not establish the mode count used for SA11.'),
        limitations=['The main5304-request study uses the unchanged pointwise default. These48requests vary the Fourier truncation independently of mesh density.',
            'The exact archived discretization/mode counts are unknown. No mode count is selected by matching measured coefficients or merely avoiding a Mach rejection.',
            'Small projected residuals do not imply small pointwise flow defects; both are recorded. Physical validity and mode/mesh convergence remain separate requirements.',
            'Section properties, source geometry, PG law, wake cores, nonlinear tolerances and Mach guard are unchanged.'])
    (ROOT/'docs/validation/isae-sa11-circulation.json').write_text(json.dumps(report,indent=2)+'\n')
    print('COMPLETE',len(rows),'Fourier sensitivity requests',flush=True)


if __name__=='__main__':main()
