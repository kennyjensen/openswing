"""Independently check ST-5 display diagnostics against saved physical loads.

Adds the existing geometric display frame as a disclosed supplementary probe;
does not solve, alter a frame or promote an archived comparison.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import resource
import signal

ROOT = Path(__file__).resolve().parents[1]
def read(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,d):
    with Path(p).open('x') as f:json.dump(d,f,indent=2,allow_nan=False);f.write('\n')


def prepare(out):
    plan=read(out/'plan.json');pins=dict(plan['pins'])
    pins[str(Path(__file__).resolve())]=sha(__file__)
    for entry in plan['cases']:
        folder=Path(entry['comparison']).parent
        for name in ('result.json','fresh-fields.npz'):pins[str(folder/name)]=sha(folder/name)
    for name in ('rigid.json','roller.json','forward.json','elliptical.json','summary.json'):
        pins[str(out/name)]=sha(out/name)
    save(out/'review-plan.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),pins=pins,
        checks=['Recompute the unit-average-normal projection directly from saved frame columns.',
                'Confirm ordinary intervals against the actual saved conservative gravity force and material length.',
                'Compare the existing geometric midpoint frame as a separate supplementary diagnostic on physical intervals only.'],
        ordinary_intervals_expected=992,unavailable_geometric_dummy_rows=200,
        solver_calls=0,primary_passes_added=0))
    print(json.dumps(dict(status='PREPARED_SAVED_LOAD_REVIEW',solver_calls=0)))


def run(out):
    import numpy as np
    plan=read(out/'plan.json');review=read(out/'review-plan.json')
    for p,h in review['pins'].items():assert sha(p)==h,p
    groups=[read(out/(f+'.json')) for f in ('rigid','roller','forward','elliptical')]
    cases={c['case']:c for g in groups for c in g['cases']}
    ordinary=[];projection_max=0.;weight_max=0.;frame_max=0.;checked=0
    for entry in plan['cases']:
        packet=read(entry['comparison']);folder=Path(entry['comparison']).parent
        result=read(folder/'result.json');assert result['converged'] and result['residual']<1e-8
        positions={r['source_line']:i for i,r in enumerate(packet['rows'])}
        elements={(e['beam'],e['t0'],e['t1']):(i,e) for i,e in enumerate(result['elements'])}
        with np.load(folder/'fresh-fields.npz',allow_pickle=False) as z:
            for r in cases[entry['case']]['rows']:
                row=packet['rows'][positions[r['source_line']]]
                assert r['expected']==row['expected'][25]
                if r['row_kind']=='final_dummy':
                    assert r['expected']==0;continue
                next_row=packet['rows'][positions[r['source_line']]+1]
                mean=(np.array(row['frame'])[:,2]+np.array(next_row['frame'])[:,2])/2
                w=(r['weights'][0]+r['weights'][1])/2
                prediction=-w*mean[2]/np.linalg.norm(mean)
                error=abs(prediction-r['predictions']['current']['endpoint_weight_unit_mean_normal'])
                projection_max=max(projection_max,error);assert error<1e-13;checked+=1
                if r['row_kind']!='ordinary':continue
                index,element=elements[(r['beam'],r['t'],r['following_t'])]
                np.testing.assert_array_equal(z['r'][row['node']],row['position'])
                assert int(z['a'][index])==row['node'] and int(z['b'][index])==next_row['node']
                actual=np.sum(z['element_forces'][index],axis=0)/element['length']
                error=float(np.max(abs(actual-np.array([0,0,-w]))));weight_max=max(weight_max,error)
                assert error<1e-12
                transform=np.asarray(element['transform_average'])
                error=float(np.max(abs(transform[2,:]-mean)));frame_max=max(frame_max,error)
                assert error<1e-13
                frame=np.asarray(element['physical_midpoint_frame'])
                np.testing.assert_allclose(frame.T@frame,np.eye(3),atol=1e-13,rtol=0)
                geometric=float(actual@frame[:,2])
                ordinary.append(dict(case=entry['case'],source_line=r['source_line'],beam=r['beam'],
                    expected=r['expected'],half_last_place=r['half_last_place'],
                    saved_geometric_projection=geometric,endpoint_unit_projection=prediction,
                    saved_conservative_force_per_length=actual.tolist()))
    assert len(ordinary)==review['ordinary_intervals_expected'] and checked==1164
    errors=[abs(r['saved_geometric_projection']-r['expected']) for r in ordinary]
    relative=[100*e/abs(r['expected']) for r,e in zip(ordinary,errors) if r['expected']]
    for p,h in review['pins'].items():assert sha(p)==h,p
    result=dict(observed_utc=datetime.now(timezone.utc).isoformat(),status='PASS_INDEPENDENT_SAVED_LOAD_CHECKS',
        normal_projections_checked=checked,physical_interval_loads_checked=len(ordinary),
        maximum_projection_reconstruction_error=projection_max,maximum_weight_reconstruction_error=weight_max,
        maximum_transform_average_error=frame_max,
        existing_geometric_frame_diagnostic=dict(required_original_rows=1192,available=992,unavailable=200,
            strict_matches=sum(e<=r['half_last_place'] for r,e in zip(ordinary,errors)),
            five_percent_matches=sum(e<=.05*abs(r['expected'])+r['half_last_place'] for r,e in zip(ordinary,errors)),
            maximum_absolute_error=max(errors),maximum_relative_percent=max(relative)),
        rows=ordinary,solver_calls=0,primary_passes_added=0,production_changes=False)
    save(out/'independent-review.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','run'])
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve()
    if a.action=='run':
        resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,)*2)
        resource.setrlimit(resource.RLIMIT_CPU,(15,)*2);signal.alarm(25)
    (prepare if a.action=='prepare' else run)(out)
