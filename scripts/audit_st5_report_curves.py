"""Check the actual Part III Figures 28–29 against their archived static tables.

Extract original PDF vector vertices; no raster tracing or solver calls.
Duplicate trace identity uses source-to-source values, never OpenSwing values.
This source audit is not a newly selected primary acceptance scope.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import audit_st5_published_curves as source

ROOT,read,sha=source.ROOT,source.read,source.sha
# Immutable drawing indices, independently located by color and visible axes.
FIGURES=[(42,69,125,126,'st5-30lb_90_10','28b'),
         (42,162,218,219,'st5-20lb_90_10','28c'),
         (42,304,360,361,'st5-20lb_80_20','28d'),
         (43,1,57,58,'st5-roller-30lb_90_10','29a'),
         (43,94,150,151,'st5-roller-20lb_90_10','29b'),
         (43,236,292,293,'st5-roller-20lb_80_20','29c')]


def audit(out):
    import pymupdf
    target_path=out/'report-curves.json'
    assert not target_path.exists()
    catalog=read(ROOT/'docs/validation/aswing-authoritative-sources.json')
    entry=next(r for r in catalog['files'] if r['id']=='isae-part-3')
    pdf=ROOT/entry['local_pdf'];assert sha(pdf)==entry['sha256']
    doc=pymupdf.open(pdf);study=read(out/'plan.json');records=[]
    pins={str(pdf.relative_to(ROOT)):sha(pdf)}
    for page,axes,red,blue,case,figure in FIGURES:
        drawings=doc[page].get_drawings();background=drawings[axes]
        assert background['fill']==(1.,1.,1.) and background['items'][0][0]=='re'
        rect=background['rect']
        assert 208<rect.width<209 and 164<rect.height<165
        folder=Path(next(c['directory'] for c in study['cases'] if c['case']==case))
        plan=read(folder/'plan.json');tpath=Path(plan['target']);target=read(tpath)
        pins[str(tpath.relative_to(ROOT))]=sha(tpath)
        comparisons=[read(folder/f'run-{i}/level{i}/comparison.json') for i in (0,1)]
        for i in (0,1):
            p=folder/f'run-{i}/level{i}/comparison.json';pins[str(p.relative_to(ROOT))]=sha(p)
        span=target['beams'][0]['rows'][-1]['physical'][2]
        for beam,index,color in ((1,red,(1.,0.,0.)),(2,blue,(0.,0.,1.))):
            drawing=drawings[index];assert drawing['color']==color
            vertices=[]
            for item in drawing['items']:
                assert item[0]=='l'
                for p in item[1:]:
                    if not vertices or list(p)!=vertices[-1]:vertices.append(list(p))
            discarded=[p for p in vertices if p[0]<rect.x0]
            curve=[[(x-rect.x0)/rect.width,-5+50*(rect.y1-y)/rect.height]
                   for x,y in vertices if x>=rect.x0]
            block=next(b for b in target['beams'] if b['beam']==beam)
            original=[r for r in block['rows'] if r['printed_t']>=0]
            sample=[]
            for r in original:
                legacy=[float(t)*10**e for t,e in zip(r['raw_tokens'],block['header_exponents'])]
                factor=.112985/.0833333
                sample.append(dict(source_line=r['source_line'],x=r['physical'][2]/span,
                    legacy_Mx=source.mx(legacy)*factor,physical_Mx=source.mx(r['physical'])*factor))
            paired=[]
            for x,m in curve:
                distance=min(abs(x-s['x']) for s in sample)
                candidates=[s for s in sample if abs(x-s['x'])<=distance+1e-12]
                # Co-located incoming/outgoing traces are disambiguated solely
                # by original published and archived values; predictions are absent.
                chosen=min(candidates,key=lambda s:abs(s['legacy_Mx']-m))
                predictions=[]
                for comparison in comparisons:
                    matching=[r for r in comparison['rows']
                              if r['beam']==beam and r['source_line']==chosen['source_line']]
                    assert len(matching)==1
                    predictions.append(matching[0]['moment_body'][0]*factor)
                paired.append(dict(pdf_x=x,pdf_Mx_Nm=m,**chosen,
                    source_x_distance=distance,
                    source_coordinate_gate=distance<3e-6,
                    source_moment_gate=abs(chosen['legacy_Mx']-m)<.0003,
                    source_candidate_lines=[s['source_line'] for s in candidates],
                    current_Mx_Nm=predictions))
            envelope=max(abs(p['pdf_Mx_Nm']) for p in paired)
            records.append(dict(figure=figure,page=page+1,case=case,beam=beam,
                axes_pdf_points=list(rect),drawing_index=index,clipped_vertices=discarded,
                source_vertices=len(original),pdf_vertices=len(paired),samples=paired,
                source_coordinate_gates_pass=sum(p['source_coordinate_gate'] for p in paired),
                source_moment_gates_pass=sum(p['source_moment_gate'] for p in paired),
                maximum_source_x_distance=max(p['source_x_distance'] for p in paired),
                max_matlab_source_error_Nm=max(abs(p['legacy_Mx']-p['pdf_Mx_Nm']) for p in paired),
                max_physical_source_error_Nm=max(abs(p['physical_Mx']-p['pdf_Mx_Nm']) for p in paired),
                max_current_error_Nm=[max(abs(p['current_Mx_Nm'][i]-p['pdf_Mx_Nm']) for p in paired) for i in (0,1)],
                max_current_error_percent_of_curve_peak=[100*max(abs(p['current_Mx_Nm'][i]-p['pdf_Mx_Nm']) for p in paired)/envelope for i in (0,1)]))
    result=dict(observed_utc=datetime.now(timezone.utc).isoformat(),curves=records,pins=pins,
        scripts={str(p.relative_to(ROOT)):sha(p) for p in (Path(__file__),Path(source.__file__))},
        solver_calls=0,primary_passes_added=0,
        qualification='Original PDF Fig28b-d/29a-c joined-wing curves only. Cantilever black curves and independent acceptance/convergence remain separate. Source matching is evidence of plotted-data lineage, not authentication of modified executable constraints.')
    target_path.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps([{k:r[k] for k in ('figure','beam','pdf_vertices','max_matlab_source_error_Nm',
        'max_current_error_percent_of_curve_peak')} for r in records]))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    audit(p.parse_args().output.resolve())
