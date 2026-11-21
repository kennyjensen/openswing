"""Small serial audit of Figure 7 and literal Daedalus beam properties."""
import argparse
from pathlib import Path
from check_daedalus_load_sensitivity import ROOT, read
from daedalus_bounded_job import run

STUDY=ROOT/'artifacts/daedalus-paper-properties-20261114'
PAPER=ROOT/'reference/st4-node-placement-20261109/drela-1989-wing-loads.pdf'


def literal_wing_tables(source):
    """Independent parser for this literal beam's numeric tables and * scales."""
    active=False;columns=None;scales=[];tables={}
    for number,line in enumerate(source.splitlines(),1):
        line=line.split('#')[0].split('!')[0].strip();tokens=line.split()
        if not tokens:continue
        if not active:
            if tokens==['Beam','1']:active=True
            continue
        if tokens==['End']:break
        if tokens[0]=='t':
            columns=tokens;scales=[1.]*len(columns)
            for name in columns[1:]:assert name not in tables;tables[name]=[]
        elif tokens[0]=='*':
            scales=[float(v) for v in tokens[1:]];assert len(scales)==len(columns)
        elif columns:
            values=[float(v)*scale for v,scale in zip(tokens,scales)]
            assert len(tokens)==len(columns)
            for name,value in zip(columns[1:],values[1:]):tables[name].append([values[0],value,number])
    assert active and tables
    return tables


def inspect(folder,args):
    import numpy as np
    import pymupdf
    from openswing.asw import parse_asw
    text=(ROOT/'examples/dae.asw').read_text();model=parse_asw(text,beam_interpolation='drela-segspl-v1')
    wing=next(b for b in model.beams if b.index==1);tables=literal_wing_tables(text)
    checked={}
    for name,rows in tables.items():
        values=np.array(rows);actual=wing.distributions[name]
        np.testing.assert_array_equal(actual.t,values[:,0]);np.testing.assert_array_equal(actual.values,values[:,1])
        checked[name]=dict(samples=len(rows),source_lines=values[:,2].astype(int).tolist())
    t=np.unique(np.r_[np.linspace(0,56,1001),*[wing.distributions[k].t for k in ('EIcc','EInn','GJ','mg','chord')]])
    # Preserve both sides of every discontinuity in presentation arrays.
    double=sorted(set(v for k in ('EIcc','EInn','GJ','mg','chord') for v in wing.distributions[k].t
                      if list(wing.distributions[k].t).count(v)>1))
    stations=[];sides=[]
    for v in t:
        if v in double:stations.append(v);sides.append('left')
        stations.append(v);sides.append('right')
    stations=np.array(stations);sides=np.array(sides)
    properties={}
    for name in ('EIcc','EInn','GJ','mg','chord','twist','Xax','Ccg'):
        values=wing.value(name,stations)
        left=sides=='left';values[left]=wing.value(name,stations[left],side='left')
        properties[name]=values
    np.savez_compressed(folder/'properties.npz',stations=stations,**properties)
    with pymupdf.open(PAPER) as pdf:
        page=pdf[7];rectangle=pymupdf.Rect(315,72,550,252)
        page.get_pixmap(matrix=pymupdf.Matrix(4,4),clip=rectangle).save(str(folder/'figure-7.png'))
        size=list(page.rect)
    samples=[]
    for station in (0,7,14,28,42,49,56):
        for side in ('left','right'):
            samples.append(dict(station_ft=station,side=side,**{k:float(wing.value(k,station,side=side)) for k in properties}))
    return dict(reference_weight_lb=230,span_ft=float(model.reference[0,2]),pdf_page=8,printed_page=329,
        clip_pdf_points=list(rectangle),render_scale=4,pdf_page_rectangle=size,
        independently_checked_tables=checked,table_count=len(checked),literal_samples=samples,
        qualification='Input-property audit only; no solver, aircraft parameter change, or identification of historical Bode settings.')


def compare(folder,args):
    import csv
    import numpy as np
    from PIL import Image
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from openswing.asw import parse_asw
    original=STUDY/'inspect';assert read(original/'terminal.json')['returncode']==0
    model=parse_asw((ROOT/'examples/dae.asw').read_text(),beam_interpolation='drela-segspl-v1')
    wing=next(b for b in model.beams if b.index==1)
    with np.load(original/'properties.npz') as data:properties=dict(data)
    rgb=np.array(Image.open(original/'figure-7.png').convert('RGB'));gray=rgb.min(axis=2)
    # Fixed manual axis calibration from the visible ticks, never a model fit.
    x0,x1=132.,908.;zero,per_unit=438.5,96.6
    span=112.;weight=230.;half=span/2
    # Independent visual trace of the lowest (mg) curve. These image points
    # define search corridors, without consulting model values or Bode output.
    anchors=np.array([[134,410],[150,416],[180,417],[220,417],[260,417],[300,417],
        [306,416],[311,396],[316,371],[323,357],[328,366],[333,393],[339,414],[346,416],
        [380,416],[420,416],[460,415],[480,415],[510,414],[519,409],[540,415],[560,417],
        [600,419],[640,420],[680,421],[698,421],[706,405],[712,398],[719,409],[729,425],
        [760,427],[800,430],[850,433],[905,434]],float)
    pixels=np.arange(134,906);guess=np.interp(pixels,anchors[:,0],anchors[:,1]);trace=[];found=[]
    for x,y in zip(pixels,guess):
        candidates=np.arange(max(0,int(np.floor(y))-5),min(len(gray),int(np.ceil(y))+6))
        dark=candidates[gray[candidates,x]<160]
        hit=bool(len(dark));found.append(hit)
        trace.append(float(dark[np.argmin(abs(dark-y))]) if hit else float(y))
    trace=np.array(trace);found=np.array(found)
    assert found.mean()>.95,found.mean()
    fraction=(pixels-x0)/(x1-x0);station=half*fraction
    ordinate=(zero-trace)/per_unit;paper_mg=ordinate*weight/span
    current=wing.value('mg',station)
    peaks=[]
    for lower,upper in ((300,346),(698,734)):
        mask=(pixels>=lower)&(pixels<=upper);x=pixels[mask];s=station[mask];v=paper_mg[mask]
        baseline=np.interp(x,[x[0],x[-1]],[v[0],v[-1]])
        excess=np.maximum(0.,v-baseline);index=int(np.argmax(v))
        # An ordinate shift bounded by two rendered pixels at every trace
        # point and its end baseline gives this conservative area bound.
        ordinate_uncertainty=2/per_unit*weight/span
        area=float(np.trapezoid(excess,s))
        area_bound=float(2*ordinate_uncertainty*(s[-1]-s[0]))
        peaks.append(dict(pixel_window=[lower,upper],station_range_ft=[float(s[0]),float(s[-1])],
            peak_station_ft=float(s[index]),peak_paper_weight_per_span_lb_ft=float(v[index]),
            modern_weight_per_span_lb_ft=float(wing.value('mg',s[index])),
            excess_weight_above_local_baseline_lb=area,conservative_two_pixel_area_bound_lb=area_bound))
    columns=list(zip(station,fraction,trace,paper_mg,current,found))
    with (folder/'mass-trace.csv').open('x',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['station_ft_assuming_112_ft_span','fraction_semispan',
            'trace_pixel_y','paper_weight_lb_ft','current_weight_lb_ft','dark_pixel_found']);writer.writerows(columns)
    # Chord width is measured independently from the two planform strokes.
    # Converting pixels to feet assumes equal scales in the drawing and b=112.
    chord_pixels=np.arange(140,900);widths=[]
    for x in chord_pixels:
        dark=np.flatnonzero(gray[510:590,x]<160)+510
        assert len(dark)>=2
        widths.append(float(dark[-1]-dark[0]))
    chord_station=(chord_pixels-x0)/(x1-x0)*half
    paper_chord=np.array(widths)*half/(x1-x0)
    projected_chord=wing.value('chord',chord_station)*np.cos(np.deg2rad(wing.value('twist',chord_station)))
    fig=plt.figure(figsize=(13,8),layout='constrained');grid=fig.add_gridspec(2,2,width_ratios=[1.3,1])
    ax=fig.add_subplot(grid[:,0]);ax.imshow(rgb);t=properties['stations'];x=x0+(x1-x0)*t/half
    for name,factor,color,label,style in [
        ('EInn',5.,'#ff4a3d','5 EInn / (Lref b²)','-'),
        ('EIcc',100.,'#ff9f1a','100 EIcc / (Lref b²)','-'),
        ('GJ',100.,'#ffd166','100 GJ / (Lref b²): conditional display','--')]:
        y=zero-per_unit*factor*properties[name]/(weight*span**2)
        ax.plot(x,y,color=color,label=label,lw=1.6,ls=style)
    ax.plot(x,zero-per_unit*properties['mg']/(weight/span),color='#2f7bff',label='mg / (Lref/b)',lw=1.6)
    ax.plot(x,zero-per_unit*properties['GJ']/(weight*span**2),color='#9b5de5',label='GJ / (Lref b²): literal label',lw=1.2,ls=':')
    ax.set_xlim(60,920);ax.set_ylim(590,25);ax.set_axis_off();ax.legend(loc='lower center',fontsize=8)
    ax.set_title('Figure 7 and current file properties\nGJ label/scale conflict remains unresolved')
    am=fig.add_subplot(grid[0,1]);am.plot(station,paper_mg,color='#333333',label='Paper raster trace')
    am.plot(t,properties['mg'],color='#2f7bff',label='Literal dae.asw')
    for peak in peaks:am.axvspan(*peak['station_range_ft'],color='#ff9f1a',alpha=.12)
    am.set_xlabel('Positive semispan station (ft)');am.set_ylabel('Weight per span (lb/ft)')
    am.set_title('Localized mass peaks absent from modern file');am.legend(fontsize=8);am.grid(alpha=.25)
    ac=fig.add_subplot(grid[1,1]);ac.plot(chord_station,paper_chord,color='#333333',label='Paper outline, assumed equal scales')
    ac.plot(chord_station,projected_chord,color='#6dd36f',label='Current projected chord')
    ac.set_xlabel('Positive semispan station (ft)');ac.set_ylabel('Planform chord (ft)');ac.grid(alpha=.25);ac.legend(fontsize=8)
    ac.set_title('Planform comparison is limited by drawing scale')
    fig.suptitle('Published reference scale Lref = 230 lb; dimensional reconstruction assumes b = 112 ft\nNo physical property adjusted; drawing comparison does not identify the later Bode setup')
    fig.savefig(folder/'properties.png',dpi=150);fig.savefig(folder/'properties.svg');plt.close(fig)
    np.savez_compressed(folder/'traces.npz',pixels=pixels,trace=trace,found=found,station=station,
        paper_mg=paper_mg,current_mg=current,chord_station=chord_station,paper_chord=paper_chord,projected_chord=projected_chord)
    return dict(calibration=dict(x_zero=x0,x_one=x1,y_zero=zero,pixels_per_ordinate=per_unit,
        assumed_full_span_ft=span,reference_weight_lb=weight,source='Visible axis tick positions; no response/model fit'),
        manual_mass_trace_anchors=anchors.tolist(),dark_pixel_fraction=float(found.mean()),peaks=peaks,
        four_joint_excess_weight_estimate_lb=2*sum(p['excess_weight_above_local_baseline_lb'] for p in peaks),
        four_joint_conservative_pixel_bound_lb=2*sum(p['conservative_two_pixel_area_bound_lb'] for p in peaks),
        modern_wing_point_weight_records=[row.tolist() for row in model.records['weight'] if int(row[0])==1],
        root_nondimensional=dict(inplane_5=float(5*wing.value('EInn',0)/(weight*span**2)),
            outplane_100=float(100*wing.value('EIcc',0)/(weight*span**2)),
            torsion_literal=float(wing.value('GJ',0)/(weight*span**2)),
            torsion_times_100=float(100*wing.value('GJ',0)/(weight*span**2)),weight=float(wing.value('mg',0)/(weight/span))),
        qualifications=['Historical paper and modern input are distinct; no new native-ASWING pass.',
            'The torsion curve resembles a 100x display, but the scanned legend does not state that factor. No physical GJ change is inferred.',
            'Mass peaks are raster estimates above a local end-to-end baseline, with neither original mass tables nor mass-centroid data.',
            'The two-pixel bound covers only trace/endpoint placement, not unknown drawing or model-systematic errors.',
            'Dimensional weight estimates assume the modern 112 ft span; plotted Lref=230 lb is a normalization, distinct from the 240 lb flight case.'])


def integrate(folder,args):
    import numpy as np
    from openswing.asw import parse_asw
    from check_daedalus_mesh_residual import accepted
    accepted(STUDY/'compare');result=read(STUDY/'compare/result.json')
    with np.load(STUDY/'compare/traces.npz') as saved:data=dict(saved)
    c=result['calibration'];x=(data['pixels']-c['x_zero'])/(c['x_one']-c['x_zero'])
    ordinate=(c['y_zero']-data['trace'])/c['pixels_per_ordinate'];weight=c['reference_weight_lb']
    # Two symmetric halves: W = Lref * integral_0^1(mg/(Lref/b)) d(2s/b).
    # Thus the inferred integrated weight does not depend on assumed span.
    x=np.r_[0.,x,1.];ordinate=np.r_[ordinate[0],ordinate,ordinate[-1]]
    paper_weight=float(weight*np.trapezoid(ordinate,x))
    ordinate_bound=2/c['pixels_per_ordinate'];paper_pixel_bound=weight*ordinate_bound
    model=parse_asw((ROOT/'examples/dae.asw').read_text(),beam_interpolation='drela-segspl-v1')
    wing=next(b for b in model.beams if b.index==1);knots=np.unique(wing.distributions['mg'].t)
    integrals=[]
    for order in (3,4):
        gx,gw=np.polynomial.legendre.leggauss(order)
        q=(knots[:-1,None]+knots[1:,None])/2+(knots[1:,None]-knots[:-1,None])/2*gx
        val=wing.value('mg',q);w=(knots[1:]-knots[:-1])/2
        integrals.append(float(2*np.sum(w*np.sum(val*gw,axis=1))))
    assert abs(integrals[1]-integrals[0])<1e-12
    old=read(ROOT/'artifacts/daedalus-wing-paper-20261113/static-and-pages-v3/result.json')
    coarse=next(row['weight_lb'] for row in old['beam_weights_lb'] if row['beam']==1)
    return dict(paper_trace_integrated_wing_weight_lb=paper_weight,
        conservative_two_pixel_ordinate_bound_lb=float(paper_pixel_bound),
        current_continuous_wing_weight_lb=integrals[-1],current_saved_discrete_wing_weight_lb=coarse,
        quadrature_order_difference_lb=abs(integrals[1]-integrals[0]),
        paper_minus_current_continuous_lb=paper_weight-integrals[-1],
        visible_peak_excess_weight_lb=result['four_joint_excess_weight_estimate_lb'],
        visible_peak_pixel_bound_lb=result['four_joint_conservative_pixel_bound_lb'],
        dimensional_peak_stations_assume_full_span_ft=c['assumed_full_span_ft'],
        integrated_weight_depends_on_span=False,
        qualification='Raster-derived historical mass estimates; two-pixel bound is not a statistical confidence interval and excludes drawing/systematic errors. Constant extension over the untraced endpoint slivers. No property or Bode run was changed.')


def measured(folder,args):
    import hashlib
    import pymupdf
    reference=ROOT/'reference/daedalus-weight-20261114';pdf_path=reference/'cruz-daedalus-weight.pdf'
    receipt=read(reference/'receipt.json')
    assert hashlib.sha256(pdf_path.read_bytes()).hexdigest()==receipt['sha256']
    with pymupdf.open(pdf_path) as pdf:
        text='\n\n'.join(f'PDF PAGE {i+1}\n'+page.get_text() for i,page in enumerate(pdf))
        for i in (1,2):pdf[i].get_pixmap(matrix=pymupdf.Matrix(1.5,1.5)).save(str(folder/f'cruz-page-{i+1}.png'))
        pages=len(pdf)
    (reference/'cruz-daedalus-weight.txt').write_text(text)
    old=read(ROOT/'artifacts/daedalus-wing-paper-20261113/static-and-pages-v3/result.json')
    weights={r['beam']:r['weight_lb'] for r in old['beam_weights_lb']}
    current_empty=old['weight_lb']-165.-12.
    # Printed Table 1 rounded totals. They require visual verification before
    # this comparison is published; kg/gram conversion is not inferred by OCR.
    comparisons=[dict(component=name,published_measured_lb=target,current_model_lb=current,
        current_minus_measured_lb=current-target,current_relative_difference_percent=100*(current/target-1))
        for name,target,current in [('Wing',41.85,weights[1]),('Elevator',1.19,weights[2]),
            ('Rudder',1.37,weights[3]),('Fuselage and remaining equipment',24.09,current_empty-sum(weights[i] for i in (1,2,3))),
            ('Empty aircraft',68.50,current_empty)]]
    return dict(source_receipt=receipt,pages=pages,text_sha256=hashlib.sha256(text.encode()).hexdigest(),
        journal='Technical Soaring',volume=14,issue=1,year=1990,conference_year=1989,
        table_pdf_page=3,table_printed_page=4,comparisons=comparisons,
        qualifications=['Primary measured construction weights, not authenticated inputs to the 2008 Bode calculation.',
            'Fuselage comparison includes the modern propeller and gearbox point weights; pilot and water are excluded.',
            'Rounded printed component subtotals differ from the rounded total by 0.01 lb.',
            'No missing component or additional mass location is inferred uniquely from these totals.'])


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=['inspect','compare','integrate','measured'])
    parser.add_argument('--tag',required=True);args=vars(parser.parse_args())
    inputs=[PAPER,ROOT/'examples/dae.asw',ROOT/'docs/validation/ISAE_STATUS.md',ROOT/'docs/validation/aswing-authoritative-sources.json',
        ROOT/'docs/validation/isae-st4-node-placement-sources-20261109.json']
    inputs+=list((ROOT/'openswing').glob('*.py'))
    if args['stage']=='compare':inputs += [p for p in (STUDY/'inspect').iterdir() if p.is_file()]
    if args['stage']=='integrate':
        inputs += [p for p in (STUDY/'compare').iterdir() if p.is_file()]
        inputs += [ROOT/'scripts/check_daedalus_mesh_residual.py',ROOT/'artifacts/daedalus-wing-paper-20261113/static-and-pages-v3/result.json']
    if args['stage']=='measured':
        inputs += [ROOT/'reference/daedalus-weight-20261114'/name for name in ('cruz-daedalus-weight.pdf','receipt.json')]
        inputs += [ROOT/'artifacts/daedalus-wing-paper-20261113/static-and-pages-v3/result.json']
    run(STUDY,args['tag'],inputs,globals()[args['stage']],args,__file__)


if __name__=='__main__':main()
