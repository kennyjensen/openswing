"""Independent Figure 7 in-plane stiffness audit and conditional physical replay.

The image corridor and exclusions come from the original drawing, before any
response is evaluated. No Bode value participates in reconstruction. Original
table stations, other properties and all excluded ordinates are preserved.
"""
import argparse
from pathlib import Path
from check_daedalus_load_sensitivity import ROOT, SOURCE, read
from daedalus_bounded_job import run

STUDY = ROOT / 'artifacts/daedalus-paper-stiffness-20261114'
PROPERTIES = ROOT / 'artifacts/daedalus-paper-properties-20261114'
PAPER = ROOT / 'reference/st4-node-placement-20261109/drela-1989-wing-loads.pdf'
DIP = 1.15737773741517


def trace(folder, args):
    import csv
    import numpy as np
    from PIL import Image
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from openswing.asw import parse_asw
    from check_daedalus_paper_properties import literal_wing_tables
    rgb = np.array(Image.open(PROPERTIES / 'inspect/figure-7.png').convert('RGB'))
    gray = rgb.min(axis=2)
    # Independently identified native black E_in curve. The excluded crossings
    # are deliberately wider than the line width; no use of the red overlay.
    anchors = np.array([[134,162],[180,162],[220,160],[260,160],[300,160],[324,160],
        [328,177],[331,194],[335,218],[339,231],[350,235],[370,244],[390,251],
        [410,256],[430,263],[450,271],[470,277],[490,284],[510,290],[530,299],
        [550,307],[561,311],[573,311],[577,321],[581,340],[585,352],[592,360],
        [610,361],[630,365],[650,370],[670,376],[680,378]], float)
    regions = [(134,327), (351,613), (649,680)]
    x0, x1, y0, scale = 132., 908., 438.5, 96.6
    weight, span = 230., 112.
    physical_scale = weight * span**2 / 5 / scale
    pixels = np.arange(134,681); guess = np.interp(pixels, anchors[:,0], anchors[:,1])
    ordinates = []; hits = []
    for x, y in zip(pixels, guess):
        candidates = np.arange(int(np.floor(y))-4, int(np.ceil(y))+5)
        dark = candidates[gray[candidates,x] < 160]
        hits.append(bool(len(dark)))
        ordinates.append(float(dark[np.argmin(abs(dark-y))]) if len(dark) else float(y))
    ordinates = np.array(ordinates); hits = np.array(hits)
    usable = np.array([any(lo <= x <= hi for lo,hi in regions) for x in pixels])
    assert hits[usable].mean() > .95
    station = (pixels-x0)/(x1-x0)*span/2
    stiffness = (y0-ordinates)*physical_scale
    text = (ROOT / 'examples/dae.asw').read_text(); tables = literal_wing_tables(text)
    model = parse_asw(text, beam_interpolation='drela-segspl-v1'); wing = model.beams[0]
    np.testing.assert_array_equal(wing.distributions['EInn'].values, np.array(tables['EInn'])[:,1])
    rows = []
    for t, original, line in tables['EInn']:
        x = x0+(x1-x0)*t/(span/2)
        clear = any(lo <= x <= hi for lo,hi in regions)
        y = float(np.interp(x,pixels,ordinates)) if clear else None
        value = (y0-y)*physical_scale if clear else original
        # Drawing-only envelope: +/-2 px horizontal and vertical, independently.
        # Includes steep-slope location uncertainty, not normalization/version errors.
        if clear:
            sample_x = np.r_[x-2,x+2,pixels[(pixels>=x-2)&(pixels<=x+2)]]
            sample_y = np.interp(sample_x,pixels,ordinates)
            lower = float((y0-max(sample_y)-2)*physical_scale)
            upper = float((y0-min(sample_y)+2)*physical_scale)
        else: lower = upper = None
        rows.append(dict(station_ft=t, source_line=int(line), original_EInn_lb_ft2=original,
            clear_native_curve=clear, paper_EInn_lb_ft2=value if clear else None,
            conditional_EInn_lb_ft2=value, paper_lower_lb_ft2=lower, paper_upper_lb_ft2=upper,
            paper_minus_original_percent=100*(value/original-1) if clear else None,
            source_pixel_x=x, source_pixel_y=y))
    with (folder / 'station-comparison.csv').open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    with (folder / 'trace.csv').open('x',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['pixel_x','pixel_y','station_ft','EInn_lb_ft2','clear_curve','dark_pixel_found'])
        writer.writerows(zip(pixels,ordinates,station,stiffness,usable,hits))
    fig,axes=plt.subplots(1,2,figsize=(13,5),layout='constrained')
    ax=axes[0];ax.imshow(rgb)
    for lo,hi in regions:
        mask=(pixels>=lo)&(pixels<=hi);ax.plot(pixels[mask],ordinates[mask],color='#2f7bff',lw=1.3)
    ax.set_xlim(120,700);ax.set_ylim(445,140);ax.set_axis_off()
    ax.set_title('Native black in-plane curve traced in blue\nCrossings and merged outer curves excluded')
    ax=axes[1];t=np.linspace(0,56,1001)
    ax.plot(t,wing.value('EInn',t)/1e6,color='#ff4a3d',label='Public dae.asw (SEGSPL)')
    for j,(lo,hi) in enumerate(regions):
        mask=(pixels>=lo)&(pixels<=hi)
        ax.plot(station[mask],stiffness[mask]/1e6,color='#2f7bff',label='Paper trace' if j==0 else None)
    clear=[r for r in rows if r['clear_native_curve']]
    x=np.array([r['station_ft'] for r in clear]);y=np.array([r['paper_EInn_lb_ft2'] for r in clear])/1e6
    lower=np.array([r['paper_lower_lb_ft2'] for r in clear])/1e6;upper=np.array([r['paper_upper_lb_ft2'] for r in clear])/1e6
    ax.errorbar(x,y,yerr=[y-lower,upper-y],fmt='.',color='#2f7bff',capsize=2,label='Original table stations; pixel bounds')
    ax.set(xlabel='Positive semispan station (ft)',ylabel='In-plane stiffness (million lb ft²)')
    ax.grid(alpha=.25);ax.legend(fontsize=8)
    fig.suptitle('Figure 7: Lref = 230 lb; b = 112 ft assumed\nInput comparison only; not identification of the later Bode model')
    fig.savefig(folder/'stiffness.png',dpi=150);fig.savefig(folder/'stiffness.svg');plt.close(fig)
    unique={r['station_ft']:r for r in clear}
    errors=np.array([r['paper_minus_original_percent'] for r in unique.values()])
    return dict(calibration=dict(x_zero=x0,x_one=x1,y_zero=y0,pixels_per_ordinate=scale,
        reference_weight_lb=weight,assumed_span_ft=span,normalization='5 EIn / (Lref b^2)'),
        anchors=anchors.tolist(),clear_pixel_regions=regions,dark_pixel_fraction=float(hits[usable].mean()),
        rows=rows,unique_clear_stations=len(unique),median_absolute_change_percent=float(np.median(abs(errors))),
        maximum_absolute_change_percent=float(max(abs(errors))),
        bound='Independent +/-2 horizontal and vertical rendered pixels. Does not cover scale, source-version, or unknown drawing errors.',
        qualification='Native curve traced independently of modern properties or Bode response. Root, crossings and merged outer curves are not reconstructed.')


def export_case(folder,args):
    import numpy as np
    from openswing.asw import parse_asw
    trace_result=read(STUDY/'trace/result.json');text=(ROOT/'examples/dae.asw').read_text()
    lines=text.splitlines(keepends=True);changed=[]
    for row in trace_result['rows']:
        if not row['clear_native_curve']:continue
        i=row['source_line']-1;tokens=lines[i].split()
        assert len(tokens)==3 and float(tokens[0])==row['station_ft']
        assert float(tokens[2])*1e6==row['original_EInn_lb_ft2']
        # Preserve existing knots and EIcc numbers. Header multiplier is 1e6.
        lines[i]=f" {tokens[0]}  {tokens[1]}  {row['conditional_EInn_lb_ft2']/1e6:.17g}\n"
        changed.append(i+1)
    modified=''.join(lines)
    old=parse_asw(text,beam_interpolation='drela-segspl-v1');new=parse_asw(modified,beam_interpolation='drela-segspl-v1')
    assert len(old.beams)==len(new.beams)
    for before,after in zip(old.beams,new.beams):
        assert before.index==after.index and set(before.distributions)==set(after.distributions)
        for name,table in before.distributions.items():
            np.testing.assert_array_equal(table.t,after.distributions[name].t)
            if before.index!=1 or name!='EInn':np.testing.assert_array_equal(table.values,after.distributions[name].values)
    assert all(a==b for i,(a,b) in enumerate(zip(text.splitlines(),modified.splitlines()),1) if i not in changed)
    path=folder/'dae-figure7-inplane-sampled.asw';path.write_text(modified)
    return dict(changed_lines=changed,changed_property='beam 1 EInn only',requires_new_trim=True,
        selected_before_response=True,interpolation='Original stations and SEGSPL; this samples the trace, not its full sharp-step shape.',
        qualification='Conditional partial historical-property reconstruction. Other properties, root and ambiguous stations remain literal. No mass changes and no Bode fitting.')


def setup(seed=None):
    import numpy as np
    from openswing.asw import parse_asw
    from openswing.source_airflow import SourceAirflowNetwork
    from openswing.equilibrium_state import restore,restore_physical_fields
    from openswing.time_state import read_condition
    original=read(SOURCE/'trim-6.7-1/state.json');packet=original if seed is None else read(seed);launch=packet['launch']
    model=parse_asw((STUDY/'case/dae-figure7-inplane-sampled.asw').read_text(),beam_interpolation='drela-segspl-v1')
    panels=dict(default=16,beams={k:dict(nodes=v[0]) for k,v in original['identity']['stations'].items()})
    n=SourceAirflowNetwork(model,panels,read_condition(launch['condition']),launch['gravity'],launch['loads'],
        operating_constraints=launch['released_constraints'],strut_mode=launch['strut_mode'],
        mesh_recipe='physical-breaks-v1',steady_trim=True)
    for k,(stations,indices) in n.station_nodes.items():
        np.testing.assert_array_equal(stations,original['identity']['stations'][str(k)][0])
    assert (n.nn,n.ne,n.ng,len(n.weights))==(108,103,82,5)
    x=restore_physical_fields(n,packet) if seed is None else restore(n,packet)
    return n,x


def replay(folder,args):
    # Reuse the already checked full-residual trim/response driver. Replacement
    # of its study-local factory is confined to this supervised child process.
    import check_daedalus_wing_peak_mass as driver
    driver.setup=setup;driver.STUDY=STUDY
    stage='trim' if args['stage']=='trim' else 'retrim_step'
    result=getattr(driver,stage)(folder,args)
    result['qualification']='Physical partial Figure 7 EInn reconstruction, with no residual offset; original full descriptor is only a preconditioner, not a rank certificate for the changed model.'
    return result


def report(folder,args):
    import csv
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import LogLocator,FuncFormatter,NullFormatter
    from check_daedalus_mesh_zeros import CHANNELS
    from check_daedalus_mesh_residual import accepted
    with (ROOT/'docs/validation/daedalus-rudder-four-outputs.csv').open() as stream:raw=list(csv.DictReader(stream))
    reference={ch:np.array(sorted((float(r['frequency_Hz']),float(r['reference_drawing_magnitude']))
        for r in raw if r['channel']==ch)) for ch in CHANNELS}
    rows=[];checks=[]
    for tag in ('low','dip','roll'):
        p=accepted(STUDY/f'{tag}-2');q=accepted(STUDY/f'{tag}-check')
        assert p['evaluated_state_accepted'] and q['evaluated_state_accepted']
        assert p['width']==.002 and q['width']==.004 and p['frequency_hz']==q['frequency_hz']
        assert p['physical_seed']==q['physical_seed']==str((STUDY/'trim-1/state.json').resolve())
        with np.load(STUDY/f'{tag}-2/arrays.npz') as data:left=dict(data)
        with np.load(STUDY/f'{tag}-check/arrays.npz') as data:right=dict(data)
        np.testing.assert_array_equal(left['state'],right['state'])
        difference=float(max(abs(left['output_correction']-right['output_correction'])/abs(left['output'])))
        assert difference<2e-7
        f=p['frequency_hz'];checks.append(dict(frequency_hz=f,first=f'{tag}-2',second=f'{tag}-check',
            first_residual=p['history'][-1]['complete_harmonic_residual'],
            second_residual=q['history'][-1]['complete_harmonic_residual'],
            width_output_correction_difference_relative=difference))
        for j,ch in enumerate(CHANNELS):
            target=float(np.exp(np.interp(np.log(f),np.log(reference[ch][:,0]),np.log(reference[ch][:,1]))))
            value=p['output_magnitude'][j];original=p['original_output_magnitude'][j]
            rows.append(dict(frequency_hz=f,channel=ch,original_magnitude=original,magnitude=value,
                reference_magnitude=target,change_from_original_percent=100*(value/original-1),
                reference_error_percent=100*(value/target-1)))
    n,x=setup(STUDY/'trim-1/state.json');residual,data=n.residual(x,detail=True)
    weight=float(sum(np.sum(record['mass']) for record in data['masses'])*n.model.constants[0])
    original_weight=read(ROOT/'artifacts/daedalus-wing-paper-20261113/static-and-pages-v3/result.json')['weight_lb']
    assert abs(weight-original_weight)<1e-10 and max(abs(residual))<1e-9
    root=data['r'][n.node(1,0)]
    trim_summary=dict(weight_lb=weight,alpha_deg=data['condition'].alpha,
        physical_trim_residual=float(max(abs(residual))),
        maximum_section_cl=max(s['cl'] for s in data['aero']['strips'] if s['cl'] is not None),
        wing_tip_height_above_root_ft=[float(data['r'][n.node(1,t),2]-root[2]) for t in (-56,56)])
    with (folder/'comparison.csv').open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    with (SOURCE/'report/comparison.csv').open() as stream:baseline=[r for r in csv.DictReader(stream) if float(r['speed_m_s'])==6.7]
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    for j,(ax,ch) in enumerate(zip(axes.flat,CHANNELS)):
        original=sorted((float(r['frequency_hz']),float(r['magnitude_display'])) for r in baseline if r['channel']==ch)
        ax.loglog(reference[ch][:,0],reference[ch][:,1],color='#333333',label='Drela published magnitude')
        ax.loglog([v[0] for v in original],[v[1] for v in original],color='#ff4a3d',label='Literal aircraft (retained sweep)')
        selected=[r for r in rows if r['channel']==ch]
        ax.loglog([r['frequency_hz'] for r in selected],[r['magnitude'] for r in selected],
            color='#ff9f1a',marker='o',linestyle='none',markersize=6,markeredgecolor='#333333',markeredgewidth=.6,
            label='Figure 7 EInn samples, physical retrim')
        ax.set_title(ch.replace('_',' ').title());ax.set_xlabel('Frequency (cycles/s)')
        ax.set_ylabel(('deg/s' if j<2 else 'deg')+' per F3 unit');ax.set_xlim(.1,10)
        for axis in (ax.xaxis,ax.yaxis):
            axis.set_major_locator(LogLocator(base=10));axis.set_minor_locator(LogLocator(base=10,subs=np.arange(2,10)))
            axis.set_major_formatter(FuncFormatter(lambda v,pos:f'{v:g}'));axis.set_minor_formatter(NullFormatter())
        ax.grid(which='major',color='#aaaaaa',alpha=.6);ax.grid(which='minor',color='#dddddd',alpha=.65)
        if j==0:ax.legend(fontsize=8)
    fig.suptitle('Daedalus: independently traced in-plane stiffness sensitivity\nPartial Figure 7 reconstruction; new results are three isolated frequency samples')
    fig.savefig(folder/'comparison.png',dpi=150);fig.savefig(folder/'comparison.svg');plt.close(fig)
    return dict(trim=trim_summary,paired_stencil_checks=checks,rows=rows,physically_retrimmed_frequencies=3,
        qualification='Only clear EInn ordinates sampled at original input knots change. Not the entire historical stiffness distribution, a new frequency sweep, or an authenticated Bode input.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['trace','export_case','trim','response','report'])
    parser.add_argument('--tag',required=True);parser.add_argument('--seed');parser.add_argument('--source')
    parser.add_argument('--state',choices=['state','next_state'],default='next_state')
    parser.add_argument('--frequency',type=float,default=DIP);parser.add_argument('--width',type=float,default=.002)
    parser.add_argument('--iterations',type=int,choices=[1,2],default=2)
    args=vars(parser.parse_args())
    inputs=[PAPER,ROOT/'examples/dae.asw',ROOT/'docs/validation/ISAE_STATUS.md',ROOT/'docs/validation/aswing-authoritative-sources.json',
        ROOT/'docs/validation/isae-st4-node-placement-sources-20261109.json',PROPERTIES/'inspect/figure-7.png']
    inputs+=list((ROOT/'openswing').glob('*.py'))
    inputs += [ROOT/'scripts'/name for name in ('check_daedalus_paper_properties.py','check_daedalus_wing_peak_mass.py',
        'check_daedalus_measured_mass.py','check_daedalus_mesh_zeros.py','check_daedalus_mesh_residual.py',
        'check_daedalus_structural_resolution.py','check_daedalus_source_operator.py')]
    folders=[]
    if args['stage']!='trace':folders+=[STUDY/'trace']
    if args['stage'] in ('trim','response','report'):
        folders += [STUDY/'case',SOURCE/'assembled-6.7']
        inputs += [SOURCE/'trim-6.7-1/state.json',SOURCE/'trim-6.7-1/trim-tangent.npz',SOURCE/'mass-6.7/layout.json',
            ROOT/'examples/dae-cruise-physical-mesh-project.json']
    if args['seed']:inputs += [Path(args['seed']).resolve()]
    if args['source']:folders += [STUDY/args['source']]
    if args['stage']=='report':
        folders += [STUDY/'trim-1',*[STUDY/f'{tag}-{suffix}' for tag in ('low','dip','roll') for suffix in ('2','check')]]
        inputs += [ROOT/'docs/validation/daedalus-rudder-four-outputs.csv',SOURCE/'report/comparison.csv',
            ROOT/'artifacts/daedalus-wing-paper-20261113/static-and-pages-v3/result.json']
    for folder in folders:inputs += [p for p in folder.iterdir() if p.suffix in ('.json','.npz','.asw','.csv')]
    worker=replay if args['stage'] in ('trim','response') else globals()[args['stage']]
    run(STUDY,args['tag'],inputs,worker,args,__file__)


if __name__=='__main__':main()
