"""Audit force reductions and equivalent frames; report conditional iw=4 comparisons."""
from pathlib import Path
import json
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from isae_sa14_reference import sha,CACHE,csv_series
from openswing.asw import parse_asw
from isae_sa14_incidence import reconstruct
D=ROOT/'docs/validation'


def stats(points):
    errors=np.array([p['predicted']-p['observed'] for p in points if p['predicted'] is not None])
    return dict(total=len(points),computed=len(errors),unavailable=len(points)-len(errors),
        rmse=float(np.sqrt(np.mean(errors**2))) if len(errors) else None,
        mean_error=float(np.mean(errors)) if len(errors) else None,
        maximum_absolute_error=float(np.max(abs(errors))) if len(errors) else None)


def main():
    study=json.loads((D/'isae-sa14-incidence.json').read_text())
    sources=json.loads((D/'isae-sa14-sources.json').read_text())
    incidence=json.loads((D/'isae-sa14-incidence-sources.json').read_text())
    assert study['computed']==54 and study['rejected']==0 and study['reused']==12
    assert study['provenance']['modules']=={p.name:sha(p) for p in (ROOT/'openswing').glob('*.py')}
    assert study['provenance']['source_report_sha256']==sha(D/'isae-sa14-sources.json')
    assert study['provenance']['incidence_source_sha256']==sha(D/'isae-sa14-incidence-sources.json')
    for name,pin in sources['files'].items():
        path=CACHE/name;assert path.stat().st_size==pin['bytes'] and sha(path)==pin['sha256']
    assert sha(ROOT/sources['primary']['path'])==incidence['primary_sha256']
    original=next(m for m in sources['models'] if m['name']=='wing_body')
    assert sha(CACHE/original['path'])==original['sha256']==incidence['original_source_sha256']
    regenerated,setup=reconstruct(original['source'])
    assert setup==incidence['setup']
    for name,v in incidence['variants'].items():
        assert v['source']==regenerated[name]==(ROOT/v['path']).read_text() and sha(ROOT/v['path'])==v['sha256']
    figure=next(f for f in sources['experimental'] if f['filename']=='Figure17.csv')
    for path in figure['identical_copies']:
        assert sha(CACHE/path)==figure['source_sha256'] and csv_series(CACHE/path)==figure['series']
    for series in incidence['measurements']['series']:
        raw=next(s for s in figure['series'] if s['label']==series['label'])
        assert [dict(row=p['row'],xy=p['xy']) for p in series['points']]==raw['points']
    reductions=[];compared=[]
    area=sources['primary']['wing']['area_m2'];span=sources['primary']['wing']['span_m']
    for row in study['rows']:
        q=row['specification'];r=row['result'];assert sha(ROOT/row['cache_path'])==row['cache_sha256']
        if 'reused_cache_path' in row:assert sha(ROOT/row['reused_cache_path'])==row['reused_cache_sha256']
        source=original['source'] if q['case']=='iw0' else incidence['variants'][q['case']]['source']
        model=parse_asw(source);np.testing.assert_array_equal(model.reference[1],[0.,0.,0.])
        strips=r['profiles']+r['body_strips'];force=np.sum([s['force'] for s in strips],axis=0)
        moment=np.sum([np.cross(np.array(s['position'])-model.reference[1],s['force'])+s['moment'] for s in strips],axis=0)
        a=np.deg2rad(q['alpha']);lift=np.array([-np.sin(a),0.,np.cos(a)])
        pressure=.5*model.constants[1]*70.**2
        total_CL=float(force@lift/pressure/area)
        local=[float(np.array(s['force'])@lift/pressure/(s['y1']-s['y0'])/(area/span)) for s in r['profiles']]
        full_CL=sum(v*(s['y1']-s['y0'])/span for v,s in zip(local,r['profiles']))
        exposed_CL=sum(v*(s['y1']-s['y0'])*s['exposed_fraction']/span for v,s in zip(local,r['profiles']))
        e=dict(specification=q,force=float(np.max(abs(force-r['force']))),moment=float(np.max(abs(moment-r['moment']))),
            total_CL=abs(total_CL-r['primary_normalization']['CL_total']),
            wing_CL=abs(full_CL-r['primary_normalization']['CL_full_wing']),
            exposed_CL=abs(exposed_CL-r['primary_normalization']['CL_exposed_wing']),
            local=float(np.max(abs(np.array(local)-[s['primary_local_load'] for s in r['profiles']]))))
        assert e['force']<1e-8 and e['moment']<1e-8 and max(e[k] for k in ['total_CL','wing_CL','exposed_CL','local'])<2e-12,e
        reductions.append(e)
        series=next(s for s in incidence['measurements']['series'] if s['alpha_w']==q['alpha_w'])
        xs=np.array([s['normalized_y'] for s in r['profiles']]);ys=np.array(local)
        points=[]
        for p in series['points']:
            x,observed=p['xy'];inside=bool(xs[0]<=x<=xs[-1])
            points.append(dict(source_row=p['row'],normalized_y=x,observed=observed,classification=p['classification'],
                nominal_station=p['nominal_station'],predicted=float(np.interp(x,xs,ys)) if inside else None,
                status='computed' if inside else 'outside_native_midpoint_range'))
        full=[p for p in points if p['classification']=='instrumented_surface_station']
        partial=[p for p in points if p['classification']=='upper_surface_measured_lower_interpolated']
        tips=[p for p in points if p['classification']=='drawn_tip_curve_endpoint']
        compared.append(dict(specification=q,points=points,full_pressure=stats(full),partly_interpolated_pressure=stats(partial),
            all_pressure=stats(full+partial),drawn_tip_endpoints=stats(tips),primary_normalization=r['primary_normalization'],
            maximum_section_normal_mach=r['maximum_section_normal_mach']))
    R=np.array(setup['wing_to_body_rotation']);pivot=np.array(setup['pivot_m']);covariance=[]
    for row in study['rows']:
        q=row['specification']
        if q['case']!='wing_frame':continue
        a=row['result'];b=next(s['result'] for s in study['rows'] if s['specification']['case']=='body_frame' and
            all(s['specification'][k]==q[k] for k in ['panels','alpha_w','pg']))
        fb=R@a['force'];mb=R@a['moment']+np.cross(pivot-R@pivot,fb)
        sa=a['profiles']+a['body_strips'];sb=b['profiles']+b['body_strips']
        assert len(sa)==len(sb)
        # Rotation changes arc-length arithmetic at roundoff; station topology stays identical.
        for x,y in zip(sa,sb):assert x['beam']==y['beam'] and abs(x['t']-y['t'])<2e-12
        d=dict(specification=q,station_roundoff=max(abs(x['t']-y['t']) for x,y in zip(sa,sb)),
            force=float(np.max(abs(fb-b['force']))),moment=float(np.max(abs(mb-b['moment']))),
            strip_force=max(float(np.max(abs(R@x['force']-y['force']))) for x,y in zip(sa,sb)),
            section_moment=max(float(np.max(abs(R@x['moment']-y['moment']))) for x,y in zip(sa,sb)),
            coefficients=max(abs(a['coefficients'][k]-b['coefficients'][k]) for k in ['CL','CD','CY']),
            primary_CL=max(abs(v-b['primary_normalization'][k]) for k,v in a['primary_normalization'].items() if k.startswith('CL_')),
            local_load=max(abs(x['primary_local_load']-y['primary_local_load']) for x,y in zip(a['profiles'],b['profiles'])),
            velocity=max(float(np.max(abs(R@x['relative_velocity']-y['relative_velocity']))) for x,y in zip(a['profiles'],b['profiles'])),
            section_cl=max(abs(x['cl']-y['cl']) for x,y in zip(a['profiles'],b['profiles'])),
            normal_mach=max(abs(x['normal_mach']-y['normal_mach']) for x,y in zip(a['profiles'],b['profiles'])))
        assert max(d[k] for k in ['force','moment','strip_force','section_moment'])<2e-8,d
        assert max(d[k] for k in ['coefficients','primary_CL','local_load','section_cl','normal_mach'])<2e-10,d
        assert d['velocity']<2e-7,d
        covariance.append(d)
    max_cov={k:max(d[k] for d in covariance) for k in covariance[0] if k!='specification'}
    max_red={k:max(d[k] for d in reductions) for k in reductions[0] if k!='specification'}
    runtime={}
    for name,count in [('wasm',18),('browser',8)]:
        path=D/f'isae-sa14-incidence-{name}.json'
        if not path.exists():
            runtime[name]=dict(status='PENDING');continue
        replay=json.loads(path.read_text())
        assert replay['native_sha256']==sha(D/'isae-sa14-incidence.json')
        assert replay['incidence_sources_sha256']==sha(D/'isae-sa14-incidence-sources.json')
        assert replay['modules']==study['provenance']['modules'] and len(replay['rows'])==count
        assert all(r['status']=='matching_solution' for r in replay['rows'])
        if name=='browser':assert replay['offline'] is True
        runtime[name]=dict(status=replay['status'],states=count,path=path.relative_to(ROOT).as_posix(),sha256=sha(path),
            maximum_coefficient_difference=max(r['maximum_coefficient_difference'] for r in replay['rows']),
            maximum_strip_force_difference=max(r['maximum_strip_force_difference'] for r in replay['rows']))
    out=dict(status='PASS_FRAME_AND_LOAD_CHECKS_EXPERIMENTAL_DISCREPANCIES_REMAIN',
        native_sha256=sha(D/'isae-sa14-incidence.json'),incidence_sources_sha256=sha(D/'isae-sa14-incidence-sources.json'),
        script_sha256=sha(Path(__file__)),modules=study['provenance']['modules'],native_states=54,new_states=42,reused_states=12,
        unchanged_upstream_files=len(sources['files']),measurement_counts=dict(full_pressure=18,partly_interpolated_pressure=3,drawn_tip_endpoints=3),
        comparisons=compared,force_reductions=reductions,frame_covariance=covariance,runtime_checks=runtime,
        maximum_reduction_error=max_red,maximum_frame_difference=max_cov,
        acceptance='Numerical identities and runtime replay are checked separately. Experimental uncertainty and a justified acceptance threshold are unavailable; no experimental pass is asserted.',
        limitations=study['limitations']+['High-angle local-load errors remain; a coordinate-equivalent reconstruction does not validate the underlying body-interference or section-stall model.',
            'The known swept-force velocity mesh defect remains. Three meshes here do not establish converged force fields.',
            'No recovered original iw4 ASW file or ASWING iw4 result is available; original ASWING iw0 comparisons are documented separately.'])
    (D/'isae-sa14-incidence-comparison.json').write_text(json.dumps(out,indent=2)+'\n')
    primary=[r for r in compared if r['specification']['case']=='wing_frame' and r['specification']['pg']=='primary_0.19']
    lines=['# SA-14: explicit 4° incidence reconstruction', '',
        'The 54-state native protocol passes force reduction and equivalent-coordinate checks. Experimental discrepancies remain. This is a conditional comparison using two explicit reconstructions; neither is a recovered original iw=4° input.', '',
        'The source case is from [ISAE’s validation repository](https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation), revision `'+study['provenance']['revision']+'`. All 50 case files remain byte-for-byte unchanged. The experiment is [NACA TN 3730](https://ntrs.nasa.gov/citations/19920075067).', '',
        '## Geometry and source interpretation', '',
        '- The report defines α as wing-root chord angle and iw as wing angle minus body angle (PDF p.5). Thus α_body = α_wing − 4°.',
        '- PDF p.6 and Figure 1 retain the root leading edge’s height when incidence changes. The reconstruction rotates about the prescribed root-leading-edge location x=36.76 in, z=3.18 in. The original model’s approximate chord and quarter-axis geometry are retained; the pivot is not fitted.',
        '- In the wing frame the wing stays fixed and the body rotates −4°. In the body frame the body stays fixed and the wing rotates +4°. The latter requires local normal-section twist '+f"{setup['wing_body_frame_normal_twist_deg']:.12g}"+'° on the swept beam; adding 4° directly to section twist is not the same geometry.',
        '- The source file named Figure17.csv contains positive absolute iw=4° loads matching the markers and curves in primary Figure 15 (PDF p.39). Primary Figure 17 shows increments. The Figure 15 assignment is a documented inference; original digitization metadata is unavailable.',
        '- Each of three angles has six standard pressure stations, one η=0.15 station with measured upper-surface pressure and interpolated lower-surface loading (PDF p.7), and one drawn tip endpoint. The η=0.15 points are retained as partly measured pressure data. Tip endpoints are excluded from pressure error metrics.', '',
        'The generated [wing-frame input](isae-sa14-iw4-wing-frame.asw) and [body-frame input](isae-sa14-iw4-body-frame.asw) preserve reference values, section properties, beam identities, joint stations and all non-geometric distributions. Constants and original source values are not fitted.', '',
        '## Protocol and checks', '',
        'The protocol uses meshes N=25, 50 and 100, wing angles 4.7°, 8.8° and 12.9°, and both primary Mach 0.19 and the archived mixed-PG convention (speed-derived PG at 4.7°, zero at 8.8°/12.9°). Each condition has an iw=0 control and both iw=4 frames: 54 states, 42 new solves and 12 reused states with matching source/module/cache hashes. All states solved.', '',
        'Local loading is wind-axis strip lift divided by dynamic pressure, projected span width and primary mean geometric chord S/b. It is not section-normal cl multiplied by a constant. Total, full-wing, exposed-wing and body lift are retained separately. No extrapolation fills data outside native midpoint coverage.', '',
        f"For 18 frame pairs, the largest force difference is {max_cov['force']:.3g} N, translated-moment difference {max_cov['moment']:.3g} N·m, local-load difference {max_cov['local_load']:.3g}, and velocity difference {max_cov['velocity']:.3g} m/s. Moments include the change of origin: M_body = R M_wing + (p − R p) × F_body. All 54 cases independently reconstruct force, moment and normalized lift from their exported strips.", '',
        '## Experimental comparison', '',
        'The table reports dimensionless local-load RMSE over seven pressure-derived points per angle, including η=0.15 with its lower-surface interpolation. The final column uses only the six fully instrumented stations. Original coordinates and values are preserved; no points are discarded to improve agreement.', '',
        '| Wing α | N=25 | N=50 | N=100 | iw=0 control, N=100 | N=100, full-pressure stations only |',
        '|---:|---:|---:|---:|---:|---:|']
    for alpha in [4.7,8.8,12.9]:
        group=[next(r for r in primary if r['specification']['alpha_w']==alpha and r['specification']['panels']==n) for n in [25,50,100]]
        control=next(r for r in compared if r['specification']==dict(case='iw0',panels=100,alpha_w=alpha,alpha=alpha,pg='primary_0.19'))
        assert all(r['all_pressure']['computed']==7 for r in group)
        lines.append('| '+f'{alpha:g}° | '+' | '.join(f"{r['all_pressure']['rmse']:.6f}" for r in group)+f" | {control['all_pressure']['rmse']:.6f} | {group[-1]['full_pressure']['rmse']:.6f} |")
    lines+=['', 'The incidence reconstruction improves this metric at 4.7° relative to the iw=0 control; discrepancies increase at the higher angles. These are error measurements, not a demonstrated validation pass. Experimental uncertainty and justified acceptance bounds have not been recovered.', '',
        '![SA-14 incidence load comparison](isae-sa14-incidence.png)', '',
        '## Limits and remaining work', '',
        'The [swept-force mesh diagnosis](swept-lifting-line-limit.md) remains unresolved: increasing resolution can increase near-tip force-point velocity even when integrated lift changes little. This study does not establish mesh convergence or cure that defect. Accurate section stall, near-juncture interference, missing source geometry provenance and experimental uncertainty still limit a full validation claim.', '',
        'The [iw=0 pilot](isae-sa14-pilot.md), [extended polars](isae-sa14-polars.md), and [original ASWING load-export audit](isae-sa14-load-exports.md) remain separate evidence. No original iw=4 ASWING output was available for a direct solver comparison.', '',
        '## Reproduction and evidence', '',
        'Run `scripts/isae_sa14_incidence.py`, `scripts/verify-isae-sa14-incidence.py`, and `scripts/summarize-isae-sa14-incidence.py` with the project Python environment. The source audit pins the original files, primary report and all 97 solver modules. The native runner uses atomic cache files and can resume without repeating completed solves.', '',
        '- [Source and geometry audit](isae-sa14-incidence-sources.json)',
        '- [All 54 native states](isae-sa14-incidence.json)',
        '- [Point comparisons, force reductions and 18 frame checks](isae-sa14-incidence-comparison.json)',
        '- [WASM replay](isae-sa14-incidence-wasm.json) uses 18 states: both frames at all three meshes and angles with primary Mach 0.19. Current status: `'+runtime['wasm']['status']+'`.',
        '- [Browser replay](isae-sa14-incidence-browser.json) checks eight states offline, including both frames at N=100 and α_w=12.9°. Current status: `'+runtime['browser']['status']+'`. Runtime agreement establishes execution consistency; it does not establish experimental accuracy.', '',
        'Runtime reproduction uses `node scripts/test-isae-sa14-incidence-wasm.mjs` and `tests/browser/isae-sa14-incidence.spec.js` against the same pinned app modules. Copy the browser evidence JSON from its Playwright output directory to `docs/validation/`, then rerun this summarizer to verify runtime provenance.', '']
    (D/'isae-sa14-incidence.md').write_text('\n'.join(lines))
    fig,axes=plt.subplots(1,3,figsize=(13.8,4.6),layout='constrained')
    colors=['#0072b2','#e69f00','#009e73']
    for ax,alpha in zip(axes,[4.7,8.8,12.9]):
        for n,color in zip([25,50,100],colors):
            row=next(r for r in study['rows'] if r['specification']==dict(case='wing_frame',panels=n,alpha_w=alpha,alpha=alpha,pg='primary_0.19'))
            pts=[s for s in row['result']['profiles'] if s['normalized_y']>=.08]
            ax.plot([s['normalized_y'] for s in pts],[s['primary_local_load'] for s in pts],color=color,label=f'iw=4°, N={n}',lw=1.5)
        row=next(r for r in study['rows'] if r['specification']==dict(case='iw0',panels=100,alpha_w=alpha,alpha=alpha,pg='primary_0.19'))
        pts=[s for s in row['result']['profiles'] if s['normalized_y']>=.08]
        ax.plot([s['normalized_y'] for s in pts],[s['primary_local_load'] for s in pts],color='.45',ls='--',label='iw=0° control, N=100',lw=1.2)
        series=next(s for s in incidence['measurements']['series'] if s['alpha_w']==alpha)
        for classification,marker,label in [('instrumented_surface_station','D','Pressure stations'),('upper_surface_measured_lower_interpolated','s','Upper measured / lower interpolated'),('drawn_tip_curve_endpoint','x','Drawn tip (not scored)')]:
            ps=[p['xy'] for p in series['points'] if p['classification']==classification]
            ax.scatter(*np.array(ps).T,marker=marker,s=30,label=label,color='black',zorder=4,facecolors='none' if marker!='x' else 'black')
        ax.set(title=f'Wing α = {alpha:g}°',xlabel='Semispan position η = 2y/b',xlim=(.08,1.02));ax.grid(alpha=.22)
    axes[0].set_ylabel('Wind-axis local loading, cl c / (S/b)')
    handles,labels=axes[0].get_legend_handles_labels();fig.legend(handles,labels,loc='outside lower center',ncols=4,fontsize=8)
    fig.suptitle('SA-14: explicit 4° incidence reconstruction vs pressure data\nPrimary Mach 0.19; unresolved force-field mesh dependence',fontsize=12)
    fig.savefig(D/'isae-sa14-incidence.png',dpi=160);fig.savefig(D/'isae-sa14-incidence.svg');plt.close(fig)
    print(out['status'],'54 reductions,18 frame pairs; max covariance',max_cov,flush=True)


if __name__=='__main__':main()
