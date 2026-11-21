"""Distinguish SA-12 ground height and aircraft attitude before comparison."""
from pathlib import Path
import hashlib, json, sys, time
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, solve_rigid, AnalysisError
REVISION='f62943df20e9e4d7d9f50e070477b22426b5f865'
CACHE=ROOT/'.reference/isae-validation'/REVISION
FOLDER=next(CACHE.glob('1 - Aerodynamics/SA*/SA - 12 - *'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    models=[dict(name='no_flap',path=FOLDER/'Aswing_Simulations/Rectangular_Wing_No_flap.asw'),
            dict(name='slotted_flap',path=FOLDER/'Aswing_Simulations/Rectangular_Wing_flap.asw')]
    modules={p.name:sha(p) for p in (ROOT/'openswing').glob('*.py')}
    identity=dict(modules=modules,script_sha256=sha(Path(__file__)),revision=REVISION,
        sources={m['path'].relative_to(CACHE).as_posix():sha(m['path']) for m in models})
    folder=ROOT/'.reference/isae-sa12-setup'/hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    folder.mkdir(parents=True,exist_ok=True);rows=[]
    (folder/'identity.json').write_text(json.dumps(identity,indent=2)+'\n')
    for model_row in models:
        model=parse_asw(model_row['path'].read_text())
        for label,height in [('05',.127),('2',.508),('inf',1000.)]:
            table=FOLDER/'Aswing_Simulations'/f"Rectangular_Wing_{'No_Flap' if model_row['name']=='no_flap' else 'Flap'}_hc_{label}.txt"
            archived=np.loadtxt(table)
            for alpha in ([0.,5.,10.] if model_row['name']=='no_flap' else [5.,10.]):
                for pose in (['level_freestream'] if alpha==0 else ['zero_attitude','level_freestream']):
                    request=dict(case=model_row['name'],height_label=label,height=height,alpha=alpha,panels=100,
                        pose=pose,speed=35.76,mach=0.,frozen=False,ground_effect=1)
                    path=folder/(hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest()+'.json')
                    if path.exists():
                        row=json.loads(path.read_text());assert row['specification']==request
                    else:
                        start=time.monotonic();pitch=alpha if pose=='level_freestream' else 0.
                        condition=FlightCondition(speed=35.76,alpha=alpha,mach=0.,ground_effect=1,
                            position_earth=(0.,0.,height),attitude=(0.,pitch,0.))
                        try:
                            result=solve_rigid(model,condition,panels=100)
                            assert result['residual']<=1e-8
                            selected={k:result[k] for k in ['CL','CD','CDi','CDi_near','CDp','Cm','residual','ground_plane','trefftz','lifting_airflow']}
                            if alpha==0:
                                expected=.01*1.524*.254/.3871
                                # Asymmetric CLmin/CLmax leaves a tiny smooth
                                # stall-leakage tail at zero incidence. A separate
                                # stall-off control gives exactly zero lift.
                                assert abs(result['CL'])<1e-9 and abs(result['CD']-expected)<1e-11
                                selected['independent_zero_alpha_drag']=expected
                                selected['zero_incidence_smooth_stall_CL']=result['CL']
                            row=dict(specification=request,status='computed',result=selected)
                        except AnalysisError as exc:
                            row=dict(specification=request,status='rejected',error=str(exc),details=getattr(exc,'details',None))
                        row['seconds']=time.monotonic()-start
                        reference=next(r for r in archived if r[4]==alpha)
                        row['archived']={key:float(reference[column]) for key,column in [('CL',5),('CD',6),('CDi',7),('Cm',8)]}
                        row['archive_sha256']=sha(table)
                        temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(row,indent=2)+'\n');temporary.replace(path)
                    row.update(cache_path=path.relative_to(ROOT).as_posix(),cache_sha256=sha(path));rows.append(row)
                    print(len(rows),request,row['status'],row.get('result',{}).get('CL'),flush=True)
    assert len(rows)==27 and modules=={p.name:sha(p) for p in (ROOT/'openswing').glob('*.py')}
    out=dict(status='SETUP_SENSITIVITY_NOT_EXPERIMENTAL_VALIDATION',identity=identity,rows=rows,
        interpretation=[
            'The primary tunnel flow is parallel to the horizontal ground board. With beta=0, pitch=alpha makes the relative freestream parallel to that board in the model.',
            'The archived commands change body alpha and Earth height but do not record Euler pitch. Zero attitude is a separate setup diagnostic, not the primary tunnel pose.',
            'h is measured at the quarter chord; Xax=.25 and the source x=0 place this point at the body origin. Rz=hc*chord for finite heights.',
            'The nominal infinite-height script retains the solid image at Rz=1000; no-ground is a separate limiting check.',
            'Source section properties, stall law, cores and solver tolerances are unchanged. The close-ground no-flap CD replacement .01+CDi in MATLAB is not applied.',
            'Pointwise circulation at100requested intervals is not proven identical to the archived NODE setting100 or its unrecorded mode count.'])
    (ROOT/'docs/validation/isae-sa12-setup.json').write_text(json.dumps(out,indent=2)+'\n')
    print('COMPLETE',len(rows),flush=True)


if __name__=='__main__':main()
