"""One serial SA-11 prescribed-field replay of the curved-bound correction.

Frozen cases reuse pinned Gamma. Current-wind cases recapture one unchanged
native solve because the previous archive did not retain its Gamma. Candidate
fields do not replace production equations or bypass the section-Mach gate.
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

import numpy as np
from scipy.integrate import quad_vec

ROOT = Path(__file__).resolve().parents[1]
SAVED = ROOT/'artifacts/isae/sa11-winglet-junction-20261107'
sys.path.insert(0, str(ROOT))
from openswing.aero import FlightCondition, AnalysisError, solve_rigid, _stall_leakage
from openswing.asw import parse_asw
from openswing.atmosphere import operating_air
from openswing.factored_influence import FactoredInfluence
from openswing.frozen_influence import lifting_geometry
from openswing.geometry import model_meshes


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def portable(value):
    if isinstance(value, np.ndarray): return value.tolist()
    if isinstance(value, np.generic): return value.item()
    if isinstance(value, dict): return {k: portable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [portable(v) for v in value]
    return value


def write(path, value):
    path.write_text(json.dumps(portable(value), indent=2, allow_nan=False)+'\n')


def components(points, g, direction, pg, gamma, own=False):
    op = FactoredInfluence(points, g['a'], g['b'], direction, pg,
                          exclude_bound=np.eye(len(gamma), dtype=bool) if own else None)
    bound = np.einsum('ijk,j->ik', op.bound, gamma)
    wake = np.einsum('ijk,j->ik', op.rays, op.wake_strengths(gamma))
    np.testing.assert_allclose(bound+wake, op.apply(gamma), atol=3e-9, rtol=2e-12)
    return bound, wake


def local_2d(points, hv, span, gamma, pg):
    # Analytic infinite straight filament in the SAME PG coordinate system.
    # This is a controlled compressible extension, not a published ASWING rule.
    tangent = span @ pg.T
    tangent /= np.linalg.norm(tangent, axis=1)[:, None]
    delta = (points-hv) @ pg.T
    perpendicular = delta - np.sum(delta*tangent, axis=1)[:, None]*tangent
    radius2 = np.sum(perpendicular**2, axis=1)
    assert np.min(radius2) > 0.
    return (gamma[:, None]/(2*np.pi) * np.cross(tangent, perpendicular)/radius2[:, None]) @ pg


def direct_bound(point, g, gamma, pg, omit=None):
    a, b = g['a'], g['b']
    if omit is not None:
        keep = np.arange(len(gamma)) != omit
        a, b, gamma = a[keep], b[keep], gamma[keep]
    first = (point-a) @ pg.T
    delta = (b-a) @ pg.T
    def integrand(t):
        r = first-t*delta
        return np.sum(gamma[:, None]*np.cross(delta, r)/np.linalg.norm(r, axis=1)[:, None]**3, axis=0) @ pg/(4*np.pi)
    value, estimate = quad_vec(integrand, 0., 1., epsabs=2e-8, epsrel=2e-10, limit=1000)
    assert estimate < 2e-7, estimate
    return value, estimate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--example', choices=('upper', 'both'), required=True)
    parser.add_argument('--panels', type=int, choices=(48, 96), required=True)
    parser.add_argument('--influence', choices=('frozen', 'current'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists(): parser.error('Use a fresh output directory.')
    stem = 'isae-sa11-wingtip-up' + ('-and-down' if args.example=='both' else '')
    source = ROOT/'examples'/f'{stem}.asw'
    frozen = args.influence=='frozen'
    baseline_path = SAVED/('results.json' if frozen else 'unfrozen-results.json')
    baseline = next(r for r in json.loads(baseline_path.read_text())
                    if r['example']==stem and r['panels']==args.panels)
    assert sha(source)==baseline['input_sha256']
    prior_plan = json.loads((SAVED/('plan.json' if frozen else 'unfrozen-plan.json')).read_text())
    for name, digest in prior_plan['modules'].items():
        assert sha(ROOT/'openswing'/name)==digest, name
    condition = FlightCondition(speed=30., alpha=5., freeze_influences=frozen)
    assert json.loads(json.dumps(asdict(condition)))==baseline['condition']
    pins = {str(p.relative_to(ROOT)): sha(p) for p in
            sorted(ROOT.glob('openswing/**/*.py')) + [ROOT/'docs/validation/ISAE_STATUS.md', ROOT/'docs/validation/isae-progress-scopes.json']}
    args.output.mkdir(parents=True)
    shutil.copyfile(__file__, args.output/'driver-used.py')
    plan = dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        previous_turn='progress: smooth-curvature singularity and section/force equation audit',
        example=stem, panels=args.panels, influence=args.influence, condition=asdict(condition),
        unchanged_pins=pins, input_sha256=sha(source), baseline_path=str(baseline_path.relative_to(ROOT)),
        baseline_sha256=sha(baseline_path), driver_sha256=sha(Path(__file__)),
        new_native_solves=0 if frozen else 1, candidate_circulation_solves=0,
        primary='local_chord_section_span',
        probes=['local_chord', 'native_cp', 'wind_halfchord'],
        local_line_directions=['section_span', 'bound_tangent'],
        rule='Vcandidate=Vambient+W(hv)+B(probe)-B2D(probe); same Gamma and all source filaments.',
        scope='Prescribed-field adaptations only. No reproduction of complete Li/MIRAS; no corrected nonlinear solve.',
        pg_scope='Original PG replay plus an identity-PG primary control; published bound correction is incompressible.',
        gates=dict(native_peak_relative=2e-9, independent_bound_atol=3e-7, independent_bound_rtol=3e-10))
    write(args.output/'plan.json', plan)
    started=time.monotonic()
    try:
        model=parse_asw(source.read_text())
        meshes=model_meshes(model, args.panels)
        assert all(m.beam.lifting and m.beam.physical_index==1 for m in meshes)
        assert not model.records.get('engine')
        assert all(np.all(m.beam.value('radius', m.tm)==0.) for m in meshes)
        wind=condition.vectors()[0]
        direction=np.array([1.,0.,0.]) if frozen else wind
        air=operating_air(model,condition)
        pg=np.eye(3)+(1/np.sqrt(1-air['ambient_mach']**2)-1)*np.outer(direction,direction)
        g=lifting_geometry(meshes,direction)
        span=np.concatenate([m.frames[...,1] for m in meshes])
        chord_direction=np.concatenate([m.frames[...,0] for m in meshes])
        normal=np.concatenate([m.frames[...,2] for m in meshes])
        beam=np.concatenate([np.full(len(m.tm),m.beam.index) for m in meshes])
        parameter=np.concatenate([m.tm for m in meshes])
        slope=np.concatenate([m.beam.value('dCLda',m.tm) for m in meshes])
        alpha=np.concatenate([m.beam.value('alpha',m.tm) for m in meshes])
        cp_normal=np.sin(np.deg2rad(alpha))[:,None]*chord_direction+np.cos(np.deg2rad(alpha))[:,None]*normal
        lower=np.concatenate([m.beam.value('CLmin',m.tm) for m in meshes])
        upper=np.concatenate([m.beam.value('CLmax',m.tm) for m in meshes])
        native_seconds=0.
        native_velocity=None
        if frozen:
            saved_path=SAVED/f'{stem}-{args.panels}.npz'
            prior_analysis=json.loads((SAVED/'analysis.json').read_text())
            assert sha(baseline_path)==prior_analysis['results_sha256']
            assert sha(saved_path)==prior_analysis['data_sha256'][saved_path.name]
            with np.load(saved_path) as saved:
                gamma=saved['gamma'].copy()
                np.testing.assert_array_equal(beam,saved['beam'])
                np.testing.assert_array_equal(parameter,saved['t'])
                for key in ('a','b','hv','cp'):
                    np.testing.assert_allclose(g[key],saved[key],atol=3e-14,rtol=0.)
            original=baseline
            write(args.output/'gamma-source.json',dict(path=str(saved_path.relative_to(ROOT)),sha256=sha(saved_path)))
        else:
            t0=time.monotonic()
            try:
                result=solve_rigid(model,condition,args.panels)
                gamma=np.array([r['circulation'] for r in result['strips']])
                native_velocity=np.array([r['relative_velocity'] for r in result['strips']])
                np.testing.assert_array_equal(beam,[r['beam'] for r in result['strips']])
                np.testing.assert_array_equal(parameter,[r['t'] for r in result['strips']])
                original=dict(status='computed',result={k:result[k] for k in ('CL','CD','CDi','Cm','residual','lifting_airflow')})
                for key in ('CL','CD','CDi','Cm'):
                    np.testing.assert_allclose(result[key],baseline['result'][key],atol=2e-11,rtol=2e-10)
            except AnalysisError as exc:
                assert exc.details['kind']=='section_normal_mach'
                trace=exc.__traceback__
                while trace is not None and trace.tb_frame.f_code.co_name!='evaluate_aerodynamics': trace=trace.tb_next
                assert trace is not None
                values=trace.tb_frame.f_locals
                gamma=values['gamma'].copy()
                native_velocity=values['v'].copy()
                np.testing.assert_array_equal(beam,values['p']['beam'])
                np.testing.assert_array_equal(parameter,values['p']['t'])
                original=dict(status='rejected',error=str(exc),details=exc.details)
                del trace,values
            native_seconds=time.monotonic()-t0
            assert original['status']==baseline['status']
        write(args.output/'native-observation.json',original)
        assert len(gamma)<=500
        ambient=condition.speed*wind
        bound,wake=components(g['hv'],g,direction,pg,gamma,own=True)
        raw=ambient+bound+wake
        if native_velocity is not None:
            np.testing.assert_allclose(raw,native_velocity,atol=3e-7,rtol=3e-10)
        original_max=original['details']['maximum'] if original['status']=='rejected' else original['result']['lifting_airflow']['maximum']
        baseline_max=baseline['details']['maximum'] if baseline['status']=='rejected' else baseline['result']['lifting_airflow']['maximum']
        np.testing.assert_allclose(original_max['normal_mach'],baseline_max['normal_mach'],atol=2e-10,rtol=2e-9)
        expected_index=int(np.argmin(np.linalg.norm(g['hv']-original_max['position'],axis=1)))
        np.testing.assert_allclose(raw[expected_index],original_max['relative_velocity'],atol=3e-7,rtol=3e-10)
        if original['status']=='rejected':
            breakdown=original['details']['vortex_breakdown']
            np.testing.assert_allclose(bound[expected_index],breakdown['bound_velocity'],atol=3e-7,rtol=3e-10)
            np.testing.assert_allclose(wake[expected_index],breakdown['wake_velocity'],atol=3e-7,rtol=3e-10)
        cp_bound,cp_wake=components(g['cp'],g,direction,pg,gamma)
        tangency=np.sum((ambient+cp_bound+cp_wake)*cp_normal,axis=1)
        records=[]
        arrays=dict(gamma=gamma,beam=beam,t=parameter,span=span,chord_direction=chord_direction,
                    pg=pg,direction=direction,ambient=ambient,bound_hv=bound,wake_hv=wake,
                    raw_velocity=raw,cp_tangency=tangency,**g)
        def observe(label, velocity, candidate_bound, *, evaluate_native_residual=True):
            vp=velocity-np.sum(velocity*span,axis=1)[:,None]*span
            speed=np.linalg.norm(vp,axis=1)
            mach=speed/air['sound_speed']
            worst=int(np.argmax(mach))
            residual=None
            if evaluate_native_residual:
                effective=np.maximum(speed,condition.speed*1e-12)
                cl=2*gamma/(g['chord']*effective)
                leakage,_=_stall_leakage(cl,lower,upper,condition.stall_width)
                residual=(tangency-effective/slope*condition.stall_factor*leakage)/condition.speed
            row=dict(label=label,maximum_normal_mach=float(mach[worst]),
                at_or_above_unity=int(np.count_nonzero(mach>=1)),
                worst=dict(index=worst,beam=int(beam[worst]),t=float(parameter[worst]),
                           position=g['hv'][worst],velocity=velocity[worst],
                           bound_contribution=candidate_bound[worst],wake_contribution=wake[worst]),
                maximum_bound_speed=float(np.max(np.linalg.norm(candidate_bound,axis=1))),
                maximum_native_stall_residual=None if residual is None else float(np.max(abs(residual))),
                peak_mach_by_beam={str(int(i)):float(np.max(mach[beam==i])) for i in np.unique(beam)})
            records.append(row)
            arrays[label+'_velocity']=velocity
            arrays[label+'_bound']=candidate_bound
            arrays[label+'_normal_mach']=mach
            if residual is not None: arrays[label+'_native_stall_residual']=residual
            return row
        raw_row=observe('native',raw,bound)
        np.testing.assert_allclose(raw_row['maximum_normal_mach'],baseline_max['normal_mach'],atol=2e-10,rtol=2e-9)
        assert raw_row['maximum_native_stall_residual']<1e-8
        across=np.linalg.norm(np.cross(direction,span),axis=1)
        probes=dict(local_chord=g['hv']+.5*g['chord'][:,None]*chord_direction,
                    native_cp=g['cp'],wind_halfchord=g['hv']+(.5*g['chord']/across)[:,None]*direction)
        tangent=g['b']-g['a'];tangent/=np.linalg.norm(tangent,axis=1)[:,None]
        for name,point in probes.items():
            field=cp_bound if name=='native_cp' else components(point,g,direction,pg,gamma)[0]
            arrays[name+'_probe']=point
            arrays[name+'_3d_bound']=field
            for span_name,local_span in (('section_span',span),('bound_tangent',tangent)):
                own=local_2d(point,g['hv'],local_span,gamma,pg)
                correction=field-own
                label=name+'_'+span_name
                arrays[label+'_2d_bound']=own
                observe(label,ambient+wake+correction,correction)
        # Isolate the small PG extension from the incompressible construction.
        b0,w0=components(g['hv'],g,direction,np.eye(3),gamma,own=True)
        bc0=components(probes['local_chord'],g,direction,np.eye(3),gamma)[0]
        corrected0=bc0-local_2d(probes['local_chord'],g['hv'],span,gamma,np.eye(3))
        observe('incompressible_native',ambient+w0+b0,b0,evaluate_native_residual=False)
        observe('incompressible_local_chord_section_span',ambient+w0+corrected0,corrected0,evaluate_native_residual=False)
        # The observe helper's displayed wake must match each variant's PG.
        for row in records[-2:]: row['worst']['wake_contribution']=w0[row['worst']['index']]
        arrays['incompressible_wake_hv']=w0
        primary=next(r for r in records if r['label']==plan['primary'])
        indices=sorted(set([expected_index,primary['worst']['index']]))
        checks=[]
        for idx in indices:
            for name,point,field,omit in (
                ('native_hv',g['hv'][idx],bound[idx],idx),
                ('local_chord',probes['local_chord'][idx],arrays['local_chord_3d_bound'][idx],None)):
                independent,estimate=direct_bound(point,g,gamma,pg,omit)
                np.testing.assert_allclose(field,independent,atol=3e-7,rtol=3e-10)
                checks.append(dict(probe=name,index=idx,quadrature_estimate=estimate,
                                   maximum_difference=float(np.max(abs(field-independent)))))
        np.savez_compressed(args.output/'fields.npz',**arrays)
        for name,digest in pins.items(): assert sha(ROOT/name)==digest,name
        result=dict(observed_utc=datetime.now(timezone.utc).isoformat(), example=args.example,
            panels=args.panels,influence=args.influence,actual_intervals=len(gamma),
            records=records,independent_checks=checks,native_solve_seconds=native_seconds,
            total_seconds=time.monotonic()-started,new_native_solves=0 if frozen else 1,
            candidate_circulation_solves=0,production_and_primary_counts_unchanged=True)
        write(args.output/'results.json',result)
        write(args.output/'verification.json',dict(status='verified',observed_utc=datetime.now(timezone.utc).isoformat(),
            unchanged_pin_count=len(pins),artifacts={p.name:sha(p) for p in sorted(args.output.iterdir()) if p.is_file()}))
        print(json.dumps(dict(status='verified',example=args.example,panels=args.panels,influence=args.influence,
            native_mach=raw_row['maximum_normal_mach'],primary_mach=primary['maximum_normal_mach'],
            primary_residual=primary['maximum_native_stall_residual'],seconds=result['total_seconds'])))
    except Exception as exc:
        write(args.output/'failure.json',dict(error_type=type(exc).__name__,error=str(exc),
                                             observed_utc=datetime.now(timezone.utc).isoformat()))
        raise


if __name__=='__main__': main()
