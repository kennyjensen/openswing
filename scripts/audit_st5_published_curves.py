"""Trace archived ST-5 vector curves to their original tables and current states.

Read-only source audit. SVG curves and the MATLAB postprocessor are not a new
acceptance scope, and their interpretation does not authenticate a joint law.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
REV='f62943df20e9e4d7d9f50e070477b22426b5f865'
ARCHIVE=ROOT/'reference/isae-validation'/REV
BASE=ARCHIVE/'3 - Structure/CASE - ST5 Joined Wing'


def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def points(d):
    """Only the explicit straight-segment SVG grammar used by these curves."""
    tokens=re.findall(r'[A-Za-z]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?',d)
    i=0;command=None;x=y=0.;out=[]
    while i<len(tokens):
        if tokens[i].isalpha():command=tokens[i];i+=1
        assert command in ('m','M','l','L','h','H','v','V'), command
        relative=command.islower();kind=command.lower()
        if kind in ('m','l'):
            a,b=map(float,tokens[i:i+2]);i+=2
            x,y=(x+a,y+b) if relative else (a,b)
        elif kind=='h':
            a=float(tokens[i]);i+=1;x=x+a if relative else a
        else:
            a=float(tokens[i]);i+=1;y=y+a if relative else a
        out.append([x,y])
        if kind=='m':command='l' if relative else 'L'
    return out


def mx(values):
    # First row of (R1*R2*R3).T in the original plotting script.
    theta,psi=map(math.radians,(values[5],values[6]))
    return (math.cos(theta)*math.cos(psi)*values[7]-math.sin(psi)*values[8]
            +math.sin(theta)*math.cos(psi)*values[9])


def audit(out):
    assert not (out/'curve-audit.json').exists()
    manifest_path=ROOT/'reference/isae-validation/manifest.json';manifest=read(manifest_path)
    assert manifest['revision']==REV
    pins={};rows=[]
    def original(path):
        expected=manifest['files'][str(path.relative_to(ARCHIVE))]
        assert path.stat().st_size==expected['bytes'] and sha(path)==expected['sha256']
        pins[str(path.relative_to(ROOT))]=sha(path)
    study=read(out/'plan.json')
    for kind in ('Rigid_Joint','Link_Joint'):
        script=BASE/kind/('Rigid_joint.m' if kind=='Rigid_Joint' else 'Link_joint.m')
        original(script)
        script_text=script.read_text()
        assert 'lbft2Nm = 0.112985;' in script_text and 'inch2ft = 0.0833333;' in script_text
        for load in ('30lb_90_10','20lb_90_10','20lb_80_20'):
            case='st5-'+('roller-' if kind=='Link_Joint' else '')+load
            folder=Path(next(r['directory'] for r in study['cases'] if r['case']==case))
            plan=read(folder/'plan.json');target=read(Path(plan['target']))
            comparison=read(folder/'run-0/level0/comparison.json')
            for p in target['source_pins']:
                path=Path(p['path']).resolve()
                if path.is_relative_to(ARCHIVE):original(path)
            svg=BASE/kind/(('Link_Joint_' if kind=='Link_Joint' else '')+'JW1_'+load+'.svg')
            original(svg);root=ET.parse(svg).getroot()
            paths=[e for e in root.iter() if e.tag.endswith('path')]
            # The actual visible grid, not text glyph baselines or image margins.
            grid=[points(e.get('d')) for e in paths if 'stroke:#dfdfdf;' in e.get('style','')]
            xmin=min(p[0] for line in grid for p in line);xmax=max(p[0] for line in grid for p in line)
            ymin=min(p[1] for line in grid for p in line);ymax=max(p[1] for line in grid for p in line)
            # Inkscape exports differ slightly in axes extent; read each grid.
            assert xmin==730. and ymin==460. and 5070.<=xmax<=5100. and 3885.<=ymax<=3890.
            labels=[''.join(e.itertext()).strip() for e in root.iter() if e.tag.endswith('text')]
            assert '-5051015202530354045' in labels
            assert any('80% FW and 20% RW' in s or '90% FW and 10% RW' in s for s in labels)
            span=target['beams'][0]['rows'][-1]['physical'][2]
            for beam,color in ((1,'#ff0000'),(2,'#0000ff')):
                candidates=[e for e in paths if 'fill:none;stroke:'+color+';stroke-width:15;' in e.get('style','')
                            and len(points(e.get('d')))>10]
                assert len(candidates)==1
                raw=points(candidates[0].get('d'))
                clipped=[p for p in raw if p[0]<xmin]
                curve=[[(x-xmin)/(xmax-xmin),-5+50*(y-ymin)/(ymax-ymin)] for x,y in raw if x>=xmin]
                block=next(b for b in target['beams'] if b['beam']==beam)
                source_rows=[r for r in block['rows'] if r['printed_t']>=0]
                current_rows=[r for r in comparison['rows'] if r['beam']==beam and r['t_printed']>=0]
                assert len(curve)==len(source_rows)==len(current_rows), (case,beam,len(curve),len(source_rows))
                samples=[]
                for p,r,c in zip(curve,source_rows,current_rows):
                    physical=r['physical']
                    legacy=[float(t)*10**e for t,e in zip(r['raw_tokens'],block['header_exponents'])]
                    # Preserve the exact constants used in the plotting scripts.
                    factor=.112985/.0833333
                    samples.append(dict(source_line=r['source_line'],curve=p,
                        archived_x=physical[2]/span,physical_Mx_Nm=mx(physical)*factor,
                        matlab_Mx_Nm=mx(legacy)*factor,current_Mx_Nm=c['moment_body'][0]*factor))
                rows.append(dict(case=case,beam=beam,svg=str(svg.relative_to(ROOT)),path_id=candidates[0].get('id'),
                    retained_clipping_vertices=clipped,samples=samples,
                    maximum_x_difference=max(abs(s['curve'][0]-s['archived_x']) for s in samples),
                    maximum_physical_source_difference_Nm=max(abs(s['curve'][1]-s['physical_Mx_Nm']) for s in samples),
                    maximum_matlab_source_difference_Nm=max(abs(s['curve'][1]-s['matlab_Mx_Nm']) for s in samples),
                    maximum_current_difference_Nm=max(abs(s['curve'][1]-s['current_Mx_Nm']) for s in samples)))
    result=dict(observed_utc=datetime.now(timezone.utc).isoformat(),curves=rows,source_pins=pins,
        script_sha256=sha(Path(__file__)),manifest_sha256=sha(manifest_path),
        primary_passes_added=0,production_imports=0,solver_calls=0,
        qualification='Archived vector figures, not digitized paper pixels. Literal postprocessor and physically decoded moment conventions both retained. Similar curves do not identify an unobserved modified joint law.')
    (out/'curve-audit.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps([{k:r[k] for k in ('case','beam','maximum_x_difference',
          'maximum_physical_source_difference_Nm','maximum_matlab_source_difference_Nm','maximum_current_difference_Nm')} for r in rows]))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    audit(parser.parse_args().output.resolve())
