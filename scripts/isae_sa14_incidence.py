"""Explicit SA-14 incidence reconstruction and equivalent-frame geometry checks."""
from pathlib import Path
import hashlib
import json
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from openswing.asw import Distribution,parse_asw
from openswing.asw_edit import serialize,model_data
from openswing.geometry import surface_frame,model_meshes

D=ROOT/'docs/validation'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def rotation(angle):
    a=np.deg2rad(angle);c,s=np.cos(a),np.sin(a)
    return np.array([[c,0.,s],[0.,1.,0.],[-s,0.,c]])


def reconstruct(source,incidence=4.):
    """Same relative geometry in wing-fixed and body-fixed coordinate systems.

    Positive incidence lowers the aft-pointing wing axis in the body frame.
    The pivot is the primary root leading-edge location, not a fitted point.
    """
    pivot=np.array([36.76*.0254,0.,3.18*.0254])
    original=parse_asw(source)
    wing_frame=parse_asw(source);body_frame=parse_asw(source)
    forward=rotation(incidence);inverse=rotation(-incidence)
    body=next(b for b in wing_frame.beams if not b.lifting)
    t=body.distributions['x'].t.copy()
    positions=(body.position(t)-pivot)@inverse.T+pivot
    for key,column in [('x',0),('z',2)]:
        body.distributions[key]=Distribution(key,t.copy(),positions[:,column],body.line)
    wing=next(b for b in body_frame.beams if b.lifting)
    reference=next(b for b in original.beams if b.lifting)
    t=wing.distributions['x'].t.copy()
    positions=(wing.position(t)-pivot)@forward.T+pivot
    for key,column in [('x',0),('z',2)]:
        wing.distributions[key]=Distribution(key,t.copy(),positions[:,column],wing.line)
    station=.5*t[-1]
    target_chord=forward@surface_frame(reference,station)[:,0]
    zero_frame=surface_frame(wing,station)
    twist=np.rad2deg(np.arctan2(-target_chord@zero_frame[:,2],target_chord@zero_frame[:,0]))
    wing.distributions['twist']=Distribution('twist',t.copy(),np.full_like(t,twist),wing.line)
    wing_frame.name=f'SA14 iw{incidence:g} explicit wing-frame reconstruction'
    body_frame.name=f'SA14 iw{incidence:g} explicit body-frame reconstruction'
    return dict(wing_frame=serialize(wing_frame),body_frame=serialize(body_frame)),dict(
        incidence_deg=incidence,pivot_m=pivot.tolist(),wing_to_body_rotation=forward.tolist(),
        wing_body_frame_normal_twist_deg=float(twist),
        angle_policy='Alpha in the primary report is wing-root angle. Use alpha_body=alpha_wing-incidence in the body frame; use alpha_wing directly in the wing frame.')


def geometry_checks(source,derived,setup):
    original=parse_asw(source);models={k:parse_asw(v) for k,v in derived.items()}
    R=np.array(setup['wing_to_body_rotation']);pivot=np.array(setup['pivot_m'])
    a,b=models['wing_frame'],models['body_frame']
    for model in models.values():
        np.testing.assert_array_equal(model.constants,original.constants)
        np.testing.assert_array_equal(model.reference,original.reference)
        assert model_data(model)['records']==model_data(original)['records']
        assert [(v.index,v.physical_index) for v in model.beams]==[(v.index,v.physical_index) for v in original.beams]
        for beam,old in zip(model.beams,original.beams):
            for key in old.distributions.keys()-{'x','z','twist'}:
                np.testing.assert_array_equal(beam.distributions[key].t,old.distributions[key].t)
                np.testing.assert_array_equal(beam.distributions[key].values,old.distributions[key].values)
    checks=[]
    for beam_a,beam_b in zip(a.beams,b.beams):
        ts=np.linspace(*beam_a.domain,129)
        transformed=(beam_a.position(ts)-pivot)@R.T+pivot
        position_error=float(np.max(abs(transformed-beam_b.position(ts))))
        frames=np.einsum('ij,njk->nik',R,surface_frame(beam_a,ts))
        frame_error=float(np.max(abs(frames-surface_frame(beam_b,ts))))
        assert position_error<2e-14 and frame_error<2e-14
        checks.append(dict(beam=beam_a.index,stations=len(ts),position_error=position_error,frame_error=frame_error))
    meshes=[]
    for panels in [25,50,100]:
        for ma,mb in zip(model_meshes(a,panels),model_meshes(b,panels)):
            assert ma.beam.index==mb.beam.index and len(ma.tm)==len(mb.tm)
            error=max(float(np.max(abs((getattr(ma,k)-pivot)@R.T+pivot-getattr(mb,k)))) for k in ['r0','r1','rm'])
            length_error=float(np.max(abs(ma.length-mb.length)))
            assert error<2e-12 and length_error<2e-12
            meshes.append(dict(panels=panels,beam=ma.beam.index,intervals=len(ma.tm),position_error=error,length_error=length_error))
    return dict(beam_checks=checks,mesh_checks=meshes,
        maximum_position_error=max(r['position_error'] for r in checks+meshes),
        maximum_frame_error=max(r['frame_error'] for r in checks))


def measurement_mapping(sources):
    figure=next(f for f in sources['experimental'] if f['filename']=='Figure17.csv')
    stations=[.1,.15,.3,.55,.75,.9,.96]
    rows=[]
    for series in figure['series']:
        points=[]
        for p in series['points']:
            x,y=p['xy'];nearest=min(stations+[1.],key=lambda t:abs(x-t));assert abs(x-nearest)<.015
            classification=('drawn_tip_curve_endpoint' if nearest==1. else
                'upper_surface_measured_lower_interpolated' if nearest==.15 else 'instrumented_surface_station')
            points.append(dict(p,classification=classification,nominal_station=nearest,coordinate_difference=x-nearest))
        assert len(points)==8 and len({p['nominal_station'] for p in points})==8
        rows.append(dict(label=series['label'],alpha_w=float(series['label'].split('alpha_')[1].replace('_','.')),points=points))
    return dict(source_filename='Figure17.csv',inferred_primary_figure=15,source_sha256=figure['source_sha256'],
        original_digitization_metadata_recovered=False,coordinate_matching_tolerance=.015,series=rows,
        full_pressure_stations=18,upper_only_with_interpolated_lower=3,drawn_tip_endpoints=3,
        evidence='Primary Figure15 plots positive absolute iw=4 loads at wing alpha4.7/8.8/12.9 with matching markers and curves. Figure17 plots incremental changes. Primary pressure-measurement description explicitly adds eta=.15 for the plane wing at iw=4, measuring upper pressure and interpolating lower pressure.',
        limitation='Figure assignment is an explicit source inference; original digitization metadata and uncertainty are unavailable. No CSV value or coordinate is changed.')


def main():
    sources=json.loads((D/'isae-sa14-sources.json').read_text())
    original=next(m for m in sources['models'] if m['name']=='wing_body')
    derived,setup=reconstruct(original['source'])
    checks=geometry_checks(original['source'],derived,setup)
    zero,zero_setup=reconstruct(original['source'],0.)
    zero_checks=geometry_checks(original['source'],zero,zero_setup)
    variants={}
    for name,source in derived.items():
        path=D/f'isae-sa14-iw4-{name.replace("_","-")}.asw';path.write_text(source)
        variants[name]=dict(path=path.relative_to(ROOT).as_posix(),sha256=sha(path),source=source)
    primary=ROOT/sources['primary']['path'];assert sha(primary)==sources['primary']['sha256']
    out=dict(status='PASS_EXPLICIT_INCIDENCE_GEOMETRY_AND_MEASUREMENT_MAPPING_PHYSICAL_VALIDATION_PENDING',
        modules={p.name:sha(p) for p in (ROOT/'openswing').glob('*.py')},script_sha256=sha(Path(__file__)),
        source_report_sha256=sha(D/'isae-sa14-sources.json'),original_source_sha256=original['sha256'],
        original_source_path=original['path'],primary_sha256=sha(primary),primary_url=sources['primary']['url'],
        primary_pdf_pages=[5,6,7,12,26,29,39,41],setup=setup,variants=variants,
        geometry_checks=checks,zero_incidence_checks=zero_checks,measurements=measurement_mapping(sources),
        limitations=['These are explicit rigid reconstructions, not recovered original iw=4 ASW files.',
            'The supplied iw=0 geometry, normal chord, section properties, shared physical beam index and joint station/offset are retained. Their primary-experiment discrepancies remain.',
            'The primary root-leading-edge pivot is prescribed at x36.76in,z3.18in; it is not selected to improve agreement.',
            'A global4deg wing rotation requires a different local normal-section twist on the swept beam; simply adding4deg to its section twist is not equivalent.',
            'Rotating the body oppositely with the wing fixed gives an equivalent reference frame. Numerical force and local-load covariance still require actual solver checks.',
            'Source Figure17.csv is inferred to trace primary Figure15; its three eta=.15 points include lower-surface interpolation, and three tip endpoints are drawn-curve values.'])
    (D/'isae-sa14-incidence-sources.json').write_text(json.dumps(out,indent=2)+'\n')
    print(out['status'],setup,checks['maximum_position_error'],checks['maximum_frame_error'],flush=True)


if __name__=='__main__':main()
